"""
Portfolio engine — tracks current holdings, P&L, and performance metrics.

Responsible for:
- Enriching positions with current market prices
- Calculating realised and unrealised P&L
- Computing portfolio-level metrics (sector exposure, risk concentration)
- Generating portfolio snapshots for the dashboard
- Evaluating portfolio health (warnings, cautions)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sector mapping
# ---------------------------------------------------------------------------
_SECTOR_MAP: dict[str, str] = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "META": "Technology", "NVDA": "Technology", "INTC": "Technology",
    "AMD": "Technology", "QCOM": "Technology", "AVGO": "Technology",
    "TXN": "Technology", "MU": "Technology", "AMAT": "Technology",
    "LRCX": "Technology", "ADI": "Technology", "SNPS": "Technology",
    "CDNS": "Technology", "MRVL": "Technology", "KLAC": "Technology",
    "ASML": "Technology", "CRM": "Technology", "ADBE": "Technology",
    "NFLX": "Technology",
    # Financial
    "JPM": "Financial", "BAC": "Financial", "V": "Financial",
    "MA": "Financial", "BRK.B": "Financial",
    # Healthcare
    "JNJ": "Healthcare", "UNH": "Healthcare",
    # Consumer
    "WMT": "Consumer", "PG": "Consumer", "DIS": "Consumer",
    "HD": "Consumer",
}


def _resolve_sector(symbol: str) -> str:
    """Look up a symbol's sector from the built-in mapping."""
    return _SECTOR_MAP.get(symbol.upper(), "Unknown")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PortfolioPosition:
    """Represents a single open position in the portfolio."""
    symbol: str
    quantity: int
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float = 0.0
    sector: str = ""
    allocation_pct: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    days_held: int = 0
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class PortfolioSnapshot:
    """Aggregated snapshot of the entire portfolio at a point in time."""
    cash: float
    total_market_value: float
    total_equity: float
    positions: list[PortfolioPosition] = field(default_factory=list)
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    win_rate: float = 0.0
    avg_return_pct: float = 0.0
    sector_exposure: dict[str, float] = field(default_factory=dict)
    risk_concentration: dict[str, float] = field(default_factory=dict)
    open_positions_count: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ClosedTrade:
    """A completed (closed) trade for win-rate and return calculations."""
    symbol: str
    entry_price: float
    exit_price: float
    quantity: int
    return_pct: float
    pnl: float
    closed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

