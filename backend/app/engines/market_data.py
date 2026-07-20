"""
Market data provider — abstract interface and concrete implementations.

Supports:
- Polygon.io  (primary — REST API)
- Alpaca Markets (secondary — paper & live trading)

All HTTP calls use httpx.AsyncClient with exponential backoff for rate limits.
Responses are cached in Redis with configurable TTLs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.redis import get_redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache TTLs (seconds)
# ---------------------------------------------------------------------------
TTL_QUOTE = 30
TTL_FUNDAMENTALS = 3600  # 1 hour
TTL_NEWS = 300  # 5 minutes
TTL_GAINERS_LOSERS = 60
TTL_VOLUME_SPIKES = 60
TTL_UNUSUAL_OPTIONS = 120
TTL_BARS_DAILY = 300
TTL_BARS_INTRADAY = 60

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------
_MAX_RETRIES = 4
_BASE_DELAY = 1.0  # seconds


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class Quote:
    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int
    bid: Optional[float] = None
    ask: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    prev_close: Optional[float] = None
    timestamp: Optional[datetime] = None


@dataclass
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None


@dataclass
class Fundamentals:
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    avg_volume: Optional[int] = None
    description: Optional[str] = None


@dataclass
class NewsItem:
    symbol: str
    title: str
    source: str
    url: str
    published_at: datetime
    summary: Optional[str] = None
    sentiment: Optional[str] = None  # positive / negative / neutral


@dataclass
class GainersLosersItem:
    symbol: str
    price: float
    change_pct: float
    volume: int


@dataclass
class VolumeSpikeItem:
    symbol: str
    price: float
    volume: int
    avg_volume: int
    relative_volume: float


@dataclass
class UnusualOptionsItem:
    symbol: str
    contract_type: str  # call / put
    strike: float
    expiry: str
    volume: int
    open_interest: int
    premium: Optional[float] = None
    trade_type: Optional[str] = None  # sweep / block / split


@dataclass
class ScanResult:
    symbol: str
    price: float
    change_pct: float
    volume: int
    relative_volume: float
    rsi_14: Optional[float] = None
    above_sma_50: Optional[bool] = None
    above_sma_200: Optional[bool] = None
    score: float = 0.0


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------
class MarketDataProvider(ABC):
    """Interface that all market-data backends must implement."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        ...

    @abstractmethod
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1D",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
    ) -> list[Bar]:
        ...

    @abstractmethod
    async def get_top_gainers(self, limit: int = 10) -> list[GainersLosersItem]:
        ...

    @abstractmethod
    async def get_top_losers(self, limit: int = 10) -> list[GainersLosersItem]:
        ...

    @abstractmethod
    async def get_volume_spikes(
        self, min_rvol: float = 2.0, limit: int = 20
    ) -> list[VolumeSpikeItem]:
        ...

    @abstractmethod
    async def get_unusual_options_activity(
        self, symbol: str, limit: int = 20
    ) -> list[UnusualOptionsItem]:
        ...

    @abstractmethod
    async def get_fundamentals(self, symbol: str) -> Optional[Fundamentals]:
        ...

    @abstractmethod
    async def get_news(
        self, symbol: str, limit: int = 10
    ) -> list[NewsItem]:
        ...


# ---------------------------------------------------------------------------
# Helpers for HTTP + caching
# ---------------------------------------------------------------------------
async def _cached_or_fetch(
    cache_key: str,
    ttl: int,
    fetch_fn,
) -> Any:
    """Return cached value if fresh; otherwise call *fetch_fn* and cache."""
    try:
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached is not None:
            return json.loads(cached)
    except Exception:
        logger.debug("Redis unavailable — skipping cache read", exc_info=True)

    result = await fetch_fn()

    try:
        redis = await get_redis()
        await redis.setex(cache_key, ttl, json.dumps(result, default=str))
    except Exception:
        logger.debug("Redis unavailable — skipping cache write", exc_info=True)

    return result


