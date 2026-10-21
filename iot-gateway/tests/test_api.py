"""Tests for FastAPI REST endpoints and WebSocket broadcast."""

import asyncio
import json
import websockets
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from iot_gateway.api import WebSocketServer, create_http_app
from iot_gateway.models import CanonicalEvent, EventType


def _make_event(event_id: str = "e1", device_id: str = "d1",
                event_type: EventType = EventType.COMMAND_ACK) -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        device_id=device_id,
        event_type=event_type,
        payload={"command_id": 1},
        mqtt_topic=f"smart-factory/{device_id}/command/ack",
        mqtt_timestamp_ms=0,
        ingested_at="2026-10-13T12:00:00Z",
        sequence=1,
    )


def test_health_returns_event_count() -> None:
    """GET /health returns status and event_count."""
    mock_store = MagicMock()
    mock_store.count = AsyncMock(return_value=42)
    mock_store.high_watermark = AsyncMock(return_value=0)
    app = create_http_app(mock_store)
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["event_count"] == 42


def test_root_returns_service_info() -> None:
    """GET / returns service name, version, docs link."""
    mock_store = MagicMock()
    app = create_http_app(mock_store)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Smart Factory IoT Gateway"
    assert data["version"] == "0.1.0"
    assert data["docs"] == "/docs"


def test_list_events_returns_event_list() -> None:
    """GET /events returns a list of events."""
    mock_store = AsyncMock()
    mock_store.query = AsyncMock(return_value=[
        {"event_id": "e1", "device_id": "d1", "event_type": "command_ack", "sequence": 1},
        {"event_id": "e2", "device_id": "d2", "event_type": "status_online", "sequence": 2},
    ])
    app = create_http_app(mock_store)
    client = TestClient(app)

    response = client.get("/events")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["events"]) == 2


def test_list_events_filters_by_device_id() -> None:
    """GET /events?device_id=... passes filter to store."""
    mock_store = AsyncMock()
    mock_store.query = AsyncMock(return_value=[])
    app = create_http_app(mock_store)
    client = TestClient(app)

    client.get("/events?device_id=device-42")
    mock_store.query.assert_called_once_with(device_id="device-42", event_type=None, limit=100)


def test_list_events_filters_by_event_type() -> None:
    """GET /events?event_type=... passes filter to store."""
    mock_store = AsyncMock()
    mock_store.query = AsyncMock(return_value=[])
    app = create_http_app(mock_store)
    client = TestClient(app)

    client.get("/events?event_type=status_offline")
    mock_store.query.assert_called_once_with(device_id=None, event_type="status_offline", limit=100)


def test_get_event_returns_event() -> None:
    """GET /events/{event_id} returns the event or 404."""
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value={
        "event_id": "e1",
        "device_id": "d1",
        "event_type": "command_ack",
    })
    app = create_http_app(mock_store)
    client = TestClient(app)

    response = client.get("/events/e1")
    assert response.status_code == 200
    assert response.json()["event_id"] == "e1"


def test_get_event_404_when_not_found() -> None:
    """GET /events/{unknown_id} returns 404."""
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=None)
    app = create_http_app(mock_store)
    client = TestClient(app)

    response = client.get("/events/unknown-id")
    assert response.status_code == 404


def test_list_events_enforces_limit_max() -> None:
    """GET /events?limit=99999 is rejected (max 10000)."""
    mock_store = AsyncMock()
    mock_store.query = AsyncMock(return_value=[])
    app = create_http_app(mock_store)
    client = TestClient(app)

    response = client.get("/events?limit=99999")
    assert response.status_code == 422  # FastAPI validation error


