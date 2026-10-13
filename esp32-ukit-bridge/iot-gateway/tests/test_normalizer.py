"""Tests for the event normalizer."""

import json

import pytest

from iot_gateway.event_normalizer import EventNormalizer
from iot_gateway.models import EventType


class TestEventNormalizer:
    """Test that raw MQTT payloads are normalized to CanonicalEvent correctly."""

    def setup_method(self) -> None:
        self.n = EventNormalizer()

    def test_command_ack_valid(self) -> None:
        """Valid command/ack payload → COMMAND_ACK event."""
        topic = "smart-factory/sf-bridge-001/command/ack"
        payload = json.dumps({
            "command_id": 1,
            "request_id": "test-001",
            "command_name": "CONVEYOR_START",
            "status": "ok",
            "status_code": 0,
            "timestamp": "2026-10-13T12:00:00Z",
        }).encode()
        event = self.n.normalize(topic, payload)
        assert event is not None
        assert event.event_type == EventType.COMMAND_ACK
        assert event.device_id == "sf-bridge-001"
        assert event.payload["status"] == "ok"
        assert event.payload["command_name"] == "CONVEYOR_START"

    def test_status_online(self) -> None:
        """status topic with online=true → STATUS_ONLINE event."""
        topic = "smart-factory/sf-bridge-001/status"
        payload = json.dumps({"online": True}).encode()
        event = self.n.normalize(topic, payload)
        assert event is not None
        assert event.event_type == EventType.STATUS_ONLINE
        assert event.device_id == "sf-bridge-001"

    def test_status_offline(self) -> None:
        """status topic with online=false → STATUS_OFFLINE event."""
        topic = "smart-factory/sf-bridge-001/status"
        payload = json.dumps({"online": False}).encode()
        event = self.n.normalize(topic, payload)
        assert event is not None
        assert event.event_type == EventType.STATUS_OFFLINE

    def test_invalid_json_returns_none(self) -> None:
        """Malformed JSON → None (log warning, no exception)."""
        topic = "smart-factory/sf-bridge-001/command/ack"
        payload = b"not valid json {"
        event = self.n.normalize(topic, payload)
        assert event is None

    def test_unknown_topic_returns_none(self) -> None:
        """Unknown topic pattern → None."""
        topic = "smart-factory/sf-bridge-001/unknown"
        payload = json.dumps({"data": 1}).encode()
        event = self.n.normalize(topic, payload)
        assert event is None

    def test_multiple_events_increment_sequence(self) -> None:
        """Each normalized event gets a unique, incrementing sequence."""
        topic = "smart-factory/device-1/command/ack"
        payload = json.dumps({"command_id": 1}).encode()
        e1 = self.n.normalize(topic, payload)
        e2 = self.n.normalize(topic, payload)
        assert e1 is not None
        assert e2 is not None
        assert e2.sequence > e1.sequence

    def test_event_id_is_unique_uuid(self) -> None:
        """Each event gets a unique event_id."""
        topic = "smart-factory/device-1/command/ack"
        payload = json.dumps({"command_id": 1}).encode()
        e1 = self.n.normalize(topic, payload)
        e2 = self.n.normalize(topic, payload)
        assert e1 is not None
        assert e2 is not None
        assert e1.event_id != e2.event_id

    def test_timestamp_ms_extracted_from_iso_string(self) -> None:
        """ISO timestamp string in payload → mqtt_timestamp_ms."""
        topic = "smart-factory/device-1/command/ack"
        payload = json.dumps({
            "command_id": 1,
            "timestamp": "2026-10-13T12:00:00Z",
        }).encode()
        event = self.n.normalize(topic, payload)
        assert event is not None
        assert event.mqtt_timestamp_ms > 0

    def test_timestamp_ms_missing(self) -> None:
        """No timestamp in payload → mqtt_timestamp_ms = 0."""
        topic = "smart-factory/device-1/command/ack"
        payload = json.dumps({"command_id": 1}).encode()
        event = self.n.normalize(topic, payload)
        assert event is not None
        assert event.mqtt_timestamp_ms == 0

    def test_mqtt_topic_preserved(self) -> None:
        """Original MQTT topic is stored in the canonical event."""
        topic = "smart-factory/device-42/status"
        payload = json.dumps({"online": True}).encode()
        event = self.n.normalize(topic, payload)
        assert event is not None
        assert event.mqtt_topic == topic

    def test_ingested_at_is_iso_string(self) -> None:
        """ingested_at is an ISO 8601 string."""
        topic = "smart-factory/device-1/status"
        payload = json.dumps({"online": True}).encode()
        event = self.n.normalize(topic, payload)
        assert event is not None
        assert "T" in event.ingested_at  # ISO format contains T
        assert "Z" in event.ingested_at or "+" in event.ingested_at

    def test_invalid_utf8_returns_none(self) -> None:
        """Invalid UTF-8 bytes → None."""
        topic = "smart-factory/sf-bridge-001/command/ack"
        payload = b"\xff\xfe\x00garbage"
        event = self.n.normalize(topic, payload)
        assert event is None
