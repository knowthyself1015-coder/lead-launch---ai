"""
Decisions API routes — trade decision endpoints for the AlphaSight dashboard.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import get_settings
from app.engines.market_data import (
    PolygonProvider,
    AlpacaProvider,
    MarketDataProvider,
)
from app.engines.decisions import (
    decide,
    decide_batch,
    generate_summary,
    should_sell,
    TradeDecision,
    DecisionSummary,
)

router = APIRouter(prefix="/decisions", tags=["decisions"])


# ---------------------------------------------------------------------------
# Pydantic schemas for request/response
# ---------------------------------------------------------------------------

class TradeDecisionResponse(BaseModel):
    symbol: str
    decision: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: int
    risk_amount: float
    reward_amount: float
    reward_to_risk_ratio: float
    reasoning: str
    timestamp: str

    model_config = {"from_attributes": True}


class DecisionSummaryResponse(BaseModel):
    total_analyzed: int
    buy_signals: int
    sell_signals: int
    hold_signals: int
    watchlist: int
    top_pick: Optional[TradeDecisionResponse] = None


class BatchRequest(BaseModel):
    symbols: list[str]
    account_value: float = Field(default=100_000, ge=1_000)


class SellCheckRequest(BaseModel):
    symbol: str
    entry_price: float
    current_price: float = Field(default=0.0)
    quantity: int = Field(default=0, ge=0)
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def _get_provider() -> MarketDataProvider:
    """Instantiate the configured market data provider."""
    settings = get_settings()
    if settings.POLYGON_API_KEY:
        return PolygonProvider()
    if settings.ALPACA_API_KEY:
        return AlpacaProvider()
    raise HTTPException(
        status_code=500,
        detail="No market data provider configured — set POLYGON_API_KEY or ALPACA_API_KEY",
    )


def _decision_to_response(d: TradeDecision) -> TradeDecisionResponse:
    """Convert a TradeDecision dataclass to a Pydantic response model."""
    return TradeDecisionResponse(
        symbol=d.symbol,
        decision=d.decision,
        confidence=d.confidence,
        entry_price=d.entry_price,
        stop_loss=d.stop_loss,
        take_profit=d.take_profit,
        position_size=d.position_size,
        risk_amount=d.risk_amount,
        reward_amount=d.reward_amount,
        reward_to_risk_ratio=d.reward_to_risk_ratio,
        reasoning=d.reasoning,
        timestamp=d.timestamp,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{symbol}", response_model=TradeDecisionResponse)
async def route_decide_single(
    symbol: str,
    account_value: float = Query(100_000, ge=1_000),
    score_threshold: float = Query(85.0, ge=0.0, le=100.0),
):
    """Get a trade decision for a single symbol."""
    provider = _get_provider()
    try:
        decision = await decide(
            symbol=symbol.upper(),
            provider=provider,
            account_value=account_value,
            score_threshold=score_threshold,
        )
        return _decision_to_response(decision)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Decision evaluation failed for {symbol}: {exc}",
        )


@router.post("/batch", response_model=list[TradeDecisionResponse])
async def route_decide_batch(body: BatchRequest):
    """Evaluate a batch of symbols and return decisions sorted by confidence."""
    provider = _get_provider()
    try:
        symbols = [s.strip().upper() for s in body.symbols if s.strip()]
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        decisions = await decide_batch(
            symbols=symbols,
            provider=provider,
            account_value=body.account_value,
        )
        return [_decision_to_response(d) for d in decisions]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Batch decision evaluation failed: {exc}",
        )


@router.get("/summary", response_model=DecisionSummaryResponse)
async def route_decision_summary(
    symbols: Optional[str] = Query(
        None,
        description="Comma-separated list of symbols to analyze (default: built-in universe)",
    ),
    account_value: float = Query(100_000, ge=1_000),
):
    """Generate a decision summary across a scanned universe of symbols."""
    provider = _get_provider()

    # Default universe if none provided
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    else:
        symbol_list = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META",
            "NVDA", "TSLA", "JPM", "V", "WMT",
        ]

    try:
        decisions = await decide_batch(
            symbols=symbol_list,
            provider=provider,
            account_value=account_value,
        )
        summary = generate_summary(decisions)

        top_pick_response = None
        if summary.top_pick:
            top_pick_response = _decision_to_response(summary.top_pick)

        return DecisionSummaryResponse(
            total_analyzed=summary.total_analyzed,
            buy_signals=summary.buy_signals,
            sell_signals=summary.sell_signals,
            hold_signals=summary.hold_signals,
            watchlist=summary.watchlist,
            top_pick=top_pick_response,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Summary generation failed: {exc}",
        )


@router.post("/sell-check", response_model=TradeDecisionResponse)
async def route_sell_check(body: SellCheckRequest):
    """Evaluate whether a held position should be sold."""
    provider = _get_provider()
    try:
        portfolio_position = {
            "symbol": body.symbol.upper(),
            "entry_price": body.entry_price,
            "quantity": body.quantity,
            "stop_loss_price": body.stop_loss_price,
            "take_profit_price": body.take_profit_price,
        }
        decision = await should_sell(
            portfolio_position=portfolio_position,
            provider=provider,
        )
        return _decision_to_response(decision)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Sell-check failed for {body.symbol}: {exc}",
        )
