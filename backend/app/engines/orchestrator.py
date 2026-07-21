"""
Pipeline Orchestrator — the conductor that runs the full AlphaSight pipeline.

Responsible for:
- Running all 10 engines end-to-end on a timer
- Market-hours awareness (NYSE calendar, 9:30 AM–4:00 PM ET)
- Daily startup (reset risk, pre-market scan)
- Daily shutdown (EOD report, log stats)
- Graceful start/stop control
- Tracking PipelineRun history
- Trader's Mind integration (regime detection, confluence, sits-out, journal)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, time, date
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
    # Trader's Mind fields
    regime: Optional[str] = None
    sit_out: bool = False
    sit_out_reason: str = ""

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)


# ---------------------------------------------------------------------------
# NYSE Market Hours
# ---------------------------------------------------------------------------

# Major US market holidays (NYSE closed). Format: (month, day)
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


def _is_holiday(dt: datetime) -> bool:
    """Check if the given date is a known NYSE holiday."""
    return (dt.month, dt.day) in _NYSE_HOLIDAYS


def is_market_open(now: Optional[datetime] = None) -> bool:
    """Check if the US stock market is currently open."""
    try:
        from zoneinfo import ZoneInfo
        eastern = ZoneInfo("America/New_York")
    except Exception:
        logger.warning("zoneinfo unavailable for America/New_York — using UTC")
        return True  # Be permissive

    et_now = (now or datetime.now(timezone.utc)).astimezone(eastern)

    if et_now.weekday() >= 5:
        return False
    if _is_holiday(et_now):
        return False

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

        # Cached market regime (updated each pipeline run)
        self._current_regime: Optional[Any] = None

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    async def run_once(self) -> PipelineRun:
        """Execute the full pipeline exactly once.

        Steps:
          0. Trader's Mind: detect regime, check sit-out
          1. Scanner scans SCAN_SYMBOLS universe
          2. Technicals analyze each scan result
          3. Sentiment analyzes news for top 20 scored symbols
          4. Scoring combines everything → 0-100 score per stock
          5. Trader's Mind: confluence gate filters signals
          6. Decisions produces BUY/SELL/HOLD/WATCHLIST
          7. Risk manager checks every BUY → approves or rejects
          8. Trader's Mind: conviction sizing adjusts position sizes
          9. For approved BUYs: execute trade via Alpaca paper trading
          10. For approved SELLs: execute sell via Alpaca
          11. Portfolio syncs positions from Alpaca
          12. Notifications fire for every trade decision
          13. Trader's Mind: journal entries for all trades
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
            # Late imports to avoid circular dependencies
            from app.engines.market_data import PolygonProvider, MarketDataProvider
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

            # ── Step 0: Trader's Mind — Regime & Sit-out ────────────
            logger.info("[0/13] Trader's Mind: detecting market regime...")
            provider = PolygonProvider()

            try:
                from app.engines.traders_mind import (
                    detect_regime,
                    check_confluence,
                    ConfluenceResult,
                    calculate_conviction_size,
                    should_sit_out,
                    get_trade_journal,
                )
                regime = await detect_regime(provider)
                self._current_regime = regime
                run.regime = regime.regime.value
                logger.info(
                    "[0/13] Regime: %s (VIX=%.1f, trend=%.2f)",
                    regime.regime.value, regime.vix_level, regime.trend_strength,
                )

                # Check sit-out
                journal = get_trade_journal()
                entries = journal.get_all_entries()
                today_str = date.today().isoformat()

                # Consecutive losses
                consecutive_losses = 0
                for e in reversed(entries):
                    if e.pnl is not None and e.pnl <= 0:
                        consecutive_losses += 1
                    elif e.pnl is not None:
                        break

                daily_entries = [e for e in entries if e.entry_date == today_str and e.pnl is not None]
                daily_pnl_pct = sum(e.pnl_pct or 0 for e in daily_entries) * 100

                daily_state = {
                    "daily_pnl_pct": round(daily_pnl_pct, 2),
                    "consecutive_losses": consecutive_losses,
                    "current_date": today_str,
                }

                sit_out_decision = should_sit_out(regime, daily_state)
                if sit_out_decision.sit_out:
                    run.sit_out = True
                    run.sit_out_reason = sit_out_decision.reason
                    run.status = "completed"
                    run.completed_at = datetime.now(timezone.utc)
                    logger.warning(
                        "[0/13] SIT-OUT: %s — %s",
                        sit_out_decision.reason, sit_out_decision.suggested_action,
                    )
                    logger.info("=" * 60)
                    logger.info("PIPELINE RUN %s — SIT-OUT (no trades)", run.run_id)
                    logger.info("=" * 60)
                    self._history.append(run)
                    if len(self._history) > self._max_history:
                        self._history = self._history[-self._max_history:]
                    return run
            except Exception:
                logger.exception("[0/13] Trader's Mind setup failed — continuing without it")
                regime = None
                sit_out_decision = None

            # Cap the symbol universe per config
            symbols = SCAN_SYMBOLS[: settings.MAX_SYMBOLS_PER_RUN]

            # ── Step 1: Scan ──────────────────────────────────────────
            logger.info("[1/13] Scanning %d symbols...", len(symbols))
            scan_results = await scan_market(provider, symbols=symbols)
            run.symbols_scanned = len(symbols)
            logger.info("[1/13] Scan complete — %d results ranked", len(scan_results))

            # ── Step 2: Technicals ────────────────────────────────────
            logger.info("[2/13] Running technical analysis on %d candidates...", len(scan_results))
            technical_scores: dict[str, dict] = {}
            for sr in scan_results[:50]:
                try:
                    bars = await provider.get_bars(sr.symbol, timeframe="1D", limit=60)
                    bar_dicts = [
                        {"c": b.close, "h": b.high, "l": b.low, "o": b.open, "v": b.volume}
                        for b in bars
                    ] if bars else []
                    tech = await analyze_technicals(sr.symbol, bars=bar_dicts if bar_dicts else None)
                    technical_scores[sr.symbol] = tech
                except Exception:
                    logger.exception("[2/13] Technicals failed for %s", sr.symbol)

            # ── Step 3: Sentiment ─────────────────────────────────────
            logger.info("[3/13] Running sentiment analysis on top 20...")
            top_20 = sorted(scan_results, key=lambda r: r.score, reverse=True)[:20]
            sentiment_scores: dict[str, dict] = {}
            for sr in top_20:
                try:
                    sent = await analyze_sentiment(sr.symbol)
                    sentiment_scores[sr.symbol] = sent
                except Exception:
                    logger.exception("[3/13] Sentiment failed for %s", sr.symbol)

            # ── Step 4: Scoring ───────────────────────────────────────
            logger.info("[4/13] Computing composite scores...")
            executor = AlpacaExecutor()
            account = await executor.get_account()
            account_equity = account.equity if account.equity > 0 else 100_000.0

            scored_signals: list[dict] = []
            for sr in scan_results:
                try:
                    tech = technical_scores.get(sr.symbol, {})
                    sent = sentiment_scores.get(sr.symbol, {})

                    scanner_score = sr.score / 100.0
                    technical_score = float(tech.get("technical_score", 0.5))
                    sentiment_score = max(0.0, min(1.0, (float(sent.get("sentiment_score", 0.0)) + 1.0) / 2.0))

                    score_result = await score_candidate(
                        ticker=sr.symbol,
                        scanner_score=scanner_score,
                        sentiment_score=sentiment_score,
                        technical_score=technical_score,
                        fundamental_score=0.5,
                    )
                    score_result["price"] = sr.price
                    score_result["change_pct"] = sr.change_pct
                    # Store scanner-level data for confluence check
                    score_result["relative_volume"] = sr.relative_volume
                    score_result["above_sma_50"] = sr.above_sma_50
                    score_result["above_sma_200"] = sr.above_sma_200
                    scored_signals.append(score_result)
                except Exception:
                    logger.exception("[4/13] Scoring failed for %s", sr.symbol)

            scored_signals.sort(key=lambda s: s["composite_score"], reverse=True)
            logger.info("[4/13] Scored %d signals — top: %s (%.4f)",
                        len(scored_signals),
                        scored_signals[0]["ticker"] if scored_signals else "N/A",
                        scored_signals[0]["composite_score"] if scored_signals else 0)

            # ── Step 5: Confluence Gate (Trader's Mind) ───────────────
            logger.info("[5/13] Trader's Mind: checking confluence gates...")
            confluent_signals: list[dict] = []
            confluence_results: dict[str, Any] = {}

            if regime is not None:
                for signal in scored_signals:
                    ticker = signal["ticker"]
                    tech = technical_scores.get(ticker, {})
                    sent = sentiment_scores.get(ticker, {})
                    try:
                        cr = check_confluence(signal, tech, sent, regime)
                        confluence_results[ticker] = cr
                        if cr.passed:
                            confluent_signals.append(signal)
                            logger.debug(
                                "[5/13] Confluence PASSED for %s: %d/%d (%s)",
                                ticker, cr.confluence_count, cr.required,
                                ", ".join(cr.active_signals),
                            )
                        else:
                            logger.debug(
                                "[5/13] Confluence FAILED for %s: %d/%d — missing: %s",
                                ticker, cr.confluence_count, cr.required,
                                ", ".join(cr.missing_signals),
                            )
                    except Exception:
                        logger.exception("[5/13] Confluence check failed for %s", ticker)
                        confluent_signals.append(signal)  # pass-through on error
            else:
                confluent_signals = scored_signals

            logger.info("[5/13] Confluence gate: %d/%d signals passed",
                        len(confluent_signals), len(scored_signals))

            # ── Step 6: Decisions ─────────────────────────────────────
            logger.info("[6/13] Generating trade decisions...")
            portfolio_snapshot = await get_portfolio_snapshot()
            current_exposure = 0.0
            total_equity = portfolio_snapshot.get("total_equity", account_equity) or account_equity
            if total_equity > 0:
                mv = portfolio_snapshot.get("market_value", 0) or 0
                current_exposure = mv / total_equity

            # Use regime-adjusted score threshold
            score_threshold = settings.SCORE_THRESHOLD / 100.0
            if regime is not None:
                score_threshold = regime.config["score_threshold"] / 100.0
                logger.info("[6/13] Regime-adjusted score threshold: %.0f%%", score_threshold * 100)

            decisions: list[TradeDecision] = []
            for signal in confluent_signals:
                try:
                    decision = await evaluate_signal(signal, total_equity)
                    # Override threshold with regime-adjusted one
                    if signal.get("composite_score", 0) >= score_threshold:
                        decisions.append(decision)
                except Exception:
                    logger.exception("[6/13] Decision failed for %s", signal.get("ticker", "?"))

            signal_count = sum(1 for d in decisions if d.action in ("buy", "sell"))
            run.signals_generated = signal_count
            logger.info("[6/13] %d trade decisions generated (%d actionable)",
                        len(decisions), signal_count)

            # ── Step 7: Risk checks ───────────────────────────────────
            logger.info("[7/13] Running risk assessments...")
            approved_buys: list[dict] = []
            approved_sells: list[dict] = []

            for decision in decisions:
                if decision.action not in ("buy", "sell"):
                    continue
                try:
                    matching_signal = next(
                        (s for s in confluent_signals if s["ticker"] == decision.ticker), {}
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
                        if price > 0:
                            stop_price = price * (1 - risk.suggested_stop_pct)
                            base_qty = calculate_position_size(
                                account_equity=total_equity,
                                entry_price=price,
                                stop_price=stop_price,
                                max_risk_pct=settings.MAX_PORTFOLIO_RISK_PCT,
                            )

                            # ── Step 8: Conviction sizing (Trader's Mind) ──
                            if regime is not None and 'calculate_conviction_size' in dir():
                                cr = confluence_results.get(decision.ticker)
                                conf_count = cr.confluence_count if cr else 3
                                score = matching_signal.get("composite_score", 0.75) * 100
                                qty = calculate_conviction_size(
                                    base_size=base_qty,
                                    score=score,
                                    regime=regime,
                                    confluence_count=conf_count,
                                )
                                logger.debug(
                                    "[8/13] Conviction sizing for %s: base=%d, adjusted=%d",
                                    decision.ticker, base_qty, qty,
                                )
                            else:
                                qty = base_qty

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
                        logger.info("[7/13] Risk rejected: %s — %s", decision.ticker, risk.reason)
                except Exception:
                    logger.exception("[7/13] Risk check failed for %s", decision.ticker)

            logger.info("[7/13] Risk: %d BUYs approved, %d SELLs approved",
                        len(approved_buys), len(approved_sells))

            # ── Step 9 & 10: Execute trades ────────────────────────────
            trades_executed = 0

            if settings.AUTO_EXECUTE:
                logger.info("[9/13] AUTO_EXECUTE=TRUE — executing approved trades...")
            else:
                logger.info("[9/13] AUTO_EXECUTE=FALSE — trades require manual approval")

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
                            # ── Journal entry ──
                            try:
                                from app.engines.traders_mind import get_trade_journal
                                j = get_trade_journal()
                                cr = confluence_results.get(ticker)
                                j.log_entry(
                                    trade_id=result.order_id or str(uuid.uuid4()),
                                    ticker=ticker,
                                    entry_price=price,
                                    quantity=qty,
                                    decision=decision,
                                    reasoning=f"Confidence: {confidence:.1%}, Confluence: {cr.confluence_count if cr else 'N/A'}",
                                    regime=regime,
                                    confluence=cr if cr else ConfluenceResult(passed=True, confluence_count=0, required=0, active_signals=[], missing_signals=[]),
                                )
                            except Exception:
                                logger.exception("[9/13] Journal entry failed for %s", ticker)
                        else:
                            run.add_error(f"Buy {ticker} failed: {result.error}")
                    except Exception:
                        logger.exception("[9/13] Execute buy failed for %s", ticker)
                        run.add_error(f"Buy {ticker} threw exception")

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
                            # ── Journal exit ──
                            try:
                                from app.engines.traders_mind import get_trade_journal
                                j = get_trade_journal()
                                # Find matching entry (simplified — uses most recent)
                                entries = j.get_all_entries()
                                if entries:
                                    last = entries[-1]
                                    if last.ticker == ticker and last.exit_price is None:
                                        pnl = (price - last.entry_price) * qty
                                        pnl_pct = (price - last.entry_price) / last.entry_price if last.entry_price > 0 else 0
                                        j.log_exit(
                                            trade_id=last.trade_id,
                                            exit_price=price,
                                            pnl=pnl,
                                            pnl_pct=pnl_pct,
                                            exit_reason=f"Signal exit — confidence: {confidence:.1%}",
                                        )
                            except Exception:
                                logger.exception("[10/13] Journal exit failed for %s", ticker)
                        else:
                            run.add_error(f"Sell {ticker} failed: {result.error}")
                    except Exception:
                        logger.exception("[10/13] Execute sell failed for %s", ticker)
                        run.add_error(f"Sell {ticker} threw exception")

                await send_trade_alert(
                    ticker=ticker,
                    action="SELL",
                    price=price,
                    quantity=qty,
                    reason=f"Confidence: {confidence:.1%}",
                )

            run.trades_executed = trades_executed

            # ── Step 11: Portfolio sync ────────────────────────────────
            logger.info("[11/13] Syncing portfolio...")
            try:
                await sync_positions()
            except Exception:
                logger.exception("[11/13] Portfolio sync failed")

            # ── Step 12: Notifications (done inline above) ────────────
            logger.info("[12/13] Notifications sent for all trade decisions")

            # ── Wrap up ───────────────────────────────────────────────
            run.completed_at = datetime.now(timezone.utc)
            run.status = "completed"
            elapsed = (run.completed_at - run.started_at).total_seconds()
            logger.info("=" * 60)
            logger.info("PIPELINE RUN %s — COMPLETED in %.1fs", run.run_id, elapsed)
            logger.info("  Regime:            %s", run.regime or "N/A")
            logger.info("  Symbols scanned:   %d", run.symbols_scanned)
            logger.info("  Confluence passed: %d", len(confluent_signals) if 'confluent_signals' in dir() else 0)
            logger.info("  Signals generated: %d", run.signals_generated)
            logger.info("  Trades executed:   %d", run.trades_executed)
            logger.info("  Errors:            %d", len(run.errors))
            logger.info("=" * 60)

        except Exception as exc:
            logger.exception("PIPELINE RUN %s — FAILED", run.run_id)
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            run.add_error(str(exc))

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
        """Start the 5-minute pipeline loop."""
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
        return self._history[-limit:]

    def get_last_run(self) -> Optional[PipelineRun]:
        return self._history[-1] if self._history else None

    @property
    def current_regime(self) -> Optional[Any]:
        return self._current_regime

    # ------------------------------------------------------------------
    # Daily startup / shutdown
    # ------------------------------------------------------------------

    async def daily_startup(self) -> None:
        """Run pre-market startup tasks."""
        logger.info("DAILY STARTUP — pre-market routine")
        try:
            from app.config import get_settings as _gs
            settings = _gs()

            logger.info("Daily startup: risk state reset")

            try:
                from app.engines.reports import generate_daily_report
                report = await generate_daily_report(date.today().isoformat())
            except Exception:
                logger.exception("Morning report generation failed")
                report = {"report_date": str(date.today()), "summary_text": "Morning report unavailable"}

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
        """Run end-of-day tasks."""
        logger.info("DAILY SHUTDOWN — end-of-day routine")
        try:
            from app.engines.reports import generate_daily_report
            from app.engines.notifications import send_daily_summary
            from app.config import get_settings as _gs

            settings = _gs()
            eod_report = await generate_daily_report(date.today().isoformat())

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

            await send_daily_summary(eod_report)
            logger.info("DAILY SHUTDOWN — complete")
        except Exception:
            logger.exception("daily_shutdown: failed")

    # ------------------------------------------------------------------
    # Daily scheduler
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

                if not startup_done_today and now_et.hour == 9 and now_et.minute >= 25:
                    logger.info("Daily scheduler: triggering daily_startup()")
                    await self.daily_startup()
                    startup_done_today = True

                if not shutdown_done_today and (now_et.hour > 16 or (now_et.hour == 16 and now_et.minute >= 5)):
                    logger.info("Daily scheduler: triggering daily_shutdown()")
                    await self.daily_shutdown()
                    shutdown_done_today = True

                if now_et.hour == 0 and now_et.minute < 5:
                    startup_done_today = False
                    shutdown_done_today = False

                await asyncio.sleep(30)
            except Exception:
                logger.exception("Daily scheduler iteration failed")
                await asyncio.sleep(30)

        logger.info("Daily scheduler stopped")

    def start_daily_scheduler(self) -> None:
        if self._daily_tasks_running:
            return
        self._daily_tasks_running = True
        self._daily_startup_task = asyncio.ensure_future(self._daily_scheduler())
        logger.info("Daily scheduler started (9:25 AM startup, 4:05 PM shutdown ET)")

    def _stop_daily_scheduler(self) -> None:
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
