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
    """Canonical event envelope for all gateway event sources."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = ""
    event_type: EventType = EventType.COMMAND_ACK
    payload: dict = field(default_factory=dict)
    mqtt_topic: str = ""
    mqtt_timestamp_ms: int = 0
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
            "ingested_at": self.ingested_at,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CanonicalEvent":
        return cls(
            event_id=data["event_id"],
            device_id=data["device_id"],
            event_type=EventType(data["event_type"]),
            payload=data["payload"],
            mqtt_topic=data["mqtt_topic"],
            mqtt_timestamp_ms=data["mqtt_timestamp_ms"],
            ingested_at=data["ingested_at"],
            sequence=data["sequence"],
        )
