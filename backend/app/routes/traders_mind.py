"""
Trader's Mind API routes — regime, confluence, sit-out, and journal.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.engines.traders_mind import (
    get_trade_journal,
    detect_regime,
    check_confluence,
    should_sit_out,
    MarketRegime,
    MarketRegimeType,
    REGIME_CONFIG,
    _FOMC_DATES_2026,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/traders-mind", tags=["traders-mind"])


# ---------------------------------------------------------------------------
# GET /traders-mind/regime
# ---------------------------------------------------------------------------

@router.get("/regime")
async def get_regime():
    """Return the current market regime.

    Attempts to fetch live data from the Polygon provider.
    Falls back to a cached/synthetic response if the provider is unavailable.
    """
    try:
        from app.engines.market_data import PolygonProvider

        provider = PolygonProvider()
        regime: MarketRegime = await detect_regime(provider)
    except Exception as exc:
        logger.warning("Failed to detect regime live: %s — returning default", exc)
        regime = MarketRegime(
            regime=MarketRegimeType.RANGING,
            vix_level=15.0,
            trend_strength=0.5,
            description="Default regime — live detection unavailable",
            implications=["Trade cautiously with standard risk parameters"],
        )

    cfg = regime.config

    return {
        "regime": regime.regime.value,
        "vix_level": regime.vix_level,
        "trend_strength": regime.trend_strength,
        "description": regime.description,
        "implications": regime.implications,
        "config": {
            "score_threshold": cfg["score_threshold"],
            "risk_per_trade_pct": cfg["risk_per_trade"],
            "min_confluence": cfg["min_confluence"],
            "max_positions": cfg["max_positions"],
        },
    }


# ---------------------------------------------------------------------------
# GET /traders-mind/confluence/{symbol}
# ---------------------------------------------------------------------------

@router.get("/confluence/{symbol}")
async def get_confluence(symbol: str):
    """Check confluence signals for a given symbol.

    Fetches live data from the scanner/technicals/sentiment engines
    and checks how many independent categories confirm a BUY.
    """
    try:
        from app.engines.market_data import PolygonProvider
        from app.engines.scanner import scan_market
        from app.engines.technicals import analyze_technicals
        from app.engines.sentiment import analyze_sentiment
        from app.engines.traders_mind import detect_regime

        provider = PolygonProvider()

        # Get regime first
        regime = await detect_regime(provider)

        # Scan the specific symbol
        scan_results = await scan_market(provider, symbols=[symbol])

        if not scan_results:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        sr = scan_results[0]

        # Build scoring-like result
        scoring_result = {
            "ticker": sr.symbol,
            "relative_volume": sr.relative_volume,
            "above_sma_50": sr.above_sma_50,
            "above_sma_200": sr.above_sma_200,
            "unusual_options": {},
        }

        # Technicals
        bars = await provider.get_bars(sr.symbol, timeframe="1D", limit=60)
        bar_dicts = [
            {"c": b.close, "h": b.high, "l": b.low, "o": b.open, "v": b.volume}
            for b in bars
        ] if bars else []
        tech = await analyze_technicals(sr.symbol, bars=bar_dicts if bar_dicts else None)

        # Sentiment
        sent = await analyze_sentiment(sr.symbol)

        # Check confluence
        result = check_confluence(scoring_result, tech, sent, regime)

        return {
            "symbol": symbol,
            "regime": regime.regime.value,
            "confluence_count": result.confluence_count,
            "required": result.required,
            "passed": result.passed,
            "active_signals": result.active_signals,
            "missing_signals": result.missing_signals,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Confluence check failed for %s", symbol)
        raise HTTPException(status_code=500, detail=f"Confluence check failed: {exc}")


# ---------------------------------------------------------------------------
# GET /traders-mind/sit-out
# ---------------------------------------------------------------------------

@router.get("/sit-out")
async def get_sit_out():
    """Check whether the agent should sit out of trading right now."""
    try:
        from app.engines.market_data import PolygonProvider
        from app.engines.traders_mind import detect_regime, should_sit_out, get_trade_journal

        provider = PolygonProvider()
        regime = await detect_regime(provider)

        # Build daily state from journal
        journal = get_trade_journal()
        stats = journal.get_stats()

        # Count consecutive losses from most recent trades
        entries = journal.get_all_entries()
        consecutive_losses = 0
        for e in reversed(entries):
            if e.pnl is not None and e.pnl <= 0:
                consecutive_losses += 1
            elif e.pnl is not None:
                break

        # Daily PnL (sum of today's closed trades)
        from datetime import date
        today = date.today().isoformat()
        daily_entries = [e for e in entries if e.entry_date == today and e.pnl is not None]
        daily_pnl_pct = sum(e.pnl_pct or 0 for e in daily_entries) * 100  # as percentage

        daily_state = {
            "daily_pnl_pct": round(daily_pnl_pct, 2),
            "consecutive_losses": consecutive_losses,
            "current_date": today,
        }

        decision = should_sit_out(regime, daily_state)

        return {
            "sit_out": decision.sit_out,
            "reason": decision.reason,
            "suggested_action": decision.suggested_action,
            "regime": regime.regime.value,
            "daily_pnl_pct": daily_state["daily_pnl_pct"],
            "consecutive_losses": consecutive_losses,
        }

    except Exception as exc:
        logger.exception("Sit-out check failed")
        raise HTTPException(status_code=500, detail=f"Sit-out check failed: {exc}")


# ---------------------------------------------------------------------------
# GET /traders-mind/journal
# ---------------------------------------------------------------------------

@router.get("/journal")
async def get_journal(limit: int = Query(20, ge=1, le=100)):
    """Return recent trade journal entries."""
    journal = get_trade_journal()
    trades = journal.get_recent_trades(limit=limit)
    return {"total": len(trades), "trades": trades}


# ---------------------------------------------------------------------------
# GET /traders-mind/journal/stats
# ---------------------------------------------------------------------------

@router.get("/journal/stats")
async def get_journal_stats():
    """Return aggregate trade journal statistics."""
    journal = get_trade_journal()
    stats = journal.get_stats()

    return {
        "total_trades": stats.total_trades,
        "winning_trades": stats.winning_trades,
        "losing_trades": stats.losing_trades,
        "win_rate": stats.win_rate,
        "avg_hold_hours": stats.avg_hold_hours,
        "win_rate_by_regime": stats.win_rate_by_regime,
        "win_rate_by_confluence": stats.win_rate_by_confluence,
        "win_rate_by_dow": stats.win_rate_by_dow,
        "best_performer": stats.best_performer,
        "worst_performer": stats.worst_performer,
    }


# ---------------------------------------------------------------------------
# GET /traders-mind/journal/lessons
# ---------------------------------------------------------------------------

@router.get("/journal/lessons")
async def get_journal_lessons():
    """Return pattern-based insights from the trade journal."""
    journal = get_trade_journal()
    lessons = journal.get_lessons()
    return {"lessons": lessons, "count": len(lessons)}


# ---------------------------------------------------------------------------
# GET /traders-mind/fomc-dates
# ---------------------------------------------------------------------------

@router.get("/fomc-dates")
async def get_fomc_dates():
    """Return the list of 2026 FOMC meeting dates."""
    return {
        "dates": sorted([d.isoformat() for d in _FOMC_DATES_2026]),
        "count": len(_FOMC_DATES_2026),
    }
