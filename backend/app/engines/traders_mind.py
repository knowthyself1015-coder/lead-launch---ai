"""
Trader's Mind engine — injects experienced-trader judgment into every decision.

Responsible for:
- Market regime detection (trending / ranging / volatile / quiet)
- Confluence gate — independent signal confirmation
- Tiered exit strategy with trailing stops
- Conviction-based position sizing
- Sit-out detection (drawdown, cold streak, Fed day, volatility)
- Trade journal with pattern-based insights
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & Data Models
# ---------------------------------------------------------------------------

class MarketRegimeType(str, Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    QUIET = "QUIET"


# Per-regime configuration table
REGIME_CONFIG: dict[MarketRegimeType, dict[str, Any]] = {
    MarketRegimeType.TRENDING_UP: {
        "score_threshold": 80,
        "risk_per_trade": 1.0,
        "min_confluence": 3,
        "max_positions": 8,
    },
    MarketRegimeType.TRENDING_DOWN: {
        "score_threshold": 90,
        "risk_per_trade": 0.5,
        "min_confluence": 4,
        "max_positions": 3,
    },
    MarketRegimeType.RANGING: {
        "score_threshold": 85,
        "risk_per_trade": 0.75,
        "min_confluence": 3,
        "max_positions": 5,
    },
    MarketRegimeType.VOLATILE: {
        "score_threshold": 95,
        "risk_per_trade": 0.25,
        "min_confluence": 4,
        "max_positions": 2,
    },
    MarketRegimeType.QUIET: {
        "score_threshold": 85,
        "risk_per_trade": 1.0,
        "min_confluence": 2,
        "max_positions": 8,
    },
}


@dataclass
class MarketRegime:
    regime: MarketRegimeType
    vix_level: float
    trend_strength: float  # 0.0–1.0
    description: str
    implications: list[str] = field(default_factory=list)

    @property
    def config(self) -> dict[str, Any]:
        return REGIME_CONFIG[self.regime]


@dataclass
class ConfluenceResult:
    passed: bool
    confluence_count: int
    required: int
    active_signals: list[str]
    missing_signals: list[str]


@dataclass
class TieredExit:
    pct: float       # fraction of position (0.0–1.0)
    target: float    # take-profit price
    stop: Optional[float] = None  # trailing stop when applicable


@dataclass
class TieredExits:
    tiers: list[TieredExit]
    description: str = ""


@dataclass
class SitOutDecision:
    sit_out: bool
    reason: str
    suggested_action: str


@dataclass
class JournalEntry:
    """A single journal entry for a trade."""
    trade_id: str
    ticker: str
    entry_date: str
    exit_date: Optional[str] = None
    direction: str = "long"
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    quantity: int = 0
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    regime: Optional[str] = None
    confluence_count: int = 0
    entry_reasoning: str = ""
    exit_reason: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class JournalStats:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_hold_hours: float = 0.0
    win_rate_by_regime: dict[str, float] = field(default_factory=dict)
    win_rate_by_confluence: dict[int, float] = field(default_factory=dict)
    win_rate_by_dow: dict[str, float] = field(default_factory=dict)
    best_performer: Optional[str] = None
    worst_performer: Optional[str] = None


# ---------------------------------------------------------------------------
# 1. Market Regime Detector
# ---------------------------------------------------------------------------

async def detect_regime(provider) -> MarketRegime:
    """Detect the current market regime by analyzing SPY, QQQ, and VIX.

    Args:
        provider: A market data provider with get_quote and get_bars methods.

    Returns a MarketRegime with classification, VIX level, trend strength,
    description, and trading implications.
    """
    from app.engines.market_data import MarketDataProvider

    vix_level: float = 15.0
    spy_price: float = 0.0
    spy_bars: list = []
    qqq_price: float = 0.0

    # Default return for error cases
    def _default() -> MarketRegime:
        return MarketRegime(
            regime=MarketRegimeType.RANGING,
            vix_level=vix_level,
            trend_strength=0.5,
            description="Unable to determine regime — defaulting to RANGING",
            implications=["Trade cautiously with standard risk parameters"],
        )

    try:
        # Fetch VIX
        vix_quote = await provider.get_quote("VIX")
        if vix_quote is not None and vix_quote.price > 0:
            vix_level = vix_quote.price
    except Exception:
        logger.warning("detect_regime: failed to fetch VIX — using default %.1f", vix_level)

    try:
        # Fetch SPY
        spy_quote = await provider.get_quote("SPY")
        if spy_quote is not None and spy_quote.price > 0:
            spy_price = spy_quote.price
        spy_bars_raw = await provider.get_bars("SPY", timeframe="1D", limit=60)
        if spy_bars_raw:
            spy_bars = spy_bars_raw
    except Exception:
        logger.warning("detect_regime: failed to fetch SPY data")

    try:
        # Fetch QQQ
        qqq_quote = await provider.get_quote("QQQ")
        if qqq_quote is not None and qqq_quote.price > 0:
            qqq_price = qqq_quote.price
    except Exception:
        logger.warning("detect_regime: failed to fetch QQQ")

    if not spy_bars or spy_price <= 0:
        return _default()

    # --- Compute SMAs and ATR from SPY bars ---
    closes = [b.close for b in spy_bars]

    def _sma(data: list[float], period: int) -> Optional[float]:
        if len(data) < period:
            return None
        return sum(data[-period:]) / period

    sma_20 = _sma(closes, 20)
    sma_50 = _sma(closes, 50)

    # ATR (14-period) as a stability measure
    atr_val = _compute_atr(spy_bars, period=14)
    avg_close = sum(closes[-20:]) / min(len(closes), 20)
    atr_pct = (atr_val / avg_close) if avg_close > 0 else 0.02

    # --- Trend strength (0–1) ---
    if sma_50 is not None and spy_price > 0:
        trend_strength = min(1.0, abs(spy_price - sma_50) / spy_price * 10)
    else:
        trend_strength = 0.5

    # --- Classify ---
    regime: MarketRegimeType
    description: str
    implications: list[str]

    if vix_level > 30:
        regime = MarketRegimeType.VOLATILE
        description = f"VIX elevated at {vix_level:.1f} — market under stress"
        implications = [
            "Reduce position sizes to 0.25% risk per trade",
            "Require 4+ confluence signals before entry",
            "Max 2 positions at a time",
            "Tight stops, quick exits — capital preservation mode",
        ]
    elif vix_level < 12:
        regime = MarketRegimeType.QUIET
        description = f"VIX very low at {vix_level:.1f} — complacency risk, but trending opportunities"
        implications = [
            "Standard 1.0% risk per trade",
            "Only 2 confluence signals required",
            "Max 8 positions — ride the calm trend",
            "Watch for sudden volatility expansion",
        ]
    elif sma_20 is not None and sma_50 is not None:
        if spy_price > sma_50 and sma_20 > sma_50 and atr_pct < 0.03:
            regime = MarketRegimeType.TRENDING_UP
            description = "SPY above SMA 50, SMA 20 > SMA 50, ATR stable — bullish trend"
            implications = [
                "Favor longs — trend is your friend",
                "1.0% risk per trade",
                "3+ confluence signals required",
                "Max 8 positions — let winners run",
            ]
        elif spy_price < sma_50 and sma_20 < sma_50:
            regime = MarketRegimeType.TRENDING_DOWN
            description = "SPY below SMA 50, SMA 20 < SMA 50 — bearish trend"
            implications = [
                "Favor shorts or cash — don't fight the trend",
                "0.5% risk per trade, max 3 positions",
                "4+ confluence signals required",
                "Tight stops essential",
            ]
        else:
            regime = MarketRegimeType.RANGING
            description = "SPY moving sideways — no clear trend"
            implications = [
                "Trade ranges — buy support, sell resistance",
                "0.75% risk per trade",
                "3+ confluence signals required",
                "Take profits quickly — don't overstay",
            ]
    else:
        regime = MarketRegimeType.RANGING
        description = "Insufficient data — defaulting to RANGING"
        implications = ["Trade cautiously with standard parameters"]

    cfg = REGIME_CONFIG[regime]
    logger.info(
        "Market Regime: %s (VIX=%.1f, trend=%.2f) — threshold=%d, risk=%.2f%%, "
        "confluence=%d, max_positions=%d",
        regime.value, vix_level, trend_strength,
        cfg["score_threshold"], cfg["risk_per_trade"],
        cfg["min_confluence"], cfg["max_positions"],
    )

    return MarketRegime(
        regime=regime,
        vix_level=round(vix_level, 2),
        trend_strength=round(trend_strength, 2),
        description=description,
        implications=implications,
    )


def _compute_atr(bars: list, period: int = 14) -> float:
    """Compute Average True Range from daily bars."""
    if len(bars) < period + 1:
        return sum(abs(b.high - b.low) for b in bars) / max(len(bars), 1)
    true_ranges: list[float] = []
    for i in range(1, len(bars)):
        prev = bars[i - 1]
        cur = bars[i]
        tr = max(
            cur.high - cur.low,
            abs(cur.high - prev.close),
            abs(cur.low - prev.close),
        )
        true_ranges.append(tr)
    return sum(true_ranges[-period:]) / period


# ---------------------------------------------------------------------------
# 2. Confluence Gate
# ---------------------------------------------------------------------------

def check_confluence(
    scoring_result: dict,
    technical_result: dict,
    sentiment_result: dict,
    regime: MarketRegime,
) -> ConfluenceResult:
    """Check that a BUY signal has confirmation from multiple independent categories.

    Categories:
      1. Technical: RSI healthy (30-70) + MACD bullish
      2. Sentiment: news sentiment score > 0 and confidence > 0.6
      3. Volume: relative_volume > 1.5x
      4. Trend: price above SMA 50 AND SMA 200
      5. Options: unusual call activity

    Args:
        scoring_result: From the scoring engine (may contain rel_vol, above_sma fields).
        technical_result: From technicals engine.
        sentiment_result: From sentiment engine.
        regime: Current market regime.

    Returns a ConfluenceResult.
    """
    active: list[str] = []
    missing: list[str] = []

    # Category 1: Technical (RSI healthy + MACD)
    indicators = technical_result.get("indicators", {}) if technical_result else {}
    rsi = indicators.get("rsi")
    macd_signal = indicators.get("macd_signal")
    macd_line = indicators.get("macd_line")

    rsi_healthy = rsi is not None and 30 <= rsi <= 70
    macd_bullish = (
        macd_line is not None
        and macd_signal is not None
        and macd_line > macd_signal
    )
    if rsi_healthy and macd_bullish:
        active.append("Technical (RSI healthy + MACD bullish)")
    else:
        missing.append("Technical (RSI healthy + MACD bullish)")

    # Category 2: Sentiment
    sent_score = sentiment_result.get("sentiment_score", 0) if sentiment_result else 0
    sent_conf = sentiment_result.get("confidence", 0) if sentiment_result else 0
    if isinstance(sent_score, (int, float)) and sent_score > 0 and sent_conf > 0.6:
        active.append("Sentiment (bullish with confidence > 0.6)")
    else:
        missing.append("Sentiment (bullish with confidence > 0.6)")

    # Category 3: Volume
    rel_vol = scoring_result.get("relative_volume", 1.0)
    if isinstance(rel_vol, (int, float)) and rel_vol > 1.5:
        active.append(f"Volume (rel_vol={rel_vol:.1f}x > 1.5x)")
    else:
        missing.append("Volume (relative volume > 1.5x)")

    # Category 4: Trend
    above_sma_50 = scoring_result.get("above_sma_50")
    above_sma_200 = scoring_result.get("above_sma_200")
    if above_sma_50 and above_sma_200:
        active.append("Trend (price > SMA 50 & SMA 200)")
    else:
        missing.append("Trend (price > SMA 50 & SMA 200)")

    # Category 5: Options (unusual call activity)
    options_data = scoring_result.get("unusual_options", {}) if scoring_result else {}
    call_activity = options_data.get("unusual_call_activity", False) if isinstance(options_data, dict) else False
    if call_activity:
        active.append("Options (unusual call activity)")
    else:
        missing.append("Options (unusual call activity)")

    required = regime.config["min_confluence"]
    passed = len(active) >= required

    logger.debug(
        "Confluence check: %d/%d required — active=%s, missing=%s",
        len(active), required, active, missing,
    )

    return ConfluenceResult(
        passed=passed,
        confluence_count=len(active),
        required=required,
        active_signals=active,
        missing_signals=missing,
    )


# ---------------------------------------------------------------------------
# 3. Tiered Exit Strategy
# ---------------------------------------------------------------------------

def calculate_tiered_exits(
    entry_price: float,
    stop_loss: float,
    rr_ratio: float = 2.0,
) -> TieredExits:
    """Calculate a three-tier exit plan.

    - Tier 1 (50%): Take profit at 2:1 RR
    - Tier 2 (30%): Take profit at 4:1 RR
    - Tier 3 (20%): Let it run with trailing stop

    Args:
        entry_price: The fill price.
        stop_loss: The initial stop-loss price.
        rr_ratio: Base risk:reward ratio for tier 1 (default 2.0 → 2:1).
    """
    risk = abs(entry_price - stop_loss)
    if risk <= 0:
        risk = entry_price * 0.02  # fallback 2%

    tier1_target = entry_price + (risk * rr_ratio)       # 2:1
    tier2_target = entry_price + (risk * rr_ratio * 2.0)  # 4:1

    tiers = [
        TieredExit(pct=0.50, target=round(tier1_target, 2), stop=None),
        TieredExit(pct=0.30, target=round(tier2_target, 2), stop=None),
        TieredExit(
            pct=0.20,
            target=0.0,  # no fixed target — trailing
            stop=None,   # trailing stop calculated dynamically
        ),
    ]

    return TieredExits(
        tiers=tiers,
        description=(
            f"Tiered exit: 50% @ {tier1_target:.2f} (2:1), "
            f"30% @ {tier2_target:.2f} (4:1), "
            f"20% trailing"
        ),
    )


# ---------------------------------------------------------------------------
# 4. Trailing Stop Calculator
# ---------------------------------------------------------------------------

def calculate_trailing_stop(
    current_price: float,
    highest_price: float,
    atr: float,
    multiplier: float = 2.0,
) -> float:
    """Calculate a trailing stop for a long position.

    Trail stop at: highest_price - (ATR * multiplier).
    Never move the stop DOWN.

    Args:
        current_price: The current market price.
        highest_price: The highest price seen since entry.
        atr: Average True Range value.
        multiplier: ATR multiplier for stop distance (default 2.0).
    """
    if atr <= 0:
        atr = current_price * 0.02  # fallback 2%

    new_stop = highest_price - (atr * multiplier)

    # Never let the stop exceed current price (for longs)
    if new_stop > current_price:
        new_stop = current_price * 0.995  # slightly below current

    return round(new_stop, 2)


def adjust_trailing_stop(
    current_stop: float,
    proposed_stop: float,
) -> float:
    """Adjust trailing stop — never move DOWN for long positions.

    Args:
        current_stop: The current stop level.
        proposed_stop: The newly calculated stop level.
    """
    return max(current_stop, proposed_stop)


# ---------------------------------------------------------------------------
# 5. Conviction-Based Position Sizing
# ---------------------------------------------------------------------------

def calculate_conviction_size(
    base_size: int,
    score: float,
    regime: MarketRegime,
    confluence_count: int,
) -> int:
    """Adjust position size based on conviction strength.

    Adjustments:
      - score ≥ 95        → 1.2x base
      - score 85–90       → 0.8x base
      - confluence ≥ 4    → 1.1x
      - confluence = 3    → 1.0x
      - confluence = 2    → 0.7x
      - VOLATILE regime   → 0.5x

    Final size is clamped to never exceed original risk rules
    (the base size already respects risk parameters; we only shrink or modestly expand).

    Args:
        base_size: Base share count from the risk engine.
        score: Composite score (0–100 scale).
        regime: Current MarketRegime.
        confluence_count: Number of active confluence signals.
    """
    if base_size <= 0:
        return 0

    multiplier = 1.0

    # Score adjustments
    if score >= 95:
        multiplier *= 1.2
    elif 85 <= score < 90:
        multiplier *= 0.8

    # Confluence adjustments
    if confluence_count >= 4:
        multiplier *= 1.1
    elif confluence_count == 3:
        multiplier *= 1.0
    elif confluence_count == 2:
        multiplier *= 0.7

    # Regime adjustments
    if regime.regime == MarketRegimeType.VOLATILE:
        multiplier *= 0.5

    # Clamp: never exceed 1.5x the base size, never go below 10% of base
    multiplier = max(0.1, min(1.5, multiplier))

    adjusted = int(round(base_size * multiplier))
    return max(1, adjusted)


# ---------------------------------------------------------------------------
# 6. Sit-Out Detector
# ---------------------------------------------------------------------------

# 2026 FOMC meeting dates (2-day meetings — we flag both days)
_FOMC_DATES_2026: set[date] = {
    date(2026, 1, 28), date(2026, 1, 29),
    date(2026, 3, 18), date(2026, 3, 19),
    date(2026, 5, 6),  date(2026, 5, 7),
    date(2026, 6, 17), date(2026, 6, 18),
    date(2026, 7, 29), date(2026, 7, 30),
    date(2026, 9, 16), date(2026, 9, 17),
    date(2026, 11, 4), date(2026, 11, 5),
    date(2026, 12, 9), date(2026, 12, 10),
}


def should_sit_out(
    regime: MarketRegime,
    daily_state: dict,
) -> SitOutDecision:
    """Determine whether the agent should sit out of trading today.

    Triggers (checked in order):
      1. VOLATILE regime + daily loss > 0%
      2. 3+ consecutive losses
      3. Fed announcement day
      4. Daily loss > 2%

    Args:
        regime: Current MarketRegime.
        daily_state: Dict with keys: daily_pnl_pct (float), consecutive_losses (int),
                     current_date (str or date).

    Returns a SitOutDecision.
    """
    daily_pnl_pct = float(daily_state.get("daily_pnl_pct", 0) or 0)
    consecutive_losses = int(daily_state.get("consecutive_losses", 0) or 0)

    # Parse current date
    cur_date_str = daily_state.get("current_date", "")
    if cur_date_str:
        try:
            cur_date = date.fromisoformat(str(cur_date_str)[:10])
        except (ValueError, TypeError):
            cur_date = date.today()
    else:
        cur_date = date.today()

    # 1. VOLATILE + any loss
    if regime.regime == MarketRegimeType.VOLATILE and daily_pnl_pct < 0:
        return SitOutDecision(
            sit_out=True,
            reason="Market volatile — protect capital",
            suggested_action="Reduce to 0.25% risk or sit out entirely. "
                            "Wait for VIX to settle below 30.",
        )

    # 2. Three consecutive losses
    if consecutive_losses >= 3:
        return SitOutDecision(
            sit_out=True,
            reason="On a cold streak — 3 consecutive losses",
            suggested_action="Step back, review recent trades in journal, "
                            "come back tomorrow with fresh eyes.",
        )

    # 3. Fed day
    if cur_date in _FOMC_DATES_2026:
        return SitOutDecision(
            sit_out=True,
            reason=f"Fed announcement day ({cur_date.isoformat()})",
            suggested_action="Wait for the dust to settle. "
                            "FOMC days are high-volatility events. "
                            "Resume trading after the announcement.",
        )

    # 4. Daily loss > 2%
    if daily_pnl_pct < -2.0:
        return SitOutDecision(
            sit_out=True,
            reason=f"Daily loss limit approaching ({daily_pnl_pct:.1f}%)",
            suggested_action="Halt trading for today. "
                            "Review what went wrong in the journal. "
                            "Protect remaining capital.",
        )

    return SitOutDecision(
        sit_out=False,
        reason="All clear — no sit-out conditions triggered",
        suggested_action="Continue trading with standard parameters",
    )


# ---------------------------------------------------------------------------
# 7. Trade Journal
# ---------------------------------------------------------------------------

class TradeJournal:
    """Journal that records every trade entry and exit for post-hoc analysis."""

    def __init__(self) -> None:
        self._entries: list[JournalEntry] = []

    def log_entry(
        self,
        trade_id: str,
        ticker: str,
        entry_price: float,
        quantity: int,
        decision: Any,
        reasoning: str,
        regime: MarketRegime,
        confluence: ConfluenceResult,
    ) -> JournalEntry:
        """Record why we entered a trade."""
        entry = JournalEntry(
            trade_id=trade_id,
            ticker=ticker,
            entry_date=date.today().isoformat(),
            direction="long",
            entry_price=entry_price,
            quantity=quantity,
            regime=regime.regime.value if regime else None,
            confluence_count=confluence.confluence_count,
            entry_reasoning=reasoning,
        )
        self._entries.append(entry)
        logger.info("Journal: ENTRY %s %s @ %.2f — %s", ticker, trade_id, entry_price, reasoning)
        return entry

    def log_exit(
        self,
        trade_id: str,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        exit_reason: str = "",
    ) -> Optional[JournalEntry]:
        """Record why we exited a trade."""
        for entry in self._entries:
            if entry.trade_id == trade_id:
                entry.exit_date = date.today().isoformat()
                entry.exit_price = exit_price
                entry.pnl = round(pnl, 2)
                entry.pnl_pct = round(pnl_pct, 4)
                entry.exit_reason = exit_reason
                logger.info(
                    "Journal: EXIT %s %s — PnL: $%.2f (%.2f%%) — %s",
                    entry.ticker, trade_id, pnl, pnl_pct * 100, exit_reason,
                )
                return entry
        logger.warning("Journal: no entry found for trade_id=%s on exit", trade_id)
        return None

    def get_stats(self) -> JournalStats:
        """Compute journal statistics."""
        stats = JournalStats()
        closed = [e for e in self._entries if e.pnl is not None]
        stats.total_trades = len(closed)

        if not closed:
            return stats

        winners = [e for e in closed if (e.pnl or 0) > 0]
        losers = [e for e in closed if (e.pnl or 0) <= 0]
        stats.winning_trades = len(winners)
        stats.losing_trades = len(losers)
        stats.win_rate = round(len(winners) / len(closed), 4) if closed else 0.0

        # Win rate by regime
        regime_groups: dict[str, list[JournalEntry]] = {}
        for e in closed:
            r = e.regime or "UNKNOWN"
            regime_groups.setdefault(r, []).append(e)
        for r, entries in regime_groups.items():
            w = sum(1 for e_ in entries if (e_.pnl or 0) > 0)
            stats.win_rate_by_regime[r] = round(w / len(entries), 4)

        # Win rate by confluence count
        conf_groups: dict[int, list[JournalEntry]] = {}
        for e in closed:
            c = e.confluence_count
            conf_groups.setdefault(c, []).append(e)
        for c, entries in conf_groups.items():
            w = sum(1 for e_ in entries if (e_.pnl or 0) > 0)
            stats.win_rate_by_confluence[c] = round(w / len(entries), 4)

        # Win rate by day of week
        dow_groups: dict[str, list[JournalEntry]] = {}
        for e in closed:
            try:
                d = date.fromisoformat(e.entry_date)
                dow = d.strftime("%A")
            except (ValueError, TypeError):
                dow = "Unknown"
            dow_groups.setdefault(dow, []).append(e)
        for dow, entries in dow_groups.items():
            w = sum(1 for e_ in entries if (e_.pnl or 0) > 0)
            stats.win_rate_by_dow[dow] = round(w / len(entries), 4)

        # Best / worst performer
        pnl_map = {e.ticker: (e.pnl or 0) for e in closed}
        if pnl_map:
            stats.best_performer = max(pnl_map, key=pnl_map.get)  # type: ignore[arg-type]
            stats.worst_performer = min(pnl_map, key=pnl_map.get)  # type: ignore[arg-type]

        # Average hold time (approximate — days)
        holds: list[float] = []
        for e in closed:
            if e.entry_date and e.exit_date:
                try:
                    d1 = date.fromisoformat(e.entry_date)
                    d2 = date.fromisoformat(e.exit_date)
                    holds.append((d2 - d1).total_seconds() / 3600.0)
                except (ValueError, TypeError):
                    pass
        if holds:
            stats.avg_hold_hours = round(sum(holds) / len(holds), 1)

        return stats

    def get_lessons(self) -> list[str]:
        """Generate pattern-based insights from the journal."""
        lessons: list[str] = []
        stats = self.get_stats()

        if stats.total_trades < 5:
            lessons.append("Not enough trades yet — keep journaling for meaningful patterns.")
            return lessons

        # Confluence insight
        high_conf = stats.win_rate_by_confluence.get(4, 0)
        low_conf = stats.win_rate_by_confluence.get(2, 0)
        if high_conf > 0 and low_conf > 0 and high_conf > low_conf:
            lessons.append(
                f"You win {high_conf:.0%} of trades with 4+ confluence signals "
                f"vs {low_conf:.0%} with 2. More confirmation = better outcomes."
            )
        elif high_conf > 0.6:
            lessons.append(
                f"Trades with 4+ confluence signals win {high_conf:.0%} of the time — "
                "stick to high-confluence setups."
            )

        # Regime insight
        trending = stats.win_rate_by_regime.get("TRENDING_UP", 0)
        ranging = stats.win_rate_by_regime.get("RANGING", 0)
        if trending > 0 and ranging > 0 and trending > ranging:
            lessons.append(
                f"Win rate in TRENDING_UP ({trending:.0%}) beats RANGING ({ranging:.0%}). "
                "Trend is your friend."
            )

        # Day of week insight
        mondays = stats.win_rate_by_dow.get("Monday", 0)
        fridays = stats.win_rate_by_dow.get("Friday", 0)
        if mondays > 0 and fridays > 0:
            if fridays > mondays:
                lessons.append(f"Fridays ({fridays:.0%}) outperform Mondays ({mondays:.0%}).")
            elif mondays > fridays:
                lessons.append(f"Mondays ({mondays:.0%}) outperform Fridays ({fridays:.0%}).")

        # Overall
        if stats.win_rate >= 0.6:
            lessons.append(
                f"Overall win rate: {stats.win_rate:.0%} across {stats.total_trades} trades. "
                "Keep doing what works."
            )
        elif stats.win_rate < 0.4:
            lessons.append(
                f"Overall win rate: {stats.win_rate:.0%} — below 40%. "
                "Review losing trades for common patterns."
            )

        if stats.worst_performer:
            lessons.append(
                f"Worst performer: {stats.worst_performer}. "
                "Consider avoiding this ticker or adjusting your approach."
            )

        return lessons

    def get_recent_trades(self, limit: int = 20) -> list[dict]:
        """Return the most recent journal entries as dictionaries."""
        recent = self._entries[-limit:]
        return [
            {
                "trade_id": e.trade_id,
                "ticker": e.ticker,
                "entry_date": e.entry_date,
                "exit_date": e.exit_date,
                "direction": e.direction,
                "entry_price": e.entry_price,
                "exit_price": e.exit_price,
                "quantity": e.quantity,
                "pnl": e.pnl,
                "pnl_pct": e.pnl_pct,
                "regime": e.regime,
                "confluence_count": e.confluence_count,
                "entry_reasoning": e.entry_reasoning,
                "exit_reason": e.exit_reason,
            }
            for e in recent
        ]

    def get_all_entries(self) -> list[JournalEntry]:
        """Return all journal entries."""
        return list(self._entries)


# ---------------------------------------------------------------------------
# Singleton journal
# ---------------------------------------------------------------------------

_trade_journal: Optional[TradeJournal] = None


def get_trade_journal() -> TradeJournal:
    """Return the singleton TradeJournal instance."""
    global _trade_journal
    if _trade_journal is None:
        _trade_journal = TradeJournal()
    return _trade_journal
