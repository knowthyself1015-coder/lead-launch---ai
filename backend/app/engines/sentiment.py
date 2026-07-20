"""
Sentiment engine — AI-powered news sentiment analysis.

Responsible for:
- Fetching news articles for a given ticker via the market data provider
- Scoring each article across five dimensions (earnings, growth, competitive,
  regulatory, market_sentiment)
- Aggregating scores into a weighted composite per symbol
- Using an LLM (OpenAI) for summary and key-points generation when configured,
  falling back to a rule-based summary otherwise
- Supporting concurrent batch analysis and broad market sentiment
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.config import get_settings
from app.engines.market_data import MarketDataProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class NewsItem(BaseModel):
    """A single news article fetched by the market-data provider."""
    source: str
    title: str
    url: str
    published_at: str  # ISO-format string
    content: str = ""
    symbols: list[str] = Field(default_factory=list)


class SentimentResult(BaseModel):
    """Aggregated sentiment for one symbol."""
    symbol: str
    overall_sentiment: str  # "BULLISH" | "NEUTRAL" | "BEARISH"
    confidence_score: float  # 0.0 – 1.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Scoring dimensions & weights
# ---------------------------------------------------------------------------

SCORING_DIMENSIONS = {
    "earnings_impact":      0.25,
    "growth_outlook":       0.25,
    "competitive_position": 0.15,
    "regulatory_risk":      0.15,
    "market_sentiment":     0.20,
}

# Keyword sets for each dimension
_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "earnings_impact": {
        "bullish": [
            "beat", "revenue growth", "earnings surprise", "raised guidance",
            "strong quarter", "record revenue", "profit", "eps beat",
            "margin expansion", "outperform", "above estimates",
        ],
        "bearish": [
            "miss", "earnings miss", "revenue decline", "lowered guidance",
            "weak quarter", "loss", "eps miss", "margin contraction",
            "below estimates", "disappointing results", "write-down",
        ],
    },
    "growth_outlook": {
        "bullish": [
            "expansion", "new market", "product launch", "innovation",
            "partnership", "acquisition", "growth", "accelerating",
            "pipeline", "demand", "tailwind", "catalyst",
        ],
        "bearish": [
            "slowdown", "declining", "mature market", "saturation",
            "headwind", "uncertainty", "delay", "cancellation",
            "layoffs", "restructuring", "divestiture",
        ],
    },
    "competitive_position": {
        "bullish": [
            "market leader", "moat", "market share gain", "competitive advantage",
            "differentiation", "patent", "barrier to entry", "brand strength",
        ],
        "bearish": [
            "competition", "market share loss", "disruption", "commoditization",
            "pricing pressure", "substitute", "copycat", "lost contract",
        ],
    },
    "regulatory_risk": {
        "bullish": [
            "approval", "fda", "clearance", "deregulation", "favorable ruling",
            "compliance", "certified", "license granted",
        ],
        "bearish": [
            "lawsuit", "investigation", "fine", "sanction", "regulation",
            "antitrust", "ban", "probe", "sec", "doj", "ftc",
            "regulatory", "compliance failure", "penalty",
        ],
    },
    "market_sentiment": {
        "bullish": [
            "upgrade", "buy rating", "overweight", "price target raised",
            "bullish", "accumulate", "outperform", "positive outlook",
            "strong buy", "analyst bullish",
        ],
        "bearish": [
            "downgrade", "sell rating", "underweight", "price target cut",
            "bearish", "reduce", "underperform", "negative outlook",
            "strong sell", "analyst bearish",
        ],
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dimension_score(text: str, dimension: str) -> float:
    """Score a single article along one dimension in [-1.0, 1.0]."""
    kw = _KEYWORDS.get(dimension, {})
    text_lower = text.lower()
    bullish_hits = sum(1 for w in kw.get("bullish", []) if w.lower() in text_lower)
    bearish_hits = sum(1 for w in kw.get("bearish", []) if w.lower() in text_lower)
    total = bullish_hits + bearish_hits
    if total == 0:
        return 0.0
    # Raw diff mapped into [-1, 1] range, capped
    raw = (bullish_hits - bearish_hits) / total
    return max(-1.0, min(1.0, raw))


def _score_article(title: str, content: str) -> dict[str, float]:
    """Return dimension scores for a single article."""
    combined = f"{title}\n{content}"
    return {dim: _dimension_score(combined, dim) for dim in SCORING_DIMENSIONS}


def _aggregate_scores(
    article_scores: list[dict[str, float]],
) -> tuple[dict[str, float], float]:
    """Weighted-average article scores into a composite per dimension and overall."""
    if not article_scores:
        return {}, 0.0

    aggregated: dict[str, float] = {}
    for dim in SCORING_DIMENSIONS:
        vals = [s[dim] for s in article_scores]
        aggregated[dim] = sum(vals) / len(vals)

    # Weighted composite
    composite = sum(
        aggregated[dim] * weight for dim, weight in SCORING_DIMENSIONS.items()
    )
    return aggregated, composite


def _composite_to_sentiment(score: float, threshold: float) -> str:
    if score >= threshold:
        return "BULLISH"
    elif score <= -threshold:
        return "BEARISH"
    return "NEUTRAL"


def _build_fallback_summary(
    symbol: str,
    sentiment: str,
    breakdown: dict[str, float],
    article_count: int,
) -> tuple[str, list[str]]:
    """Generate a rule-based summary when no LLM is available."""
    key_points: list[str] = []

    for dim, score in sorted(breakdown.items(), key=lambda x: abs(x[1]), reverse=True):
        label = dim.replace("_", " ").title()
        if score > 0.3:
            key_points.append(f"{label}: positive ({score:+.2f})")
        elif score < -0.3:
            key_points.append(f"{label}: negative ({score:+.2f})")

    if not key_points:
        key_points.append("No strong signals detected")

    summary = (
        f"{symbol} sentiment is {sentiment} based on {article_count} articles. "
        f"Key factors: {'; '.join(key_points[:3])}."
    )
    return summary, key_points[:5]


# ---------------------------------------------------------------------------
# LLM integration
# ---------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """You are an expert financial analyst with decades of experience in equity research.
Your task is to analyze a set of news headlines and article excerpts for a given stock ticker.

