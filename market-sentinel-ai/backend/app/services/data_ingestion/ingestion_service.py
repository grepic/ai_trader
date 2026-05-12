"""Orchestrates all data sources and persists raw SourceItems to the database."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import SourceItem, WatchlistTicker
from app.services.data_ingestion.sources import get_all_sources
from app.services.verification.engine import VerificationEngine

logger = logging.getLogger(__name__)


class DataIngestionService:
    """Fetches data from all sources and saves new SourceItems to the DB."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._verifier = VerificationEngine()

    async def get_active_tickers(self) -> list[str]:
        result = await self._db.execute(
            select(WatchlistTicker.ticker).where(WatchlistTicker.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def ingest_all(self) -> int:
        """Run all data sources and persist new items. Returns number of new items saved."""
        tickers = await self.get_active_tickers()
        if not tickers:
            logger.info("No active tickers in watchlist — skipping ingestion")
            return 0

        sources = get_all_sources()
        total_new = 0

        for source in sources:
            try:
                items = await source.fetch(tickers)
                for item_data in items:
                    saved = await self._save_item(item_data)
                    if saved:
                        total_new += 1
            except Exception as e:
                logger.error("Source %s failed: %s", source.source_name, e)

        await self._db.flush()
        logger.info("Ingestion complete: %d new items", total_new)
        return total_new

    async def _save_item(self, data: dict) -> bool:
        """Save a raw item if not already seen (dedup). Returns True if new."""
        headline = data.get("headline") or ""
        ticker = data.get("ticker_detected") or ""

        if not headline or not ticker:
            return False

        dedup_hash = self._verifier.compute_dedup_hash(headline, ticker)

        # Check for existing item with same hash
        existing = await self._db.execute(
            select(SourceItem.id).where(SourceItem.dedup_hash == dedup_hash)
        )
        if existing.scalar_one_or_none():
            return False  # Already processed

        item = SourceItem(
            source_name=data.get("source_name", "unknown"),
            source_type=data.get("source_type", "unknown"),
            source_url=data.get("source_url"),
            author=data.get("author"),
            published_at=data.get("published_at"),
            collected_at=datetime.now(timezone.utc),
            ticker_detected=ticker,
            headline=headline[:1024],
            content=(data.get("content") or "")[:4096],
            raw_data=data.get("raw_data"),
            is_processed=False,
            dedup_hash=dedup_hash,
        )
        self._db.add(item)
        return True
