"""
Tests for the Risk Manager Engine.

Covers position sizing, stop-loss / take-profit calculation, trade checks,
daily state management, and circuit-breaker halts.
"""

from __future__ import annotations

import math

import pytest

from app.engines.risk import (
    RiskParams,
    TradeCheck,
    DailyRiskState,
    calculate_position_size,
    calculate_stop_loss,
    calculate_take_profit,
    check_trade,
    update_daily_state,
    reset_daily_state,
)


# ======================================================================
# calculate_position_size
# ======================================================================

class TestCalculatePositionSize:
    """Position sizing from account value and risk parameters."""

    def test_basic_long_position(self):
        """Standard LONG trade with 1% risk."""
        shares = calculate_position_size(
            entry_price=100.0,
            stop_loss=98.0,
            account_value=100_000.0,
            max_risk_pct=0.01,
        )
        # Risk $ = 100k * 1% = $1000, risk/share = $2 → 500 shares
        assert shares == 500

    def test_tight_stop_more_shares(self):
        """Tight stop → more shares allowed for same dollar risk."""
        shares = calculate_position_size(
            entry_price=50.0,
            stop_loss=49.50,
            account_value=100_000.0,
            max_risk_pct=0.01,
        )
        # Risk $ = 1000, risk/share = 0.50 → 2000 shares
        assert shares == 2000

    def test_wide_stop_fewer_shares(self):
        """Wide stop → fewer shares for same dollar risk."""
        shares = calculate_position_size(
            entry_price=200.0,
            stop_loss=190.0,
            account_value=100_000.0,
            max_risk_pct=0.01,
        )
        # Risk $ = 1000, risk/share = 10 → 100 shares
        assert shares == 100

    def test_zero_risk_per_share_returns_zero(self):
        """If entry == stop, risk/share is zero → return 0 (protect against div/0)."""
        shares = calculate_position_size(
            entry_price=100.0,
            stop_loss=100.0,
            account_value=100_000.0,
        )
        assert shares == 0

    def test_small_account_produces_zero(self):
        """Very small account may yield 0 shares."""
        shares = calculate_position_size(
            entry_price=100.0,
            stop_loss=99.0,
            account_value=50.0,
            max_risk_pct=0.01,
        )
        # risk_amount = 0.50, risk/share = 1 → floor(0.5) = 0
        assert shares == 0

    def test_risk_never_exceeds_one_percent(self):
        """Dollar risk should never exceed max_risk_pct of account."""
        account = 100_000.0
        max_pct = 0.01
        entry = 100.0
        stop = 97.0
        shares = calculate_position_size(entry, stop, account, max_pct)
        actual_risk = shares * abs(entry - stop)
        max_allowed = account * max_pct
        assert actual_risk <= max_allowed
        # Should be close to but not over
        assert actual_risk <= 1000.0

    def test_floor_rounding(self):
        """Position size uses floor, truncating fractional shares conservatively."""
        shares = calculate_position_size(
            entry_price=10.0,
            stop_loss=9.99,
            account_value=100_000.0,
            max_risk_pct=0.01,
        )
        # risk_amount = 1000, risk/share = 0.01 → 100000 exactly
        assert shares == 100000


# ======================================================================
# calculate_stop_loss
# ======================================================================

class TestCalculateStopLoss:
    """ATR-based stop-loss calculation."""

    def test_long_stop_below_entry(self):
        stop = calculate_stop_loss(entry_price=100.0, atr_value=2.0, direction="LONG", multiplier=2.0)
        assert stop == 96.0  # 100 - 2*2

    def test_short_stop_above_entry(self):
        stop = calculate_stop_loss(entry_price=100.0, atr_value=3.0, direction="SHORT", multiplier=1.5)
        assert stop == 104.5  # 100 + 3*1.5

    def test_default_direction_is_long(self):
        stop = calculate_stop_loss(entry_price=50.0, atr_value=1.0)
        assert stop == 48.0  # 50 - 1*2

    def test_negative_atr_handled(self):
        """Negative ATR values are handled (abs applied)."""
        stop = calculate_stop_loss(entry_price=100.0, atr_value=-2.0, multiplier=2.0)
        assert stop == 96.0


# ======================================================================
# calculate_take_profit
# ======================================================================

class TestCalculateTakeProfit:
    """Reward-to-risk-based take-profit calculation."""

    def test_long_take_profit(self):
        tp = calculate_take_profit(entry_price=100.0, stop_loss=95.0, min_rr=2.0)
        assert tp == 110.0  # 100 + (100-95)*2

    def test_short_take_profit(self):
        tp = calculate_take_profit(entry_price=100.0, stop_loss=105.0, min_rr=3.0)
        assert tp == 85.0  # 100 - (105-100)*3

    def test_default_min_rr(self):
        tp = calculate_take_profit(entry_price=50.0, stop_loss=48.0)
        assert tp == 54.0  # 50 + (50-48)*2


# ======================================================================
# check_trade
# ======================================================================

