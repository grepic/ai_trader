"""Factory for creating the appropriate broker client."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.services.broker.alpaca_broker import AlpacaBrokerClient
from app.services.broker.base import BrokerClient
from app.services.broker.mock_broker import MockBrokerClient


@lru_cache(maxsize=1)
def get_broker_client() -> BrokerClient:
    settings = get_settings()
    if settings.has_alpaca:
        return AlpacaBrokerClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            base_url=settings.alpaca_base_url,
        )
    # Fall back to mock broker when Alpaca credentials are not configured
    return MockBrokerClient()
