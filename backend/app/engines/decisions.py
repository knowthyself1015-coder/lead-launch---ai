"""
Decisions engine — evaluates scored signals and decides which trades to take.

Responsible for:
- Filtering signals by confidence threshold
- Applying override rules (e.g., never trade earnings week)
- Generating order instructions for accepted signals
- Tracking decision rationale for audit trail
- Coordinating with the risk engine for final pre-trade checks
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeDecision:
    ticker: str
    action: str  # "buy", "sell", "skip"
    confidence: float
    quantity: int = 0
    order_type: str = "market"
    reason: str = ""
    risk_assessment: Optional[dict] = None


async def evaluate_signal(signal: dict, account_equity: float) -> TradeDecision:
    """Evaluate a scored signal and return a trade decision.

    Args:
        signal: Dict from the scoring engine with composite scores.
        account_equity: Current account equity for sizing.

    Returns a TradeDecision with action instructions.
    """
    confidence = signal.get("composite_score", 0.0)

    # Check if we already hold this position
    from app.engines.portfolio import get_portfolio_snapshot
    try:
        portfolio = await get_portfolio_snapshot()
        positions = portfolio.get("positions", [])
        held_symbols = {p.get("symbol", "").upper(): p for p in positions}
    except Exception:
        held_symbols = {}

    ticker = signal.get("ticker", "").upper()

    if ticker in held_symbols:
        # Already holding — decide whether to sell
        pos = held_symbols[ticker]
        unrealized_pl_pct = float(pos.get("unrealized_plpc", 0) or 0)

        if confidence < 0.55:
            # Moderate-to-weak signal on a held position — sell to free capital
            return TradeDecision(
                ticker=ticker,
                action="sell",
                confidence=confidence,
                reason=f"Rotate: signal {confidence:.2f} below hold threshold (P&L: {unrealized_pl_pct:.1%})",
            )
        elif unrealized_pl_pct > 0.03:
            # Profit-taking: up >3%, lock in gains
            return TradeDecision(
                ticker=ticker,
                action="sell",
                confidence=confidence,
                reason=f"Take profit: +{unrealized_pl_pct:.1%} with confidence {confidence:.2f}",
            )
        elif unrealized_pl_pct < -0.03:
            # Stop-loss: down >3%, cut losses
            return TradeDecision(
                ticker=ticker,
                action="sell",
                confidence=confidence,
                reason=f"Stop loss: {unrealized_pl_pct:.1%} with confidence {confidence:.2f}",
            )
        else:
            return TradeDecision(
                ticker=ticker,
                action="skip",
                confidence=confidence,
                reason=f"Holding — signal ok ({confidence:.2f}), P&L: {unrealized_pl_pct:.1%}",
            )

    if confidence < 0.45:
        return TradeDecision(
            ticker=ticker,
            action="skip",
            confidence=confidence,
            reason="Below confidence threshold",
        )

    return TradeDecision(
        ticker=ticker,
        action="buy",
        confidence=confidence,
        reason="Meets criteria — pending risk check",
    )
