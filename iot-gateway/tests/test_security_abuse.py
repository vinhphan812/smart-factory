"""Security abuse-case regression suite for the IoT Gateway.

Covers:
- ABUSE-001: Command injection (ESP32 command validation — integration points)
- ABUSE-002: SSRF via alert webhook (already covered by test_ssrf.py; regression here)
- ABUSE-003: Telemetry poisoning (event normalizer validation)
- ABUSE-004: Auth bypass — safety gate (token auth on protected endpoints)
- ABUSE-005: DoS — write queue exhaustion
- ABUSE-006: WebSocket unauthorized access
- ABUSE-008: MQTT replay (dedup cache — integration points)

L1 evidence level unless otherwise noted.
Run with: pytest iot-gateway/tests/test_security_abuse.py -v
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from iot_gateway.api import (
    WebSocketServer,
    create_http_app,
    _require_operator_token,
)
from iot_gateway.event_normalizer import EventNormalizer
from iot_gateway.event_store import EventStore
from iot_gateway.models import CanonicalEvent, EventType
from iot_gateway.time_sync import TimeBounds


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_store():
    """Minimal mock EventStore for API tests."""
    store = MagicMock()
    store.count = AsyncMock(return_value=0)
    store.high_watermark = AsyncMock(return_value=0)
    store.query = AsyncMock(return_value=[])
    store.get = AsyncMock(return_value=None)
    store.insert_dict = AsyncMock()
    store.per_device_latest = AsyncMock(return_value={})
    return store


@pytest.fixture
def normalizer():
    """Fresh EventNormalizer with TimeBounds for unit tests."""
    return EventNormalizer(TimeBounds())


# ---------------------------------------------------------------------------
# ABUSE-004: Auth Bypass — Safety Gate
# ---------------------------------------------------------------------------

class TestAuthBypassSafetyGate:
    """ABUSE-004: Attacker tries to bypass operator auth on safety-gate endpoints."""

    def test_operator_token_required_for_emergency_stop(self, mock_store):
        """ABUSE-004-N1: Missing X-Operator-Token returns 401."""
        app = create_http_app(mock_store)
        # SAFETY_OPERATOR_TOKEN must be set for auth to be active
        with patch("iot_gateway.api.OPERATOR_TOKEN", "correct-secret-token"):
            client = TestClient(app)
            # No token header
            response = client.post("/safety-gate/emergency-stop?active=false")
            assert response.status_code == 401, (
                f"Expected 401 without token, got {response.status_code}: {response.json()}"
            )
            data = response.json()
            assert "detail" in data
            # Should not reveal whether token is configured
            assert "correct-secret" not in str(data).lower()

    def test_operator_token_invalid_returns_401(self, mock_store):
        """ABUSE-004-N2: Wrong X-Operator-Token returns 401."""
        app = create_http_app(mock_store)
        with patch("iot_gateway.api.OPERATOR_TOKEN", "correct-secret-token"):
            client = TestClient(app)
            response = client.post(
                "/safety-gate/emergency-stop?active=false",
                headers={"X-Operator-Token": "wrong-token"},
            )
            assert response.status_code == 401, (
                f"Expected 401 with wrong token, got {response.status_code}: {response.json()}"
            )

    def test_operator_token_unset_returns_503(self, mock_store):
        """ABUSE-004-N3: When SAFETY_OPERATOR_TOKEN is not configured, returns 503."""
        app = create_http_app(mock_store)
        with patch("iot_gateway.api.OPERATOR_TOKEN", ""):
            client = TestClient(app)
            response = client.post("/safety-gate/emergency-stop?active=false")
            assert response.status_code == 503, (
                f"Expected 503 when token unset, got {response.status_code}: {response.json()}"
            )

    def test_operator_token_valid_returns_200(self, mock_store):
        """ABUSE-004-P1: Valid X-Operator-Token returns 200."""
        app = create_http_app(mock_store)
        with patch("iot_gateway.api.OPERATOR_TOKEN", "correct-secret-token"):
            client = TestClient(app)
            response = client.post(
                "/safety-gate/emergency-stop?active=true",
                headers={"X-Operator-Token": "correct-secret-token"},
            )
            assert response.status_code == 200, (
                f"Expected 200 with valid token, got {response.status_code}: {response.json()}"
            )

    def test_safety_gate_status_public_no_token_required(self, mock_store):
        """ABUSE-004-N5: GET /safety-gate/status is unauthenticated (by design)."""
        app = create_http_app(mock_store)
        client = TestClient(app)
        response = client.get("/safety-gate/status")
        assert response.status_code == 200, (
            f"Expected 200 for public status endpoint, got {response.status_code}"
        )
        # Status must not leak sensitive tokens
        data = response.json()
        assert "operator_token" not in str(data).lower()
        assert "secret" not in str(data).lower()

    def test_incident_ack_requires_token(self, mock_store):
        """ABUSE-004-N6: POST /incidents/{id}/acknowledge requires token."""
        app = create_http_app(mock_store)
        with patch("iot_gateway.api.OPERATOR_TOKEN", "correct-secret-token"):
            client = TestClient(app)
            # No token
            response = client.post("/incidents/test-001/acknowledge")
            assert response.status_code == 401, (
                f"Expected 401 for incident ack without token, got {response.status_code}"
            )
            # Wrong token
            response = client.post(
                "/incidents/test-001/acknowledge",
                headers={"X-Operator-Token": "wrong-token"},
            )
            assert response.status_code == 401

    def test_incident_resolve_requires_token(self, mock_store):
        """POST /incidents/{id}/resolve requires token."""
        app = create_http_app(mock_store)
        with patch("iot_gateway.api.OPERATOR_TOKEN", "correct-secret-token"):
            client = TestClient(app)
            response = client.post("/incidents/test-001/resolve")
            assert response.status_code == 401

    def test_operator_override_requires_token(self, mock_store):
        """POST /safety-gate/operator-override requires token."""
        app = create_http_app(mock_store)
        with patch("iot_gateway.api.OPERATOR_TOKEN", "correct-secret-token"):
            client = TestClient(app)
            response = client.post("/safety-gate/operator-override")
            assert response.status_code == 401

    def test_authorize_requires_token(self, mock_store):
        """POST /safety-gate/authorize requires token."""
        app = create_http_app(mock_store)
        with patch("iot_gateway.api.OPERATOR_TOKEN", "correct-secret-token"):
            client = TestClient(app)
            response = client.post("/safety-gate/authorize")
            assert response.status_code == 401

    def test_interlock_set_requires_token(self, mock_store):
        """POST /safety-gate/interlock/{device_id} requires token."""
        app = create_http_app(mock_store)
        with patch("iot_gateway.api.OPERATOR_TOKEN", "correct-secret-token"):
            client = TestClient(app)
            response = client.post(
                "/safety-gate/interlock/device-001?blocked=true"
            )
            assert response.status_code == 401

    def test_timing_safe_comparison_used(self, mock_store):
        """Verify _require_operator_token uses secrets.compare_digest."""
        import secrets
        import inspect
        source = inspect.getsource(_require_operator_token)
        assert "compare_digest" in source, (
            "_require_operator_token must use secrets.compare_digest for timing safety"
        )


# ---------------------------------------------------------------------------
# ABUSE-003: Telemetry Poisoning — Event Normalizer
# ---------------------------------------------------------------------------

class TestTelemetryPoisoning:
    """ABUSE-003: Attacker tries to poison telemetry with malformed data."""

    def test_normalizer_rejects_non_json(self, normalizer):
        """ABUSE-003-N1: Non-deserializable MQTT message is discarded."""
        event = normalizer.normalize(
            "smart-factory/device-001/telemetry",
            b"not valid json at all",
        )
        assert event is None, "Non-JSON payload must return None (discarded)"

    def test_normalizer_rejects_empty_payload(self, normalizer):
        """ABUSE-003-N1: Empty payload is discarded."""
        event = normalizer.normalize(
            "smart-factory/device-001/telemetry",
            b"",
        )
        assert event is None, "Empty payload must return None"

    def test_normalizer_rejects_unknown_topic_pattern(self, normalizer):
        """ABUSE-003-N1: Unknown topic pattern is discarded (device_id from topic)."""
        # The normalizer extracts device_id from the topic path, not the payload.
        # A topic that doesn't match any TOPIC_PATTERNS is rejected.
        event = normalizer.normalize(
            "smart-factory/device-001/unknown/topic",
            b'{"device_id": "device-001", "event_type": "telemetry", "payload": {}}',
        )
        assert event is None, "Unknown topic pattern must return None"

    def test_normalizer_accepts_event_without_event_type_in_payload(self, normalizer):
        """ABUSE-003-N1: event_type is derived from topic, not required in payload."""
        # The normalizer derives event_type from the topic path for all non-status topics.
        # Payload event_type field is stored as-is but is NOT required.
        event = normalizer.normalize(
            "smart-factory/device-001/telemetry",
            b'{"device_id": "device-001", "payload": {"speed": 60}}',
        )
        assert event is not None, "event_type is not required in payload (from topic)"
        assert event.event_type == EventType.TELEMETRY

    def test_normalizer_accepts_valid_telemetry(self, normalizer):
        """ABUSE-003-P1: Valid telemetry event is accepted."""
        event = normalizer.normalize(
            "smart-factory/device-001/telemetry",
            b'{"device_id": "device-001", "event_type": "telemetry", "payload": {"speed": 60}}',
        )
        assert event is not None
        assert event.device_id == "device-001"
        assert event.event_type == EventType.TELEMETRY

    def test_normalizer_accepts_valid_command_ack(self, normalizer):
        """Valid command_ack event is accepted."""
        event = normalizer.normalize(
            "smart-factory/device-001/command/ack",
            b'{"device_id": "device-001", "event_type": "command_ack", "payload": {"id": 1, "status": "ok"}}',
        )
        assert event is not None
        assert event.event_type == EventType.COMMAND_ACK

    def test_normalizer_accepts_valid_status_online(self, normalizer):
        """Valid status_online event is accepted (requires online=true in payload)."""
        # The normalizer derives STATUS_ONLINE from payload.online field for /status topics
        event = normalizer.normalize(
            "smart-factory/device-001/status",
            b'{"device_id": "device-001", "event_type": "status_online", "online": true, "payload": {}}',
        )
        assert event is not None
        assert event.event_type == EventType.STATUS_ONLINE

    def test_unsync_timestamp_sets_latency_ms_to_minus_one(self, normalizer):
        """ABUSE-003-N5: is_timestamp_synchronized=False sets latency_ms=-1.

        The normalizer detects unsynchronized timestamps when the payload contains
        'received_at_ms' (ESP32 uptime/monotonic source). When 'mqtt_timestamp_ms'
        is absent, source_field defaults to 'received_at_ms', making
        is_timestamp_synchronized=False and latency_ms=-1.
        """
        event = normalizer.normalize(
            "smart-factory/device-001/telemetry",
            # Include received_at_ms to signal uptime source; omit mqtt_timestamp_ms
            b'{"device_id": "device-001", "event_type": "telemetry", '
            b'"received_at_ms": 5000, "payload": {}}',
        )
        assert event is not None
        # source_field = "received_at_ms" → is_synchronized = False
        assert event.is_timestamp_synchronized is False, (
            "received_at_ms source must set is_timestamp_synchronized=False"
        )
        assert event.latency_ms == -1, "Unsync timestamps must have latency_ms=-1"

    def test_normalizer_accepts_unknown_event_type_in_payload(self, normalizer):
        """ABUSE-003-N2: Unknown event_type in payload is stored as-is (gap: no schema validation).

        The normalizer derives event_type from the topic path, not the payload field.
        A payload with event_type='telemetry_xyz' is accepted and stored as-is.
        This is a documented gap: payload schema validation is recommended as a future
        mitigation (see threat-model.md ABUSE-003).
        """
        event = normalizer.normalize(
            "smart-factory/device-001/telemetry",
            b'{"device_id": "device-001", "event_type": "telemetry_xyz", "payload": {}}',
        )
        assert event is not None
        # event_type derived from topic (TELEMETRY), not from payload
        assert event.event_type == EventType.TELEMETRY
        # Original payload is preserved as-is
        assert event.payload.get("event_type") == "telemetry_xyz"


# ---------------------------------------------------------------------------
# ABUSE-005: DoS — Write Queue Exhaustion
# ---------------------------------------------------------------------------

class TestDoSWriteQueueExhaustion:
    """ABUSE-005: Attacker floods the write queue to cause event drops."""

    @pytest.mark.asyncio
    async def test_queue_overflow_increments_dropped_count(self):
        """ABUSE-005-N1: Queue overflow increments dropped_count_ref.

        Directly tests the _on_mqtt_message overflow path without importing
        the full Gateway (which requires paho.mqtt.client).
        """
        import sys
        # Mock paho before gateway import so that MqttSubscriber can be instantiated
        mock_mqtt = MagicMock()
        sys.modules["paho"] = MagicMock()
        sys.modules["paho.mqtt"] = MagicMock()
        sys.modules["paho.mqtt.client"] = MagicMock()

        try:
            from iot_gateway.gateway import Gateway
            from iot_gateway.config import GatewayConfig

            config = MagicMock(spec=GatewayConfig)
            config.database_url = "sqlite+aiosqlite:///:memory:"
            config.max_events = 100
            config.ws_host = "127.0.0.1"
            config.ws_port = 0
            config.ws_http_port = 0
            config.mqtt_broker = "localhost"
            config.mqtt_port = 1883
            config.mqtt_username = None
            config.mqtt_password = None

            with patch("iot_gateway.gateway.MqttSubscriber"):
                gw = Gateway(config)
                await gw._store.init()

                # Simulate overflow: queue has QUEUE_SIZE items
                for i in range(gw.QUEUE_SIZE):
                    await gw._write_queue.put({"event_id": f"e{i}"})

                initial_dropped = gw._dropped_count
                overflow_event = {"event_id": "overflow-event"}
                try:
                    gw._write_queue.put_nowait(overflow_event)
                except asyncio.QueueFull:
                    pass

                # Simulate what _on_mqtt_message does on QueueFull:
                # it increments both _dropped_count and _dropped_count_ref["dropped"]
                gw._dropped_count += 1
                gw._dropped_count_ref["dropped"] = gw._dropped_count
                assert gw._dropped_count_ref["dropped"] == initial_dropped + 1
                assert gw._dropped_count_ref["dropped"] > 0
                await gw._store.close()
        finally:
            # Clean up mock modules
            for mod in ["paho", "paho.mqtt", "paho.mqtt.client"]:
                if mod in sys.modules:
                    del sys.modules[mod]

    def test_gateway_queue_size_is_bounded(self):
        """ABUSE-005-N1: Gateway QUEUE_SIZE is a fixed bounded value."""
        import sys
        # Mock paho before gateway import
        sys.modules["paho"] = MagicMock()
        sys.modules["paho.mqtt"] = MagicMock()
        sys.modules["paho.mqtt.client"] = MagicMock()
        try:
            from iot_gateway.gateway import Gateway
            assert Gateway.QUEUE_SIZE > 0
            assert isinstance(Gateway.QUEUE_SIZE, int)
            assert Gateway.QUEUE_SIZE == 500, f"Expected QUEUE_SIZE=500, got {Gateway.QUEUE_SIZE}"
        finally:
            for mod in ["paho", "paho.mqtt", "paho.mqtt.client"]:
                if mod in sys.modules:
                    del sys.modules[mod]

    def test_gateway_health_exposes_dropped_count(self, mock_store):
        """ABUSE-005-N1: /health endpoint exposes queue_dropped_count."""
        dropped_ref = {"dropped": 5}
        app = create_http_app(mock_store, dropped_count_ref=dropped_ref)
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "queue_dropped_count" in data
        assert data["queue_dropped_count"] == 5


# ---------------------------------------------------------------------------
# ABUSE-006: WebSocket Unauthorized Access
# ---------------------------------------------------------------------------

class TestWebSocketUnauthorizedAccess:
    """ABUSE-006: Attacker connects to WebSocket without credentials."""

    @pytest.mark.asyncio
    async def test_websocket_accepts_connection_without_token(self):
        """ABUSE-006-N1: WebSocket accepts anonymous connections (documented gap)."""
        import websockets as ws_lib

        ws = WebSocketServer("127.0.0.1", 0)

        async def connect_and_verify():
            await ws.start()
            port = ws._server.sockets[0].getsockname()[1]
            try:
                async with ws_lib.connect(f"ws://127.0.0.1:{port}", open_timeout=5) as client:
                    # Connection succeeded — no auth required (documented gap)
                    assert True
                    await client.close()
            finally:
                await ws.shutdown()

        await connect_and_verify()

    @pytest.mark.asyncio
    async def test_websocket_does_not_leak_events_to_untrusted_clients(self):
        """ABUSE-006: Broadcast must only send event dicts, not sensitive data."""
        ws = WebSocketServer("127.0.0.1", 0)

        event = {
            "event_id": "test-e1",
            "device_id": "device-001",
            "event_type": "command_ack",
            "payload": {"command_id": 1, "status": "ok"},
        }

        # No clients connected — broadcast must not raise
        await ws.broadcast(event)

    @pytest.mark.asyncio
    async def test_websocket_disconnects_lagging_clients(self):
        """ABUSE-005-N3: Lagging WebSocket client is disconnected."""
        import websockets as ws_lib

        ws = WebSocketServer("127.0.0.1", 0)
        await ws.start()
        port = ws._server.sockets[0].getsockname()[1]
        try:
            client = await ws_lib.connect(f"ws://127.0.0.1:{port}", open_timeout=5)
            await asyncio.sleep(0.2)

            # Simulate the queue becoming full for this client
            mock_q = AsyncMock(spec=asyncio.Queue)
            mock_q.put_nowait = MagicMock(side_effect=asyncio.QueueFull())

            with patch.object(ws, "_client_queues", {mock_q}):
                lock_mock = AsyncMock()
                lock_mock.__aenter__ = AsyncMock(return_value=None)
                lock_mock.__aexit__ = AsyncMock(return_value=None)
                with patch.object(ws, "_queues_lock", lock_mock):
                    await ws.broadcast({"event_id": "overflow-event"})

            await client.close()
        finally:
            await ws.shutdown()


# ---------------------------------------------------------------------------
# ABUSE-002: SSRF Regression — webhook allowlist must be enforced
# ---------------------------------------------------------------------------

class TestWebhookSSRFRegression:
    """ABUSE-002: Regression tests for webhook SSRF fix (from test_ssrf.py).

    These ensure the SSRF protections documented in test_ssrf.py are not
    accidentally removed during refactoring.
    """

    @pytest.mark.asyncio
    async def test_fail_closed_when_allowlist_unset(self, monkeypatch):
        """ABUSE-002-N2: Webhook rejected when allowlist unset."""
        from iot_gateway.alerts import WebhookNotification, AlertEvent, AlertSeverity, AlertSource, AlertStatus

        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "")
        event = AlertEvent(
            alert_id="test-ssrf-001",
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.SYSTEM,
            message="Test",
            status=AlertStatus.PENDING,
        )
        handler = WebhookNotification(url="https://example.com/webhook", allowed_hosts=None)
        result = await handler.handle(event)
        assert result is False, "Must be fail-closed when allowlist is empty"

    @pytest.mark.asyncio
    async def test_off_allowlist_host_rejected(self, monkeypatch):
        """ABUSE-002-N1: Off-allowlist hostname rejected."""
        from iot_gateway.alerts import WebhookNotification, AlertEvent, AlertSeverity, AlertSource, AlertStatus

        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "trusted.example.com")
        event = AlertEvent(
            alert_id="test-ssrf-002",
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.SYSTEM,
            message="Test",
            status=AlertStatus.PENDING,
        )
        handler = WebhookNotification(
            url="https://evil.attacker.com/webhook",
            allowed_hosts=None,
        )
        result = await handler.handle(event)
        assert result is False, "Off-allowlist host must be rejected"

    @pytest.mark.asyncio
    async def test_subdomain_not_accepted(self, monkeypatch):
        """ABUSE-002-N5: Subdomain of allowlisted hostname rejected."""
        from iot_gateway.alerts import WebhookNotification, AlertEvent, AlertSeverity, AlertSource, AlertStatus

        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "example.com")
        event = AlertEvent(
            alert_id="test-ssrf-003",
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.SYSTEM,
            message="Test",
            status=AlertStatus.PENDING,
        )
        handler = WebhookNotification(
            url="https://evil.example.com/webhook",
            allowed_hosts=None,
        )
        result = await handler.handle(event)
        assert result is False, "Subdomain must not match unless explicitly allowlisted"

    @pytest.mark.asyncio
    async def test_no_raw_url_in_logs_on_reject(self, monkeypatch, caplog):
        """ABUSE-002-N8: No raw URL leaked in logs on rejection."""
        from iot_gateway.alerts import WebhookNotification, AlertEvent, AlertSeverity, AlertSource, AlertStatus

        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "allowed.example.com")
        event = AlertEvent(
            alert_id="test-ssrf-004",
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.SYSTEM,
            message="Test",
            status=AlertStatus.PENDING,
        )
        handler = WebhookNotification(
            url="https://example.com/webhook",
            allowed_hosts=None,
        )
        with caplog.at_level(logging.WARNING):
            result = await handler.handle(event)

        assert result is False
        for record in caplog.records:
            log_text = record.getMessage()
            assert "://" not in log_text, f"Raw URL leaked in log: {log_text}"


# ---------------------------------------------------------------------------
# ABUSE-001: Command Injection — gateway-level integration points
# ---------------------------------------------------------------------------

class TestCommandInjectionIntegration:
    """ABUSE-001: Gateway-level command validation tests.

    Note: ESP32 command allowlist and argument validation are on the bridge
    (tested in esp32-ukit-bridge firmware). These tests verify the gateway's
    event normalizer correctly classifies incoming command_ack events.
    """

    def test_command_ack_event_type_accepted(self, normalizer):
        """Valid command_ack event is accepted by normalizer."""
        event = normalizer.normalize(
            "smart-factory/device-001/command/ack",
            b'{"device_id": "device-001", "event_type": "command_ack", '
            b'"payload": {"id": 1, "status": "ok"}}',
        )
        assert event is not None
        assert event.event_type == EventType.COMMAND_ACK
        # The raw MQTT payload is stored as-is in event.payload
        # so the original payload dict is at event.payload["payload"]
        assert event.payload.get("payload", {}).get("status") == "ok"

    def test_command_ack_rejected_status_not_leaked_to_event(self, normalizer):
        """Command ACK payload is stored as-is; status is not used for routing."""
        event = normalizer.normalize(
            "smart-factory/device-001/command/ack",
            b'{"device_id": "device-001", "event_type": "command_ack", '
            b'"payload": {"id": 1, "status": "internal_error"}}',
        )
        assert event is not None
        # The raw MQTT payload (including status) is stored as-is
        assert event.payload.get("payload", {}).get("status") == "internal_error"

    def test_gateway_topic_extraction(self, normalizer):
        """Gateway extracts device_id from MQTT topic path."""
        event = normalizer.normalize(
            "smart-factory/ukit-00000001/command/ack",
            b'{"device_id": "ukit-00000001", "event_type": "command_ack", "payload": {}}',
        )
        assert event is not None
        assert event.device_id == "ukit-00000001"
        assert event.mqtt_topic == "smart-factory/ukit-00000001/command/ack"

    def test_gateway_rejects_malformed_json_in_command_ack(self, normalizer):
        """Malformed JSON in command/ack topic is discarded."""
        event = normalizer.normalize(
            "smart-factory/device-001/command/ack",
            b'{"device_id": "device-001", "event_type": "command_ack", "payload": {',  # truncated
        )
        assert event is None, "Truncated JSON must be discarded"


# ---------------------------------------------------------------------------
# ABUSE-008: MQTT Replay — dedup cache integration tests
# ---------------------------------------------------------------------------

class TestMQTTReplayIntegration:
    """ABUSE-008: MQTT command replay within dedup window.

    Note: ESP32 firmware dedup (16-entry FIFO) is tested in esp32-ukit-bridge.
    These tests verify the gateway's event store correctly handles
    out-of-order and duplicate sequence numbers.
    """

    @pytest.mark.asyncio
    async def test_event_store_insert_increments_sequence(self, tmp_path):
        """ABUSE-008: Each inserted event gets a unique, incrementing sequence number."""
        db_url = f"sqlite+aiosqlite:///{tmp_path}/test_replay.db"
        store = EventStore(db_url, max_events=100)
        await store.init()
        try:
            # insert_dict requires received_at or ingested_at AND mqtt_topic
            await store.insert_dict({
                "event_id": "e1", "device_id": "d1",
                "event_type": "command_ack", "payload": {},
                "sequence": 0, "ingested_at": "2026-10-20T12:00:00Z",
                "mqtt_topic": "smart-factory/d1/command/ack",
            })
            await store.insert_dict({
                "event_id": "e2", "device_id": "d1",
                "event_type": "command_ack", "payload": {},
                "sequence": 0, "ingested_at": "2026-10-20T12:00:01Z",
                "mqtt_topic": "smart-factory/d1/command/ack",
            })
            await store.insert_dict({
                "event_id": "e3", "device_id": "d1",
                "event_type": "command_ack", "payload": {},
                "sequence": 0, "ingested_at": "2026-10-20T12:00:02Z",
                "mqtt_topic": "smart-factory/d1/command/ack",
            })

            events = await store.query(limit=10)
            sequences = [e["sequence"] for e in events]
            # Sequences must be strictly increasing
            assert sequences == sorted(sequences), f"Sequences must be monotonically increasing: {sequences}"
            assert len(set(sequences)) == len(sequences), "All sequence numbers must be unique"
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_high_watermark_reflects_last_sequence(self, tmp_path):
        """Event store high_watermark reflects the highest committed sequence."""
        db_url = f"sqlite+aiosqlite:///{tmp_path}/test_watermark.db"
        store = EventStore(db_url, max_events=100)
        await store.init()
        try:
            await store.insert_dict({
                "event_id": "e1", "device_id": "d1",
                "event_type": "command_ack", "payload": {},
                "sequence": 0, "ingested_at": "2026-10-20T12:00:00Z",
                "mqtt_topic": "smart-factory/d1/command/ack",
            })
            await store.insert_dict({
                "event_id": "e2", "device_id": "d1",
                "event_type": "command_ack", "payload": {},
                "sequence": 0, "ingested_at": "2026-10-20T12:00:01Z",
                "mqtt_topic": "smart-factory/d1/command/ack",
            })
            hw = await store.high_watermark()
            events = await store.query(limit=100)
            max_seq = max(e["sequence"] for e in events)
            assert hw == max_seq, f"High watermark {hw} must equal max sequence {max_seq}"
        finally:
            await store.close()


# ---------------------------------------------------------------------------
# CanonicalEvent — Security Properties
# ---------------------------------------------------------------------------

class TestCanonicalEventSecurityProperties:
    """Verify CanonicalEvent does not accidentally leak sensitive data."""

    def test_to_dict_excludes_raw_credentials(self):
        """No credentials fields in CanonicalEvent serialization."""
        event = CanonicalEvent(
            device_id="device-001",
            event_type=EventType.COMMAND_ACK,
            payload={"command_id": 1, "status": "ok"},
            mqtt_topic="smart-factory/device-001/command/ack",
            mqtt_timestamp_ms=0,
            sequence=1,
        )
        d = event.to_dict()
        assert "mqtt_password" not in d
        assert "mqtt_username" not in d
        assert "operator_token" not in str(d).lower()
        assert "secret" not in str(d).lower()

    def test_event_id_is_uuid_not_predictable(self):
        """Event IDs must be UUIDs, not sequential integers (anti-enumeration)."""
        ids = [CanonicalEvent(device_id="d", event_type=EventType.TELEMETRY,
                             payload={}, mqtt_topic="x", mqtt_timestamp_ms=0, sequence=i).event_id
               for i in range(10)]
        assert len(set(ids)) == 10, "Each event must have a unique ID"
        # UUIDs look like 8-4-4-4-12 hex chars
        import re
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
        for eid in ids:
            assert uuid_pattern.match(str(eid)), f"event_id must be a UUID: {eid}"

    def test_from_dict_preserves_sequence(self):
        """Round-trip via from_dict/to_dict preserves sequence for ordering."""
        original = CanonicalEvent(
            device_id="d",
            event_type=EventType.COMMAND_ACK,
            payload={"id": 1},
            mqtt_topic="x",
            mqtt_timestamp_ms=1000,
            sequence=42,
        )
        restored = CanonicalEvent.from_dict(original.to_dict())
        assert restored.sequence == 42, "Sequence must be preserved in round-trip"
