"""Simple in-memory rate limiter for sensitive endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from fastapi import HTTPException, Request


class RateLimiter:
    """Allow at most `calls` requests per `period` seconds per IP."""

    def __init__(self, calls: int, period: int) -> None:
        self._calls = calls
        self._period = period
        self._history: dict[str, list[float]] = defaultdict(list)

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self._period
        history = self._history[key]
        # Evict expired entries
        self._history[key] = [t for t in history if t > cutoff]
        if len(self._history[key]) >= self._calls:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit: max {self._calls} requests per {self._period}s",
            )
        self._history[key].append(now)


# 5 calls per 60 seconds for dangerous bot control endpoints
bot_control_limiter = RateLimiter(calls=5, period=60)
