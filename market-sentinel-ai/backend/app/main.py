"""Market Sentinel AI — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import create_tables
from app.jobs.scheduler import create_scheduler
from app.api.routers import (
    backtest,
    overview,
    positions,
    reports,
    risk,
    signals,
    sources,
    trades,
    watchlist,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("Market Sentinel AI starting up")
    logger.info("Mode: %s", "PAPER TRADING" if settings.is_paper_mode else "⚠️  LIVE TRADING")
    logger.info("Real trading enabled: %s", settings.real_trading_enabled)
    logger.info("=" * 60)

    # Create DB tables (use Alembic for production migrations)
    await create_tables()

    # Seed default watchlist if empty
    await _seed_default_watchlist()

    # Start background scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Background scheduler started with %d jobs", len(scheduler.get_jobs()))

    yield

    scheduler.shutdown(wait=False)
    logger.info("Market Sentinel AI shutting down")


async def _seed_default_watchlist() -> None:
    """Add default tickers if watchlist is empty."""
    from app.database import AsyncSessionLocal
    from app.models.core import WatchlistTicker
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count(WatchlistTicker.id)))
        count = result.scalar()
        if count == 0:
            defaults = [
                ("AAPL", "Apple Inc.", "Technology"),
                ("MSFT", "Microsoft Corp.", "Technology"),
                ("NVDA", "NVIDIA Corp.", "Technology"),
                ("TSLA", "Tesla Inc.", "Consumer Cyclical"),
                ("GOOGL", "Alphabet Inc.", "Technology"),
                ("AMZN", "Amazon.com Inc.", "Consumer Cyclical"),
                ("META", "Meta Platforms Inc.", "Technology"),
                ("SPY", "SPDR S&P 500 ETF", "ETF"),
            ]
            for ticker, name, sector in defaults:
                db.add(WatchlistTicker(ticker=ticker, name=name, sector=sector))
            await db.commit()
            logger.info("Seeded %d default watchlist tickers", len(defaults))


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Market Sentinel AI",
        description=(
            "Automated AI-powered stock trading assistant. "
            "⚠️ For research and educational purposes only. "
            "Paper trading is enabled by default."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register all routers
    app.include_router(overview.router)
    app.include_router(signals.router)
    app.include_router(trades.router)
    app.include_router(positions.router)
    app.include_router(sources.router)
    app.include_router(risk.router)
    app.include_router(watchlist.router)
    app.include_router(reports.router)
    app.include_router(backtest.router)

    return app


app = create_app()
