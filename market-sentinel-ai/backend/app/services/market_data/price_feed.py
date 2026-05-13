"""
Real-time and historical price feed via yfinance.

Uses a simple in-memory cache (TTL=5min) to avoid hammering the API.
Falls back silently — callers must handle None return values.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# In-memory cache: ticker → (price, fetched_at)
_live_cache: dict[str, tuple[float, datetime]] = {}
_LIVE_TTL = timedelta(minutes=5)


async def get_live_price(ticker: str) -> float | None:
    """Fetch latest trade price for a ticker. Returns None on failure."""
    ticker = ticker.upper()
    now = datetime.now(timezone.utc)

    cached = _live_cache.get(ticker)
    if cached and (now - cached[1]) < _LIVE_TTL:
        return cached[0]

    loop = asyncio.get_event_loop()
    price = await loop.run_in_executor(None, _fetch_live_sync, ticker)
    if price and price > 0:
        _live_cache[ticker] = (price, now)
    return price


def _fetch_live_sync(ticker: str) -> float | None:
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        price = t.fast_info.last_price
        if price and float(price) > 0:
            return float(price)
        # Fallback: recent 1-minute bars
        data = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=True)
        if not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception as e:
        logger.debug("yfinance live price failed for %s: %s", ticker, e)
    return None


async def get_historical_prices(
    ticker: str, start: date, end: date
) -> list[float] | None:
    """
    Fetch daily closing prices from yfinance.
    Returns list ordered oldest→newest, or None on failure.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_historical_sync, ticker, start, end)


def _fetch_historical_sync(ticker: str, start: date, end: date) -> list[float] | None:
    try:
        import yfinance as yf
        # Extra day buffer so end date is inclusive
        end_buf = (end + timedelta(days=2)).isoformat()
        data = yf.download(
            ticker,
            start=start.isoformat(),
            end=end_buf,
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if data.empty or len(data) < 2:
            logger.warning("yfinance: no data for %s (%s – %s)", ticker, start, end)
            return None
        return [float(p) for p in data["Close"].tolist()]
    except Exception as e:
        logger.warning("yfinance historical failed for %s: %s", ticker, e)
        return None


def invalidate_cache(ticker: str | None = None) -> None:
    """Clear price cache. Pass None to clear all."""
    if ticker:
        _live_cache.pop(ticker.upper(), None)
    else:
        _live_cache.clear()
