"""Tests for the Mock Broker."""

import pytest
from app.services.broker.mock_broker import MockBrokerClient


@pytest.fixture
def broker():
    return MockBrokerClient(initial_cash=10_000.0)


class TestMockBrokerAccount:
    @pytest.mark.asyncio
    async def test_initial_account(self, broker):
        account = await broker.get_account()
        assert account.cash == 10_000.0
        assert account.status == "ACTIVE"
        assert account.paper_mode is True

    @pytest.mark.asyncio
    async def test_is_paper_mode(self, broker):
        assert broker.is_paper is True


class TestMarketOrders:
    @pytest.mark.asyncio
    async def test_buy_order_fills(self, broker):
        order = await broker.submit_market_order("AAPL", "buy", 1.0)
        assert order.status == "filled"
        assert order.filled_quantity == 1.0
        assert order.filled_price is not None

    @pytest.mark.asyncio
    async def test_buy_reduces_cash(self, broker):
        before = (await broker.get_account()).cash
        await broker.submit_market_order("AAPL", "buy", 1.0)
        after = (await broker.get_account()).cash
        assert after < before

    @pytest.mark.asyncio
    async def test_buy_creates_position(self, broker):
        await broker.submit_market_order("AAPL", "buy", 2.0)
        pos = await broker.get_position("AAPL")
        assert pos is not None
        assert pos.quantity == 2.0

    @pytest.mark.asyncio
    async def test_sell_without_position_rejected(self, broker):
        order = await broker.submit_market_order("AAPL", "sell", 1.0)
        assert order.status == "rejected"

    @pytest.mark.asyncio
    async def test_buy_then_sell_closes_position(self, broker):
        await broker.submit_market_order("AAPL", "buy", 2.0)
        await broker.submit_market_order("AAPL", "sell", 2.0)
        pos = await broker.get_position("AAPL")
        assert pos is None

    @pytest.mark.asyncio
    async def test_insufficient_cash_rejected(self, broker):
        # Try to buy more than we can afford
        order = await broker.submit_market_order("AAPL", "buy", 1_000_000.0)
        assert order.status == "rejected"
        assert "Insufficient" in (order.error_message or "")


class TestPositions:
    @pytest.mark.asyncio
    async def test_no_positions_initially(self, broker):
        positions = await broker.get_positions()
        assert positions == []

    @pytest.mark.asyncio
    async def test_get_position_not_found(self, broker):
        pos = await broker.get_position("AAPL")
        assert pos is None

    @pytest.mark.asyncio
    async def test_multiple_buys_average_price(self, broker):
        await broker.submit_market_order("AAPL", "buy", 1.0)
        await broker.submit_market_order("AAPL", "buy", 1.0)
        pos = await broker.get_position("AAPL")
        assert pos is not None
        assert abs(pos.quantity - 2.0) < 0.01


class TestClosePosition:
    @pytest.mark.asyncio
    async def test_close_position(self, broker):
        await broker.submit_market_order("TSLA", "buy", 1.0)
        await broker.close_position("TSLA")
        pos = await broker.get_position("TSLA")
        assert pos is None

    @pytest.mark.asyncio
    async def test_close_nonexistent_position_returns_none(self, broker):
        result = await broker.close_position("FAKE")
        assert result is None


class TestMarketStatus:
    @pytest.mark.asyncio
    async def test_market_open_by_default(self, broker):
        assert await broker.is_market_open() is True

    @pytest.mark.asyncio
    async def test_set_market_closed(self, broker):
        broker.set_market_open(False)
        assert await broker.is_market_open() is False


class TestCurrentPrice:
    @pytest.mark.asyncio
    async def test_known_ticker_returns_price(self, broker):
        price = await broker.get_current_price("AAPL")
        assert price is not None
        assert price > 0

    @pytest.mark.asyncio
    async def test_unknown_ticker_returns_default(self, broker):
        price = await broker.get_current_price("UNKN")
        assert price is not None
        assert price > 0
