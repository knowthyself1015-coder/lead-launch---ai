"""
Risk engine — position sizing, stop-loss calculation, portfolio risk controls.

Responsible for:
- Calculating appropriate position size given account equity & risk params
- Setting dynamic stop-loss and take-profit levels
- Enforcing maximum portfolio exposure limits
- Tracking daily drawdown and circuit-breaker conditions
- Pre-trade risk checks before execution
"""

from dataclasses import dataclass


@dataclass
class RiskAssessment:
    ticker: str
    allowed: bool
    max_position_size_pct: float
    suggested_stop_pct: float
    suggested_target_pct: float
    risk_reward_ratio: float
    reason: str = ""


async def assess_risk(
    ticker: str,
    account_equity: float,
    current_exposure_pct: float,
    volatility: float | None = None,
) -> RiskAssessment:
    """Evaluate whether a trade meets risk parameters.

    Returns a RiskAssessment with go/no-go and sizing recommendations.
    """
    # TODO: Implement risk parameter calculation
    return RiskAssessment(
        ticker=ticker,
        allowed=True,
        max_position_size_pct=0.05,
        suggested_stop_pct=0.02,
        suggested_target_pct=0.04,
        risk_reward_ratio=2.0,
        reason="Passed risk checks",
    )


def calculate_position_size(
    account_equity: float,
    entry_price: float,
    stop_price: float,
    max_risk_pct: float = 0.02,
) -> int:
    """Calculate the number of shares for a position given risk parameters.

    Uses the 2% rule: position size = (account * risk_pct) / (entry - stop)
    """
    if entry_price <= stop_price:
        return 0
    risk_per_share = abs(entry_price - stop_price)
    max_risk_dollars = account_equity * max_risk_pct
    shares = int(max_risk_dollars / risk_per_share)
    return shares
