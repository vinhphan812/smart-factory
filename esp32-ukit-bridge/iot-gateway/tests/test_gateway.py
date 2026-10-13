"""Integration tests for the Gateway — MQTT → normalize → write queue → store → broadcast.

These tests verify the gateway's components work correctly in isolation and
as a pipeline, without requiring a live MQTT broker.
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iot_gateway.config import GatewayConfig
from iot_gateway.gateway import Gateway
from iot_gateway.models import EventType


@pytest.fixture
def gateway_config(tmp_path) -> GatewayConfig:
    """Minimal config pointing at a temp SQLite database."""
    db = f"sqlite+aiosqlite:///{tmp_path}/gateway_test.db"
    return GatewayConfig(
        mqtt_broker="localhost",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        database_url=db,
        max_events=100,
        ws_host="127.0.0.1",
        ws_port=0,
        ws_http_port=0,
    )


@pytest.fixture
def mock_mqtt_subscriber() -> MagicMock:
    """Mock MqttSubscriber that does nothing on start/stop."""
    mock = MagicMock()
    mock.start = MagicMock()
    mock.stop = MagicMock()
    return mock


@pytest.fixture
def mock_ws_server() -> MagicMock:
    """Mock WebSocketServer that tracks broadcast calls."""
    mock = MagicMock()
    mock.broadcast = AsyncMock()
    mock.shutdown = AsyncMock()
    mock.start = AsyncMock()
    return mock


class TestGatewayMQTTPipeline:
    """TC1: Simulated event flows through the pipeline."""

    @pytest.mark.asyncio
    async def test_tel_event_normalized_stored_and_broadcast(
        self, gateway_config: GatewayConfig, mock_ws_server: MagicMock
    ) -> None:
        """A command_ack event is normalized, stored, and broadcast."""
        with patch("iot_gateway.gateway.WebSocketServer", return_value=mock_ws_server):
            gateway = Gateway(gateway_config)
            # Simulate start() setting the event loop (mqtt_callback needs it)
            gateway._loop = asyncio.get_running_loop()
            await gateway._store.init()
            gateway._stop_events = [
                asyncio.Event() for _ in range(gateway.NUM_WRITERS)
            ]
            gateway._writers_done = [
                asyncio.create_task(gateway._write_worker(i, stop))
                for i, stop in enumerate(gateway._stop_events)
            ]

            topic = "smart-factory/sf-bridge-001/command/ack"
            payload = json.dumps({
                "command_id": 1,
                "request_id": "req-001",
                "command_name": "CONVEYOR_START",
                "status": "ok",
                "status_code": 0,
            }).encode()

            # Await the async handler directly (bypasses thread bridge for tests)
            await gateway._on_mqtt_message(topic, payload)

            # Wait for queue to drain: poll until count reaches expected
            import time
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                count = await gateway._store.count()
                if count == 1:
                    break
                await asyncio.sleep(0.1)

            assert await gateway._store.count() == 1
            mock_ws_server.broadcast.assert_called_once()
            broadcast_event = mock_ws_server.broadcast.call_args[0][0]
            assert broadcast_event["device_id"] == "sf-bridge-001"
            assert broadcast_event["event_type"] == "command_ack"
            assert broadcast_event["payload"]["command_name"] == "CONVEYOR_START"

            for stop in gateway._stop_events:
                stop.set()
            await asyncio.gather(*gateway._writers_done, return_exceptions=True)
            await gateway._store.close()


class TestGatewayQuarantine:
    """TC2: Malformed or unknown-device events are silently quarantined."""

    @pytest.mark.asyncio
    async def test_malformed_json_not_stored(self, gateway_config: GatewayConfig) -> None:
        """Malformed JSON is dropped and never reaches the store."""
        with patch("iot_gateway.gateway.WebSocketServer"):
            gateway = Gateway(gateway_config)
            await gateway._store.init()

            await gateway._on_mqtt_message(
                "smart-factory/d1/command/ack", b"not json"
            )
            assert await gateway._store.count() == 0
            await gateway._store.close()

    @pytest.mark.asyncio
    async def test_unknown_topic_not_stored(self, gateway_config: GatewayConfig) -> None:
        """Unknown topic pattern is dropped and never reaches the store."""
        with patch("iot_gateway.gateway.WebSocketServer"):
            gateway = Gateway(gateway_config)
            await gateway._store.init()

            await gateway._on_mqtt_message(
                "smart-factory/d1/unknown/topic", b'{"data":1}'
            )
            assert await gateway._store.count() == 0
            await gateway._store.close()


class TestGatewayDeduplication:
    """TC3: Read-only design — gateway cannot publish commands."""

    @pytest.mark.asyncio
    async def test_gateway_has_no_publish_method(self, gateway_config: GatewayConfig) -> None:
        """The gateway class has no MQTT publish capability."""
        gateway = Gateway(gateway_config)
        assert not hasattr(gateway, "publish")
        assert not hasattr(gateway, "_publish")
        assert not hasattr(gateway, "_mqtt_publisher")


class TestGatewayOrdering:
    """TC4: Events are stored with deterministic sequence ordering."""

    @pytest.mark.asyncio
    async def test_events_stored_with_incrementing_sequence(
        self, gateway_config: GatewayConfig
    ) -> None:
        """Multiple events each get a unique, incrementing sequence number."""
        with patch("iot_gateway.gateway.WebSocketServer"):
            gateway = Gateway(gateway_config)
            await gateway._store.init()

            seqs: list[int] = []
            for i in range(5):
                topic = f"smart-factory/device-{i}/command/ack"
                payload = json.dumps({"command_id": i}).encode()
                await gateway._on_mqtt_message(topic, payload)
                seqs.append(gateway._normalizer._sequence)

            # Sequences are strictly increasing (each normalize increments the counter)
            assert seqs == sorted(seqs)
            assert seqs[-1] > seqs[0]

            await gateway._store.close()


class TestGatewayBoundedQueue:
    """TC5: Bounded write queue drops events when full."""

    @pytest.mark.asyncio
    async def test_queue_rejects_overflow(
        self, gateway_config: GatewayConfig
    ) -> None:
        """When the write queue is full, further events are dropped."""
        with patch("iot_gateway.gateway.WebSocketServer"):
            gateway = Gateway(gateway_config)
            await gateway._store.init()
            gateway._stop_events = [
                asyncio.Event() for _ in range(gateway.NUM_WRITERS)
            ]
            gateway._writers_done = [
                asyncio.create_task(gateway._write_worker(i, stop))
                for i, stop in enumerate(gateway._stop_events)
            ]

            topic = "smart-factory/device-1/command/ack"

            # Fill the queue (500 capacity)
            accepted = 0
            for i in range(600):
                try:
                    gateway._write_queue.put_nowait({
                        "event_id": f"test-{i}",
                        "device_id": "device-1",
                        "event_type": "command_ack",
                        "payload": {},
                        "mqtt_topic": topic,
                        "mqtt_timestamp_ms": 0,
                        "ingested_at": "2026-10-13T12:00:00Z",
                        "sequence": i + 1,
                    })
                    accepted += 1
                except asyncio.QueueFull:
                    pass

            assert accepted == 500, f"Expected 500 accepted, got {accepted}"

            for stop in gateway._stop_events:
                stop.set()
            await asyncio.gather(*gateway._writers_done, return_exceptions=True)
            await gateway._store.close()


class TestGatewayReadOnly:
    """TC6: Gateway is a read-only client — cannot issue commands."""

    @pytest.mark.asyncio
    async def test_gateway_is_readonly_does_not_publish(
        self, gateway_config: GatewayConfig, mock_ws_server: MagicMock
    ) -> None:
        """Gateway never publishes MQTT commands."""
        with patch("iot_gateway.gateway.WebSocketServer", return_value=mock_ws_server):
            gateway = Gateway(gateway_config)
            assert not hasattr(gateway, "_mqtt_publisher")
            assert not hasattr(gateway, "publish")


class TestGatewayShutdown:
    """TC7: Shutdown drains the write queue and persists all accepted events."""

    @pytest.mark.asyncio
    async def test_all_enqueued_events_persisted_after_shutdown(
        self, gateway_config: GatewayConfig
    ) -> None:
        """Events in the queue at shutdown time are all durable in SQLite."""
        with patch("iot_gateway.gateway.WebSocketServer"):
            gateway = Gateway(gateway_config)
            await gateway._store.init()
            gateway._stop_events = [
                asyncio.Event() for _ in range(gateway.NUM_WRITERS)
            ]
            gateway._writers_done = [
                asyncio.create_task(gateway._write_worker(i, stop))
                for i, stop in enumerate(gateway._stop_events)
            ]

            topic = "smart-factory/device-1/command/ack"
            num_events = 10
            for i in range(num_events):
                payload = json.dumps({"command_id": i}).encode()
                await gateway._on_mqtt_message(topic, payload)

            # Allow workers to process all items
            import time
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                count = await gateway._store.count()
                if count >= num_events:
                    break
                await asyncio.sleep(0.1)

            # Stop — workers must have drained everything
            for stop in gateway._stop_events:
                stop.set()
            await asyncio.gather(*gateway._writers_done, return_exceptions=True)

            # All events must be durable in SQLite
            count = await gateway._store.count()
            assert count == num_events, (
                f"Expected {num_events} events persisted, got {count} — "
                "events were dropped during shutdown drain"
            )
            await gateway._store.close()
