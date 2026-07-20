from fastapi import APIRouter

from app.schemas import DailyReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[DailyReportResponse])
async def list_reports(limit: int = 30):
    """List daily performance reports."""
    from app.engines.reports import get_reports

    return await get_reports(limit=limit)


@router.get("/latest", response_model=DailyReportResponse)
async def latest_report():
    """Get the most recent daily report."""
    # TODO: Query database
    return None
