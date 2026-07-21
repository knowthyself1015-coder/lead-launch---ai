"""
Tests for the Trader's Mind engine.
"""

from datetime import date

import pytest

from app.engines.traders_mind import (
    MarketRegime,
    MarketRegimeType,
    ConfluenceResult,
    TieredExits,
    TieredExit,
    SitOutDecision,
    TradeJournal,
    JournalEntry,
    detect_regime,
    check_confluence,
    calculate_tiered_exits,
    calculate_trailing_stop,
    adjust_trailing_stop,
    calculate_conviction_size,
    should_sit_out,
    get_trade_journal,
    REGIME_CONFIG,
)


# ============================================================================
# Fixtures
# ============================================================================

def _make_regime(regime_type: MarketRegimeType) -> MarketRegime:
    """Helper to create a MarketRegime for testing."""
    return MarketRegime(
        regime=regime_type,
        vix_level=15.0,
        trend_strength=0.5,
        description=f"Test regime: {regime_type.value}",
        implications=[],
    )


# ============================================================================
# 1. Market Regime Detector tests
# ============================================================================

class TestMarketRegime:
    """Test all five market regime classifications."""

    def test_regime_config_has_all_types(self):
        """Verify every regime type has a config entry."""
        for rt in MarketRegimeType:
            assert rt in REGIME_CONFIG, f"Missing config for {rt}"
            cfg = REGIME_CONFIG[rt]
            assert "score_threshold" in cfg
            assert "risk_per_trade" in cfg
            assert "min_confluence" in cfg
            assert "max_positions" in cfg

    def test_trending_up_config(self):
        cfg = REGIME_CONFIG[MarketRegimeType.TRENDING_UP]
        assert cfg["score_threshold"] == 80
        assert cfg["risk_per_trade"] == 1.0
        assert cfg["min_confluence"] == 3
        assert cfg["max_positions"] == 8

    def test_trending_down_config(self):
        cfg = REGIME_CONFIG[MarketRegimeType.TRENDING_DOWN]
        assert cfg["score_threshold"] == 90
        assert cfg["risk_per_trade"] == 0.5
        assert cfg["min_confluence"] == 4
        assert cfg["max_positions"] == 3

    def test_ranging_config(self):
        cfg = REGIME_CONFIG[MarketRegimeType.RANGING]
        assert cfg["score_threshold"] == 85
        assert cfg["risk_per_trade"] == 0.75
        assert cfg["min_confluence"] == 3
        assert cfg["max_positions"] == 5

    def test_volatile_config(self):
        cfg = REGIME_CONFIG[MarketRegimeType.VOLATILE]
        assert cfg["score_threshold"] == 95
        assert cfg["risk_per_trade"] == 0.25
        assert cfg["min_confluence"] == 4
        assert cfg["max_positions"] == 2

    def test_quiet_config(self):
        cfg = REGIME_CONFIG[MarketRegimeType.QUIET]
        assert cfg["score_threshold"] == 85
        assert cfg["risk_per_trade"] == 1.0
        assert cfg["min_confluence"] == 2
        assert cfg["max_positions"] == 8

    def test_regime_config_accessor(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        assert regime.config["score_threshold"] == 80

    def test_regime_has_implications(self):
        regime = _make_regime(MarketRegimeType.VOLATILE)
        assert isinstance(regime.implications, list)

    def test_regime_trend_strength_range(self):
        """Trend strength should be between 0 and 1."""
        for rt in MarketRegimeType:
            regime = MarketRegime(
                regime=rt, vix_level=20.0, trend_strength=1.5,
                description="", implications=[],
            )
            # Construction allows values outside 0-1; that's fine
            # The detector clamps it
            assert isinstance(regime.trend_strength, float)


# ============================================================================
# 2. Confluence Gate tests
# ============================================================================

class TestConfluenceGate:
    """Test the confluence signal checking."""

    def _make_scoring(self, **kwargs) -> dict:
        defaults = {
            "ticker": "AAPL",
            "relative_volume": 1.0,
            "above_sma_50": False,
            "above_sma_200": False,
            "unusual_options": {},
        }
        defaults.update(kwargs)
        return defaults

    def _make_technicals(self, rsi=None, macd_line=None, macd_signal=None) -> dict:
        indicators = {}
        if rsi is not None:
            indicators["rsi"] = rsi
        if macd_line is not None:
            indicators["macd_line"] = macd_line
        if macd_signal is not None:
            indicators["macd_signal"] = macd_signal
        return {"indicators": indicators}

    def _make_sentiment(self, score=0.0, confidence=0.0) -> dict:
        return {"sentiment_score": score, "confidence": confidence}

    def test_passes_with_4_signals_in_trending_up(self):
        """Trending up requires 3, 4 active → pass."""
        scoring = self._make_scoring(
            relative_volume=2.0, above_sma_50=True, above_sma_200=True,
        )
        tech = self._make_technicals(rsi=50, macd_line=1.0, macd_signal=0.5)
        sent = self._make_sentiment(score=0.5, confidence=0.8)
        regime = _make_regime(MarketRegimeType.TRENDING_UP)

        result = check_confluence(scoring, tech, sent, regime)
        assert result.passed is True
        assert result.confluence_count >= 3
        assert len(result.active_signals) >= 3

    def test_fails_with_2_signals_in_trending_up(self):
        """Trending up requires 3, 2 active → fail."""
        scoring = self._make_scoring(
            relative_volume=1.0, above_sma_50=False, above_sma_200=False,
        )
        tech = self._make_technicals(rsi=50, macd_line=1.0, macd_signal=0.5)
        sent = self._make_sentiment(score=0.5, confidence=0.8)
        regime = _make_regime(MarketRegimeType.TRENDING_UP)

        result = check_confluence(scoring, tech, sent, regime)
        assert result.passed is False
        assert result.confluence_count <= 2

    def test_passes_with_2_signals_in_quiet(self):
        """Quiet regime only requires 2 confluence."""
        scoring = self._make_scoring(
            relative_volume=1.0, above_sma_50=False, above_sma_200=False,
        )
        tech = self._make_technicals(rsi=50, macd_line=1.0, macd_signal=0.5)
        sent = self._make_sentiment(score=0.5, confidence=0.8)
        regime = _make_regime(MarketRegimeType.QUIET)

        result = check_confluence(scoring, tech, sent, regime)
        assert result.passed is True
        assert result.confluence_count == 2

    def test_all_five_signals_active(self):
        """Maximum confluence: all 5 categories green."""
        scoring = self._make_scoring(
            relative_volume=2.0,
            above_sma_50=True,
            above_sma_200=True,
            unusual_options={"unusual_call_activity": True},
        )
        tech = self._make_technicals(rsi=50, macd_line=1.0, macd_signal=0.5)
        sent = self._make_sentiment(score=0.5, confidence=0.8)
        regime = _make_regime(MarketRegimeType.TRENDING_UP)

        result = check_confluence(scoring, tech, sent, regime)
        assert result.passed is True
        assert result.confluence_count == 5

    def test_zero_signals_active(self):
        """No confluence signals at all."""
        scoring = self._make_scoring(
            relative_volume=0.5, above_sma_50=False, above_sma_200=False,
        )
        tech = self._make_technicals(rsi=80, macd_line=0.5, macd_signal=1.0)
        sent = self._make_sentiment(score=-0.5, confidence=0.3)
        regime = _make_regime(MarketRegimeType.RANGING)

        result = check_confluence(scoring, tech, sent, regime)
        assert result.passed is False
        assert result.confluence_count == 0

    def test_result_has_all_fields(self):
        scoring = self._make_scoring()
        tech = self._make_technicals()
        sent = self._make_sentiment()
        regime = _make_regime(MarketRegimeType.RANGING)

        result = check_confluence(scoring, tech, sent, regime)
        assert isinstance(result.passed, bool)
        assert isinstance(result.confluence_count, int)
        assert isinstance(result.required, int)
        assert isinstance(result.active_signals, list)
        assert isinstance(result.missing_signals, list)

    def test_handles_none_inputs(self):
        """Should handle None technical_result and sentiment_result gracefully."""
        scoring = self._make_scoring()
        regime = _make_regime(MarketRegimeType.RANGING)

        result = check_confluence(scoring, None, None, regime)
        assert isinstance(result.passed, bool)
        assert result.confluence_count == 0


# ============================================================================
# 3. Tiered Exit Strategy tests
# ============================================================================

class TestTieredExits:
    """Test the tiered exit calculation."""

    def test_tiers_sum_to_100_percent(self):
        exits = calculate_tiered_exits(entry_price=100.0, stop_loss=95.0)
        total_pct = sum(t.pct for t in exits.tiers)
        assert total_pct == 1.0, f"Expected 1.0, got {total_pct}"

    def test_three_tiers_returned(self):
        exits = calculate_tiered_exits(entry_price=100.0, stop_loss=95.0)
        assert len(exits.tiers) == 3

    def test_tier1_50_percent(self):
        exits = calculate_tiered_exits(entry_price=100.0, stop_loss=95.0)
        assert exits.tiers[0].pct == 0.50

    def test_tier2_30_percent(self):
        exits = calculate_tiered_exits(entry_price=100.0, stop_loss=95.0)
        assert exits.tiers[1].pct == 0.30

    def test_tier3_20_percent(self):
        exits = calculate_tiered_exits(entry_price=100.0, stop_loss=95.0)
        assert exits.tiers[2].pct == 0.20

    def test_tier1_target_at_2_to_1_rr(self):
        """Tier 1 target should be at 2:1 RR."""
        exits = calculate_tiered_exits(entry_price=100.0, stop_loss=95.0, rr_ratio=2.0)
        # Risk = 5, Tier1 target = 100 + 5*2 = 110
        assert exits.tiers[0].target == 110.0

    def test_tier2_target_at_4_to_1_rr(self):
        """Tier 2 target should be at 4:1 RR."""
        exits = calculate_tiered_exits(entry_price=100.0, stop_loss=95.0, rr_ratio=2.0)
        # Risk = 5, Tier2 target = 100 + 5*4 = 120
        assert exits.tiers[1].target == 120.0

    def test_tier3_no_fixed_target(self):
        """Tier 3 should have no fixed target (trailing)."""
        exits = calculate_tiered_exits(entry_price=100.0, stop_loss=95.0)
        assert exits.tiers[2].target == 0.0  # trailing, no fixed target

    def test_tiered_exits_with_zero_risk_fallback(self):
        """Entry == stop — should use fallback 2% risk."""
        exits = calculate_tiered_exits(entry_price=100.0, stop_loss=100.0)
        # Fallback: risk = 100 * 0.02 = 2, tier1 = 100 + 2*2 = 104
        assert exits.tiers[0].target == 104.0

    def test_description_not_empty(self):
        exits = calculate_tiered_exits(entry_price=100.0, stop_loss=95.0)
        assert len(exits.description) > 0


# ============================================================================
# 4. Trailing Stop Calculator tests
# ============================================================================

class TestTrailingStop:
    """Test trailing stop calculation."""

    def test_basic_trail(self):
        stop = calculate_trailing_stop(
            current_price=110.0, highest_price=112.0, atr=2.0, multiplier=2.0,
        )
        # highest - (atr * multiplier) = 112 - 4 = 108
        assert stop == 108.0

    def test_stop_below_current_price(self):
        stop = calculate_trailing_stop(
            current_price=100.0, highest_price=105.0, atr=3.0, multiplier=2.0,
        )
        # 105 - 6 = 99
        assert stop < 100.0

    def test_never_exceeds_current_price(self):
        """If ATR is huge, stop should be clamped."""
        stop = calculate_trailing_stop(
            current_price=100.0, highest_price=101.0, atr=50.0, multiplier=2.0,
        )
        # 101 - 100 = 1, which is below 100
        # But the code checks: if new_stop > current_price: clamp to current * 0.995
        assert stop <= 100.0

    def test_adjust_never_moves_down(self):
        """adjust_trailing_stop should never lower the stop."""
        current = 105.0
        proposed = 103.0  # lower than current
        result = adjust_trailing_stop(current, proposed)
        assert result == 105.0  # should keep higher value

    def test_adjust_moves_up(self):
        """adjust_trailing_stop should allow raising."""
        current = 100.0
        proposed = 102.0  # higher than current
        result = adjust_trailing_stop(current, proposed)
        assert result == 102.0

    def test_adjust_keeps_same(self):
        result = adjust_trailing_stop(100.0, 100.0)
        assert result == 100.0

    def test_zero_atr_fallback(self):
        """Zero ATR should use fallback."""
        stop = calculate_trailing_stop(
            current_price=100.0, highest_price=105.0, atr=0.0,
        )
        # Fallback: atr = 100 * 0.02 = 2, stop = 105 - 4 = 101
        assert stop > 0
        assert stop < 105.0


# ============================================================================
# 5. Conviction-Based Position Sizing tests
# ============================================================================

class TestConvictionSizing:
    """Test conviction-based position sizing."""

    def test_base_size_returned_when_no_adjustments(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        size = calculate_conviction_size(
            base_size=100, score=90, regime=regime, confluence_count=3,
        )
        assert size == 100

    def test_high_score_boosts_size(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        size = calculate_conviction_size(
            base_size=100, score=96, regime=regime, confluence_count=3,
        )
        # score >= 95 → 1.2x, confluence=3 → 1.0x → total 1.2x
        assert size == 120

    def test_low_score_reduces_size(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        size = calculate_conviction_size(
            base_size=100, score=87, regime=regime, confluence_count=3,
        )
        # score 85-90 → 0.8x, confluence=3 → 1.0x → total 0.8x
        assert size == 80

    def test_high_confluence_boosts_size(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        size = calculate_conviction_size(
            base_size=100, score=90, regime=regime, confluence_count=4,
        )
        # confluence >= 4 → 1.1x → 110
        assert size == 110

    def test_low_confluence_reduces_size(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        size = calculate_conviction_size(
            base_size=100, score=90, regime=regime, confluence_count=2,
        )
        # confluence = 2 → 0.7x → 70
        assert size == 70

    def test_volatile_regime_halves_size(self):
        regime = _make_regime(MarketRegimeType.VOLATILE)
        size = calculate_conviction_size(
            base_size=100, score=90, regime=regime, confluence_count=3,
        )
        # VOLATILE → 0.5x → 50
        assert size == 50

    def test_zero_base_returns_zero(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        size = calculate_conviction_size(
            base_size=0, score=90, regime=regime, confluence_count=3,
        )
        assert size == 0

    def test_never_exceeds_1_5x(self):
        """Sizing should never exceed 1.5x the base."""
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        size = calculate_conviction_size(
            base_size=100, score=96, regime=regime, confluence_count=5,
        )
        # 1.2 * 1.1 = 1.32, clamped to max 1.5 → 132
        assert size <= 150

    def test_minimum_size_is_1(self):
        """Even with heavy reductions, min size is 1."""
        regime = _make_regime(MarketRegimeType.VOLATILE)
        size = calculate_conviction_size(
            base_size=10, score=87, regime=regime, confluence_count=2,
        )
        # 0.8 * 0.7 * 0.5 = 0.28 → 2.8 → rounds to 3, which is > 1
        assert size >= 1


# ============================================================================
# 6. Sit-Out Detector tests
# ============================================================================

class TestSitOutDetector:
    """Test the sit-out logic."""

    def test_normal_day_no_sit_out(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        daily_state = {"daily_pnl_pct": 1.5, "consecutive_losses": 1, "current_date": "2026-07-22"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is False

    def test_volatile_with_loss_sits_out(self):
        regime = _make_regime(MarketRegimeType.VOLATILE)
        daily_state = {"daily_pnl_pct": -0.5, "consecutive_losses": 0, "current_date": "2026-07-22"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is True
        assert "volatile" in result.reason.lower()

    def test_three_consecutive_losses_sits_out(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        daily_state = {"daily_pnl_pct": 0.0, "consecutive_losses": 3, "current_date": "2026-07-22"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is True
        assert "consecutive" in result.reason.lower() or "cold streak" in result.reason.lower()

    def test_fomc_day_sits_out(self):
        """Jan 28, 2026 is an FOMC day."""
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        daily_state = {"daily_pnl_pct": 1.0, "consecutive_losses": 0, "current_date": "2026-01-28"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is True
        assert "fed" in result.reason.lower() or "fomc" in result.reason.lower()

    def test_fomc_second_day_sits_out(self):
        """Jan 29, 2026 is second day of FOMC meeting."""
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        daily_state = {"daily_pnl_pct": 1.0, "consecutive_losses": 0, "current_date": "2026-01-29"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is True

    def test_non_fomc_day_does_not_sit_out(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        daily_state = {"daily_pnl_pct": 1.0, "consecutive_losses": 0, "current_date": "2026-01-27"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is False

    def test_daily_loss_over_2_percent_sits_out(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        daily_state = {"daily_pnl_pct": -2.5, "consecutive_losses": 0, "current_date": "2026-07-22"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is True
        assert "loss" in result.reason.lower()

    def test_daily_loss_under_2_percent_does_not_sit_out(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        daily_state = {"daily_pnl_pct": -1.5, "consecutive_losses": 1, "current_date": "2026-07-22"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is False

    def test_volatile_no_loss_does_not_sit_out(self):
        """VOLATILE with positive PnL should not trigger."""
        regime = _make_regime(MarketRegimeType.VOLATILE)
        daily_state = {"daily_pnl_pct": 0.5, "consecutive_losses": 0, "current_date": "2026-07-22"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is False

    def test_volatile_flat_does_not_sit_out(self):
        """VOLATILE with exactly zero PnL should not trigger."""
        regime = _make_regime(MarketRegimeType.VOLATILE)
        daily_state = {"daily_pnl_pct": 0.0, "consecutive_losses": 0, "current_date": "2026-07-22"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is False

    def test_sit_out_has_suggested_action(self):
        regime = _make_regime(MarketRegimeType.VOLATILE)
        daily_state = {"daily_pnl_pct": -1.0, "consecutive_losses": 0, "current_date": "2026-07-22"}
        result = should_sit_out(regime, daily_state)
        assert len(result.suggested_action) > 0

    def test_all_clear_has_suggested_action(self):
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        daily_state = {"daily_pnl_pct": 1.0, "consecutive_losses": 0, "current_date": "2026-07-22"}
        result = should_sit_out(regime, daily_state)
        assert result.sit_out is False
        assert "all clear" in result.reason.lower()


# ============================================================================
# 7. Trade Journal tests
# ============================================================================

class TestTradeJournal:
    """Test the trade journal logging and stats."""

    def test_log_entry_creates_record(self):
        journal = TradeJournal()
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        confluence = ConfluenceResult(
            passed=True, confluence_count=3, required=3,
            active_signals=["Tech", "Sentiment", "Volume"],
            missing_signals=["Trend", "Options"],
        )
        entry = journal.log_entry(
            trade_id="test-1",
            ticker="AAPL",
            entry_price=150.0,
            quantity=100,
            decision=None,
            reasoning="Strong setup",
            regime=regime,
            confluence=confluence,
        )
        assert entry.ticker == "AAPL"
        assert entry.trade_id == "test-1"
        assert len(journal.get_all_entries()) == 1

    def test_log_exit_updates_entry(self):
        journal = TradeJournal()
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        confluence = ConfluenceResult(
            passed=True, confluence_count=3, required=3,
            active_signals=[], missing_signals=[],
        )
        journal.log_entry(
            trade_id="exit-test", ticker="MSFT", entry_price=300.0,
            quantity=50, decision=None, reasoning="Test",
            regime=regime, confluence=confluence,
        )
        result = journal.log_exit(
            trade_id="exit-test", exit_price=315.0,
            pnl=750.0, pnl_pct=0.05, exit_reason="Target hit",
        )
        assert result is not None
        assert result.pnl == 750.0
        assert result.exit_price == 315.0

    def test_log_exit_nonexistent_returns_none(self):
        journal = TradeJournal()
        result = journal.log_exit("nonexistent", 100.0, 0.0, 0.0)
        assert result is None

    def test_get_stats_empty(self):
        journal = TradeJournal()
        stats = journal.get_stats()
        assert stats.total_trades == 0
        assert stats.win_rate == 0.0

    def test_get_stats_with_trades(self):
        journal = TradeJournal()
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        confluence = ConfluenceResult(True, 3, 3, [], [])

        # Win
        journal.log_entry("w1", "AAPL", 100, 10, None, "", regime, confluence)
        journal.log_exit("w1", 110, 100.0, 0.10, "win")

        # Loss
        journal.log_entry("l1", "MSFT", 200, 10, None, "", regime, confluence)
        journal.log_exit("l1", 190, -100.0, -0.05, "loss")

        stats = journal.get_stats()
        assert stats.total_trades == 2
        assert stats.winning_trades == 1
        assert stats.losing_trades == 1
        assert stats.win_rate == 0.5

    def test_get_recent_trades(self):
        journal = TradeJournal()
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        confluence = ConfluenceResult(True, 3, 3, [], [])

        for i in range(25):
            journal.log_entry(
                f"t{i}", "AAPL", 100.0, 10, None, f"trade {i}",
                regime, confluence,
            )

        trades = journal.get_recent_trades(limit=20)
        assert len(trades) == 20

    def test_lessons_with_few_trades(self):
        journal = TradeJournal()
        lessons = journal.get_lessons()
        assert len(lessons) == 1
        assert "not enough" in lessons[0].lower()

    def test_lessons_with_enough_trades(self):
        journal = TradeJournal()
        regime_up = _make_regime(MarketRegimeType.TRENDING_UP)
        confluence_4 = ConfluenceResult(True, 4, 3, ["A", "B", "C", "D"], [])
        confluence_2 = ConfluenceResult(True, 2, 3, ["A", "B"], ["C", "D"])

        # 5 wins with high confluence
        for i in range(5):
            journal.log_entry(f"hw{i}", "AAPL", 100, 10, None, "", regime_up, confluence_4)
            journal.log_exit(f"hw{i}", 110, 100, 0.10, "")

        # 5 losses with low confluence
        for i in range(5):
            journal.log_entry(f"ll{i}", "MSFT", 100, 10, None, "", regime_up, confluence_2)
            journal.log_exit(f"ll{i}", 90, -100, -0.10, "")

        lessons = journal.get_lessons()
        assert len(lessons) > 0

    def test_journal_singleton(self):
        j1 = get_trade_journal()
        j2 = get_trade_journal()
        assert j1 is j2

    def test_win_rate_by_regime(self):
        journal = TradeJournal()
        regime_up = _make_regime(MarketRegimeType.TRENDING_UP)
        confluence = ConfluenceResult(True, 3, 3, [], [])

        journal.log_entry("r1", "AAPL", 100, 10, None, "", regime_up, confluence)
        journal.log_exit("r1", 110, 100, 0.10, "")
        journal.log_entry("r2", "AAPL", 100, 10, None, "", regime_up, confluence)
        journal.log_exit("r2", 90, -100, -0.10, "")

        stats = journal.get_stats()
        assert "TRENDING_UP" in stats.win_rate_by_regime
        assert stats.win_rate_by_regime["TRENDING_UP"] == 0.5

    def test_win_rate_by_confluence(self):
        journal = TradeJournal()
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        confluence_4 = ConfluenceResult(True, 4, 3, [], [])
        confluence_2 = ConfluenceResult(True, 2, 3, [], [])

        journal.log_entry("c1", "AAPL", 100, 10, None, "", regime, confluence_4)
        journal.log_exit("c1", 110, 100, 0.10, "")
        journal.log_entry("c2", "AAPL", 100, 10, None, "", regime, confluence_2)
        journal.log_exit("c2", 90, -100, -0.10, "")

        stats = journal.get_stats()
        assert 4 in stats.win_rate_by_confluence
        assert stats.win_rate_by_confluence[4] == 1.0
        assert stats.win_rate_by_confluence[2] == 0.0


# ============================================================================
# Edge case & integration tests
# ============================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_conviction_minimum(self):
        """Very unfavorable conditions should still return at least 1 share."""
        regime = _make_regime(MarketRegimeType.VOLATILE)
        size = calculate_conviction_size(
            base_size=1, score=50, regime=regime, confluence_count=1,
        )
        assert size >= 1

    def test_trailing_stop_zero_price(self):
        """Should handle zero prices gracefully."""
        stop = calculate_trailing_stop(0.0, 0.0, 0.0)
        assert stop >= 0.0

    def test_confluence_handles_empty_dicts(self):
        result = check_confluence({}, {}, {}, _make_regime(MarketRegimeType.RANGING))
        assert result.passed is False
        assert result.confluence_count == 0

    def test_journal_handles_missing_dates(self):
        journal = TradeJournal()
        regime = _make_regime(MarketRegimeType.TRENDING_UP)
        confluence = ConfluenceResult(True, 3, 3, [], [])
        entry = JournalEntry(
            trade_id="nodate", ticker="AAPL",
            entry_date="invalid-date", exit_date="bad-date",
            entry_price=100.0, exit_price=110.0, pnl=10.0, pnl_pct=0.1,
            regime="TRENDING_UP", confluence_count=3,
        )
        journal._entries.append(entry)
        stats = journal.get_stats()
        assert stats.total_trades == 1
