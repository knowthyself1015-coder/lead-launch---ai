"""
Technical analysis engine — pure Python + numpy implementation.

All indicators and pattern detection are implemented from scratch.
No external TA libraries (no TA-Lib, no pandas_ta).

Provides:
- 9 indicator calculations (RSI, MACD, EMA, SMA, VWAP, ATR, Bollinger,
  Support/Resistance, Fibonacci)
- 5 pattern detectors (Bull Flag, Cup & Handle, Double Bottom,
  Breakout, Trend Reversal)
- Main `analyze()` and `analyze_batch()` entry points
- Standalone `detect_patterns()` function
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TechnicalResult:
    """Full technical analysis result for a single symbol."""
    symbol: str
    timestamp: datetime
    indicators: dict = field(default_factory=dict)
    patterns: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bars_to_arrays(bars: list) -> dict[str, np.ndarray]:
    """Convert a list of Bar objects to numpy arrays.

    The market data provider returns Bar objects with:
      open, high, low, close, volume, timestamp, vwap, symbol

    Returns dict with numpy arrays keyed by field name.
    """
    if not bars:
        raise ValueError("No bar data provided")

    n = len(bars)
    out = {
        "open": np.zeros(n),
        "high": np.zeros(n),
        "low": np.zeros(n),
        "close": np.zeros(n),
        "volume": np.zeros(n, dtype=np.float64),
        "timestamps": [None] * n,
    }
    # vwap may or may not be present
    has_vwap = all(getattr(b, "vwap", None) is not None for b in bars)
    if has_vwap:
        out["vwap"] = np.zeros(n)

    for i, b in enumerate(bars):
        out["open"][i] = b.open
        out["high"][i] = b.high
        out["low"][i] = b.low
        out["close"][i] = b.close
        out["volume"][i] = b.volume
        out["timestamps"][i] = b.timestamp
        if has_vwap:
            out["vwap"][i] = b.vwap

    return out


# ---------------------------------------------------------------------------
# Indicator implementations (pure numpy, no external libraries)
# ---------------------------------------------------------------------------

def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average.

    Uses Wilder's smoothing: alpha = 2 / (period + 1).
    For the initial value, we use SMA of the first 'period' elements.
    """
    n = len(data)
    result = np.full(n, np.nan)
    if n < period:
        return result

    alpha = 2.0 / (period + 1.0)
    # Initial SMA seed
    result[period - 1] = np.mean(data[:period])
    for i in range(period, n):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    n = len(data)
    result = np.full(n, np.nan)
    if n < period:
        return result
    # Cumulative sum approach for efficiency
    cumsum = np.cumsum(np.insert(data, 0, 0))
    result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result


