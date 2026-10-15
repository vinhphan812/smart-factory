"""Canonical event models for the gateway."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid


class EventType(str, Enum):
    COMMAND_ACK = "command_ack"
    STATUS_ONLINE = "status_online"
    STATUS_OFFLINE = "status_offline"
    TELEMETRY = "telemetry"  # future: when bridge publishes telemetry
    HEARTBEAT = "heartbeat"  # future: when heartbeat topic is wired


@dataclass
class CanonicalEvent:
    """Canonical event envelope for all gateway event sources.

    Includes timing metadata for staleness detection and out-of-order handling.
    The event_timestamp_ms field is the authoritative source timestamp; mqtt_timestamp_ms
    is preserved for wire compatibility with existing consumers.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = ""
    event_type: EventType = EventType.COMMAND_ACK
    payload: dict = field(default_factory=dict)
    mqtt_topic: str = ""
    mqtt_timestamp_ms: int = 0
    # Timing metadata for staleness and ordering
    event_timestamp_ms: int = 0
    received_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    latency_ms: int = 0
    stale: bool = False
    out_of_order: bool = False
    ingested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sequence: int = 0

    def to_dict(self) -> dict:
        return {
            "event_id": str(self.event_id),
            "device_id": self.device_id,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "mqtt_topic": self.mqtt_topic,
            "mqtt_timestamp_ms": self.mqtt_timestamp_ms,
            # Canonical timestamp alias for consumers
            "timestamp": self.event_timestamp_ms or self.mqtt_timestamp_ms,
            "received_at": self.received_at or self.ingested_at,
            "latency_ms": self.latency_ms,
            "stale": self.stale,
            "out_of_order": self.out_of_order,
            "ingested_at": self.ingested_at,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CanonicalEvent":
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            device_id=data["device_id"],
            event_type=EventType(data["event_type"]),
            payload=data["payload"],
            mqtt_topic=data["mqtt_topic"],
            mqtt_timestamp_ms=data.get("mqtt_timestamp_ms", data.get("timestamp", 0)),
            event_timestamp_ms=data.get("event_timestamp_ms", data.get("timestamp", 0)),
            received_at=data.get("received_at", data["ingested_at"]),
            latency_ms=data.get("latency_ms", 0),
            stale=data.get("stale", False),
            out_of_order=data.get("out_of_order", False),
            ingested_at=data["ingested_at"],
            sequence=data["sequence"],
        )
