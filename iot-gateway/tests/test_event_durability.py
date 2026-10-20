"""Unit tests for event_durability.py — WAL, retry queue, idempotency."""

import asyncio
import json
from datetime import datetime, timezone

import pytest

from iot_gateway.event_durability import (
    RetryEntry,
    RetryStatus,
    WALDurability,
    WALRecord,
)


@pytest.fixture
def wal_db(tmp_path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'wal_test.db'}"


@pytest.fixture
async def wal(wal_db: str) -> WALDurability:
    w = WALDurability(wal_db, max_retries=3)
    await w.init()
    try:
        yield w
    finally:
        await w.close()


# ---------------------------------------------------------------------------
# WAL append / idempotency
# ---------------------------------------------------------------------------

class TestWALAppend:
    @pytest.mark.asyncio
    async def test_append_new_event_returns_true(self, wal: WALDurability) -> None:
        ok = await wal.wal_append(
            event_id="evt-001",
            topic="smart-factory/d1/command/ack",
            raw_payload=b'{"data":1}',
            sequence=1,
        )
        assert ok is True

    @pytest.mark.asyncio
    async def test_append_duplicate_returns_false(self, wal: WALDurability) -> None:
        await wal.wal_append("evt-001", "topic", b"payload", 1)
        ok = await wal.wal_append("evt-001", "topic", b"payload", 1)
        assert ok is False

    @pytest.mark.asyncio
    async def test_confirmed_events_are_deduplicated(self, wal: WALDurability) -> None:
        await wal.wal_append("evt-001", "topic", b"payload", 1)
        await wal.confirm("evt-001")
        dup = await wal.is_duplicate("evt-001")
        assert dup is True

    @pytest.mark.asyncio
    async def test_unconfirmed_event_is_not_duplicate(self, wal: WALDurability) -> None:
        await wal.wal_append("evt-001", "topic", b"payload", 1)
        dup = await wal.is_duplicate("evt-001")
        assert dup is False


# ---------------------------------------------------------------------------
# Retry queue
# ---------------------------------------------------------------------------

class TestRetryQueue:
    @pytest.mark.asyncio
    async def test_schedule_retry_adds_entry(self, wal: WALDurability) -> None:
        await wal.schedule_retry(
            "evt-001",
            {"event_id": "evt-001", "device_id": "d1"},
            "store error",
        )
        assert wal.retry_queue_size() == 1

    @pytest.mark.asyncio
    async def test_get_ready_retries_returns_after_backoff(self, wal: WALDurability) -> None:
        await wal.wal_append("evt-001", "topic", b"{}", 1)
        await wal.schedule_retry("evt-001", {"event_id": "evt-001"}, "error")
        # Immediately: not ready yet (backoff > 0)
        ready = await wal.get_ready_retries()
        assert len(ready) == 0

    @pytest.mark.asyncio
    async def test_retry_entry_backoff_increases(self) -> None:
        entry1 = RetryEntry(event_id="x", event_dict={})
        entry2 = RetryEntry(event_id="x", event_dict={}, retry_count=2)
        entry3 = RetryEntry(event_id="x", event_dict={}, retry_count=3)
        b1 = entry1.backoff_seconds()
        b2 = entry2.backoff_seconds()
        b3 = entry3.backoff_seconds()
        assert b2 >= b1
        assert b3 >= b2

    @pytest.mark.asyncio
    async def test_stats_includes_wal_counts(self, wal: WALDurability) -> None:
        await wal.wal_append("e1", "t1", b"{}", 1)
        await wal.wal_append("e2", "t2", b"{}", 2)
        await wal.confirm("e1")
        stats = await wal.stats()
        assert stats["wal_total"] == 2
        assert stats["wal_pending"] == 1
        assert stats["wal_done"] == 1
        assert stats["wal_retrying"] == 0


# ---------------------------------------------------------------------------
# Partition tolerance (multiple concurrent writers)
# ---------------------------------------------------------------------------

class TestPartitionTolerance:
    @pytest.mark.asyncio
    async def test_concurrent_wal_appends_are_idempotent(self, wal: WALDurability) -> None:
        async def append_once() -> bool:
            return await wal.wal_append("evt-parallel", "topic", b"{}", 1)

        results = await asyncio.gather(*[append_once() for _ in range(10)])
        # Only one should return True; nine should return False (duplicate)
        trues = sum(1 for r in results if r is True)
        assert trues == 1
