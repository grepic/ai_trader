"""Pluggable data source adapters — each source produces a list of raw dicts."""

from __future__ import annotations

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

_MOCK_EVENTS = [
    ("{ticker} beats Q3 earnings estimates by 12%, raises full-year guidance", "positive", "earnings"),
    ("{ticker} announces strategic partnership with major cloud provider", "positive", "other"),
    ("{ticker} CEO sells $5M in shares ahead of earnings", "negative", "ceo_change"),
    ("{ticker} receives FDA approval for new drug", "positive", "regulatory"),
    ("Analyst upgrades {ticker} to BUY with new price target", "positive", "analyst_rating"),
    ("{ticker} misses revenue expectations, stock drops in after-hours", "negative", "earnings"),
    ("{ticker} faces SEC investigation over accounting practices", "negative", "lawsuit"),
    ("Rumor: {ticker} in merger talks with tech giant (unconfirmed)", "positive", "merger"),
    ("{ticker} announces $2B share buyback program", "positive", "other"),
    ("{ticker} CFO resigns unexpectedly, company provides no explanation", "negative", "ceo_change"),
    ("{ticker} launches next-generation AI product line", "positive", "product_launch"),
    ("{ticker} reports record operating margins in Q4", "positive", "earnings"),
    ("Short seller publishes critical report on {ticker} business practices", "negative", "lawsuit"),
    ("{ticker} increases dividend by 15% quarter-over-quarter", "positive", "other"),
    ("{ticker} supply chain disruption may impact next quarter guidance", "negative", "macro"),
]


class MockNewsSource(BaseSource):
    source_name = "mock_financial_news"
    source_type = "news"

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        items = []
        for ticker in tickers:
            # 25% chance of news per ticker per cycle
            if random.random() < 0.25:
                headline_tpl, sentiment_hint, event_type = random.choice(_MOCK_EVENTS)
                headline = headline_tpl.format(ticker=ticker)
                published = _now() - timedelta(minutes=random.randint(1, 90))
                # Randomly pick a credible news source
                source = random.choice(["Reuters", "Bloomberg", "AP", "CNBC", "MarketWatch", "Benzinga"])
                items.append({
                    "source_name": source,
                    "source_type": self.source_type,
                    "source_url": f"https://{source.lower().replace(' ', '')}.com/news/{ticker.lower()}-{random.randint(1000,9999)}",
                    "author": f"{source} Staff",
                    "published_at": published,
                    "ticker_detected": ticker,
                    "headline": headline,
                    "content": f"Detailed analysis: {headline}. Market participants are watching closely as {ticker} navigates this development. " * 3,
                    "raw_data": {"mock": True, "sentiment_hint": sentiment_hint, "event_type": event_type},
                })
        return items


class MockSECSource(BaseSource):
    source_name = "sec_edgar_mock"
    source_type = "sec"

    _FORM_TYPES = [
        ("8-K", "Material event disclosure filed with SEC"),
        ("10-Q", "Quarterly earnings report filed with SEC"),
        ("13D", "Major shareholder stake change notification"),
        ("DEF 14A", "Proxy statement — executive compensation details"),
    ]

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        items = []
        for ticker in tickers:
            if random.random() < 0.04:  # ~4% chance per cycle
                form_type, description = random.choice(self._FORM_TYPES)
                items.append({
                    "source_name": "SEC EDGAR",
                    "source_type": "sec",
                    "source_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&symbol={ticker}&type={form_type}",
                    "author": "SEC EDGAR",
                    "published_at": _now() - timedelta(hours=random.randint(1, 6)),
                    "ticker_detected": ticker,
                    "headline": f"{ticker} files {form_type}: {description}",
                    "content": (
                        f"Company {ticker} has filed a {form_type} form with the SEC. "
                        f"{description}. Investors should review the full filing for complete details."
                    ),
                    "raw_data": {"form_type": form_type, "mock": True},
                })
        return items


