"""
Scoring engine — unified multi-factor model for ranking trade opportunities.

Responsible for:
- Combining scanner, sentiment, technical, and fundamental scores
- Weighting factors according to strategy configuration
- Applying market-regime adjustments
- Producing a final confidence score (0.0 – 1.0)
- Training / retraining the XGBoost model on historical signal outcomes
"""


async def score_candidate(
    ticker: str,
    scanner_score: float = 0.0,
    sentiment_score: float = 0.0,
    technical_score: float = 0.0,
    fundamental_score: float = 0.0,
) -> dict:
    """Combine sub-scores into a composite confidence score.

    Returns a dict with:
        - ticker
        - composite_score (0.0 – 1.0)
        - individual scores
        - meets_threshold (bool)
        - confidence_level (low/medium/high)
    """
    # Current MVP: simple weighted average
    weights = {
        "scanner": 0.15,
        "sentiment": 0.25,
        "technical": 0.40,
        "fundamental": 0.20,
    }
    composite = (
        scanner_score * weights["scanner"]
        + sentiment_score * weights["sentiment"]
        + technical_score * weights["technical"]
        + fundamental_score * weights["fundamental"]
    )

    confidence = "low"
    if composite >= 0.7:
        confidence = "high"
    elif composite >= 0.5:
        confidence = "medium"

    return {
        "ticker": ticker,
        "composite_score": round(composite, 4),
        "scanner_score": scanner_score,
        "sentiment_score": sentiment_score,
        "technical_score": technical_score,
        "fundamental_score": fundamental_score,
        "meets_threshold": composite >= 0.70,
        "confidence_level": confidence,
    }
