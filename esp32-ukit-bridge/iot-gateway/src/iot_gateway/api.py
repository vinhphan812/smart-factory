"""WebSocket and HTTP API servers for the gateway."""

import asyncio
import json
import logging
from typing import Any

import websockets
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .event_store import EventStore

logger = logging.getLogger(__name__)


class EventQuery(BaseModel):
    device_id: str | None = None
    event_type: str | None = None
    limit: int = 100


class WebSocketServer:
    """Broadcasts events to all connected WebSocket clients.

    Each client has its own outbound queue so that slow clients do not block
    fast clients and every connected client receives every broadcast event.

    Uses the ``websockets`` library (RFC-6455) so Unity, browsers, and any
    standards-compliant WebSocket client can connect.
    """

    MAX_QUEUE_PER_CLIENT = 64

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        # Per-client queue set — each client task pulls from its own queue
        self._client_queues: set[asyncio.Queue[str]] = set()
        self._queues_lock: asyncio.Lock = asyncio.Lock()
        self._server: websockets.Server | None = None

    async def start(self) -> None:
        """Start the WebSocket server on self._host:self._port."""
        # Define the handler as a lambda so websockets.serve receives a regular
        # callable, not a bound method whose return value (coroutine) might not
        # be awaited correctly on all Python/asyncio versions.
        async def handler(conn: websockets.ServerConnection) -> None:
            client_queue: asyncio.Queue[str] = asyncio.Queue(
                maxsize=self.MAX_QUEUE_PER_CLIENT
            )
            async with self._queues_lock:
                self._client_queues.add(client_queue)
            addr = conn.remote_address
            logger.info("WS client connected: %s", addr)
            try:
                while True:
                    try:
                        # Timeout allows the event loop to process WebSocket frames
                        # (close handshake, keepalives) so ConnectionClosed is raised.
                        data = await asyncio.wait_for(
                            client_queue.get(), timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        # No message in 5 s — yield to allow websockets internals
                        # to run (ping/pong, close detection). Re-check connection.
                        continue
                    await conn.send(data)
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                async with self._queues_lock:
                    self._client_queues.discard(client_queue)
                logger.info("WS client disconnected: %s", addr)

        self._server = await websockets.serve(
            handler,
            self._host,
            self._port,
        )
        logger.info("WebSocket server started on %s:%d", self._host, self._port)

    async def broadcast(self, event_dict: dict[str, Any]) -> None:
        """Fan-out an event to every connected client.

        Serializes the event once and enqueues the string in each client's
        individual queue. Slow clients are isolated; fast clients proceed
        immediately.
        """
        payload = json.dumps(event_dict, default=str)
        async with self._queues_lock:
            queues = list(self._client_queues)
        if not queues:
            return
        await asyncio.gather(
            *(q.put(payload) for q in queues),
            return_exceptions=True,
        )

    async def shutdown(self) -> None:
        """Close the WebSocket server gracefully."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()


def create_http_app(store: EventStore) -> FastAPI:
    """Build FastAPI app with REST endpoints backed by the event store."""

    app = FastAPI(
        title="Smart Factory IoT Gateway API",
        version="0.1.0",
        description="MQTT ingestion gateway for ESP32-uKit Bridge.",
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        count = await store.count()
        return {"status": "ok", "event_count": count}

    @app.get("/events")
    async def list_events(
        device_id: str | None = Query(None, description="Filter by device ID"),
        event_type: str | None = Query(None, description="Filter by event type"),
        limit: int = Query(100, ge=1, le=10000, description="Max events to return"),
    ) -> dict[str, Any]:
        events = await store.query(
            device_id=device_id, event_type=event_type, limit=limit
        )
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
