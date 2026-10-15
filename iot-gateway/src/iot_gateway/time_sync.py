"""Time bounds and metrics for canonical gateway events.

This module provides:
- TimeBounds: Configurable staleness thresholds and clock skew limits
- TimeMetrics: In-process latency/jitter tracking and stale/out-of-order counting
- Utility functions for parsing event timestamps

These components enable the gateway to:
1. Detect and flag stale events based on configurable thresholds
2. Track out-of-order events per device
3. Provide observability metrics via the /metrics endpoint
4. Support client snapshot/resync with authoritative timestamps
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class TimeBounds:
    """Configurable event freshness and clock-skew limits.

    Attributes:
        stale_threshold_ms: Maximum allowed event age in milliseconds. Events
            exceeding this threshold are flagged as stale. Default: 30 seconds.
        max_clock_skew_ms: Maximum allowed clock skew between gateway and
            devices in milliseconds. Default: 5 minutes.
    """

    stale_threshold_ms: int = 30_000
    max_clock_skew_ms: int = 5 * 60_000

    def threshold_for(self, device_id: str, event_type: str) -> int:
        """Get the stale threshold for a specific device and event type.

        Currently returns the global stale_threshold_ms. Can be extended
        to support per-device or per-event-type thresholds.
        """
        return self.stale_threshold_ms

    def is_clock_skew(
        self, event_timestamp_ms: int, received_timestamp_ms: int
    ) -> bool:
        """Return True when the source timestamp is ahead of the receive time
        by more than max_clock_skew_ms, indicating a device clock error.

        Args:
            event_timestamp_ms: The event's source timestamp in ms (UTC).
            received_timestamp_ms: The gateway receive timestamp in ms (UTC).

        Returns:
            True if |event - received| exceeds max_clock_skew_ms in the future
            direction; False otherwise.
        """
        if event_timestamp_ms <= 0 or received_timestamp_ms <= 0:
            return False
        skew = event_timestamp_ms - received_timestamp_ms
        return skew > self.max_clock_skew_ms


class TimeMetrics:
    """Bounded, in-process latency and ordering metrics.

    Tracks per-device latency distributions, jitter, and stale/out-of-order
    event counts. Metrics are bounded to a configurable sample size to prevent
    unbounded memory growth.

    Use snapshot() to retrieve current metrics for observability or export.
    """

    def __init__(self, max_samples: int = 1_000) -> None:
        self._latencies: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=max_samples)
        )
        self._jitter: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=max_samples)
        )
        self._last_latency: dict[str, float] = {}
        self._last_event_ms: dict[str, int] = {}
        self._stale = 0
        self._out_of_order = 0

    def observe(self, event: Any) -> None:
        """Record metrics from an event.

        Args:
            event: An object with device_id, latency_ms, stale, out_of_order,
                   and event_timestamp_ms attributes.
        """
        key = event.device_id or "unknown"
        latency = float(event.latency_ms or 0)
        self._latencies[key].append(latency)

        # Track jitter (latency delta)
        previous = self._last_latency.get(key)
        if previous is not None:
            self._jitter[key].append(abs(latency - previous))
        self._last_latency[key] = latency

        # Count stale and out-of-order events
        if event.stale:
            self._stale += 1
        if event.out_of_order:
            self._out_of_order += 1

        # Track latest event timestamp per device (for sequence validation)
        if event.event_timestamp_ms:
            self._last_event_ms[key] = max(
                event.event_timestamp_ms, self._last_event_ms.get(key, 0)
            )

    def snapshot(self) -> dict[str, Any]:
        """Return current metrics as a dictionary.

        Returns:
            Dict with latency_ms (per-device stats), jitter_ms (per-device mean),
            stale_event_count, and out_of_order_event_count.
        """
        return {
            "latency_ms": {
                device: {
                    "count": len(values),
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                    "mean": mean(values) if values else 0,
                    "samples": list(values),
                }
                for device, values in self._latencies.items()
            },
            "jitter_ms": {
                device: (mean(values) if values else 0)
                for device, values in self._jitter.items()
            },
            "stale_event_count": self._stale,
            "out_of_order_event_count": self._out_of_order,
            "last_event_ms": dict(self._last_event_ms),
        }


def utc_now() -> datetime:
    """Return current UTC time as datetime with timezone."""
    return datetime.now(timezone.utc)


def parse_event_time(value: Any) -> datetime | None:
    """Parse various timestamp formats to UTC datetime.

    Supports:
    - Unix milliseconds (int/float)
    - ISO 8601 strings (with or without Z suffix)

    Args:
        value: Timestamp in any supported format.

    Returns:
        UTC datetime or None if parsing fails.
    """
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None
