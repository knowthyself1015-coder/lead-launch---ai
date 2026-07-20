from fastapi import APIRouter

from app.schemas import StockResponse, WatchlistItemResponse, WatchlistItemCreate

router = APIRouter(tags=["stocks"])


@router.get("/stocks", response_model=list[StockResponse])
async def list_stocks(limit: int = 100):
    """List all tracked stocks."""
    # TODO: Query database
    return []


@router.get("/stocks/{ticker}", response_model=StockResponse)
async def get_stock(ticker: str):
    """Get details for a specific stock."""
    # TODO: Query database
    return None


# -----------------------------------------------------------
# Watchlist
# -----------------------------------------------------------
@router.get("/watchlist", response_model=list[WatchlistItemResponse])
async def list_watchlist():
    """List all watchlist items."""
    return []


@router.post("/watchlist", response_model=WatchlistItemResponse)
async def add_to_watchlist(item: WatchlistItemCreate):
    """Add a ticker to the watchlist."""
    # TODO: Persist to database
    return item
