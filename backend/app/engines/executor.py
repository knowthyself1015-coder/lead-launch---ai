"""
Trade Executor — executes trades via Alpaca Markets.

Supports paper and live trading.  All orders are placed through the
Alpaca Trading API v2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AccountInfo:
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    status: str


@dataclass
class ExecutionResult:
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Alpaca Executor
# ---------------------------------------------------------------------------

class AlpacaExecutor:
    """Execute trades via Alpaca Markets trading API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.ALPACA_API_KEY
        self._secret_key = secret_key or settings.ALPACA_SECRET_KEY
        self._base_url = base_url or settings.ALPACA_BASE_URL
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(15.0),
                headers={
                    "APCA-API-KEY-ID": self._api_key,
                    "APCA-API-SECRET-KEY": self._secret_key,
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    async def get_account(self) -> AccountInfo:
        """Fetch account information from Alpaca."""
        if not self._api_key or not self._secret_key:
            logger.warning("Alpaca credentials not set — returning paper default account")
            return AccountInfo(
                equity=100_000.0,
                cash=100_000.0,
                buying_power=200_000.0,
                portfolio_value=100_000.0,
                status="ACTIVE",
            )

        try:
            resp = await self.client.get("/v2/account")
            resp.raise_for_status()
            data = resp.json()
            return AccountInfo(
                equity=float(data.get("equity", 100_000)),
                cash=float(data.get("cash", 100_000)),
                buying_power=float(data.get("buying_power", 200_000)),
                portfolio_value=float(data.get("portfolio_value", 100_000)),
                status=data.get("status", "ACTIVE"),
            )
        except Exception:
            logger.exception("Failed to fetch Alpaca account — returning default")
            return AccountInfo(
                equity=100_000.0,
                cash=100_000.0,
                buying_power=200_000.0,
                portfolio_value=100_000.0,
                status="ACTIVE",
            )

    # ------------------------------------------------------------------
    # Order execution
    # ------------------------------------------------------------------

    async def execute_buy(
        self,
        ticker: str,
        quantity: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> ExecutionResult:
        """Place a buy order via Alpaca."""
        if not self._api_key or not self._secret_key:
            logger.info(
                "PAPER BUY: %s x%d @ market (stop=%.2f, target=%.2f)",
                ticker, quantity, stop_loss or 0, take_profit or 0,
            )
            return ExecutionResult(success=True, order_id=f"paper-{ticker}-buy")

        try:
            payload = {
                "symbol": ticker.upper(),
                "qty": str(quantity),
                "side": "buy",
                "type": "market",
                "time_in_force": "day",
            }
            if stop_loss is not None:
                payload["order_class"] = "bracket"
                payload["stop_loss"] = {"stop_price": str(round(stop_loss, 2))}
            if take_profit is not None:
                payload.setdefault("order_class", "bracket")
                payload["take_profit"] = {"limit_price": str(round(take_profit, 2))}

            resp = await self.client.post("/v2/orders", json=payload)
            resp.raise_for_status()
            data = resp.json()
            order_id = data.get("id", "unknown")
            logger.info("BUY order placed: %s x%d — order_id=%s", ticker, quantity, order_id)
            return ExecutionResult(success=True, order_id=order_id)
        except Exception as exc:
            logger.exception("BUY order failed for %s", ticker)
            return ExecutionResult(success=False, error=str(exc))

    async def execute_sell(
        self,
        ticker: str,
        quantity: int,
    ) -> ExecutionResult:
        """Place a sell order via Alpaca."""
        if not self._api_key or not self._secret_key:
            logger.info("PAPER SELL: %s x%d @ market", ticker, quantity)
            return ExecutionResult(success=True, order_id=f"paper-{ticker}-sell")

        try:
            payload = {
                "symbol": ticker.upper(),
                "qty": str(quantity),
                "side": "sell",
                "type": "market",
                "time_in_force": "day",
            }
            resp = await self.client.post("/v2/orders", json=payload)
            resp.raise_for_status()
            data = resp.json()
            order_id = data.get("id", "unknown")
            logger.info("SELL order placed: %s x%d — order_id=%s", ticker, quantity, order_id)
            return ExecutionResult(success=True, order_id=order_id)
        except Exception as exc:
            logger.exception("SELL order failed for %s", ticker)
            return ExecutionResult(success=False, error=str(exc))
