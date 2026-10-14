"""Tests for the CanonicalEvent model and related types."""

import uuid

from iot_gateway.models import CanonicalEvent, EventType


class TestCanonicalEvent:
    """Tests for CanonicalEvent dataclass."""

    def test_event_type_enum_values(self) -> None:
        """All expected event types are present in the enum."""
        assert EventType.COMMAND_ACK.value == "command_ack"
        assert EventType.STATUS_ONLINE.value == "status_online"
        assert EventType.STATUS_OFFLINE.value == "status_offline"
        assert EventType.TELEMETRY.value == "telemetry"
        assert EventType.HEARTBEAT.value == "heartbeat"

    def test_to_dict_returns_serializable_dict(self) -> None:
        """to_dict() returns a dict with only JSON-serializable values."""
        event = CanonicalEvent(
            event_id=uuid.uuid4(),
            device_id="device-1",
            event_type=EventType.COMMAND_ACK,
            payload={"status": "ok"},
            mqtt_topic="smart-factory/device-1/command/ack",
            mqtt_timestamp_ms=1234567890000,
            ingested_at="2026-10-13T12:00:00Z",
            sequence=1,
        )
        d = event.to_dict()
        # Should be JSON serializable
        import json
        json.dumps(d)

    def test_event_id_is_uuid_string(self) -> None:
        """event_id is a UUID string in to_dict."""
        event = CanonicalEvent(
            event_id=uuid.uuid4(),
            device_id="device-1",
            event_type=EventType.STATUS_ONLINE,
            payload={"online": True},
            mqtt_topic="smart-factory/device-1/status",
            mqtt_timestamp_ms=0,
            ingested_at="2026-10-13T12:00:00Z",
            sequence=1,
        )
        d = event.to_dict()
        # Should not raise — uuid is converted to string by json.dumps default
        import json
        s = json.dumps(d)
        parsed = json.loads(s)
        assert "event_id" in parsed
        # Verify it's a valid UUID string
        uuid.UUID(parsed["event_id"])

    def test_payload_preserved(self) -> None:
        """Original payload dict is stored and returned as-is."""
        payload = {"status": "ok", "code": 0, "nested": {"key": "value"}}
        event = CanonicalEvent(
            event_id=uuid.uuid4(),
            device_id="device-1",
            event_type=EventType.COMMAND_ACK,
            payload=payload,
            mqtt_topic="smart-factory/device-1/command/ack",
            mqtt_timestamp_ms=0,
            ingested_at="2026-10-13T12:00:00Z",
            sequence=1,
        )
        d = event.to_dict()
        assert d["payload"] == payload
