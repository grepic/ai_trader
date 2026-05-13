"""Tests for price feed and yfinance integration."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from app.services.market_data.price_feed import (
    _fetch_historical_sync,
    _fetch_live_sync,
    get_live_price,
    invalidate_cache,
)


class TestLivePriceFeed:
    def setup_method(self):
        invalidate_cache()

    def test_fetch_live_returns_float_on_success(self):
        mock_ticker = MagicMock()
        mock_ticker.fast_info.last_price = 175.50

        with patch("yfinance.Ticker", return_value=mock_ticker):
            price = _fetch_live_sync("AAPL")
        assert price == 175.50

    def test_fetch_live_returns_none_on_exception(self):
        with patch("yfinance.Ticker", side_effect=Exception("network error")):
            price = _fetch_live_sync("AAPL")
        assert price is None

    def test_fetch_live_ignores_zero_price(self):
        mock_ticker = MagicMock()
        mock_ticker.fast_info.last_price = 0.0

        import pandas as pd
        mock_data = pd.DataFrame({"Close": [175.0]})

        with patch("yfinance.Ticker", return_value=mock_ticker), \
             patch("yfinance.download", return_value=mock_data):
            price = _fetch_live_sync("AAPL")
        assert price == 175.0

    @pytest.mark.asyncio
    async def test_get_live_price_caches_result(self):
        mock_ticker = MagicMock()
        mock_ticker.fast_info.last_price = 200.0

        with patch("yfinance.Ticker", return_value=mock_ticker):
            price1 = await get_live_price("MSFT")
            price2 = await get_live_price("MSFT")  # From cache

        assert price1 == price2 == 200.0

    @pytest.mark.asyncio
    async def test_get_live_price_returns_none_on_failure(self):
        with patch("yfinance.Ticker", side_effect=Exception("offline")):
            price = await get_live_price("UNKNOWN")
        assert price is None


class TestHistoricalPriceFeed:
    def test_fetch_historical_returns_price_list(self):
        import pandas as pd
        mock_data = pd.DataFrame(
            {"Close": [170.0, 172.5, 171.0, 175.0, 173.0]},
            index=pd.date_range("2024-01-01", periods=5),
        )
        with patch("yfinance.download", return_value=mock_data):
            prices = _fetch_historical_sync("AAPL", date(2024, 1, 1), date(2024, 1, 5))

        assert prices is not None
        assert len(prices) == 5
        assert prices[0] == 170.0

    def test_fetch_historical_returns_none_on_empty_data(self):
        import pandas as pd
        with patch("yfinance.download", return_value=pd.DataFrame()):
            prices = _fetch_historical_sync("FAKE", date(2024, 1, 1), date(2024, 1, 5))
        assert prices is None

    def test_fetch_historical_returns_none_on_exception(self):
        with patch("yfinance.download", side_effect=Exception("network error")):
            prices = _fetch_historical_sync("AAPL", date(2024, 1, 1), date(2024, 1, 5))
        assert prices is None


class TestBacktestWithRealData:
    def test_backtest_uses_yfinance_when_available(self):
        import pandas as pd
        from app.services.backtesting.engine import BacktestEngine

        mock_data = pd.DataFrame(
            {"Close": [170.0 + i * 0.5 for i in range(60)]},
            index=pd.date_range("2024-01-01", periods=60),
        )
        with patch("yfinance.download", return_value=mock_data):
            engine = BacktestEngine()
            result = engine.run(
                tickers=["AAPL"],
                start_date="2024-01-01",
                end_date="2024-03-01",
                initial_capital=10000.0,
                strategy="news_momentum",
            )
        assert result["strategy"] == "news_momentum"
        assert len(result["equity_curve"]) > 0

    def test_backtest_falls_back_to_synthetic_on_failure(self):
        from app.services.backtesting.engine import BacktestEngine

        with patch("yfinance.download", side_effect=Exception("offline")):
            engine = BacktestEngine()
            result = engine.run(
                tickers=["AAPL"],
                start_date="2024-01-01",
                end_date="2024-03-01",
                initial_capital=10000.0,
            )
        # Should still return a valid result using synthetic data
        assert "total_return_pct" in result
        assert result["initial_capital"] == 10000.0


class TestMockBrokerLivePrices:
    @pytest.mark.asyncio
    async def test_mock_broker_uses_live_prices_when_enabled(self):
        from app.services.broker.mock_broker import MockBrokerClient

        broker = MockBrokerClient(use_live_prices=True)
        with patch(
            "app.services.market_data.price_feed.get_live_price",
            return_value=180.0,
        ):
            price = await broker.get_current_price("AAPL")
        assert price == 180.0

    @pytest.mark.asyncio
    async def test_mock_broker_falls_back_to_mock_price_on_failure(self):
        from app.services.broker.mock_broker import MockBrokerClient

        broker = MockBrokerClient(use_live_prices=True)
        with patch(
            "app.services.market_data.price_feed.get_live_price",
            return_value=None,
        ):
            price = await broker.get_current_price("AAPL")
        assert price is not None
        assert price > 0  # Falls back to mock price

    @pytest.mark.asyncio
    async def test_mock_broker_without_live_prices_never_calls_feed(self):
        from app.services.broker.mock_broker import MockBrokerClient

        broker = MockBrokerClient(use_live_prices=False)
        with patch("app.services.market_data.price_feed.get_live_price") as mock_feed:
            price = await broker.get_current_price("AAPL")
            mock_feed.assert_not_called()
        assert price is not None