class MockSocialSource(BaseSource):
    """Mock social media posts — always low credibility requiring corroboration."""

    source_name = "mock_social"
    source_type = "social"

    _SOCIAL_POSTS = [
        ("Hearing strong rumors that {ticker} is about to announce something huge 🚀", "positive"),
        ("{ticker} is going to zero, just look at the technicals 📉", "negative"),
        ("Just bought a huge position in {ticker}, this thing is going to pop", "positive"),
        ("Insiders at {ticker} are selling everything, be warned ⚠️", "negative"),
        ("{ticker} is massively undervalued right now — hidden gem", "positive"),
    ]

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        items = []
        for ticker in tickers:
            if random.random() < 0.15:
                post_tpl, sentiment_hint = random.choice(self._SOCIAL_POSTS)
                post = post_tpl.format(ticker=ticker)
                platform = random.choice(["Twitter/X", "Reddit/r/stocks", "StockTwits"])
                followers = random.randint(100, 50_000)
                items.append({
                    "source_name": platform,
                    "source_type": "social",
                    "source_url": f"https://{platform.split('/')[0].lower()}.com/status/{random.randint(10**15, 10**16)}",
                    "author": f"trader_{random.randint(100,999)}",
                    "published_at": _now() - timedelta(minutes=random.randint(1, 30)),
                    "ticker_detected": ticker,
                    "headline": post[:200],
                    "content": post,
                    "raw_data": {
                        "mock": True,
                        "platform": platform,
                        "followers": followers,
                        "likes": random.randint(0, followers // 10),
                        "sentiment_hint": sentiment_hint,
                    },
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
        # Batch tickers to reduce API calls
        query = " OR ".join(tickers[:4])
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": query,
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": 20,
                        "apiKey": settings.newsapi_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                for article in data.get("articles", []):
                    title = article.get("title") or ""
                    # Detect which ticker this is about
                    detected = next((t for t in tickers if t.upper() in title.upper()), None)
                    if not detected:
                        detected = next((t for t in tickers if t.lower() in (article.get("description") or "").lower()), None)
                    if not detected:
                        continue

                    pub = article.get("publishedAt")
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00")) if pub else None
                    items.append({
                        "source_name": article.get("source", {}).get("name", "newsapi"),
                        "source_type": "news",
                        "source_url": article.get("url"),
                        "author": article.get("author"),
                        "published_at": pub_dt,
                        "ticker_detected": detected,
                        "headline": title[:512],
                        "content": (article.get("description") or "") + " " + (article.get("content") or ""),
                        "raw_data": article,
                    })
            except Exception as e:
                logger.warning("NewsAPI fetch failed: %s", e)

        return items


# ---------------------------------------------------------------------------
# Alpha Vantage — news & market data
# ---------------------------------------------------------------------------

class AlphaVantageNewsSource(BaseSource):
    """Alpha Vantage News Sentiment API (free tier: 25 req/day)."""

    source_name = "alpha_vantage_news"
    source_type = "news"

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        settings = get_settings()
        if not settings.alphavantage_key:
            return []

        items = []
        # Fetch news for first 2 tickers (rate-limit friendly)
        for ticker in tickers[:2]:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        "https://www.alphavantage.co/query",
                        params={
                            "function": "NEWS_SENTIMENT",
                            "tickers": ticker,
                            "limit": 10,
                            "apikey": settings.alphavantage_key,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                for article in data.get("feed", []):
                    pub_str = article.get("time_published", "")
                    pub_dt = None
                    if pub_str:
                        try:
                            pub_dt = datetime.strptime(pub_str, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                        except ValueError:
                            pass

                    # Find this ticker's sentiment score
                    ticker_sentiment = next(
                        (ts for ts in article.get("ticker_sentiment", []) if ts.get("ticker") == ticker),
                        {},
                    )
                    sentiment_score = float(ticker_sentiment.get("ticker_sentiment_score", 0))
                    sentiment = "positive" if sentiment_score > 0.1 else "negative" if sentiment_score < -0.1 else "neutral"

                    items.append({
                        "source_name": article.get("source", "alpha_vantage"),
                        "source_type": "news",
                        "source_url": article.get("url"),
                        "author": article.get("authors", [None])[0] if article.get("authors") else None,
                        "published_at": pub_dt,
                        "ticker_detected": ticker,
                        "headline": article.get("title", "")[:512],
                        "content": article.get("summary", ""),
                        "raw_data": {
                            "overall_sentiment_label": article.get("overall_sentiment_label"),
                            "overall_sentiment_score": article.get("overall_sentiment_score"),
                            "ticker_sentiment_score": sentiment_score,
                            "sentiment": sentiment,
                        },
                    })
            except Exception as e:
                logger.warning("Alpha Vantage news fetch failed for %s: %s", ticker, e)

        return items


# ---------------------------------------------------------------------------
# Reddit source (public JSON — no API key needed)
# ---------------------------------------------------------------------------

class RedditSource(BaseSource):
    source_name = "reddit"
    source_type = "social"

    _SUBREDDITS = ["stocks", "wallstreetbets", "investing", "StockMarket"]

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        items = []
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "MarketSentinelAI/1.0 (research bot)"},
        ) as client:
            for sub in self._SUBREDDITS[:2]:
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
                            # Match ticker as whole word (not part of another word)
                            import re
                            if re.search(rf"\b{re.escape(ticker)}\b", title, re.IGNORECASE):
                                created = datetime.fromtimestamp(
                                    d.get("created_utc", 0), tz=timezone.utc
                                )
                                score = d.get("score", 0)
                                items.append({
                                    "source_name": f"reddit/r/{sub}",
                                    "source_type": "social",
                                    "source_url": f"https://reddit.com{d.get('permalink', '')}",
                                    "author": d.get("author"),
                                    "published_at": created,
                                    "ticker_detected": ticker,
                                    "headline": title[:512],
                                    "content": d.get("selftext", "")[:2000],
                                    "raw_data": {
                                        "score": score,
                                        "num_comments": d.get("num_comments"),
                                        "upvote_ratio": d.get("upvote_ratio"),
                                        "subreddit": sub,
                                        "is_high_karma": score > 1000,
                                    },
                                })
                except Exception as e:
                    logger.warning("Reddit fetch failed for r/%s: %s", sub, e)

        return items


# ---------------------------------------------------------------------------
# StockTwits public stream (no auth required for public feed)
# ---------------------------------------------------------------------------

class StockTwitsSource(BaseSource):
    source_name = "stocktwits"
    source_type = "social"

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        items = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for ticker in tickers[:3]:  # Rate limit
                try:
                    resp = await client.get(
                        f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json",
                        params={"limit": 10},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    for msg in data.get("messages", []):
                        created_at = msg.get("created_at")
                        pub_dt = None
                        if created_at:
                            try:
                                pub_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            except ValueError:
                                pass
                        sentiment = None
                        if msg.get("entities", {}).get("sentiment"):
                            raw = msg["entities"]["sentiment"].get("basic", "Neutral")
                            sentiment = raw.lower()

                        items.append({
                            "source_name": "StockTwits",
                            "source_type": "social",
                            "source_url": f"https://stocktwits.com/message/{msg.get('id')}",
                            "author": msg.get("user", {}).get("username"),
                            "published_at": pub_dt,
                            "ticker_detected": ticker,
                            "headline": msg.get("body", "")[:300],
                            "content": msg.get("body", ""),
                            "raw_data": {
                                "message_id": msg.get("id"),
                                "likes": msg.get("likes", {}).get("total", 0),
                                "sentiment": sentiment,
                                "followers": msg.get("user", {}).get("followers", 0),
                            },
                        })
                except Exception as e:
                    logger.debug("StockTwits fetch failed for %s: %s", ticker, e)

        return items


# ---------------------------------------------------------------------------
# Earnings calendar (mock implementation; real data from Alpha Vantage / Quandl)
# ---------------------------------------------------------------------------

class EarningsCalendarSource(BaseSource):
    """Mock upcoming earnings announcements."""

    source_name = "earnings_calendar"
    source_type = "earnings"

    async def fetch(self, tickers: list[str]) -> list[dict[str, Any]]:
        items = []
        for ticker in tickers:
            # ~10% chance of having an upcoming earnings date
            if random.random() < 0.10:
                days_ahead = random.randint(1, 14)
                earnings_date = _now() + timedelta(days=days_ahead)
                items.append({
                    "source_name": self.source_name,
                    "source_type": self.source_type,
                    "source_url": f"https://www.earningswhispers.com/stocks/{ticker.lower()}",
                    "author": "Earnings Calendar",
                    "published_at": _now(),
                    "ticker_detected": ticker,
                    "headline": f"{ticker} reports earnings in {days_ahead} day(s) — {earnings_date.strftime('%b %d')}",
                    "content": (
                        f"{ticker} is scheduled to report quarterly earnings on {earnings_date.strftime('%Y-%m-%d')}. "
                        f"Analysts are watching EPS estimates and revenue guidance closely."
                    ),
                    "raw_data": {
                        "earnings_date": earnings_date.isoformat(),
                        "days_ahead": days_ahead,
                        "mock": True,
                    },
                })
        return items


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

def get_all_sources() -> list[BaseSource]:
    """Return all configured data sources in priority order."""
    settings = get_settings()
    sources: list[BaseSource] = [
        # Official sources first (highest trust)
        MockSECSource(),
        EarningsCalendarSource(),
        # Quality news
        MockNewsSource(),
        NewsAPISource(),
        AlphaVantageNewsSource(),
        # Social (lower trust — requires corroboration)
        RedditSource(),
        StockTwitsSource(),
        MockSocialSource(),
    ]
    return sources
