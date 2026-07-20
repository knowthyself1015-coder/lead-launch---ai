"""
Sentiment API routes — news sentiment analysis endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.engines.market_data import (
    PolygonProvider,
    AlpacaProvider,
    MarketDataProvider,
)
from app.engines.sentiment import (
    analyze_news,
    analyze_batch,
    get_market_sentiment,
    SentimentResult,
)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class BatchSentimentRequest(BaseModel):
    symbols: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of ticker symbols to analyze (max 20)",
    )


class MarketSentimentResponse(BaseModel):
    indices: dict[str, SentimentResult]


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------
def _get_provider() -> MarketDataProvider:
    settings = get_settings()
    if settings.POLYGON_API_KEY:
        return PolygonProvider()
    if settings.ALPACA_API_KEY:
        return AlpacaProvider()
    raise HTTPException(
        status_code=500,
        detail="No market data provider configured — set POLYGON_API_KEY or ALPACA_API_KEY",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/{symbol}", response_model=SentimentResult)
async def route_analyze_symbol(symbol: str):
    """Analyze news sentiment for a single ticker symbol."""
    provider = _get_provider()
    try:
        return await analyze_news(symbol.upper(), provider)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Sentiment analysis failed for {symbol.upper()}: {exc}",
        )


@router.post("/batch", response_model=list[SentimentResult])
async def route_analyze_batch(body: BatchSentimentRequest):
    """Analyze news sentiment for multiple ticker symbols concurrently."""
    provider = _get_provider()
    symbols = [s.strip().upper() for s in body.symbols if s.strip()]
    if not symbols:
        raise HTTPException(status_code=400, detail="No valid symbols provided")
    try:
        return await analyze_batch(symbols, provider)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Batch sentiment analysis failed: {exc}",
        )


@router.get("/market", response_model=dict[str, SentimentResult])
async def route_market_sentiment():
    """Get broad market sentiment across major index ETFs (SPY, QQQ, IWM)."""
    provider = _get_provider()
    try:
        return await get_market_sentiment(provider)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Market sentiment analysis failed: {exc}",
        )
