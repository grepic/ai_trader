"""In-memory mock broker for testing and CI — no real network calls."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from app.services.broker.base import AccountInfo, BrokerClient, BrokerOrder, Position


_MOCK_PRICES: dict[str, float] = {
    "AAPL": 175.0,
    "TSLA": 220.0,
    "NVDA": 480.0,
    "MSFT": 415.0,
    "GOOGL": 155.0,
    "AMZN": 185.0,
    "META": 510.0,
    "SPY": 505.0,
    "QQQ": 435.0,
}


class MockBrokerClient(BrokerClient):
    """
    Simulated broker for testing and paper trading.

    With use_live_prices=True (default in non-test environments) prices are
    fetched from yfinance with a 5-minute cache. Set to False for tests so
    no network calls are made.
    """

    def __init__(self, initial_cash: float = 100_000.0, use_live_prices: bool = False):
        self._cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, BrokerOrder] = {}
        self._market_open = True
        self._use_live_prices = use_live_prices

    @property
    def is_paper(self) -> bool:
        return True

    async def get_account(self) -> AccountInfo:
        portfolio_value = sum(p.market_value for p in self._positions.values())
        equity = self._cash + portfolio_value
        return AccountInfo(
            account_id="MOCK-001",
            status="ACTIVE",
            cash=self._cash,
            portfolio_value=equity,
            buying_power=self._cash * 2,
            equity=equity,
            last_equity=equity,
            paper_mode=True,
        )

    async def get_positions(self) -> list[Position]:
        # Refresh current prices
        for ticker, pos in self._positions.items():
            price = await self.get_current_price(ticker) or pos.current_price
            market_value = pos.quantity * price
            unrealized_pl = market_value - (pos.quantity * pos.avg_entry_price)
            self._positions[ticker] = Position(
                ticker=ticker,
                quantity=pos.quantity,
                avg_entry_price=pos.avg_entry_price,
                current_price=price,
                market_value=market_value,
                unrealized_pl=unrealized_pl,
                unrealized_pl_pct=(unrealized_pl / (pos.quantity * pos.avg_entry_price)) * 100,
            )
        return list(self._positions.values())

    async def get_position(self, ticker: str) -> Position | None:
        return self._positions.get(ticker.upper())

    async def submit_market_order(
        self, ticker: str, side: str, quantity: float, paper_mode: bool = True
    ) -> BrokerOrder:
        ticker = ticker.upper()
        price = await self.get_current_price(ticker) or 100.0
        order_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        if side == "buy":
            cost = quantity * price
            if cost > self._cash:
                return BrokerOrder(
                    broker_order_id=order_id,
                    ticker=ticker,
                    side=side,
                    order_type="market",
                    quantity=quantity,
                    status="rejected",
                    error_message="Insufficient buying power",
                    submitted_at=now,
                )
            self._cash -= cost
            existing = self._positions.get(ticker)
            if existing:
                total_qty = existing.quantity + quantity
                avg_price = (
                    (existing.quantity * existing.avg_entry_price) + (quantity * price)
                ) / total_qty
                self._positions[ticker] = Position(
                    ticker=ticker,
                    quantity=total_qty,
                    avg_entry_price=avg_price,
                    current_price=price,
                    market_value=total_qty * price,
                    unrealized_pl=(total_qty * price) - (total_qty * avg_price),
                    unrealized_pl_pct=((price - avg_price) / avg_price) * 100,
                )
            else:
                self._positions[ticker] = Position(
                    ticker=ticker,
                    quantity=quantity,
                    avg_entry_price=price,
                    current_price=price,
                    market_value=quantity * price,
                    unrealized_pl=0.0,
                    unrealized_pl_pct=0.0,
                )
        elif side == "sell":
            existing = self._positions.get(ticker)
            if not existing or existing.quantity < quantity:
                return BrokerOrder(
                    broker_order_id=order_id,
                    ticker=ticker,
                    side=side,
                    order_type="market",
                    quantity=quantity,
                    status="rejected",
                    error_message="Insufficient shares",
                    submitted_at=now,
                )
            self._cash += quantity * price
            remaining = existing.quantity - quantity
            if remaining <= 0:
                del self._positions[ticker]
            else:
                self._positions[ticker] = Position(
                    ticker=ticker,
                    quantity=remaining,
                    avg_entry_price=existing.avg_entry_price,
                    current_price=price,
                    market_value=remaining * price,
                    unrealized_pl=(remaining * price) - (remaining * existing.avg_entry_price),
                    unrealized_pl_pct=((price - existing.avg_entry_price) / existing.avg_entry_price) * 100,
                )

        order = BrokerOrder(
            broker_order_id=order_id,
            ticker=ticker,
            side=side,
            order_type="market",
            quantity=quantity,
            status="filled",
            filled_price=price,
            filled_quantity=quantity,
            submitted_at=now,
            filled_at=now,
        )
        self._orders[order_id] = order
        return order

    async def submit_limit_order(
        self, ticker: str, side: str, quantity: float, limit_price: float, paper_mode: bool = True
    ) -> BrokerOrder:
        # For mock, treat limit as market if price is close
        return await self.submit_market_order(ticker, side, quantity, paper_mode)

    async def cancel_order(self, broker_order_id: str) -> bool:
        order = self._orders.get(broker_order_id)
        if order and order.status == "pending":
            order.status = "cancelled"
            return True
        return False

    async def close_position(self, ticker: str) -> BrokerOrder | None:
        pos = self._positions.get(ticker.upper())
        if not pos:
            return None
        return await self.submit_market_order(ticker, "sell", pos.quantity)

    async def get_order(self, broker_order_id: str) -> BrokerOrder | None:
        return self._orders.get(broker_order_id)

    async def get_orders(self, status: str = "all", limit: int = 50) -> list[BrokerOrder]:
        orders = list(self._orders.values())
        if status != "all":
            orders = [o for o in orders if o.status == status]
        return orders[-limit:]

    async def get_current_price(self, ticker: str) -> float | None:
        if self._use_live_prices:
            try:
                from app.services.market_data.price_feed import get_live_price
                price = await get_live_price(ticker)
                if price:
                    return price
            except Exception:
                pass  # Fall through to mock price
        base = _MOCK_PRICES.get(ticker.upper(), 100.0)
        return round(base * (1 + random.uniform(-0.005, 0.005)), 2)

    async def is_market_open(self) -> bool:
        return self._market_open

    def set_market_open(self, open_: bool) -> None:
        self._market_open = open_