class TestWebSocketBroadcast:
    """Tests for WebSocketServer broadcast to multiple simultaneous clients."""

    def _run_async(self, coro):
        """Run a coroutine in a new event loop (Python 3.10+ compatible)."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_broadcast_serializes_event_to_all_client_queues(self) -> None:
        """broadcast() serializes an event once and enqueues it in every client queue.

        Verifies the fan-out logic: each queue receives the same JSON string
        (not double-encoded). Uses put_nowait so a full queue does not block.
        """
        from iot_gateway.api import WebSocketServer

        ws = WebSocketServer("127.0.0.1", 0)

        # Create three mock queues (put_nowait succeeds for all)
        mock_q1: asyncio.Queue[str] = AsyncMock(spec=asyncio.Queue)
        mock_q2: asyncio.Queue[str] = AsyncMock(spec=asyncio.Queue)
        mock_q3: asyncio.Queue[str] = AsyncMock(spec=asyncio.Queue)

        with patch.object(ws, "_client_queues", {mock_q1, mock_q2, mock_q3}):
            lock_mock = AsyncMock()
            lock_mock.__aenter__ = AsyncMock(return_value=None)
            lock_mock.__aexit__ = AsyncMock(return_value=None)
            with patch.object(ws, "_queues_lock", lock_mock):
                event = {"event_id": "e1", "device_id": "d1"}
                self._run_async(ws.broadcast(event))

        # Each queue must have received exactly one item via put_nowait
        assert mock_q1.put_nowait.call_count == 1
        assert mock_q2.put_nowait.call_count == 1
        assert mock_q3.put_nowait.call_count == 1

        # All three must have received the same JSON string (not double-encoded)
        payloads = [
            mock_q1.put_nowait.call_args[0][0],
            mock_q2.put_nowait.call_args[0][0],
            mock_q3.put_nowait.call_args[0][0],
        ]
        assert all(p == payloads[0] for p in payloads)
        assert json.loads(payloads[0]) == event

    def test_broadcast_empty_when_no_clients(self) -> None:
        """broadcast() returns without enqueuing when no clients are connected."""
        from iot_gateway.api import WebSocketServer

        ws = WebSocketServer("127.0.0.1", 0)
        lock_mock = AsyncMock()
        lock_mock.__aenter__ = AsyncMock(return_value=None)
        lock_mock.__aexit__ = AsyncMock(return_value=None)

        with patch.object(ws, "_client_queues", set()):
            with patch.object(ws, "_queues_lock", lock_mock):
                self._run_async(ws.broadcast({"event_id": "orphan"}))

        # Lock was acquired but no queue.put_nowait was called
        lock_mock.__aenter__.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_no_clients_does_not_raise(self) -> None:
        """broadcast() is safe to call with zero connected clients."""
        ws = WebSocketServer("127.0.0.1", 0)
        await ws.start()
        try:
            # No clients connected — should not raise
            await ws.broadcast({"event_id": "orphan"})
        finally:
            await ws.shutdown()

    def test_broadcast_disconnects_lagging_clients(self) -> None:
        """A full client queue causes broadcast() to disconnect that client.

        put_nowait raises QueueFull when the client's outbound buffer is
        saturated (e.g. network stall). Instead of blocking the write worker,
        broadcast() removes the lagging client from the registry so fast clients
        are not held up.
        """
        from iot_gateway.api import WebSocketServer

        ws = WebSocketServer("127.0.0.1", 0)

        # Two mock queues: one normal, one already full
        mock_q1: asyncio.Queue[str] = AsyncMock(spec=asyncio.Queue)
        mock_q1.put_nowait = MagicMock()  # will succeed
        mock_q2: asyncio.Queue[str] = AsyncMock(spec=asyncio.Queue)
        mock_q2.put_nowait = MagicMock(
            side_effect=asyncio.QueueFull()
        )  # simulates a stalled client

        # Pin the set to a local name before patching — patch restores the
        # original attribute value on exit, so we need a reference to the
        # patched set to inspect it afterwards.
        patched_set = {mock_q1, mock_q2}
        with patch.object(ws, "_client_queues", patched_set):
            lock_mock = AsyncMock()
            lock_mock.__aenter__ = AsyncMock(return_value=None)
            lock_mock.__aexit__ = AsyncMock(return_value=None)
            with patch.object(ws, "_queues_lock", lock_mock):
                self._run_async(ws.broadcast({"event_id": "e1"}))

        # Q1 received the event; Q2 raised QueueFull and was dropped
        mock_q1.put_nowait.assert_called_once()
        mock_q2.put_nowait.assert_called_once()
        # Q2 (lagging) must have been removed from the set
        assert mock_q2 not in patched_set
        # Q1 (healthy) must still be registered
        assert mock_q1 in patched_set

    @pytest.mark.asyncio
    async def test_handler_unregisters_client_on_close(self) -> None:
        """Handler removes client queue when the connection closes.

        The handler checks conn.close_code on each queue timeout (1 s).  When the
        client disconnects, close_code becomes non-None; the handler breaks out of
        its loop and the finally-block removes the queue.  We verify this by
        closing the client and waiting long enough for the timeout to fire.
        """
        import websockets
        from iot_gateway.api import WebSocketServer

        ws = WebSocketServer("127.0.0.1", 0)
        await ws.start()
        port = ws._server.sockets[0].getsockname()[1]

        client = await websockets.connect(
            f"ws://127.0.0.1:{port}", open_timeout=5
        )
        await asyncio.sleep(0.3)
        assert len(ws._client_queues) == 1

        # Close the client — the server's conn.close_code becomes non-None.
        # The handler detects this on its next queue timeout (≤ 1 s) and exits.
        await client.close()
        await asyncio.sleep(1.5)

        assert len(ws._client_queues) == 0
        await ws.shutdown()


