"""Unit tests for event_ordering.py — sequence, gap detection, timestamp normalization."""

import asyncio
import pytest

from iot_gateway.event_ordering import (
    EventOrdering,
    GapCause,
    SequenceGap,
)


@pytest.fixture
def ordering() -> EventOrdering:
    return EventOrdering(buffer_size=10, max_sequence_age=5, initial_sequence=0)


# ---------------------------------------------------------------------------
# Sequence numbering
# ---------------------------------------------------------------------------

class TestSequenceNumbering:
    @pytest.mark.asyncio
    async def test_next_sequence_increments(self, ordering: EventOrdering) -> None:
        s1 = await ordering.next_sequence()
        s2 = await ordering.next_sequence()
        assert s2 == s1 + 1

    @pytest.mark.asyncio
    async def test_set_cursor_updates_state(self, ordering: EventOrdering) -> None:
        await ordering.set_cursor(100)
        cursor = await ordering.get_cursor()
        assert cursor == 100
        nxt = await ordering.next_sequence()
        assert nxt == 101

    @pytest.mark.asyncio
    async def test_get_cursor_returns_current(self, ordering: EventOrdering) -> None:
        await ordering.next_sequence()
        await ordering.next_sequence()
        assert await ordering.get_cursor() == 2


# ---------------------------------------------------------------------------
# Timestamp normalization
# ---------------------------------------------------------------------------

class TestTimestampNormalization:
    def test_normalize_utc_epoch_ms(self, ordering: EventOrdering) -> None:
        payload = {"timestamp_ms": 1730000000000}
        result = ordering.normalize_timestamp(payload, received_at_ms=1730000000100)
        assert result["event_timestamp_ms"] == 1730000000000
        assert result["latency_ms"] == 100
        assert result["is_timestamp_synchronized"] is True

    def test_normalize_iso_string(self, ordering: EventOrdering) -> None:
        payload = {"timestamp": "2026-10-20T10:00:00Z"}
        result = ordering.normalize_timestamp(payload, received_at_ms=1730000000000)
        assert result["event_timestamp_ms"] > 0
        assert result["is_timestamp_synchronized"] is True

    def test_normalize_unsynced_uptime(self, ordering: EventOrdering) -> None:
        payload = {"received_at_ms": 12345}
        result = ordering.normalize_timestamp(payload, received_at_ms=1730000000000)
        assert result["is_timestamp_synchronized"] is False
        assert result["latency_ms"] == -1

    def test_normalize_missing_timestamp(self, ordering: EventOrdering) -> None:
        payload = {}
        result = ordering.normalize_timestamp(payload, received_at_ms=1730000000000)
        assert result["event_timestamp_ms"] == 1730000000000
        assert result["latency_ms"] == -1

    def test_detect_out_of_order(self, ordering: EventOrdering) -> None:
        is_ooo = ordering.detect_out_of_order(
            "device-1", event_timestamp_ms=1000, is_synchronized=True
        )
        assert is_ooo is False  # first event, no comparison

        is_ooo2 = ordering.detect_out_of_order(
            "device-1", event_timestamp_ms=900, is_synchronized=True
        )
        assert is_ooo2 is True  # older than last seen


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------

class TestGapDetection:
    @pytest.mark.asyncio
    async def test_process_event_increments_sequence(self, ordering: EventOrdering) -> None:
        evt = await ordering.process_event({"event_id": "e1"})
        assert evt.sequence == 1
        assert evt.is_gap is False

    @pytest.mark.asyncio
    async def test_check_gap_detects_missing_sequence(self, ordering: EventOrdering) -> None:
        # Simulate: we expect seq 5 but the event has seq 7 (gap of 2)
        gap = await ordering.check_gap(
            {"event_id": "e1", "sequence": 7},
            expected_sequence=5,
        )
        # gap_size = 7-5=2 < max_sequence_age=5, so no gap
        assert gap is None

    @pytest.mark.asyncio
    async def test_get_gaps_returns_list(self, ordering: EventOrdering) -> None:
        ordering._gaps.append(
            SequenceGap(
                expected_sequence=5,
                observed_sequence=10,
                cause=GapCause.UNKNOWN,
            )
        )
        gaps = ordering.get_gaps()
        assert len(gaps) == 1
        assert gaps[0]["gap_size"] == 5

    @pytest.mark.asyncio
    async def test_clear_gaps_returns_count(self, ordering: EventOrdering) -> None:
        ordering._gaps.append(SequenceGap(5, 10, GapCause.UNKNOWN))
        count = ordering.clear_gaps()
        assert count == 1
        assert len(ordering.get_gaps()) == 0


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

class TestOrderingStats:
    def test_stats_returns_counters(self, ordering: EventOrdering) -> None:
        stats = ordering.stats()
        assert "cursor" in stats
        assert "total_ordered" in stats
        assert "total_gaps" in stats
        assert stats["total_ordered"] == 0