async def _request_with_backoff(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    """Perform an HTTP request with exponential backoff on 429 / 5xx."""
    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else _BASE_DELAY * (2**attempt)
                logger.warning("Rate-limited on %s — retrying in %.1fs (attempt %d/%d)",
                               url, delay, attempt + 1, _MAX_RETRIES)
                await asyncio.sleep(delay)
                continue
            if resp.status_code >= 500:
                delay = _BASE_DELAY * (2**attempt)
                logger.warning("Server error %d on %s — retrying in %.1fs (attempt %d/%d)",
                               resp.status_code, url, delay, attempt + 1, _MAX_RETRIES)
                await asyncio.sleep(delay)
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500 and exc.response.status_code != 429:
                raise
            last_exc = exc
        except (httpx.RequestError, asyncio.TimeoutError) as exc:
            last_exc = exc
            delay = _BASE_DELAY * (2**attempt)
            logger.warning("Request error on %s — retrying in %.1fs (attempt %d/%d): %s",
                           url, delay, attempt + 1, _MAX_RETRIES, exc)
            await asyncio.sleep(delay)

    raise last_exc or RuntimeError(f"Exhausted retries for {url}")


# ---------------------------------------------------------------------------
# Polygon.io provider
# ---------------------------------------------------------------------------
class PolygonProvider(MarketDataProvider):
    """Market data via Polygon.io REST API (free-tier compatible)."""

    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.POLYGON_API_KEY
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=httpx.Timeout(15.0),
                params={"apiKey": self._api_key},
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # get_quote
    # ------------------------------------------------------------------
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        cache_key = f"polygon:quote:{symbol.upper()}"

        async def _fetch():
            resp = await _request_with_backoff(
                self.client, "GET", f"/v3/quotes/{symbol.upper()}"
            )
            data = resp.json()
            if data.get("status") != "OK" or not data.get("results"):
                return None
            r = data["results"][0]
            return Quote(
                symbol=symbol.upper(),
                price=r.get("ap") or r.get("bp") or 0,
                change=0.0,
                change_pct=0.0,
                volume=r.get("s", 0),
                bid=r.get("bp"),
                ask=r.get("ap"),
                timestamp=datetime.fromtimestamp(r["t"] / 1e9) if r.get("t") else None,
            )

        result = await _cached_or_fetch(cache_key, TTL_QUOTE, _fetch)
        if result is None:
            return None
        return Quote(**result) if isinstance(result, dict) else result

    # ------------------------------------------------------------------
    # get_bars
    # ------------------------------------------------------------------
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1D",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
    ) -> list[Bar]:
        cache_key = f"polygon:bars:{symbol.upper()}:{timeframe}:{start}:{end}:{limit}"
        ttl = TTL_BARS_INTRADAY if "min" in timeframe.lower() or "hour" in timeframe.lower() else TTL_BARS_DAILY

        async def _fetch():
            # Polygon uses multiplier + timespan (e.g. 1/day)
            if timeframe == "1D":
                multiplier, timespan = 1, "day"
            elif timeframe == "1H":
                multiplier, timespan = 1, "hour"
            elif timeframe == "15min":
                multiplier, timespan = 15, "minute"
            elif "min" in timeframe:
                multiplier = int(timeframe.replace("min", ""))
                timespan = "minute"
            elif "H" in timeframe:
                multiplier = int(timeframe.replace("H", ""))
                timespan = "hour"
            else:
                multiplier, timespan = 1, "day"

            params = {"adjusted": "true", "limit": limit}
            if start:
                params["from"] = start
            if end:
                params["to"] = end

            resp = await _request_with_backoff(
                self.client, "GET",
                f"/v2/aggs/ticker/{symbol.upper()}/range/{multiplier}/{timespan}/{start or '2024-01-01'}/{end or datetime.now().strftime('%Y-%m-%d')}",
                params=params,
            )
            data = resp.json()
            results: list[Bar] = []
            for r in data.get("results", []):
                results.append(Bar(
                    symbol=symbol.upper(),
                    timestamp=datetime.fromtimestamp(r["t"] / 1000),
                    open=r["o"],
                    high=r["h"],
                    low=r["l"],
                    close=r["c"],
                    volume=r["v"],
                    vwap=r.get("vw"),
                ))
            return results

        raw = await _cached_or_fetch(cache_key, ttl, _fetch)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [Bar(**b) for b in raw]
        return raw

    # ------------------------------------------------------------------
    # get_top_gainers / get_top_losers
    # ------------------------------------------------------------------
    async def get_top_gainers(self, limit: int = 10) -> list[GainersLosersItem]:
        cache_key = f"polygon:gainers:{limit}"

        async def _fetch():
            resp = await _request_with_backoff(
                self.client, "GET", "/v2/snapshot/locale/us/markets/stocks/gainers",
                params={"include_otc": "false"},
            )
            data = resp.json()
            results: list[dict] = []
            for ticker_data in data.get("tickers", [])[:limit]:
                day = ticker_data.get("day", {})
                results.append(GainersLosersItem(
                    symbol=ticker_data["ticker"],
                    price=day.get("c", 0),
                    change_pct=day.get("c", 0),
                    volume=day.get("v", 0),
                ))
            return results

        raw = await _cached_or_fetch(cache_key, TTL_GAINERS_LOSERS, _fetch)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [GainersLosersItem(**it) for it in raw]
        return raw

    async def get_top_losers(self, limit: int = 10) -> list[GainersLosersItem]:
        cache_key = f"polygon:losers:{limit}"

        async def _fetch():
            resp = await _request_with_backoff(
                self.client, "GET", "/v2/snapshot/locale/us/markets/stocks/losers",
                params={"include_otc": "false"},
            )
            data = resp.json()
            results: list[dict] = []
            for ticker_data in data.get("tickers", [])[:limit]:
                day = ticker_data.get("day", {})
                results.append(GainersLosersItem(
                    symbol=ticker_data["ticker"],
                    price=day.get("c", 0),
                    change_pct=day.get("c", 0),
                    volume=day.get("v", 0),
                ))
            return results

        raw = await _cached_or_fetch(cache_key, TTL_GAINERS_LOSERS, _fetch)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [GainersLosersItem(**it) for it in raw]
        return raw

    # ------------------------------------------------------------------
    # get_volume_spikes
    # ------------------------------------------------------------------
    async def get_volume_spikes(
        self, min_rvol: float = 2.0, limit: int = 20
    ) -> list[VolumeSpikeItem]:
        cache_key = f"polygon:volspikes:{min_rvol}:{limit}"

        async def _fetch():
            # Use Polygon's gainers endpoint as a proxy — stocks with large
            # moves typically have volume spikes.  Then filter by relative volume.
            resp = await _request_with_backoff(
                self.client, "GET", "/v2/snapshot/locale/us/markets/stocks/gainers",
                params={"include_otc": "false"},
            )
            data = resp.json()
            results: list[dict] = []
            for ticker_data in data.get("tickers", []):
                day = ticker_data.get("day", {})
                prev_day = ticker_data.get("prevDay", {})
                avg_vol = prev_day.get("v", 0)
                vol = day.get("v", 0)
                rvol = (vol / avg_vol) if avg_vol and avg_vol > 0 else 0.0
                if rvol >= min_rvol:
                    results.append({
                        "symbol": ticker_data["ticker"],
                        "price": day.get("c", 0),
                        "volume": vol,
                        "avg_volume": avg_vol,
                        "relative_volume": round(rvol, 2),
                    })
            results.sort(key=lambda x: x["relative_volume"], reverse=True)
            return results[:limit]

        raw = await _cached_or_fetch(cache_key, TTL_VOLUME_SPIKES, _fetch)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [VolumeSpikeItem(**it) for it in raw]
        return raw

    # ------------------------------------------------------------------
    # get_unusual_options_activity
    # ------------------------------------------------------------------
    async def get_unusual_options_activity(
        self, symbol: str, limit: int = 20
    ) -> list[UnusualOptionsItem]:
        cache_key = f"polygon:options:{symbol.upper()}:{limit}"

        async def _fetch():
            # Polygon snapshot — options chain for a single ticker
            resp = await _request_with_backoff(
                self.client, "GET",
                f"/v3/snapshot/options/{symbol.upper()}",
            )
            data = resp.json()
            results: list[dict] = []
            for item in data.get("results", []):
                details = item.get("details", {})
                results.append(UnusualOptionsItem(
                    symbol=symbol.upper(),
                    contract_type=details.get("contract_type", "call"),
                    strike=details.get("strike_price", 0),
                    expiry=details.get("expiration_date", ""),
                    volume=details.get("volume", 0),
                    open_interest=details.get("open_interest", 0),
                    premium=details.get("day", {}).get("c"),
                    trade_type=item.get("type"),
                ))
            # Sort by volume descending and return top N
            results.sort(key=lambda x: x.volume, reverse=True)
            return results[:limit]

        raw = await _cached_or_fetch(cache_key, TTL_UNUSUAL_OPTIONS, _fetch)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [UnusualOptionsItem(**it) for it in raw]
        return raw

    # ------------------------------------------------------------------
    # get_fundamentals
    # ------------------------------------------------------------------
    async def get_fundamentals(self, symbol: str) -> Optional[Fundamentals]:
        cache_key = f"polygon:fundamentals:{symbol.upper()}"

        async def _fetch():
            resp = await _request_with_backoff(
                self.client, "GET", f"/v3/reference/tickers/{symbol.upper()}"
            )
            data = resp.json()
            result = data.get("results", {})
            if not result:
                return None
            return Fundamentals(
                symbol=symbol.upper(),
                name=result.get("name"),
                sector=result.get("sic_description"),
                industry=result.get("sic_description"),
                market_cap=result.get("market_cap"),
                description=result.get("description"),
            )

        raw = await _cached_or_fetch(cache_key, TTL_FUNDAMENTALS, _fetch)
        if raw is None:
            return None
        if isinstance(raw, dict):
            return Fundamentals(**raw) if raw else None
        return raw

    # ------------------------------------------------------------------
    # get_news
    # ------------------------------------------------------------------
    async def get_news(
        self, symbol: str, limit: int = 10
    ) -> list[NewsItem]:
        cache_key = f"polygon:news:{symbol.upper()}:{limit}"

        async def _fetch():
            resp = await _request_with_backoff(
                self.client, "GET", "/v2/reference/news",
                params={"ticker": symbol.upper(), "limit": limit, "order": "desc"},
            )
            data = resp.json()
            results: list[dict] = []
            for r in data.get("results", []):
                results.append(NewsItem(
                    symbol=symbol.upper(),
                    title=r.get("title", ""),
                    source=r.get("publisher", {}).get("name", "Unknown"),
                    url=r.get("article_url", ""),
                    published_at=datetime.fromisoformat(
                        r.get("published_utc", "").replace("Z", "+00:00")
                    ),
                    summary=r.get("description"),
                    sentiment=_classify_sentiment(r.get("title", "")),
                ))
            return results

        raw = await _cached_or_fetch(cache_key, TTL_NEWS, _fetch)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [NewsItem(**it) for it in raw]
        return raw


