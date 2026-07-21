from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# -----------------------------------------------------------
# Stock
# -----------------------------------------------------------
class StockBase(BaseModel):
    ticker: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    exchange: Optional[str] = None


class StockCreate(StockBase):
    pass


class StockResponse(StockBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# -----------------------------------------------------------
# Trade
# -----------------------------------------------------------
class TradeBase(BaseModel):
    ticker: str
    side: str
    quantity: int
    price: float
    notional: float
    commission: float = 0.0
    order_type: str = "market"
    signal_id: Optional[int] = None
    alpaca_order_id: Optional[str] = None


class TradeCreate(TradeBase):
    pass


class TradeResponse(TradeBase):
    id: int
    filled_at: datetime
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


# -----------------------------------------------------------
# Portfolio Position
# -----------------------------------------------------------
class PortfolioPositionBase(BaseModel):
    ticker: str
    quantity: int
    avg_entry_price: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None


class PortfolioPositionResponse(PortfolioPositionBase):
    id: int
    is_open: bool
    opened_at: datetime
    closed_at: Optional[datetime] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


# -----------------------------------------------------------
# Signal
# -----------------------------------------------------------
class SignalBase(BaseModel):
    ticker: str
    direction: str
    confidence: float
    scanner_score: float = 0.0
    sentiment_score: float = 0.0
    technical_score: float = 0.0
    fundamental_score: float = 0.0
    composite_score: float = 0.0
    suggested_entry: Optional[float] = None
    suggested_stop: Optional[float] = None
    suggested_target: Optional[float] = None
    position_size_pct: Optional[float] = None


class SignalCreate(SignalBase):
    pass


class SignalResponse(SignalBase):
    id: int
    status: str
    metadata_json: Optional[dict] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    decision_reason: Optional[str] = None

    model_config = {"from_attributes": True}


# -----------------------------------------------------------
# Watchlist Item
# -----------------------------------------------------------
class WatchlistItemBase(BaseModel):
    ticker: str
    added_reason: Optional[str] = None
    target_buy_price: Optional[float] = None
    alert_enabled: bool = True


class WatchlistItemCreate(WatchlistItemBase):
    pass


class WatchlistItemResponse(WatchlistItemBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# -----------------------------------------------------------
# Daily Report
# -----------------------------------------------------------
class DailyReportResponse(BaseModel):
    id: int
    report_date: datetime
    starting_equity: float
    ending_equity: float
    net_pnl: float
    net_pnl_pct: float
    win_rate: Optional[float] = None
    total_trades: int
    winning_trades: int
    losing_trades: int
    max_drawdown_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    signals_generated: int
    signals_accepted: int
    signals_rejected: int
    summary_text: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# -----------------------------------------------------------
# Health
# -----------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class HealthReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, str]


# -----------------------------------------------------------
# Scanner
# -----------------------------------------------------------
class ScanResultResponse(BaseModel):
    symbol: str
    price: float
    change_pct: float
    volume: int
    relative_volume: float
    rsi_14: Optional[float] = None
    above_sma_50: Optional[bool] = None
    above_sma_200: Optional[bool] = None
    score: float = 0.0


class GainersLosersResponse(BaseModel):
    symbol: str
    price: float
    change_pct: float
    volume: int


class VolumeSpikeResponse(BaseModel):
    symbol: str
    price: float
    volume: int
    avg_volume: int
    relative_volume: float


class UnusualOptionsResponse(BaseModel):
    symbol: str
    contract_type: str
    strike: float
    expiry: str
    volume: int
    open_interest: int
    premium: Optional[float] = None
    trade_type: Optional[str] = None
