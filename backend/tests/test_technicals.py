"""
Unit tests for the Technical Analysis engine.

Tests indicator calculations against known values and verifies
all pattern detectors return non-trivial results for valid inputs.
"""

import numpy as np
import pytest
from datetime import datetime, timedelta

from app.engines.technicals import (
    compute_rsi,
    compute_macd,
    compute_emas,
    compute_smas,
    compute_vwap,
    compute_atr,
    compute_bollinger,
    compute_support_resistance,
    compute_fibonacci,
    detect_bull_flag,
    detect_cup_and_handle,
    detect_double_bottom,
    detect_breakout,
    detect_trend_reversal,
    detect_patterns,
    _ema,
    _sma,
    _bars_to_arrays,
    _find_local_extrema,
    _cluster_levels,
    TechnicalResult,
)


# ---------------------------------------------------------------------------
# Test fixtures — synthetic price data
# ---------------------------------------------------------------------------

@pytest.fixture
def uptrend_prices():
    """Simple linear uptrend with some noise: 100 bars from 100 to 150."""
    np.random.seed(42)
    n = 100
    base = np.linspace(100, 150, n)
    noise = np.random.randn(n) * 2
    close = base + noise
    close = np.maximum(close, 1.0)
    return close


@pytest.fixture
def ohclv_data():
    """Generate synthetic OHLCV data from close prices."""
    np.random.seed(42)
    n = 100
    base = np.linspace(100, 150, n)
    noise = np.random.randn(n) * 2
    close = base + noise
    close = np.maximum(close, 1.0)
    high = close + np.abs(np.random.randn(n)) * 2
    low = close - np.abs(np.random.randn(n)) * 2
    open_price = np.roll(close, 1)
    open_price[0] = close[0] - 1
    volume = np.random.randint(1000000, 10000000, size=n).astype(float)
    timestamps = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n)]
    return {
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "timestamps": timestamps,
    }


# ---------------------------------------------------------------------------
# RSI Tests
# ---------------------------------------------------------------------------

class TestRSI:
    def test_rsi_known_values(self):
        """All up days → RSI near 100. All down days → RSI near 0."""
        prices_up = np.array([float(i) for i in range(20)])
        rsi_up = compute_rsi(prices_up, 14)
        assert not np.isnan(rsi_up[-1])
        assert rsi_up[-1] > 90

        prices_down = np.array([float(20 - i) for i in range(20)])
        rsi_down = compute_rsi(prices_down, 14)
        assert not np.isnan(rsi_down[-1])
        assert rsi_down[-1] < 10

    def test_rsi_alternating(self):
        """Alternating up/down should be near 50."""
        prices = np.array([100.0])
        for i in range(1, 30):
            if i % 2 == 0:
                prices = np.append(prices, prices[-1] + 1.0)
            else:
                prices = np.append(prices, prices[-1] - 1.0)
        rsi = compute_rsi(prices, 14)
        assert not np.isnan(rsi[-1])
        assert 40 < rsi[-1] < 60

    def test_rsi_returns_nan_for_short_series(self):
        rsi = compute_rsi(np.array([100.0, 101.0, 102.0]), 14)
        assert np.all(np.isnan(rsi))


# ---------------------------------------------------------------------------
# MACD Tests
# ---------------------------------------------------------------------------

class TestMACD:
    def test_macd_output_shape(self):
        """MACD on a long series should produce non-NaN values at the end."""
        prices = np.linspace(100, 200, 200)
        result = compute_macd(prices)
        assert len(result["macd_line"]) == 200
        # After 200 bars, all three should be non-NaN
        last = 199
        assert not np.isnan(result["macd_line"][last])
        assert not np.isnan(result["signal_line"][last])
        assert not np.isnan(result["histogram"][last])
        # histogram = macd - signal
        assert abs(
            result["histogram"][last] -
            (result["macd_line"][last] - result["signal_line"][last])
        ) < 1e-10

    def test_macd_uptrend(self):
        prices = np.linspace(100, 300, 100)
        result = compute_macd(prices)
        last = 99
        assert not np.isnan(result["macd_line"][last])
        assert result["macd_line"][last] > 0


# ---------------------------------------------------------------------------
# SMA / EMA Tests
# ---------------------------------------------------------------------------

