"""Pytest configuration and shared fixtures for iot-gateway tests."""

import asyncio
import os
from typing import Generator

import pytest

# Test-only auth configuration. Must be set BEFORE iot_gateway.api (and
# therefore iot_gateway.auth) is imported, because auth.py captures
# AUTH_TEST_MODE and JWT_SECRET at module import time. Without this the
# test users are never provisioned and USERS_DB stays empty.
os.environ.setdefault("AUTH_TEST_MODE", "1")
os.environ.setdefault(
    "JWT_SECRET",
    "test-secret-key-for-testing-purposes-minimum-32-characters-long",
)

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
async def ws_server(tmp_path) -> "WebSocketServer":
    """Live WebSocketServer on a random port (for integration tests)."""
    from iot_gateway.api import WebSocketServer

    ws = WebSocketServer("127.0.0.1", 0)
    await ws.start()
    try:
        yield ws
    finally:
        await ws.shutdown()

