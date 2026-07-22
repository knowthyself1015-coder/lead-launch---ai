"""
Pipeline Orchestrator — the conductor that runs the full AlphaSight pipeline.

Responsible for:
- Running the full pipeline on a configurable interval
- Market-hours awareness (NYSE calendar, 9:30 AM–4:00 PM ET)
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
    return (dt.month, dt.day) in _NYSE_HOLIDAYS


def is_market_open(now: Optional[datetime] = None) -> bool:
    """Check if the US stock market is currently open."""
    try:
        from zoneinfo import ZoneInfo
        eastern = ZoneInfo("America/New_York")
    except Exception:
        logger.warning("zoneinfo unavailable for America/New_York — using UTC")
        return True

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
        self._batch_index: int = 0  # rotates through symbol batches

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    async def run_once(self) -> PipelineRun:
        """Execute the full pipeline exactly once."""
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
            from app.engines.market_data import AlpacaProvider
            from app.engines.scanner import scan_market, SCAN_SYMBOLS
            from app.engines.technicals import analyze_technicals
            from app.engines.sentiment import analyze_sentiment
            from app.engines.scoring import score_candidate
            from app.engines.decisions import evaluate_signal, TradeDecision
            from app.engines.risk import assess_risk, calculate_position_size
            from app.engines.portfolio import sync_positions, get_portfolio_snapshot
            from app.engines.notifications import send_trade_alert
            from app.engines.executor import AlpacaExecutor

            # Staggered batching — scan 5 symbols per run, rotating through
            # the full list so all stocks get covered over multiple runs.
            BATCH_SIZE = 5
            total = len(SCAN_SYMBOLS)
            start_idx = self._batch_index % total
            batch_symbols = []
            for i in range(min(BATCH_SIZE, total)):
                batch_symbols.append(SCAN_SYMBOLS[(start_idx + i) % total])
            self._batch_index = (self._batch_index + BATCH_SIZE) % total

            symbols = batch_symbols
            logger.info("Batch rotation: run picks %d symbols starting at index %d/%d",
                        len(symbols), start_idx, total)

            # ── Step 1: Scan ──────────────────────────────────────────
            logger.info("[1/8] Scanning %d symbols...", len(symbols))

            # Alpaca only — no fallback to Polygon
            provider = AlpacaProvider()

            scan_results = await scan_market(provider, symbols=symbols)
            run.symbols_scanned = len(symbols)
            logger.info("[1/8] Scan complete — %d results ranked", len(scan_results))

            # ── Step 2: Technicals ────────────────────────────────────
            logger.info("[2/8] Running technical analysis on %d candidates...", len(scan_results))
            technical_scores: dict[str, dict] = {}
            for sr in scan_results[:50]:
                try:
                    bars = await provider.get_bars(sr.symbol, timeframe="1D", limit=21)
                    bar_dicts = [
                        {"c": b.close, "h": b.high, "l": b.low, "o": b.open, "v": b.volume}
                        for b in bars
                    ] if bars else []
                    tech = await analyze_technicals(sr.symbol, bars=bar_dicts if bar_dicts else None)
                    technical_scores[sr.symbol] = tech
                except Exception:
                    logger.exception("[2/8] Technicals failed for %s", sr.symbol)

            # ── Step 3: Sentiment ─────────────────────────────────────
            logger.info("[3/8] Running sentiment analysis on top 20...")
            top_20 = sorted(scan_results, key=lambda r: r.score, reverse=True)[:20]
            sentiment_scores: dict[str, dict] = {}
            for sr in top_20:
                try:
                    sent = await analyze_sentiment(sr.symbol)
                    sentiment_scores[sr.symbol] = sent
                except Exception:
                    logger.exception("[3/8] Sentiment failed for %s", sr.symbol)

            # ── Step 4: Scoring ───────────────────────────────────────
            logger.info("[4/8] Computing composite scores...")
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
                    scored_signals.append(score_result)
                except Exception:
                    logger.exception("[4/8] Scoring failed for %s", sr.symbol)

            scored_signals.sort(key=lambda s: s["composite_score"], reverse=True)
            logger.info("[4/8] Scored %d signals", len(scored_signals))

            # ── Step 5: Decisions ─────────────────────────────────────
            logger.info("[5/8] Generating trade decisions...")
            portfolio_snapshot = await get_portfolio_snapshot()
            total_equity = portfolio_snapshot.get("total_equity", account_equity) or account_equity

            score_threshold = settings.SCORE_THRESHOLD / 100.0

            decisions: list[TradeDecision] = []
            for signal in scored_signals:
                try:
                    decision = await evaluate_signal(signal, total_equity)
                    if signal.get("composite_score", 0) >= score_threshold:
                        decisions.append(decision)
                except Exception:
                    logger.exception("[5/8] Decision failed for %s", signal.get("ticker", "?"))

            run.signals_generated = len(decisions)
            logger.info("[5/8] %d trade decisions generated", len(decisions))

            # ── Step 6: Risk checks ───────────────────────────────────
            logger.info("[6/8] Running risk assessments...")
            current_exposure = 0.0
            if total_equity > 0:
                mv = portfolio_snapshot.get("market_value", 0) or 0
                current_exposure = mv / total_equity

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
                        if decision.action == "buy" and price > 0:
                            stop_price = price * (1 - risk.suggested_stop_pct)
                            qty = calculate_position_size(
                                account_equity=total_equity,
                                entry_price=price,
                                stop_price=stop_price,
                                max_risk_pct=settings.MAX_PORTFOLIO_RISK_PCT,
                            )
                            decision.quantity = qty
                        elif decision.action == "sell":
                            # For sells, use the existing position quantity
                            pos_data = portfolio_snapshot.get("positions", [])
                            held = next((p for p in pos_data if p.get("symbol", "").upper() == decision.ticker.upper()), None)
                            if held:
                                decision.quantity = int(float(held.get("qty", 0)))
                            else:
                                decision.quantity = 0

                        if decision.action == "buy":
                            approved_buys.append({
                                "ticker": decision.ticker,
                                "price": price,
                                "quantity": decision.quantity,
                                "stop_loss_pct": risk.suggested_stop_pct,
                                "take_profit_pct": risk.suggested_target_pct,
                                "confidence": decision.confidence,
                            })
                        elif decision.action == "sell" and decision.quantity > 0:
                            approved_sells.append({
                                "ticker": decision.ticker,
                                "price": price,
                                "quantity": decision.quantity,
                                "confidence": decision.confidence,
                            })
                    else:
                        logger.info("[6/8] Risk rejected: %s — %s", decision.ticker, risk.reason)
                except Exception:
                    logger.exception("[6/8] Risk check failed for %s", decision.ticker)

            logger.info("[6/8] Risk: %d BUYs approved, %d SELLs approved",
                        len(approved_buys), len(approved_sells))

            # ── Step 7: Execute trades ────────────────────────────────
            trades_executed = 0

            if settings.AUTO_EXECUTE:
                logger.info("[7/8] AUTO_EXECUTE=TRUE — executing approved trades...")
            else:
                logger.info("[7/8] AUTO_EXECUTE=FALSE — trades require manual approval")

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
                        logger.exception("[7/8] Execute buy failed for %s", ticker)
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
                        else:
                            run.add_error(f"Sell {ticker} failed: {result.error}")
                    except Exception:
                        logger.exception("[7/8] Execute sell failed for %s", ticker)
                        run.add_error(f"Sell {ticker} threw exception")

                await send_trade_alert(
                    ticker=ticker,
                    action="SELL",
                    price=price,
                    quantity=qty,
                    reason=f"Confidence: {confidence:.1%}",
                )

            run.trades_executed = trades_executed

            # ── Step 8: Portfolio sync ────────────────────────────────
            logger.info("[8/8] Syncing portfolio...")
            try:
                await sync_positions()
            except Exception:
                logger.exception("[8/8] Portfolio sync failed")

            # ── Wrap up ───────────────────────────────────────────────
            run.completed_at = datetime.now(timezone.utc)
            run.status = "completed"
            elapsed = (run.completed_at - run.started_at).total_seconds()
            logger.info("=" * 60)
            logger.info("PIPELINE RUN %s — COMPLETED in %.1fs", run.run_id, elapsed)
            logger.info("  Symbols scanned:   %d", run.symbols_scanned)
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
        """Start the pipeline loop."""
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

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 20) -> list[PipelineRun]:
        return self._history[-limit:]

    def get_last_run(self) -> Optional[PipelineRun]:
        return self._history[-1] if self._history else None


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
