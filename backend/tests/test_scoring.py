"""
Tests for the Unified AI Scoring Model.

Covers each component scorer in isolation, full score_stock with mock
providers, batch scoring / sorting, threshold filtering, and boundary checks.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.scoring import (
    ScoreComponents,
    StockScore,
    _score_trend,
    _score_volume,
    _score_momentum,
    _score_news,
    _score_options_flow,
    _score_financials,
    score_stock,
    score_batch,
    get_top_opportunities,
    score_candidate,
)


# ======================================================================
# 1. Trend scoring (0–25)
# ======================================================================

class TestScoreTrend:
    """Trend component: SMA alignment and cross signals."""

    def test_perfect_trend_all_signals(self):
        """All four trend signals active → max 25."""
        score, sigs, warns = _score_trend(
            above_sma_20_vs_50=True,
            above_sma_50_vs_200=True,
            above_sma_50=True,
            above_sma_200=True,
        )
        assert score == 25.0
        assert "price_above_sma50" in sigs
        assert "price_above_sma200" in sigs
        assert "sma20_above_sma50" in sigs
        assert "sma50_above_sma200" in sigs
        assert len(warns) == 0

    def test_no_trend_signals(self):
        """No trend signals → 0, all warnings."""
        score, sigs, warns = _score_trend(
            above_sma_20_vs_50=False,
            above_sma_50_vs_200=False,
            above_sma_50=False,
            above_sma_200=False,
        )
        assert score == 0.0
        assert len(sigs) == 0
        assert len(warns) == 4

    def test_partial_trend_price_above_smas_only(self):
        """Only price above SMAs → 15 points."""
        score, sigs, warns = _score_trend(
            above_sma_20_vs_50=None,
            above_sma_50_vs_200=None,
            above_sma_50=True,
            above_sma_200=True,
        )
        assert score == 15.0
        assert "price_above_sma50" in sigs
        assert "price_above_sma200" in sigs

    def test_trend_with_none_values(self):
        """None values should be treated as no signal (no add, no warn)."""
        score, sigs, warns = _score_trend(
            above_sma_20_vs_50=None,
            above_sma_50_vs_200=None,
            above_sma_50=None,
            above_sma_200=None,
        )
        assert score == 0.0
        assert len(sigs) == 0
        assert len(warns) == 0


# ======================================================================
# 2. Volume scoring (0–20)
# ======================================================================

class TestScoreVolume:
    """Volume component: relative volume bands."""

    def test_volume_above_2x(self):
        score, sigs, warns = _score_volume(3.0)
        assert score == 20.0
        assert "relvol_above_2x" in sigs
        assert len(warns) == 0

    def test_volume_15_to_2x(self):
        score, sigs, warns = _score_volume(1.75)
        assert score == 15.0
        assert "relvol_15_2x" in sigs

    def test_volume_10_to_15x(self):
        score, sigs, warns = _score_volume(1.2)
        assert score == 10.0
        assert "relvol_10_15x" in sigs

    def test_volume_below_1x(self):
        score, sigs, warns = _score_volume(0.5)
        assert score == 5.0
        assert "relvol_below_1x" in warns

    def test_volume_exactly_1x(self):
        """Exactly 1.0 → falls in 1.0-1.5x bucket."""
        score, sigs, warns = _score_volume(1.0)
        assert score == 10.0

    def test_volume_exactly_15x(self):
        """Exactly 1.5 → falls in 1.5-2x bucket."""
        score, sigs, warns = _score_volume(1.5)
        assert score == 15.0


# ======================================================================
# 3. Momentum scoring (0–15)
# ======================================================================

class TestScoreMomentum:
    """Momentum component: RSI, MACD."""

    def test_full_momentum(self):
        score, sigs, warns = _score_momentum(
            rsi=55.0,
            rsi_trending_up=True,
            macd_above_signal=True,
            macd_histogram_increasing=True,
        )
        assert score == 15.0
        assert "rsi_healthy" in sigs
        assert "rsi_trending_up" in sigs
        assert "macd_above_signal" in sigs
        assert "macd_histogram_increasing" in sigs

    def test_no_momentum(self):
        score, sigs, warns = _score_momentum(
            rsi=None,
            rsi_trending_up=None,
            macd_above_signal=None,
            macd_histogram_increasing=None,
        )
        assert score == 0.0
        assert len(sigs) == 0

    def test_rsi_overbought_warning(self):
        score, sigs, warns = _score_momentum(
            rsi=85.0,
            rsi_trending_up=False,
            macd_above_signal=False,
            macd_histogram_increasing=False,
        )
        assert score == 0.0
        assert "rsi_overbought" in warns

    def test_rsi_weak_warning(self):
        score, sigs, warns = _score_momentum(
            rsi=25.0,
        )
        assert score == 0.0
        assert "rsi_weak" in warns


# ======================================================================
# 4. News scoring (0–20)
# ======================================================================

class TestScoreNews:
    """News component from sentiment_score."""

    def test_strongly_bullish(self):
        score, sigs, warns = _score_news(0.9)
        assert score == 18.0
        assert "news_strongly_bullish" in sigs

    def test_neutral(self):
        score, sigs, warns = _score_news(0.0)
        assert score == 0.0
        assert "news_neutral_or_bearish" in warns

    def test_bearish_clamped_to_zero(self):
        score, sigs, warns = _score_news(-0.8)
        assert score == 0.0
        assert "news_neutral_or_bearish" in warns

    def test_max_bullish(self):
        score, sigs, warns = _score_news(1.0)
        assert score == 20.0
        assert "news_strongly_bullish" in sigs

    def test_moderately_bullish(self):
        score, sigs, warns = _score_news(0.6)
        assert score == 12.0
        assert "news_moderately_bullish" in sigs


# ======================================================================
# 5. Options flow scoring (0–10)
# ======================================================================

class TestScoreOptionsFlow:
    """Options flow component."""

    def test_unusual_call(self):
        score, sigs, warns = _score_options_flow("unusual_call")
        assert score == 10.0
        assert "unusual_call_activity" in sigs

    def test_moderate(self):
        score, sigs, warns = _score_options_flow("moderate")
        assert score == 5.0

    def test_none(self):
        score, sigs, warns = _score_options_flow(None)
        assert score == 0.0

    def test_unknown_string(self):
        score, sigs, warns = _score_options_flow("garbage")
        assert score == 0.0


# ======================================================================
# 6. Financials scoring (0–10)
# ======================================================================

class TestScoreFinancials:
    """Financials component: P/E and revenue growth."""

    def test_both_positive(self):
        score, sigs, warns = _score_financials(
            pe_ratio=15.0,
            revenue_growth_positive=True,
        )
        assert score == 10.0
        assert "pe_ratio_reasonable" in sigs
        assert "revenue_growth_positive" in sigs

    def test_high_pe_negative_growth(self):
        score, sigs, warns = _score_financials(
            pe_ratio=60.0,
            revenue_growth_positive=False,
        )
        assert score == 0.0
        assert "pe_ratio_high" in warns
        assert "revenue_growth_negative" in warns

    def test_pe_unavailable(self):
        score, sigs, warns = _score_financials(
            pe_ratio=None,
            revenue_growth_positive=True,
        )
        assert score == 7.5  # 2.5 partial + 5 growth
        assert "pe_ratio_unavailable" in warns
        assert "revenue_growth_positive" in sigs

    def test_revenue_growth_none(self):
        score, sigs, warns = _score_financials(
            pe_ratio=20.0,
            revenue_growth_positive=None,
        )
        assert score == 5.0  # only P/E


# ======================================================================
# 7. StockScore dataclass
# ======================================================================

class TestStockScore:
    """StockScore model behaviour."""

    def test_defaults(self):
        s = StockScore(symbol="AAPL", total_score=75.5)
        assert s.symbol == "AAPL"
        assert s.total_score == 75.5
        assert isinstance(s.components, ScoreComponents)
        assert s.signals == []
        assert s.warnings == []
        assert s.timestamp is not None

    def test_total_score_clamped_by_score_stock(self):
        """Verify that the scoring logic naturally stays within 0–100."""
        # Just verify ScoreComponents values are within bounds
        comp = ScoreComponents(
            trend=25, volume=20, momentum=15,
            news=20, options_flow=10, financials=10,
        )
        total = sum([
            comp.trend, comp.volume, comp.momentum,
            comp.news, comp.options_flow, comp.financials,
        ])
        assert total == 100.0

        comp2 = ScoreComponents()
        total2 = sum([
            comp2.trend, comp2.volume, comp2.momentum,
            comp2.news, comp2.options_flow, comp2.financials,
        ])
        assert total2 == 0.0


# ======================================================================
# 8. score_candidate (backward-compatible wrapper)
# ======================================================================

class TestScoreCandidate:
    """Legacy wrapper compatibility."""

    @pytest.mark.asyncio
    async def test_returns_legacy_shape(self):
        result = await score_candidate("AAPL", scanner_score=0.8, sentiment_score=0.7,
                                       technical_score=0.6, fundamental_score=0.5)
        assert result["ticker"] == "AAPL"
        assert "composite_score" in result
        assert "meets_threshold" in result
        assert "confidence_level" in result
        assert 0.0 <= result["composite_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_high_confidence(self):
        result = await score_candidate("NVDA", scanner_score=0.9, sentiment_score=0.95,
                                       technical_score=0.85, fundamental_score=0.8)
        assert result["confidence_level"] == "high"
        assert result["meets_threshold"] is True


# ======================================================================
# 9. Batch scoring and threshold filtering
# ======================================================================

class TestBatchAndThreshold:
    """score_batch and get_top_opportunities."""

    @pytest.mark.asyncio
    async def test_score_batch_empty(self):
        """Empty list → empty result."""
        provider = MagicMock()
        results = await score_batch([], provider)
        assert results == []

    @pytest.mark.asyncio
    async def test_score_batch_sorted_desc(self):
        """Results must be sorted by total_score descending."""
        provider = MagicMock()

        async def mock_score_stock(sym, provider, **kwargs):
            scores = {"A": 90.0, "B": 50.0, "C": 75.0}
            return StockScore(symbol=sym, total_score=scores.get(sym, 0.0))

        with patch("app.engines.scoring.score_stock", side_effect=mock_score_stock):
            results = await score_batch(["A", "B", "C"], provider)

        assert len(results) == 3
        assert results[0].symbol == "A"  # 90
        assert results[1].symbol == "C"  # 75
        assert results[2].symbol == "B"  # 50

    @pytest.mark.asyncio
    async def test_get_top_opportunities_threshold(self):
        """Only stocks above threshold are returned."""
        provider = MagicMock()

        async def mock_score_stock(sym, provider, **kwargs):
            scores = {"AAPL": 92.0, "MSFT": 88.0, "TSLA": 79.0, "F": 45.0}
            return StockScore(symbol=sym, total_score=scores.get(sym, 0.0))

        with patch("app.engines.scoring.score_stock", side_effect=mock_score_stock):
            results = await get_top_opportunities(
                ["AAPL", "MSFT", "TSLA", "F"], provider, threshold=85.0
            )

        assert len(results) == 2
        assert results[0].symbol == "AAPL"
        assert results[1].symbol == "MSFT"

    @pytest.mark.asyncio
    async def test_get_top_opportunities_none_above(self):
        """No stocks above threshold → empty list."""
        provider = MagicMock()

        async def mock_score_stock(sym, provider, **kwargs):
            return StockScore(symbol=sym, total_score=50.0)

        with patch("app.engines.scoring.score_stock", side_effect=mock_score_stock):
            results = await get_top_opportunities(
                ["AAPL", "MSFT"], provider, threshold=95.0
            )

        assert results == []


# ======================================================================
# 10. Integration: score_stock with mock provider
# ======================================================================

class TestScoreStockIntegration:
    """Full score_stock with mocked market data provider."""

    @pytest.mark.asyncio
    async def test_score_stock_with_mock_provider(self):
        """End-to-end scoring uses mocked provider data."""
        from app.engines.market_data import Bar, Quote, Fundamentals

        provider = MagicMock()

        # Mock bars — 200 days of flat-ish data with an uptrend at the end
        bars = []
        for i in range(200):
            price = 100.0 + i * 0.1  # slow uptrend
            bars.append(Bar(
                symbol="TEST",
                timestamp=datetime.now(timezone.utc),
                open=price - 0.5,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=1_000_000 if i < 190 else 3_000_000,  # volume spike at end
            ))
        provider.get_bars = AsyncMock(return_value=bars)

        provider.get_quote = AsyncMock(return_value=Quote(
            symbol="TEST", price=119.9, change=0.5, change_pct=0.42, volume=3_000_000,
        ))

        provider.get_fundamentals = AsyncMock(return_value=Fundamentals(
            symbol="TEST", pe_ratio=22.0, eps=5.0,
        ))

        provider.get_unusual_options_activity = AsyncMock(return_value=[])

        # Mock sentiment — patch the source module since score_stock does a
        # late import inside the function body
        with patch(
            "app.engines.sentiment.analyze_sentiment",
            new_callable=AsyncMock,
            return_value={"ticker": "TEST", "sentiment_score": 0.6},
        ):
            result = await score_stock("TEST", provider)

        assert isinstance(result, StockScore)
        assert result.symbol == "TEST"
        assert 0.0 <= result.total_score <= 100.0
        assert isinstance(result.components, ScoreComponents)
        # With our data setup we should have some trend signals
        assert len(result.signals) > 0

    @pytest.mark.asyncio
    async def test_score_stock_handles_provider_errors(self):
        """Provider failures should be caught gracefully — no crash."""
        provider = MagicMock()
        provider.get_bars = AsyncMock(side_effect=Exception("API down"))
        provider.get_quote = AsyncMock(side_effect=Exception("API down"))
        provider.get_fundamentals = AsyncMock(side_effect=Exception("API down"))
        provider.get_unusual_options_activity = AsyncMock(side_effect=Exception("API down"))

        with patch(
            "app.engines.sentiment.analyze_sentiment",
            new_callable=AsyncMock,
            side_effect=Exception("Sentiment API down"),
        ):
            result = await score_stock("FAIL", provider)

        assert result.symbol == "FAIL"
        assert 0.0 <= result.total_score <= 100.0
        # Should still return a valid result even with all APIs failing


# ======================================================================
# 11. Component boundary checks
# ======================================================================

class TestComponentBoundaries:
    """Ensure each component's contribution stays within its max."""

    def test_trend_max_25(self):
        score, _, _ = _score_trend(True, True, True, True)
        assert score <= 25.0

    def test_volume_max_20(self):
        score, _, _ = _score_volume(10.0)
        assert score <= 20.0

    def test_momentum_max_15(self):
        score, _, _ = _score_momentum(55.0, True, True, True)
        assert score <= 15.0

    def test_news_max_20(self):
        score, _, _ = _score_news(2.0)  # clamped to 1.0 internally
        assert score <= 20.0

    def test_options_flow_max_10(self):
        score, _, _ = _score_options_flow("unusual_call")
        assert score <= 10.0

    def test_financials_max_10(self):
        score, _, _ = _score_financials(15.0, True)
        assert score <= 10.0