class TestCheckTrade:
    """Pre-trade risk evaluation."""

    def test_clean_trade_approved(self):
        """A well-structured trade passes all checks."""
        result = check_trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,        # RR = (106-100)/(100-98) = 3:1
            account_value=100_000.0,
            symbol="AAPL",
        )
        assert result.is_approved is True
        assert result.rejection_reason is None
        assert result.position_size_shares > 0
        assert result.reward_to_risk_ratio == 3.0

    def test_rr_below_minimum_rejected(self):
        """Reward-to-risk below 2:1 is rejected."""
        result = check_trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=101.0,        # RR = 1/2 = 0.5:1
            account_value=100_000.0,
            symbol="AAPL",
        )
        assert result.is_approved is False
        assert result.rejection_reason is not None
        assert "Reward-to-risk" in result.rejection_reason

    def test_exact_min_rr_approved(self):
        """Reward-to-risk exactly at 2:1 should be approved."""
        result = check_trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=104.0,        # RR = 4/2 = 2:1 exactly
            account_value=100_000.0,
            symbol="AAPL",
        )
        assert result.is_approved is True

    def test_trading_halted_rejected(self):
        """If daily state is halted, trade is immediately rejected."""
        halted_state = DailyRiskState(is_trading_halted=True, halt_reason="Test halt")
        result = check_trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,
            account_value=100_000.0,
            daily_state=halted_state,
            symbol="AAPL",
        )
        assert result.is_approved is False
        assert "Trading halted" in result.rejection_reason

    def test_daily_loss_limit_breach_rejected(self):
        """If trade would push daily P&L past the loss limit, reject."""
        # Position capped at 20% of 100k = $20k, so 200 shares at $100.
        # Risk = 200 * (100-98) = $400. Need daily P&L such that -pnl - 400 < -3000.
        lossy_state = DailyRiskState(current_daily_pnl=-2700.0)
        result = check_trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,
            account_value=100_000.0,
            daily_state=lossy_state,
            symbol="AAPL",
            risk_params=RiskParams(account_value=100_000.0, max_daily_loss_pct=0.03),
        )
        # -2700 - 400 = -3100 which exceeds -3000 limit
        assert result.is_approved is False
        assert "daily loss limit" in (result.rejection_reason or "").lower()

    def test_daily_loss_not_yet_breached_approved(self):
        """Trade that would NOT breach daily loss limit is approved."""
        ok_state = DailyRiskState(current_daily_pnl=-500.0)
        result = check_trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,
            account_value=100_000.0,
            daily_state=ok_state,
            symbol="AAPL",
            risk_params=RiskParams(account_value=100_000.0, max_daily_loss_pct=0.03),
        )
        # -500 - ~1000 = -1500, max is 3000 → still OK
        assert result.is_approved is True

    def test_consecutive_losses_rejected(self):
        """3 consecutive losses halts trading by default."""
        loss_state = DailyRiskState(consecutive_losses=3)
        result = check_trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,
            account_value=100_000.0,
            daily_state=loss_state,
            symbol="AAPL",
        )
        assert result.is_approved is False
        assert "Consecutive loss" in (result.rejection_reason or "")

    def test_sector_exposure_limit_rejected(self):
        """Trade that pushes sector exposure past 40% is rejected."""
        positions = [
            {"symbol": "AAPL", "sector": "Technology", "market_value": 38_000.0},
        ]
        result = check_trade(
            entry_price=200.0,
            stop_loss=196.0,
            take_profit=212.0,
            account_value=100_000.0,
            current_positions=positions,
            symbol="MSFT",
            sector="Technology",
        )
        # 38k AAPL + (max 20% position = 20k = 100 shares * $200) = 58k > 40k → rejected
        assert result.is_approved is False
        assert "Sector" in (result.rejection_reason or "")

    def test_sector_exposure_without_sector_approved(self):
        """If positions lack sector info, no sector check → approved."""
        positions = [
            {"symbol": "AAPL", "market_value": 38_000.0},
        ]
        result = check_trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,
            account_value=100_000.0,
            current_positions=positions,
            symbol="MSFT",
        )
        assert result.is_approved is True

    def test_position_size_respects_max_position_pct(self):
        """Position value doesn't exceed max_position_pct of account."""
        result = check_trade(
            entry_price=10.0,
            stop_loss=9.80,
            take_profit=10.60,
            account_value=100_000.0,
            symbol="AAPL",
            risk_params=RiskParams(account_value=100_000.0, max_position_pct=0.20),
        )
        # risk $ = 1000, risk/share = 0.20 → 5000 shares = $50,000 pos
        # max position = 20% of 100k = $20,000 → clamped to 2000 shares
        assert result.is_approved is True
        assert result.position_size_shares <= 2000
        pos_value = result.position_size_shares * 10.0
        assert pos_value <= 20_000.0

    def test_risk_amount_correct(self):
        """Verify risk_amount field is correct (clamped by max_position_pct)."""
        result = check_trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,
            account_value=100_000.0,
            symbol="AAPL",
        )
        # Max position 20% of 100k = 200 shares at $100/ea (capped from 500)
        # Risk = 200 * $2 = $400
        assert result.risk_amount == pytest.approx(400.0, rel=0.01)

    def test_reward_amount_correct(self):
        """Verify reward_amount field is correct (clamped by max_position_pct)."""
        result = check_trade(
            entry_price=100.0,
            stop_loss=98.0,
            take_profit=106.0,
            account_value=100_000.0,
            symbol="AAPL",
        )
        # Max position 20% of 100k = 200 shares at $100/ea
        # Reward = 200 * $6 = $1200
        assert result.reward_amount == pytest.approx(1200.0, rel=0.01)


