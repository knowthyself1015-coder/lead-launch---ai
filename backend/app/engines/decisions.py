"""
Decisions engine — the culmination engine that takes scored stocks,
runs them through the risk manager, and produces final trade decisions.

Responsible for:
- Converting StockScore + TradeCheck into actionable TradeDecisions
- Applying decision logic: BUY, SELL, HOLD, WATCHLIST
- Calculating entry/exit parameters via the risk engine
- Generating decision summaries for the dashboard
- Evaluating exit conditions for held positions

Decision thresholds (from business plan):
    BUY       — total_score >= 85  AND  risk check passes
    WATCHLIST — total_score >= 85  BUT  risk check fails
    HOLD      — total_score 60–84
    SELL      — score drops below 40, or stop-loss was hit
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TradeDecision:
    """Final trade decision for a single symbol."""
    symbol: str
    decision: str          # "BUY" | "SELL" | "HOLD" | "WATCHLIST"
    confidence: float      # 0.0 – 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: int
    risk_amount: float
    reward_amount: float
    reward_to_risk_ratio: float
    reasoning: str         # bullet-point explanation
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class DecisionSummary:
    """Aggregated summary across all decisions."""
    total_analyzed: int
    buy_signals: int
    sell_signals: int
    hold_signals: int
    watchlist: int
    top_pick: Optional[TradeDecision] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_reasoning(
    score: "StockScore",
    check: "TradeCheck",
    decision_type: str,
) -> str:
    """Build a bullet-point reasoning string for the trade decision."""
    lines = [
        f"• Decision: {decision_type}",
        f"• Total score: {score.total_score:.1f}/100",
    ]

    comp = score.components
    lines.append(f"• Trend: {comp.trend:.1f}/25 | Volume: {comp.volume:.1f}/20")
    lines.append(f"• Momentum: {comp.momentum:.1f}/15 | News: {comp.news:.1f}/20")
    lines.append(f"• Options flow: {comp.options_flow:.1f}/10 | Financials: {comp.financials:.1f}/10")

    if score.signals:
        lines.append(f"• Signals: {', '.join(score.signals[:5])}")
    if score.warnings:
        lines.append(f"• Warnings: {', '.join(score.warnings[:5])}")

    if decision_type == "BUY":
        lines.append(f"• Risk check: APPROVED")
        lines.append(f"• Position: {check.position_size_shares} shares")
        lines.append(f"• Risk: ${check.risk_amount:,.2f} | Reward: ${check.reward_amount:,.2f}")
        lines.append(f"• R:R = {check.reward_to_risk_ratio:.1f}:1")
    elif decision_type == "WATCHLIST":
        reason = check.rejection_reason or "Unknown risk constraint"
        lines.append(f"• Risk check: FAILED — {reason}")
        lines.append("• Action: Added to watchlist for re-evaluation")
    elif decision_type == "HOLD":
        lines.append(f"• Score in hold range (60–84) — monitoring")
    elif decision_type == "SELL":
        lines.append(f"• Exit signal triggered")
        lines.append(f"• Risk check: {check.is_approved}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core decision functions
# ---------------------------------------------------------------------------

async def decide(
    symbol: str,
    provider: "MarketDataProvider",
    account_value: float = 100_000,
    current_positions: Optional[list[dict]] = None,
    daily_state: Optional["DailyRiskState"] = None,
    score_threshold: float = 85.0,
) -> TradeDecision:
    """Evaluate a single symbol and produce a trade decision.

    Parameters
    ----------
    symbol : str
        Ticker to evaluate (e.g. "AAPL").
    provider : MarketDataProvider
        Market data backend for quotes, bars, and fundamentals.
    account_value : float
        Total account equity for position sizing.
    current_positions : list[dict] | None
        Current open positions, each dict with keys:
        symbol, sector, market_value, quantity, entry_price.
    daily_state : DailyRiskState | None
        Current daily P&L and circuit-breaker state.
    score_threshold : float
        Minimum total_score (0–100) to trigger a BUY or WATCHLIST.

    Returns
    -------
    TradeDecision
    """
    # ── Late imports to avoid circular dependencies ──
    from app.engines.scoring import score_stock, StockScore  # noqa: PLC0415
    from app.engines.risk import (  # noqa: PLC0415
        check_trade,
        calculate_stop_loss,
        calculate_take_profit,
        calculate_position_size,
        TradeCheck,
        DailyRiskState,
        RiskParams,
        reset_daily_state,
    )

    if daily_state is None:
        daily_state = reset_daily_state()

    # 1) Score the stock
    stock_score: StockScore = await score_stock(symbol, provider)

    # 2) Get current quote for entry price
    quote = await provider.get_quote(symbol)
    if quote is None:
        return TradeDecision(
            symbol=symbol,
            decision="HOLD",
            confidence=0.0,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            position_size=0,
            risk_amount=0.0,
            reward_amount=0.0,
            reward_to_risk_ratio=0.0,
            reasoning=f"• No quote data available for {symbol}\n• Cannot evaluate entry/exit",
        )

    entry_price = quote.price

    # 3) Calculate stop-loss and take-profit from risk engine
    #    Estimate ATR as 2% of price if not available from provider
    atr_bars = await provider.get_bars(symbol, timespan="day", limit=14)
    atr_value = _estimate_atr(atr_bars) if atr_bars else entry_price * 0.02

    stop_loss = calculate_stop_loss(entry_price, atr_value, direction="LONG", multiplier=2.0)
    take_profit = calculate_take_profit(entry_price, stop_loss, min_rr=2.0)

    # 4) Risk check
    risk_params = RiskParams(account_value=account_value)
    sector = _resolve_sector(symbol, current_positions)

    trade_check: TradeCheck = check_trade(
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        account_value=account_value,
        current_positions=current_positions,
        daily_state=daily_state,
        symbol=symbol,
        sector=sector,
        risk_params=risk_params,
    )

    # 5) Decision logic
    total_score = stock_score.total_score
    confidence = total_score / 100.0  # normalize 0–100 → 0.0–1.0

    if total_score >= score_threshold:
        if trade_check.is_approved:
            decision_type = "BUY"
        else:
            decision_type = "WATCHLIST"
    elif total_score >= 60:
        decision_type = "HOLD"
    else:
        # Score < 60 — check if it's a held position that should be sold
        is_held = _is_position_held(symbol, current_positions)
        if is_held and total_score < 40:
            decision_type = "SELL"
        else:
            decision_type = "HOLD"

    reasoning = _build_reasoning(stock_score, trade_check, decision_type)

    return TradeDecision(
        symbol=symbol,
        decision=decision_type,
        confidence=round(confidence, 4),
        entry_price=entry_price,
        stop_loss=round(stop_loss, 2),
        take_profit=round(take_profit, 2),
        position_size=trade_check.position_size_shares,
        risk_amount=trade_check.risk_amount,
        reward_amount=trade_check.reward_amount,
        reward_to_risk_ratio=trade_check.reward_to_risk_ratio,
        reasoning=reasoning,
    )


async def decide_batch(
    symbols: list[str],
    provider: "MarketDataProvider",
    account_value: float = 100_000,
    current_positions: Optional[list[dict]] = None,
    daily_state: Optional["DailyRiskState"] = None,
) -> list[TradeDecision]:
    """Evaluate a list of symbols concurrently, sorted by confidence desc.

    Parameters
    ----------
    symbols : list[str]
        Tickers to evaluate.
    provider : MarketDataProvider
    account_value : float
    current_positions : list[dict] | None
    daily_state : DailyRiskState | None

    Returns
    -------
    list[TradeDecision] — sorted by confidence descending.
    """
    import asyncio  # noqa: PLC0415

    async def _decide_one(sym: str) -> TradeDecision:
        try:
            return await decide(
                symbol=sym,
                provider=provider,
                account_value=account_value,
                current_positions=current_positions,
                daily_state=daily_state,
            )
        except Exception as exc:
            logger.exception("Decision failed for %s: %s", sym, exc)
            return TradeDecision(
                symbol=sym,
                decision="HOLD",
                confidence=0.0,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                position_size=0,
                risk_amount=0.0,
                reward_amount=0.0,
                reward_to_risk_ratio=0.0,
                reasoning=f"• Error during evaluation: {exc}",
            )

    tasks = [_decide_one(s) for s in symbols]
    results = await asyncio.gather(*tasks)

    # Sort by confidence descending
    results.sort(key=lambda d: d.confidence, reverse=True)
    return results


def generate_summary(decisions: list[TradeDecision]) -> DecisionSummary:
    """Produce an aggregated summary from a list of trade decisions.

    Parameters
    ----------
    decisions : list[TradeDecision]

    Returns
    -------
    DecisionSummary
    """
    buy_signals = sum(1 for d in decisions if d.decision == "BUY")
    sell_signals = sum(1 for d in decisions if d.decision == "SELL")
    hold_signals = sum(1 for d in decisions if d.decision == "HOLD")
    watchlist = sum(1 for d in decisions if d.decision == "WATCHLIST")

    # Top pick = highest-confidence BUY (first in sorted list)
    top_pick = None
    for d in decisions:
        if d.decision == "BUY":
            top_pick = d
            break

    return DecisionSummary(
        total_analyzed=len(decisions),
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        hold_signals=hold_signals,
        watchlist=watchlist,
        top_pick=top_pick,
    )


async def should_sell(
    portfolio_position: dict,
    provider: "MarketDataProvider",
) -> TradeDecision:
    """Evaluate whether a currently held position should be sold.

    Triggers a SELL when:
    - The stock's score drops below 40
    - The current price has hit the stop-loss level
    - The take-profit target has been reached (take-profit sell)

    Parameters
    ----------
    portfolio_position : dict
        Keys: symbol, entry_price, quantity, stop_loss_price, take_profit_price.
    provider : MarketDataProvider

    Returns
    -------
    TradeDecision — with decision="SELL" if exit conditions are met,
                    otherwise decision="HOLD".
    """
    symbol = portfolio_position["symbol"]
    entry_price = portfolio_position.get("entry_price", 0.0)
    quantity = portfolio_position.get("quantity", 0)
    stop_loss_price = portfolio_position.get("stop_loss_price")
    take_profit_price = portfolio_position.get("take_profit_price")

    # Get current price
    quote = await provider.get_quote(symbol)
    if quote is None:
        return TradeDecision(
            symbol=symbol,
            decision="HOLD",
            confidence=0.0,
            entry_price=entry_price,
            stop_loss=stop_loss_price or 0.0,
            take_profit=take_profit_price or 0.0,
            position_size=quantity,
            risk_amount=0.0,
            reward_amount=0.0,
            reward_to_risk_ratio=0.0,
            reasoning=f"• No quote available for {symbol} — cannot evaluate exit",
        )

    current_price = quote.price
    unrealized_pnl = (current_price - entry_price) * quantity
    pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0.0

    # Check stop-loss hit (before scoring — fast exit)
    if stop_loss_price and current_price <= stop_loss_price:
        return TradeDecision(
            symbol=symbol,
            decision="SELL",
            confidence=1.0,
            entry_price=entry_price,
            stop_loss=stop_loss_price,
            take_profit=take_profit_price or 0.0,
            position_size=quantity,
            risk_amount=abs(unrealized_pnl),
            reward_amount=0.0,
            reward_to_risk_ratio=0.0,
            reasoning=(
                f"• STOP-LOSS HIT\n"
                f"• Entry: ${entry_price:.2f} → Current: ${current_price:.2f}\n"
                f"• Stop-loss level: ${stop_loss_price:.2f}\n"
                f"• Loss: ${abs(unrealized_pnl):,.2f} ({pnl_pct:.1f}%)"
            ),
        )

    # Check take-profit hit (before scoring — fast exit)
    if take_profit_price and current_price >= take_profit_price:
        return TradeDecision(
            symbol=symbol,
            decision="SELL",
            confidence=1.0,
            entry_price=entry_price,
            stop_loss=stop_loss_price or 0.0,
            take_profit=take_profit_price,
            position_size=quantity,
            risk_amount=0.0,
            reward_amount=unrealized_pnl,
            reward_to_risk_ratio=0.0,
            reasoning=(
                f"• TAKE-PROFIT HIT\n"
                f"• Entry: ${entry_price:.2f} → Current: ${current_price:.2f}\n"
                f"• Take-profit level: ${take_profit_price:.2f}\n"
                f"• Gain: ${unrealized_pnl:,.2f} ({pnl_pct:.1f}%)"
            ),
        )

    # Late import — only needed if stop/target not hit
    from app.engines.scoring import score_stock, StockScore  # noqa: PLC0415

    # Score the stock to check for score-based sell
    try:
        stock_score: StockScore = await score_stock(symbol, provider)
        total_score = stock_score.total_score

        if total_score < 40:
            return TradeDecision(
                symbol=symbol,
                decision="SELL",
                confidence=round((100.0 - total_score) / 100.0, 4),
                entry_price=entry_price,
                stop_loss=stop_loss_price or 0.0,
                take_profit=take_profit_price or 0.0,
                position_size=quantity,
                risk_amount=abs(unrealized_pnl) if unrealized_pnl < 0 else 0.0,
                reward_amount=unrealized_pnl if unrealized_pnl > 0 else 0.0,
                reward_to_risk_ratio=0.0,
                reasoning=(
                    f"• SCORE-BASED SELL — Score dropped to {total_score:.1f}/100\n"
                    f"• Entry: ${entry_price:.2f} → Current: ${current_price:.2f}\n"
                    f"• P&L: ${unrealized_pnl:,.2f} ({pnl_pct:.1f}%)\n"
                    f"• Score components: trend={stock_score.components.trend:.1f}, "
                    f"momentum={stock_score.components.momentum:.1f}"
                ),
            )
    except Exception as exc:
        logger.warning("Scoring failed for sell-check on %s: %s", symbol, exc)
        # Can't score — fall through to HOLD

    # No sell conditions triggered
    return TradeDecision(
        symbol=symbol,
        decision="HOLD",
        confidence=0.5,
        entry_price=entry_price,
        stop_loss=stop_loss_price or 0.0,
        take_profit=take_profit_price or 0.0,
        position_size=quantity,
        risk_amount=0.0,
        reward_amount=unrealized_pnl if unrealized_pnl > 0 else 0.0,
        reward_to_risk_ratio=0.0,
        reasoning=(
            f"• No exit conditions triggered\n"
            f"• Current P&L: ${unrealized_pnl:,.2f} ({pnl_pct:.1f}%)\n"
            f"• Stop: ${stop_loss_price:.2f} | Target: ${take_profit_price:.2f}"
        ),
    )


# ---------------------------------------------------------------------------
# Backward-compatible wrapper (original stub interface)
# ---------------------------------------------------------------------------

@dataclass
class LegacyTradeDecision:
    """Original TradeDecision for backward compatibility with evaluate_signal."""
    ticker: str
    action: str  # "buy", "sell", "skip"
    confidence: float
    quantity: int = 0
    order_type: str = "market"
    reason: str = ""
    risk_assessment: Optional[dict] = None


async def evaluate_signal(signal: dict, account_equity: float) -> LegacyTradeDecision:
    """Legacy wrapper — evaluate a scored signal and return a trade decision.

    Maps the old dict-based scoring API onto the new decision logic.
    Use ``decide()`` for new code.

    Args:
        signal: Dict from the scoring engine with composite scores.
        account_equity: Current account equity for sizing.

    Returns a LegacyTradeDecision with action instructions.
    """
    confidence = signal.get("composite_score", 0.0)
    ticker = signal.get("ticker", "")

    if confidence < 0.70:
        return LegacyTradeDecision(
            ticker=ticker,
            action="skip",
            confidence=confidence,
            reason="Below confidence threshold",
        )

    return LegacyTradeDecision(
        ticker=ticker,
        action="buy",
        confidence=confidence,
        reason="Meets criteria — pending risk check",
    )


# ---------------------------------------------------------------------------
# Pure helpers (no I/O)
# ---------------------------------------------------------------------------

def _estimate_atr(bars: list) -> float:
    """Estimate ATR from a list of Bar objects.

    Uses a simple true-range average over available bars.
    Falls back to 2% of the last close if insufficient data.
    """
    if not bars or len(bars) < 2:
        return 0.0

    true_ranges: list[float] = []
    for i in range(1, len(bars)):
        high = bars[i].high
        low = bars[i].low
        prev_close = bars[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    if not true_ranges:
        return bars[-1].close * 0.02

    return sum(true_ranges) / len(true_ranges)


def _resolve_sector(symbol: str, current_positions: Optional[list[dict]]) -> str:
    """Look up a symbol's sector from current_positions or return empty string."""
    if not current_positions:
        return ""
    for pos in current_positions:
        if pos.get("symbol", "").upper() == symbol.upper():
            return pos.get("sector", "")
    return ""


def _is_position_held(symbol: str, current_positions: Optional[list[dict]]) -> bool:
    """Check whether a symbol is in the current positions list."""
    if not current_positions:
        return False
    return any(
        pos.get("symbol", "").upper() == symbol.upper()
        for pos in current_positions
    )
