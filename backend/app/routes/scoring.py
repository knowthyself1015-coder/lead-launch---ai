"""
Scoring API routes — unified scoring and opportunity discovery endpoints.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import get_settings
from app.engines.market_data import (
    PolygonProvider,
    AlpacaProvider,
    MarketDataProvider,
)
from app.engines.scoring import (
    score_stock,
    score_batch,
    get_top_opportunities,
    StockScore,
    ScoreComponents,
)
from app.engines.scanner import SCAN_SYMBOLS
router = APIRouter(prefix="/scoring", tags=["scoring"])


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class ScoreComponentsResponse(BaseModel):
    trend: float
    volume: float
    momentum: float
    news: float
    options_flow: float
    financials: float


class StockScoreResponse(BaseModel):
    symbol: str
    total_score: float
    components: ScoreComponentsResponse
    signals: list[str]
    warnings: list[str]
    timestamp: str

    @classmethod
    def from_stock_score(cls, s: StockScore) -> "StockScoreResponse":
        return cls(
            symbol=s.symbol,
            total_score=s.total_score,
            components=ScoreComponentsResponse(
                trend=s.components.trend,
                volume=s.components.volume,
                momentum=s.components.momentum,
                news=s.components.news,
                options_flow=s.components.options_flow,
                financials=s.components.financials,
            ),
            signals=s.signals,
            warnings=s.warnings,
            timestamp=s.timestamp,
        )


class BatchScoringRequest(BaseModel):
    symbols: list[str]


class BatchScoringResponse(BaseModel):
    results: list[StockScoreResponse]
    count: int


class OpportunitiesResponse(BaseModel):
    results: list[StockScoreResponse]
    count: int
    threshold: float


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

@router.get("/{symbol}", response_model=StockScoreResponse)
async def route_score_stock(symbol: str):
    """Score a single stock — calls all relevant engines internally.

    Returns the full 0–100 score with component breakdown, signals, and
    warnings.
    """
    provider = _get_provider()
    try:
        result = await score_stock(symbol.upper(), provider)
        return StockScoreResponse.from_stock_score(result)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Scoring failed for {symbol}: {exc}",
        )


@router.post("/batch", response_model=BatchScoringResponse)
async def route_score_batch(body: BatchScoringRequest):
    """Score a batch of symbols — returns results sorted by total_score desc.

    Body: {"symbols": ["AAPL", "MSFT", ...]}
    """
    provider = _get_provider()
    symbols = [s.strip().upper() for s in body.symbols if s.strip()]
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols list cannot be empty")

    try:
        results = await score_batch(symbols, provider)
        return BatchScoringResponse(
            results=[StockScoreResponse.from_stock_score(r) for r in results],
            count=len(results),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Batch scoring failed: {exc}",
        )


@router.get("/opportunities", response_model=OpportunitiesResponse)
async def route_opportunities(
    threshold: float = Query(85.0, ge=0.0, le=100.0, description="Minimum total_score to include"),
    symbols: Optional[str] = Query(
        None,
        description="Comma-separated symbols to scan (default: built-in universe)",
    ),
):
    """Return top opportunities — stocks scoring above *threshold*.

    Uses the built-in SCAN_SYMBOLS universe by default, or a custom
    comma-separated list via the *symbols* query parameter.
    """
    provider = _get_provider()
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    else:
        symbol_list = SCAN_SYMBOLS

    try:
        results = await get_top_opportunities(symbol_list, provider, threshold=threshold)
        return OpportunitiesResponse(
            results=[StockScoreResponse.from_stock_score(r) for r in results],
            count=len(results),
            threshold=threshold,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Opportunities scan failed: {exc}",
        )
