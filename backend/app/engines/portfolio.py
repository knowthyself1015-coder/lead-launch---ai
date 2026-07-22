"""
Portfolio engine — tracks current holdings, P&L, and performance metrics.

Responsible for:
- Syncing positions with Alpaca brokerage
- Calculating realised and unrealised P&L
- Computing portfolio-level metrics (Sharpe, drawdown, beta)
- Maintaining position-level stop/target tracking
- Generating portfolio snapshots for the dashboard
"""

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def get_portfolio_snapshot() -> dict:
    """Return a snapshot of the current portfolio state from Alpaca.

    Returns dict with:
        - total_equity
        - cash
        - market_value
        - positions (list of open positions)
        - daily_pnl
        - total_pnl
    """
    settings = get_settings()

    if not settings.ALPACA_API_KEY:
        return {
            "total_equity": 100_000.0,
            "cash": 100_000.0,
            "market_value": 0.0,
            "positions": [],
            "daily_pnl": 0.0,
            "total_pnl": 0.0,
        }

    try:
        async with httpx.AsyncClient(
            base_url=settings.ALPACA_BASE_URL,
            timeout=httpx.Timeout(15.0),
            headers={
                "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": settings.ALPACA_SECRET_KEY,
            },
        ) as client:
            # Fetch account
            acct_resp = await client.get("/v2/account")
            acct_resp.raise_for_status()
            acct = acct_resp.json()

            # Fetch positions
            pos_resp = await client.get("/v2/positions")
            pos_resp.raise_for_status()
            raw_positions = pos_resp.json()

            positions = []
            for p in raw_positions:
                positions.append({
                    "symbol": p.get("symbol", ""),
                    "qty": float(p.get("qty", 0)),
                    "market_value": float(p.get("market_value", 0)),
                    "cost_basis": float(p.get("cost_basis", 0)),
                    "avg_entry_price": float(p.get("avg_entry_price", 0)),
                    "unrealized_pl": float(p.get("unrealized_pl", 0)),
                    "unrealized_plpc": float(p.get("unrealized_plpc", 0)),
                    "current_price": float(p.get("current_price", 0)),
                    "side": p.get("side", "long"),
                })

            return {
                "total_equity": float(acct.get("equity", 0)),
                "cash": float(acct.get("cash", 0)),
                "buying_power": float(acct.get("buying_power", 0)),
                "market_value": float(acct.get("portfolio_value", 0)),
                "positions": positions,
                "daily_pnl": 0.0,
                "total_pnl": float(acct.get("equity", 0)) - float(acct.get("last_equity", float(acct.get("equity", 0)))),
            }
    except Exception:
        logger.exception("Failed to fetch portfolio from Alpaca")
        return {
            "total_equity": 0.0,
            "cash": 0.0,
            "market_value": 0.0,
            "positions": [],
            "daily_pnl": 0.0,
            "total_pnl": 0.0,
        }


async def sync_positions() -> None:
    """Synchronise local position records with Alpaca."""
    # The snapshot already fetches live data — no local sync needed for MVP
    pass
