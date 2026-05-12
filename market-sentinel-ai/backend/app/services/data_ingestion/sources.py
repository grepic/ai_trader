"""Pluggable data source adapters — each source produces a list of raw dicts."""

from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class BaseSource:
    source_name: str = "unknown"
    source_type: str = "unknown"

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Mock / Demo source (always available — no API keys needed)
# ---------------------------------------------------------------------------

_MOCK_HEADLINES = [
    ("{ticker} beats Q3 earnings estimates by 12%, raises full-year guidance", "positive"),
    ("{ticker} announces strategic partnership with major cloud provider", "positive"),
    ("{ticker} CEO sells $5M in shares ahead of earnings", "negative"),
    ("{ticker} receives FDA approval for new drug", "positive"),
    ("Analyst upgrades {ticker} to BUY with $250 price target", "positive"),
    ("{ticker} misses revenue expectations, stock drops in after-hours", "negative"),
    ("{ticker} faces SEC investigation over accounting practices", "negative"),
    ("Rumor: {ticker} in merger talks with tech giant (unconfirmed)", "positive"),
    ("{ticker} announces $2B share buyback program", "positive"),
    ("{ticker} CFO resigns, company provides no explanation", "negative"),
]


class MockNewsSource(BaseSource):
    source_name = "mock_financial_news"
    source_type = "news"

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        items = []
        for ticker in tickers:
            if random.random() < 0.3:  # 30% chance of news per ticker per cycle
                headline_template, sentiment = random.choice(_MOCK_HEADLINES)
                headline = headline_template.format(ticker=ticker)
                published = _now() - timedelta(minutes=random.randint(1, 60))
                items.append({
                    "source_name": self.source_name,
                    "source_type": self.source_type,
                    "source_url": f"https://mockfinance.example/news/{ticker.lower()}-{random.randint(1000,9999)}",
                    "author": "Mock Reporter",
                    "published_at": published,
                    "ticker_detected": ticker,
                    "headline": headline,
                    "content": f"Extended article content about {ticker}. " * 5,
                    "raw_data": {"mock": True, "sentiment_hint": sentiment},
                })
        return items


class MockSECSource(BaseSource):
    source_name = "sec_edgar_mock"
    source_type = "sec"

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        items = []
        for ticker in tickers:
            if random.random() < 0.05:  # 5% chance
                items.append({
                    "source_name": self.source_name,
                    "source_type": "sec",
                    "source_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&symbol={ticker}",
                    "author": "SEC EDGAR",
                    "published_at": _now() - timedelta(hours=random.randint(1, 8)),
                    "ticker_detected": ticker,
                    "headline": f"{ticker} files 8-K: Material event disclosure",
                    "content": f"The company {ticker} has filed an 8-K form disclosing a material event.",
                    "raw_data": {"form_type": "8-K", "mock": True},
                })
        return items


# ---------------------------------------------------------------------------
# NewsAPI adapter
# ---------------------------------------------------------------------------

class NewsAPISource(BaseSource):
    source_name = "newsapi"
    source_type = "news"

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        settings = get_settings()
        if not settings.newsapi_key:
            return []

        items = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for ticker in tickers[:5]:  # Rate limit friendly
                try:
                    resp = await client.get(
                        "https://newsapi.org/v2/everything",
                        params={
                            "q": ticker,
                            "language": "en",
                            "sortBy": "publishedAt",
                            "pageSize": 5,
                            "apiKey": settings.newsapi_key,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    for article in data.get("articles", []):
                        pub = article.get("publishedAt")
                        pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00")) if pub else None
                        items.append({
                            "source_name": article.get("source", {}).get("name", "newsapi"),
                            "source_type": "news",
                            "source_url": article.get("url"),
                            "author": article.get("author"),
                            "published_at": pub_dt,
                            "ticker_detected": ticker,
                            "headline": article.get("title"),
                            "content": article.get("description") or article.get("content"),
                            "raw_data": article,
                        })
                except Exception as e:
                    logger.warning("NewsAPI fetch failed for %s: %s", ticker, e)

        return items


# ---------------------------------------------------------------------------
# Reddit source (public JSON, no API key needed)
# ---------------------------------------------------------------------------

class RedditSource(BaseSource):
    source_name = "reddit"
    source_type = "social"

    _SUBREDDITS = ["stocks", "wallstreetbets", "investing", "StockMarket"]

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        items = []
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "MarketSentinelAI/1.0"},
        ) as client:
            for sub in self._SUBREDDITS[:2]:  # Limit to 2 subreddits
                try:
                    resp = await client.get(
                        f"https://www.reddit.com/r/{sub}/hot.json",
                        params={"limit": 25},
                    )
                    resp.raise_for_status()
                    posts = resp.json().get("data", {}).get("children", [])
                    for post in posts:
                        d = post.get("data", {})
                        title = d.get("title", "")
                        for ticker in tickers:
                            if ticker.upper() in title.upper():
                                created = datetime.fromtimestamp(
                                    d.get("created_utc", 0), tz=timezone.utc
                                )
                                items.append({
                                    "source_name": f"reddit/r/{sub}",
                                    "source_type": "social",
                                    "source_url": f"https://reddit.com{d.get('permalink', '')}",
                                    "author": d.get("author"),
                                    "published_at": created,
                                    "ticker_detected": ticker,
                                    "headline": title[:512],
                                    "content": d.get("selftext", "")[:1000],
                                    "raw_data": {
                                        "score": d.get("score"),
                                        "num_comments": d.get("num_comments"),
                                        "upvote_ratio": d.get("upvote_ratio"),
                                        "subreddit": sub,
                                    },
                                })
                except Exception as e:
                    logger.warning("Reddit fetch failed: %s", e)

        return items


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

def get_all_sources() -> list[BaseSource]:
    """Return all configured data sources."""
    sources: list[BaseSource] = [
        MockNewsSource(),
        MockSECSource(),
        NewsAPISource(),
        RedditSource(),
    ]
    return sources
