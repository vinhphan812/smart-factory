"""Pytest configuration and shared fixtures for iot-gateway tests."""

import asyncio
from typing import Generator

import pytest

from iot_gateway.api import WebSocketServer
from iot_gateway.event_store import EventStore


@pytest.fixture
def database_url(tmp_path) -> str:
    """Temp SQLite database per test."""
    db_path = tmp_path / "test.db"
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
async def store(database_url: str) -> Generator[EventStore, None, None]:
    """Fresh EventStore for each test."""
    s = EventStore(database_url, max_events=1000)
    await s.init()
    try:
        yield s
    finally:
        await s.close()


@pytest.fixture
async def ws_server(database_url) -> Generator["WebSocketServer", None, None]:
    """Live WebSocketServer backed by a temp SQLite store (used by API tests)."""
    from iot_gateway.api import WebSocketServer
    store = EventStore(database_url, max_events=1000)
    await store.init()
    ws = WebSocketServer("127.0.0.1", 0)
    await ws.start()
    try:
        yield ws
    finally:
        await ws.shutdown()
        await store.close()

