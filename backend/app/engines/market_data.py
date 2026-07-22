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
    # get_quote — uses /v2/aggs/ticker/{symbol}/prev (works on free tier)
    # ------------------------------------------------------------------
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        cache_key = f"polygon:quote:{symbol.upper()}"

        async def _fetch():
            # Polygon free tier does NOT allow /v3/quotes (403).
            # /v2/aggs/ticker/{symbol}/prev returns the previous day's OHLCV
            # bar, which we use as the current price signal.
            resp = await _request_with_backoff(
                self.client, "GET", f"/v2/aggs/ticker/{symbol.upper()}/prev"
            )
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return None
            r = results[0]
            close_price = r.get("c", 0)
            open_price = r.get("o", close_price)
            high_price = r.get("h")
            low_price = r.get("l")
            vol = r.get("v", 0)
            change = close_price - open_price
            change_pct = (change / open_price * 100) if open_price else 0.0
            return Quote(
                symbol=symbol.upper(),
                price=close_price,
                change=round(change, 2),
                change_pct=round(change_pct, 2),
                volume=vol,
                bid=None,
                ask=None,
                high=high_price,
                low=low_price,
                open=open_price,
                prev_close=None,
                timestamp=datetime.fromtimestamp(r["t"] / 1000) if r.get("t") else None,
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
                f"/v2/aggs/ticker/{symbol.upper()}/range/{multiplier}/{timespan}/{start or (datetime.now() - timedelta(days=45)).strftime('%Y-%m-%d')}/{end or datetime.now().strftime('%Y-%m-%d')}",
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
    # get_quote — uses snapshot for real-time price + daily stats
    # ------------------------------------------------------------------
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        cache_key = f"alpaca:quote:{symbol.upper()}"

        async def _fetch():
            # Use snapshot (single-symbol variant) which carries latestTrade,
            # dailyBar, and prevDailyBar — all in one call.
            resp = await _request_with_backoff(
                self.client, "GET", f"/v2/stocks/{symbol.upper()}/snapshot"
            )
            data = resp.json()
            latest = data.get("latestTrade", {})
            daily = data.get("dailyBar", {})
            prev = data.get("prevDailyBar", {})

            price = latest.get("p", 0) or daily.get("c", 0)
            prev_close = prev.get("c", 0)
            change = price - prev_close if prev_close else 0.0
            change_pct = (change / prev_close * 100) if prev_close else 0.0

            return Quote(
                symbol=symbol.upper(),
                price=price,
                change=round(change, 2),
                change_pct=round(change_pct, 2),
                volume=daily.get("v", 0),
                bid=None,
                ask=None,
                high=daily.get("h"),
                low=daily.get("l"),
                open=daily.get("o"),
                prev_close=prev_close,
                timestamp=datetime.fromisoformat(
                    latest["t"].replace("Z", "+00:00")
                ) if latest.get("t") else None,
            )

        result = await _cached_or_fetch(cache_key, TTL_QUOTE, _fetch)
        if result is None:
            return None
        return Quote(**result) if isinstance(result, dict) else result

    # ------------------------------------------------------------------
    # get_bars — uses snapshot dailyBar + prevDailyBar + file cache
    # ------------------------------------------------------------------
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1D",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
    ) -> list[Bar]:
        """Return daily bars for *symbol*.

        Alpaca paper tier only returns 1 bar from /v2/stocks/{symbol}/bars.
        To work around this, we:
        1. Fetch the snapshot (which gives dailyBar + prevDailyBar)
        2. Merge into a file-based bar cache keyed by (symbol, date)
        3. Return up to *limit* cached bars sorted by date.

        Over successive pipeline runs the cache grows to 15+ bars, at which
        point RSI-14 and SMA calculations become meaningful.
        """
        import os as _os

        cache_key = f"alpaca:bars:{symbol.upper()}:{timeframe}:{start}:{end}:{limit}"
        ttl = TTL_BARS_INTRADAY if "min" in timeframe.lower() or "hour" in timeframe.lower() else TTL_BARS_DAILY

        # Cache file path — shared across providers so bars accumulate
        _cache_dir = _os.path.join(_os.path.dirname(__file__), "..", "..", ".cache")
        _os.makedirs(_cache_dir, exist_ok=True)
        _cache_path = _os.path.join(_cache_dir, "alpaca_bars.json")

        async def _fetch():
            sym = symbol.upper()

            # 1. Fetch snapshot to get dailyBar + prevDailyBar (only for 1D)
            bars_by_date: dict[str, dict] = {}
            if timeframe == "1D":
                try:
                    resp = await _request_with_backoff(
                        self.client, "GET", f"/v2/stocks/{sym}/snapshot"
                    )
                    snap = resp.json()
                    daily = snap.get("dailyBar", {})
                    prev = snap.get("prevDailyBar", {})

                    for bar_data in [daily, prev]:
                        t_val = bar_data.get("t")
                        if t_val and bar_data.get("c") is not None:
                            date_str = t_val[:10]  # "2026-07-22"
                            bars_by_date[date_str] = {
                                "o": bar_data["o"],
                                "h": bar_data["h"],
                                "l": bar_data["l"],
                                "c": bar_data["c"],
                                "v": bar_data["v"],
                                "vw": bar_data.get("vw"),
                            }
                except Exception:
                    logger.debug("Snapshot fetch failed for %s — trying bars endpoint", sym)

            # 2. Also try the bars endpoint (gives today's bar if nothing else)
            try:
                resp = await _request_with_backoff(
                    self.client, "GET", f"/v2/stocks/{sym}/bars",
                    params={"timeframe": "1Day", "limit": 1, "adjustment": "all"},
                )
                data = resp.json()
                for r in data.get("bars", []):
                    t_val = r.get("t", "")
                    if t_val:
                        date_str = t_val[:10]
                        if date_str not in bars_by_date:
                            bars_by_date[date_str] = {
                                "o": r["o"], "h": r["h"], "l": r["l"],
                                "c": r["c"], "v": r["v"], "vw": r.get("vw"),
                            }
            except Exception:
                logger.debug("Bars endpoint failed for %s", sym)

            # 3. Load existing cache, merge new bars
            cached: dict[str, dict[str, dict]] = {}
            try:
                if _os.path.exists(_cache_path):
                    with open(_cache_path, "r") as fh:
                        cached = json.load(fh)
            except Exception:
                cached = {}

            if sym not in cached:
                cached[sym] = {}

            for date_str, bar_data in bars_by_date.items():
                cached[sym][date_str] = bar_data

            # Prune: keep only last 100 dates per symbol
            sorted_dates = sorted(cached[sym].keys(), reverse=True)[:100]
            cached[sym] = {d: cached[sym][d] for d in sorted_dates}

            # Persist
            try:
                with open(_cache_path, "w") as fh:
                    json.dump(cached, fh, default=str)
            except Exception:
                pass

            # 4. Return bars sorted ascending, up to *limit*
            all_dates = sorted(cached[sym].keys())[-limit:]
            results: list[dict] = []
            for d in all_dates:
                bd = cached[sym][d]
                results.append(Bar(
                    symbol=sym,
                    timestamp=datetime.fromisoformat(d + "T00:00:00+00:00"),
                    open=bd["o"], high=bd["h"], low=bd["l"],
                    close=bd["c"], volume=int(bd["v"]),
                    vwap=bd.get("vw"),
                ))
            return results

        try:
            # Bypass Redis cache — bars accumulate in the file cache;
            # we always need fresh snapshots to grow the history.
            raw = await _fetch()
        except Exception:
            logger.exception("get_bars failed for %s — returning empty", symbol)
            return []

        if isinstance(raw, list):
            if raw and isinstance(raw[0], dict):
                return [Bar(**b) for b in raw]
            return raw
        return []

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
# Fallback provider — tries primary, falls back to secondary
# ---------------------------------------------------------------------------
class FallbackProvider(MarketDataProvider):
    """Wraps two MarketDataProvider instances.  Every call is forwarded to
    *primary* first; if that raises an exception, *secondary* is tried.
    Useful so the scanner can prefer Alpaca (real-time) but survive an
    Alpaca outage by falling back to Polygon.
    """

    def __init__(self, primary: MarketDataProvider, secondary: MarketDataProvider) -> None:
        self._primary = primary
        self._secondary = secondary

    async def _try(self, method_name: str, *args, **kwargs):
        """Call *method_name* on primary, falling back to secondary on error."""
        for provider, label in [(self._primary, "primary"), (self._secondary, "secondary")]:
            try:
                method = getattr(provider, method_name)
                return await method(*args, **kwargs)
            except Exception:
                logger.warning(
                    "FallbackProvider: %s.%s failed — %s",
                    label, method_name,
                    "trying secondary" if label == "primary" else "giving up",
                    exc_info=(label == "primary"),
                )
                if label == "secondary":
                    raise
        return None  # unreachable

    async def get_quote(self, symbol: str) -> Optional[Quote]:
        return await self._try("get_quote", symbol)

    async def get_bars(self, symbol: str, timeframe: str = "1D",
                       start: Optional[str] = None, end: Optional[str] = None,
                       limit: int = 100) -> list[Bar]:
        return await self._try("get_bars", symbol, timeframe, start, end, limit)

    async def get_top_gainers(self, limit: int = 10) -> list[GainersLosersItem]:
        return await self._try("get_top_gainers", limit)

    async def get_top_losers(self, limit: int = 10) -> list[GainersLosersItem]:
        return await self._try("get_top_losers", limit)

    async def get_volume_spikes(self, min_rvol: float = 2.0, limit: int = 20) -> list[VolumeSpikeItem]:
        return await self._try("get_volume_spikes", min_rvol, limit)

    async def get_unusual_options_activity(self, symbol: str, limit: int = 20) -> list[UnusualOptionsItem]:
        return await self._try("get_unusual_options_activity", symbol, limit)

    async def get_fundamentals(self, symbol: str) -> Optional[Fundamentals]:
        return await self._try("get_fundamentals", symbol)

    async def get_news(self, symbol: str, limit: int = 10) -> list[NewsItem]:
        return await self._try("get_news", symbol, limit)


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
