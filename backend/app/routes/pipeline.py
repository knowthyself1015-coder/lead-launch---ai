"""Pipeline control routes — start, stop, and check status of the pipeline loop."""

import logging

from fastapi import APIRouter

from app.engines.orchestrator import (
    get_orchestrator,
    is_market_open,
    market_status_detail,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"])


@router.post("/pipeline/start")
async def pipeline_start():
    """Start the pipeline loop."""
    orch = get_orchestrator()
    orch.start()
    return {
        "status": "started",
        "running": orch.is_running(),
    }


@router.post("/pipeline/stop")
async def pipeline_stop():
    """Stop the pipeline loop."""
    orch = get_orchestrator()
    orch.stop()
    return {
        "status": "stopped",
        "running": orch.is_running(),
    }


@router.get("/pipeline/status")
async def pipeline_status():
    """Get pipeline status, last run, and market info."""
    orch = get_orchestrator()
    last_run = orch.get_last_run()
    market = market_status_detail()

    return {
        "running": orch.is_running(),
        "last_run": {
            "run_id": last_run.run_id,
            "started_at": last_run.started_at.isoformat() if last_run.started_at else None,
            "completed_at": last_run.completed_at.isoformat() if last_run.completed_at else None,
            "status": last_run.status,
            "symbols_scanned": last_run.symbols_scanned,
            "signals_generated": last_run.signals_generated,
            "trades_executed": last_run.trades_executed,
            "errors": len(last_run.errors),
        } if last_run else None,
        "market": market,
    }


@router.get("/pipeline/history")
async def pipeline_history(limit: int = 20):
    """Get recent pipeline run history."""
    orch = get_orchestrator()
    history = orch.get_history(limit=limit)
    return {
        "count": len(history),
        "runs": [
            {
                "run_id": r.run_id,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "status": r.status,
                "symbols_scanned": r.symbols_scanned,
                "signals_generated": r.signals_generated,
                "trades_executed": r.trades_executed,
                "errors": len(r.errors),
            }
            for r in reversed(history)
        ],
    }
