"""Normalize raw MQTT messages into CanonicalEvent envelope."""

import json
import logging
import re
import time
from datetime import datetime, timezone

from .models import CanonicalEvent, EventType

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
    for invalid messages rather than raising exceptions.
    """

    def __init__(self) -> None:
        self._sequence = 0
        self._patterns = TOPIC_PATTERNS

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

        # Extract MQTT timestamp if available, else use now
        mqtt_ts_ms = payload.get("timestamp_ms") or payload.get("timestamp")
        if isinstance(mqtt_ts_ms, str):
            try:
                dt = datetime.fromisoformat(mqtt_ts_ms.replace("Z", "+00:00"))
                mqtt_ts_ms = int(dt.timestamp() * 1000)
            except (ValueError, AttributeError):
                mqtt_ts_ms = 0
        elif not isinstance(mqtt_ts_ms, (int, float)):
            mqtt_ts_ms = 0

        return CanonicalEvent(
            device_id=device_id,
            event_type=event_type,
            payload=payload,
            mqtt_topic=topic,
            mqtt_timestamp_ms=int(mqtt_ts_ms),
            ingested_at=datetime.now(timezone.utc).isoformat(),
            sequence=self._next_sequence(),
        )
