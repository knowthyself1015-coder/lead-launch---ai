from fastapi import APIRouter

from app.schemas import SignalResponse

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalResponse])
async def list_signals(status: str | None = None, limit: int = 50):
    """List recent trade signals, optionally filtered by status."""
    # TODO: Query database
    return []


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(signal_id: int):
    """Get a specific signal by ID."""
    # TODO: Query database
    return None
