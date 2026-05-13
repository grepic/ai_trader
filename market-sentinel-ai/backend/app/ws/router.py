"""WebSocket endpoint for real-time dashboard push."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

_HEARTBEAT_INTERVAL = 30  # seconds


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws_manager.connect(ws)
    heartbeat_task = asyncio.create_task(_heartbeat(ws))
    try:
        while True:
            # Keep connection alive; client can send pings
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WebSocket error: %s", e)
    finally:
        heartbeat_task.cancel()
        await ws_manager.disconnect(ws)


async def _heartbeat(ws: WebSocket) -> None:
    """Send periodic heartbeat so the client knows the connection is alive."""
    import json
    from datetime import datetime, timezone

    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL)
        try:
            payload = json.dumps({
                "type": "heartbeat",
                "data": {"connections": ws_manager.connection_count},
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            await ws.send_text(payload)
        except Exception:
            break
