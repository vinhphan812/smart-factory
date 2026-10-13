"""WebSocket and HTTP API servers for the gateway."""

import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .event_store import EventStore

logger = logging.getLogger(__name__)


class EventQuery(BaseModel):
    device_id: str | None = None
    event_type: str | None = None
    limit: int = 100


class WebSocketServer:
    """Broadcasts events to connected WebSocket clients."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._clients: set[asyncio.Queue] = set()
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        async def _ws_handler(
            ws: asyncio.StreamReader, sw: asyncio.StreamWriter
        ) -> None:
            addr = sw.get_extra_info("peername")
            queue: asyncio.Queue[bytes] = asyncio.Queue()
            self._clients.add(queue)
            logger.info("WebSocket client connected: %s", addr)
            try:
                while True:
                    data = await queue.get()
                    sw.write(data + b"\n")
                    await sw.drain()
            except ConnectionResetError:
                pass
            finally:
                self._clients.discard(queue)
                logger.info("WebSocket client disconnected: %s", addr)

        self._server = await asyncio.start_server(_ws_handler, self._host, self._port)
        logger.info("WebSocket server started on %s:%d", self._host, self._port)

    async def broadcast(self, event_dict: dict[str, Any]) -> None:
        """Push an event to all connected clients."""
        if not self._clients:
            return
        data = json.dumps(event_dict, default=str).encode()
        await asyncio.gather(
            *(queue.put(data) for queue in list(self._clients)),
            return_exceptions=True,
        )

    async def shutdown(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()


def create_http_app(store: EventStore, ws_broadcaster: WebSocketServer) -> FastAPI:
    """Build FastAPI app with REST endpoints backed by the event store."""

    app = FastAPI(
        title="Smart Factory IoT Gateway API",
        version="0.1.0",
        description="MQTT ingestion gateway for ESP32-uKit Bridge. "
        "Normalizes bridge events into canonical envelope and serves them via HTTP/WebSocket.",
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        count = await store.count()
        ws_clients = len(ws_broadcaster._clients)
        return {
            "status": "ok",
            "event_count": count,
            "ws_clients": ws_clients,
        }

    @app.get("/events")
    async def list_events(
        device_id: str | None = Query(None, description="Filter by device ID"),
        event_type: str | None = Query(None, description="Filter by event type"),
        limit: int = Query(100, ge=1, le=10000, description="Max events to return"),
    ) -> dict[str, Any]:
        events = await store.query(device_id=device_id, event_type=event_type, limit=limit)
        return {"events": events, "count": len(events)}

    @app.get("/events/{event_id}")
    async def get_event(event_id: str) -> dict[str, Any]:
        event = await store.get(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return event

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": "Smart Factory IoT Gateway",
            "version": "0.1.0",
            "docs": "/docs",
        }

    return app
