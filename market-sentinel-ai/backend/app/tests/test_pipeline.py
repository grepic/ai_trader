"""Integration tests for the full trading pipeline (ingest → signal → trade)."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.database import AsyncSessionLocal, create_tables, engine
from app.database import Base
from app.models.core import SourceItem, WatchlistTicker
from app.services.broker.mock_broker import MockBrokerClient
from app.services.risk.engine import RiskEngine
from app.services.strategy.trading_service import TradingService


@pytest.fixture(autouse=True)
async def setup_db():
    await create_tables()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def mock_broker():
    return MockBrokerClient(initial_cash=100_000.0)


@pytest.fixture
def risk_engine():
    return RiskEngine()


async def _seed_watchlist(db, ticker="AAPL"):
    db.add(WatchlistTicker(ticker=ticker, name="Apple Inc.", sector="Technology"))
    await db.commit()


def _make_source_item(ticker="AAPL", headline="Apple beats earnings by 20%") -> SourceItem:
    return SourceItem(
        source_name="Reuters",
        source_type="news",
        source_url="https://reuters.com/test",
        ticker_detected=ticker,
        headline=headline,
        content=f"{ticker}: {headline}. Analysts are positive.",
        published_at=datetime.now(timezone.utc),
        is_processed=False,
    )


class TestTradingPipeline:
    async def test_item_in_watchlist_gets_processed(self, mock_broker, risk_engine):
        async with AsyncSessionLocal() as db:
            await _seed_watchlist(db, "AAPL")
            item = _make_source_item("AAPL")
            db.add(item)
            await db.flush()

            service = TradingService(db=db, broker=mock_broker, risk_engine=risk_engine)

            # Patch AI analyzer to return deterministic result
            ai_response = {
                "event_summary": "Apple beats earnings",
                "event_type": "earnings",
                "sentiment": "positive",
                "confidence": 90.0,
                "expected_time_horizon": "hours",
                "expected_price_impact": "high",
                "risk_level": "medium",
                "trade_decision": "BUY",
                "reasoning_summary": "Strong beat",
                "sources_used": ["Reuters"],
                "model_used": "test",
            }
            service._analyzer.analyze = AsyncMock(return_value=ai_response)

            count = await service.process_unprocessed_items()
            assert count == 1
            assert item.is_processed is True

    async def test_ticker_not_in_watchlist_skipped(self, mock_broker, risk_engine):
        async with AsyncSessionLocal() as db:
            # Don't add AAPL to watchlist
            item = _make_source_item("AAPL")
            db.add(item)
            await db.flush()

            service = TradingService(db=db, broker=mock_broker, risk_engine=risk_engine)
            count = await service.process_unprocessed_items()

            # Item is still processed (marked), but no signal/trade created
            assert count == 1

    async def test_hold_signal_does_not_execute_trade(self, mock_broker, risk_engine):
        async with AsyncSessionLocal() as db:
            await _seed_watchlist(db, "AAPL")
            item = _make_source_item("AAPL")
            db.add(item)
            await db.flush()

            service = TradingService(db=db, broker=mock_broker, risk_engine=risk_engine)
            service._analyzer.analyze = AsyncMock(return_value={
                "event_summary": "Neutral news",
                "event_type": "other",
                "sentiment": "neutral",
                "confidence": 55.0,
                "expected_time_horizon": "days",
                "expected_price_impact": "low",
                "risk_level": "low",
                "trade_decision": "HOLD",
                "reasoning_summary": "No clear signal",
                "sources_used": ["Reuters"],
                "model_used": "test",
            })

            count = await service.process_unprocessed_items()
            assert count == 1
            # MockBrokerClient starts with no positions
            positions = await mock_broker.get_positions()
            assert len(positions) == 0

    async def test_extreme_risk_blocks_trade(self, mock_broker, risk_engine):
        async with AsyncSessionLocal() as db:
            await _seed_watchlist(db, "AAPL")
            item = _make_source_item("AAPL")
            db.add(item)
            await db.flush()

            service = TradingService(db=db, broker=mock_broker, risk_engine=risk_engine)
            service._analyzer.analyze = AsyncMock(return_value={
                "event_summary": "Extreme risk event",
                "event_type": "earnings",
                "sentiment": "positive",
                "confidence": 95.0,
                "expected_time_horizon": "hours",
                "expected_price_impact": "high",
                "risk_level": "extreme",
                "trade_decision": "BUY",
                "reasoning_summary": "Risky",
                "sources_used": ["Reuters"],
                "model_used": "test",
            })

            count = await service.process_unprocessed_items()
            assert count == 1
            # Extreme risk — no positions opened
            positions = await mock_broker.get_positions()
            assert len(positions) == 0

    async def test_paused_engine_blocks_trade(self, mock_broker, risk_engine):
        risk_engine.pause()
        async with AsyncSessionLocal() as db:
            await _seed_watchlist(db, "AAPL")
            item = _make_source_item("AAPL")
            db.add(item)
            await db.flush()

            service = TradingService(db=db, broker=mock_broker, risk_engine=risk_engine)
            service._analyzer.analyze = AsyncMock(return_value={
                "event_summary": "Good earnings",
                "event_type": "earnings",
                "sentiment": "positive",
                "confidence": 90.0,
                "expected_time_horizon": "hours",
                "expected_price_impact": "high",
                "risk_level": "medium",
                "trade_decision": "BUY",
                "reasoning_summary": "Strong buy",
                "sources_used": ["Reuters"],
                "model_used": "test",
            })

            await service.process_unprocessed_items()
            positions = await mock_broker.get_positions()
            assert len(positions) == 0

    async def test_multiple_items_all_processed(self, mock_broker, risk_engine):
        async with AsyncSessionLocal() as db:
            await _seed_watchlist(db, "AAPL")
            await _seed_watchlist(db, "MSFT")

            for ticker, headline in [
                ("AAPL", "Apple Q4 beats"),
                ("MSFT", "Microsoft cloud revenue up"),
                ("AAPL", "Apple product launch"),
            ]:
                db.add(_make_source_item(ticker, headline))
            await db.flush()

            service = TradingService(db=db, broker=mock_broker, risk_engine=risk_engine)
            service._analyzer.analyze = AsyncMock(return_value={
                "event_summary": "Test",
                "event_type": "earnings",
                "sentiment": "positive",
                "confidence": 60.0,  # below 80 threshold → no trade, but processed
                "expected_time_horizon": "hours",
                "expected_price_impact": "medium",
                "risk_level": "medium",
                "trade_decision": "BUY",
                "reasoning_summary": "ok",
                "sources_used": [],
                "model_used": "test",
            })

            count = await service.process_unprocessed_items()
            assert count == 3
