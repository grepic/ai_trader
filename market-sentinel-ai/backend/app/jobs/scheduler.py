"""APScheduler background jobs for data ingestion, analysis, and reporting."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.database import AsyncSessionLocal
from app.models.core import DailyReport, PortfolioSnapshot, RiskEvent
from app.services.broker.factory import get_broker_client
from app.services.data_ingestion.ingestion_service import DataIngestionService
from app.services.reporting.reporter import ReportingService
from app.services.risk.engine import RiskEngine
from app.services.strategy.trading_service import TradingService

logger = logging.getLogger(__name__)

_risk_engine: RiskEngine | None = None
reporter = ReportingService()


def _get_risk() -> RiskEngine:
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskEngine()
    return _risk_engine


# ---------------------------------------------------------------------------
# Job functions
# ---------------------------------------------------------------------------

async def job_ingest_data() -> None:
    """Collect data from all sources."""
    try:
        async with AsyncSessionLocal() as db:
            service = DataIngestionService(db)
            count = await service.ingest_all()
            logger.info("Ingestion job: %d new items", count)
    except Exception as e:
        logger.error("Ingestion job failed: %s", e)


async def job_process_signals() -> None:
    """Verify sources → AI analysis → risk check → paper trade."""
    try:
        broker = get_broker_client()
        risk = _get_risk()
        async with AsyncSessionLocal() as db:
            service = TradingService(db=db, broker=broker, risk_engine=risk)
            count = await service.process_unprocessed_items()
            logger.info("Signal processing job: %d items processed", count)
    except Exception as e:
        logger.error("Signal processing job failed: %s", e)


async def job_portfolio_snapshot() -> None:
    """Snapshot portfolio state to DB."""
    try:
        broker = get_broker_client()
        account = await broker.get_account()
        positions = await broker.get_positions()

        positions_value = sum(p.market_value for p in positions)
        unrealized_pl = sum(p.unrealized_pl for p in positions)

        async with AsyncSessionLocal() as db:
            snap = PortfolioSnapshot(
                account_value=account.equity,
                cash_balance=account.cash,
                positions_value=positions_value,
                unrealized_pl=unrealized_pl,
                realized_pl_today=0.0,
                daily_pl=account.equity - account.last_equity,
                trades_today=_get_risk().get_status()["trades_today"],
                open_positions=len(positions),
                paper_mode=broker.is_paper,
                snapshot_at=datetime.now(timezone.utc),
            )
            db.add(snap)
            await db.commit()
        logger.info("Portfolio snapshot saved. Equity: $%.2f", account.equity)
    except Exception as e:
        logger.error("Portfolio snapshot job failed: %s", e)


async def job_daily_report() -> None:
    """Generate and send end-of-day report."""
    try:
        broker = get_broker_client()
        account = await broker.get_account()
        risk = _get_risk()

        today = date.today().isoformat()
        report_data = {
            "report_date": today,
            "account_value": account.equity,
            "cash_balance": account.cash,
            "daily_pl": account.equity - account.last_equity,
            "realized_pl": 0.0,
            "unrealized_pl": 0.0,
            "total_trades": risk.get_status()["trades_today"],
            "winning_trades": 0,
            "losing_trades": 0,
            "signals_generated": 0,
            "signals_traded": 0,
            "signals_alerted": 0,
            "signals_ignored": 0,
            "risk_events_count": 0,
            "paper_mode": broker.is_paper,
        }

        msg = reporter.format_daily_report_telegram(report_data)
        tg_sent = await reporter.send_telegram(msg)

        email_html = reporter.format_email_daily_report(report_data)
        email_sent = await reporter.send_email(
            f"Market Sentinel AI — Daily Report {today}", email_html
        )

        async with AsyncSessionLocal() as db:
            report = DailyReport(
                **{k: v for k, v in report_data.items()},
                sent_telegram=tg_sent,
                sent_email=email_sent,
            )
            db.add(report)
            await db.commit()

        logger.info("Daily report sent (TG: %s, Email: %s)", tg_sent, email_sent)
    except Exception as e:
        logger.error("Daily report job failed: %s", e)


async def job_morning_report() -> None:
    """Send pre-market morning briefing."""
    try:
        broker = get_broker_client()
        account = await broker.get_account()
        positions = await broker.get_positions()
        market_open = await broker.is_market_open()

        from sqlalchemy import select, func
        from app.models.core import WatchlistTicker
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(func.count(WatchlistTicker.id)).where(WatchlistTicker.is_active.is_(True))
            )
            watchlist_count = result.scalar() or 0

        msg = reporter.format_morning_report_telegram(
            account_value=account.equity,
            open_positions=len(positions),
            watchlist_count=watchlist_count,
            market_open=market_open,
            paper_mode=broker.is_paper,
        )
        await reporter.send_telegram(msg)
        logger.info("Morning report sent")
    except Exception as e:
        logger.error("Morning report job failed: %s", e)


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------

def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Data ingestion — every 2 minutes
    scheduler.add_job(
        job_ingest_data,
        trigger=IntervalTrigger(minutes=2),
        id="ingest_data",
        name="Data Ingestion",
        max_instances=1,
        coalesce=True,
    )

    # Signal processing — every 1 minute
    scheduler.add_job(
        job_process_signals,
        trigger=IntervalTrigger(minutes=1),
        id="process_signals",
        name="Signal Processing",
        max_instances=1,
        coalesce=True,
    )

    # Portfolio snapshot — every 5 minutes
    scheduler.add_job(
        job_portfolio_snapshot,
        trigger=IntervalTrigger(minutes=5),
        id="portfolio_snapshot",
        name="Portfolio Snapshot",
        max_instances=1,
        coalesce=True,
    )

    # Daily report — 4:30 PM ET (21:30 UTC)
    scheduler.add_job(
        job_daily_report,
        trigger=CronTrigger(hour=21, minute=30, timezone="UTC"),
        id="daily_report",
        name="Daily Report",
        max_instances=1,
    )

    # Morning report — 9:00 AM ET (14:00 UTC)
    scheduler.add_job(
        job_morning_report,
        trigger=CronTrigger(hour=14, minute=0, timezone="UTC"),
        id="morning_report",
        name="Morning Report",
        max_instances=1,
    )

    return scheduler
