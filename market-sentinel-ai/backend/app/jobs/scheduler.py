"""APScheduler background jobs for data ingestion, analysis, and reporting."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.core import AISignal, DailyReport, PortfolioSnapshot, RiskEvent, TradeDecision
from app.services.broker.factory import get_broker_client
from app.services.data_ingestion.ingestion_service import DataIngestionService
from app.services.reporting.reporter import ReportingService
from app.services.risk.engine import RiskEngine
from app.services.strategy.pnl_tracker import PnLTracker
from app.services.strategy.trading_service import TradingService
from app.ws.manager import ws_manager

logger = logging.getLogger(__name__)

_risk_engine: RiskEngine | None = None
reporter = ReportingService()
pnl_tracker = PnLTracker()


def _get_risk() -> RiskEngine:
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskEngine()
    return _risk_engine


# ---------------------------------------------------------------------------
# Job functions
# ---------------------------------------------------------------------------

async def job_ingest_data() -> None:
    """Collect data from all configured sources."""
    try:
        async with AsyncSessionLocal() as db:
            service = DataIngestionService(db)
            count = await service.ingest_all()
            await db.commit()
            if count:
                logger.info("Ingestion job: %d new items collected", count)
    except Exception as e:
        logger.error("Ingestion job failed: %s", e)


async def job_process_signals() -> None:
    """Verify sources → AI analysis → strategy → risk check → paper trade."""
    try:
        broker = get_broker_client()
        risk = _get_risk()
        async with AsyncSessionLocal() as db:
            service = TradingService(db=db, broker=broker, risk_engine=risk)
            count = await service.process_unprocessed_items()
            await db.commit()
            if count:
                logger.info("Signal processing: %d items processed", count)
    except Exception as e:
        logger.error("Signal processing job failed: %s", e)


async def job_portfolio_snapshot() -> None:
    """Snapshot portfolio state to DB with realized P&L."""
    try:
        broker = get_broker_client()
        account = await broker.get_account()
        positions = await broker.get_positions()

        positions_value = sum(p.market_value for p in positions)
        unrealized_pl = sum(p.unrealized_pl for p in positions)

        async with AsyncSessionLocal() as db:
            realized_pl = await pnl_tracker.get_daily_realized_pnl(db)
            trade_stats = await pnl_tracker.get_trade_stats_today(db)

            snap = PortfolioSnapshot(
                account_value=account.equity,
                cash_balance=account.cash,
                positions_value=positions_value,
                unrealized_pl=unrealized_pl,
                realized_pl_today=realized_pl,
                daily_pl=account.equity - account.last_equity,
                trades_today=trade_stats["total_trades"],
                open_positions=len(positions),
                paper_mode=broker.is_paper,
                snapshot_at=datetime.now(timezone.utc),
            )
            db.add(snap)
            await db.commit()

        logger.info(
            "Portfolio snapshot: equity=$%.2f positions=%d upl=$%.2f rpl=$%.2f",
            account.equity, len(positions), unrealized_pl, realized_pl,
        )

        await ws_manager.broadcast("portfolio", {
            "account_value": account.equity,
            "cash_balance": account.cash,
            "positions_value": positions_value,
            "unrealized_pl": unrealized_pl,
            "realized_pl_today": realized_pl,
            "daily_pl": account.equity - account.last_equity,
            "open_positions": len(positions),
        })
    except Exception as e:
        logger.error("Portfolio snapshot job failed: %s", e)


async def job_daily_report() -> None:
    """Generate and send end-of-day summary report."""
    try:
        broker = get_broker_client()
        account = await broker.get_account()
        positions = await broker.get_positions()
        risk = _get_risk()
        today = date.today().isoformat()

        async with AsyncSessionLocal() as db:
            realized_pl = await pnl_tracker.get_daily_realized_pnl(db)
            trade_stats = await pnl_tracker.get_trade_stats_today(db)

            # Count signals generated today
            from sqlalchemy import select, func
            today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
            sig_result = await db.execute(
                select(func.count(AISignal.id)).where(AISignal.created_at >= today_start)
            )
            signals_today = sig_result.scalar() or 0

            risk_events_result = await db.execute(
                select(func.count(RiskEvent.id)).where(RiskEvent.created_at >= today_start)
            )
            risk_events = risk_events_result.scalar() or 0

            unrealized_pl = sum(p.unrealized_pl for p in positions)

            report_data = {
                "report_date": today,
                "account_value": account.equity,
                "cash_balance": account.cash,
                "daily_pl": account.equity - account.last_equity,
                "realized_pl": realized_pl,
                "unrealized_pl": unrealized_pl,
                "total_trades": trade_stats["total_trades"],
                "winning_trades": trade_stats["winning_trades"],
                "losing_trades": trade_stats["losing_trades"],
                "signals_generated": signals_today,
                "signals_traded": trade_stats["total_trades"],
                "signals_alerted": max(0, signals_today - trade_stats["total_trades"]),
                "signals_ignored": 0,
                "best_trade_ticker": trade_stats["best_trade_ticker"],
                "best_trade_pl": trade_stats["best_trade_pl"],
                "worst_trade_ticker": trade_stats["worst_trade_ticker"],
                "worst_trade_pl": trade_stats["worst_trade_pl"],
                "risk_events_count": risk_events,
                "paper_mode": broker.is_paper,
            }

            msg = reporter.format_daily_report_telegram(report_data)
            tg_sent = await reporter.send_telegram(msg)

            email_html = reporter.format_email_daily_report(report_data)
            email_sent = await reporter.send_email(
                f"Market Sentinel AI — Daily Report {today}", email_html
            )

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


async def job_risk_monitor() -> None:
    """Check risk thresholds and send alerts if approaching limits."""
    try:
        risk = _get_risk()
        status = risk.get_status()

        # Alert at 70% of daily loss limit
        pct = status["daily_loss_pct"]
        if 70 <= pct < 100:
            msg = reporter.format_risk_alert_telegram(
                event_type="daily_loss_warning",
                description=f"Daily loss at {pct:.0f}% of ${status['max_daily_loss_usd']:.0f} limit (${status['daily_loss_usd']:.2f} used)",
                severity="warning",
            )
            await reporter.send_telegram(msg)
            await ws_manager.broadcast("risk", {
                "event_type": "daily_loss_warning",
                "severity": "warning",
                "daily_loss_pct": pct,
                "daily_loss_usd": status["daily_loss_usd"],
                "max_daily_loss_usd": status["max_daily_loss_usd"],
            })
        elif pct >= 100:
            msg = reporter.format_risk_alert_telegram(
                event_type="daily_loss_limit_reached",
                description=f"Daily loss limit REACHED: ${status['daily_loss_usd']:.2f}. Trading suspended for today.",
                severity="critical",
            )
            await reporter.send_telegram(msg)
            await ws_manager.broadcast("risk", {
                "event_type": "daily_loss_limit_reached",
                "severity": "critical",
                "daily_loss_pct": pct,
                "daily_loss_usd": status["daily_loss_usd"],
                "max_daily_loss_usd": status["max_daily_loss_usd"],
            })
    except Exception as e:
        logger.error("Risk monitor job failed: %s", e)


async def job_monitor_positions() -> None:
    """
    Check stop-loss and take-profit levels for all open positions.
    Closes positions automatically when price crosses the thresholds.
    """
    try:
        broker = get_broker_client()
        if not await broker.is_market_open():
            return

        positions = await broker.get_positions()
        if not positions:
            return

        async with AsyncSessionLocal() as db:
            for pos in positions:
                ticker = pos.ticker
                current_price = pos.current_price

                # Find the most recent executed trade decision with SL/TP set
                result = await db.execute(
                    select(TradeDecision)
                    .where(
                        TradeDecision.ticker == ticker,
                        TradeDecision.executed.is_(True),
                        or_(
                            TradeDecision.stop_loss_price.isnot(None),
                            TradeDecision.take_profit_price.isnot(None),
                        ),
                    )
                    .order_by(TradeDecision.created_at.desc())
                    .limit(1)
                )
                decision = result.scalar_one_or_none()
                if not decision:
                    continue

                trigger: str | None = None
                threshold: float | None = None

                if decision.stop_loss_price and current_price <= decision.stop_loss_price:
                    trigger = "stop_loss"
                    threshold = decision.stop_loss_price
                elif decision.take_profit_price and current_price >= decision.take_profit_price:
                    trigger = "take_profit"
                    threshold = decision.take_profit_price

                if not trigger:
                    continue

                logger.info(
                    "%s triggered for %s: price=%.2f, threshold=%.2f",
                    trigger.upper(), ticker, current_price, threshold,
                )

                order = await broker.close_position(ticker)
                if not order:
                    logger.warning("Failed to close %s on %s", ticker, trigger)
                    continue

                pnl = pos.unrealized_pl
                severity = "warning" if trigger == "stop_loss" else "info"
                emoji = "🛑" if trigger == "stop_loss" else "🎯"

                msg = (
                    f"<b>{emoji} {trigger.replace('_', ' ').title()} Hit</b>\n"
                    f"Ticker: <b>{ticker}</b>\n"
                    f"Current price: ${current_price:.2f}\n"
                    f"Threshold: ${threshold:.2f}\n"
                    f"Unrealized P/L: {'+'if pnl >= 0 else ''}{pnl:.2f}\n"
                    f"<i>Position closed at market.</i>"
                )
                await reporter.send_telegram(msg)
                await ws_manager.broadcast("trade", {
                    "ticker": ticker,
                    "side": "sell",
                    "trigger": trigger,
                    "price": current_price,
                    "threshold": threshold,
                    "unrealized_pl": pnl,
                    "paper_mode": broker.is_paper,
                })

                # Log the risk event
                async with AsyncSessionLocal() as db2:
                    db2.add(RiskEvent(
                        event_type=trigger,
                        severity=severity,
                        ticker=ticker,
                        description=f"{trigger.replace('_',' ').title()} hit at ${current_price:.2f} (threshold: ${threshold:.2f})",
                        action_taken=f"Position closed at market. P/L: {'+'if pnl >= 0 else ''}{pnl:.2f}",
                    ))
                    await db2.commit()

    except Exception as e:
        logger.error("Position monitor job failed: %s", e)


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
        misfire_grace_time=30,
    )

    # Signal processing — every 1 minute
    scheduler.add_job(
        job_process_signals,
        trigger=IntervalTrigger(minutes=1),
        id="process_signals",
        name="Signal Processing",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
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

    # Risk monitor — every 10 minutes during market hours
    scheduler.add_job(
        job_risk_monitor,
        trigger=IntervalTrigger(minutes=10),
        id="risk_monitor",
        name="Risk Monitor",
        max_instances=1,
        coalesce=True,
    )

    # Stop-loss / take-profit position monitor — every 5 minutes
    scheduler.add_job(
        job_monitor_positions,
        trigger=IntervalTrigger(minutes=5),
        id="monitor_positions",
        name="Position Monitor (SL/TP)",
        max_instances=1,
        coalesce=True,
    )

    # Daily report — 4:30 PM ET (21:30 UTC, after market close)
    scheduler.add_job(
        job_daily_report,
        trigger=CronTrigger(hour=21, minute=30, timezone="UTC"),
        id="daily_report",
        name="Daily Report",
        max_instances=1,
    )

    # Morning report — 9:00 AM ET (14:00 UTC, before market open)
    scheduler.add_job(
        job_morning_report,
        trigger=CronTrigger(hour=14, minute=0, timezone="UTC"),
        id="morning_report",
        name="Morning Report",
        max_instances=1,
    )

    return scheduler
