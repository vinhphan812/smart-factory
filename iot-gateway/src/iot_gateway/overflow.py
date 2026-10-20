"""Overflow handling: backpressure, ring buffer, and circuit breaker.

Backpressure
------------
When consumers (write workers, WebSocket broadcast) fall behind, the gateway
applies progressive throttling.  The write queue has a high-watermark; when
it exceeds that mark, events are dropped and a backpressure signal is raised.

Ring buffer
-----------
The in-flight event ring buffer holds events that have been acknowledged by the
WAL but not yet confirmed by the store.  Events are evicted in FIFO order when
the buffer is full; evicted events are re-queued for retry.

Circuit breaker
--------------
The CircuitBreaker protects downstream services (store, WebSocket broadcast)
from cascade failures.  When failures exceed a threshold, the breaker opens,
rejecting new events immediately with a fast-fail response rather than blocking.
After a recovery timeout, the breaker half-opens and allows a probe request;
if that succeeds the breaker closes.

Thread-safety
-------------
All state is protected by asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit breaker states
# ---------------------------------------------------------------------------


class CircuitState(str, Enum):
    CLOSED = "closed"    # Normal operation
    OPEN = "open"        # Failing fast — reject immediately
    HALF_OPEN = "half_open"  # Testing recovery


# ---------------------------------------------------------------------------
# Ring buffer
# ---------------------------------------------------------------------------


@dataclass
class RingBuffer:
    """Fixed-capacity FIFO ring buffer for in-flight events.

    When full, oldest entries are evicted and returned to the caller
    so they can be re-queued for retry.
    """

    capacity: int
    _buffer: deque = field(default_factory=deque)

    def push(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Push an item into the buffer.

        If the buffer is at capacity, the oldest item is evicted and returned.
        Returns the evicted item, or None if no eviction occurred.
        """
        evicted: dict[str, Any] | None = None
        if len(self._buffer) >= self.capacity:
            evicted = self._buffer.popleft()
        self._buffer.append(item)
        return evicted

    def pop(self) -> dict[str, Any] | None:
        """Remove and return the oldest item, or None if empty."""
        try:
            return self._buffer.popleft()
        except IndexError:
            return None

    def __len__(self) -> int:
        return len(self._buffer)

    def is_full(self) -> bool:
        return len(self._buffer) >= self.capacity

    def is_empty(self) -> bool:
        return len(self._buffer) == 0

    def clear(self) -> list[dict[str, Any]]:
        """Return and remove all items."""
        items = list(self._buffer)
        self._buffer.clear()
        return items


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Tripping circuit breaker for downstream service calls.

    Implements a three-state machine: CLOSED (normal) → OPEN (fast-fail) →
    HALF_OPEN (probe).  Transitions are governed by:
    - failure_threshold: consecutive failures to trip the breaker
    - recovery_timeout: seconds to wait before transitioning OPEN → HALF_OPEN
    - half_open_max_calls: probe calls allowed in HALF_OPEN state before deciding

    Thread-safe via asyncio.Lock.

    Usage::

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        async def call_downstream():
            if not cb.can_proceed():
                raise CircuitBreakerOpen("breaker open")
            try:
                result = await _actual_call()
                cb.record_success()
                return result
            except Exception as exc:
                cb.record_failure(exc)
                raise
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._opened_at: float = 0.0  # monotonic seconds
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def name(self) -> str:
        return self._name

    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    def can_proceed(self) -> bool:
        """Return True if a call may proceed, False if it should fast-fail."""
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if (time.monotonic() - self._opened_at) >= self._recovery_timeout:
                return True  # will transition to HALF_OPEN on next record
            return False
        # HALF_OPEN: only allow up to half_open_max_calls probes
        return self._half_open_calls < self._half_open_max_calls

    def record_success(self) -> None:
        """Record a successful call; may close the breaker."""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed — transition to HALF_OPEN
            if (time.monotonic() - self._opened_at) >= self._recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
                logger.info(
                    "CircuitBreaker '%s' HALF_OPEN after recovery timeout",
                    self._name,
                )
            else:
                return  # still waiting for recovery timeout

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            self._consecutive_successes += 1
            if self._half_open_calls >= self._half_open_max_calls:
                self._transition(CircuitState.CLOSED)
                logger.info("CircuitBreaker '%s' CLOSED after successful recovery", self._name)
        elif self._state == CircuitState.CLOSED:
            self._consecutive_failures = 0

    def record_failure(self, exc: BaseException | None = None) -> None:
        """Record a failed call; may open the breaker."""
        self._consecutive_failures += 1
        self._consecutive_successes = 0

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN trips back to OPEN
            self._transition(CircuitState.OPEN)
            logger.warning(
                "CircuitBreaker '%s' re-opened after failure in HALF_OPEN: %s",
                self._name,
                exc,
            )
            return

        if self._state == CircuitState.CLOSED:
            if self._consecutive_failures >= self._failure_threshold:
                self._transition(CircuitState.OPEN)
                logger.warning(
                    "CircuitBreaker '%s' OPENED after %d consecutive failures: %s",
                    self._name,
                    self._failure_threshold,
                    exc,
                )

    def _transition(self, new_state: CircuitState) -> None:
        self._state = new_state
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._half_open_calls = 0
        if new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED."""
        self._transition(CircuitState.CLOSED)
        logger.info("CircuitBreaker '%s' manually reset to CLOSED", self._name)

    def stats(self) -> dict[str, Any]:
        """Return circuit breaker statistics."""
        return {
            "name": self._name,
            "state": self._state.value,
            "consecutive_failures": self._consecutive_failures,
            "failure_threshold": self._failure_threshold,
            "recovery_timeout_s": self._recovery_timeout,
            "half_open_calls": self._half_open_calls,
            "half_open_max_calls": self._half_open_max_calls,
        }


# ---------------------------------------------------------------------------
# Backpressure controller
# ---------------------------------------------------------------------------


class BackpressureController:
    """Progressive backpressure based on write queue depth.

    The backpressure level is computed as:
    - Level 0 (normal): queue depth < high_watermark
    - Level 1 (warning): queue depth >= high_watermark
    - Level 2 (throttling): queue depth >= high_watermark * 2
    - Level 3 (drop): queue depth >= max_capacity

    Throttling delay is applied per-event to slow the producer without
    dropping events at levels 1 and 2.  At level 3, events are dropped.

    Thread-safe via asyncio.Lock.
    """

    def __init__(
        self,
        high_watermark: int = 400,
        max_capacity: int = 500,
    ) -> None:
        self._high_watermark = high_watermark
        self._max_capacity = max_capacity

        self._level = 0
        self._dropped_count = 0
        self._last_backpressure_at: str | None = None

    @property
    def level(self) -> int:
        return self._level

    @property
    def dropped_count(self) -> int:
        return self._dropped_count

    def compute_level(self, queue_size: int) -> int:
        """Compute current backpressure level (0–3) from queue size.

        Thresholds (tested in priority order):
        - Level 3 (drop): size >= max_capacity
        - Level 2 (throttle): size >= high_watermark * 1.5
        - Level 1 (warn): size >= high_watermark
        - Level 0 (normal): below high_watermark

        Note: Level 3 is checked before Level 2 so max_capacity always
        takes precedence when they share the same boundary.
        """
        if queue_size >= self._max_capacity:
            return 3
        if queue_size >= self._high_watermark * 1.5:
            return 2
        if queue_size >= self._high_watermark:
            return 1
        return 0

    def record_queue_size(self, queue_size: int) -> None:
        """Update backpressure state based on current queue depth."""
        new_level = self.compute_level(queue_size)
        if new_level > self._level:
            self._last_backpressure_at = datetime.now(timezone.utc).isoformat()
        self._level = new_level

    def throttle_delay(self) -> float:
        """Return throttle delay in seconds for current backpressure level.

        Level 0: 0 s
        Level 1: 0.01 s
        Level 2: 0.05 s
        Level 3: not applicable — events are dropped
        """
        return {0: 0.0, 1: 0.01, 2: 0.05, 3: 0.0}[self._level]

    def should_drop(self) -> bool:
        """Return True if events should be dropped at current level."""
        return self._level >= 3

    def record_drop(self) -> None:
        """Increment the dropped count."""
        self._dropped_count += 1

    def stats(self) -> dict[str, Any]:
        return {
            "backpressure_level": self._level,
            "high_watermark": self._high_watermark,
            "max_capacity": self._max_capacity,
            "backpressure_dropped_count": self._dropped_count,
            "last_backpressure_at": self._last_backpressure_at,
        }
