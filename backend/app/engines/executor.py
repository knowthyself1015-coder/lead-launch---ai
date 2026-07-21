"""
Alpaca Trade Executor — executes trades via the Alpaca Trading API.

Responsible for:
- Placing buy orders with stop-loss and take-profit brackets
- Placing sell orders (market)
- Fetching account info (cash, equity, buying power)
- Fetching current positions
- Emergency cancel-all-orders
- Rate-limited, paper-first, with detailed audit logging
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TradeResult:
    """Result of a single trade execution attempt."""
    success: bool
    order_id: Optional[str] = None
    symbol: str = ""
    side: str = ""  # "buy" or "sell"
    quantity: int = 0
    filled_price: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AccountInfo:
    """Snapshot of Alpaca account state."""
    cash: float = 0.0
    equity: float = 0.0
    buying_power: float = 0.0
    portfolio_value: float = 0.0
    daytrade_count: int = 0
    status: str = "UNKNOWN"


@dataclass
class PositionInfo:
    """Snapshot of an open Alpaca position."""
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pl: Optional[float] = None
    unrealized_plpc: Optional[float] = None


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple token-bucket rate limiter for Alpaca API calls."""

    def __init__(self, max_calls_per_second: float = 50.0):
        import time
        self._interval = 1.0 / max_calls_per_second
        self._last_call = 0.0
        self._time = time

    async def acquire(self) -> None:
        import asyncio
        now = self._time.monotonic()
        wait = self._interval - (now - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = self._time.monotonic()


# ---------------------------------------------------------------------------
# Alpaca Executor
# ---------------------------------------------------------------------------

class AlpacaExecutor:
    """Executes trades via the Alpaca Trading API (paper-first by default)."""

    def __init__(self) -> None:
        self._client: Any = None
        self._rate_limiter = RateLimiter(max_calls_per_second=50)
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazily initialize the Alpaca client from config."""
        if self._initialized:
            return

        settings = get_settings()

        if not settings.ALPACA_API_KEY or not settings.ALPACA_SECRET_KEY:
            logger.warning(
                "AlpacaExecutor: ALPACA_API_KEY or ALPACA_SECRET_KEY not set — "
                "trading will be simulated (dry-run mode)."
            )
            self._initialized = True
            return

        try:
            from alpaca.trading.client import TradingClient

            self._client = TradingClient(
                api_key=settings.ALPACA_API_KEY,
                secret_key=settings.ALPACA_SECRET_KEY,
                paper=True,  # ALWAYS paper — live requires explicit config change
                url_override=settings.ALPACA_BASE_URL,
            )
            logger.info(
                "AlpacaExecutor initialized — base URL: %s (paper trading)",
                settings.ALPACA_BASE_URL,
            )
        except ImportError:
            logger.error(
                "alpaca-py not installed. Install with: pip install alpaca-py. "
                "Trading will be simulated until the package is available."
            )
        except Exception:
            logger.exception("Failed to initialize Alpaca trading client")

        self._initialized = True

    # ------------------------------------------------------------------
    # Account & Positions
    # ------------------------------------------------------------------

    async def get_account(self) -> AccountInfo:
        """Return current account information from Alpaca."""
        self._ensure_initialized()

        if self._client is None:
            logger.warning("get_account: Alpaca client unavailable — returning zeros")
            return AccountInfo(status="DRY_RUN")

        try:
            await self._rate_limiter.acquire()
            import asyncio
            account = await asyncio.to_thread(self._client.get_account)

            return AccountInfo(
                cash=float(account.cash),
                equity=float(account.equity),
                buying_power=float(account.buying_power),
                portfolio_value=float(account.portfolio_value),
                daytrade_count=int(account.daytrade_count),
                status=str(getattr(account, "status", "ACTIVE")),
            )
        except Exception:
            logger.exception("get_account: failed to fetch account info")
            return AccountInfo(status="ERROR")

    async def get_positions(self) -> list[PositionInfo]:
        """Return current open positions from Alpaca."""
        self._ensure_initialized()

        if self._client is None:
            logger.warning("get_positions: Alpaca client unavailable")
            return []

        try:
            await self._rate_limiter.acquire()
            import asyncio
            positions = await asyncio.to_thread(self._client.get_all_positions)

            return [
                PositionInfo(
                    symbol=p.symbol,
                    qty=float(p.qty),
                    avg_entry_price=float(p.avg_entry_price),
                    current_price=float(p.current_price) if p.current_price else None,
                    market_value=float(p.market_value) if p.market_value else None,
                    unrealized_pl=float(p.unrealized_pl) if p.unrealized_pl else None,
                    unrealized_plpc=float(p.unrealized_plpc) if p.unrealized_plpc else None,
                )
                for p in positions
            ]
        except Exception:
            logger.exception("get_positions: failed to fetch positions")
            return []

    # ------------------------------------------------------------------
    # Trade Execution
    # ------------------------------------------------------------------

    async def execute_buy(
        self,
        symbol: str,
        quantity: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> TradeResult:
        """Execute a BUY order, optionally with bracket orders for stop/target.

        Args:
            symbol: Ticker symbol.
            quantity: Number of shares (must be > 0).
            stop_loss: Optional stop-loss price for the bracket.
            take_profit: Optional take-profit price for the bracket.

        Returns:
            TradeResult with order details.
        """
        self._ensure_initialized()

        if quantity <= 0:
            return TradeResult(
                success=False,
                symbol=symbol,
                side="buy",
                quantity=quantity,
                error="Quantity must be > 0",
            )

        logger.info(
            "EXECUTE BUY: %s x %d shares (stop=%.2f, target=%.2f)",
            symbol, quantity,
            stop_loss or 0,
            take_profit or 0,
        )

        if self._client is None:
            logger.warning("execute_buy: DRY_RUN — simulated fill for %s", symbol)
            return TradeResult(
                success=True,
                order_id="dry-run-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
                symbol=symbol.upper(),
                side="buy",
                quantity=quantity,
                filled_price=0.0,  # unknown in dry run
            )

        try:
            await self._rate_limiter.acquire()
            import asyncio
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            order_request = MarketOrderRequest(
                symbol=symbol.upper(),
                qty=quantity,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )

            # If stop_loss and take_profit are provided, use bracket order
            if stop_loss is not None and take_profit is not None:
                from alpaca.trading.requests import TakeProfitRequest, StopLossRequest
                order_request.take_profit = TakeProfitRequest(limit_price=take_profit)
                order_request.stop_loss = StopLossRequest(stop_price=stop_loss)

            order = await asyncio.to_thread(self._client.submit_order, order_request)

            filled_price = (
                float(order.filled_avg_price)
                if order.filled_avg_price
                else None
            )

            logger.info(
                "EXECUTE BUY — order %s filled: %s x %d @ %.2f",
                order.id, symbol, quantity, filled_price or 0,
            )

            return TradeResult(
                success=True,
                order_id=str(order.id),
                symbol=symbol.upper(),
                side="buy",
                quantity=quantity,
                filled_price=filled_price,
                timestamp=datetime.now(timezone.utc),
            )

        except Exception as exc:
            logger.exception("execute_buy: failed for %s", symbol)
            return TradeResult(
                success=False,
                symbol=symbol.upper(),
                side="buy",
                quantity=quantity,
                error=str(exc),
            )

    async def execute_sell(self, symbol: str, quantity: int) -> TradeResult:
        """Execute a SELL (market) order.

        Args:
            symbol: Ticker symbol.
            quantity: Number of shares (must be > 0).

        Returns:
            TradeResult with order details.
        """
        self._ensure_initialized()

        if quantity <= 0:
            return TradeResult(
                success=False,
                symbol=symbol,
                side="sell",
                quantity=quantity,
                error="Quantity must be > 0",
            )

        logger.info("EXECUTE SELL: %s x %d shares", symbol, quantity)

        if self._client is None:
            logger.warning("execute_sell: DRY_RUN — simulated fill for %s", symbol)
            return TradeResult(
                success=True,
                order_id="dry-run-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
                symbol=symbol.upper(),
                side="sell",
                quantity=quantity,
                filled_price=0.0,
            )

        try:
            await self._rate_limiter.acquire()
            import asyncio
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            order_request = MarketOrderRequest(
                symbol=symbol.upper(),
                qty=quantity,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )

            order = await asyncio.to_thread(self._client.submit_order, order_request)

            filled_price = (
                float(order.filled_avg_price)
                if order.filled_avg_price
                else None
            )

            logger.info(
                "EXECUTE SELL — order %s filled: %s x %d @ %.2f",
                order.id, symbol, quantity, filled_price or 0,
            )

            return TradeResult(
                success=True,
                order_id=str(order.id),
                symbol=symbol.upper(),
                side="sell",
                quantity=quantity,
                filled_price=filled_price,
                timestamp=datetime.now(timezone.utc),
            )

        except Exception as exc:
            logger.exception("execute_sell: failed for %s", symbol)
            return TradeResult(
                success=False,
                symbol=symbol.upper(),
                side="sell",
                quantity=quantity,
                error=str(exc),
            )

    async def cancel_all_orders(self) -> int:
        """Cancel all open orders (emergency stop).

        Returns:
            Number of orders cancelled.
        """
        self._ensure_initialized()

        logger.warning("CANCEL ALL ORDERS — emergency stop triggered")

        if self._client is None:
            logger.warning("cancel_all_orders: Alpaca client unavailable")
            return 0

        try:
            await self._rate_limiter.acquire()
            import asyncio
            result = await asyncio.to_thread(self._client.cancel_orders)
            count = len(result) if isinstance(result, list) else 1
            logger.info("cancel_all_orders: cancelled %d orders", count)
            return count
        except Exception:
            logger.exception("cancel_all_orders: failed")
            return 0