def compute_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index (Wilder's smoothing).

    RSI = 100 - 100 / (1 + RS), where RS = avg_gain / avg_loss.
    Uses Wilder's smoothing (EMA of gains/losses).
    """
    n = len(close)
    result = np.full(n, np.nan)
    if n < period + 1:
        return result

    delta = np.diff(close)
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)

    # Initial average gain/loss (simple mean of first 'period' deltas)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    # Wilder's smoothing for the rest
    for i in range(period + 1, n):
        avg_gain = ((avg_gain * (period - 1)) + gains[i - 1]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i - 1]) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))

    return result


def compute_macd(close: np.ndarray,
                 fast: int = 12,
                 slow: int = 26,
                 signal: int = 9) -> dict[str, np.ndarray]:
    """MACD — Moving Average Convergence Divergence.

    Returns dict with: macd_line, signal_line, histogram.
    Signal line is computed only on the valid (non-NaN) portion
    of the MACD line to avoid NaN cascading from the slow EMA seed.
    """
    n = len(close)
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = np.full(n, np.nan)

    # The MACD line becomes valid after the slow EMA seeds (index slow-1).
    first_valid = slow - 1
    if first_valid < n:
        valid_slice = macd_line[first_valid:]
        if len(valid_slice) >= signal:
            signal_valid = _ema(valid_slice, signal)
            # signal_valid[signal-1:] maps to signal_line[first_valid+signal-1:]
            signal_line[first_valid + signal - 1:] = signal_valid[signal - 1:]

    histogram = macd_line - signal_line
    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
    }


def compute_emas(close: np.ndarray) -> dict[str, np.ndarray]:
    """Compute EMA for standard periods: 9, 20, 50, 200."""
    return {
        "ema_9": _ema(close, 9),
        "ema_20": _ema(close, 20),
        "ema_50": _ema(close, 50),
        "ema_200": _ema(close, 200),
    }


def compute_smas(close: np.ndarray) -> dict[str, np.ndarray]:
    """Compute SMA for standard periods: 20, 50, 200."""
    return {
        "sma_20": _sma(close, 20),
        "sma_50": _sma(close, 50),
        "sma_200": _sma(close, 200),
    }


def compute_vwap(high: np.ndarray, low: np.ndarray,
                 close: np.ndarray, volume: np.ndarray,
                 timestamps: list,
                 intraday_reset: bool = True) -> np.ndarray:
    """Volume Weighted Average Price.

    Typical price = (high + low + close) / 3.
    VWAP = cumulative(typical_price * volume) / cumulative(volume).

    If intraday_reset is True, the cumulative sum resets each day.
    """
    n = len(close)
    typical_price = (high + low + close) / 3.0
    pv = typical_price * volume

    result = np.full(n, np.nan)

    if not intraday_reset:
        cum_pv = np.cumsum(pv)
        cum_vol = np.cumsum(volume)
        mask = cum_vol > 0
        result[mask] = cum_pv[mask] / cum_vol[mask]
        return result

    # Intraday reset: group by trading day
    cum_pv = 0.0
    cum_vol = 0.0
    last_day = None

    for i in range(n):
        ts = timestamps[i]
        day = ts.date() if hasattr(ts, "date") else ts
        if last_day is not None and day != last_day:
            cum_pv = 0.0
            cum_vol = 0.0
        cum_pv += pv[i]
        cum_vol += volume[i]
        if cum_vol > 0:
            result[i] = cum_pv / cum_vol
        last_day = day

    return result


def compute_atr(high: np.ndarray, low: np.ndarray,
                close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range (Wilder's smoothing).

    True Range = max(high - low, |high - prev_close|, |low - prev_close|).
    """
    n = len(close)
    result = np.full(n, np.nan)
    if n < period + 1:
        return result

    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    # Initial ATR as simple average of first 'period' TR values (skip tr[0]=0)
    result[period] = np.mean(tr[1:period + 1])

    # Wilder's smoothing
    for i in range(period + 1, n):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period

    return result


def compute_bollinger(close: np.ndarray, period: int = 20,
                      num_std: float = 2.0) -> dict[str, np.ndarray]:
    """Bollinger Bands.

    Returns: upper, middle, lower, bandwidth_pct.
    bandwidth_pct = (upper - lower) / middle * 100.
    """
    n = len(close)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    bandwidth = np.full(n, np.nan)

    middle = _sma(close, period)
    if n < period:
        return {"upper": upper, "middle": middle, "lower": lower, "bandwidth_pct": bandwidth}

    # Rolling standard deviation
    for i in range(period - 1, n):
        window = close[i - period + 1:i + 1]
        std = np.std(window, ddof=1)  # sample std
        upper[i] = middle[i] + num_std * std
        lower[i] = middle[i] - num_std * std
        if middle[i] != 0:
            bandwidth[i] = (upper[i] - lower[i]) / middle[i] * 100

    return {
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "bandwidth_pct": bandwidth,
    }


def _find_local_extrema(data: np.ndarray, order: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Find local minima and maxima using neighbourhood comparison.

    A point is a local maximum if it's greater than 'order' points
    on either side. Similarly for minima.
    """
    n = len(data)
    maxima_idx = []
    minima_idx = []

    for i in range(order, n - order):
        if np.all(data[i] >= data[i - order:i + order + 1]):
            maxima_idx.append(i)
        if np.all(data[i] <= data[i - order:i + order + 1]):
            minima_idx.append(i)

    return np.array(maxima_idx), np.array(minima_idx)


def _cluster_levels(levels: np.ndarray, tolerance: float = 0.05) -> np.ndarray:
    """Cluster nearby price levels within tolerance % of each other.

    Returns the mean of each cluster, sorted ascending.
    """
    if len(levels) == 0:
        return np.array([])

    sorted_levels = np.sort(levels)
    clusters = []
    current_cluster = [sorted_levels[0]]

    for level in sorted_levels[1:]:
        if abs(level - current_cluster[-1]) / current_cluster[-1] <= tolerance:
            current_cluster.append(level)
        else:
            clusters.append(np.mean(current_cluster))
            current_cluster = [level]
    clusters.append(np.mean(current_cluster))

    return np.array(clusters)


def compute_support_resistance(high: np.ndarray, low: np.ndarray,
                               close: np.ndarray,
                               tolerance: float = 0.05) -> dict[str, list[float]]:
    """Find key support and resistance levels.

    Uses local minima for support and local maxima for resistance,
    then clusters levels within the tolerance %.
    """
    # Use close for extrema detection, high/low for actual levels
    _, minima_idx = _find_local_extrema(close, order=5)
    maxima_idx, _ = _find_local_extrema(close, order=5)

    support_levels = close[minima_idx] if len(minima_idx) > 0 else np.array([])
    resistance_levels = close[maxima_idx] if len(maxima_idx) > 0 else np.array([])

    support_clustered = _cluster_levels(support_levels, tolerance)
    resistance_clustered = _cluster_levels(resistance_levels, tolerance)

    return {
        "support": sorted(support_clustered.tolist()),
        "resistance": sorted(resistance_clustered.tolist(), reverse=True),
    }


def compute_fibonacci(high: np.ndarray, low: np.ndarray,
                      close: np.ndarray) -> dict[str, Any]:
    """Fibonacci retracement levels from recent swing high to swing low.

    Finds the most recent significant swing high and swing low
    over the entire lookback, then calculates key Fibonacci levels.
    """
    n = len(close)
    if n < 20:
        return {"swing_high": None, "swing_low": None, "levels": {}, "direction": "unknown"}

    maxima_idx, minima_idx = _find_local_extrema(close, order=5)

    if len(maxima_idx) == 0 or len(minima_idx) == 0:
        return {"swing_high": None, "swing_low": None, "levels": {}, "direction": "unknown"}

    # Determine if we're in an uptrend or downtrend based on recent price action
    # Use the last 20 bars slope
    recent_close = close[-20:]
    x = np.arange(20)
    slope = np.polyfit(x, recent_close, 1)[0]

    if slope >= 0:
        # Uptrend: fib retracement from high to low (expecting pullback)
        swing_high_idx = maxima_idx[-1]
        # Find the most recent swing low before the high
        valid_lows = minima_idx[minima_idx < swing_high_idx]
        if len(valid_lows) == 0:
            return {"swing_high": None, "swing_low": None, "levels": {}, "direction": "unknown"}
        swing_low_idx = valid_lows[-1]
        direction = "uptrend"
    else:
        # Downtrend: fib retracement from low to high (expecting bounce)
        swing_low_idx = minima_idx[-1]
        valid_highs = maxima_idx[maxima_idx < swing_low_idx]
        if len(valid_highs) == 0:
            return {"swing_high": None, "swing_low": None, "levels": {}, "direction": "unknown"}
        swing_high_idx = valid_highs[-1]
        direction = "downtrend"

    swing_high = float(close[swing_high_idx])
    swing_low = float(close[swing_low_idx])

    fib_ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    diff = swing_high - swing_low

    levels = {}
    for ratio in fib_ratios:
        if direction == "uptrend":
            level = swing_high - diff * ratio
        else:
            level = swing_low + diff * ratio
        levels[str(ratio)] = round(level, 2)

    return {
        "swing_high": swing_high,
        "swing_low": swing_low,
        "levels": levels,
        "direction": direction,
    }


# ---------------------------------------------------------------------------
# Pattern Detection (all from scratch)
# ---------------------------------------------------------------------------

def detect_bull_flag(close: np.ndarray, volume: np.ndarray,
                     high: np.ndarray, low: np.ndarray) -> bool:
    """Detect Bull Flag pattern.

    Criteria:
    1. Sharp rise (flagpole): >= 10% price increase over 5-15 bars
    2. Consolidation channel sloping slightly down: price drifting
       lower within a narrowing range over the next 5-20 bars
    3. Volume declining during consolidation (confirms flag)
    """
    n = len(close)
    if n < 30:
        return False

    # Look backwards from the end to find a sharp rise
    # First find a consolidation period at the end
    lookback = min(40, n)

    # Scan for flagpole + flag pattern
    for pole_end in range(n - 15, n - 5):
        # Flagpole: look for sharp rise ending at pole_end
        for pole_start in range(max(0, pole_end - 15), pole_end - 3):
            pole_pct = (close[pole_end] - close[pole_start]) / close[pole_start]
            if pole_pct < 0.10:
                continue

            # Check volume spike during flagpole
            pole_vol = np.mean(volume[pole_start:pole_end + 1])
            prev_vol = np.mean(volume[max(0, pole_start - 10):pole_start])
            if prev_vol > 0 and pole_vol < prev_vol * 1.2:
                continue  # Not enough volume surge

            # Flag consolidation: bars after pole_end
            flag_end = min(n - 1, pole_end + 20)
            if flag_end - pole_end < 3:
                continue

            flag_close = close[pole_end + 1:flag_end + 1]
            flag_volume = volume[pole_end + 1:flag_end + 1]
            flag_high = high[pole_end + 1:flag_end + 1]
            flag_low = low[pole_end + 1:flag_end + 1]

            # Flag should slope slightly down or be flat
            x = np.arange(len(flag_close))
            flag_slope = np.polyfit(x, flag_close, 1)[0]
            # Normalize by price
            flag_slope_pct = flag_slope / np.mean(flag_close)

            # Must be slightly negative to flat (-5% to 0% slope normalized per bar)
            if flag_slope_pct > 0.001 or flag_slope_pct < -0.015:
                continue

            # Volume should decline during flag
            flag_vol_first_half = np.mean(flag_volume[:len(flag_volume)//2])
            flag_vol_second_half = np.mean(flag_volume[len(flag_volume)//2:])
            if flag_vol_second_half > flag_vol_first_half * 0.9:
                continue

            # Flag should be contained within flagpole range (not breaking above recent high)
            pole_high = np.max(high[pole_start:pole_end + 1])
            if np.max(flag_high) > pole_high * 1.02:
                continue

            return True

    return False


def detect_cup_and_handle(close: np.ndarray, volume: np.ndarray) -> bool:
    """Detect Cup and Handle pattern.

    Criteria:
    1. U-shaped recovery: price drops 10-30%, then recovers to near original level
    2. The cup should be at least 20 bars wide
    3. Handle: small downward drift (5-10%) after the cup, lasting 5-10 bars
    4. Volume higher on the left side of the cup, declining through, rising on right
    """
    n = len(close)
    if n < 40:
        return False

    # Look at the last ~60 bars, find a cup shape
    window = min(60, n)
    segment = close[-window:]

    # Find the highest point in the first 20% of the window (left lip)
    left_third = int(window * 0.3)
    if left_third < 5:
        return False

    left_lip_idx = np.argmax(segment[:left_third])
    left_lip = segment[left_lip_idx]

    # Find the lowest point in the middle portion (cup bottom)
    mid_start = left_lip_idx + 5
    mid_end = int(window * 0.75)
    if mid_end - mid_start < 10:
        return False

    bottom_idx = mid_start + np.argmin(segment[mid_start:mid_end])
    bottom = segment[bottom_idx]

    # Find the right lip (recovery)
    right_start = bottom_idx + 5
    if right_start >= window - 5:
        return False

    right_lip_idx = right_start + np.argmax(segment[right_start:])
    right_lip = segment[right_lip_idx]

    # Cup depth: 10-30%
    cup_depth = (left_lip - bottom) / left_lip
    if cup_depth < 0.05 or cup_depth > 0.35:
        return False

    # Recovery: right lip should be within 5% of left lip
    recovery_pct = (right_lip - bottom) / bottom
    if recovery_pct < cup_depth * 0.6:  # Didn't recover enough
        return False
    if abs(right_lip - left_lip) / left_lip > 0.08:  # Too far from original level
        return False

    # Handle: after right lip, small downward drift
    if right_lip_idx >= window - 5:
        return False
    handle_segment = segment[right_lip_idx:]
    if len(handle_segment) < 3:
        return False

    handle_drop = (right_lip - np.min(handle_segment)) / right_lip
    if handle_drop < 0.02 or handle_drop > 0.12:
        return False

    # Volume check: volume should be higher on recovery (right side of cup)
    vol_segment = volume[-window:]
    vol_left = np.mean(vol_segment[:window//3])
    vol_right = np.mean(vol_segment[2*window//3:])
    if vol_right < vol_left * 0.8:
        return False

    return True


def detect_double_bottom(close: np.ndarray) -> bool:
    """Detect Double Bottom pattern (W-shaped reversal).

    Criteria:
    1. Two similar lows within 3% of each other
    2. A peak between them at least 5% above the lows
    3. The two lows should be separated by at least 5 bars
    4. Confirmation: price breaks above the middle peak
    """
    n = len(close)
    if n < 20:
        return False

    # Look in the last 40 bars
    window = min(40, n)
    segment = close[-window:]

    maxima_idx, minima_idx = _find_local_extrema(segment, order=3)

    if len(minima_idx) < 2:
        return False

    # Look at the last two significant minima
    for i in range(len(minima_idx) - 1):
        low1_idx = minima_idx[i]
        low2_idx = minima_idx[i + 1]

        if low2_idx - low1_idx < 5:
            continue

        low1 = segment[low1_idx]
        low2 = segment[low2_idx]

        # Troughs must be within 3%
        if abs(low1 - low2) / max(low1, low2) > 0.03:
            continue

        # Find a peak between the two lows
        between_maxima = maxima_idx[(maxima_idx > low1_idx) & (maxima_idx < low2_idx)]
        if len(between_maxima) == 0:
            continue

        peak_idx = between_maxima[np.argmax(segment[between_maxima])]
        peak = segment[peak_idx]

        # Peak must be at least 5% above lows
        if (peak - min(low1, low2)) / min(low1, low2) < 0.05:
            continue

        # Confirmation: recent price breaks above the middle peak
        if segment[-1] > peak * 0.98:
            return True

    return False


def detect_breakout(close: np.ndarray, volume: np.ndarray,
                    high: np.ndarray) -> bool:
    """Detect price breakout above resistance.

    Criteria:
    1. Recent close above a resistance level
    2. Volume on breakout bar is above 20-period average
    3. The resistance was tested at least once before (validated level)
    """
    n = len(close)
    if n < 30:
        return False

    # Find resistance levels from recent data
    sr = compute_support_resistance(high, np.full(n, np.nan), close, tolerance=0.03)
    resistances = sr.get("resistance", [])

    if not resistances:
        return False

    # Get the nearest resistance above recent price (before breakout)
    recent_close = close[-5]
    for res in resistances:
        if res > recent_close * 0.95 and res < recent_close * 1.15:
            # This resistance is nearby — check if we broke above it
            if close[-1] > res and close[-2] <= res:
                # Price just broke above resistance
                # Volume check
                avg_vol_20 = np.mean(volume[-21:-1])
                if avg_vol_20 > 0 and volume[-1] > avg_vol_20 * 1.2:
                    return True

    return False


def detect_trend_reversal(close: np.ndarray, volume: np.ndarray) -> bool:
    """Detect potential trend reversal.

    Uses two methods:
    1. RSI divergence: price makes higher high but RSI makes lower high
       (bearish divergence) or vice versa (bullish divergence)
    2. Moving average crossover: EMA(9) crosses EMA(20)
    """
    n = len(close)
    if n < 30:
        return False

    rsi = compute_rsi(close, 14)
    ema_9 = _ema(close, 9)
    ema_20 = _ema(close, 20)

    # Method 1: RSI divergence
    # Look at last 20 bars for two swing highs/lows
    lookback = min(30, n)
    segment = close[-lookback:]
    rsi_segment = rsi[-lookback:]

    maxima_idx, minima_idx = _find_local_extrema(segment, order=3)

    # Bearish divergence: price makes higher high, RSI makes lower high
    if len(maxima_idx) >= 2:
        last_two_highs = maxima_idx[-2:]
        if segment[last_two_highs[-1]] > segment[last_two_highs[-2]]:
            if (not np.isnan(rsi_segment[last_two_highs[-1]]) and
                not np.isnan(rsi_segment[last_two_highs[-2]])):
                if rsi_segment[last_two_highs[-1]] < rsi_segment[last_two_highs[-2]]:
                    # Bearish divergence detected
                    return True

    # Bullish divergence: price makes lower low, RSI makes higher low
    if len(minima_idx) >= 2:
        last_two_lows = minima_idx[-2:]
        if segment[last_two_lows[-1]] < segment[last_two_lows[-2]]:
            if (not np.isnan(rsi_segment[last_two_lows[-1]]) and
                not np.isnan(rsi_segment[last_two_lows[-2]])):
                if rsi_segment[last_two_lows[-1]] > rsi_segment[last_two_lows[-2]]:
                    # Bullish divergence detected
                    return True

    # Method 2: EMA crossover
    if not np.isnan(ema_9[-2]) and not np.isnan(ema_20[-2]):
        # Bullish cross
        if ema_9[-2] <= ema_20[-2] and ema_9[-1] > ema_20[-1]:
            return True
        # Bearish cross
        if ema_9[-2] >= ema_20[-2] and ema_9[-1] < ema_20[-1]:
            return True

    return False


# ---------------------------------------------------------------------------
# Unified pattern detection
# ---------------------------------------------------------------------------

def detect_patterns(df_or_bars) -> list[str]:
    """Standalone pattern detector that returns found pattern names.

    Accepts either:
    - A list of Bar objects (from market_data provider)
    - A dict of numpy arrays (from _bars_to_arrays)

    Returns a list of pattern name strings that were detected.
    """
    # Handle Bar objects
    if isinstance(df_or_bars, list) and hasattr(df_or_bars[0], 'close'):
        arrays = _bars_to_arrays(df_or_bars)
    elif isinstance(df_or_bars, dict):
        arrays = df_or_bars
    else:
        raise TypeError("Expected list of Bar objects or dict of numpy arrays")

    close = arrays["close"]
    volume = arrays["volume"]
    high = arrays["high"]
    low = arrays["low"]

    patterns = []

    if detect_bull_flag(close, volume, high, low):
        patterns.append("Bull Flag")
    if detect_cup_and_handle(close, volume):
        patterns.append("Cup and Handle")
    if detect_double_bottom(close):
        patterns.append("Double Bottom")
    if detect_breakout(close, volume, high):
        patterns.append("Breakout")
    if detect_trend_reversal(close, volume):
        patterns.append("Trend Reversal")

    return patterns


# ---------------------------------------------------------------------------
# Main analysis entry points
# ---------------------------------------------------------------------------

def _generate_signals(close: np.ndarray, indicators: dict,
                      patterns: list[str]) -> list[str]:
    """Generate trading signals based on indicators and patterns."""
    signals = []
    n = len(close)
    last = n - 1

    rsi_val = indicators.get("rsi_14")
    if rsi_val is not None and not np.isnan(rsi_val):
        if rsi_val < 30:
            signals.append("BULLISH")
        elif rsi_val > 70:
            signals.append("BEARISH")

    macd = indicators.get("macd", {})
    macd_line = macd.get("macd_line")
    signal_line = macd.get("signal_line")
    if (macd_line is not None and signal_line is not None and
        not np.isnan(macd_line) and not np.isnan(signal_line)):
        if macd_line > signal_line:
            signals.append("BULLISH")
        else:
            signals.append("BEARISH")

    # Check SMA alignment
    sma_20 = indicators.get("sma_20")
    sma_50 = indicators.get("sma_50")
    if sma_20 is not None and sma_50 is not None:
        if not np.isnan(sma_20) and not np.isnan(sma_50):
            if sma_20 > sma_50:
                signals.append("BULLISH")
            else:
                signals.append("BEARISH")

    # Check price vs SMA 200
    sma_200 = indicators.get("sma_200")
    if sma_200 is not None and not np.isnan(sma_200):
        if close[last] > sma_200:
            signals.append("BULLISH")
        else:
            signals.append("BEARISH")

    # Bollinger Band position
    bb = indicators.get("bollinger", {})
    bb_lower = bb.get("lower")
    bb_upper = bb.get("upper")
    if bb_lower is not None and not np.isnan(bb_lower):
        if close[last] < bb_lower:
            signals.append("BULLISH")  # Oversold
        elif bb_upper is not None and not np.isnan(bb_upper) and close[last] > bb_upper:
            signals.append("BEARISH")  # Overbought

    # Pattern signals
    bullish_patterns = {"Bull Flag", "Cup and Handle", "Double Bottom", "Breakout"}
    for p in patterns:
        if p in bullish_patterns:
            signals.append("BULLISH")
        elif p == "Trend Reversal":
            signals.append("BULLISH")  # Could be either; default bullish for reversal detection

    if not signals:
        signals.append("NEUTRAL")

    return signals


def _build_summary(symbol: str, indicators: dict, patterns: list[str],
                   signals: list[str]) -> str:
    """Build a human-readable technical summary string."""
    parts = [f"Technical Analysis for {symbol}:"]

    # RSI
    rsi_val = indicators.get("rsi_14")
    if rsi_val is not None and not np.isnan(rsi_val):
        rsi_str = f"RSI(14)={rsi_val:.1f}"
        if rsi_val > 70:
            rsi_str += " (overbought)"
        elif rsi_val < 30:
            rsi_str += " (oversold)"
        parts.append(rsi_str)

    # MACD
    macd = indicators.get("macd", {})
    if macd.get("macd_line") is not None and not np.isnan(macd["macd_line"]):
        hist = indicators.get("macd_histogram", macd.get("histogram"))
        hist_val = hist if isinstance(hist, (float, np.floating)) else None
        if hist_val is not None and not np.isnan(hist_val):
            direction = "bullish" if hist_val > 0 else "bearish"
            parts.append(f"MACD histogram={direction}")

    # Trend
    sma_20 = indicators.get("sma_20")
    sma_200 = indicators.get("sma_200")
    if sma_20 is not None and sma_200 is not None:
        if not np.isnan(sma_20) and not np.isnan(sma_200):
            trend = "above" if sma_20 > sma_200 else "below"
            parts.append(f"SMA(20) {trend} SMA(200)")

    # Patterns
    if patterns:
        parts.append(f"Patterns: {', '.join(patterns)}")

    # Overall
    bull_count = signals.count("BULLISH")
    bear_count = signals.count("BEARISH")
    if bull_count > bear_count:
        parts.append("Overall: BULLISH")
    elif bear_count > bull_count:
        parts.append("Overall: BEARISH")
    else:
        parts.append("Overall: NEUTRAL")

    return " | ".join(parts)


async def analyze(symbol: str, provider,
                  lookback_days: int = 90) -> TechnicalResult:
    """Run full technical analysis on a single symbol.

    Args:
        symbol: Ticker symbol (e.g. "AAPL")
        provider: MarketDataProvider instance (has async get_bars method)
        lookback_days: Number of calendar days of price history to fetch

    Returns:
        TechnicalResult with all indicators, patterns, signals, and summary.
    """
    end = datetime.utcnow()
    start = end - timedelta(days=lookback_days)

    bars = await provider.get_bars(
        symbol=symbol,
        timeframe="1D",
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        limit=lookback_days + 20,  # buffer
    )

    if not bars or len(bars) < 20:
        logger.warning(f"Insufficient bar data for {symbol} (got {len(bars) if bars else 0})")
        return TechnicalResult(
            symbol=symbol.upper(),
            timestamp=datetime.utcnow(),
            indicators={},
            patterns=[],
            signals=["NEUTRAL"],
            summary=f"Insufficient data for {symbol}",
        )

    arrays = _bars_to_arrays(bars)
    close = arrays["close"]
    high = arrays["high"]
    low = arrays["low"]
    volume = arrays["volume"]
    timestamps = arrays["timestamps"]

    # Compute all indicators
    rsi = compute_rsi(close, 14)
    macd_data = compute_macd(close)
    emas = compute_emas(close)
    smas = compute_smas(close)
    vwap = compute_vwap(high, low, close, volume, timestamps, intraday_reset=True)
    atr = compute_atr(high, low, close, 14)
    bollinger = compute_bollinger(close, 20, 2.0)
    sr = compute_support_resistance(high, low, close)
    fib = compute_fibonacci(high, low, close)

    # Package indicators — only the latest values where appropriate
    last = len(close) - 1
    indicators = {
        # Single latest values
        "rsi_14": round(float(rsi[last]), 2) if not np.isnan(rsi[last]) else None,
        "atr_14": round(float(atr[last]), 2) if not np.isnan(atr[last]) else None,
        # MACD latest values
        "macd": {
            "macd_line": round(float(macd_data["macd_line"][last]), 4) if not np.isnan(macd_data["macd_line"][last]) else None,
            "signal_line": round(float(macd_data["signal_line"][last]), 4) if not np.isnan(macd_data["signal_line"][last]) else None,
            "histogram": round(float(macd_data["histogram"][last]), 4) if not np.isnan(macd_data["histogram"][last]) else None,
        },
        # EMAs
        "ema_9": round(float(emas["ema_9"][last]), 2) if not np.isnan(emas["ema_9"][last]) else None,
        "ema_20": round(float(emas["ema_20"][last]), 2) if not np.isnan(emas["ema_20"][last]) else None,
        "ema_50": round(float(emas["ema_50"][last]), 2) if not np.isnan(emas["ema_50"][last]) else None,
        "ema_200": round(float(emas["ema_200"][last]), 2) if not np.isnan(emas["ema_200"][last]) else None,
        # SMAs
        "sma_20": round(float(smas["sma_20"][last]), 2) if not np.isnan(smas["sma_20"][last]) else None,
        "sma_50": round(float(smas["sma_50"][last]), 2) if not np.isnan(smas["sma_50"][last]) else None,
        "sma_200": round(float(smas["sma_200"][last]), 2) if not np.isnan(smas["sma_200"][last]) else None,
        # VWAP
        "vwap": round(float(vwap[last]), 2) if not np.isnan(vwap[last]) else None,
        # Bollinger Bands
        "bollinger": {
            "upper": round(float(bollinger["upper"][last]), 2) if not np.isnan(bollinger["upper"][last]) else None,
            "middle": round(float(bollinger["middle"][last]), 2) if not np.isnan(bollinger["middle"][last]) else None,
            "lower": round(float(bollinger["lower"][last]), 2) if not np.isnan(bollinger["lower"][last]) else None,
            "bandwidth_pct": round(float(bollinger["bandwidth_pct"][last]), 2) if not np.isnan(bollinger["bandwidth_pct"][last]) else None,
        },
        # Support / Resistance
        "support_resistance": sr,
        # Fibonacci
        "fibonacci": fib,
        # Price context
        "last_close": round(float(close[last]), 2),
        "last_volume": int(volume[last]),
        "avg_volume_20": round(float(np.mean(volume[max(0, last-20):last+1])), 0),
        # Full arrays for charts (optional, may be large)
        "close_series": [round(float(x), 2) for x in close[-60:]],
        "rsi_series": [round(float(x), 2) if not np.isnan(x) else None for x in rsi[-60:]],
    }

    # Detect patterns
    patterns = detect_patterns(arrays)

    # Generate signals
    signals = _generate_signals(close, indicators, patterns)

    # Build summary
    summary = _build_summary(symbol.upper(), indicators, patterns, signals)

    return TechnicalResult(
        symbol=symbol.upper(),
        timestamp=datetime.utcnow(),
        indicators=indicators,
        patterns=patterns,
        signals=signals,
        summary=summary,
    )


async def analyze_batch(symbols: Sequence[str], provider) -> list[TechnicalResult]:
    """Run technical analysis on multiple symbols concurrently.

    Args:
        symbols: List of ticker symbols
        provider: MarketDataProvider instance

    Returns:
        List of TechnicalResult, one per symbol (in order).
    """
    tasks = [analyze(sym, provider) for sym in symbols]
    return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Legacy compatibility wrapper
# ---------------------------------------------------------------------------

async def analyze_technicals(ticker: str, bars: list | None = None,
                             provider=None) -> dict:
    """Legacy wrapper — kept for backwards compatibility with engines/__init__.py.

    If bars are provided directly, use them instead of fetching from provider.
    """
    if bars is not None:
        arrays = _bars_to_arrays(bars)
        close = arrays["close"]
        high = arrays["high"]
        low = arrays["low"]
        volume = arrays["volume"]
        timestamps = arrays["timestamps"]

        rsi = compute_rsi(close, 14)
        macd_data = compute_macd(close)
        smas = compute_smas(close)

        last = len(close) - 1
        patterns = detect_patterns(arrays)

        return {
            "ticker": ticker,
            "technical_score": 0.5,
            "indicators": {
                "rsi_14": round(float(rsi[last]), 2) if not np.isnan(rsi[last]) else None,
                "macd": {
                    "macd_line": round(float(macd_data["macd_line"][last]), 4) if not np.isnan(macd_data["macd_line"][last]) else None,
                    "signal_line": round(float(macd_data["signal_line"][last]), 4) if not np.isnan(macd_data["signal_line"][last]) else None,
                },
                "sma_20": round(float(smas["sma_20"][last]), 2) if not np.isnan(smas["sma_20"][last]) else None,
                "sma_50": round(float(smas["sma_50"][last]), 2) if not np.isnan(smas["sma_50"][last]) else None,
            },
            "patterns": patterns,
            "suggested_entry": None,
            "suggested_stop": None,
            "suggested_target": None,
        }

    if provider is not None:
        result = await analyze(ticker, provider)
        return {
            "ticker": result.symbol,
            "technical_score": 0.5,
            "indicators": result.indicators,
            "patterns": result.patterns,
            "suggested_entry": None,
            "suggested_stop": None,
            "suggested_target": None,
        }

    raise ValueError("Either bars or provider must be provided")
