"""
Tests for the Trade Decision Engine.

Tests cover:
- BUY signal when score >= 85 and risk passes
- WATCHLIST when score >= 85 but risk fails
- HOLD for medium scores (60-84)
- SELL for losing positions (score < 40 and held)
- Confidence score calculation
- Batch decisions sorted by confidence
- Summary generation
- should_sell logic (stop-loss, take-profit, score-based)
- Helper functions (_estimate_atr, _resolve_sector, _is_position_held)
"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Minimal replica dataclasses matching the expected interfaces
# (so tests don't depend on the actual scoring/risk modules being fully
# implemented yet on this branch)
# ---------------------------------------------------------------------------

@dataclass
class ScoreComponents:
    trend: float = 0.0
    volume: float = 0.0
    momentum: float = 0.0
    news: float = 0.0
    options_flow: float = 0.0
    financials: float = 0.0


@dataclass
class StockScore:
    symbol: str
    total_score: float
    components: ScoreComponents = field(default_factory=ScoreComponents)
    signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    timestamp: str = "2026-07-20T12:00:00Z"


@dataclass
class TradeCheck:
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_shares: int
    risk_amount: float
    reward_amount: float
    reward_to_risk_ratio: float
    is_approved: bool
    rejection_reason: str | None = None
    max_shares: int = 0
    suggested_shares: int = 0


@dataclass
class RiskParams:
    account_value: float
    max_risk_per_trade_pct: float = 0.01
    max_daily_loss_pct: float = 0.03
    max_consecutive_losses: int = 3
    min_reward_to_risk: float = 2.0
    max_position_pct: float = 0.20
    max_sector_exposure_pct: float = 0.40


@dataclass
class DailyRiskState:
    current_daily_pnl: float = 0.0
    consecutive_losses: int = 0
    trades_today: int = 0
    is_trading_halted: bool = False
    halt_reason: str | None = None
    sector_exposure: dict[str, float] = field(default_factory=dict)


# Fake Quote / Bar for mocking provider
@dataclass
class FakeQuote:
    symbol: str
    price: float
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0


@dataclass
class FakeBar:
    symbol: str
    timestamp: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0


# ---------------------------------------------------------------------------
# Shared helpers for building mock patches
# ---------------------------------------------------------------------------

def _make_default_trade_check(**overrides) -> TradeCheck:
    defaults = dict(
        symbol="AAPL", entry_price=150.0, stop_loss=145.0, take_profit=160.0,
        position_size_shares=200, risk_amount=1000.0, reward_amount=2000.0,
        reward_to_risk_ratio=2.0, is_approved=True,
    )
    defaults.update(overrides)
    return TradeCheck(**defaults)


def _make_score(total: float) -> StockScore:
    return StockScore(
        symbol="AAPL",
        total_score=total,
        components=ScoreComponents(
            trend=20, volume=15, momentum=10, news=15, options_flow=5, financials=5,
        ),
        signals=["price_above_sma50", "rsi_bullish"],
        warnings=[],
    )


def _patch_all_for_decide(
    total_score: float = 90.0,
    is_approved: bool = True,
    rejection_reason: str | None = None,
):
    """Return a context-manager stack that patches all late imports for decide().

    Uses patch.object with create=True because the scoring/risk stubs on the
    current branch don't yet export the expanded interfaces.
    """
    import app.engines.scoring as scoring_mod
    import app.engines.risk as risk_mod

    score_mock = AsyncMock(return_value=_make_score(total_score))
    check_mock = MagicMock(return_value=_make_default_trade_check(
        is_approved=is_approved, rejection_reason=rejection_reason,
    ))

    stack = ExitStack()
    stack.enter_context(patch.object(scoring_mod, "score_stock", score_mock, create=True))
    stack.enter_context(patch.object(scoring_mod, "StockScore", StockScore, create=True))
    stack.enter_context(patch.object(risk_mod, "check_trade", check_mock, create=True))
    stack.enter_context(patch.object(risk_mod, "calculate_stop_loss", MagicMock(return_value=145.0), create=True))
    stack.enter_context(patch.object(risk_mod, "calculate_take_profit", MagicMock(return_value=160.0), create=True))
    stack.enter_context(patch.object(risk_mod, "calculate_position_size", MagicMock(return_value=200), create=True))
    stack.enter_context(patch.object(risk_mod, "RiskParams", MagicMock(return_value=RiskParams(account_value=100_000)), create=True))
    stack.enter_context(patch.object(risk_mod, "reset_daily_state", MagicMock(return_value=DailyRiskState()), create=True))
    stack.enter_context(patch.object(risk_mod, "DailyRiskState", DailyRiskState, create=True))
    stack.enter_context(patch.object(risk_mod, "TradeCheck", TradeCheck, create=True))
    return stack


def _make_provider(price=150.0):
    provider = MagicMock()
    provider.get_quote = AsyncMock(return_value=FakeQuote("AAPL", price=price))
    provider.get_bars = AsyncMock(return_value=[
        FakeBar("AAPL", high=152, low=148, close=150),
        FakeBar("AAPL", high=153, low=149, close=152),
        FakeBar("AAPL", high=155, low=151, close=154),
    ])
    return provider


# ===================================================================
# Pure-helper tests (no mocking needed)
# ===================================================================

class TestEstimateATR:
    def test_atr_with_valid_bars(self):
        from app.engines.decisions import _estimate_atr
        bars = [
            FakeBar("AAPL", high=152.0, low=148.0, close=150.0),
            FakeBar("AAPL", high=153.0, low=149.0, close=152.0),
            FakeBar("AAPL", high=155.0, low=151.0, close=154.0),
        ]
        atr = _estimate_atr(bars)
        assert atr == pytest.approx(4.0)

    def test_atr_single_bar_returns_zero(self):
        from app.engines.decisions import _estimate_atr
        assert _estimate_atr([FakeBar("AAPL")]) == 0.0

    def test_atr_empty_returns_zero(self):
        from app.engines.decisions import _estimate_atr
        assert _estimate_atr([]) == 0.0

    def test_atr_none_returns_zero(self):
        from app.engines.decisions import _estimate_atr
        assert _estimate_atr(None) == 0.0


class TestResolveSector:
    def test_sector_found(self):
        from app.engines.decisions import _resolve_sector
        pos = [
            {"symbol": "AAPL", "sector": "Technology"},
            {"symbol": "JPM", "sector": "Financials"},
        ]
        assert _resolve_sector("AAPL", pos) == "Technology"
        assert _resolve_sector("JPM", pos) == "Financials"

    def test_sector_not_found(self):
        from app.engines.decisions import _resolve_sector
        assert _resolve_sector("MSFT", [{"symbol": "AAPL", "sector": "Tech"}]) == ""

    def test_sector_none_positions(self):
        from app.engines.decisions import _resolve_sector
        assert _resolve_sector("AAPL", None) == ""

    def test_sector_case_insensitive(self):
        from app.engines.decisions import _resolve_sector
        assert _resolve_sector("aapl", [{"symbol": "AAPL", "sector": "Tech"}]) == "Tech"


class TestIsPositionHeld:
    def test_position_held(self):
        from app.engines.decisions import _is_position_held
        assert _is_position_held("AAPL", [{"symbol": "AAPL"}, {"symbol": "MSFT"}]) is True

    def test_position_not_held(self):
        from app.engines.decisions import _is_position_held
        assert _is_position_held("MSFT", [{"symbol": "AAPL"}]) is False

    def test_none_positions(self):
        from app.engines.decisions import _is_position_held
        assert _is_position_held("AAPL", None) is False

    def test_case_insensitive(self):
        from app.engines.decisions import _is_position_held
        assert _is_position_held("aapl", [{"symbol": "AAPL"}]) is True


# ===================================================================
# Summary tests
# ===================================================================

class TestGenerateSummary:
    def _d(self, sym, dec, conf=0.8):
        from app.engines.decisions import TradeDecision
        return TradeDecision(
            symbol=sym, decision=dec, confidence=conf,
            entry_price=100.0, stop_loss=95.0, take_profit=110.0,
            position_size=100, risk_amount=500.0, reward_amount=1000.0,
            reward_to_risk_ratio=2.0, reasoning="test",
        )

    def test_counts_all_types(self):
        from app.engines.decisions import generate_summary
        decisions = [
            self._d("A", "BUY", 0.95), self._d("B", "BUY", 0.90),
            self._d("C", "SELL", 0.85),
            self._d("D", "HOLD", 0.60), self._d("E", "HOLD", 0.55),
            self._d("F", "WATCHLIST", 0.92),
        ]
        s = generate_summary(decisions)
        assert s.total_analyzed == 6
        assert s.buy_signals == 2
        assert s.sell_signals == 1
        assert s.hold_signals == 2
        assert s.watchlist == 1

    def test_top_pick_first_buy(self):
        from app.engines.decisions import generate_summary
        decisions = [
            self._d("A", "BUY", 0.80), self._d("B", "BUY", 0.95), self._d("C", "BUY", 0.88),
        ]
        s = generate_summary(decisions)
        assert s.top_pick is not None
        assert s.top_pick.symbol == "A"

    def test_no_buys_top_pick_none(self):
        from app.engines.decisions import generate_summary
        s = generate_summary([self._d("A", "HOLD", 0.5), self._d("B", "WATCHLIST", 0.9)])
        assert s.top_pick is None

    def test_empty_list(self):
        from app.engines.decisions import generate_summary
        s = generate_summary([])
        assert s.total_analyzed == 0
        assert s.buy_signals == 0
        assert s.top_pick is None


# ===================================================================
# Decision type tests (with source-level patching)
# ===================================================================

class TestDecideDecisionTypes:
    def test_buy_signal_score_high_risk_passes(self):
        """BUY when total_score >= 85 AND risk check passes."""
        from app.engines.decisions import decide

        provider = _make_provider()

        with _patch_all_for_decide(total_score=90.0, is_approved=True):
            result = asyncio.run(decide("AAPL", provider, account_value=100_000))

        assert result.decision == "BUY"
        assert result.confidence == 0.9
        assert result.position_size > 0
        assert "BUY" in result.reasoning
        assert "APPROVED" in result.reasoning

    def test_watchlist_score_high_risk_fails(self):
        """WATCHLIST when total_score >= 85 BUT risk check fails."""
        from app.engines.decisions import decide

        provider = _make_provider()

        with _patch_all_for_decide(total_score=88.0, is_approved=False,
                                   rejection_reason="Daily loss limit hit"):
            result = asyncio.run(decide("AAPL", provider))

        assert result.decision == "WATCHLIST"
        assert "FAILED" in result.reasoning
        assert "Daily loss limit hit" in result.reasoning

    def test_hold_for_medium_scores(self):
        """HOLD when total_score is 60-84."""
        from app.engines.decisions import decide

        provider = _make_provider()

        with _patch_all_for_decide(total_score=72.0, is_approved=True):
            result = asyncio.run(decide("AAPL", provider))

        assert result.decision == "HOLD"

    def test_sell_for_held_position_low_score(self):
        """SELL for a held position when score < 40."""
        from app.engines.decisions import decide

        provider = _make_provider()
        positions = [{"symbol": "AAPL", "sector": "Technology", "market_value": 5000}]

        with _patch_all_for_decide(total_score=35.0, is_approved=False):
            result = asyncio.run(decide("AAPL", provider, current_positions=positions))

        assert result.decision == "SELL"

    def test_hold_for_unheld_low_score(self):
        """HOLD for a position NOT held, even with low score."""
        from app.engines.decisions import decide

        provider = _make_provider()

        with _patch_all_for_decide(total_score=30.0, is_approved=False):
            result = asyncio.run(decide("AAPL", provider, current_positions=[]))

        assert result.decision == "HOLD"


class TestConfidenceCalculation:
    def test_confidence_from_score(self):
        """Confidence = total_score / 100."""
        from app.engines.decisions import decide

        provider = _make_provider()

        with _patch_all_for_decide(total_score=95.0, is_approved=True):
            result = asyncio.run(decide("AAPL", provider))

        assert result.confidence == 0.95
        assert 0.0 <= result.confidence <= 1.0

    def test_confidence_zero_score(self):
        from app.engines.decisions import decide

        provider = _make_provider()

        with _patch_all_for_decide(total_score=0.0, is_approved=False):
            result = asyncio.run(decide("AAPL", provider))

        assert result.confidence == 0.0


class TestBatchDecisions:
    def test_batch_sorted_by_confidence_desc(self):
        """Batch results should be sorted by confidence descending."""
        from app.engines.decisions import decide_batch

        provider = _make_provider()

        with patch("app.engines.decisions.decide") as mock_decide:
            from app.engines.decisions import TradeDecision

            async def fake_decide(**kwargs):
                sym = kwargs["symbol"]
                scores = {"AAPL": 95, "MSFT": 72, "GOOGL": 88}
                total = scores.get(sym, 50)
                if total >= 85:
                    dec = "BUY"
                elif total >= 60:
                    dec = "HOLD"
                else:
                    dec = "HOLD"
                return TradeDecision(
                    symbol=sym, decision=dec, confidence=total / 100.0,
                    entry_price=150.0, stop_loss=145.0, take_profit=160.0,
                    position_size=200, risk_amount=500.0, reward_amount=1000.0,
                    reward_to_risk_ratio=2.0, reasoning="test",
                )

            mock_decide.side_effect = fake_decide
            results = asyncio.run(decide_batch(["AAPL", "MSFT", "GOOGL"], provider))

        assert len(results) == 3
        assert results[0].symbol == "AAPL"
        assert results[1].symbol == "GOOGL"
        assert results[2].symbol == "MSFT"
        assert results[0].confidence == 0.95
        assert results[1].confidence == 0.88
        assert results[2].confidence == 0.72


# ===================================================================
# should_sell tests
# ===================================================================

class TestShouldSell:
    def test_stop_loss_hit(self):
        """SELL when current price <= stop_loss."""
        from app.engines.decisions import should_sell

        provider = MagicMock()
        provider.get_quote = AsyncMock(return_value=FakeQuote("AAPL", price=138.0))

        position = {
            "symbol": "AAPL", "entry_price": 150.0, "quantity": 100,
            "stop_loss_price": 140.0, "take_profit_price": 165.0,
        }

        result = asyncio.run(should_sell(position, provider))
        assert result.decision == "SELL"
        assert "STOP-LOSS" in result.reasoning

    def test_take_profit_hit(self):
        """SELL when current price >= take_profit."""
        from app.engines.decisions import should_sell

        provider = MagicMock()
        provider.get_quote = AsyncMock(return_value=FakeQuote("AAPL", price=167.0))

        position = {
            "symbol": "AAPL", "entry_price": 150.0, "quantity": 100,
            "stop_loss_price": 140.0, "take_profit_price": 165.0,
        }

        result = asyncio.run(should_sell(position, provider))
        assert result.decision == "SELL"
        assert "TAKE-PROFIT" in result.reasoning

    def test_score_based_sell(self):
        """SELL when score drops below 40."""
        from app.engines.decisions import should_sell
        import app.engines.scoring as scoring_mod

        provider = MagicMock()
        provider.get_quote = AsyncMock(return_value=FakeQuote("AAPL", price=145.0))

        position = {
            "symbol": "AAPL", "entry_price": 150.0, "quantity": 100,
            "stop_loss_price": 130.0, "take_profit_price": 170.0,
        }

        mock_score = AsyncMock(return_value=_make_score(35.0))

        stack = ExitStack()
        stack.enter_context(patch.object(scoring_mod, "score_stock", mock_score, create=True))
        stack.enter_context(patch.object(scoring_mod, "StockScore", StockScore, create=True))
        with stack:
            result = asyncio.run(should_sell(position, provider))

        assert result.decision == "SELL"
        assert "SCORE-BASED" in result.reasoning
        assert "35.0" in result.reasoning

    def test_no_sell_conditions(self):
        """HOLD when no exit conditions triggered."""
        from app.engines.decisions import should_sell
        import app.engines.scoring as scoring_mod

        provider = MagicMock()
        provider.get_quote = AsyncMock(return_value=FakeQuote("AAPL", price=152.0))

        position = {
            "symbol": "AAPL", "entry_price": 150.0, "quantity": 100,
            "stop_loss_price": 140.0, "take_profit_price": 165.0,
        }

        mock_score = AsyncMock(return_value=_make_score(72.0))

        stack = ExitStack()
        stack.enter_context(patch.object(scoring_mod, "score_stock", mock_score, create=True))
        stack.enter_context(patch.object(scoring_mod, "StockScore", StockScore, create=True))
        with stack:
            result = asyncio.run(should_sell(position, provider))

        assert result.decision == "HOLD"
        assert "No exit conditions" in result.reasoning

    def test_stop_loss_priority_over_score(self):
        """Stop-loss hit triggers SELL immediately, before scoring."""
        from app.engines.decisions import should_sell

        provider = MagicMock()
        provider.get_quote = AsyncMock(return_value=FakeQuote("AAPL", price=138.0))

        position = {
            "symbol": "AAPL", "entry_price": 150.0, "quantity": 100,
            "stop_loss_price": 140.0, "take_profit_price": 165.0,
        }

        # No scoring patch needed — stop-loss triggers before score is called
        result = asyncio.run(should_sell(position, provider))
        assert result.decision == "SELL"
        assert "STOP-LOSS" in result.reasoning

    def test_no_quote_returns_hold(self):
        """HOLD when provider returns no quote."""
        from app.engines.decisions import should_sell

        provider = MagicMock()
        provider.get_quote = AsyncMock(return_value=None)

        position = {"symbol": "AAPL", "entry_price": 150.0, "quantity": 100}

        result = asyncio.run(should_sell(position, provider))
        assert result.decision == "HOLD"
        assert "No quote" in result.reasoning
        assert result.confidence == 0.0


# ===================================================================
# Reasoning builder tests
# ===================================================================

class TestBuildReasoning:
    def test_reasoning_buy_includes_all_components(self):
        from app.engines.decisions import _build_reasoning

        score = _make_score(92.0)
        check = _make_default_trade_check(is_approved=True)
        r = _build_reasoning(score, check, "BUY")

        assert "BUY" in r
        assert "92.0/100" in r
        assert "Trend: 20" in r
        assert "APPROVED" in r

    def test_reasoning_watchlist_includes_rejection(self):
        from app.engines.decisions import _build_reasoning

        score = _make_score(88.0)
        check = _make_default_trade_check(
            is_approved=False, rejection_reason="Sector exposure exceeded",
        )
        r = _build_reasoning(score, check, "WATCHLIST")

        assert "WATCHLIST" in r
        assert "FAILED" in r
        assert "Sector exposure exceeded" in r
