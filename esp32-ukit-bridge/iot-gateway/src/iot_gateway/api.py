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
            close_event = asyncio.Event()

            async def wait_for_close() -> None:
                """Monitor the connection and signal close when the client departs."""
                try:
                    await conn.wait_closed()
                except Exception:
                    pass
                close_event.set()

            close_monitor = asyncio.create_task(wait_for_close())

            async with self._queues_lock:
                self._client_queues.add(client_queue)
            addr = conn.remote_address
            logger.info("WS client connected: %s", addr)
            try:
                while True:
                    # Wait for either the next queued message or a close signal.
                    # close_event fires when the client disconnects, so we detect
                    # departure promptly without needing long timeouts.
                    done, _ = await asyncio.wait(
                        {
                            asyncio.create_task(client_queue.get()),
                            asyncio.create_task(close_event.wait()),
                        },
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if close_monitor in done:
                        # Connection closed — break so finally runs and queue is unregistered.
                        break
                    # A queued message arrived — cancel the close monitor and send it.
                    # Cancelling is safe: wait_closed() either returned (close_event
                    # already set) or hasn't returned yet; either way the event is done.
                    close_monitor.cancel()
                    try:
                        await close_monitor
                    except asyncio.CancelledError:
                        pass
                    # Get the result from the queue task (the other one in done)
                    queue_task = next(t for t in done if t is not close_monitor)
                    data = queue_task.result()
                    await conn.send(data)
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                close_monitor.cancel()
                try:
                    await close_monitor
                except asyncio.CancelledError:
                    pass
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
        individual queue. Uses put_nowait so a full client queue does not block
        the calling write worker — the lagging client is disconnected instead.
        """
        payload = json.dumps(event_dict, default=str)
        async with self._queues_lock:
            queues = list(self._client_queues)
        if not queues:
            return

        lagging: list[asyncio.Queue[str]] = []
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                lagging.append(q)

        if lagging:
            async with self._queues_lock:
                for q in lagging:
                    self._client_queues.discard(q)
            logger.warning(
                "Dropped %d lagging WebSocket client(s) — outbound queue full "
                "(maxsize=%d)",
                len(lagging),
                self.MAX_QUEUE_PER_CLIENT,
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
