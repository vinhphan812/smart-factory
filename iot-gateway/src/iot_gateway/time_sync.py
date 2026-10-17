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
        self, event_timestamp_ms: int, received_timestamp_ms: int,
        is_synchronized: bool = True
    ) -> bool:
        """Return True when the source timestamp is ahead of the receive time
        by more than max_clock_skew_ms, indicating a device clock error.

        Args:
            event_timestamp_ms: The event's source timestamp in ms (UTC).
            received_timestamp_ms: The gateway receive timestamp in ms (UTC).
            is_synchronized: Whether the source timestamp is in UTC (True) or
                uptime/monotonic (False). When False, returns False because
                clock skew cannot be computed without a common time base.

        Returns:
            True if |event - received| exceeds max_clock_skew_ms in the future
            direction AND is_synchronized is True; False otherwise.
        """
        if not is_synchronized:
            return False
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

    Latency/Jitter aggregates: only include events with valid (>= 0) latency
    values. Events with latency_ms = -1 (unsynchronized/uptime sources) are
    counted in unsynchronized_event_count but excluded from numeric aggregates
    so that mean/median reflect only measurable transit times.
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
        self._unsynchronized = 0

    def observe(self, event: Any) -> None:
        """Record metrics from an event.

        Only events with valid (>= 0) latency are included in latency_ms and
        jitter_ms aggregates. Unsynced events (is_timestamp_synchronized=False
        or latency_ms < 0) increment unsynchronized_event_count only.

        Args:
            event: An object with device_id, latency_ms, stale, out_of_order,
                   event_timestamp_ms, and is_timestamp_synchronized attributes.
                   Accepts both CanonicalEvent objects and event dicts.
        """
        # Support both object attributes (CanonicalEvent) and dict access.
        _dev_id = getattr(event, "device_id", None)
        if isinstance(event, dict):
            _dev_id = event.get("device_id", None) if _dev_id is None else _dev_id
        key = _dev_id or "unknown"

        _lat = getattr(event, "latency_ms", None)
        if isinstance(event, dict):
            _lat = event.get("latency_ms", 0) if _lat is None else _lat
        latency = float(_lat if _lat is not None else 0)

        _stale = getattr(event, "stale", None)
        if isinstance(event, dict):
            _stale = event.get("stale", False) if _stale is None else _stale
        stale = bool(_stale)

        _oo = getattr(event, "out_of_order", None)
        if isinstance(event, dict):
            _oo = event.get("out_of_order", False) if _oo is None else _oo
        out_of_order = bool(_oo)

        _ts = getattr(event, "event_timestamp_ms", None)
        if isinstance(event, dict):
            _ts = event.get("event_timestamp_ms", 0) if _ts is None else _ts
        event_ts = _ts

        # Count stale and out-of-order events
        if stale:
            self._stale += 1
        if out_of_order:
            self._out_of_order += 1

        # Track latest event timestamp per device (for sequence validation)
        if event_ts:
            self._last_event_ms[key] = max(
                event_ts, self._last_event_ms.get(key, 0)
            )

        # Count unsynchronized events (uptime timestamps where latency/clock_skew invalid).
        # P1 fix: check is_timestamp_synchronized flag; fall back to latency < 0 sentinel.
        is_sync = getattr(event, "is_timestamp_synchronized", True)
        if isinstance(event, dict):
            is_sync = event.get("is_timestamp_synchronized", True)
        if is_sync is False:
            self._unsynchronized += 1
            # Do NOT append latency=-1 to numeric aggregates — it would skew
            # mean/median. Unsynced events only affect unsynchronized_event_count.
            return

        # P1 fix: only include valid latency in aggregates.
        # latency == -1 is the sentinel for "unknown"; skip it from numeric stats.
        if latency < 0:
            self._unsynchronized += 1
            return

        # Valid latency — include in aggregates
        self._latencies[key].append(latency)

        # Track jitter (latency delta) only for consecutive synced events
        previous = self._last_latency.get(key)
        if previous is not None and previous >= 0:
            self._jitter[key].append(abs(latency - previous))
        self._last_latency[key] = latency

    def snapshot(self) -> dict[str, Any]:
        """Return current metrics as a dictionary.

        Returns:
            Dict with latency_ms (per-device stats), jitter_ms (per-device mean),
            stale_event_count, and out_of_order_event_count.

        Note:
            latency_ms and jitter_ms aggregates include only events with valid
            (>= 0) latency — events with latency = -1 (unsynchronized/uptime
            sources) are excluded from numeric aggregates per P1 fix.
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
            "unsynchronized_event_count": self._unsynchronized,
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
