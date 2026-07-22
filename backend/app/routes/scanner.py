"""
Scanner API routes — market scanning and discovery endpoints.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.engines.market_data import (
    AlpacaProvider,
    MarketDataProvider,
)
from app.engines.scanner import (
    scan_market,
    scan_top_gainers,
    scan_top_losers,
    scan_volume_spikes,
    scan_unusual_options,
)
from app.schemas import (
    ScanResultResponse,
    GainersLosersResponse,
    VolumeSpikeResponse,
    UnusualOptionsResponse,
)

router = APIRouter(prefix="/scanner", tags=["scanner"])


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------
def _get_provider() -> MarketDataProvider:
    """Instantiate the configured market data provider — Alpaca only."""
    settings = get_settings()

    if settings.ALPACA_API_KEY:
        return AlpacaProvider()

    raise HTTPException(
        status_code=500,
        detail="No market data provider configured — set ALPACA_API_KEY",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/scan", response_model=list[ScanResultResponse])
async def route_scan_market(
    symbols: Optional[str] = Query(
        None,
        description="Comma-separated list of symbols to scan (default: built-in universe)",
    ),
):
    """Run a full market scan across the configured symbol universe and
    return scored results sorted highest-first."""
    provider = _get_provider()
    symbol_list = None
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    try:
        return await scan_market(provider, symbols=symbol_list)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market scan failed: {exc}")


@router.get("/gainers", response_model=list[GainersLosersResponse])
async def route_top_gainers(limit: int = Query(10, ge=1, le=50)):
    """Return today's top gainers."""
    provider = _get_provider()
    try:
        return await scan_top_gainers(provider, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch gainers: {exc}")


@router.get("/losers", response_model=list[GainersLosersResponse])
async def route_top_losers(limit: int = Query(10, ge=1, le=50)):
    """Return today's top losers."""
    provider = _get_provider()
    try:
        return await scan_top_losers(provider, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch losers: {exc}")


@router.get("/volume-spikes", response_model=list[VolumeSpikeResponse])
async def route_volume_spikes(
    min_rvol: float = Query(2.0, ge=1.0, description="Minimum relative volume threshold"),
    limit: int = Query(20, ge=1, le=50),
):
    """Return stocks with volume significantly above their average."""
    provider = _get_provider()
    try:
        return await scan_volume_spikes(provider, min_rvol=min_rvol, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch volume spikes: {exc}")


@router.get("/options/{symbol}", response_model=list[UnusualOptionsResponse])
async def route_unusual_options(
    symbol: str,
    limit: int = Query(20, ge=1, le=50),
):
    """Return unusual options activity for a specific symbol."""
    provider = _get_provider()
    try:
        return await scan_unusual_options(provider, symbol=symbol.upper(), limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch options data: {exc}")
