"""Alpaca Markets broker integration (paper and live)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.broker.base import AccountInfo, BrokerClient, BrokerOrder, Position

logger = logging.getLogger(__name__)


class AlpacaBrokerClient(BrokerClient):
    """Alpaca Markets REST API v2 client."""

    def __init__(self, api_key: str, secret_key: str, base_url: str):
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
            "Content-Type": "application/json",
        }
        self._paper = "paper-api" in base_url

    @property
    def is_paper(self) -> bool:
        return self._paper

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=10.0,
        )

    async def _get(self, path: str, **params: Any) -> dict[str, Any] | list[Any]:
        async with self._client() as c:
            r = await c.get(path, params=params)
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.post(path, json=body)
            r.raise_for_status()
            return r.json()

    async def _delete(self, path: str) -> bool:
        async with self._client() as c:
            r = await c.delete(path)
            return r.status_code in (200, 204)

    async def get_account(self) -> AccountInfo:
        data = await self._get("/v2/account")
        assert isinstance(data, dict)
        return AccountInfo(
            account_id=data.get("id", ""),
            status=data.get("status", "UNKNOWN"),
            cash=float(data.get("cash", 0)),
            portfolio_value=float(data.get("portfolio_value", 0)),
            buying_power=float(data.get("buying_power", 0)),
            equity=float(data.get("equity", 0)),
            last_equity=float(data.get("last_equity", 0)),
            paper_mode=self._paper,
            raw=data,
        )

    async def get_positions(self) -> list[Position]:
        data = await self._get("/v2/positions")
        assert isinstance(data, list)
        return [self._parse_position(p) for p in data]

    async def get_position(self, ticker: str) -> Position | None:
        try:
            data = await self._get(f"/v2/positions/{ticker.upper()}")
            assert isinstance(data, dict)
            return self._parse_position(data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def _parse_position(self, data: dict[str, Any]) -> Position:
        return Position(
            ticker=data.get("symbol", ""),
            quantity=float(data.get("qty", 0)),
            avg_entry_price=float(data.get("avg_entry_price", 0)),
            current_price=float(data.get("current_price", 0)),
            market_value=float(data.get("market_value", 0)),
            unrealized_pl=float(data.get("unrealized_pl", 0)),
            unrealized_pl_pct=float(data.get("unrealized_plpc", 0)) * 100,
            side=data.get("side", "long"),
            raw=data,
        )

    async def submit_market_order(
        self, ticker: str, side: str, quantity: float, paper_mode: bool = True
    ) -> BrokerOrder:
        body = {
            "symbol": ticker.upper(),
            "qty": str(quantity),
            "side": side,
            "type": "market",
            "time_in_force": "day",
        }
        try:
            data = await self._post("/v2/orders", body)
            return self._parse_order(data)
        except httpx.HTTPStatusError as e:
            return BrokerOrder(
                broker_order_id="",
                ticker=ticker,
                side=side,
                order_type="market",
                quantity=quantity,
                status="rejected",
                error_message=str(e),
            )

    async def submit_limit_order(
        self, ticker: str, side: str, quantity: float, limit_price: float, paper_mode: bool = True
    ) -> BrokerOrder:
        body = {
            "symbol": ticker.upper(),
            "qty": str(quantity),
            "side": side,
            "type": "limit",
            "limit_price": str(limit_price),
            "time_in_force": "day",
        }
        try:
            data = await self._post("/v2/orders", body)
            return self._parse_order(data)
        except httpx.HTTPStatusError as e:
            return BrokerOrder(
                broker_order_id="",
                ticker=ticker,
                side=side,
                order_type="limit",
                quantity=quantity,
                status="rejected",
                error_message=str(e),
            )

    async def cancel_order(self, broker_order_id: str) -> bool:
        return await self._delete(f"/v2/orders/{broker_order_id}")

    async def close_position(self, ticker: str) -> BrokerOrder | None:
        try:
            data = await self._delete(f"/v2/positions/{ticker.upper()}")
            return None  # Alpaca returns 204 on position close
        except Exception as e:
            logger.error("Failed to close position %s: %s", ticker, e)
            return None

    def _parse_order(self, data: dict[str, Any]) -> BrokerOrder:
        def _dt(s: str | None) -> datetime | None:
            if not s:
                return None
            return datetime.fromisoformat(s.replace("Z", "+00:00"))

        return BrokerOrder(
            broker_order_id=data.get("id", ""),
            ticker=data.get("symbol", ""),
            side=data.get("side", ""),
            order_type=data.get("type", ""),
            quantity=float(data.get("qty", 0)),
            status=data.get("status", "pending"),
            limit_price=float(data["limit_price"]) if data.get("limit_price") else None,
            filled_price=float(data["filled_avg_price"]) if data.get("filled_avg_price") else None,
            filled_quantity=float(data["filled_qty"]) if data.get("filled_qty") else None,
            submitted_at=_dt(data.get("submitted_at")),
            filled_at=_dt(data.get("filled_at")),
            raw=data,
        )

    async def get_order(self, broker_order_id: str) -> BrokerOrder | None:
        try:
            data = await self._get(f"/v2/orders/{broker_order_id}")
            assert isinstance(data, dict)
            return self._parse_order(data)
        except httpx.HTTPStatusError:
            return None

    async def get_orders(self, status: str = "all", limit: int = 50) -> list[BrokerOrder]:
        params: dict[str, Any] = {"limit": limit}
        if status != "all":
            params["status"] = status
        data = await self._get("/v2/orders", **params)
        assert isinstance(data, list)
        return [self._parse_order(o) for o in data]

    async def get_current_price(self, ticker: str) -> float | None:
        try:
            data = await self._get(f"/v2/stocks/{ticker.upper()}/quotes/latest")
            assert isinstance(data, dict)
            quote = data.get("quote", {})
            ask = quote.get("ap", 0)
            bid = quote.get("bp", 0)
            if ask and bid:
                return (ask + bid) / 2
            return ask or bid or None
        except Exception:
            return None

    async def is_market_open(self) -> bool:
        try:
            data = await self._get("/v2/clock")
            assert isinstance(data, dict)
            return bool(data.get("is_open", False))
        except Exception:
            return False
