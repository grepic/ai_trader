"""FastAPI dependency injection helpers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.broker.factory import get_broker_client
from app.services.broker.base import BrokerClient
from app.services.risk.engine import RiskEngine

# Module-level singleton risk engine (shared state across requests)
_risk_engine: RiskEngine | None = None


def get_risk_engine() -> RiskEngine:
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskEngine(broker=get_broker_client())
    return _risk_engine


DbSession = Annotated[AsyncSession, Depends(get_db)]
Broker = Annotated[BrokerClient, Depends(get_broker_client)]
Risk = Annotated[RiskEngine, Depends(get_risk_engine)]
