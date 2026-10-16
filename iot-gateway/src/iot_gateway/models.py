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

    Timestamp provenance (see docs/issue-34-time-sync-gateway-contract.md):
    - ESP32 telemetry: received_at_ms is uptime/monotonic — NOT UTC.
      Transit latency and clock-skew detection are NOT valid for these sources.
      is_timestamp_synchronized = False.
    - Command ACK / status: timestamp_ms may be UTC when sourced from NTP-synced clocks.
      Check is_timestamp_synchronized before using latency_ms or is_clock_skew.

    The is_timestamp_synchronized flag indicates whether the source timestamp is
    in UTC (True) or uptime/monotonic (False). When False, latency_ms is set to -1
    and is_clock_skew always returns False.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = ""
    event_type: EventType = EventType.COMMAND_ACK
    payload: dict = field(default_factory=dict)
    mqtt_topic: str = ""
    mqtt_timestamp_ms: int = 0
    # Timing metadata
    event_timestamp_ms: int = 0
    received_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Milliseconds (UTC epoch) when the gateway received the event.
    # Use this instead of datetime arithmetic for latency computation.
    received_at_ms: int = 0
    # Transit latency in ms (gateway receive - source timestamp).
    # Set to -1 when is_timestamp_synchronized is False (uptime/unknown domain).
    latency_ms: int = 0
    stale: bool = False
    out_of_order: bool = False
    # Explicit flag: True = source timestamp is UTC (latency/clock_skew valid);
    # False = source timestamp is uptime/monotonic (latency/clock_skew NOT valid).
    is_timestamp_synchronized: bool = True
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
            "received_at_ms": self.received_at_ms,
            "latency_ms": self.latency_ms,
            "stale": self.stale,
            "out_of_order": self.out_of_order,
            "is_timestamp_synchronized": self.is_timestamp_synchronized,
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
            received_at_ms=data.get("received_at_ms", 0),
            latency_ms=data.get("latency_ms", 0),
            stale=data.get("stale", False),
            out_of_order=data.get("out_of_order", False),
            is_timestamp_synchronized=data.get("is_timestamp_synchronized", True),
            ingested_at=data["ingested_at"],
            sequence=data["sequence"],
        )
