#!/usr/bin/env python3
"""
Market Sentinel AI — CLI management tool.

Usage:
    python cli.py seed           Seed default watchlist tickers
    python cli.py status         Show bot and account status
    python cli.py ingest         Run one data ingestion cycle
    python cli.py signals        Show recent AI signals
    python cli.py backtest       Run a backtest with defaults
    python cli.py report         Send a manual daily report
    python cli.py positions      Show current open positions
    python cli.py emergency-stop Activate emergency stop
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone


async def cmd_seed() -> None:
    """Seed default watchlist tickers into the database."""
    from app.database import AsyncSessionLocal, create_tables
    from app.models.core import WatchlistTicker
    from sqlalchemy import select, func

    await create_tables()

    async with AsyncSessionLocal() as db:
        count_result = await db.execute(select(func.count(WatchlistTicker.id)))
        count = count_result.scalar() or 0

        if count > 0:
            print(f"Watchlist already has {count} tickers. Use --force to re-seed.")
            return

        defaults = [
            ("AAPL", "Apple Inc.", "Technology"),
            ("MSFT", "Microsoft Corp.", "Technology"),
            ("NVDA", "NVIDIA Corp.", "Technology"),
            ("TSLA", "Tesla Inc.", "Consumer Cyclical"),
            ("GOOGL", "Alphabet Inc.", "Technology"),
            ("AMZN", "Amazon.com Inc.", "Consumer Cyclical"),
            ("META", "Meta Platforms Inc.", "Technology"),
            ("SPY", "SPDR S&P 500 ETF", "ETF"),
            ("QQQ", "Invesco QQQ ETF", "ETF"),
            ("AMD", "Advanced Micro Devices", "Technology"),
        ]
        for ticker, name, sector in defaults:
            db.add(WatchlistTicker(ticker=ticker, name=name, sector=sector, is_active=True))
        await db.commit()
        print(f"✓ Seeded {len(defaults)} tickers: {', '.join(t[0] for t in defaults)}")


async def cmd_status() -> None:
    """Show bot and account status."""
    from app.services.broker.factory import get_broker_client
    from app.services.risk.engine import RiskEngine
    from app.database import AsyncSessionLocal
    from app.models.core import AISignal, TradeDecision, WatchlistTicker
    from sqlalchemy import select, func

    broker = get_broker_client()
    risk = RiskEngine()

    account = await broker.get_account()
    positions = await broker.get_positions()
    market_open = await broker.is_market_open()
    risk_status = risk.get_status()

    async with AsyncSessionLocal() as db:
        tickers_count = (await db.execute(
            select(func.count(WatchlistTicker.id)).where(WatchlistTicker.is_active.is_(True))
        )).scalar() or 0
        signals_count = (await db.execute(select(func.count(AISignal.id)))).scalar() or 0
        trades_count = (await db.execute(
            select(func.count(TradeDecision.id)).where(TradeDecision.executed.is_(True))
        )).scalar() or 0

    mode = "📄 PAPER" if broker.is_paper else "💰 LIVE"
    market = "🟢 OPEN" if market_open else "🔴 CLOSED"
    bot = "🟢 RUNNING" if risk_status["bot_running"] else "🔴 STOPPED"

    print(f"\n{'='*50}")
    print(f"  Market Sentinel AI — Status")
    print(f"{'='*50}")
    print(f"  Mode:            {mode}")
    print(f"  Bot:             {bot}")
    print(f"  Market:          {market}")
    print(f"")
    print(f"  Account Equity:  ${account.equity:,.2f}")
    print(f"  Cash:            ${account.cash:,.2f}")
    print(f"  Daily P/L:       ${account.equity - account.last_equity:+,.2f}")
    print(f"")
    print(f"  Open Positions:  {len(positions)} / {risk_status.get('max_open_positions', 5)}")
    print(f"  Watching:        {tickers_count} tickers")
    print(f"  Total Signals:   {signals_count}")
    print(f"  Total Trades:    {trades_count}")
    print(f"")
    print(f"  Daily Loss:      ${risk_status['daily_loss_usd']:.2f} / ${risk_status['max_daily_loss_usd']:.2f}")
    print(f"{'='*50}\n")

    if positions:
        print("  Open Positions:")
        for p in positions:
            pl_str = f"+${p.unrealized_pl:.2f}" if p.unrealized_pl >= 0 else f"-${abs(p.unrealized_pl):.2f}"
            print(f"    {p.ticker:6s}  {p.quantity:.4f} shares  @ ${p.current_price:.2f}  P/L: {pl_str}")
        print()


async def cmd_ingest() -> None:
    """Run one data ingestion cycle."""
    from app.database import AsyncSessionLocal, create_tables
    from app.services.data_ingestion.ingestion_service import DataIngestionService

    await create_tables()
    async with AsyncSessionLocal() as db:
        service = DataIngestionService(db)
        tickers = await service.get_active_tickers()
        if not tickers:
            print("⚠️  No active tickers — run 'python cli.py seed' first")
            return
        print(f"📡 Ingesting data for {len(tickers)} tickers: {', '.join(tickers[:5])}{'...' if len(tickers) > 5 else ''}")
        count = await service.ingest_all()
        await db.commit()
        print(f"✓ Ingested {count} new items")


async def cmd_signals() -> None:
    """Show the 10 most recent AI signals."""
    from app.database import AsyncSessionLocal, create_tables
    from app.models.core import AISignal
    from sqlalchemy import select

    await create_tables()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AISignal).order_by(AISignal.created_at.desc()).limit(10)
        )
        signals = result.scalars().all()

    if not signals:
        print("No signals yet. Run 'python cli.py ingest' to collect data.")
        return

    print(f"\n{'='*70}")
    print(f"  Recent AI Signals ({len(signals)})")
    print(f"{'='*70}")
    for s in signals:
        sentiment_icon = {"positive": "🟢", "negative": "🔴", "neutral": "⚪", "mixed": "🟡"}.get(s.sentiment, "⚪")
        action_icon = {"BUY": "📈", "SELL": "📉", "HOLD": "⏸", "ALERT_ONLY": "🔔", "IGNORE": "🔇"}.get(s.trade_decision, "❓")
        print(f"  {action_icon} {s.ticker:6s} | {s.trade_decision:10s} | {sentiment_icon} {s.sentiment:8s} | {s.confidence:3.0f}% | {s.event_type:15s}")
        print(f"         {s.event_summary[:70]}")
        print()


async def cmd_backtest() -> None:
    """Run a quick backtest with default settings."""
    from app.services.backtesting.engine import BacktestEngine

    print("Running backtest: AAPL, MSFT, NVDA | 2024-01-01 to 2024-12-31 | $10,000 capital")
    engine = BacktestEngine()
    result = engine.run(
        tickers=["AAPL", "MSFT", "NVDA"],
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_capital=10_000.0,
        strategy="news_momentum",
    )

    r_sign = "+" if result["total_return_pct"] >= 0 else ""
    print(f"\n{'='*50}")
    print(f"  Backtest Results — news_momentum strategy")
    print(f"{'='*50}")
    print(f"  Total Return:    {r_sign}{result['total_return_pct']:.2f}%")
    print(f"  Final Capital:   ${result['final_capital']:,.2f}")
    print(f"  Win Rate:        {result['win_rate_pct']:.1f}%")
    print(f"  Max Drawdown:    -{result['max_drawdown_pct']:.2f}%")
    print(f"  Sharpe Ratio:    {result['sharpe_ratio']:.2f}")
    print(f"  Total Trades:    {result['total_trades']} ({result['winning_trades']}W/{result['losing_trades']}L)")
    print(f"  Avg Win:         +${result['avg_win']:.2f}")
    print(f"  Avg Loss:        -${abs(result['avg_loss']):.2f}")
    if result.get("best_trade"):
        bt = result["best_trade"]
        print(f"  Best Trade:      {bt['ticker']} +${bt['pnl']:.2f} on {bt['date']}")
    if result.get("worst_trade"):
        wt = result["worst_trade"]
        print(f"  Worst Trade:     {wt['ticker']} -${abs(wt['pnl']):.2f} on {wt['date']}")
    print(f"{'='*50}\n")


async def cmd_report() -> None:
    """Send a manual daily report via Telegram and email."""
    from app.services.broker.factory import get_broker_client
    from app.services.reporting.reporter import ReportingService
    from app.services.risk.engine import RiskEngine

    broker = get_broker_client()
    reporter = ReportingService()
    risk = RiskEngine()

    account = await broker.get_account()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

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

    print("Sending Telegram report...")
    tg_msg = reporter.format_daily_report_telegram(report_data)
    tg_ok = await reporter.send_telegram(tg_msg)
    print(f"  Telegram: {'✓ sent' if tg_ok else '✗ skipped (not configured)'}")

    print("Sending email report...")
    email_html = reporter.format_email_daily_report(report_data)
    email_ok = await reporter.send_email(f"Market Sentinel AI — Daily Report {today}", email_html)
    print(f"  Email: {'✓ sent' if email_ok else '✗ skipped (not configured)'}")


async def cmd_positions() -> None:
    """Show current open positions."""
    from app.services.broker.factory import get_broker_client

    broker = get_broker_client()
    positions = await broker.get_positions()

    if not positions:
        print("No open positions.")
        return

    account = await broker.get_account()
    total_upl = sum(p.unrealized_pl for p in positions)

    print(f"\n{'='*65}")
    print(f"  Open Positions  {'(PAPER)' if broker.is_paper else '(LIVE ⚠️)'}")
    print(f"{'='*65}")
    print(f"  {'Ticker':<8} {'Qty':>8} {'Entry':>10} {'Current':>10} {'Value':>10} {'P/L':>10}")
    print(f"  {'-'*63}")
    for p in positions:
        pl_str = f"+${p.unrealized_pl:.2f}" if p.unrealized_pl >= 0 else f"-${abs(p.unrealized_pl):.2f}"
        print(f"  {p.ticker:<8} {p.quantity:>8.4f} {p.avg_entry_price:>9.2f}$ {p.current_price:>9.2f}$ {p.market_value:>9.2f}$ {pl_str:>10}")
    print(f"  {'-'*63}")
    total_str = f"+${total_upl:.2f}" if total_upl >= 0 else f"-${abs(total_upl):.2f}"
    print(f"  {'TOTAL':<8} {'':>8} {'':>10} {'':>10} {sum(p.market_value for p in positions):>9.2f}$ {total_str:>10}")
    print(f"  Account Equity: ${account.equity:,.2f}  |  Cash: ${account.cash:,.2f}")
    print(f"{'='*65}\n")


async def cmd_emergency_stop() -> None:
    """Activate emergency stop and close all positions."""
    from app.services.broker.factory import get_broker_client
    from app.services.risk.engine import RiskEngine

    confirm = input("⚠️  This will close ALL positions and stop trading. Type 'CONFIRM' to proceed: ")
    if confirm != "CONFIRM":
        print("Cancelled.")
        return

    broker = get_broker_client()
    risk = RiskEngine()
    risk.emergency_stop()

    positions = await broker.get_positions()
    closed = []
    for pos in positions:
        print(f"  Closing {pos.ticker}...")
        order = await broker.close_position(pos.ticker)
        if order and order.status == "filled":
            closed.append(pos.ticker)

    print(f"\n🚨 Emergency stop activated. Closed: {', '.join(closed) or 'none'}")


COMMANDS = {
    "seed": cmd_seed,
    "status": cmd_status,
    "ingest": cmd_ingest,
    "signals": cmd_signals,
    "backtest": cmd_backtest,
    "report": cmd_report,
    "positions": cmd_positions,
    "emergency-stop": cmd_emergency_stop,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("Available commands:")
        for name in COMMANDS:
            print(f"  {name}")
        sys.exit(1)

    cmd = COMMANDS[sys.argv[1]]
    asyncio.run(cmd())


if __name__ == "__main__":
    main()
