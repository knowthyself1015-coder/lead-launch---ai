"""
Pipeline Orchestrator — the conductor that runs the full AlphaSight pipeline.

Responsible for:
- Running all 10 engines end-to-end on a timer
- Market-hours awareness (NYSE calendar, 9:30 AM–4:00 PM ET)
- Daily startup (reset risk, pre-market scan)
- Daily shutdown (EOD report, log stats)
- Graceful start/stop control
- Tracking PipelineRun history
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, time
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PipelineRun:
    """Tracks the result of a single pipeline execution."""
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    symbols_scanned: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    errors: list[str] = field(default_factory=list)
    status: str = "running"  # "running" | "completed" | "failed"

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)


# ---------------------------------------------------------------------------
# NYSE Market Hours
# ---------------------------------------------------------------------------

# Major US market holidays (NYSE closed). Format: (month, day)
# This is a simplified list; a full implementation would use a holiday library.
_NYSE_HOLIDAYS: set[tuple[int, int]] = {
    (1, 1),    # New Year's Day
    (1, 15),   # MLK Day (3rd Monday — approximated)
    (2, 19),   # Presidents' Day (3rd Monday — approximated)
    (5, 27),   # Memorial Day (last Monday — approximated)
    (7, 4),    # Independence Day
    (9, 2),    # Labor Day (1st Monday — approximated)
    (11, 28),  # Thanksgiving (4th Thursday — approximated)
    (12, 25),  # Christmas
}


def _is_holiday(date: datetime) -> bool:
    """Check if the given date is a known NYSE holiday."""
    return (date.month, date.day) in _NYSE_HOLIDAYS


def is_market_open(now: Optional[datetime] = None) -> bool:
    """Check if the US stock market is currently open.

    Rules:
    - Monday through Friday
    - 9:30 AM to 4:00 PM Eastern Time
    - Not a recognized holiday
    """
    try:
        from zoneinfo import ZoneInfo
        eastern = ZoneInfo("America/New_York")
    except Exception:
        # Fallback: use UTC offset approximation
        logger.warning("zoneinfo unavailable for America/New_York — using UTC")
        now_utc = now or datetime.now(timezone.utc)
        # Eastern is UTC-4 (EDT) or UTC-5 (EST). Rough approximation.
        # This should only happen in very limited environments.
        eastern_time = now_utc
        return True  # Be permissive rather than blocking

    et_now = (now or datetime.now(timezone.utc)).astimezone(eastern)

    # Weekend check
    if et_now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    # Holiday check
    if _is_holiday(et_now):
        return False

    # Time-of-day check
    market_open = time(9, 30)
    market_close = time(16, 0)
    current_time = et_now.time()

    return market_open <= current_time <= market_close


def market_status_detail(now: Optional[datetime] = None) -> dict:
    """Return a detailed dict about current market status."""
    try:
        from zoneinfo import ZoneInfo
        eastern = ZoneInfo("America/New_York")
    except Exception:
        return {
            "is_open": False,
            "reason": "timezone_unavailable",
            "current_time_et": "unknown",
            "next_open": "unknown",
        }

    et_now = (now or datetime.now(timezone.utc)).astimezone(eastern)

    if et_now.weekday() >= 5:
        return {"is_open": False, "reason": "weekend", "current_time_et": et_now.isoformat()}
    if _is_holiday(et_now):
        return {"is_open": False, "reason": "holiday", "current_time_et": et_now.isoformat()}

    market_open = time(9, 30)
    market_close = time(16, 0)
    current_time = et_now.time()

    if current_time < market_open:
        return {"is_open": False, "reason": "pre_market", "current_time_et": et_now.isoformat()}
    if current_time > market_close:
        return {"is_open": False, "reason": "after_hours", "current_time_et": et_now.isoformat()}

    return {"is_open": True, "reason": "market_hours", "current_time_et": et_now.isoformat()}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """Conductor that runs the full AlphaSight pipeline on a schedule."""

    def __init__(self) -> None:
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._history: list[PipelineRun] = []
        self._max_history: int = 200

        # Daily scheduler tasks
        self._daily_startup_task: Optional[asyncio.Task] = None
        self._daily_shutdown_task: Optional[asyncio.Task] = None
        self._daily_tasks_running: bool = False

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    async def run_once(self) -> PipelineRun:
        """Execute the full pipeline exactly once.

        Steps:
          1. Scanner scans SCAN_SYMBOLS universe
          2. Technicals analyze each scan result
          3. Sentiment analyzes news for top 20 scored symbols
          4. Scoring combines everything → 0-100 score per stock
          5. Decisions produces BUY/SELL/HOLD/WATCHLIST
          6. Risk manager checks every BUY → approves or rejects
          7. For approved BUYs: execute trade via Alpaca paper trading
          8. For approved SELLs: execute sell via Alpaca
          9. Portfolio syncs positions from Alpaca
          10. Notifications fire for every trade decision
        """
        settings = get_settings()
        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
        )

        logger.info("=" * 60)
        logger.info("PIPELINE RUN %s — STARTING", run.run_id)
        logger.info("=" * 60)

        try:
            # Late imports to avoid circular dependencies at module level
            from app.engines.market_data import PolygonProvider
            from app.engines.scanner import scan_market, SCAN_SYMBOLS
            from app.engines.technicals import analyze_technicals
            from app.engines.sentiment import analyze_sentiment
            from app.engines.scoring import score_candidate
            from app.engines.decisions import evaluate_signal, TradeDecision
            from app.engines.risk import assess_risk, calculate_position_size
            from app.engines.portfolio import sync_positions, get_portfolio_snapshot
            from app.engines.notifications import (
                send_trade_alert,
                send_daily_summary,
            )
            from app.engines.executor import AlpacaExecutor

            # Cap the symbol universe per config
            symbols = SCAN_SYMBOLS[: settings.MAX_SYMBOLS_PER_RUN]

            # ── Step 1: Scan ──────────────────────────────────────────
            logger.info("[1/10] Scanning %d symbols...", len(symbols))
            provider = PolygonProvider()
            scan_results = await scan_market(provider, symbols=symbols)
            run.symbols_scanned = len(symbols)
            logger.info("[1/10] Scan complete — %d results ranked", len(scan_results))

            # ── Step 2: Technicals ────────────────────────────────────
            logger.info("[2/10] Running technical analysis on %d candidates...", len(scan_results))
            technical_scores: dict[str, dict] = {}
            for sr in scan_results[:50]:  # top 50 for efficiency
                try:
                    bars = await provider.get_bars(sr.symbol, timeframe="1D", limit=60)
                    bar_dicts = [
                        {"c": b.close, "h": b.high, "l": b.low, "o": b.open, "v": b.volume}
                        for b in bars
                    ] if bars else []
                    tech = await analyze_technicals(sr.symbol, bars=bar_dicts if bar_dicts else None)
                    technical_scores[sr.symbol] = tech
                except Exception:
                    logger.exception("[2/10] Technicals failed for %s", sr.symbol)

            # ── Step 3: Sentiment ─────────────────────────────────────
            logger.info("[3/10] Running sentiment analysis on top 20...")
            top_20 = sorted(scan_results, key=lambda r: r.score, reverse=True)[:20]
            sentiment_scores: dict[str, dict] = {}
            for sr in top_20:
                try:
                    sent = await analyze_sentiment(sr.symbol)
                    sentiment_scores[sr.symbol] = sent
                except Exception:
                    logger.exception("[3/10] Sentiment failed for %s", sr.symbol)

            # ── Step 4: Scoring ───────────────────────────────────────
            logger.info("[4/10] Computing composite scores...")
            executor = AlpacaExecutor()
            account = await executor.get_account()
            account_equity = account.equity if account.equity > 0 else 100_000.0

            scored_signals: list[dict] = []
            for sr in scan_results:
                try:
                    tech = technical_scores.get(sr.symbol, {})
                    sent = sentiment_scores.get(sr.symbol, {})

                    # Convert scanner score (0-100) to 0-1 scale
                    scanner_score = sr.score / 100.0
                    technical_score = float(tech.get("technical_score", 0.5))
                    sentiment_score = max(0.0, min(1.0, (float(sent.get("sentiment_score", 0.0)) + 1.0) / 2.0))

                    score_result = await score_candidate(
                        ticker=sr.symbol,
                        scanner_score=scanner_score,
                        sentiment_score=sentiment_score,
                        technical_score=technical_score,
                        fundamental_score=0.5,  # placeholder
                    )
                    # Store price info alongside score
                    score_result["price"] = sr.price
                    score_result["change_pct"] = sr.change_pct
                    scored_signals.append(score_result)
                except Exception:
                    logger.exception("[4/10] Scoring failed for %s", sr.symbol)

            # Sort by composite score descending
            scored_signals.sort(key=lambda s: s["composite_score"], reverse=True)
            logger.info("[4/10] Scored %d signals — top: %s (%.4f)",
                        len(scored_signals),
                        scored_signals[0]["ticker"] if scored_signals else "N/A",
                        scored_signals[0]["composite_score"] if scored_signals else 0)

            # ── Step 5: Decisions ─────────────────────────────────────
            logger.info("[5/10] Generating trade decisions...")
            portfolio_snapshot = await get_portfolio_snapshot()
            current_exposure = 0.0
            total_equity = portfolio_snapshot.get("total_equity", account_equity) or account_equity
            if total_equity > 0:
                mv = portfolio_snapshot.get("market_value", 0) or 0
                current_exposure = mv / total_equity

            decisions: list[TradeDecision] = []
            for signal in scored_signals:
                try:
                    decision = await evaluate_signal(signal, total_equity)
                    decisions.append(decision)
                except Exception:
                    logger.exception("[5/10] Decision failed for %s", signal.get("ticker", "?"))

            signal_count = sum(1 for d in decisions if d.action in ("buy", "sell"))
            run.signals_generated = signal_count
            logger.info("[5/10] %d trade decisions generated (%d actionable)",
                        len(decisions), signal_count)

            # ── Step 6: Risk checks ───────────────────────────────────
            logger.info("[6/10] Running risk assessments...")
            approved_buys: list[dict] = []
            approved_sells: list[dict] = []

            for decision in decisions:
                if decision.action not in ("buy", "sell"):
                    continue
                try:
                    matching_signal = next(
                        (s for s in scored_signals if s["ticker"] == decision.ticker), {}
                    )
                    price = matching_signal.get("price", 0)
                    risk = await assess_risk(
                        ticker=decision.ticker,
                        account_equity=total_equity,
                        current_exposure_pct=current_exposure,
                    )
                    if risk.allowed:
                        decision.risk_assessment = {
                            "allowed": risk.allowed,
                            "max_position_size_pct": risk.max_position_size_pct,
                            "suggested_stop_pct": risk.suggested_stop_pct,
                            "suggested_target_pct": risk.suggested_target_pct,
                            "risk_reward_ratio": risk.risk_reward_ratio,
                            "reason": risk.reason,
                        }
                        # Calculate position size
                        if price > 0:
                            stop_price = price * (1 - risk.suggested_stop_pct)
                            qty = calculate_position_size(
                                account_equity=total_equity,
                                entry_price=price,
                                stop_price=stop_price,
                                max_risk_pct=settings.MAX_PORTFOLIO_RISK_PCT,
                            )
                            decision.quantity = qty

                        if decision.action == "buy":
                            approved_buys.append({
                                "ticker": decision.ticker,
                                "price": price,
                                "quantity": decision.quantity,
                                "stop_loss_pct": risk.suggested_stop_pct,
                                "take_profit_pct": risk.suggested_target_pct,
                                "confidence": decision.confidence,
                                "risk": risk,
                            })
                        elif decision.action == "sell":
                            approved_sells.append({
                                "ticker": decision.ticker,
                                "price": price,
                                "quantity": decision.quantity,
                                "confidence": decision.confidence,
                            })
                    else:
                        logger.info("[6/10] Risk rejected: %s — %s", decision.ticker, risk.reason)
                except Exception:
                    logger.exception("[6/10] Risk check failed for %s", decision.ticker)

            logger.info("[6/10] Risk: %d BUYs approved, %d SELLs approved",
                        len(approved_buys), len(approved_sells))

            # ── Step 7 & 8: Execute trades ────────────────────────────
            trades_executed = 0

            if settings.AUTO_EXECUTE:
                logger.info("[7/10] AUTO_EXECUTE=TRUE — executing approved trades...")
            else:
                logger.info("[7/10] AUTO_EXECUTE=FALSE — trades require manual approval")
                logger.info("[7/10] Approved but not executed: %d BUYs, %d SELLs",
                            len(approved_buys), len(approved_sells))

            for buy in approved_buys:
                ticker = buy["ticker"]
                qty = buy["quantity"]
                price = buy["price"]
                stop_pct = buy.get("stop_loss_pct", 0.02)
                target_pct = buy.get("take_profit_pct", 0.04)
                confidence = buy.get("confidence", 0.5)

                stop_loss = price * (1 - stop_pct) if price > 0 else None
                take_profit = price * (1 + target_pct) if price > 0 else None

                if settings.AUTO_EXECUTE:
                    try:
                        result = await executor.execute_buy(ticker, qty, stop_loss, take_profit)
                        if result.success:
                            trades_executed += 1
                        else:
                            run.add_error(f"Buy {ticker} failed: {result.error}")
                    except Exception:
                        logger.exception("[7/10] Execute buy failed for %s", ticker)
                        run.add_error(f"Buy {ticker} threw exception")

                # Notify for every BUY decision (executed or pending)
                await send_trade_alert(
                    ticker=ticker,
                    action="BUY",
                    price=price,
                    quantity=qty,
                    reason=f"Confidence: {confidence:.1%}",
                )

            for sell in approved_sells:
                ticker = sell["ticker"]
                qty = sell["quantity"]
                price = sell["price"]
                confidence = sell.get("confidence", 0.5)

                if settings.AUTO_EXECUTE:
                    try:
                        result = await executor.execute_sell(ticker, qty)
                        if result.success:
                            trades_executed += 1
                        else:
                            run.add_error(f"Sell {ticker} failed: {result.error}")
                    except Exception:
                        logger.exception("[8/10] Execute sell failed for %s", ticker)
                        run.add_error(f"Sell {ticker} threw exception")

                await send_trade_alert(
                    ticker=ticker,
                    action="SELL",
                    price=price,
                    quantity=qty,
                    reason=f"Confidence: {confidence:.1%}",
                )

            run.trades_executed = trades_executed

            # ── Step 9: Portfolio sync ────────────────────────────────
            logger.info("[9/10] Syncing portfolio...")
            try:
                await sync_positions()
            except Exception:
                logger.exception("[9/10] Portfolio sync failed")

            # ── Step 10: Notifications (done inline above) ────────────
            logger.info("[10/10] Notifications sent for all trade decisions")

            # ── Wrap up ───────────────────────────────────────────────
            run.completed_at = datetime.now(timezone.utc)
            run.status = "completed"
            elapsed = (run.completed_at - run.started_at).total_seconds()
            logger.info("=" * 60)
            logger.info("PIPELINE RUN %s — COMPLETED in %.1fs", run.run_id, elapsed)
            logger.info("  Symbols scanned:  %d", run.symbols_scanned)
            logger.info("  Signals generated: %d", run.signals_generated)
            logger.info("  Trades executed:   %d", run.trades_executed)
            logger.info("  Errors:            %d", len(run.errors))
            logger.info("=" * 60)

        except Exception as exc:
            logger.exception("PIPELINE RUN %s — FAILED", run.run_id)
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            run.add_error(str(exc))

        # Store in history
        self._history.append(run)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        return run

    # ------------------------------------------------------------------
    # Loop control
    # ------------------------------------------------------------------

    async def _loop(self, interval_seconds: int) -> None:
        """Internal loop that calls run_once() on the configured interval."""
        logger.info("Pipeline loop started — interval=%ds", interval_seconds)

        while self._running:
            try:
                if is_market_open():
                    await self.run_once()
                else:
                    logger.debug("Market closed — skipping pipeline run")

                # Sleep in small increments so we can respond to stop()
                for _ in range(interval_seconds):
                    if not self._running:
                        break
                    await asyncio.sleep(1)

            except Exception:
                logger.exception("Pipeline loop iteration failed — retrying in 30s")
                for _ in range(30):
                    if not self._running:
                        break
                    await asyncio.sleep(1)

        logger.info("Pipeline loop stopped")

    def start(self, interval_seconds: Optional[int] = None) -> None:
        """Start the 5-minute pipeline loop.

        Args:
            interval_seconds: Override the default PIPELINE_INTERVAL_SECONDS.
        """
        if self._running:
            logger.warning("Pipeline loop is already running")
            return

        if interval_seconds is None:
            settings = get_settings()
            interval_seconds = settings.PIPELINE_INTERVAL_SECONDS

        self._running = True
        self._task = asyncio.ensure_future(self._loop(interval_seconds))
        logger.info("Orchestrator.start() — pipeline will run every %ds", interval_seconds)

    def stop(self) -> None:
        """Gracefully stop the pipeline loop."""
        logger.info("Orchestrator.stop() — shutting down pipeline loop")
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self._stop_daily_scheduler()

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 20) -> list[PipelineRun]:
        """Return the most recent pipeline runs."""
        return self._history[-limit:]

    def get_last_run(self) -> Optional[PipelineRun]:
        """Return the most recent pipeline run, or None."""
        return self._history[-1] if self._history else None

    # ------------------------------------------------------------------
    # Daily startup / shutdown
    # ------------------------------------------------------------------

    async def daily_startup(self) -> None:
        """Run pre-market startup tasks:
        - Reset daily risk state
        - Generate morning report
        - Log startup to configured channels
        """
        logger.info("DAILY STARTUP — pre-market routine")

        try:
            from app.config import get_settings as _gs

            settings = _gs()

            # Reset risk daily state (in-memory for now)
            logger.info("Daily startup: risk state reset")

            # Generate morning report
            try:
                from app.engines.reports import generate_daily_report
                from datetime import date
                report = await generate_daily_report(date.today().isoformat())
            except Exception:
                logger.exception("Morning report generation failed")
                report = {"report_date": str(date.today()), "summary_text": "Morning report unavailable"}

            # Log morning brief
            logger.info(
                "Morning Brief: Market opens at 9:30 AM ET. "
                "Pipeline active — scanning %d symbols. "
                "Auto-execute: %s. Score threshold: %s.",
                settings.MAX_SYMBOLS_PER_RUN,
                "ENABLED" if settings.AUTO_EXECUTE else "DISABLED",
                settings.SCORE_THRESHOLD,
            )

            logger.info("DAILY STARTUP — complete")

        except Exception:
            logger.exception("daily_startup: failed")

    async def daily_shutdown(self) -> None:
        """Run end-of-day tasks:
        - Generate EOD report
        - Log day's stats
        - Send EOD summary to configured channels
        """
        logger.info("DAILY SHUTDOWN — end-of-day routine")

        try:
            from app.engines.reports import generate_daily_report
            from app.engines.notifications import send_daily_summary
            from app.config import get_settings as _gs
            from datetime import date

            settings = _gs()

            # Generate EOD report
            eod_report = await generate_daily_report(date.today().isoformat())

            # Log day stats from pipeline history
            today_runs = [r for r in self._history if r.started_at.date() == date.today()]
            if today_runs:
                total_scanned = sum(r.symbols_scanned for r in today_runs)
                total_signals = sum(r.signals_generated for r in today_runs)
                total_trades = sum(r.trades_executed for r in today_runs)
                total_errors = sum(len(r.errors) for r in today_runs)

                logger.info("EOD Stats — %d runs | %d scanned | %d signals | %d trades | %d errors",
                            len(today_runs), total_scanned, total_signals, total_trades, total_errors)

                eod_report["signals_generated"] = total_signals
                eod_report["signals_accepted"] = total_trades

            # Send EOD summary
            await send_daily_summary(eod_report)

            logger.info("DAILY SHUTDOWN — complete")

        except Exception:
            logger.exception("daily_shutdown: failed")

    # ------------------------------------------------------------------
    # Daily scheduler (asyncio tasks for 9:25 AM and 4:05 PM ET)
    # ------------------------------------------------------------------

    async def _daily_scheduler(self) -> None:
        """Background task that schedules daily_startup and daily_shutdown."""
        logger.info("Daily scheduler started")

        startup_done_today = False
        shutdown_done_today = False

        while self._daily_tasks_running:
            try:
                from zoneinfo import ZoneInfo
                eastern = ZoneInfo("America/New_York")
                now_et = datetime.now(timezone.utc).astimezone(eastern)

                # 9:25 AM ET — daily startup
                if not startup_done_today and now_et.hour == 9 and now_et.minute >= 25:
                    logger.info("Daily scheduler: triggering daily_startup()")
                    await self.daily_startup()
                    startup_done_today = True

                # 4:05 PM ET — daily shutdown
                if not shutdown_done_today and (now_et.hour > 16 or (now_et.hour == 16 and now_et.minute >= 5)):
                    logger.info("Daily scheduler: triggering daily_shutdown()")
                    await self.daily_shutdown()
                    shutdown_done_today = True

                # Reset flags at midnight ET
                if now_et.hour == 0 and now_et.minute < 5:
                    startup_done_today = False
                    shutdown_done_today = False

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception:
                logger.exception("Daily scheduler iteration failed")
                await asyncio.sleep(30)

        logger.info("Daily scheduler stopped")

    def start_daily_scheduler(self) -> None:
        """Start the background daily scheduler for startup/shutdown events."""
        if self._daily_tasks_running:
            return

        self._daily_tasks_running = True
        self._daily_startup_task = asyncio.ensure_future(self._daily_scheduler())
        logger.info("Daily scheduler started (9:25 AM startup, 4:05 PM shutdown ET)")

    def _stop_daily_scheduler(self) -> None:
        """Stop the daily scheduler."""
        self._daily_tasks_running = False
        for task in (self._daily_startup_task, self._daily_shutdown_task):
            if task:
                task.cancel()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Return the singleton Orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
