"""Abstract broker interface — all broker implementations must satisfy this contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AccountInfo:
    account_id: str
    status: str  # ACTIVE|RESTRICTED|etc
    cash: float
    portfolio_value: float
    buying_power: float
    equity: float
    last_equity: float
    currency: str = "USD"
    paper_mode: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    ticker: str
    quantity: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float
    side: str = "long"  # long|short
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrokerOrder:
    broker_order_id: str
    ticker: str
    side: str  # buy|sell
    order_type: str  # market|limit
    quantity: float
    status: str  # pending|filled|cancelled|rejected|partially_filled
    limit_price: float | None = None
    filled_price: float | None = None
    filled_quantity: float | None = None
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    error_message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class BrokerClient(ABC):
    """Abstract base class for all broker integrations."""

    @property
    @abstractmethod
    def is_paper(self) -> bool:
        """True if this is a paper trading account."""
        ...

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """Return current account status and balances."""
        ...

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Return all current open positions."""
        ...

    @abstractmethod
    async def get_position(self, ticker: str) -> Position | None:
        """Return a single position, or None if not held."""
        ...

    @abstractmethod
    async def submit_market_order(
        self, ticker: str, side: str, quantity: float, paper_mode: bool = True
    ) -> BrokerOrder:
        """Submit a market order. side: 'buy'|'sell'."""
        ...

    @abstractmethod
    async def submit_limit_order(
        self, ticker: str, side: str, quantity: float, limit_price: float, paper_mode: bool = True
    ) -> BrokerOrder:
        """Submit a limit order."""
        ...

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel a pending order. Returns True if successful."""
        ...

    @abstractmethod
    async def close_position(self, ticker: str) -> BrokerOrder | None:
        """Close an entire position at market price."""
        ...

    @abstractmethod
    async def get_order(self, broker_order_id: str) -> BrokerOrder | None:
        """Get order status by broker order id."""
        ...

    @abstractmethod
    async def get_orders(
        self, status: str = "all", limit: int = 50
    ) -> list[BrokerOrder]:
        """List recent orders."""
        ...

    @abstractmethod
    async def get_current_price(self, ticker: str) -> float | None:
        """Get latest trade price for a ticker."""
        ...

    @abstractmethod
    async def is_market_open(self) -> bool:
        """Return True if the market is currently open for trading."""
        ...
