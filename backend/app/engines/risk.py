"""
Risk Manager Engine — gatekeeper for every trade.

Responsible for:
- Position sizing from account equity and risk parameters
- Stop-loss and take-profit calculation (ATR-based or simple)
- Pre-trade risk checks (reward-to-risk, position limits, drawdown, sector exposure)
- Daily risk state tracking with circuit-breaker halts

Conservative / fail-safe: when in doubt, the trade is rejected.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RiskParams:
    """Configurable risk parameters for the trading account."""
    account_value: float
    max_risk_per_trade_pct: float = 0.01       # 1% per trade
    max_daily_loss_pct: float = 0.03           # 3% daily drawdown
    max_consecutive_losses: int = 3
    min_reward_to_risk: float = 2.0
    max_position_pct: float = 0.20             # max 20% in one position
    max_sector_exposure_pct: float = 0.40      # max 40% in one sector


@dataclass
class TradeCheck:
    """Result of a pre-trade risk evaluation."""
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_shares: int
    risk_amount: float
    reward_amount: float
    reward_to_risk_ratio: float
    is_approved: bool
    rejection_reason: Optional[str] = None
    max_shares: int = 0
    suggested_shares: int = 0


@dataclass
class DailyRiskState:
    """Mutable daily risk-tracking state."""
    current_daily_pnl: float = 0.0
    consecutive_losses: int = 0
    trades_today: int = 0
    is_trading_halted: bool = False
    halt_reason: Optional[str] = None
    # Per-sector exposure tracking: dict of sector -> dollar exposure
    sector_exposure: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core calculation helpers
# ---------------------------------------------------------------------------

def calculate_position_size(
    entry_price: float,
    stop_loss: float,
    account_value: float,
    max_risk_pct: float = 0.01,
) -> int:
    """Calculate the maximum number of shares for a position given risk.

    risk_amount      = account_value * max_risk_pct
    risk_per_share   = abs(entry_price - stop_loss)
    position_size    = floor(risk_amount / risk_per_share)

    Returns 0 if risk_per_share is zero (e.g. entry == stop).
    """
    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share <= 0.0:
        return 0
    risk_amount = account_value * max_risk_pct
    shares = int(math.floor(risk_amount / risk_per_share))
    return max(shares, 0)


def calculate_stop_loss(
    entry_price: float,
    atr_value: float,
    direction: str = "LONG",
    multiplier: float = 2.0,
) -> float:
    """Calculate a dynamic stop-loss level using ATR.

    LONG  → entry_price - (ATR * multiplier)
    SHORT → entry_price + (ATR * multiplier)
    """
    if atr_value < 0:
        atr_value = abs(atr_value)
    offset = atr_value * multiplier
    direction_upper = direction.upper()
    if direction_upper == "SHORT":
        return entry_price + offset
    # Default LONG (conservative)
    return entry_price - offset


def calculate_take_profit(
    entry_price: float,
    stop_loss: float,
    min_rr: float = 2.0,
) -> float:
    """Calculate take-profit price so reward:risk ≥ min_rr.

    LONG  → entry + (entry - stop) * min_rr
    SHORT → entry - (stop - entry) * min_rr  [stop > entry for SHORT]
    """
    if stop_loss < entry_price:
        # LONG: stop is below entry
        risk = entry_price - stop_loss
        return entry_price + risk * min_rr
    else:
        # SHORT: stop is above entry
        risk = stop_loss - entry_price
        return entry_price - risk * min_rr


# ---------------------------------------------------------------------------
# Pre-trade risk check
# ---------------------------------------------------------------------------

def check_trade(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    account_value: float,
    current_positions: Optional[list[dict]] = None,
    daily_state: Optional[DailyRiskState] = None,
    atr_value: Optional[float] = None,
    symbol: str = "",
    sector: str = "",
    risk_params: Optional[RiskParams] = None,
) -> TradeCheck:
    """Evaluate a candidate trade against all risk rules.

    Parameters
    ----------
    entry_price : float
    stop_loss : float
    take_profit : float
    account_value : float
        Total account equity.
    current_positions : list[dict] | None
        List of dicts with keys: symbol, sector, market_value (dollars).
        Used for sector-exposure checks.
    daily_state : DailyRiskState | None
        Current daily state. If None, a fresh default state is used.
    atr_value : float | None
        Provided for informational / validation purposes.
    symbol : str
        Ticker symbol for the candidate trade.
    sector : str
        Sector of the candidate trade (e.g. "Technology"). Used for sector
        exposure checks alongside current_positions.
    risk_params : RiskParams | None
        Custom risk parameters. If None, defaults are used.

    Returns
    -------
    TradeCheck
    """
    if risk_params is None:
        risk_params = RiskParams(account_value=account_value)

    if daily_state is None:
        daily_state = DailyRiskState()

    # Short-circuit: trading already halted
    if daily_state.is_trading_halted:
        return TradeCheck(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_shares=0,
            risk_amount=0.0,
            reward_amount=0.0,
            reward_to_risk_ratio=0.0,
            is_approved=False,
            rejection_reason=f"Trading halted: {daily_state.halt_reason}",
            max_shares=0,
            suggested_shares=0,
        )

    # --- Reward-to-Risk ---
    risk_per_share = abs(entry_price - stop_loss)
    reward_per_share = abs(take_profit - entry_price)
    reward_to_risk = reward_per_share / risk_per_share if risk_per_share > 0 else 0.0

    if reward_to_risk < risk_params.min_reward_to_risk:
        return TradeCheck(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_shares=0,
            risk_amount=0.0,
            reward_amount=0.0,
            reward_to_risk_ratio=round(reward_to_risk, 4),
            is_approved=False,
            rejection_reason=(
                f"Reward-to-risk {reward_to_risk:.2f}:1 below minimum "
                f"{risk_params.min_reward_to_risk}:1"
            ),
            max_shares=0,
            suggested_shares=0,
        )

    # --- Position size ---
    position_size = calculate_position_size(
        entry_price, stop_loss, account_value, risk_params.max_risk_per_trade_pct
    )

    if position_size <= 0:
        return TradeCheck(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_shares=0,
            risk_amount=0.0,
            reward_amount=0.0,
            reward_to_risk_ratio=round(reward_to_risk, 4),
            is_approved=False,
            rejection_reason="Invalid position size — risk per share is zero or negative",
            max_shares=0,
            suggested_shares=0,
        )

    # --- Max position exposure ---
    position_value = position_size * entry_price
    max_position_value = account_value * risk_params.max_position_pct
    max_shares = int(math.floor(max_position_value / entry_price))

    if position_value > max_position_value:
        # Clamp to max allowed
        position_size = max_shares
        position_value = position_size * entry_price

    if position_size <= 0:
        return TradeCheck(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_shares=0,
            risk_amount=0.0,
            reward_amount=0.0,
            reward_to_risk_ratio=round(reward_to_risk, 4),
            is_approved=False,
            rejection_reason=(
                f"Position value (${position_value:,.2f}) exceeds max position "
                f"exposure {risk_params.max_position_pct*100:.0f}% of account"
            ),
            max_shares=max_shares,
            suggested_shares=0,
        )

    # --- Daily loss limit ---
    # Calculate potential loss if this trade hits stop
    potential_loss = position_size * risk_per_share
    projected_daily_pnl = daily_state.current_daily_pnl - potential_loss
    max_daily_loss = account_value * risk_params.max_daily_loss_pct

    if projected_daily_pnl <= -max_daily_loss:
        return TradeCheck(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_shares=0,
            risk_amount=round(potential_loss, 2),
            reward_amount=round(position_size * reward_per_share, 2),
            reward_to_risk_ratio=round(reward_to_risk, 4),
            is_approved=False,
            rejection_reason=(
                f"Trade would breach daily loss limit of "
                f"${max_daily_loss:,.2f} ({risk_params.max_daily_loss_pct*100:.0f}%) — "
                f"current P&L: ${daily_state.current_daily_pnl:,.2f}, "
                f"potential loss: ${potential_loss:,.2f}"
            ),
            max_shares=max_shares,
            suggested_shares=0,
        )

    # --- Consecutive losses ---
    if daily_state.consecutive_losses >= risk_params.max_consecutive_losses:
        return TradeCheck(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_shares=0,
            risk_amount=round(potential_loss, 2),
            reward_amount=round(position_size * reward_per_share, 2),
            reward_to_risk_ratio=round(reward_to_risk, 4),
            is_approved=False,
            rejection_reason=(
                f"Consecutive loss limit reached ({daily_state.consecutive_losses} "
                f">= {risk_params.max_consecutive_losses})"
            ),
            max_shares=max_shares,
            suggested_shares=0,
        )

    # --- Sector exposure ---
    if sector and current_positions:
        # Sum existing market value for positions in the same sector
        sector_value = sum(
            p.get("market_value", 0.0)
            for p in current_positions
            if p.get("sector", "") == sector
        )
        # Also consider tracked exposure in daily_state
        tracked_exposure = daily_state.sector_exposure.get(sector, 0.0)
        total_sector_value = max(sector_value, tracked_exposure) + position_value
        max_sector_value = account_value * risk_params.max_sector_exposure_pct

        if total_sector_value > max_sector_value:
            return TradeCheck(
                symbol=symbol,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size_shares=0,
                risk_amount=round(potential_loss, 2),
                reward_amount=round(position_size * reward_per_share, 2),
                reward_to_risk_ratio=round(reward_to_risk, 4),
                is_approved=False,
                rejection_reason=(
                    f"Sector '{sector}' exposure would be "
                    f"${total_sector_value:,.2f} — exceeds "
                    f"{risk_params.max_sector_exposure_pct*100:.0f}% of account "
                    f"(${max_sector_value:,.2f})"
                ),
                max_shares=max_shares,
                suggested_shares=0,
            )

    # --- All checks passed ---
    return TradeCheck(
        symbol=symbol,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size_shares=position_size,
        risk_amount=round(position_size * risk_per_share, 2),
        reward_amount=round(position_size * reward_per_share, 2),
        reward_to_risk_ratio=round(reward_to_risk, 4),
        is_approved=True,
        rejection_reason=None,
        max_shares=max_shares,
        suggested_shares=position_size,
    )


# ---------------------------------------------------------------------------
# Daily state management
# ---------------------------------------------------------------------------

def update_daily_state(
    daily_state: DailyRiskState,
    trade_result: dict,
    account_value: float,
    risk_params: Optional[RiskParams] = None,
) -> DailyRiskState:
    """Update the daily risk state after a trade closes.

    Parameters
    ----------
    daily_state : DailyRiskState
    trade_result : dict
        Must contain at least: 'pnl' (float), representing realized P&L.
        Optional: 'sector' (str).
    account_value : float
    risk_params : RiskParams | None

    Returns
    -------
    DailyRiskState — updated (mutated in place, also returned).
    """
    if risk_params is None:
        risk_params = RiskParams(account_value=account_value)

    pnl = trade_result.get("pnl", 0.0)
    daily_state.current_daily_pnl += pnl
    daily_state.trades_today += 1

    # Update consecutive wins / losses
    if pnl > 0:
        daily_state.consecutive_losses = 0
    elif pnl < 0:
        daily_state.consecutive_losses += 1
    # pnl == 0 (breakeven) leaves the streak unchanged

    # Track sector exposure
    sector = trade_result.get("sector", "")
    if sector:
        current = daily_state.sector_exposure.get(sector, 0.0)
        daily_state.sector_exposure[sector] = current + pnl  # delta, not absolute

    # --- Circuit breakers ---
    # Daily loss limit
    max_daily_loss = account_value * risk_params.max_daily_loss_pct
    if daily_state.current_daily_pnl <= -max_daily_loss:
        daily_state.is_trading_halted = True
        daily_state.halt_reason = (
            f"Daily loss limit breached: "
            f"${daily_state.current_daily_pnl:,.2f} <= -${max_daily_loss:,.2f}"
        )

    # Consecutive losses
    if daily_state.consecutive_losses >= risk_params.max_consecutive_losses:
        daily_state.is_trading_halted = True
        daily_state.halt_reason = (
            f"Consecutive loss limit reached: "
            f"{daily_state.consecutive_losses} >= {risk_params.max_consecutive_losses}"
        )

    return daily_state


def reset_daily_state() -> DailyRiskState:
    """Return a fresh DailyRiskState for a new trading day."""
    return DailyRiskState()
