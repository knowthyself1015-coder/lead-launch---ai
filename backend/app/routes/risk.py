"""
Risk management API routes.

POST /api/v1/risk/check          — evaluate a candidate trade
GET  /api/v1/risk/daily-state    — current daily risk state
POST /api/v1/risk/reset          — reset daily state for new trading day
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.engines.risk import (
    RiskParams,
    TradeCheck,
    DailyRiskState,
    check_trade,
    calculate_position_size,
    calculate_stop_loss,
    calculate_take_profit,
    update_daily_state,
    reset_daily_state,
)

router = APIRouter(prefix="/risk", tags=["risk"])


# ---------------------------------------------------------------------------
# In-memory state — persisted to Redis in production
# ---------------------------------------------------------------------------
_current_daily_state: DailyRiskState = DailyRiskState()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class RiskCheckRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10, description="Ticker symbol")
    entry_price: float = Field(..., gt=0, description="Entry price per share")
    stop_loss: float = Field(..., gt=0, description="Stop-loss price")
    take_profit: float = Field(..., gt=0, description="Take-profit price")
    atr_value: Optional[float] = Field(None, gt=0, description="Optional ATR value")
    account_value: Optional[float] = Field(None, gt=0, description="Account equity (default: 100000)")
    sector: Optional[str] = Field(None, description="Sector of the trade (e.g. Technology)")
    current_positions: Optional[list[dict]] = Field(
        None, description="Current positions for sector exposure check"
    )
    max_risk_per_trade_pct: Optional[float] = Field(
        0.01, gt=0, le=1.0, description="Max risk per trade as fraction"
    )
    max_daily_loss_pct: Optional[float] = Field(
        0.03, gt=0, le=1.0, description="Max daily loss as fraction"
    )
    max_consecutive_losses: Optional[int] = Field(
        3, ge=1, description="Max consecutive losses before halt"
    )
    min_reward_to_risk: Optional[float] = Field(
        2.0, ge=0, description="Minimum reward-to-risk ratio"
    )
    max_position_pct: Optional[float] = Field(
        0.20, gt=0, le=1.0, description="Max position size as fraction"
    )
    max_sector_exposure_pct: Optional[float] = Field(
        0.40, gt=0, le=1.0, description="Max sector exposure as fraction"
    )


class RiskCheckResponse(BaseModel):
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_shares: int
    risk_amount: float
    reward_amount: float
    reward_to_risk_ratio: float
    is_approved: bool
    rejection_reason: Optional[str]
    max_shares: int
    suggested_shares: int


class DailyStateResponse(BaseModel):
    current_daily_pnl: float
    consecutive_losses: int
    trades_today: int
    is_trading_halted: bool
    halt_reason: Optional[str]


class TradeResultUpdate(BaseModel):
    pnl: float = Field(..., description="Realized P&L from the closed trade")
    sector: Optional[str] = Field(None, description="Sector of the traded symbol")
    account_value: Optional[float] = Field(None, gt=0, description="Current account value")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/check", response_model=RiskCheckResponse)
async def route_risk_check(body: RiskCheckRequest):
    """Evaluate a candidate trade against all risk rules.

    Returns a TradeCheck with approval status, sizing recommendations,
    and a specific rejection reason if not approved.
    """
    account_value = body.account_value or 100_000.0

    risk_params = RiskParams(
        account_value=account_value,
        max_risk_per_trade_pct=body.max_risk_per_trade_pct,
        max_daily_loss_pct=body.max_daily_loss_pct,
        max_consecutive_losses=body.max_consecutive_losses,
        min_reward_to_risk=body.min_reward_to_risk,
        max_position_pct=body.max_position_pct,
        max_sector_exposure_pct=body.max_sector_exposure_pct,
    )

    result = check_trade(
        entry_price=body.entry_price,
        stop_loss=body.stop_loss,
        take_profit=body.take_profit,
        account_value=account_value,
        current_positions=body.current_positions,
        daily_state=_current_daily_state,
        atr_value=body.atr_value,
        symbol=body.symbol,
        sector=body.sector or "",
        risk_params=risk_params,
    )

    return RiskCheckResponse(
        symbol=result.symbol,
        entry_price=result.entry_price,
        stop_loss=result.stop_loss,
        take_profit=result.take_profit,
        position_size_shares=result.position_size_shares,
        risk_amount=result.risk_amount,
        reward_amount=result.reward_amount,
        reward_to_risk_ratio=result.reward_to_risk_ratio,
        is_approved=result.is_approved,
        rejection_reason=result.rejection_reason,
        max_shares=result.max_shares,
        suggested_shares=result.suggested_shares,
    )


@router.get("/daily-state", response_model=DailyStateResponse)
async def route_get_daily_state():
    """Return the current daily risk state (P&L, losses, halt status)."""
    return DailyStateResponse(
        current_daily_pnl=_current_daily_state.current_daily_pnl,
        consecutive_losses=_current_daily_state.consecutive_losses,
        trades_today=_current_daily_state.trades_today,
        is_trading_halted=_current_daily_state.is_trading_halted,
        halt_reason=_current_daily_state.halt_reason,
    )


@router.post("/reset", response_model=DailyStateResponse)
async def route_reset_daily_state():
    """Reset daily risk state for a new trading day."""
    global _current_daily_state
    _current_daily_state = reset_daily_state()
    return DailyStateResponse(
        current_daily_pnl=_current_daily_state.current_daily_pnl,
        consecutive_losses=_current_daily_state.consecutive_losses,
        trades_today=_current_daily_state.trades_today,
        is_trading_halted=_current_daily_state.is_trading_halted,
        halt_reason=_current_daily_state.halt_reason,
    )


@router.post("/update-state", response_model=DailyStateResponse)
async def route_update_daily_state(body: TradeResultUpdate):
    """Update daily risk state after a trade closes.

    Call this after each trade to keep the circuit-breaker current.
    """
    global _current_daily_state
    account_value = body.account_value or 100_000.0

    _current_daily_state = update_daily_state(
        daily_state=_current_daily_state,
        trade_result={"pnl": body.pnl, "sector": body.sector},
        account_value=account_value,
    )

    return DailyStateResponse(
        current_daily_pnl=_current_daily_state.current_daily_pnl,
        consecutive_losses=_current_daily_state.consecutive_losses,
        trades_today=_current_daily_state.trades_today,
        is_trading_halted=_current_daily_state.is_trading_halted,
        halt_reason=_current_daily_state.halt_reason,
    )
