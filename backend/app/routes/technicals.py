"""
Technical analysis API routes.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.engines.market_data import (
    PolygonProvider,
    AlpacaProvider,
    MarketDataProvider,
)
from app.engines.technicals import analyze, analyze_batch

router = APIRouter(prefix="/technicals", tags=["technicals"])


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------
def _get_provider() -> MarketDataProvider:
    """Instantiate the configured market data provider."""
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
@router.get("/{symbol}")
async def route_technicals(
    symbol: str,
    lookback_days: int = Query(90, ge=30, le=365, description="Days of price history to analyze"),
):
    """Run full technical analysis on a single symbol."""
    provider = _get_provider()
    try:
        result = await analyze(symbol.upper(), provider, lookback_days=lookback_days)
        return {
            "symbol": result.symbol,
            "timestamp": result.timestamp.isoformat(),
            "indicators": result.indicators,
            "patterns": result.patterns,
            "signals": result.signals,
            "summary": result.summary,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Technical analysis failed: {exc}")


@router.post("/batch")
async def route_technicals_batch(
    body: dict,
):
    """Run technical analysis on multiple symbols concurrently.

    Request body: {"symbols": ["AAPL", "MSFT", ...]}
    """
    symbols = body.get("symbols", [])
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols list is required")
    if not isinstance(symbols, list):
        raise HTTPException(status_code=400, detail="symbols must be a list of strings")
    if len(symbols) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols per batch request")

    symbols = [s.strip().upper() for s in symbols if s.strip()]

    provider = _get_provider()
    try:
        results = await analyze_batch(symbols, provider)
        return {
            "results": [
                {
                    "symbol": r.symbol,
                    "timestamp": r.timestamp.isoformat(),
                    "indicators": r.indicators,
                    "patterns": r.patterns,
                    "signals": r.signals,
                    "summary": r.summary,
                }
                for r in results
            ]
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Batch analysis failed: {exc}")
