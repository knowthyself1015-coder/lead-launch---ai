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
    # TODO: Implement full decision pipeline with risk checks
    confidence = signal.get("composite_score", 0.0)
    if confidence < 0.70:
        return TradeDecision(
            ticker=signal["ticker"],
            action="skip",
            confidence=confidence,
            reason="Below confidence threshold",
        )

    return TradeDecision(
        ticker=signal["ticker"],
        action="buy",
        confidence=confidence,
        reason="Meets criteria — pending risk check",
    )
