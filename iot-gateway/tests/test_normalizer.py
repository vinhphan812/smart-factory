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

    def test_telemetry_normalization(self) -> None:
        """Telemetry topic → TELEMETRY event."""
        topic = "smart-factory/conveyor-01/telemetry"
        payload = json.dumps({"value": 65.5, "speed": 1.2}).encode()
        event = self.n.normalize(topic, payload)
        assert event is not None
        assert event.event_type == EventType.TELEMETRY
        assert event.device_id == "conveyor-01"
        assert event.payload["value"] == 65.5

    def test_heartbeat_normalization(self) -> None:
        """Heartbeat topic → HEARTBEAT event."""
        topic = "smart-factory/conveyor-01/heartbeat"
        payload = json.dumps({"uptime_ms": 123456}).encode()
        event = self.n.normalize(topic, payload)
        assert event is not None
        assert event.event_type == EventType.HEARTBEAT
        assert event.device_id == "conveyor-01"
        assert event.payload["uptime_ms"] == 123456

    def test_esp32_telemetry_values_and_pairs(self) -> None:
        """ESP32 bridge emits canonical AMLP telemetry as values[] + pairs{}.

        The ESP32 telemetry path (bridge::publishTelemetry in mqtt_bridge.h) emits
        a JSON payload with:
          - "values": array of raw telemetry field strings (temperature, humidity,
            digital inputs, etc.)
          - "pairs": object of key=value sensor readings (e.g. SENSOR1=1)
          - "device_id": bridge identifier
          - "received_at_ms": millisecond timestamp

        This test verifies the normalizer accepts and preserves the full canonical
        structure end-to-end, matching what ESP32 actually emits on the wire.
        """
        topic = "smart-factory/bridge-001/telemetry"
        esp32_payload = {
            "device_id": "bridge-001",
            "received_at_ms": 12345678,
            "values": ["STATE", "60", "2534", "6550", "5"],
            "pairs": {
                "SENSOR1": "1",
                "SENSOR2": "0",
                "SENSOR3": "1",
                "SENSOR4": "0",
            },
            "truncated": False,
        }
        payload_bytes = json.dumps(esp32_payload).encode()
        event = self.n.normalize(topic, payload_bytes)
        assert event is not None
        assert event.event_type == EventType.TELEMETRY
        assert event.device_id == "bridge-001"
        # Full payload including values[] and pairs{} is preserved
        assert "values" in event.payload
        assert "pairs" in event.payload
        assert event.payload["values"] == ["STATE", "60", "2534", "6550", "5"]
        assert event.payload["pairs"]["SENSOR1"] == "1"
        assert event.payload["pairs"]["SENSOR2"] == "0"
        assert event.payload["pairs"]["SENSOR3"] == "1"
        assert event.payload["pairs"]["SENSOR4"] == "0"
        assert event.payload["received_at_ms"] == 12345678
        assert event.payload["truncated"] is False
