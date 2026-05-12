"""Tests for the Backtesting Engine."""

import pytest
from app.services.backtesting.engine import BacktestEngine


@pytest.fixture
def engine():
    return BacktestEngine()


class TestBacktestBasics:
    def test_backtest_runs_without_error(self, engine):
        result = engine.run(
            tickers=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000.0,
        )
        assert result is not None
        assert "total_return_pct" in result
        assert "win_rate_pct" in result
        assert "max_drawdown_pct" in result

    def test_multiple_tickers(self, engine):
        result = engine.run(
            tickers=["AAPL", "MSFT", "NVDA"],
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=10000.0,
        )
        assert result["tickers"] == ["AAPL", "MSFT", "NVDA"]

    def test_initial_capital_preserved_with_no_trades(self, engine):
        result = engine.run(
            tickers=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-01-02",  # Only 1 day
            initial_capital=10000.0,
        )
        assert result["initial_capital"] == 10000.0

    def test_invalid_dates_raise_error(self, engine):
        with pytest.raises(ValueError):
            engine.run(
                tickers=["AAPL"],
                start_date="2024-12-31",
                end_date="2024-01-01",  # End before start
                initial_capital=10000.0,
            )

    def test_win_rate_between_0_and_100(self, engine):
        result = engine.run(
            tickers=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=10000.0,
        )
        assert 0 <= result["win_rate_pct"] <= 100

    def test_max_drawdown_non_negative(self, engine):
        result = engine.run(
            tickers=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=10000.0,
        )
        assert result["max_drawdown_pct"] >= 0

    def test_equity_curve_returned(self, engine):
        result = engine.run(
            tickers=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000.0,
        )
        assert "equity_curve" in result
        assert len(result["equity_curve"]) > 0
        for point in result["equity_curve"]:
            assert "date" in point
            assert "equity" in point
            assert point["equity"] > 0

    def test_trade_counts_consistent(self, engine):
        result = engine.run(
            tickers=["AAPL"],
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=10000.0,
        )
        assert result["total_trades"] == result["winning_trades"] + result["losing_trades"]

    def test_different_strategies_run(self, engine):
        for strategy in ["news_momentum", "earnings_surprise", "social_sentiment"]:
            result = engine.run(
                tickers=["AAPL"],
                start_date="2024-01-01",
                end_date="2024-06-30",
                initial_capital=10000.0,
                strategy=strategy,
            )
            assert result["strategy"] == strategy
