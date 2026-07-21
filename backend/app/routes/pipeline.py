"""
Pipeline API routes — start, stop, and monitor the orchestration loop.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.engines.orchestrator import get_orchestrator, is_market_open, market_status_detail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# ---------------------------------------------------------------------------
# POST /pipeline/start
# ---------------------------------------------------------------------------

@router.post("/start")
async def start_pipeline(interval_seconds: Optional[int] = Query(None, ge=30, le=3600)):
    """Start the orchestration loop. Optional: override pipeline interval (30-3600s)."""
    orch = get_orchestrator()

    if orch.is_running():
        return {
            "status": "already_running",
            "message": "Pipeline orchestration loop is already running.",
            "interval_seconds": None,
        }

    orch.start(interval_seconds=interval_seconds)
    orch.start_daily_scheduler()

    return {
        "status": "started",
        "message": "Pipeline orchestration loop started. Daily scheduler also started.",
        "interval_seconds": interval_seconds or 300,
    }


# ---------------------------------------------------------------------------
# POST /pipeline/stop
# ---------------------------------------------------------------------------

@router.post("/stop")
async def stop_pipeline():
    """Stop the orchestration loop gracefully."""
    orch = get_orchestrator()

    if not orch.is_running():
        return {
            "status": "already_stopped",
            "message": "Pipeline orchestration loop is not running.",
        }

    orch.stop()

    return {
        "status": "stopped",
        "message": "Pipeline orchestration loop stopped.",
    }


# ---------------------------------------------------------------------------
# GET /pipeline/status
# ---------------------------------------------------------------------------

@router.get("/status")
async def pipeline_status():
    """Get current pipeline status: running? last run? market status?"""
    orch = get_orchestrator()
    last_run = orch.get_last_run()
    market = market_status_detail()

    return {
        "pipeline": {
            "running": orch.is_running(),
        },
        "last_run": {
            "run_id": last_run.run_id,
            "started_at": last_run.started_at.isoformat() if last_run else None,
            "completed_at": last_run.completed_at.isoformat() if last_run and last_run.completed_at else None,
            "status": last_run.status if last_run else None,
            "symbols_scanned": last_run.symbols_scanned if last_run else 0,
            "signals_generated": last_run.signals_generated if last_run else 0,
            "trades_executed": last_run.trades_executed if last_run else 0,
            "error_count": len(last_run.errors) if last_run else 0,
        } if last_run else None,
        "market": market,
    }


# ---------------------------------------------------------------------------
# POST /pipeline/run-once
# ---------------------------------------------------------------------------

@router.post("/run-once")
async def run_once():
    """Trigger a single pipeline run manually, independent of the loop."""
    orch = get_orchestrator()

    try:
        run = await orch.run_once()
        return {
            "status": "completed",
            "run_id": run.run_id,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "symbols_scanned": run.symbols_scanned,
            "signals_generated": run.signals_generated,
            "trades_executed": run.trades_executed,
            "errors": run.errors,
        }
    except Exception as exc:
        logger.exception("run-once failed")
        raise HTTPException(status_code=500, detail=f"Pipeline run failed: {exc}")


# ---------------------------------------------------------------------------
# GET /pipeline/history
# ---------------------------------------------------------------------------

@router.get("/history")
async def pipeline_history(limit: int = Query(20, ge=1, le=200)):
    """Return the last N pipeline runs."""
    orch = get_orchestrator()
    runs = orch.get_history(limit=limit)

    return {
        "total": len(runs),
        "runs": [
            {
                "run_id": r.run_id,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "status": r.status,
                "symbols_scanned": r.symbols_scanned,
                "signals_generated": r.signals_generated,
                "trades_executed": r.trades_executed,
                "error_count": len(r.errors),
                "errors": r.errors[-5:] if r.errors else [],  # last 5 errors only
            }
            for r in runs
        ],
    }


# ---------------------------------------------------------------------------
# GET /pipeline/market-status
# ---------------------------------------------------------------------------

@router.get("/market-status")
async def get_market_status():
    """Return whether the market is currently open."""
    return market_status_detail()
