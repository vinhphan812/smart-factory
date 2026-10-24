"""Normalize raw MQTT messages into CanonicalEvent envelope with time sync and staleness checks."""

import json
import logging
import re
from datetime import datetime, timezone

from .models import CanonicalEvent, EventType
from .time_sync import TimeBounds

logger = logging.getLogger(__name__)

# Topic patterns → (device_id extraction regex, event_type)
TOPIC_PATTERNS = [
    (
        re.compile(r"^smart-factory/([^/]+)/command/ack$"),
        EventType.COMMAND_ACK,
    ),
    (
        re.compile(r"^smart-factory/([^/]+)/status$"),
        None,  # event_type depends on payload
    ),
    (
        re.compile(r"^smart-factory/([^/]+)/telemetry$"),
        EventType.TELEMETRY,
    ),
    (
        re.compile(r"^smart-factory/([^/]+)/heartbeat$"),
        EventType.HEARTBEAT,
    ),
]

# Command status codes → canonical labels
STATUS_CODE_MAP = {
    0: "ok",
    1: "invalid_argument",
    2: "unknown_command",
    3: "internal_error",
    4: "queue_full",
    5: "timeout",
}


class EventNormalizer:
    """Parse MQTT payloads and normalize to CanonicalEvent.

    Handles malformed payloads gracefully — logs a warning and returns None
    for invalid messages rather than raising exceptions. Tracks per-device
    last event timestamps for out-of-order detection and computes transit latency.

    Args:
        time_bounds: Configurable staleness thresholds. Defaults to TimeBounds().
    """

    def __init__(self, time_bounds: TimeBounds | None = None) -> None:
        self._sequence = 0
        self._patterns = TOPIC_PATTERNS
        self._time_bounds = time_bounds or TimeBounds()
        self._last_device_timestamp_ms: dict[str, int] = {}

    def seed_sequence(self, sequence: int) -> None:
        """Continue the sequence numbering from a persisted high-watermark.

        The counter is process-local, so after a gateway restart it would
        restart at 1. Those values collide with (and sort below) the
        sequences already stored, which makes the retention pruner delete
        the freshly written events immediately and freezes the reported
        high-watermark. Seeding from the store on startup keeps the
        sequence space strictly monotonic across restarts.
        """
        if sequence > self._sequence:
            self._sequence = sequence

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence
    def normalize(self, topic: str, payload_bytes: bytes) -> CanonicalEvent | None:
        """Parse MQTT message and return a CanonicalEvent, or None if invalid."""
        try:
            payload = json.loads(payload_bytes.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Malformed JSON on topic %r: %s", topic, exc)
            return None

        # Extract device_id from topic — handle /status specially since event_type
        # depends on the payload, not just the topic pattern.
        event_type: EventType | None = None
        device_id = ""
        is_status_topic = False
        for pattern_re, et in self._patterns:
            m = pattern_re.match(topic)
            if m:
                device_id = m.group(1)
                event_type = et
                is_status_topic = topic.endswith("/status")
                break

        if not device_id:
            logger.warning("Unknown topic pattern: %s", topic)
            return None

        # Derive event_type from payload for STATUS topics
        if is_status_topic:
            is_online = payload.get("online", False)
            event_type = EventType.STATUS_ONLINE if is_online else EventType.STATUS_OFFLINE

        # Extract event timestamp (source of truth UTC)
        mqtt_ts_ms = payload.get("timestamp_ms") or payload.get("timestamp")
        if isinstance(mqtt_ts_ms, str):
            try:
                dt = datetime.fromisoformat(mqtt_ts_ms.replace("Z", "+00:00"))
                mqtt_ts_ms = int(dt.timestamp() * 1000)
            except (ValueError, AttributeError):
                mqtt_ts_ms = 0
        elif not isinstance(mqtt_ts_ms, (int, float)):
            mqtt_ts_ms = 0

        # Timestamp domain detection:
        # ESP32 telemetry publishes "received_at_ms" — this is uptime/monotonic,
        # NOT UTC.  Transit latency and clock-skew are NOT valid for this source.
        # Presence of "received_at_ms" signals an unsynchronized uptime source.
        # The ESP32 does NOT publish "timestamp_ms" for telemetry — that field
        # comes from command_ack/status which may be UTC from an NTP-synced host.
        source_field = None
        if payload.get("received_at_ms") is not None:
            source_field = "received_at_ms"
        elif payload.get("timestamp_ms") is not None or payload.get("timestamp") is not None:
            source_field = "timestamp_ms"

        # Compute receive time and transit latency
        now_utc = datetime.now(timezone.utc)
        received_at_str = now_utc.isoformat()
        received_at_ms = int(now_utc.timestamp() * 1000)

        # is_synchronized = True (UTC domain) unless we see received_at_ms (uptime)
        is_synchronized = source_field != "received_at_ms"

        if is_synchronized:
            # Source timestamp in UTC — compute real transit latency
            event_ts_ms = int(mqtt_ts_ms) if mqtt_ts_ms > 0 else received_at_ms
            latency_ms = max(0, received_at_ms - event_ts_ms)
        else:
            # Source is uptime/monotonic — latency/clock_skew are undefined
            event_ts_ms = received_at_ms  # use receive time as ordering anchor
            latency_ms = -1  # sentinel: not computable without clock sync

        # Staleness check: use received_at_ms (always UTC) as the reference.
        # For synced sources this equals transit latency; for uptime sources
        # it is a conservative upper bound (event cannot be older than
        # now - received_at_ms, which is the gateway's age of the event).
        stale_threshold = self._time_bounds.threshold_for(device_id, event_type.value if event_type else "")
        is_stale = received_at_ms - event_ts_ms > stale_threshold

        # Out-of-order check: use the raw source timestamp when available.
        # For unsynced sources (uptime), this may be unreliable — fall back to
        # received_at_ms as a proxy only when mqtt_ts_ms is 0.
        _src_for_oo = int(mqtt_ts_ms) if mqtt_ts_ms > 0 else received_at_ms
        last_ts = self._last_device_timestamp_ms.get(device_id, 0)
        is_out_of_order = False
        if _src_for_oo > 0 and last_ts > 0 and _src_for_oo < last_ts:
            is_out_of_order = True
        # Update the last seen timestamp for this device
        if _src_for_oo > 0:
            self._last_device_timestamp_ms[device_id] = max(_src_for_oo, last_ts)

        return CanonicalEvent(
            device_id=device_id,
            event_type=event_type,
            payload=payload,
            mqtt_topic=topic,
            mqtt_timestamp_ms=int(mqtt_ts_ms) if mqtt_ts_ms > 0 else 0,
            event_timestamp_ms=event_ts_ms,
            received_at=received_at_str,
            received_at_ms=received_at_ms,
            latency_ms=latency_ms,
            stale=is_stale,
            out_of_order=is_out_of_order,
            is_timestamp_synchronized=is_synchronized,
            ingested_at=received_at_str,
            sequence=self._next_sequence(),
        )
