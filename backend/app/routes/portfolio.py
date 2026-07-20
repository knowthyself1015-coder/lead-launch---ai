from fastapi import APIRouter

from app.schemas import PortfolioPositionResponse, TradeResponse

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio", response_model=dict)
async def get_portfolio():
    """Get current portfolio snapshot."""
    from app.engines.portfolio import get_portfolio_snapshot

    return await get_portfolio_snapshot()


@router.get("/portfolio/positions", response_model=list[PortfolioPositionResponse])
async def list_positions():
    """List all open positions."""
    return []


@router.get("/trades", response_model=list[TradeResponse])
async def list_trades(limit: int = 100):
    """List recent trades."""
    return []
