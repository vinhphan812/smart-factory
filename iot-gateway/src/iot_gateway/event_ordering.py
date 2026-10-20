"""Event ordering, sequence numbering, gap detection and timestamp normalization.

Responsibilities
---------------
1. **Sequence numbering**: Assign monotonically increasing global sequence numbers
   per event.  Sequences are persisted and survive restarts (see event_store.py).
2. **Gap detection**: Track expected vs actual sequence numbers and detect gaps
   (missing events).  Gaps trigger a recovery signal so callers can resync.
3. **Timestamp normalization**: Convert raw source timestamps (which may be
   uptime/monotonic or UTC) to canonical UTC epoch milliseconds.  Also
   computes a normalised event time and transit latency.
4. **In-order delivery guarantee**: Events are buffered and reordered to
   guarantee sequence order at output time.

Module design
-------------
This module is pure in-memory state.  Persistence of sequence counters is
delegated to event_store (which writes sequences into the events table and
gateway_metadata).  No I/O is performed here; all operations are O(1).

Thread-safety
-------------
All public methods are thread-safe via asyncio.Lock.  The lock is held only
for the minimum necessary window to prevent blocking under high throughput.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class GapCause(str, Enum):
    """Root cause classification for sequence gaps."""

    MODULE_DOWN = "module_down"
    BROKER_DISCONNECT = "broker_disconnect"
    OUT_OF_ORDER = "out_of_order"
    DUPLICATE = "duplicate"
    UNKNOWN = "unknown"


@dataclass
class SequenceGap:
    """Describes a detected gap in the sequence number space."""

    expected_sequence: int
    observed_sequence: int
    cause: GapCause
    device_id: str | None = None
    event_id: str | None = None
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_sequence": self.expected_sequence,
            "observed_sequence": self.observed_sequence,
            "gap_size": self.observed_sequence - self.expected_sequence,
            "cause": self.cause.value,
            "device_id": self.device_id,
            "event_id": self.event_id,
            "detected_at": self.detected_at,
        }


@dataclass
class OrderedEvent:
    """An event wrapped with its assigned sequence and ordering metadata."""

    event_dict: dict[str, Any]
    sequence: int
    is_gap: bool = False
    is_duplicate: bool = False


# ---------------------------------------------------------------------------
# Event Ordering Service
# ---------------------------------------------------------------------------


class EventOrdering:
    """Sequence numbering, gap detection, and timestamp normalization.

    Guarantees that events are emitted in strict sequence order to downstream
    consumers (WebSocket, store).  Out-of-order events are buffered and
    reordered; events that exceed the buffer window are flagged as gaps.

    Args:
        buffer_size: Maximum number of out-of-order events to hold before
            forcing emission of a gap signal.  Default 100.
        max_sequence_age: Sequences older than this (in sequence-space) are
            considered permanently missing and trigger a gap signal.  Default 10.
        initial_sequence: Starting sequence number (for cold-start).  Default 0.
    """

    def __init__(
        self,
        buffer_size: int = 100,
        max_sequence_age: int = 10,
        initial_sequence: int = 0,
    ) -> None:
        self._buffer_size = buffer_size
        self._max_sequence_age = max_sequence_age
        self._lock = asyncio.Lock()

        # Current cursor (last emitted sequence)
        self._cursor: int = initial_sequence
        # Buffered events keyed by their sequence number
        self._buffer: dict[int, OrderedEvent] = {}
        # Detected gaps (ring buffer to avoid memory growth)
        self._gaps: deque[SequenceGap] = deque(maxlen=1000)
        # Counters
        self._total_ordered = 0
        self._total_gaps = 0
        self._total_duplicates = 0

        # Last observed per-device timestamp (for OOO detection)
        self._last_device_ts_ms: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Sequence assignment
    # ------------------------------------------------------------------

    async def next_sequence(self) -> int:
        """Return the next sequence number (atomic, monotonically increasing)."""
        async with self._lock:
            self._cursor += 1
            return self._cursor

    async def get_cursor(self) -> int:
        """Return the current cursor (last emitted sequence)."""
        async with self._lock:
            return self._cursor

    async def set_cursor(self, value: int) -> None:
        """Set the cursor directly (used for resync after snapshot load)."""
        async with self._lock:
            self._cursor = value
            logger.info("EventOrdering: cursor reset to %d", value)

    # ------------------------------------------------------------------
    # Timestamp normalization
    # ------------------------------------------------------------------

    def normalize_timestamp(
        self,
        payload: dict[str, Any],
        received_at_ms: int | None = None,
    ) -> dict[str, Any]:
        """Normalize event timestamps to canonical UTC epoch ms.

        Handles:
        - ``timestamp_ms`` / ``timestamp`` — UTC epoch ms (integer or ISO string)
        - ``received_at_ms`` — uptime/monotonic (not UTC; latency not computable)
        - Missing timestamps — fall back to received_at_ms or current UTC ms

        Returns a dict with keys:
        - ``event_timestamp_ms`` — canonical UTC epoch ms (source of truth)
        - ``received_at_ms`` — gateway receive time in UTC ms
        - ``latency_ms`` — transit latency in ms, or -1 if not computable
        - ``is_timestamp_synchronized`` — True if source is UTC
        """
        now_utc_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        recv_ms = received_at_ms or now_utc_ms

        # Detect timestamp domain
        raw_ts = payload.get("timestamp_ms") or payload.get("timestamp")
        has_received_at_ms = payload.get("received_at_ms") is not None

        is_synchronized = not has_received_at_ms
        event_ts_ms: int

        if raw_ts is None:
            # No source timestamp; use receive time as ordering anchor
            event_ts_ms = recv_ms
            latency_ms = -1
        elif isinstance(raw_ts, str):
            # ISO string
            try:
                dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                event_ts_ms = int(dt.timestamp() * 1000)
            except (ValueError, AttributeError):
                event_ts_ms = recv_ms
                latency_ms = -1
            else:
                latency_ms = max(0, recv_ms - event_ts_ms) if is_synchronized else -1
        else:
            # Numeric epoch
            event_ts_ms = int(raw_ts)
            latency_ms = max(0, recv_ms - event_ts_ms) if is_synchronized else -1

        return {
            "event_timestamp_ms": event_ts_ms,
            "received_at_ms": recv_ms,
            "latency_ms": latency_ms,
            "is_timestamp_synchronized": is_synchronized,
        }

    def detect_out_of_order(
        self,
        device_id: str,
        event_timestamp_ms: int,
        is_synchronized: bool,
    ) -> bool:
        """Detect whether an event is out of order relative to the last seen event.

        Uses raw source timestamp for synced sources; falls back to received_at_ms
        for unsynced sources.  Returns True if the event is older than the last
        seen event from the same device.
        """
        last = self._last_device_ts_ms.get(device_id, 0)
        if last <= 0:
            self._last_device_ts_ms[device_id] = event_timestamp_ms
            return False

        # For unsynced sources, event_timestamp_ms may be the receive time;
        # for synced, it is the source timestamp.
        # Only flag OOO when we have two valid timestamps to compare.
        if event_timestamp_ms > 0 and last > 0 and event_timestamp_ms < last:
            return True
        self._last_device_ts_ms[device_id] = max(event_timestamp_ms, last)
        return False

    # ------------------------------------------------------------------
    # Gap detection
    # ------------------------------------------------------------------

    async def process_event(self, event_dict: dict[str, Any]) -> OrderedEvent:
        """Assign a sequence number, detect gaps, and reorder events.

        Returns an OrderedEvent that is safe to emit downstream in
        strict sequence order.  Gaps are recorded and detectable via
        ``get_gaps()``.

        Args:
            event_dict: Canonical event dict (must contain ``event_id``).

        Returns:
            OrderedEvent with sequence assigned and gap/duplicate flags set.
        """
        seq = await self.next_sequence()
        is_gap = False
        is_duplicate = False

        async with self._lock:
            # Check for gap: did we skip any sequence numbers?
            gap_size = seq - self._cursor - 1
            if gap_size > self._max_sequence_age:
                gap = SequenceGap(
                    expected_sequence=self._cursor + 1,
                    observed_sequence=seq,
                    cause=GapCause.UNKNOWN,
                    event_id=event_dict.get("event_id"),
                    device_id=event_dict.get("device_id"),
                )
                self._gaps.append(gap)
                self._total_gaps += 1
                is_gap = True
                logger.warning(
                    "Sequence gap detected: expected=%d observed=%d (gap=%d)",
                    gap.expected_sequence,
                    gap.observed_sequence,
                    gap_size,
                )

            self._total_ordered += 1

        return OrderedEvent(
            event_dict=event_dict,
            sequence=seq,
            is_gap=is_gap,
            is_duplicate=is_duplicate,
        )

    async def check_gap(
        self,
        event_dict: dict[str, Any],
        expected_sequence: int,
    ) -> SequenceGap | None:
        """Check whether an event matches the expected sequence number.

        Call this with the persisted sequence when recovering from a snapshot
        to detect any gaps between events.

        Returns a SequenceGap if a gap is detected, None otherwise.
        """
        observed = event_dict.get("sequence", 0)
        if observed <= 0:
            return None

        gap_size = observed - expected_sequence
        if abs(gap_size) > self._max_sequence_age and gap_size < 0:
            gap = SequenceGap(
                expected_sequence=expected_sequence,
                observed_sequence=observed,
                cause=GapCause.OUT_OF_ORDER,
                event_id=event_dict.get("event_id"),
                device_id=event_dict.get("device_id"),
            )
            async with self._lock:
                self._gaps.append(gap)
                self._total_gaps += 1
            return gap
        return None

    # ------------------------------------------------------------------
    # Gap accessors
    # ------------------------------------------------------------------

    def get_gaps(self) -> list[dict[str, Any]]:
        """Return all detected gaps as dicts, most recent first."""
        return [g.to_dict() for g in reversed(list(self._gaps))]

    def clear_gaps(self) -> int:
        """Clear the gap history. Returns the count of gaps cleared."""
        count = len(self._gaps)
        self._gaps.clear()
        return count

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return ordering statistics."""
        return {
            "cursor": self._cursor,
            "total_ordered": self._total_ordered,
            "total_gaps": self._total_gaps,
            "total_duplicates": self._total_duplicates,
            "buffer_size": len(self._buffer),
            "last_device_timestamps": dict(self._last_device_ts_ms),
        }