# ======================================================================
# update_daily_state
# ======================================================================

class TestUpdateDailyState:
    """Daily risk state updates after trade closes."""

    def test_win_resets_consecutive_losses(self):
        state = DailyRiskState(consecutive_losses=2, trades_today=2)
        updated = update_daily_state(state, {"pnl": 500.0}, account_value=100_000.0)
        assert updated.consecutive_losses == 0
        assert updated.trades_today == 3
        assert updated.current_daily_pnl == 500.0

    def test_loss_increments_consecutive(self):
        state = DailyRiskState(consecutive_losses=1, trades_today=1)
        updated = update_daily_state(state, {"pnl": -200.0}, account_value=100_000.0)
        assert updated.consecutive_losses == 2
        assert updated.current_daily_pnl == -200.0

    def test_breakeven_does_not_change_streak(self):
        state = DailyRiskState(consecutive_losses=1, trades_today=1)
        updated = update_daily_state(state, {"pnl": 0.0}, account_value=100_000.0)
        assert updated.consecutive_losses == 1  # unchanged

    def test_daily_loss_limit_halts_trading(self):
        state = DailyRiskState(current_daily_pnl=-2500.0)
        updated = update_daily_state(
            state, {"pnl": -600.0}, account_value=100_000.0,
            risk_params=RiskParams(account_value=100_000.0, max_daily_loss_pct=0.03),
        )
        # -2500 - 600 = -3100 → exceeds -3000
        assert updated.is_trading_halted is True
        assert "Daily loss limit" in (updated.halt_reason or "")

    def test_consecutive_losses_halts_trading(self):
        state = DailyRiskState(consecutive_losses=2, trades_today=2)
        updated = update_daily_state(
            state, {"pnl": -100.0}, account_value=100_000.0,
            risk_params=RiskParams(account_value=100_000.0, max_consecutive_losses=3),
        )
        # consecutive goes to 3 → halt
        assert updated.is_trading_halted is True
        assert "Consecutive loss" in (updated.halt_reason or "")


# ======================================================================
# reset_daily_state
# ======================================================================

class TestResetDailyState:
    """Fresh state for new trading day."""

    def test_reset_gives_clean_slate(self):
        state = DailyRiskState(
            current_daily_pnl=-500.0,
            consecutive_losses=3,
            trades_today=10,
            is_trading_halted=True,
            halt_reason="Old halt",
            sector_exposure={"Tech": 5000.0},
        )
        fresh = reset_daily_state()
        assert fresh.current_daily_pnl == 0.0
        assert fresh.consecutive_losses == 0
        assert fresh.trades_today == 0
        assert fresh.is_trading_halted is False
        assert fresh.halt_reason is None
        assert fresh.sector_exposure == {}


# ======================================================================
# RiskParams defaults
# ======================================================================

class TestRiskParams:
    """Default risk parameters."""

    def test_default_values(self):
        params = RiskParams(account_value=100_000.0)
        assert params.max_risk_per_trade_pct == 0.01
        assert params.max_daily_loss_pct == 0.03
        assert params.max_consecutive_losses == 3
        assert params.min_reward_to_risk == 2.0
        assert params.max_position_pct == 0.20
        assert params.max_sector_exposure_pct == 0.40

    def test_custom_values(self):
        params = RiskParams(
            account_value=50_000.0,
            max_risk_per_trade_pct=0.02,
            min_reward_to_risk=3.0,
        )
        assert params.account_value == 50_000.0
        assert params.max_risk_per_trade_pct == 0.02
        assert params.min_reward_to_risk == 3.0
        # defaults still apply
        assert params.max_daily_loss_pct == 0.03


# ======================================================================
# Edge cases
# ======================================================================

class TestEdgeCases:
    """Miscellaneous edge cases."""

    def test_zero_account_value_still_works(self):
        """Account value zero still returns 0 shares (no div/0)."""
        shares = calculate_position_size(
            entry_price=10.0, stop_loss=9.0, account_value=0.0
        )
        assert shares == 0

    def test_negative_prices_handled(self):
        """Negative entry/stop shouldn't crash (though unrealistic)."""
        shares = calculate_position_size(
            entry_price=-10.0, stop_loss=-12.0, account_value=100_000.0
        )
        # abs(-10 - (-12)) = abs(2) = 2, risk=1000, shares=500
        assert shares >= 0