**Instructions:**
1. Review the provided headlines and excerpts carefully.
2. Identify the most important bullish and bearish signals.
3. Determine an overall sentiment: "BULLISH", "NEUTRAL", or "BEARISH".
4. Assign a confidence score from 0 to 100 based on the clarity and consistency of the signals.
5. Write a 1-2 sentence summary capturing the key takeaway for an investor.
6. List 3-5 key points (each a single sentence) that support your assessment.

**Output format — return ONLY a valid JSON object (no markdown, no extra text):**
{
  "sentiment": "BULLISH" | "NEUTRAL" | "BEARISH",
  "confidence": <integer 0-100>,
  "summary": "<1-2 sentence summary>",
  "key_points": ["<point 1>", "<point 2>", ...]
}
"""


async def _llm_analyze(
    symbol: str,
    headlines: list[str],
    excerpts: list[str],
) -> Optional[dict[str, Any]]:
    """Call OpenAI to generate a structured sentiment analysis.

    Returns the parsed JSON dict on success, or None if the call fails
    or no API key is configured.
    """
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return None

    # Build the user prompt
    joined_headlines = "\n".join(f"- {h}" for h in headlines[:20])
    joined_excerpts = "\n---\n".join(e for e in excerpts[:10] if e)

    user_prompt = (
        f"**Ticker:** {symbol}\n\n"
        f"**Headlines:**\n{joined_headlines}\n\n"
        f"**Article Excerpts:**\n{joined_excerpts or '(none available)'}"
    )

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        if not raw:
            logger.warning("LLM returned empty response for %s", symbol)
            return None

        parsed = json.loads(raw)

        # Validate required fields
        sentiment = parsed.get("sentiment", "NEUTRAL").upper()
        if sentiment not in ("BULLISH", "NEUTRAL", "BEARISH"):
            sentiment = "NEUTRAL"
        confidence = max(0, min(100, int(parsed.get("confidence", 50))))
        summary = str(parsed.get("summary", ""))
        key_points = [
            str(p) for p in parsed.get("key_points", []) if isinstance(p, str)
        ]

        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "summary": summary,
            "key_points": key_points,
        }

    except Exception:
        logger.exception("LLM sentiment analysis failed for %s", symbol)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_news(
    symbol: str,
    provider: MarketDataProvider,
    *,
    limit: int = 10,
) -> SentimentResult:
    """Analyse news sentiment for a single symbol.

    1. Fetch news articles from the market data provider.
    2. Score each article on five dimensions.
    3. Aggregate into a weighted composite.
    4. If an OpenAI API key is configured, generate summary/key_points via LLM.
    5. Otherwise fall back to a rule-based summary.
    """
    settings = get_settings()

    # 1. Fetch news
    try:
        raw_articles = await provider.get_news(symbol, limit=limit)
    except Exception:
        logger.exception("Failed to fetch news for %s", symbol)
        return SentimentResult(
            symbol=symbol.upper(),
            overall_sentiment="NEUTRAL",
            confidence_score=0.0,
            score_breakdown={},
            summary=f"Could not fetch news for {symbol.upper()}.",
            key_points=["News fetch failed"],
            sources_used=[],
        )

    if not raw_articles:
        return SentimentResult(
            symbol=symbol.upper(),
            overall_sentiment="NEUTRAL",
            confidence_score=0.0,
            score_breakdown={},
            summary=f"No recent news found for {symbol.upper()}.",
            key_points=["No articles available"],
            sources_used=[],
        )

    # Normalise to our NewsItem model
    articles: list[NewsItem] = []
    for a in raw_articles:
        published = (
            a.published_at.isoformat()
            if hasattr(a, "published_at") and a.published_at
            else ""
        )
        title = getattr(a, "title", "")
        summary_text = getattr(a, "summary", "") or ""
        content = f"{title}\n{summary_text}"
        source = getattr(a, "source", "Unknown")
        url = getattr(a, "url", "")
        sym = getattr(a, "symbol", "")
        symbols_list = [sym.upper()] if sym else [symbol.upper()]

        articles.append(
            NewsItem(
                source=source,
                title=title,
                url=url,
                published_at=published,
                content=content,
                symbols=symbols_list,
            )
        )

    # 2. Score each article
    article_scores = [_score_article(a.title, a.content) for a in articles]

    # 3. Aggregate
    score_breakdown, composite = _aggregate_scores(article_scores)

    # Normalise composite from [-1, 1] to confidence [0, 1]
    confidence_score = (abs(composite) + 1.0) / 2.0  # maps 0→0.5, 1→1.0
    # Better: use the magnitude of composite as confidence
    confidence_score = min(1.0, max(0.0, abs(composite)))

    sentiment = _composite_to_sentiment(
        composite, settings.SENTIMENT_CONFIDENCE_THRESHOLD
    )

    sources_used = list({a.source for a in articles})

    # 4. LLM summary
    headlines = [a.title for a in articles]
    excerpts = [a.content for a in articles]
    llm_result = await _llm_analyze(symbol.upper(), headlines, excerpts)

    if llm_result:
        summary = llm_result["summary"]
        key_points = llm_result["key_points"]
        # Blend LLM confidence with scoring confidence
        llm_conf = llm_result["confidence"] / 100.0
        confidence_score = (confidence_score + llm_conf) / 2.0
        # LLM sentiment can override if scores are flat
        if abs(composite) < 0.2 and llm_result["sentiment"] != "NEUTRAL":
            sentiment = llm_result["sentiment"]
    else:
        summary, key_points = _build_fallback_summary(
            symbol.upper(), sentiment, score_breakdown, len(articles)
        )

    return SentimentResult(
        symbol=symbol.upper(),
        overall_sentiment=sentiment,
        confidence_score=round(confidence_score, 4),
        score_breakdown={k: round(v, 4) for k, v in score_breakdown.items()},
        summary=summary,
        key_points=key_points,
        sources_used=sources_used,
    )


async def analyze_batch(
    symbols: list[str],
    provider: MarketDataProvider,
    *,
    max_concurrent: int = 5,
) -> list[SentimentResult]:
    """Analyze multiple symbols concurrently with a semaphore limit."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _analyze_one(sym: str) -> SentimentResult:
        async with semaphore:
            return await analyze_news(sym, provider)

    tasks = [asyncio.create_task(_analyze_one(s)) for s in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    out: list[SentimentResult] = []
    for sym, res in zip(symbols, results):
        if isinstance(res, Exception):
            logger.exception("Batch analysis failed for %s", sym)
            out.append(
                SentimentResult(
                    symbol=sym.upper(),
                    overall_sentiment="NEUTRAL",
                    confidence_score=0.0,
                    score_breakdown={},
                    summary=f"Analysis failed: {res}",
                    key_points=["Error during analysis"],
                    sources_used=[],
                )
            )
        else:
            out.append(res)

    return out


async def get_market_sentiment(
    provider: MarketDataProvider,
) -> dict[str, SentimentResult]:
    """Broad market sentiment across major index ETFs (SPY, QQQ, IWM)."""
    indices = ["SPY", "QQQ", "IWM"]
    results = await analyze_batch(indices, provider, max_concurrent=3)
    return {r.symbol: r for r in results}


# ---------------------------------------------------------------------------
# Legacy stub compatibility — kept until callers are migrated
# ---------------------------------------------------------------------------

async def analyze_sentiment(ticker: str) -> dict:
    """Legacy wrapper for the old stub signature.

    Returns a dict compatible with the stub that was previously in place.
    Prefer using ``analyze_news()`` directly.
    """
    from app.engines.market_data import PolygonProvider, AlpacaProvider

    settings = get_settings()
    if settings.POLYGON_API_KEY:
        provider = PolygonProvider()
    elif settings.ALPACA_API_KEY:
        provider = AlpacaProvider()
    else:
        return {
            "ticker": ticker.upper(),
            "sentiment_score": 0.0,
            "headline_count": 0,
            "top_headlines": [],
            "summary": "No market data provider configured",
        }

    result = await analyze_news(ticker, provider)

    return {
        "ticker": result.symbol,
        "sentiment_score": (
            result.confidence_score
            if result.overall_sentiment == "BULLISH"
            else -result.confidence_score
            if result.overall_sentiment == "BEARISH"
            else 0.0
        ),
        "headline_count": len(result.sources_used),
        "top_headlines": result.key_points[:5],
        "summary": result.summary,
    }