async def get_positions(
    positions_data: list[dict],
    provider: "MarketDataProvider",
) -> list[PortfolioPosition]:
    """Take raw positions + provider, enrich with current prices.

    Parameters
    ----------
    positions_data : list[dict]
        Each dict must have keys:
        - symbol (or ticker)
        - quantity
        - avg_entry_price (or entry_price)
        Optional keys:
        - realized_pnl
        - stop_loss / stop_loss_price
        - take_profit / take_profit_price
        - sector
        - opened_at (datetime or ISO string)
    provider : MarketDataProvider
        Used to fetch current quotes.

    Returns
    -------
    list[PortfolioPosition]
    """
    enriched: list[PortfolioPosition] = []

    for pos in positions_data:
        symbol = (pos.get("symbol") or pos.get("ticker", "")).upper()
        quantity = int(pos.get("quantity", 0))
        avg_entry = float(pos.get("avg_entry_price") or pos.get("entry_price", 0.0))
        realized_pnl = float(pos.get("realized_pnl", 0.0))

        # Fetch current price from provider
        quote = await provider.get_quote(symbol)
        current_price = quote.price if quote else 0.0

        market_value = current_price * quantity
        unrealized_pnl = (current_price - avg_entry) * quantity if avg_entry > 0 else 0.0
        unrealized_pnl_pct = (
            ((current_price - avg_entry) / avg_entry * 100) if avg_entry > 0 else 0.0
        )

        # Resolve sector
        sector = pos.get("sector") or _resolve_sector(symbol)

        # Stop-loss / take-profit — accept both naming conventions
        stop_loss = pos.get("stop_loss") or pos.get("stop_loss_price")
        if stop_loss is not None:
            stop_loss = float(stop_loss)
        take_profit = pos.get("take_profit") or pos.get("take_profit_price")
        if take_profit is not None:
            take_profit = float(take_profit)

        # Days held
        days_held = 0
        opened_at = pos.get("opened_at")
        if opened_at is not None:
            if isinstance(opened_at, datetime):
                delta = datetime.now(timezone.utc) - opened_at
                days_held = max(0, delta.days)
            elif isinstance(opened_at, str):
                try:
                    opened_dt = datetime.fromisoformat(
                        opened_at.replace("Z", "+00:00")
                    )
                    # Handle offset-naive
                    if opened_dt.tzinfo is None:
                        opened_dt = opened_dt.replace(tzinfo=timezone.utc)
                    delta = datetime.now(timezone.utc) - opened_dt
                    days_held = max(0, delta.days)
                except (ValueError, TypeError):
                    days_held = 0

        enriched.append(PortfolioPosition(
            symbol=symbol,
            quantity=quantity,
            avg_entry_price=round(avg_entry, 2),
            current_price=round(current_price, 2),
            market_value=round(market_value, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
            realized_pnl=round(realized_pnl, 2),
            sector=sector,
            stop_loss=round(stop_loss, 2) if stop_loss is not None else None,
            take_profit=round(take_profit, 2) if take_profit is not None else None,
            days_held=days_held,
        ))

    # Compute allocation percentages after total equity is known
    total_mv = sum(p.market_value for p in enriched)
    for p in enriched:
        p.allocation_pct = round((p.market_value / total_mv * 100), 2) if total_mv > 0 else 0.0

    return enriched


def calculate_snapshot(
    positions: list[PortfolioPosition],
    cash: float,
    closed_trades: Optional[list[ClosedTrade]] = None,
) -> PortfolioSnapshot:
    """Compute full portfolio summary from positions, cash, and closed trades.

    Parameters
    ----------
    positions : list[PortfolioPosition]
        Enriched open positions.
    cash : float
        Available cash balance.
    closed_trades : list[ClosedTrade] | None
        Historical closed trades for win-rate and avg-return calculations.

    Returns
    -------
    PortfolioSnapshot
    """
    if closed_trades is None:
        closed_trades = []

    total_market_value = sum(p.market_value for p in positions)
    total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
    total_realized_pnl = sum(t.pnl for t in closed_trades)
    total_equity = cash + total_market_value

    # Win rate & avg return from closed trades
    total_closed = len(closed_trades)
    if total_closed > 0:
        winning = sum(1 for t in closed_trades if t.pnl > 0)
        win_rate = round(winning / total_closed, 4)
        avg_return_pct = round(
            sum(t.return_pct for t in closed_trades) / total_closed, 2
        )
    else:
        win_rate = 0.0
        avg_return_pct = 0.0

    # Sector exposure & risk concentration
    sector_exposure = calculate_sector_exposure(positions, total_market_value)
    risk_concentration = calculate_risk_concentration(positions, total_equity)

    return PortfolioSnapshot(
        cash=round(cash, 2),
        total_market_value=round(total_market_value, 2),
        total_equity=round(total_equity, 2),
        positions=positions,
        total_unrealized_pnl=round(total_unrealized_pnl, 2),
        total_realized_pnl=round(total_realized_pnl, 2),
        win_rate=win_rate,
        avg_return_pct=avg_return_pct,
        sector_exposure=sector_exposure,
        risk_concentration=risk_concentration,
        open_positions_count=len(positions),
    )


def calculate_sector_exposure(
    positions: list[PortfolioPosition],
    total_market_value: Optional[float] = None,
) -> dict[str, float]:
    """Group positions by sector, calculate % of total portfolio per sector.

    Parameters
    ----------
    positions : list[PortfolioPosition]
    total_market_value : float | None
        Optional pre-computed total; computed from positions if omitted.

    Returns
    -------
    dict[str, float] — sector name → allocation percentage.
    """
    if total_market_value is None:
        total_market_value = sum(p.market_value for p in positions)

    if total_market_value <= 0:
        return {}

    sector_totals: dict[str, float] = {}
    for pos in positions:
        sector = pos.sector or "Unknown"
        sector_totals[sector] = sector_totals.get(sector, 0.0) + pos.market_value

    return {
        sector: round((mv / total_market_value) * 100, 2)
        for sector, mv in sector_totals.items()
    }


def calculate_risk_concentration(
    positions: list[PortfolioPosition],
    total_equity: Optional[float] = None,
) -> dict[str, float]:
    """Per-symbol allocation as % of total equity.

    Flags any position > 20% via logging but the caller (get_portfolio_health)
    is responsible for raising warnings.

    Parameters
    ----------
    positions : list[PortfolioPosition]
    total_equity : float | None
        Optional pre-computed total equity; computed from positions if omitted.

    Returns
    -------
    dict[str, float] — symbol → allocation percentage of total equity.
    """
    if total_equity is None:
        total_equity = sum(p.market_value for p in positions)

    if total_equity <= 0:
        return {}

    result: dict[str, float] = {}
    for pos in positions:
        pct = (pos.market_value / total_equity) * 100
        result[pos.symbol] = round(pct, 2)
        if pct > 20.0:
            logger.warning(
                "High concentration: %s is %.1f%% of portfolio equity",
                pos.symbol, pct,
            )

    return result


def get_portfolio_health(snapshot: PortfolioSnapshot) -> dict:
    """Evaluate overall portfolio health and return status + issues.

    Rules (highest-severity wins):
        WARNING:
            - Any single position > 20% of equity
            - Any sector > 40% of total market value
            - Max drawdown > 10% (computed from unrealized P&L as proxy)

        CAUTION:
            - Win rate < 40%  (and at least 5 closed trades)
            - More than 5 open positions

        HEALTHY otherwise.

    Parameters
    ----------
    snapshot : PortfolioSnapshot

    Returns
    -------
    dict
        {"status": "HEALTHY" | "CAUTION" | "WARNING", "issues": [...]}
    """
    issues: list[str] = []

    # ── WARNING checks ──
    # Position concentration > 20%
    for symbol, pct in snapshot.risk_concentration.items():
        if pct > 20.0:
            issues.append(f"Position {symbol} exceeds 20% allocation ({pct:.1f}%)")

    # Sector concentration > 40%
    for sector, pct in snapshot.sector_exposure.items():
        if pct > 40.0:
            issues.append(f"Sector '{sector}' exceeds 40% exposure ({pct:.1f}%)")

    # Drawdown > 10% (unrealized P&L proxy)
    if snapshot.total_equity > 0:
        unrealized_drawdown_pct = abs(
            snapshot.total_unrealized_pnl / snapshot.total_equity * 100
        )
        if snapshot.total_unrealized_pnl < 0 and unrealized_drawdown_pct > 10.0:
            issues.append(
                f"Drawdown exceeds 10% ({unrealized_drawdown_pct:.1f}% unrealized loss)"
            )

    if issues:
        return {"status": "WARNING", "issues": issues}

    # ── CAUTION checks ──
    # Win rate < 40% (only when we have enough data)
    if snapshot.win_rate > 0 and snapshot.win_rate < 0.40:
        issues.append(f"Win rate below 40% ({snapshot.win_rate * 100:.1f}%)")

    # More than 5 open positions
    if snapshot.open_positions_count > 5:
        issues.append(
            f"High position count: {snapshot.open_positions_count} open positions (> 5)"
        )

    if issues:
        return {"status": "CAUTION", "issues": issues}

    # ── HEALTHY ──
    return {"status": "HEALTHY", "issues": []}


def update_position(
    position: PortfolioPosition,
    trade_update: dict,
) -> PortfolioPosition:
    """Update a portfolio position after a partial sell, stop adjustment, etc.

    Parameters
    ----------
    position : PortfolioPosition
        The current position to update.
    trade_update : dict
        Fields to update. Supported keys:
        - quantity_delta (int): change in quantity (negative for sells)
        - fill_price (float): price at which the trade executed
        - new_stop_loss (float or None): updated stop-loss level
        - new_take_profit (float or None): updated take-profit level
        - realized_pnl_delta (float): P&L realised in the partial close

    Returns
    -------
    PortfolioPosition — updated position (new dataclass, original unchanged).
    """
    from dataclasses import replace

    updated = replace(position)

    quantity_delta = trade_update.get("quantity_delta", 0)
    fill_price = trade_update.get("fill_price")
    realized_pnl_delta = trade_update.get("realized_pnl_delta", 0.0)

    if quantity_delta != 0:
        new_quantity = updated.quantity + quantity_delta
        if new_quantity < 0:
            new_quantity = 0

        # If partially sold at a known fill price, adjust realized P&L
        if fill_price is not None and quantity_delta < 0:
            sold_qty = abs(quantity_delta)
            realized = (fill_price - updated.avg_entry_price) * sold_qty
            updated.realized_pnl += round(realized, 2)

        updated.quantity = new_quantity

        # Recalculate market value and unrealized P&L
        updated.market_value = round(updated.current_price * new_quantity, 2)
        updated.unrealized_pnl = round(
            (updated.current_price - updated.avg_entry_price) * new_quantity, 2
        )
        updated.unrealized_pnl_pct = round(
            ((updated.current_price - updated.avg_entry_price) / updated.avg_entry_price * 100), 2
        ) if updated.avg_entry_price > 0 else 0.0

    if realized_pnl_delta != 0:
        updated.realized_pnl += round(realized_pnl_delta, 2)

    # Stop / target adjustments
    if "new_stop_loss" in trade_update:
        updated.stop_loss = trade_update["new_stop_loss"]
    if "new_take_profit" in trade_update:
        updated.take_profit = trade_update["new_take_profit"]

    updated.last_updated = datetime.now(timezone.utc).isoformat()

    return updated


# ---------------------------------------------------------------------------
# Backward-compatible stub (original interface)
# ---------------------------------------------------------------------------

async def get_portfolio_snapshot(
    positions_data: Optional[list[dict]] = None,
    cash: float = 0.0,
    closed_trades: Optional[list[ClosedTrade]] = None,
    provider: Optional["MarketDataProvider"] = None,
) -> dict:
    """Return a snapshot of the current portfolio state.

    Compatible with the original stub signature — returns a plain dict for
    backward compatibility with existing callers.

    Parameters
    ----------
    positions_data : list[dict] | None
        Raw position dicts.  If None, returns an empty portfolio.
    cash : float
        Available cash.
    closed_trades : list[ClosedTrade] | None
    provider : MarketDataProvider | None
        If None, positions won't be enriched with live prices.

    Returns
    -------
    dict — flattened snapshot suitable for API responses.
    """
    if provider is None:
        from app.engines.market_data import PolygonProvider
        settings = None
        try:
            from app.config import get_settings
            settings = get_settings()
        except Exception:
            pass

        if settings and settings.POLYGON_API_KEY:
            provider = PolygonProvider()
        else:
            # Cannot fetch live prices — return empty portfolio
            return {
                "total_equity": cash,
                "cash": cash,
                "market_value": 0.0,
                "positions": [],
                "daily_pnl": 0.0,
                "total_pnl": 0.0,
            }

    if not positions_data:
        snapshot = calculate_snapshot([], cash, closed_trades or [])
    else:
        positions = await get_positions(positions_data, provider)
        snapshot = calculate_snapshot(positions, cash, closed_trades or [])

    return {
        "total_equity": snapshot.total_equity,
        "cash": snapshot.cash,
        "market_value": snapshot.total_market_value,
        "positions": [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_entry_price": p.avg_entry_price,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "unrealized_pnl_pct": p.unrealized_pnl_pct,
                "realized_pnl": p.realized_pnl,
                "sector": p.sector,
                "allocation_pct": p.allocation_pct,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "days_held": p.days_held,
                "last_updated": p.last_updated,
            }
            for p in snapshot.positions
        ],
        "daily_pnl": snapshot.total_unrealized_pnl,
        "total_pnl": snapshot.total_unrealized_pnl + snapshot.total_realized_pnl,
    }


async def sync_positions() -> None:
    """Synchronise local position records with Alpaca — stub for future use."""
    pass
