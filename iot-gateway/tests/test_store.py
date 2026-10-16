"""Tests for the SQLAlchemy async event store."""

import uuid

import pytest

from iot_gateway.event_store import EventRecord, EventStore
from iot_gateway.event_normalizer import EventNormalizer
from iot_gateway.models import CanonicalEvent, EventType


@pytest.mark.asyncio
async def test_insert_and_get(store: EventStore) -> None:
    """An inserted event can be retrieved by its event_id."""
    normalizer = EventNormalizer()
    topic = "smart-factory/device-1/command/ack"
    payload = b'{"command_id":1,"command_name":"PING"}'
    event = normalizer.normalize(topic, payload)
    assert event is not None

    await store.insert(event)
    fetched = await store.get(event.event_id)
    assert fetched is not None
    assert fetched["event_id"] == str(event.event_id)
    assert fetched["device_id"] == "device-1"
    assert fetched["event_type"] == "command_ack"


@pytest.mark.asyncio
async def test_query_by_device_id(store: EventStore) -> None:
    """Query returns only events matching the device_id filter."""
    normalizer = EventNormalizer()
    for i in range(3):
        topic = f"smart-factory/device-{i}/command/ack"
        event = normalizer.normalize(topic, b'{"command_id":1}')
        assert event is not None
        await store.insert(event)

    # Also insert for another device
    other = normalizer.normalize("smart-factory/other/status", b'{"online":true}')
    assert other is not None
    await store.insert(other)

    events = await store.query(device_id="device-1")
    assert all(e["device_id"] == "device-1" for e in events)


@pytest.mark.asyncio
async def test_query_by_event_type(store: EventStore) -> None:
    """Query returns only events matching the event_type filter."""
    normalizer = EventNormalizer()
    # Insert one of each type
    for topic, payload in [
        ("smart-factory/d1/command/ack", b'{"command_id":1}'),
        ("smart-factory/d2/status", b'{"online":true}'),
    ]:
        event = normalizer.normalize(topic, payload)
        assert event is not None
        await store.insert(event)

    events = await store.query(event_type="command_ack")
    assert all(e["event_type"] == "command_ack" for e in events)


@pytest.mark.asyncio
async def test_query_limit(store: EventStore) -> None:
    """Query respects the limit parameter."""
    normalizer = EventNormalizer()
    for i in range(20):
        event = normalizer.normalize("smart-factory/d1/command/ack", b'{"command_id":1}')
        assert event is not None
        await store.insert(event)

    events = await store.query(device_id="d1", limit=5)
    assert len(events) == 5


@pytest.mark.asyncio
async def test_count_returns_accurate_total(store: EventStore) -> None:
    """count() reflects the total number of stored events."""
    normalizer = EventNormalizer()
    assert await store.count() == 0

    for i in range(10):
        event = normalizer.normalize("smart-factory/d1/status", b'{"online":true}')
        assert event is not None
        await store.insert(event)

    assert await store.count() == 10


@pytest.mark.asyncio
async def test_bounded_retention(database_url: str) -> None:
    """When count exceeds max_events, oldest events are purged."""
    # Create store with max_events=5 using the same database_url fixture
    small_store = EventStore(database_url, max_events=5)
    await small_store.init()
    try:
        normalizer = EventNormalizer()
        for i in range(10):
            event = normalizer.normalize("smart-factory/d1/command/ack", b'{"command_id":1}')
            assert event is not None
            await small_store.insert(event)

        # Should retain at most 5
        assert await small_store.count() <= 5
    finally:
        await small_store.close()


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none(store: EventStore) -> None:
    """get() for an unknown event_id returns None."""
    result = await store.get(str(uuid.uuid4()))
    assert result is None


@pytest.mark.asyncio
async def test_query_empty(store: EventStore) -> None:
    """Query against an empty store returns empty list."""
    events = await store.query(device_id="nonexistent")
    assert events == []


@pytest.mark.asyncio
async def test_sequence_ordering(store: EventStore) -> None:
    """Events are returned in ascending sequence order when requested."""
    normalizer = EventNormalizer()
    for i in range(5):
        event = normalizer.normalize("smart-factory/d1/command/ack", b'{"command_id":1}')
        assert event is not None
        await store.insert(event)

    events = await store.query(device_id="d1", limit=10)
    sequences = [e["sequence"] for e in events]
    # query() returns events sorted by sequence ASC (ascending order)
    assert sequences == sorted(sequences), (
        "Events must be returned in ascending sequence order for deterministic replay"
    )
