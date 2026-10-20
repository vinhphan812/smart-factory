"""Unit tests for overflow.py — ring buffer, circuit breaker, backpressure."""

import asyncio
import time

import pytest

from iot_gateway.overflow import (
    BackpressureController,
    CircuitBreaker,
    CircuitState,
    RingBuffer,
)


# ---------------------------------------------------------------------------
# Ring buffer
# ---------------------------------------------------------------------------

class TestRingBuffer:
    def test_push_returns_none_when_not_full(self) -> None:
        rb = RingBuffer(capacity=3)
        evicted = rb.push({"id": 1})
        assert evicted is None
        assert len(rb) == 1

    def test_push_evicts_oldest_when_full(self) -> None:
        rb = RingBuffer(capacity=3)
        rb.push({"id": 1})
        rb.push({"id": 2})
        rb.push({"id": 3})
        evicted = rb.push({"id": 4})
        assert evicted == {"id": 1}
        assert len(rb) == 3

    def test_pop_returns_fifo_order(self) -> None:
        rb = RingBuffer(capacity=5)
        rb.push({"id": 1})
        rb.push({"id": 2})
        rb.push({"id": 3})
        assert rb.pop() == {"id": 1}
        assert rb.pop() == {"id": 2}
        assert len(rb) == 1

    def test_pop_empty_returns_none(self) -> None:
        rb = RingBuffer(capacity=5)
        assert rb.pop() is None

    def test_is_full_and_is_empty(self) -> None:
        rb = RingBuffer(capacity=2)
        assert rb.is_empty() is True
        rb.push({"id": 1})
        rb.push({"id": 2})
        assert rb.is_full() is True

    def test_clear_returns_all_items(self) -> None:
        rb = RingBuffer(capacity=5)
        rb.push({"id": 1})
        rb.push({"id": 2})
        cleared = rb.clear()
        assert cleared == [{"id": 1}, {"id": 2}]
        assert len(rb) == 0


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_initial_state_is_closed(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.can_proceed() is True

    def test_trips_after_failure_threshold(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure(RuntimeError("fail"))
        assert cb.state == CircuitState.OPEN
        assert cb.can_proceed() is False

    def test_open_transitions_to_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=0.01,
        )
        cb.record_failure(RuntimeError("fail"))
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.can_proceed() is True

    def test_half_open_successes_close_breaker(self) -> None:
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=0.01,
            half_open_max_calls=2,
        )
        cb.record_failure(RuntimeError("fail"))
        time.sleep(0.02)
        # Probe 1
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        # Probe 2
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_breaker(self) -> None:
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=0.01,
            half_open_max_calls=2,
        )
        cb.record_failure(RuntimeError("fail"))
        time.sleep(0.02)
        cb.record_success()  # move to half-open
        cb.record_failure(RuntimeError("fail"))
        assert cb.state == CircuitState.OPEN

    def test_reset_closes_breaker(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.record_failure(RuntimeError("fail"))
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_stats_includes_state(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3)
        stats = cb.stats()
        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_threshold"] == 3


# ---------------------------------------------------------------------------
# Backpressure controller
# ---------------------------------------------------------------------------

class TestBackpressure:
    def test_level_0_normal(self) -> None:
        bp = BackpressureController(high_watermark=100, max_capacity=200)
        assert bp.compute_level(50) == 0
        assert bp.throttle_delay() == 0.0
        assert bp.should_drop() is False

    def test_level_1_warning(self) -> None:
        bp = BackpressureController(high_watermark=100, max_capacity=200)
        bp.record_queue_size(100)  # sets self._level
        assert bp.compute_level(100) == 1
        assert bp.throttle_delay() == 0.01

    def test_level_2_throttling(self) -> None:
        bp = BackpressureController(high_watermark=100, max_capacity=200)
        bp.record_queue_size(150)  # sets self._level
        assert bp.compute_level(150) == 2
        assert bp.throttle_delay() == 0.05

    def test_level_3_drop(self) -> None:
        bp = BackpressureController(high_watermark=100, max_capacity=200)
        bp.record_queue_size(200)  # sets self._level
        assert bp.compute_level(200) == 3
        assert bp.should_drop() is True

    def test_record_drop_increments_count(self) -> None:
        bp = BackpressureController(high_watermark=100, max_capacity=200)
        bp.record_drop()
        bp.record_drop()
        assert bp.dropped_count == 2

    def test_record_queue_size_updates_level(self) -> None:
        bp = BackpressureController(high_watermark=100, max_capacity=200)
        bp.record_queue_size(50)
        assert bp.level == 0
        bp.record_queue_size(200)
        assert bp.level == 3

    def test_stats_includes_all_fields(self) -> None:
        bp = BackpressureController(high_watermark=100, max_capacity=200)
        stats = bp.stats()
        assert stats["high_watermark"] == 100
        assert stats["max_capacity"] == 200
        assert "backpressure_dropped_count" in stats