def _classify_sentiment(text: str) -> str:
    """Naive keyword-based sentiment classifier for news headlines."""
    pos_words = {"up", "rise", "gain", "beat", "strong", "bull", "growth", "positive",
                  "record", "surge", "rally", "wins", "higher", "boost"}
    neg_words = {"down", "drop", "fall", "miss", "weak", "bear", "decline", "negative",
                  "crash", "plunge", "sell", "loss", "lower", "cut", "warn", "risk"}
    text_lower = text.lower()
    pos_count = sum(1 for w in pos_words if w in text_lower)
    neg_count = sum(1 for w in neg_words if w in text_lower)
    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"


# ---------------------------------------------------------------------------
# Alpaca provider
# ---------------------------------------------------------------------------
class AlpacaProvider(MarketDataProvider):
    """Market data via Alpaca Markets API (paper / live)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        data_url: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.ALPACA_API_KEY
        self._secret_key = secret_key or settings.ALPACA_SECRET_KEY
        self._base_url = base_url or settings.ALPACA_BASE_URL
        self._data_url = data_url or settings.ALPACA_DATA_URL
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._data_url,
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
    # get_quote
    # ------------------------------------------------------------------
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        cache_key = f"alpaca:quote:{symbol.upper()}"

        async def _fetch():
            resp = await _request_with_backoff(
                self.client, "GET", f"/v2/stocks/{symbol.upper()}/quotes/latest"
            )
            data = resp.json()
            quote_data = data.get("quote", {})
            if not quote_data:
                return None
            return Quote(
                symbol=symbol.upper(),
                price=(quote_data.get("ap", 0) + quote_data.get("bp", 0)) / 2 or quote_data.get("ap") or quote_data.get("bp") or 0,
                change=0.0,
                change_pct=0.0,
                volume=0,
                bid=quote_data.get("bp"),
                ask=quote_data.get("ap"),
                timestamp=datetime.fromisoformat(
                    quote_data["t"].replace("Z", "+00:00")
                ) if quote_data.get("t") else None,
            )

        result = await _cached_or_fetch(cache_key, TTL_QUOTE, _fetch)
        if result is None:
            return None
        return Quote(**result) if isinstance(result, dict) else result

    # ------------------------------------------------------------------
    # get_bars
    # ------------------------------------------------------------------
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1D",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
    ) -> list[Bar]:
        cache_key = f"alpaca:bars:{symbol.upper()}:{timeframe}:{start}:{end}:{limit}"
        ttl = TTL_BARS_INTRADAY if "min" in timeframe.lower() or "hour" in timeframe.lower() else TTL_BARS_DAILY

        # Alpaca uses different timeframe format
        alpaca_tf = timeframe.replace("min", "Min").replace("H", "Hour").replace("D", "Day")
        if not alpaca_tf.endswith(("Min", "Hour", "Day")):
            alpaca_tf = "1Day"

        async def _fetch():
            params: dict[str, Any] = {
                "timeframe": alpaca_tf,
                "limit": min(limit, 1000),
                "adjustment": "all",
            }
            if start:
                params["start"] = start
            if end:
                params["end"] = end

            resp = await _request_with_backoff(
                self.client, "GET",
                f"/v2/stocks/{symbol.upper()}/bars",
                params=params,
            )
            data = resp.json()
            results: list[Bar] = []
            for r in data.get("bars", []):
                results.append(Bar(
                    symbol=symbol.upper(),
                    timestamp=datetime.fromisoformat(r["t"].replace("Z", "+00:00")),
                    open=r["o"],
                    high=r["h"],
                    low=r["l"],
                    close=r["c"],
                    volume=r["v"],
                    vwap=r.get("vw"),
                ))
            return results

        raw = await _cached_or_fetch(cache_key, ttl, _fetch)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [Bar(**b) for b in raw]
        return raw

    # ------------------------------------------------------------------
    # get_top_gainers
    # ------------------------------------------------------------------
    async def get_top_gainers(self, limit: int = 10) -> list[GainersLosersItem]:
        cache_key = f"alpaca:gainers:{limit}"

        async def _fetch():
            # Alpaca doesn't have a native gainers endpoint, so we
            # snapshot a list of major tickers and compute locally.
            resp = await _request_with_backoff(
                self.client, "GET", "/v2/stocks/snapshots",
                params={"symbols": ",".join(_get_watchlist_symbols())},
            )
            data = resp.json()
            items: list[dict] = []
            for sym, snap in data.items():
                bar = snap.get("latestTrade", {})
                prev = snap.get("prevDailyBar", {})
                prev_close = prev.get("c", 0)
                price = bar.get("p", 0)
                change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
                items.append({
                    "symbol": sym,
                    "price": price,
                    "change_pct": round(change_pct, 2),
                    "volume": snap.get("dailyBar", {}).get("v", 0),
                })
            items.sort(key=lambda x: x["change_pct"], reverse=True)
            return items[:limit]

        raw = await _cached_or_fetch(cache_key, TTL_GAINERS_LOSERS, _fetch)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [GainersLosersItem(**it) for it in raw]
        return raw

    # ------------------------------------------------------------------
    # get_top_losers
    # ------------------------------------------------------------------
    async def get_top_losers(self, limit: int = 10) -> list[GainersLosersItem]:
        cache_key = f"alpaca:losers:{limit}"

        async def _fetch():
            resp = await _request_with_backoff(
                self.client, "GET", "/v2/stocks/snapshots",
                params={"symbols": ",".join(_get_watchlist_symbols())},
            )
            data = resp.json()
            items: list[dict] = []
            for sym, snap in data.items():
                bar = snap.get("latestTrade", {})
                prev = snap.get("prevDailyBar", {})
                prev_close = prev.get("c", 0)
                price = bar.get("p", 0)
                change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
                items.append({
                    "symbol": sym,
                    "price": price,
                    "change_pct": round(change_pct, 2),
                    "volume": snap.get("dailyBar", {}).get("v", 0),
                })
            items.sort(key=lambda x: x["change_pct"])
            return items[:limit]

        raw = await _cached_or_fetch(cache_key, TTL_GAINERS_LOSERS, _fetch)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [GainersLosersItem(**it) for it in raw]
        return raw

    # ------------------------------------------------------------------
    # get_volume_spikes
    # ------------------------------------------------------------------
    async def get_volume_spikes(
        self, min_rvol: float = 2.0, limit: int = 20
    ) -> list[VolumeSpikeItem]:
        cache_key = f"alpaca:volspikes:{min_rvol}:{limit}"

        async def _fetch():
            symbols = _get_watchlist_symbols()
            resp = await _request_with_backoff(
                self.client, "GET", "/v2/stocks/snapshots",
                params={"symbols": ",".join(symbols)},
            )
            data = resp.json()
            results: list[dict] = []
            for sym, snap in data.items():
                daily = snap.get("dailyBar", {})
                prev = snap.get("prevDailyBar", {})
                vol = daily.get("v", 0)
                avg_vol = prev.get("v", 0)
                rvol = (vol / avg_vol) if avg_vol and avg_vol > 0 else 0.0
                if rvol >= min_rvol:
                    results.append({
                        "symbol": sym,
                        "price": snap.get("latestTrade", {}).get("p", 0),
                        "volume": vol,
                        "avg_volume": avg_vol,
                        "relative_volume": round(rvol, 2),
                    })
            results.sort(key=lambda x: x["relative_volume"], reverse=True)
            return results[:limit]

        raw = await _cached_or_fetch(cache_key, TTL_VOLUME_SPIKES, _fetch)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [VolumeSpikeItem(**it) for it in raw]
        return raw

    # ------------------------------------------------------------------
    # get_unusual_options_activity
    # ------------------------------------------------------------------
    async def get_unusual_options_activity(
        self, symbol: str, limit: int = 20
    ) -> list[UnusualOptionsItem]:
        # Alpaca does not provide options data through the standard paper API.
        # Return empty list gracefully.
        logger.debug("AlpacaProvider.get_unusual_options_activity is not supported — returning []")
        return []

    # ------------------------------------------------------------------
    # get_fundamentals
    # ------------------------------------------------------------------
    async def get_fundamentals(self, symbol: str) -> Optional[Fundamentals]:
        cache_key = f"alpaca:fundamentals:{symbol.upper()}"

        async def _fetch():
            # Alpaca doesn't expose fundamentals via v2 REST.  Return basic
            # info from the asset endpoint as a fallback.
            try:
                resp = await _request_with_backoff(
                    self.client, "GET", f"/v2/assets/{symbol.upper()}"
                )
                data = resp.json()
                return Fundamentals(
                    symbol=symbol.upper(),
                    name=data.get("name"),
                    sector=None,
                    industry=None,
                    market_cap=None,
                )
            except httpx.HTTPStatusError:
                return None

        raw = await _cached_or_fetch(cache_key, TTL_FUNDAMENTALS, _fetch)
        if raw is None:
            return None
        if isinstance(raw, dict):
            return Fundamentals(**raw) if raw else None
        return raw

    # ------------------------------------------------------------------
    # get_news
    # ------------------------------------------------------------------
    async def get_news(
        self, symbol: str, limit: int = 10
    ) -> list[NewsItem]:
        # Alpaca v2 REST does not have a news endpoint.  Return empty list.
        logger.debug("AlpacaProvider.get_news is not supported — returning []")
        return []


# ---------------------------------------------------------------------------
# Symbol lists
# ---------------------------------------------------------------------------
def _get_watchlist_symbols() -> list[str]:
    """Hardcoded MVP symbol list (S&P 500 top + semis)."""
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JPM",
        "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD", "BAC", "DIS", "NFLX", "ADBE",
        "CRM", "INTC", "AMD", "QCOM", "AVGO", "TXN", "MU", "AMAT", "LRCX", "ADI",
        "SNPS", "CDNS", "MRVL", "KLAC", "ASML",
    ]