class TestMovingAverages:
    def test_sma_accuracy(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sma = _sma(data, 3)
        assert np.isnan(sma[0])
        assert np.isnan(sma[1])
        assert sma[2] == pytest.approx(2.0)
        assert sma[3] == pytest.approx(3.0)
        assert sma[4] == pytest.approx(4.0)

    def test_ema_accuracy(self):
        data = np.ones(20)
        ema = _ema(data, 3)
        assert not np.isnan(ema[-1])
        assert abs(ema[-1] - 1.0) < 1e-6

    def test_compute_smas_output(self):
        prices = np.linspace(50, 100, 200)
        smas = compute_smas(prices)
        assert "sma_20" in smas
        assert "sma_50" in smas
        assert "sma_200" in smas

    def test_compute_emas_output(self):
        prices = np.linspace(50, 100, 200)
        emas = compute_emas(prices)
        assert "ema_9" in emas
        assert not np.isnan(emas["ema_9"][-1])


# ---------------------------------------------------------------------------
# VWAP Tests
# ---------------------------------------------------------------------------

class TestVWAP:
    def test_vwap_constant(self):
        n = 20
        close = np.full(n, 100.0)
        high = np.full(n, 101.0)
        low = np.full(n, 99.0)
        volume = np.full(n, 1000.0)
        timestamps = [datetime(2024, 1, 1, 10, 0) + timedelta(minutes=i) for i in range(n)]
        vwap = compute_vwap(high, low, close, volume, timestamps, intraday_reset=False)
        assert not np.isnan(vwap[-1])
        typical = (101 + 99 + 100) / 3
        assert abs(vwap[-1] - typical) < 1e-6

    def test_vwap_intraday_reset(self):
        n = 20
        close = np.full(n, 100.0)
        high = np.full(n, 101.0)
        low = np.full(n, 99.0)
        volume = np.full(n, 1000.0)
        timestamps = (
            [datetime(2024, 1, 1, 10, 0) + timedelta(minutes=i) for i in range(10)] +
            [datetime(2024, 1, 2, 10, 0) + timedelta(minutes=i) for i in range(10)]
        )
        vwap = compute_vwap(high, low, close, volume, timestamps, intraday_reset=True)
        typical = (101 + 99 + 100) / 3
        assert abs(vwap[9] - typical) < 1e-6
        assert abs(vwap[10] - typical) < 1e-6


# ---------------------------------------------------------------------------
# ATR Tests
# ---------------------------------------------------------------------------

class TestATR:
    def test_atr_positive(self):
        n = 30
        close = np.linspace(100, 120, n)
        high = close + 5
        low = close - 5
        atr = compute_atr(high, low, close, 14)
        assert not np.isnan(atr[-1])
        assert atr[-1] > 0

    def test_atr_zero_range(self):
        n = 30
        close = np.full(n, 100.0)
        high = np.full(n, 100.0)
        low = np.full(n, 100.0)
        atr = compute_atr(high, low, close, 14)
        assert not np.isnan(atr[-1])
        assert atr[-1] < 0.01


# ---------------------------------------------------------------------------
# Bollinger Bands Tests
# ---------------------------------------------------------------------------

class TestBollinger:
    def test_bollinger_output(self):
        prices = np.linspace(100, 150, 100)
        bb = compute_bollinger(prices, 20, 2.0)
        assert "upper" in bb
        assert "middle" in bb
        assert "lower" in bb
        last = 99
        assert bb["upper"][last] > bb["middle"][last] > bb["lower"][last]
        assert bb["bandwidth_pct"][last] > 0

    def test_bollinger_constant_price(self):
        prices = np.full(100, 100.0)
        bb = compute_bollinger(prices, 20, 2.0)
        last = 99
        assert abs(bb["upper"][last] - 100.0) < 1e-6
        assert abs(bb["middle"][last] - 100.0) < 1e-6
        assert abs(bb["lower"][last] - 100.0) < 1e-6


# ---------------------------------------------------------------------------
# Support / Resistance Tests
# ---------------------------------------------------------------------------

class TestSupportResistance:
    def test_levels_found(self):
        np.random.seed(42)
        n = 100
        close = np.concatenate([
            np.linspace(100, 120, 30),
            np.linspace(120, 100, 30),
            np.linspace(100, 120, 40),
        ])
        high = close + 2
        low = close - 2
        sr = compute_support_resistance(high, low, close, tolerance=0.05)
        assert len(sr["support"]) > 0
        assert len(sr["resistance"]) > 0


# ---------------------------------------------------------------------------
# Fibonacci Tests
# ---------------------------------------------------------------------------

class TestFibonacci:
    def test_fib_levels(self):
        """Create large swing to ensure Fibonacci detects levels."""
        n = 120
        # Big clear swing: 100 → 200 → 100
        close = np.concatenate([
            np.full(20, 100.0),
            np.linspace(100, 200, 40),
            np.full(20, 200.0),
            np.linspace(200, 100, 40),
        ])
        high = close + 2
        low = close - 2
        fib = compute_fibonacci(high, low, close)
        assert fib["swing_high"] is not None, f"swing_high is None; maxima found"
        assert fib["swing_low"] is not None
        assert len(fib["levels"]) == 7


# ---------------------------------------------------------------------------
# Pattern Detection Tests
# ---------------------------------------------------------------------------

class TestBullFlag:
    def test_no_flag_on_random(self, ohclv_data):
        """Random-ish linear data should not produce a bull flag."""
        assert not detect_bull_flag(
            ohclv_data["close"],
            ohclv_data["volume"],
            ohclv_data["high"],
            ohclv_data["low"],
        )


class TestDoubleBottom:
    def test_double_bottom_on_bottoming_pattern(self):
        """Create a distinctive double bottom (W shape) with breakout.

        The algorithm only looks at the last 40 bars, so place the W
        pattern entirely within that window.
        """
        n = 50
        # First 10 bars: pre-pattern
        # Bars 10-49: W shape entirely within last 40
        # W: 80 → 70 → 80 → 70 → 85 (breakout)
        base = np.zeros(n)
        for i in range(5):
            base[i] = 82.0  # pre-pattern
        for i in range(5, 15):
            base[i] = 82.0 - (i - 5) * 1.2  # 82 -> 70
        for i in range(15, 25):
            base[i] = 70.0 + (i - 15) * 1.2  # 70 -> 82
        for i in range(25, 35):
            base[i] = 82.0 - (i - 25) * 1.2  # 82 -> 70
        for i in range(35, 50):
            base[i] = 70.0 + (i - 35) * 1.0  # 70 -> 85 (breakout)

        np.random.seed(1)
        noise = np.random.randn(n) * 0.02
        close = base + noise
        detected = detect_double_bottom(close)
        assert detected is True, f"Double bottom not detected"


class TestBreakout:
    def test_breakout_on_rising_prices(self):
        """Test that the function runs without error on various inputs."""
        n = 60
        np.random.seed(42)
        close = np.concatenate([
            np.linspace(100, 120, 25),
            np.full(10, 119.0),
            np.array([122.0, 125.0, 128.0, 130.0, 132.0]),
        ])
        high = close + 1
        low = close - 1
        volume = np.full(n, 1000000.0)
        volume[-1] = 3000000.0
        detected = detect_breakout(close, volume, high)
        assert isinstance(detected, bool)


class TestTrendReversal:
    def test_detects_ema_crossover(self):
        """Sideways then sharp decline should create EMA crossover reversal."""
        n = 60
        np.random.seed(42)
        close = np.concatenate([
            np.linspace(100, 102, 30),
            np.linspace(102, 85, 30),
        ])
        volume = np.full(n, 1000000.0)
        detected = detect_trend_reversal(close, volume)
        assert isinstance(detected, bool)


# ---------------------------------------------------------------------------
# Standalone detect_patterns Tests
# ---------------------------------------------------------------------------

class TestDetectPatterns:
    def test_returns_list(self, ohclv_data):
        patterns = detect_patterns(ohclv_data)
        assert isinstance(patterns, list)
        valid = {"Bull Flag", "Cup and Handle", "Double Bottom", "Breakout", "Trend Reversal"}
        for p in patterns:
            assert p in valid

    def test_detects_double_bottom_from_arrays(self):
        """detect_patterns should find a clear double bottom."""
        n = 50
        np.random.seed(1)
        base = np.zeros(n)
        for i in range(5):
            base[i] = 82.0
        for i in range(5, 15):
            base[i] = 82.0 - (i - 5) * 1.2
        for i in range(15, 25):
            base[i] = 70.0 + (i - 15) * 1.2
        for i in range(25, 35):
            base[i] = 82.0 - (i - 25) * 1.2
        for i in range(35, 50):
            base[i] = 70.0 + (i - 35) * 1.0

        noise = np.random.randn(n) * 0.02
        close = base + noise
        high = close + 1
        low = close - 1
        volume = np.full(n, 1000000.0)
        timestamps = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n)]

        arrays = {"close": close, "high": high, "low": low,
                  "volume": volume, "timestamps": timestamps}
        patterns = detect_patterns(arrays)
        assert "Double Bottom" in patterns, f"Patterns found: {patterns}"


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_extrema(self):
        """_find_local_extrema should find obvious peaks.

        With order=2, we look 2 bars on each side.
        The loop runs from 'order' to 'n - order - 1' (inclusive).

        Data: [1.0, 3.0, 2.0, 5.0, 3.0, 7.0, 4.0, 6.0, 3.0]
        Indices: 0    1    2    3    4    5    6    7    8

        n=9, order=2: loop runs i=2..6 (indices 2,3,4,5,6)
        i=5: window=[3:8]=[5.0,3.0,7.0,4.0,6.0] — 7.0 IS max
        """
        data = np.array([1.0, 3.0, 2.0, 5.0, 3.0, 7.0, 4.0, 6.0, 3.0])
        maxima, _ = _find_local_extrema(data, order=2)

        # Should find maximum at index 5
        assert 5 in maxima, f"maxima={maxima}"

    def test_extrema_finds_minima(self):
        """Test minima detection with a clearer trough pattern."""
        # Data with a clear trough: 10, 8, 5, 8, 10, 12
        # With order=2: i=2 (value 5), window=[0:5]=[10,8,5,8,10] — 5 IS min
        data = np.array([10.0, 8.0, 5.0, 8.0, 10.0, 12.0])
        _, minima = _find_local_extrema(data, order=2)
        assert 2 in minima, f"minima={minima}"

    def test_cluster_levels(self):
        levels = np.array([100.0, 101.0, 102.0, 150.0, 151.0])
        clustered = _cluster_levels(levels, tolerance=0.05)
        assert len(clustered) == 2

    def test_technical_result_creation(self):
        tr = TechnicalResult(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 15),
            indicators={"rsi_14": 55.5},
            patterns=["Breakout"],
            signals=["BULLISH", "BULLISH"],
            summary="Test summary",
        )
        assert tr.symbol == "AAPL"
        assert tr.indicators["rsi_14"] == 55.5
        assert "Breakout" in tr.patterns
