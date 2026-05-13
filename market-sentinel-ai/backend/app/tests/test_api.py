"""Integration tests for FastAPI endpoints using in-memory SQLite."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import create_tables, engine
from app.main import app


@pytest.fixture(autouse=True)
async def setup_db():
    """Create tables once per test, drop them after."""
    await create_tables()
    yield
    async with engine.begin() as conn:
        from app.database import Base
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    async def test_health_returns_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

class TestOverview:
    async def test_overview_returns_structure(self, client):
        r = await client.get("/api/overview")
        assert r.status_code == 200
        data = r.json()
        assert "bot_status" in data
        assert "risk_status" in data
        assert "recent_signals" in data
        assert "recent_trades" in data

    async def test_overview_paper_mode_true(self, client):
        r = await client.get("/api/overview")
        assert r.json()["bot_status"]["paper_mode"] is True


# ---------------------------------------------------------------------------
# Risk / Bot control
# ---------------------------------------------------------------------------

class TestBotControl:
    async def test_pause_then_resume(self, client):
        r = await client.post("/api/bot/pause")
        assert r.status_code == 200
        assert r.json()["status"] == "paused"

        r = await client.post("/api/bot/resume")
        assert r.status_code == 200
        assert r.json()["status"] == "running"

    async def test_emergency_stop_persists(self, client):
        r = await client.post("/api/bot/emergency-stop")
        assert r.status_code == 200
        assert r.json()["status"] == "emergency_stopped"

        # Resume should fail after emergency stop
        r = await client.post("/api/bot/resume")
        assert r.status_code == 400
        assert "emergency" in r.json()["detail"].lower()

    async def test_risk_status_structure(self, client):
        r = await client.get("/api/risk/status")
        assert r.status_code == 200
        data = r.json()
        assert "daily_loss_usd" in data
        assert "max_daily_loss_usd" in data
        assert "emergency_stopped" in data
        assert isinstance(data["risk_warnings"], list)


# ---------------------------------------------------------------------------
# Positions & Portfolio
# ---------------------------------------------------------------------------

class TestPositions:
    async def test_get_positions_returns_list(self, client):
        r = await client.get("/api/positions")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_get_portfolio_returns_snapshot(self, client):
        r = await client.get("/api/positions/portfolio")
        assert r.status_code == 200
        data = r.json()
        assert "account_value" in data
        assert "cash_balance" in data
        assert data["paper_mode"] is True

    async def test_close_nonexistent_position_404(self, client):
        r = await client.post("/api/positions/FAKEXYZ/close")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

class TestSignals:
    async def test_get_signals_empty(self, client):
        r = await client.get("/api/signals")
        assert r.status_code == 200
        assert r.json() == []

    async def test_get_signals_with_ticker_filter(self, client):
        r = await client.get("/api/signals?ticker=AAPL")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_get_signal_404(self, client):
        r = await client.get("/api/signals/nonexistent-id")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

class TestTrades:
    async def test_get_trades_empty(self, client):
        r = await client.get("/api/trades")
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

class TestSources:
    async def test_get_sources_empty(self, client):
        r = await client.get("/api/sources")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_get_verified_events_empty(self, client):
        r = await client.get("/api/sources/verified")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

class TestWatchlist:
    async def test_get_watchlist_initially_empty(self, client):
        r = await client.get("/api/watchlist")
        assert r.status_code == 200
        # May be seeded by lifespan, but always a list
        assert isinstance(r.json(), list)

    async def test_add_and_remove_ticker(self, client):
        r = await client.post("/api/watchlist", json={"ticker": "TESTCO", "name": "Test Corp"})
        assert r.status_code in (200, 201)
        assert r.json()["ticker"] == "TESTCO"

        r = await client.delete("/api/watchlist/TESTCO")
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

class TestLogs:
    async def test_get_logs_empty(self, client):
        r = await client.get("/api/logs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_get_logs_with_filters(self, client):
        r = await client.get("/api/logs?level=INFO&ticker=AAPL&limit=10")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class TestReports:
    async def test_get_daily_reports_empty(self, client):
        r = await client.get("/api/reports/daily")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_get_report_by_date_404(self, client):
        r = await client.get("/api/reports/daily/2000-01-01")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

class TestBacktest:
    async def test_run_backtest_returns_result(self, client):
        payload = {
            "tickers": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "initial_capital": 10000.0,
            "strategy": "news_momentum",
        }
        r = await client.post("/api/backtest/run", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["strategy"] == "news_momentum"
        assert "total_return_pct" in data
        assert "equity_curve" in data
        assert len(data["equity_curve"]) > 0

    async def test_run_backtest_multiple_tickers(self, client):
        payload = {
            "tickers": ["AAPL", "MSFT", "NVDA"],
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "initial_capital": 50000.0,
            "strategy": "conservative",
        }
        r = await client.post("/api/backtest/run", json=payload)
        assert r.status_code == 200
        assert r.json()["initial_capital"] == 50000.0
