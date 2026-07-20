"""
Scoring engine — unified multi-factor model for ranking trade opportunities.

Combines signals from scanner, sentiment, technicals, and market data into a
single 0–100 score per stock, using the weighted categories from the business plan:

    Trend (25) + Volume (20) + Momentum (15) + News (20)
    + Options Flow (10) + Financials (10) = 100 total.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.engines.market_data import (
    MarketDataProvider,
    ScanResult,
    Quote,
    Bar,
    Fundamentals,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ScoreComponents:
    """Breakdown of the 0–100 total score across the six weighted categories."""

    trend: float = 0.0         # max 25
    volume: float = 0.0        # max 20
    momentum: float = 0.0      # max 15
    news: float = 0.0          # max 20
    options_flow: float = 0.0  # max 10
    financials: float = 0.0    # max 10


@dataclass
class StockScore:
    """Complete scoring result for one symbol."""

    symbol: str
    total_score: float  # 0–100
    components: ScoreComponents = field(default_factory=ScoreComponents)
    signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Component scoring functions (pure functions — no I/O)
# ---------------------------------------------------------------------------

def _score_trend(
    above_sma_20_vs_50: Optional[bool] = None,
    above_sma_50_vs_200: Optional[bool] = None,
    above_sma_50: Optional[bool] = None,
    above_sma_200: Optional[bool] = None,
) -> tuple[float, list[str], list[str]]:
    """Score trend alignment (0–25).

    * Price above SMA 50  → +8
    * Price above SMA 200 → +7
    * SMA 20 > SMA 50 (uptrend) → +5
    * SMA 50 > SMA 200 (golden-cross territory) → +5
    """
    score = 0.0
    signals: list[str] = []
    warnings: list[str] = []

    if above_sma_50 is True:
        score += 8
        signals.append("price_above_sma50")
    elif above_sma_50 is False:
        warnings.append("price_below_sma50")

    if above_sma_200 is True:
        score += 7
        signals.append("price_above_sma200")
    elif above_sma_200 is False:
        warnings.append("price_below_sma200")

    if above_sma_20_vs_50 is True:
        score += 5
        signals.append("sma20_above_sma50")
    elif above_sma_20_vs_50 is False:
        warnings.append("sma20_below_sma50")

    if above_sma_50_vs_200 is True:
        score += 5
        signals.append("sma50_above_sma200")
    elif above_sma_50_vs_200 is False:
        warnings.append("sma50_below_sma200")

    return score, signals, warnings


def _score_volume(relative_volume: float) -> tuple[float, list[str], list[str]]:
    """Score relative volume (0–20).

    * Rel vol > 2x      → +20
    * Rel vol 1.5–2x    → +15
    * Rel vol 1.0–1.5x  → +10
    * Rel vol < 1x      → +5
    """
    signals: list[str] = []
    warnings: list[str] = []

    if relative_volume > 2.0:
        score = 20.0
        signals.append("relvol_above_2x")
    elif relative_volume >= 1.5:
        score = 15.0
        signals.append("relvol_15_2x")
    elif relative_volume >= 1.0:
        score = 10.0
        signals.append("relvol_10_15x")
    else:
        score = 5.0
        warnings.append("relvol_below_1x")

    return score, signals, warnings


def _score_momentum(
    rsi: Optional[float] = None,
    rsi_trending_up: Optional[bool] = None,
    macd_above_signal: Optional[bool] = None,
    macd_histogram_increasing: Optional[bool] = None,
) -> tuple[float, list[str], list[str]]:
    """Score momentum indicators (0–15).

    * RSI 40–70 (healthy zone)    → +5
    * RSI trending up              → +5
    * MACD > Signal                → +3
    * MACD histogram increasing    → +2
    """
    score = 0.0
    signals: list[str] = []
    warnings: list[str] = []

    if rsi is not None:
        if 40 <= rsi <= 70:
            score += 5
            signals.append("rsi_healthy")
        elif rsi > 70:
            warnings.append("rsi_overbought")
        elif rsi < 40:
            warnings.append("rsi_weak")

    if rsi_trending_up is True:
        score += 5
        signals.append("rsi_trending_up")
    elif rsi_trending_up is False and rsi is not None:
        warnings.append("rsi_trending_down")

    if macd_above_signal is True:
        score += 3
        signals.append("macd_above_signal")
    elif macd_above_signal is False:
        warnings.append("macd_below_signal")

    if macd_histogram_increasing is True:
        score += 2
        signals.append("macd_histogram_increasing")
    elif macd_histogram_increasing is False:
        warnings.append("macd_histogram_decreasing")

    return score, signals, warnings


def _score_news(sentiment_score: float) -> tuple[float, list[str], list[str]]:
    """Score news sentiment (0–20).

    Uses bullish confidence from the sentiment engine: sentiment_score × 20.
    sentiment_score is expected in [-1.0, +1.0] where positive = bullish.

    Returns a score in [0, 20].
    """
    signals: list[str] = []
    warnings: list[str] = []

    # Clamp sentiment to [0, 1] for scoring — we only reward bullishness
    bullish_confidence = max(0.0, min(1.0, sentiment_score))
    score = bullish_confidence * 20.0

    if score >= 15:
        signals.append("news_strongly_bullish")
    elif score >= 10:
        signals.append("news_moderately_bullish")
    elif score >= 5:
        signals.append("news_slightly_bullish")
    else:
        warnings.append("news_neutral_or_bearish")

    return score, signals, warnings


def _score_options_flow(
    options_activity: Optional[str] = None,
) -> tuple[float, list[str], list[str]]:
    """Score unusual options activity (0–10).

    * Unusual call activity detected → +10
    * Moderate activity              → +5
    * None                           → 0
    """
    signals: list[str] = []
    warnings: list[str] = []

    if options_activity == "unusual_call":
        score = 10.0
        signals.append("unusual_call_activity")
    elif options_activity == "moderate":
        score = 5.0
        signals.append("moderate_options_activity")
    else:
        score = 0.0

    return score, signals, warnings


def _score_financials(
    pe_ratio: Optional[float] = None,
    revenue_growth_positive: Optional[bool] = None,
) -> tuple[float, list[str], list[str]]:
    """Score fundamentals (0–10).

    * P/E ratio reasonable (< 50 or None) → +5
    * Revenue growth positive YoY          → +5
    """
    score = 0.0
    signals: list[str] = []
    warnings: list[str] = []

    if pe_ratio is None:
        # No data — give partial credit rather than zero
        score += 2.5
        warnings.append("pe_ratio_unavailable")
    elif pe_ratio < 50:
        score += 5
        signals.append("pe_ratio_reasonable")
    else:
        warnings.append("pe_ratio_high")

    if revenue_growth_positive is True:
        score += 5
        signals.append("revenue_growth_positive")
    elif revenue_growth_positive is False:
        warnings.append("revenue_growth_negative")

    return score, signals, warnings


# ---------------------------------------------------------------------------
# Bar-analysis helpers (extracted from scanner for re-use)
# ---------------------------------------------------------------------------

def _sma(bars: list[Bar], period: int) -> Optional[float]:
    """Compute simple moving average from *bars*."""
    if len(bars) < period:
        return None
    closes = [b.close for b in bars[-period:]]
    return sum(closes) / len(closes)


def _approx_rsi(bars: list[Bar], period: int = 14) -> Optional[float]:
    """Compute a simple RSI-14 from daily close prices."""
    if len(bars) < period + 1:
        return None
    closes = [b.close for b in bars[-(period + 1):]]
    gains = 0.0
    losses = 0.0
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        if delta > 0:
            gains += delta
        else:
            losses += abs(delta)
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _relative_volume(bars: list[Bar]) -> float:
    """Latest volume relative to 10-day average."""
    if len(bars) < 11:
        return 1.0
    latest_vol = bars[-1].volume
    avg_vol = sum(b.volume for b in bars[-11:-1]) / 10
    if avg_vol == 0:
        return 1.0
    return latest_vol / avg_vol


# ---------------------------------------------------------------------------
# Main scoring entry-points
# ---------------------------------------------------------------------------

async def score_stock(
    symbol: str,
    provider: MarketDataProvider,
    sentiment_result: Optional[dict] = None,
    technical_result: Optional[dict] = None,
    scan_result: Optional[ScanResult] = None,
) -> StockScore:
    """Compute the full 0–100 score for a single symbol.

    Parameters
    ----------
    symbol : str
        Ticker symbol.
    provider : MarketDataProvider
        Provider for quotes, bars, fundamentals, and options data.
    sentiment_result : dict | None
        Pre-fetched sentiment analysis result.  If ``None`` the engine will
        attempt to call ``analyze_sentiment``.
    technical_result : dict | None
        Pre-fetched technical analysis result.  If ``None`` the engine will
        attempt to call ``analyze_technicals``.
    scan_result : ScanResult | None
        Pre-fetched scan result.  If ``None`` the engine will fetch bars and
        compute the necessary metrics internally.

    Returns
    -------
    StockScore
    """
    all_signals: list[str] = []
    all_warnings: list[str] = []

    # ------------------------------------------------------------------
    # 1. Fetch raw data when not pre-supplied
    # ------------------------------------------------------------------
    bars: list[Bar] = []
    quote: Optional[Quote] = None
    fundamentals: Optional[Fundamentals] = None
    rsi_value: Optional[float] = None
    above_sma_50: Optional[bool] = None
    above_sma_200: Optional[bool] = None
    rel_vol: float = 1.0

    if scan_result is not None:
        rsi_value = scan_result.rsi_14
        above_sma_50 = scan_result.above_sma_50
        above_sma_200 = scan_result.above_sma_200
        rel_vol = scan_result.relative_volume

    # Always fetch bars for SMA cross calculations (scan_result only gives
    # price-vs-SMA, not SMA-vs-SMA).  We also need bars for MACD.
    try:
        bars = await provider.get_bars(symbol, timeframe="1D", limit=200)
    except Exception:
        logger.warning("score_stock: could not fetch bars for %s", symbol)

    # Compute trend cross signals from bars
    sma_20 = _sma(bars, 20)
    sma_50 = _sma(bars, 50)
    sma_200 = _sma(bars, 200)

    above_sma_20_vs_50: Optional[bool] = None
    if sma_20 is not None and sma_50 is not None:
        above_sma_20_vs_50 = sma_20 > sma_50

    above_sma_50_vs_200: Optional[bool] = None
    if sma_50 is not None and sma_200 is not None:
        above_sma_50_vs_200 = sma_50 > sma_200

    # Compute RSI from bars if not available from scan
    if rsi_value is None:
        rsi_value = _approx_rsi(bars)
    # Compute price-to-SMA if not available
    if above_sma_50 is None and bars:
        try:
            quote = await provider.get_quote(symbol)
        except Exception:
            logger.warning("score_stock: could not fetch quote for %s", symbol)
        if quote and quote.price and sma_50 is not None:
            above_sma_50 = quote.price > sma_50
    if above_sma_200 is None and bars:
        if quote is None:
            try:
                quote = await provider.get_quote(symbol)
            except Exception:
                pass
        if quote and quote.price and sma_200 is not None:
            above_sma_200 = quote.price > sma_200
    # Relative volume
    if bars and len(bars) >= 11:
        rel_vol = _relative_volume(bars)

    # MACD approximation
    macd_above_signal: Optional[bool] = None
    macd_histogram_increasing: Optional[bool] = None
    if len(bars) >= 26:
        ema_12 = _ema(bars, 12)
        ema_26 = _ema(bars, 26)
        if ema_12 is not None and ema_26 is not None:
            macd_line = ema_12 - ema_26
            # Signal line: 9-period EMA of MACD — use the last 9 daily MACD values
            # For simplicity we approximate signal as EMA of MACD over last 9 data points
            macd_values = _macd_series(bars)
            if len(macd_values) >= 2:
                signal_line = _ema_from_values(macd_values, 9)
                if signal_line is not None:
                    macd_above_signal = macd_line > signal_line
                    # histogram increasing if the last two histogram values are rising
                    if len(macd_values) >= 2:
                        hist_latest = macd_values[-1] - signal_line
                        hist_prev = macd_values[-2] - signal_line
                        macd_histogram_increasing = hist_latest > hist_prev

    # RSI trend: compare current RSI to RSI from 3 bars ago
    rsi_trending_up: Optional[bool] = None
    if bars and len(bars) >= 18:  # 14 + 3
        rsi_now = rsi_value
        rsi_prev = _approx_rsi(bars[:-3])
        if rsi_now is not None and rsi_prev is not None:
            rsi_trending_up = rsi_now > rsi_prev

    # ------------------------------------------------------------------
    # 2. Fetch fundamentals
    # ------------------------------------------------------------------
    try:
        fundamentals = await provider.get_fundamentals(symbol)
    except Exception:
        logger.warning("score_stock: could not fetch fundamentals for %s", symbol)

    pe_ratio = fundamentals.pe_ratio if fundamentals else None
    # revenue_growth_positive: we don't have a direct field, approximate
    # from available data — if P/E is reasonable and company has positive EPS
    revenue_growth_positive: Optional[bool] = None
    if fundamentals is not None and fundamentals.eps is not None:
        revenue_growth_positive = fundamentals.eps > 0

    # ------------------------------------------------------------------
    # 3. Options flow
    # ------------------------------------------------------------------
    options_activity: Optional[str] = None
    try:
        unusual_opts = await provider.get_unusual_options_activity(symbol, limit=5)
        if unusual_opts:
            call_count = sum(
                1 for o in unusual_opts if o.contract_type.lower() == "call"
            )
            if call_count >= 2:
                options_activity = "unusual_call"
            elif call_count >= 1:
                options_activity = "moderate"
    except Exception:
        logger.warning("score_stock: could not fetch options for %s", symbol)

    # ------------------------------------------------------------------
    # 4. Sentiment (call engine if not provided)
    # ------------------------------------------------------------------
    sentiment_score = 0.0
    if sentiment_result is not None:
        sentiment_score = sentiment_result.get("sentiment_score", 0.0)
    else:
        try:
            from app.engines.sentiment import analyze_sentiment

            sent = await analyze_sentiment(symbol)
            sentiment_score = sent.get("sentiment_score", 0.0)
        except Exception:
            logger.warning("score_stock: could not fetch sentiment for %s", symbol)

    # ------------------------------------------------------------------
    # 5. Compute each component
    # ------------------------------------------------------------------
    trend, trend_sigs, trend_warns = _score_trend(
        above_sma_20_vs_50=above_sma_20_vs_50,
        above_sma_50_vs_200=above_sma_50_vs_200,
        above_sma_50=above_sma_50,
        above_sma_200=above_sma_200,
    )
    volume, vol_sigs, vol_warns = _score_volume(rel_vol)
    momentum, mom_sigs, mom_warns = _score_momentum(
        rsi=rsi_value,
        rsi_trending_up=rsi_trending_up,
        macd_above_signal=macd_above_signal,
        macd_histogram_increasing=macd_histogram_increasing,
    )
    news, news_sigs, news_warns = _score_news(sentiment_score)
    opts, opts_sigs, opts_warns = _score_options_flow(options_activity)
    fin, fin_sigs, fin_warns = _score_financials(
        pe_ratio=pe_ratio,
        revenue_growth_positive=revenue_growth_positive,
    )

    # Aggregate
    components = ScoreComponents(
        trend=round(trend, 2),
        volume=round(volume, 2),
        momentum=round(momentum, 2),
        news=round(news, 2),
        options_flow=round(opts, 2),
        financials=round(fin, 2),
    )
    all_signals = (
        trend_sigs + vol_sigs + mom_sigs + news_sigs + opts_sigs + fin_sigs
    )
    all_warnings = (
        trend_warns + vol_warns + mom_warns + news_warns + opts_warns + fin_warns
    )
    total = trend + volume + momentum + news + opts + fin

    # Clamp to [0, 100]
    total = max(0.0, min(100.0, total))

    return StockScore(
        symbol=symbol,
        total_score=round(total, 2),
        components=components,
        signals=all_signals,
        warnings=all_warnings,
    )


async def score_batch(
    symbols: list[str],
    provider: MarketDataProvider,
    sentiment_results: Optional[dict[str, dict]] = None,
    technical_results: Optional[dict[str, dict]] = None,
    scan_results: Optional[dict[str, ScanResult]] = None,
) -> list[StockScore]:
    """Score multiple symbols concurrently, returning results sorted desc by
    total_score.
    """
    sentiment_map = sentiment_results or {}
    technical_map = technical_results or {}
    scan_map = scan_results or {}

    async def _score_one(sym: str) -> StockScore:
        return await score_stock(
            sym,
            provider,
            sentiment_result=sentiment_map.get(sym),
            technical_result=technical_map.get(sym),
            scan_result=scan_map.get(sym),
        )

    tasks = [_score_one(s) for s in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    scores: list[StockScore] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning("score_batch: error scoring %s: %s", symbols[i], result)
            scores.append(
                StockScore(
                    symbol=symbols[i],
                    total_score=0.0,
                    warnings=[f"scoring_error: {result}"],
                )
            )
        else:
            scores.append(result)

    scores.sort(key=lambda s: s.total_score, reverse=True)
    return scores


async def get_top_opportunities(
    symbols: list[str],
    provider: MarketDataProvider,
    threshold: float = 85.0,
    sentiment_results: Optional[dict[str, dict]] = None,
    technical_results: Optional[dict[str, dict]] = None,
    scan_results: Optional[dict[str, ScanResult]] = None,
) -> list[StockScore]:
    """Score *symbols* and return only those with total_score >= *threshold*,
    sorted highest-first.
    """
    all_scores = await score_batch(
        symbols,
        provider,
        sentiment_results=sentiment_results,
        technical_results=technical_results,
        scan_results=scan_results,
    )
    return [s for s in all_scores if s.total_score >= threshold]


# ---------------------------------------------------------------------------
# Internal helpers for MACD / EMA
# ---------------------------------------------------------------------------

def _ema(bars: list[Bar], period: int) -> Optional[float]:
    """Exponential moving average over *period* bars."""
    if len(bars) < period:
        return None
    closes = [b.close for b in bars[-period:]]
    multiplier = 2.0 / (period + 1)
    ema_val = closes[0]
    for price in closes[1:]:
        ema_val = (price - ema_val) * multiplier + ema_val
    return ema_val


def _macd_series(bars: list[Bar]) -> list[float]:
    """Compute MACD line values for each bar where both EMAs are available."""
    values: list[float] = []
    for i in range(26, len(bars) + 1):
        window = bars[:i]
        e12 = _ema(window, 12)
        e26 = _ema(window, 26)
        if e12 is not None and e26 is not None:
            values.append(e12 - e26)
    return values


def _ema_from_values(values: list[float], period: int) -> Optional[float]:
    """EMA of a pre-computed series."""
    if len(values) < period:
        return None
    subset = values[-period:]
    multiplier = 2.0 / (period + 1)
    ema_val = subset[0]
    for v in subset[1:]:
        ema_val = (v - ema_val) * multiplier + ema_val
    return ema_val


# ---------------------------------------------------------------------------
# Backward-compatible wrapper (original stub signature → new model)
# ---------------------------------------------------------------------------

async def score_candidate(
    ticker: str,
    scanner_score: float = 0.0,
    sentiment_score: float = 0.0,
    technical_score: float = 0.0,
    fundamental_score: float = 0.0,
) -> dict:
    """Legacy wrapper — use ``score_stock`` for new code.

    Maps the old weighted-average API on top of the new scoring components,
    returning a dict with the same shape as the original stub.
    """
    # Map old sub-scores (0.0–1.0) onto the new component space (100-point scale).
    components = ScoreComponents(
        trend=round(technical_score * 25.0, 2),
        volume=round(scanner_score * 20.0, 2),
        momentum=round(technical_score * 15.0, 2),
        news=round(sentiment_score * 20.0, 2),
        options_flow=round(scanner_score * 10.0, 2),
        financials=round(fundamental_score * 10.0, 2),
    )
    total = (
        technical_score * 25.0
        + scanner_score * 20.0
        + technical_score * 15.0
        + sentiment_score * 20.0
        + scanner_score * 10.0
        + fundamental_score * 10.0
    )
    # Re-apply legacy weights for the composite
    legacy_weights = {
        "scanner": 0.15,
        "sentiment": 0.25,
        "technical": 0.40,
        "fundamental": 0.20,
    }
    composite = (
        scanner_score * legacy_weights["scanner"]
        + sentiment_score * legacy_weights["sentiment"]
        + technical_score * legacy_weights["technical"]
        + fundamental_score * legacy_weights["fundamental"]
    )

    confidence = "low"
    if composite >= 0.7:
        confidence = "high"
    elif composite >= 0.5:
        confidence = "medium"

    return {
        "ticker": ticker,
        "composite_score": round(composite, 4),
        "scanner_score": scanner_score,
        "sentiment_score": sentiment_score,
        "technical_score": technical_score,
        "fundamental_score": fundamental_score,
        "meets_threshold": composite >= 0.70,
        "confidence_level": confidence,
        # New-style extras
        "total_score_100": round(total, 2),
        "components": components,
    }
