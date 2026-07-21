"""
Tests for the Portfolio Manager Engine.

Covers:
- get_positions (enrichment with current prices)
- calculate_snapshot (equity, P&L, win rate)
- calculate_sector_exposure
- calculate_risk_concentration (warnings)
- get_portfolio_health (HEALTHY, CAUTION, WARNING)
- update_position (partial sell, stop adjustment)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.portfolio import (
    PortfolioPosition,
    PortfolioSnapshot,
    ClosedTrade,
    get_positions,
    calculate_snapshot,
    calculate_sector_exposure,
    calculate_risk_concentration,
    get_portfolio_health,
    update_position,
    _resolve_sector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quote(symbol: str, price: float) -> object:
    """Create a minimal Quote-like object."""
    from app.engines.market_data import Quote
    return Quote(
        symbol=symbol,
        price=price,
        change=0.0,
        change_pct=0.0,
        volume=1000000,
    )


def _make_provider(quotes: dict[str, float]) -> AsyncMock:
    """Create a mock provider whose get_quote returns the given prices."""
    provider = AsyncMock()
    async def _get_quote(symbol: str):
        price = quotes.get(symbol.upper())
        if price is None:
            return None
        return _make_quote(symbol, price)
    provider.get_quote.side_effect = _get_quote
    return provider


# ---------------------------------------------------------------------------
# Basic fixture data
# ---------------------------------------------------------------------------

def _sample_positions_data() -> list[dict]:
    return [
        {"symbol": "AAPL", "quantity": 50, "avg_entry_price": 185.00, "sector": "Technology"},
        {"symbol": "MSFT", "quantity": 30, "avg_entry_price": 420.00, "sector": "Technology"},
        {"symbol": "JPM", "quantity": 40, "avg_entry_price": 195.00, "sector": "Financial"},
        {"symbol": "JNJ", "quantity": 25, "avg_entry_price": 160.00, "sector": "Healthcare"},
    ]


def _sample_closed_trades() -> list[ClosedTrade]:
    return [
        ClosedTrade(symbol="TSLA", entry_price=250, exit_price=275, quantity=10, return_pct=10.0, pnl=250.0),
        ClosedTrade(symbol="META", entry_price=480, exit_price=510, quantity=5, return_pct=6.25, pnl=150.0),
        ClosedTrade(symbol="INTC", entry_price=45, exit_price=42, quantity=100, return_pct=-6.67, pnl=-300.0),
        ClosedTrade(symbol="AMD", entry_price=160, exit_price=155, quantity=20, return_pct=-3.13, pnl=-100.0),
    ]


# ===================================================================
# Tests — get_positions
# ===================================================================

class TestGetPositions:
    """Tests for the get_positions async function."""

    @pytest.mark.asyncio
    async def test_enriches_with_current_prices(self):
        """Each position should have its current_price and derived values set."""
        provider = _make_provider({"AAPL": 200.0, "MSFT": 450.0, "JPM": 210.0, "JNJ": 170.0})
        positions = await get_positions(_sample_positions_data(), provider)

        assert len(positions) == 4

        aapl = positions[0]
        assert aapl.symbol == "AAPL"
        assert aapl.current_price == 200.0
        assert aapl.market_value == 200.0 * 50  # 10000
        assert aapl.unrealized_pnl == (200.0 - 185.0) * 50  # 750
        assert aapl.unrealized_pnl_pct == pytest.approx(8.11, rel=0.01)

    @pytest.mark.asyncio
    async def test_handles_missing_quote_gracefully(self):
        """When a quote is not available, current_price should be 0."""
        provider = _make_provider({"AAPL": 200.0, "MSFT": 450.0})  # JPM & JNJ missing
        positions = await get_positions(_sample_positions_data(), provider)

        jpm = positions[2]
        assert jpm.symbol == "JPM"
        assert jpm.current_price == 0.0
        assert jpm.market_value == 0.0
        assert jpm.unrealized_pnl == -195.0 * 40  # (0 - 195) * 40

    @pytest.mark.asyncio
    async def test_resolves_sector_from_data(self):
        """Sector passed in positions_data should be used."""
        provider = _make_provider({"AAPL": 200.0})
        positions = await get_positions(
            [{"symbol": "AAPL", "quantity": 10, "avg_entry_price": 185.0, "sector": "Technology"}],
            provider,
        )
        assert positions[0].sector == "Technology"

    @pytest.mark.asyncio
    async def test_resolves_sector_from_fallback(self):
        """Sector not provided — should fall back to built-in mapping."""
        provider = _make_provider({"NVDA": 900.0})
        positions = await get_positions(
            [{"symbol": "NVDA", "quantity": 10, "avg_entry_price": 850.0}],
            provider,
        )
        assert positions[0].sector == "Technology"

    @pytest.mark.asyncio
    async def test_stop_loss_and_take_profit_parsed(self):
        """Both naming conventions (stop_loss / stop_loss_price) should work."""
        provider = _make_provider({"AAPL": 200.0})
        positions = await get_positions(
            [{
                "symbol": "AAPL", "quantity": 10, "avg_entry_price": 185.0,
                "stop_loss": 175.0, "take_profit": 210.0,
            }],
            provider,
        )
        p = positions[0]
        assert p.stop_loss == 175.0
        assert p.take_profit == 210.0

    @pytest.mark.asyncio
    async def test_allocation_pct_calculated(self):
        """Each position should have allocation_pct based on total market value."""
        provider = _make_provider({"AAPL": 200.0, "MSFT": 450.0})
        positions = await get_positions(_sample_positions_data()[:2], provider)
        # AAPL: 200*50=10000, MSFT: 450*30=13500, total=23500
        assert positions[0].allocation_pct == pytest.approx(42.55, rel=0.01)  # 10000/23500
        assert positions[1].allocation_pct == pytest.approx(57.45, rel=0.01)  # 13500/23500

    @pytest.mark.asyncio
    async def test_empty_positions_returns_empty(self):
        """Empty positions_data should return empty list."""
        provider = _make_provider({})
        positions = await get_positions([], provider)
        assert positions == []


# ===================================================================
# Tests — calculate_snapshot
# ===================================================================

class TestCalculateSnapshot:
    """Tests for the calculate_snapshot function."""

    def test_basic_equity_and_pnl(self):
        """Snapshot should correctly compute total equity and P&L."""
        positions = [
            PortfolioPosition(symbol="AAPL", quantity=50, avg_entry_price=185.0,
                              current_price=200.0, market_value=10000.0,
                              unrealized_pnl=750.0, unrealized_pnl_pct=8.11, sector="Technology"),
            PortfolioPosition(symbol="JPM", quantity=40, avg_entry_price=195.0,
                              current_price=210.0, market_value=8400.0,
                              unrealized_pnl=600.0, unrealized_pnl_pct=7.69, sector="Financial"),
        ]
        closed = [
            ClosedTrade(symbol="TSLA", entry_price=250, exit_price=275, quantity=10,
                        return_pct=10.0, pnl=250.0),
            ClosedTrade(symbol="INTC", entry_price=45, exit_price=42, quantity=100,
                        return_pct=-6.67, pnl=-300.0),
        ]
        snapshot = calculate_snapshot(positions, cash=5000.0, closed_trades=closed)

        assert snapshot.cash == 5000.0
        assert snapshot.total_market_value == 18400.0  # 10000 + 8400
        assert snapshot.total_equity == 23400.0  # 5000 + 18400
        assert snapshot.total_unrealized_pnl == 1350.0  # 750 + 600
        assert snapshot.total_realized_pnl == -50.0  # 250 + (-300)
        assert snapshot.open_positions_count == 2

    def test_win_rate_calculation(self):
        """Win rate = winning trades / total closed trades."""
        closed = [
            ClosedTrade(symbol="A", entry_price=100, exit_price=110, quantity=10,
                        return_pct=10.0, pnl=100.0),
            ClosedTrade(symbol="B", entry_price=100, exit_price=105, quantity=10,
                        return_pct=5.0, pnl=50.0),
            ClosedTrade(symbol="C", entry_price=100, exit_price=95, quantity=10,
                        return_pct=-5.0, pnl=-50.0),
            ClosedTrade(symbol="D", entry_price=100, exit_price=90, quantity=10,
                        return_pct=-10.0, pnl=-100.0),
        ]
        snapshot = calculate_snapshot([], cash=0.0, closed_trades=closed)
        assert snapshot.win_rate == 0.50  # 2 wins / 4 total

    def test_win_rate_no_trades(self):
        """Win rate should be 0 with no closed trades."""
        snapshot = calculate_snapshot([], cash=10000.0)
        assert snapshot.win_rate == 0.0

    def test_avg_return_pct(self):
        """Average return across closed trades."""
        closed = [
            ClosedTrade(symbol="A", entry_price=100, exit_price=110, quantity=10,
                        return_pct=10.0, pnl=100.0),
            ClosedTrade(symbol="B", entry_price=100, exit_price=90, quantity=10,
                        return_pct=-10.0, pnl=-100.0),
        ]
        snapshot = calculate_snapshot([], cash=0.0, closed_trades=closed)
        assert snapshot.avg_return_pct == 0.0

    def test_sector_exposure_in_snapshot(self):
        """Snapshot should include sector_exposure dict."""
        positions = [
            PortfolioPosition(symbol="AAPL", quantity=50, avg_entry_price=185.0,
                              current_price=200.0, market_value=10000.0,
                              unrealized_pnl=750.0, unrealized_pnl_pct=8.11, sector="Technology"),
            PortfolioPosition(symbol="JPM", quantity=40, avg_entry_price=195.0,
                              current_price=210.0, market_value=8400.0,
                              unrealized_pnl=600.0, unrealized_pnl_pct=7.69, sector="Financial"),
        ]
        snapshot = calculate_snapshot(positions, cash=5000.0)
        assert "Technology" in snapshot.sector_exposure
        assert "Financial" in snapshot.sector_exposure

    def test_risk_concentration_in_snapshot(self):
        """Snapshot should include risk_concentration dict."""
        positions = [
            PortfolioPosition(symbol="AAPL", quantity=50, avg_entry_price=185.0,
                              current_price=200.0, market_value=10000.0,
                              unrealized_pnl=750.0, unrealized_pnl_pct=8.11, sector="Technology"),
        ]
        snapshot = calculate_snapshot(positions, cash=5000.0)
        assert "AAPL" in snapshot.risk_concentration

    def test_no_positions_no_trades(self):
        """Empty portfolio should return zeroed snapshot."""
        snapshot = calculate_snapshot([], cash=25000.0)
        assert snapshot.cash == 25000.0
        assert snapshot.total_market_value == 0.0
        assert snapshot.total_equity == 25000.0
        assert snapshot.open_positions_count == 0
        assert snapshot.win_rate == 0.0
        assert snapshot.avg_return_pct == 0.0


# ===================================================================
# Tests — calculate_sector_exposure
# ===================================================================

class TestSectorExposure:
    """Tests for calculate_sector_exposure."""

    def test_groups_by_sector(self):
        positions = [
            PortfolioPosition(symbol="AAPL", quantity=10, avg_entry_price=100,
                              current_price=100, market_value=1000.0,
                              unrealized_pnl=0.0, unrealized_pnl_pct=0.0, sector="Technology"),
            PortfolioPosition(symbol="MSFT", quantity=10, avg_entry_price=100,
                              current_price=100, market_value=1000.0,
                              unrealized_pnl=0.0, unrealized_pnl_pct=0.0, sector="Technology"),
            PortfolioPosition(symbol="JPM", quantity=10, avg_entry_price=100,
                              current_price=100, market_value=1000.0,
                              unrealized_pnl=0.0, unrealized_pnl_pct=0.0, sector="Financial"),
        ]
        exposure = calculate_sector_exposure(positions)
        assert exposure["Technology"] == pytest.approx(66.67, rel=0.01)  # 2000/3000
        assert exposure["Financial"] == pytest.approx(33.33, rel=0.01)  # 1000/3000

    def test_empty_positions(self):
        assert calculate_sector_exposure([]) == {}

    def test_zero_market_value(self):
        positions = [
            PortfolioPosition(symbol="AAPL", quantity=10, avg_entry_price=100,
                              current_price=0.0, market_value=0.0,
                              unrealized_pnl=0.0, unrealized_pnl_pct=0.0, sector="Technology"),
        ]
        assert calculate_sector_exposure(positions) == {}


# ===================================================================
# Tests — calculate_risk_concentration
# ===================================================================

class TestRiskConcentration:
    """Tests for calculate_risk_concentration."""

    def test_per_symbol_allocation(self):
        positions = [
            PortfolioPosition(symbol="AAPL", quantity=10, avg_entry_price=100,
                              current_price=100, market_value=1000.0,
                              unrealized_pnl=0.0, unrealized_pnl_pct=0.0, sector="Technology"),
            PortfolioPosition(symbol="MSFT", quantity=10, avg_entry_price=100,
                              current_price=100, market_value=500.0,
                              unrealized_pnl=0.0, unrealized_pnl_pct=0.0, sector="Technology"),
        ]
        concentration = calculate_risk_concentration(positions, total_equity=1500.0)
        assert concentration["AAPL"] == pytest.approx(66.67, rel=0.01)
        assert concentration["MSFT"] == pytest.approx(33.33, rel=0.01)

    def test_empty_positions(self):
        assert calculate_risk_concentration([]) == {}

    def test_zero_equity(self):
        positions = [
            PortfolioPosition(symbol="AAPL", quantity=10, avg_entry_price=100,
                              current_price=100, market_value=1000.0,
                              unrealized_pnl=0.0, unrealized_pnl_pct=0.0, sector="Technology"),
        ]
        assert calculate_risk_concentration(positions, total_equity=0.0) == {}


# ===================================================================
# Tests — get_portfolio_health
# ===================================================================

class TestPortfolioHealth:
    """Tests for get_portfolio_health."""

    def _make_snapshot(self, **overrides) -> PortfolioSnapshot:
        defaults = {
            "cash": 5000.0,
            "total_market_value": 20000.0,
            "total_equity": 25000.0,
            "positions": [
                PortfolioPosition(symbol="AAPL", quantity=50, avg_entry_price=185.0,
                                  current_price=200.0, market_value=10000.0,
                                  unrealized_pnl=750.0, unrealized_pnl_pct=8.11, sector="Technology"),
            ],
            "total_unrealized_pnl": 750.0,
            "total_realized_pnl": 200.0,
            "win_rate": 0.55,
            "avg_return_pct": 3.5,
            "sector_exposure": {"Technology": 50.0, "Financial": 50.0},
            "risk_concentration": {"AAPL": 40.0},
            "open_positions_count": 1,
        }
        defaults.update(overrides)
        return PortfolioSnapshot(**defaults)

    def test_healthy_portfolio(self):
        snapshot = self._make_snapshot(
            risk_concentration={"AAPL": 15.0},
            sector_exposure={"Technology": 30.0},
            total_unrealized_pnl=500.0,
            win_rate=0.55,
            open_positions_count=3,
        )
        health = get_portfolio_health(snapshot)
        assert health["status"] == "HEALTHY"
        assert health["issues"] == []

    def test_warning_position_over_20_pct(self):
        snapshot = self._make_snapshot(
            risk_concentration={"AAPL": 25.0},
        )
        health = get_portfolio_health(snapshot)
        assert health["status"] == "WARNING"
        assert any("exceeds 20%" in issue for issue in health["issues"])

    def test_warning_sector_over_40_pct(self):
        snapshot = self._make_snapshot(
            sector_exposure={"Technology": 55.0},
        )
        health = get_portfolio_health(snapshot)
        assert health["status"] == "WARNING"
        assert any("exceeds 40%" in issue for issue in health["issues"])

    def test_warning_drawdown_over_10_pct(self):
        snapshot = self._make_snapshot(
            total_unrealized_pnl=-3000.0,  # -12% of 25000
            total_equity=25000.0,
        )
        health = get_portfolio_health(snapshot)
        assert health["status"] == "WARNING"
        assert any("Drawdown exceeds" in issue for issue in health["issues"])

    def test_caution_win_rate_below_40(self):
        snapshot = self._make_snapshot(
            win_rate=0.30,
            risk_concentration={"AAPL": 10.0},
            sector_exposure={"Technology": 30.0},
            total_unrealized_pnl=100.0,
        )
        health = get_portfolio_health(snapshot)
        assert health["status"] == "CAUTION"
        assert any("Win rate below" in issue for issue in health["issues"])

    def test_caution_too_many_positions(self):
        snapshot = self._make_snapshot(
            open_positions_count=7,
            win_rate=0.50,
            risk_concentration={"AAPL": 10.0},
            sector_exposure={"Technology": 30.0},
            total_unrealized_pnl=100.0,
        )
        health = get_portfolio_health(snapshot)
        assert health["status"] == "CAUTION"
        assert any("position count" in issue.lower() for issue in health["issues"])

    def test_warning_trumps_caution(self):
        """When both WARNING and CAUTION conditions exist, WARNING should win."""
        snapshot = self._make_snapshot(
            risk_concentration={"AAPL": 25.0},  # WARNING trigger
            open_positions_count=7,  # CAUTION trigger
            win_rate=0.30,  # CAUTION trigger
        )
        health = get_portfolio_health(snapshot)
        assert health["status"] == "WARNING"


# ===================================================================
# Tests — update_position
# ===================================================================

class TestUpdatePosition:
    """Tests for the update_position function."""

    def _make_position(self, **overrides) -> PortfolioPosition:
        defaults = {
            "symbol": "AAPL",
            "quantity": 50,
            "avg_entry_price": 185.0,
            "current_price": 200.0,
            "market_value": 10000.0,
            "unrealized_pnl": 750.0,
            "unrealized_pnl_pct": 8.11,
            "realized_pnl": 0.0,
            "sector": "Technology",
            "allocation_pct": 40.0,
            "stop_loss": 175.0,
            "take_profit": 210.0,
            "days_held": 10,
        }
        defaults.update(overrides)
        return PortfolioPosition(**defaults)

    def test_partial_sell_reduces_quantity(self):
        pos = self._make_position()
        updated = update_position(pos, {"quantity_delta": -20, "fill_price": 205.0})

        assert updated.quantity == 30  # 50 - 20
        assert updated.realized_pnl == pytest.approx((205.0 - 185.0) * 20, rel=0.01)  # 400
        assert updated.last_updated != pos.last_updated

    def test_partial_sell_no_fill_price(self):
        """When fill_price is not given, realized_pnl delta should come from explicit delta."""
        pos = self._make_position()
        updated = update_position(pos, {"quantity_delta": -10, "realized_pnl_delta": 120.0})
        assert updated.quantity == 40
        assert updated.realized_pnl == 120.0

    def test_adjust_stop_loss(self):
        pos = self._make_position()
        updated = update_position(pos, {"new_stop_loss": 185.0})
        assert updated.stop_loss == 185.0
        assert updated.quantity == 50  # unchanged
        assert updated.take_profit == 210.0  # unchanged

    def test_adjust_take_profit(self):
        pos = self._make_position()
        updated = update_position(pos, {"new_take_profit": 220.0})
        assert updated.take_profit == 220.0
        assert updated.stop_loss == 175.0  # unchanged

    def test_quantity_never_goes_negative(self):
        pos = self._make_position()
        updated = update_position(pos, {"quantity_delta": -100})
        assert updated.quantity == 0

    def test_no_changes_returns_updated_copy(self):
        """Even with no changes, the returned object should be a new equivalent copy."""
        pos = self._make_position()
        updated = update_position(pos, {})
        assert updated is not pos
        assert updated.quantity == pos.quantity
        assert updated.last_updated >= pos.last_updated


# ===================================================================
# Tests — _resolve_sector
# ===================================================================

class TestResolveSector:
    """Tests for the sector resolution helper."""

    def test_known_technology(self):
        assert _resolve_sector("AAPL") == "Technology"
        assert _resolve_sector("NVDA") == "Technology"

    def test_known_financial(self):
        assert _resolve_sector("JPM") == "Financial"
        assert _resolve_sector("BAC") == "Financial"

    def test_known_healthcare(self):
        assert _resolve_sector("JNJ") == "Healthcare"

    def test_known_consumer(self):
        assert _resolve_sector("WMT") == "Consumer"

    def test_unknown_returns_unknown(self):
        assert _resolve_sector("ZZZZ") == "Unknown"

    def test_case_insensitive(self):
        assert _resolve_sector("aapl") == "Technology"
        assert _resolve_sector("MsFt") == "Technology"
