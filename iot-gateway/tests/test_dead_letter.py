"""Unit tests for dead_letter.py — DLQ, replay, alert threshold."""

import asyncio
from datetime import datetime, timezone

import pytest

from iot_gateway.dead_letter import DLQRecord, DLQService


@pytest.fixture
def dlq_db(tmp_path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'dlq_test.db'}"


@pytest.fixture
async def dlq(dlq_db: str) -> DLQService:
    d = DLQService(dlq_db, alert_threshold=5)
    await d.init()
    try:
        yield d
    finally:
        await d.close()


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------

class TestDLQEnqueue:
    @pytest.mark.asyncio
    async def test_enqueue_creates_record(self, dlq: DLQService) -> None:
        await dlq.enqueue(
            original_event_id="evt-001",
            payload={"event_id": "evt-001", "device_id": "d1"},
            error_message="store failure",
            retry_count=3,
            device_id="d1",
            event_type="command_ack",
            topic="smart-factory/d1/command/ack",
        )
        count = await dlq.count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_enqueue_idempotent(self, dlq: DLQService) -> None:
        await dlq.enqueue("evt-001", {"event_id": "evt-001"}, "err", 3)
        await dlq.enqueue("evt-001", {"event_id": "evt-001"}, "err", 3)
        count = await dlq.count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_returns_record(self, dlq: DLQService) -> None:
        await dlq.enqueue("evt-001", {"event_id": "evt-001"}, "err", 3)
        record = await dlq.get("evt-001")
        assert record is not None
        assert record["original_event_id"] == "evt-001"
        assert record["retry_count"] == 3

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, dlq: DLQService) -> None:
        record = await dlq.get("nonexistent")
        assert record is None


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

class TestDLQReplay:
    @pytest.mark.asyncio
    async def test_replay_returns_new_event_id(self, dlq: DLQService) -> None:
        await dlq.enqueue("evt-001", {"event_id": "evt-001", "device_id": "d1"}, "err", 3)
        replay = await dlq.replay("evt-001")
        assert replay is not None
        assert replay["event_id"] != "evt-001"
        assert replay["_replay_of"] == "evt-001"

    @pytest.mark.asyncio
    async def test_replay_increments_replay_count(self, dlq: DLQService) -> None:
        await dlq.enqueue("evt-001", {"event_id": "evt-001"}, "err", 3)
        await dlq.replay("evt-001")
        await dlq.replay("evt-001")
        record = await dlq.get("evt-001")
        assert record["replay_count"] == 2

    @pytest.mark.asyncio
    async def test_replay_nonexistent_returns_none(self, dlq: DLQService) -> None:
        result = await dlq.replay("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_replay_missing_event_returns_none(self, dlq: DLQService) -> None:
        result = await dlq.replay("missing-evt")
        assert result is None


# ---------------------------------------------------------------------------
# Discard
# ---------------------------------------------------------------------------

class TestDLQDiscard:
    @pytest.mark.asyncio
    async def test_discard_soft_deletes(self, dlq: DLQService) -> None:
        await dlq.enqueue("evt-001", {"event_id": "evt-001"}, "err", 3)
        ok = await dlq.discard("evt-001")
        assert ok is True
        count = await dlq.count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_discard_nonexistent_returns_false(self, dlq: DLQService) -> None:
        ok = await dlq.discard("missing")
        assert ok is False

    @pytest.mark.asyncio
    async def test_discard_all_returns_count(self, dlq: DLQService) -> None:
        await dlq.enqueue("e1", {"event_id": "e1"}, "err", 3)
        await dlq.enqueue("e2", {"event_id": "e2"}, "err", 3)
        count = await dlq.discard_all()
        assert count == 2
        assert await dlq.count() == 0


# ---------------------------------------------------------------------------
# Alert threshold
# ---------------------------------------------------------------------------

class TestDLQAlert:
    @pytest.mark.asyncio
    async def test_check_alert_threshold_below_limit(self, dlq: DLQService) -> None:
        # alert_threshold=5, enqueue 3
        for i in range(3):
            await dlq.enqueue(f"evt-{i}", {"event_id": f"evt-{i}"}, "err", 3)
        should_alert = await dlq.check_alert_threshold()
        assert should_alert is False

    @pytest.mark.asyncio
    async def test_check_alert_threshold_above_limit(self, dlq: DLQService) -> None:
        # alert_threshold=5, enqueue 6
        for i in range(6):
            await dlq.enqueue(f"evt-{i}", {"event_id": f"evt-{i}"}, "err", 3)
        should_alert = await dlq.check_alert_threshold()
        assert should_alert is True

    @pytest.mark.asyncio
    async def test_alert_respects_cooldown(self, dlq: DLQService) -> None:
        for i in range(6):
            await dlq.enqueue(f"evt-{i}", {"event_id": f"evt-{i}"}, "err", 3)
        first = await dlq.check_alert_threshold()
        assert first is True
        second = await dlq.check_alert_threshold()
        assert second is False  # cooldown not elapsed


# ---------------------------------------------------------------------------
# List / pagination
# ---------------------------------------------------------------------------

class TestDLQList:
    @pytest.mark.asyncio
    async def test_list_returns_most_recent_first(self, dlq: DLQService) -> None:
        for i in range(5):
            await dlq.enqueue(f"evt-{i}", {"event_id": f"evt-{i}"}, "err", 3)
        entries = await dlq.list(limit=3)
        assert len(entries) == 3
        # Most recent first
        assert entries[0]["original_event_id"] == "evt-4"
