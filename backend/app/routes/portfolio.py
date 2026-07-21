"""
Portfolio API routes — portfolio snapshot, positions, health, exposure, and updates.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import get_settings
from app.engines.market_data import (
    PolygonProvider,
    AlpacaProvider,
    MarketDataProvider,
)
from app.engines.portfolio import (
    PortfolioPosition,
    PortfolioSnapshot,
    ClosedTrade,
    get_positions,
    calculate_snapshot,
    calculate_sector_exposure,
    calculate_risk_concentration,
    get_portfolio_health,
    update_position,
)

router = APIRouter(tags=["portfolio"])


# ---------------------------------------------------------------------------
# Pydantic schemas for request/response
# ---------------------------------------------------------------------------

class PositionResponse(BaseModel):
    symbol: str
    quantity: int
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float
    sector: str
    allocation_pct: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    days_held: int
    last_updated: str

    model_config = {"from_attributes": True}


class PortfolioSnapshotResponse(BaseModel):
    cash: float
    total_market_value: float
    total_equity: float
    positions: list[PositionResponse]
    total_unrealized_pnl: float
    total_realized_pnl: float
    win_rate: float
    avg_return_pct: float
    sector_exposure: dict[str, float]
    risk_concentration: dict[str, float]
    open_positions_count: int
    timestamp: str


class PortfolioHealthResponse(BaseModel):
    status: str
    issues: list[str]


class ExposureResponse(BaseModel):
    sector_exposure: dict[str, float]
    risk_concentration: dict[str, float]


class PositionUpdateRequest(BaseModel):
    symbol: str
    quantity_delta: int = Field(default=0, description="Change in quantity (negative = partial sell)")
    fill_price: Optional[float] = None
    realized_pnl_delta: float = Field(default=0.0)
    new_stop_loss: Optional[float] = None
    new_take_profit: Optional[float] = None


class PortfolioRequest(BaseModel):
    """Request body for computing a portfolio snapshot from raw data."""
    positions_data: list[dict] = Field(default_factory=list)
    cash: float = Field(default=0.0, ge=0)
    closed_trades: list[dict] = Field(default_factory=list)


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


def _position_to_response(p: PortfolioPosition) -> PositionResponse:
    """Convert a PortfolioPosition dataclass to a Pydantic response model."""
    return PositionResponse(
        symbol=p.symbol,
        quantity=p.quantity,
        avg_entry_price=p.avg_entry_price,
        current_price=p.current_price,
        market_value=p.market_value,
        unrealized_pnl=p.unrealized_pnl,
        unrealized_pnl_pct=p.unrealized_pnl_pct,
        realized_pnl=p.realized_pnl,
        sector=p.sector,
        allocation_pct=p.allocation_pct,
        stop_loss=p.stop_loss,
        take_profit=p.take_profit,
        days_held=p.days_held,
        last_updated=p.last_updated,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/portfolio", response_model=PortfolioSnapshotResponse)
async def route_get_portfolio(
    cash: float = Query(0.0, ge=0, description="Available cash balance"),
):
    """Get full portfolio snapshot — positions, summary, and health."""
    provider = _get_provider()

    # Build sample positions for demo / testing when no broker positions exist
    positions_data = _sample_positions()

    try:
        positions = await get_positions(positions_data, provider)
        closed_trades = _sample_closed_trades()
        snapshot = calculate_snapshot(positions, cash, closed_trades)

        return PortfolioSnapshotResponse(
            cash=snapshot.cash,
            total_market_value=snapshot.total_market_value,
            total_equity=snapshot.total_equity,
            positions=[_position_to_response(p) for p in snapshot.positions],
            total_unrealized_pnl=snapshot.total_unrealized_pnl,
            total_realized_pnl=snapshot.total_realized_pnl,
            win_rate=snapshot.win_rate,
            avg_return_pct=snapshot.avg_return_pct,
            sector_exposure=snapshot.sector_exposure,
            risk_concentration=snapshot.risk_concentration,
            open_positions_count=snapshot.open_positions_count,
            timestamp=snapshot.timestamp,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch portfolio snapshot: {exc}",
        )


@router.get("/portfolio/positions", response_model=list[PositionResponse])
async def route_list_positions(
    cash: float = Query(0.0, ge=0, description="Available cash balance"),
):
    """List all open positions enriched with current prices."""
    provider = _get_provider()
    positions_data = _sample_positions()

    try:
        positions = await get_positions(positions_data, provider)
        return [_position_to_response(p) for p in positions]
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch positions: {exc}",
        )


@router.get("/portfolio/health", response_model=PortfolioHealthResponse)
async def route_portfolio_health(
    cash: float = Query(0.0, ge=0, description="Available cash balance"),
):
    """Get portfolio health status and any issues."""
    provider = _get_provider()
    positions_data = _sample_positions()

    try:
        positions = await get_positions(positions_data, provider)
        closed_trades = _sample_closed_trades()
        snapshot = calculate_snapshot(positions, cash, closed_trades)
        health = get_portfolio_health(snapshot)
        return PortfolioHealthResponse(status=health["status"], issues=health["issues"])
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to compute portfolio health: {exc}",
        )


@router.get("/portfolio/exposure", response_model=ExposureResponse)
async def route_portfolio_exposure(
    cash: float = Query(0.0, ge=0, description="Available cash balance"),
):
    """Get sector exposure and risk concentration breakdown."""
    provider = _get_provider()
    positions_data = _sample_positions()

    try:
        positions = await get_positions(positions_data, provider)
        total_mv = sum(p.market_value for p in positions)
        total_equity = cash + total_mv

        sector_exposure = calculate_sector_exposure(positions, total_mv)
        risk_concentration = calculate_risk_concentration(positions, total_equity)

        return ExposureResponse(
            sector_exposure=sector_exposure,
            risk_concentration=risk_concentration,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to compute exposure: {exc}",
        )


@router.post("/portfolio/update", response_model=PositionResponse)
async def route_update_position(body: PositionUpdateRequest):
    """Update a position — adjust stop, partial close, etc."""
    provider = _get_provider()
    symbol = body.symbol.upper()

    try:
        # Look up the existing position from sample data
        positions_data = _sample_positions()
        existing_data = None
        for pd_item in positions_data:
            sym = (pd_item.get("symbol") or pd_item.get("ticker", "")).upper()
            if sym == symbol:
                existing_data = pd_item
                break

        if existing_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Position not found for symbol: {symbol}",
            )

        # Enrich to get a PortfolioPosition
        [position] = await get_positions([existing_data], provider)

        # Apply update
        update_dict = body.model_dump(exclude={"symbol"}, exclude_none=False)
        updated = update_position(position, update_dict)

        return _position_to_response(updated)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to update position for {symbol}: {exc}",
        )


# ---------------------------------------------------------------------------
# Sample data (MVP — replace with broker sync in production)
# ---------------------------------------------------------------------------

def _sample_positions() -> list[dict]:
    """Return sample positions for demo / testing."""
    return [
        {
            "symbol": "AAPL",
            "quantity": 50,
            "avg_entry_price": 185.00,
            "sector": "Technology",
            "realized_pnl": 0.0,
            "stop_loss": 175.00,
            "take_profit": 210.00,
        },
        {
            "symbol": "MSFT",
            "quantity": 30,
            "avg_entry_price": 420.00,
            "sector": "Technology",
            "realized_pnl": 0.0,
            "stop_loss": 395.00,
            "take_profit": 470.00,
        },
        {
            "symbol": "NVDA",
            "quantity": 20,
            "avg_entry_price": 850.00,
            "sector": "Technology",
            "realized_pnl": 0.0,
            "stop_loss": 800.00,
            "take_profit": 950.00,
        },
        {
            "symbol": "JPM",
            "quantity": 40,
            "avg_entry_price": 195.00,
            "sector": "Financial",
            "realized_pnl": 0.0,
            "stop_loss": 182.00,
            "take_profit": 220.00,
        },
        {
            "symbol": "JNJ",
            "quantity": 25,
            "avg_entry_price": 160.00,
            "sector": "Healthcare",
            "realized_pnl": 0.0,
            "stop_loss": 150.00,
            "take_profit": 180.00,
        },
    ]


def _sample_closed_trades() -> list[ClosedTrade]:
    """Return sample closed trades for demo / testing."""
    return [
        ClosedTrade(
            symbol="TSLA",
            entry_price=250.00,
            exit_price=275.00,
            quantity=10,
            return_pct=10.0,
            pnl=250.0,
        ),
        ClosedTrade(
            symbol="META",
            entry_price=480.00,
            exit_price=510.00,
            quantity=5,
            return_pct=6.25,
            pnl=150.0,
        ),
        ClosedTrade(
            symbol="INTC",
            entry_price=45.00,
            exit_price=42.00,
            quantity=100,
            return_pct=-6.67,
            pnl=-300.0,
        ),
        ClosedTrade(
            symbol="AMD",
            entry_price=160.00,
            exit_price=155.00,
            quantity=20,
            return_pct=-3.13,
            pnl=-100.0,
        ),
    ]
