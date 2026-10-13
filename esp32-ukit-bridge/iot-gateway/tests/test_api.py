"""Tests for FastAPI REST endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from iot_gateway.api import create_http_app
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


def test_health_returns_event_count_and_ws_clients() -> None:
    """GET /health returns status, event_count, and ws_clients."""
    mock_store = MagicMock()
    mock_store.count = AsyncMock(return_value=42)
    mock_ws = MagicMock()
    mock_ws._clients = set()

    app = create_http_app(mock_store, mock_ws)
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["event_count"] == 42
    assert data["ws_clients"] == 0


def test_root_returns_service_info() -> None:
    """GET / returns service name, version, docs link."""
    mock_store = MagicMock()
    mock_ws = MagicMock()
    mock_ws._clients = set()
    app = create_http_app(mock_store, mock_ws)
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
    mock_ws = MagicMock()
    mock_ws._clients = set()
    app = create_http_app(mock_store, mock_ws)
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
    mock_ws = MagicMock()
    mock_ws._clients = set()
    app = create_http_app(mock_store, mock_ws)
    client = TestClient(app)

    client.get("/events?device_id=device-42")
    mock_store.query.assert_called_once_with(device_id="device-42", event_type=None, limit=100)


def test_list_events_filters_by_event_type() -> None:
    """GET /events?event_type=... passes filter to store."""
    mock_store = AsyncMock()
    mock_store.query = AsyncMock(return_value=[])
    mock_ws = MagicMock()
    mock_ws._clients = set()
    app = create_http_app(mock_store, mock_ws)
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
    mock_ws = MagicMock()
    mock_ws._clients = set()
    app = create_http_app(mock_store, mock_ws)
    client = TestClient(app)

    response = client.get("/events/e1")
    assert response.status_code == 200
    assert response.json()["event_id"] == "e1"


def test_get_event_404_when_not_found() -> None:
    """GET /events/{unknown_id} returns 404."""
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=None)
    mock_ws = MagicMock()
    mock_ws._clients = set()
    app = create_http_app(mock_store, mock_ws)
    client = TestClient(app)

    response = client.get("/events/unknown-id")
    assert response.status_code == 404


def test_list_events_enforces_limit_max() -> None:
    """GET /events?limit=99999 is rejected (max 10000)."""
    mock_store = AsyncMock()
    mock_store.query = AsyncMock(return_value=[])
    mock_ws = MagicMock()
    mock_ws._clients = set()
    app = create_http_app(mock_store, mock_ws)
    client = TestClient(app)

    response = client.get("/events?limit=99999")
    assert response.status_code == 422  # FastAPI validation error
