"""
Scanner engine — scans markets for opportunity candidates.

Responsible for:
- Pulling a universe of stocks from the market data provider
- Running pre-screen checks (price, volume, relative volume)
- Scoring each candidate with a simple composite
- Producing a ranked shortlist for deeper analysis
"""

from __future__ import annotations

import logging
from typing import Optional

from app.engines.market_data import (
    MarketDataProvider,
    ScanResult,
    GainersLosersItem,
    VolumeSpikeItem,
    UnusualOptionsItem,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Symbol universe — top S&P 500 / NASDAQ 100 / Russell 2000 + semis (MVP)
# ---------------------------------------------------------------------------
SCAN_SYMBOLS: list[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JPM",
    "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD", "BAC", "DIS", "NFLX", "ADBE",
    "CRM", "INTC", "AMD", "QCOM", "AVGO", "TXN", "MU", "AMAT", "LRCX", "ADI",
    "SNPS", "CDNS", "MRVL", "KLAC", "ASML",
]


# ---------------------------------------------------------------------------
# Market scan
# ---------------------------------------------------------------------------
async def scan_market(
    provider: MarketDataProvider,
    symbols: Optional[list[str]] = None,
) -> list[ScanResult]:
    """Scan every symbol in *symbols* (default: SCAN_SYMBOLS) and return
    scored results sorted highest-first.

    For each symbol we fetch the latest quote and daily bars, compute a
    handful of simple technical metrics, assign a composite score, and
    return the ranked list.
    """
    if symbols is None:
        symbols = SCAN_SYMBOLS

    results: list[ScanResult] = []

    for sym in symbols:
        try:
            quote = await provider.get_quote(sym)
            if quote is None or quote.price is None or quote.price <= 0:
                continue

            # Fetch daily bars to compute SMA and RSI approximations
            bars = await provider.get_bars(sym, timeframe="1D", limit=60)

            rsi_14 = _approx_rsi(bars, period=14) if bars else None
            above_sma_50 = _above_sma(bars, period=50, price=quote.price) if bars else None
            above_sma_200 = _above_sma(bars, period=200, price=quote.price) if bars else None

            # Relative volume — compare latest volume to 10-day avg
            rel_vol = _relative_volume(bars) if bars else 1.0

            score = _compute_score(
                change_pct=quote.change_pct,
                rel_vol=rel_vol,
                rsi=rsi_14,
                above_sma_50=above_sma_50,
                above_sma_200=above_sma_200,
            )

            results.append(ScanResult(
                symbol=sym,
                price=quote.price,
                change_pct=quote.change_pct,
                volume=quote.volume,
                relative_volume=round(rel_vol, 2),
                rsi_14=round(rsi_14, 1) if rsi_14 is not None else None,
                above_sma_50=above_sma_50,
                above_sma_200=above_sma_200,
                score=round(score, 2),
            ))
        except Exception:
            logger.exception("scan_market: error processing %s", sym)
            continue

    results.sort(key=lambda r: r.score, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Top gainers / losers
# ---------------------------------------------------------------------------
async def scan_top_gainers(
    provider: MarketDataProvider, limit: int = 10
) -> list[GainersLosersItem]:
    """Return top gainers from the market data provider."""
    return await provider.get_top_gainers(limit=limit)


async def scan_top_losers(
    provider: MarketDataProvider, limit: int = 10
) -> list[GainersLosersItem]:
    """Return top losers from the market data provider."""
    return await provider.get_top_losers(limit=limit)


# ---------------------------------------------------------------------------
# Volume spikes
# ---------------------------------------------------------------------------
async def scan_volume_spikes(
    provider: MarketDataProvider,
    min_rvol: float = 2.0,
    limit: int = 20,
) -> list[VolumeSpikeItem]:
    """Return stocks with relative volume above *min_rvol*."""
    return await provider.get_volume_spikes(min_rvol=min_rvol, limit=limit)


# ---------------------------------------------------------------------------
# Unusual options
# ---------------------------------------------------------------------------
async def scan_unusual_options(
    provider: MarketDataProvider,
    symbol: str,
    limit: int = 20,
) -> list[UnusualOptionsItem]:
    """Return unusual options activity for *symbol*."""
    return await provider.get_unusual_options_activity(symbol=symbol, limit=limit)


# ---------------------------------------------------------------------------
# Technical helpers
# ---------------------------------------------------------------------------
def _approx_rsi(bars: list, period: int = 14) -> Optional[float]:
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


def _above_sma(
    bars: list, period: int, price: float
) -> Optional[bool]:
    """Return True if *price* is above the *period*-SMA calculated from *bars*."""
    if len(bars) < period:
        return None
    closes = [b.close for b in bars[-period:]]
    sma = sum(closes) / len(closes)
    return price > sma


def _relative_volume(bars: list) -> float:
    """Latest volume relative to 10-day average."""
    if len(bars) < 11:
        return 1.0
    latest_vol = bars[-1].volume
    avg_vol = sum(b.volume for b in bars[-11:-1]) / 10
    if avg_vol == 0:
        return 1.0
    return latest_vol / avg_vol


def _compute_score(
    change_pct: float,
    rel_vol: float,
    rsi: Optional[float] = None,
    above_sma_50: Optional[bool] = None,
    above_sma_200: Optional[bool] = None,
) -> float:
    """Compute a simple composite momentum score (0-100)."""
    score = 50.0  # neutral baseline

    # Price momentum
    if change_pct > 2:
        score += 15
    elif change_pct > 0:
        score += 5
    elif change_pct < -2:
        score -= 15
    elif change_pct < 0:
        score -= 5

    # Volume confirmation
    if rel_vol > 2.0:
        score += 10
    elif rel_vol > 1.5:
        score += 5

    # RSI
    if rsi is not None:
        if 40 <= rsi <= 70:
            score += 10  # healthy zone
        elif rsi > 70:
            score -= 5  # overbought
        elif rsi < 30:
            score += 5  # oversold — potential bounce

    # Trend
    if above_sma_50 is True:
        score += 5
    if above_sma_200 is True:
        score += 5

    return max(0.0, min(100.0, score))
