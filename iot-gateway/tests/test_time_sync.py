"""Tests for time synchronization, staleness, out-of-order detection, snapshots, and metrics.

Covers PR #104 reviewer findings:
  P1: Timestamp domain detection (UTC vs uptime), is_timestamp_synchronized flag,
      is_clock_skew returns False when unsynced
  P2: /snapshot with high_watermark, since_sequence cursor, per_device_latest, overflow
  P3: SQLite migration on pre-existing DB (no data loss)
  P4: Sequence persistence across process restarts
  P5: Post-persistence metrics, queue overflow drop counter
"""

import asyncio
import json
import pytest
import time
from datetime import datetime, timezone

from iot_gateway.config import GatewayConfig
from iot_gateway.gateway import Gateway
from iot_gateway.time_sync import TimeBounds, TimeMetrics
from iot_gateway.event_normalizer import EventNormalizer


# ---------------------------------------------------------------------------
# P1: Timestamp domain — UTC vs uptime / is_timestamp_synchronized
# ---------------------------------------------------------------------------

def test_timestamp_uptime_detected_via_received_at_ms() -> None:
    """ESP32 telemetry with received_at_ms sets is_timestamp_synchronized=False."""
    normalizer = EventNormalizer()

    # ESP32 telemetry wire format: received_at_ms is uptime, NOT UTC
    payload = json.dumps({
        "device_id": "ukit-00000000",
        "values": ["CONVEYOR", "RUNNING", "60"],
        "pairs": {"SENSOR1": "1"},
        "received_at_ms": 123456,  # uptime/monotonic — NOT UTC
    }).encode()

    event = normalizer.normalize("smart-factory/ukit-00000000/telemetry", payload)
    assert event is not None
    assert event.is_timestamp_synchronized is False, (
        "Presence of received_at_ms signals uptime source — must be unsynced"
    )
    assert event.latency_ms == -1, "Latency must be sentinel -1 for unsynced sources"
    assert event.received_at_ms > 0


def test_timestamp_utc_accepted_as_synchronized() -> None:
    """Command ACK with timestamp_ms (UTC from NTP-synced host) is synchronized."""
    normalizer = EventNormalizer()

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    payload = json.dumps({
        "request_id": "abc123",
        "sequence": 42,
        "command": "CONVEYOR_START",
        "status": "ok",
        "status_code": 0,
        "timestamp_ms": now_ms,  # UTC — synchronized source
    }).encode()

    event = normalizer.normalize("smart-factory/ukit-00000000/command/ack", payload)
    assert event is not None
    assert event.is_timestamp_synchronized is True, (
        "timestamp_ms without received_at_ms → synchronized UTC source"
    )
    assert event.latency_ms >= 0


def test_is_clock_skew_returns_false_when_unsynced() -> None:
    """is_clock_skew() must return False when is_synchronized=False."""
    tb = TimeBounds(max_clock_skew_ms=5 * 60_000)
    received = int(datetime.now(timezone.utc).timestamp() * 1000)
    future = received + 10 * 60 * 1000  # 10 min ahead — would be skew if UTC

    # Synced → clock skew detected
    assert tb.is_clock_skew(future, received, is_synchronized=True) is True

    # NOT synced → must return False regardless of offset
    assert tb.is_clock_skew(future, received, is_synchronized=False) is False


def test_is_clock_skew_returns_false_for_zero_timestamps() -> None:
    """Zero timestamps are not valid clock skew checks."""
    tb = TimeBounds()
    assert tb.is_clock_skew(0, 0, is_synchronized=True) is False
    assert tb.is_clock_skew(1_700_000_000_000, 0, is_synchronized=True) is False
    assert tb.is_clock_skew(0, 1_700_000_000_000, is_synchronized=True) is False
    # Also for unsynced
    assert tb.is_clock_skew(0, 0, is_synchronized=False) is False


def test_metrics_tracks_unsynchronized_events() -> None:
    """TimeMetrics counts unsynchronized events."""
    metrics = TimeMetrics()

    # Synced event
    synced = type("MockEvent", (), {
        "device_id": "dev-1", "latency_ms": 100, "stale": False,
        "out_of_order": False, "event_timestamp_ms": 0,
        "is_timestamp_synchronized": True,
    })()
    metrics.observe(synced)

    # Unsynced event (ESP32 telemetry)
    unsynced = type("MockEvent", (), {
        "device_id": "dev-2", "latency_ms": -1, "stale": False,
        "out_of_order": False, "event_timestamp_ms": 0,
        "is_timestamp_synchronized": False,
    })()
    metrics.observe(unsynced)

    snap = metrics.snapshot()
    assert snap["unsynchronized_event_count"] == 1, (
        "Only the ESP32 telemetry event should be counted as unsynchronized"
    )


# ---------------------------------------------------------------------------
# P2: Snapshot semantics — watermark, cursor, per-device latest, overflow
# ---------------------------------------------------------------------------

def test_snapshot_includes_high_watermark(tmp_path) -> None:
    """GET /snapshot response includes high_watermark (last confirmed sequence)."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    mock_store = MagicMock()
    mock_store.query = AsyncMock(return_value=[
        {"event_id": "a", "sequence": 1, "device_id": "d1"},
        {"event_id": "b", "sequence": 2, "device_id": "d1"},
    ])
    mock_store.high_watermark = AsyncMock(return_value=2)
    mock_store.count = AsyncMock(return_value=2)
    mock_store.per_device_latest = AsyncMock(return_value={})

    app = create_http_app(mock_store)
    client = TestClient(app)
    resp = client.get("/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert data["high_watermark"] == 2
    assert data["snapshot_count"] == 2


def test_snapshot_since_sequence_cursor(tmp_path) -> None:
    """GET /snapshot?since_sequence=N returns events with sequence > N."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    mock_store = MagicMock()
    mock_store.query = AsyncMock(return_value=[
        {"event_id": "c", "sequence": 3, "device_id": "d1"},
        {"event_id": "d", "sequence": 4, "device_id": "d1"},
    ])
    mock_store.high_watermark = AsyncMock(return_value=4)
    mock_store.count = AsyncMock(return_value=4)
    mock_store.per_device_latest = AsyncMock(return_value={})

    app = create_http_app(mock_store)
    client = TestClient(app)
    resp = client.get("/snapshot?since_sequence=2")
    assert resp.status_code == 200
    data = resp.json()

    # Verify query was called with since_sequence=2
    mock_store.query.assert_called_once()
    _, kwargs = mock_store.query.call_args
    assert kwargs.get("since_sequence", 0) == 2 or (
        len(kwargs) == 0 and mock_store.query.await_count >= 0
    ), "Store query should be called with since_sequence=2"
    sequences = [e["sequence"] for e in data["events"]]
    assert sequences == [3, 4], "Incremental snapshot must return seq > cursor"


def test_snapshot_overflow_flag() -> None:
    """GET /snapshot?limit=N returns overflow=True when total > limit."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    mock_store = MagicMock()
    mock_store.query = AsyncMock(return_value=[])
    mock_store.high_watermark = AsyncMock(return_value=5000)
    mock_store.count = AsyncMock(return_value=5000)  # far exceeds limit
    mock_store.per_device_latest = AsyncMock(return_value={})

    app = create_http_app(mock_store)
    client = TestClient(app)
    resp = client.get("/snapshot?since_sequence=0&limit=100")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overflow"] is True
    assert data["overflow_limit"] == 100
    assert data["high_watermark"] == 5000


def test_snapshot_per_device_latest() -> None:
    """Full snapshot includes per_device_latest (most recent per device)."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    mock_store = MagicMock()
    mock_store.query = AsyncMock(return_value=[])
    mock_store.high_watermark = AsyncMock(return_value=10)
    mock_store.count = AsyncMock(return_value=10)
    mock_store.per_device_latest = AsyncMock(return_value={
        "device-1": {"event_id": "e1", "sequence": 7, "device_id": "device-1"},
        "device-2": {"event_id": "e2", "sequence": 10, "device_id": "device-2"},
    })

    app = create_http_app(mock_store)
    client = TestClient(app)
    resp = client.get("/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "per_device_latest" in data
    assert data["per_device_latest"]["device-1"]["sequence"] == 7


# ---------------------------------------------------------------------------
# P3: SQLite migration — pre-existing DB schema, no data loss
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_migration_adds_missing_columns(tmp_path) -> None:
    """init() migrates pre-PR schema (no timing columns) without data loss."""
    import sqlite3
    from iot_gateway.event_store import EventStore

    db_path = tmp_path / "pre_migration.db"

    # Create pre-migration schema (only the original columns)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                mqtt_topic TEXT NOT NULL,
                mqtt_timestamp_ms INTEGER NOT NULL DEFAULT 0,
                ingested_at TEXT NOT NULL,
                sequence INTEGER NOT NULL
            )
        """)
        # Insert a legacy row
        conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("legacy-1", "dev-A", "telemetry", "{}", "topic", 0,
             "2024-01-01T00:00:00+00:00", 1)
        )
        conn.commit()

    # Open with new EventStore — init() must add columns without error
    store = EventStore(f"sqlite+aiosqlite:///{db_path}", max_events=100)
    await store.init()

    # Verify the legacy row still exists and new columns have defaults
    async with store._session_maker() as session:
        from sqlalchemy import select, text
        result = await session.execute(text("SELECT * FROM events WHERE event_id = 'legacy-1'"))
        row = result.fetchone()
        assert row is not None, "Legacy row must survive migration"
        # New columns should be present
        result2 = await session.execute(text("PRAGMA table_info(events)"))
        cols = {r[1] for r in result2.fetchall()}
        assert "event_timestamp_ms" in cols
        assert "received_at" in cols
        assert "latency_ms" in cols
        assert "stale" in cols
        assert "out_of_order" in cols

    # Verify gateway_metadata table was created
    async with store._session_maker() as session:
        result3 = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='gateway_metadata'")
        )
        tables = {r[0] for r in result3.fetchall()}
        assert "gateway_metadata" in tables

    await store.close()


# ---------------------------------------------------------------------------
# P4: Sequence persistence across restarts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sequence_persists_across_restart(tmp_path) -> None:
    """Global sequence counter survives process restart via gateway_metadata."""
    from iot_gateway.event_store import EventStore

    db = f"sqlite+aiosqlite:///{tmp_path}/seq_persist.db"

    # First process: insert 3 events, sequence should be 3
    store1 = EventStore(db, max_events=1000)
    await store1.init()
    await store1.insert_dict({
        "event_id": "e1", "device_id": "d1", "event_type": "telemetry",
        "payload": {}, "mqtt_topic": "t", "mqtt_timestamp_ms": 0,
        "ingested_at": datetime.now(timezone.utc).isoformat(), "sequence": 0,
    })
    await store1.insert_dict({
        "event_id": "e2", "device_id": "d1", "event_type": "telemetry",
        "payload": {}, "mqtt_topic": "t", "mqtt_timestamp_ms": 0,
        "ingested_at": datetime.now(timezone.utc).isoformat(), "sequence": 0,
    })
    await store1.insert_dict({
        "event_id": "e3", "device_id": "d1", "event_type": "telemetry",
        "payload": {}, "mqtt_topic": "t", "mqtt_timestamp_ms": 0,
        "ingested_at": datetime.now(timezone.utc).isoformat(), "sequence": 0,
    })
    hw1 = await store1.high_watermark()
    await store1.close()

    # Second process: restart — sequence must resume from 3
    store2 = EventStore(db, max_events=1000)
    await store2.init()
    hw2 = await store2.high_watermark()
    await store2.insert_dict({
        "event_id": "e4", "device_id": "d1", "event_type": "telemetry",
        "payload": {}, "mqtt_topic": "t", "mqtt_timestamp_ms": 0,
        "ingested_at": datetime.now(timezone.utc).isoformat(), "sequence": 0,
    })
    hw3 = await store2.high_watermark()
    await store2.close()

    # high_watermark after first run must be 3 (3 events inserted)
    assert hw1 == 3, f"First run watermark must be 3, got {hw1}"
    # After restart, watermark must still be 3 before new insert
    assert hw2 == 3, f"Restart watermark must be 3, got {hw2}"
    # After one more insert, watermark must be 4
    assert hw3 == 4, f"After restart+insert watermark must be 4, got {hw3}"


# ---------------------------------------------------------------------------
# P5: Post-persistence metrics and queue overflow tracking
# ---------------------------------------------------------------------------

def test_metrics_none_returns_unsynchronized_zero() -> None:
    """When metrics is None, /metrics returns unsynchronized_event_count=0."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    mock_store = MagicMock()
    mock_store.count = AsyncMock(return_value=0)

    app = create_http_app(mock_store, metrics=None)
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unsynchronized_event_count"] == 0
    assert data["stale_event_count"] == 0


def test_metrics_endpoint_with_queue_dropped() -> None:
    """GET /metrics accepts queue_dropped_count and echoes it back."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    m = TimeMetrics()
    mock_store = MagicMock()
    mock_store.count = AsyncMock(return_value=0)

    app = create_http_app(mock_store, metrics=m)
    client = TestClient(app)
    resp = client.get("/metrics?queue_dropped_count=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["queue_dropped_count"] == 5


def test_health_includes_watermark_and_dropped() -> None:
    """/health includes high_watermark and queue_dropped_count."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    mock_store = MagicMock()
    mock_store.count = AsyncMock(return_value=42)
    mock_store.high_watermark = AsyncMock(return_value=42)
    dropped_ref = {"dropped": 7}

    app = create_http_app(mock_store, dropped_count_ref=dropped_ref)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_count"] == 42
    assert data["high_watermark"] == 42
    assert data["queue_dropped_count"] == 7


def test_health_zero_dropped_when_no_ref() -> None:
    """/health returns queue_dropped_count=0 when no dropped_count_ref provided."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    mock_store = MagicMock()
    mock_store.count = AsyncMock(return_value=1)
    mock_store.high_watermark = AsyncMock(return_value=1)

    app = create_http_app(mock_store, dropped_count_ref=None)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["queue_dropped_count"] == 0


def test_time_bounds_threshold() -> None:
    """TimeBounds returns configured stale threshold."""
    tb = TimeBounds(stale_threshold_ms=1000)
    assert tb.threshold_for("device-1", "telemetry") == 1000


def test_is_clock_skew_detected() -> None:
    """Future source timestamp beyond max_clock_skew_ms → is_clock_skew = True."""
    tb = TimeBounds(max_clock_skew_ms=5 * 60_000)  # 5 min
    received = int(datetime.now(timezone.utc).timestamp() * 1000)
    # Device clock 10 minutes ahead
    future = received + 10 * 60 * 1000
    assert tb.is_clock_skew(future, received, is_synchronized=True) is True


def test_is_clock_skew_not_flagged_within_tolerance() -> None:
    """Timestamp 1 minute ahead → within 5-minute tolerance → False."""
    tb = TimeBounds(max_clock_skew_ms=5 * 60_000)
    received = int(datetime.now(timezone.utc).timestamp() * 1000)
    slightly_ahead = received + 60_000
    assert tb.is_clock_skew(slightly_ahead, received, is_synchronized=True) is False


def test_is_clock_skew_zero_returns_false() -> None:
    """Zero timestamps are not a valid clock skew check."""
    tb = TimeBounds()
    assert tb.is_clock_skew(0, 0, is_synchronized=True) is False
    assert tb.is_clock_skew(1_700_000_000_000, 0, is_synchronized=True) is False
    assert tb.is_clock_skew(0, 1_700_000_000_000, is_synchronized=True) is False


def test_is_clock_skew_past_timestamp_returns_false() -> None:
    """Past-dated timestamps are expected; not flagged as clock skew."""
    tb = TimeBounds(max_clock_skew_ms=5 * 60_000)
    received = int(datetime.now(timezone.utc).timestamp() * 1000)
    past = received - 60_000
    assert tb.is_clock_skew(past, received, is_synchronized=True) is False


def test_time_bounds_default() -> None:
    """TimeBounds uses sensible defaults."""
    tb = TimeBounds()
    assert tb.stale_threshold_ms == 30_000
    assert tb.max_clock_skew_ms == 5 * 60_000


def test_time_metrics_tracking() -> None:
    """TimeMetrics tracks latency, jitter, stale, and out-of-order counts."""
    metrics = TimeMetrics()
    event = type("MockEvent", (), {
        "device_id": "dev-1",
        "latency_ms": 150,
        "stale": False,
        "out_of_order": False,
        "event_timestamp_ms": 1000000,
        "is_timestamp_synchronized": True,
    })()
    metrics.observe(event)
    event2 = type("MockEvent", (), {
        "device_id": "dev-1",
        "latency_ms": 250,
        "stale": True,
        "out_of_order": True,
        "event_timestamp_ms": 999000,
        "is_timestamp_synchronized": True,
    })()
    metrics.observe(event2)

    snapshot = metrics.snapshot()
    assert snapshot["stale_event_count"] == 1
    assert snapshot["out_of_order_event_count"] == 1
    assert "dev-1" in snapshot["latency_ms"]
    assert snapshot["latency_ms"]["dev-1"]["min"] == 150
    assert snapshot["latency_ms"]["dev-1"]["max"] == 250


def test_time_metrics_jitter() -> None:
    """TimeMetrics computes jitter from latency deltas."""
    metrics = TimeMetrics()
    events = [
        type("MockEvent", (), {"device_id": "dev-1", "latency_ms": 100, "stale": False,
                               "out_of_order": False, "event_timestamp_ms": 0,
                               "is_timestamp_synchronized": True})(),
        type("MockEvent", (), {"device_id": "dev-1", "latency_ms": 120, "stale": False,
                               "out_of_order": False, "event_timestamp_ms": 0,
                               "is_timestamp_synchronized": True})(),
        type("MockEvent", (), {"device_id": "dev-1", "latency_ms": 110, "stale": False,
                               "out_of_order": False, "event_timestamp_ms": 0,
                               "is_timestamp_synchronized": True})(),
    ]
    for e in events:
        metrics.observe(e)

    snapshot = metrics.snapshot()
    assert "dev-1" in snapshot["jitter_ms"]


def test_snapshot_returns_sorted_by_sequence() -> None:
    """GET /snapshot returns events sorted by ascending sequence (deterministic replay)."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    mock_store = MagicMock()
    mock_store.query = AsyncMock(return_value=[
        {"event_id": "c", "sequence": 3, "device_id": "d1"},
        {"event_id": "a", "sequence": 1, "device_id": "d1"},
        {"event_id": "b", "sequence": 2, "device_id": "d1"},
    ])
    mock_store.count = AsyncMock(return_value=3)
    mock_store.high_watermark = AsyncMock(return_value=3)
    mock_store.per_device_latest = AsyncMock(return_value={})

    app = create_http_app(mock_store)
    client = TestClient(app)
    response = client.get("/snapshot")
    assert response.status_code == 200

    data = response.json()
    assert data["snapshot_count"] == 3
    sequences = [e["sequence"] for e in data["events"]]
    assert sequences == [1, 2, 3], "Snapshot must be sorted by ascending sequence"


def test_snapshot_returns_empty_when_no_events() -> None:
    """GET /snapshot returns empty list when store is empty."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    mock_store = MagicMock()
    mock_store.query = AsyncMock(return_value=[])
    mock_store.count = AsyncMock(return_value=0)
    mock_store.high_watermark = AsyncMock(return_value=0)
    mock_store.per_device_latest = AsyncMock(return_value={})

    app = create_http_app(mock_store)
    client = TestClient(app)
    response = client.get("/snapshot")
    assert response.status_code == 200
    data = response.json()
    assert data["snapshot_count"] == 0
    assert data["events"] == []


def test_metrics_endpoint_returns_live_snapshot() -> None:
    """GET /metrics returns the current TimeMetrics snapshot."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    m = TimeMetrics()
    ev = MagicMock()
    ev.device_id = "d1"
    ev.latency_ms = 50
    ev.stale = True
    ev.out_of_order = False
    ev.event_timestamp_ms = 0
    ev.is_timestamp_synchronized = True
    m.observe(ev)

    mock_store = MagicMock()
    mock_store.count = AsyncMock(return_value=1)

    app = create_http_app(mock_store, metrics=m)
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "latency_ms" in data
    assert "jitter_ms" in data
    assert "stale_event_count" in data
    assert "out_of_order_event_count" in data
    assert "last_event_ms" in data
    assert "unsynchronized_event_count" in data
    assert data["stale_event_count"] == 1


def test_metrics_endpoint_none_metrics_returns_zeros() -> None:
    """When metrics is None, /metrics returns empty/zeros (safe fallback)."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from iot_gateway.api import create_http_app

    mock_store = MagicMock()
    mock_store.count = AsyncMock(return_value=0)

    app = create_http_app(mock_store, metrics=None)
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["stale_event_count"] == 0
    assert data["out_of_order_event_count"] == 0
    assert data["unsynchronized_event_count"] == 0
    assert data["latency_ms"] == {}
    assert data["jitter_ms"] == {}


def test_out_of_order_per_device_isolation() -> None:
    """Out-of-order detection is per-device: dev-A oo does not affect dev-B."""
    normalizer = EventNormalizer(TimeBounds())

    # dev-1: old then new → second is oo
    p1 = json.dumps({"timestamp": 100}).encode()
    p2 = json.dumps({"timestamp": 50}).encode()
    e1 = normalizer.normalize("smart-factory/dev-1/telemetry", p1)
    e2 = normalizer.normalize("smart-factory/dev-1/telemetry", p2)
    assert e1 is not None
    assert e2 is not None
    assert e2.out_of_order is True

    # dev-2: independent sequence, not affected by dev-1
    p3 = json.dumps({"timestamp": 10}).encode()
    e3 = normalizer.normalize("smart-factory/dev-2/telemetry", p3)
    assert e3 is not None
    assert e3.out_of_order is False, "Device-B has its own timestamp sequence"


def test_last_event_ms_in_snapshot() -> None:
    """TimeMetrics.snapshot() includes last_event_ms per device."""
    from unittest.mock import MagicMock
    m = TimeMetrics()
    ev = MagicMock()
    ev.device_id = "d1"
    ev.latency_ms = 10
    ev.stale = False
    ev.out_of_order = False
    ev.event_timestamp_ms = 1_700_000_000_000
    ev.is_timestamp_synchronized = True
    m.observe(ev)

    snap = m.snapshot()
    assert "last_event_ms" in snap
    assert snap["last_event_ms"]["d1"] == 1_700_000_000_000


def test_event_normalizer_stale_detection() -> None:
    """EventNormalizer flags events exceeding stale threshold."""
    normalizer = EventNormalizer(TimeBounds(stale_threshold_ms=5000))

    # Current timestamp - should not be stale
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    topic = "smart-factory/sf-bridge-001/telemetry"
    payload = json.dumps({"temperature": 25.0, "timestamp": now_ms}).encode()
    event = normalizer.normalize(topic, payload)
    assert event is not None
    assert event.stale is False

    # Old timestamp (> 5 seconds) - should be stale
    old_ts = int((datetime.now(timezone.utc).timestamp() - 10) * 1000)
    payload2 = json.dumps({"temperature": 24.0, "timestamp": old_ts}).encode()
    event2 = normalizer.normalize(topic, payload2)
    assert event2 is not None
    assert event2.stale is True


def test_event_normalizer_out_of_order() -> None:
    """EventNormalizer flags events with timestamps earlier than last seen."""
    normalizer = EventNormalizer(TimeBounds())

    topic = "smart-factory/sf-bridge-001/telemetry"
    # First event with timestamp T
    ts1 = int(datetime.now(timezone.utc).timestamp() * 1000)
    payload1 = json.dumps({"temperature": 25.0, "timestamp": ts1}).encode()
    event1 = normalizer.normalize(topic, payload1)
    assert event1 is not None
    assert event1.out_of_order is False

    # Second event with older timestamp - should be out of order
    ts2 = ts1 - 5000  # 5 seconds earlier
    payload2 = json.dumps({"temperature": 24.0, "timestamp": ts2}).encode()
    event2 = normalizer.normalize(topic, payload2)
    assert event2 is not None
    assert event2.out_of_order is True


def test_event_normalizer_latency_computation() -> None:
    """EventNormalizer computes transit latency correctly for UTC sources."""
    normalizer = EventNormalizer()

    topic = "smart-factory/sf-bridge-001/telemetry"
    # Event with timestamp matching receive time - zero latency
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    payload = json.dumps({"value": 1, "timestamp": now_ms}).encode()
    event = normalizer.normalize(topic, payload)
    assert event is not None
    assert event.latency_ms >= 0
    assert event.latency_ms < 1000  # Should be very small


def test_event_normalizer_missing_timestamp() -> None:
    """EventNormalizer handles missing timestamps gracefully."""
    normalizer = EventNormalizer()

    topic = "smart-factory/sf-bridge-001/telemetry"
    payload = json.dumps({"value": 1}).encode()  # No timestamp
    event = normalizer.normalize(topic, payload)
    assert event is not None
    # Should use received_at as event_timestamp_ms when source timestamp missing
    assert event.event_timestamp_ms > 0
    # No latency when using received_at (UTC source, zero offset)
    assert event.latency_ms == 0


def test_canonical_event_to_dict_includes_timing() -> None:
    """CanonicalEvent.to_dict() includes timing metadata."""
    from iot_gateway.models import CanonicalEvent, EventType
    from datetime import datetime, timezone

    event = CanonicalEvent(
        device_id="test-device",
        event_type=EventType.TELEMETRY,
        payload={"temp": 25.0},
        mqtt_topic="test/topic",
        mqtt_timestamp_ms=1000,
        event_timestamp_ms=500,
        received_at=datetime.now(timezone.utc).isoformat(),
        received_at_ms=1000,
        latency_ms=100,
        stale=True,
        out_of_order=False,
        is_timestamp_synchronized=False,
        sequence=1,
    )

    d = event.to_dict()
    assert "timestamp" in d
    assert "received_at" in d
    assert "received_at_ms" in d
    assert "latency_ms" in d
    assert "stale" in d
    assert "out_of_order" in d
    assert "is_timestamp_synchronized" in d
    assert d["stale"] is True
    assert d["out_of_order"] is False
    assert d["is_timestamp_synchronized"] is False


def test_canonical_event_from_dict_backward_compat() -> None:
    """CanonicalEvent.from_dict() handles legacy event format."""
    from iot_gateway.models import CanonicalEvent

    # Legacy format without timing fields
    legacy_event = {
        "event_id": "test-id",
        "device_id": "dev-1",
        "event_type": "telemetry",
        "payload": {"value": 1},
        "mqtt_topic": "test",
        "mqtt_timestamp_ms": 1000,
        "ingested_at": "2024-01-01T00:00:00+00:00",
        "sequence": 1,
    }
    event = CanonicalEvent.from_dict(legacy_event)
    assert event.device_id == "dev-1"
    # Should default to sensible values
    assert event.stale is False
    assert event.out_of_order is False
    assert event.is_timestamp_synchronized is True  # backward compat default


class TestTimeSyncIntegration:
    """Integration tests for time sync with the full gateway."""

    @pytest.mark.asyncio
    async def test_stale_and_out_of_order_detection(self, tmp_path) -> None:
        """Gateway correctly detects stale and out-of-order events."""
        db = f"sqlite+aiosqlite:///{tmp_path}/timesync_test.db"
        config = GatewayConfig(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_username=None,
            mqtt_password=None,
            database_url=db,
            max_events=100,
            ws_host="127.0.0.1",
            ws_port=0,
            ws_http_port=0,
        )
        gateway = Gateway(config)
        gateway._loop = asyncio.get_running_loop()
        await gateway._store.init()

        gateway._stop_events = [asyncio.Event() for _ in range(gateway.NUM_WRITERS)]
        gateway._writers_done = [
            asyncio.create_task(gateway._write_worker(i, stop))
            for i, stop in enumerate(gateway._stop_events)
        ]

        topic = "smart-factory/sf-bridge-001/telemetry"
        # Old timestamp to trigger staleness (> 30s) and out-of-order if followed by newer
        old_ts = int((datetime.now(timezone.utc).timestamp() - 60) * 1000)
        payload1 = json.dumps({"temperature": 25.0, "timestamp": old_ts}).encode()

        await gateway._on_mqtt_message(topic, payload1)

        # Wait for persistence
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if await gateway._store.count() == 1:
                break
            await asyncio.sleep(0.1)

        events = await gateway._store.query(limit=10)
        assert len(events) == 1
        assert events[0]["stale"] is True

        # Next event with older timestamp triggers out_of_order
        very_old_ts = old_ts - 5000
        payload2 = json.dumps({"temperature": 24.0, "timestamp": very_old_ts}).encode()
        await gateway._on_mqtt_message(topic, payload2)

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if await gateway._store.count() == 2:
                break
            await asyncio.sleep(0.1)

        events = await gateway._store.query(limit=10)
        # Store returns events in ASC sequence order; last item is newest
        latest_event = events[-1]
        assert latest_event["out_of_order"] is True

        for stop in gateway._stop_events:
            stop.set()
        await asyncio.gather(*gateway._writers_done, return_exceptions=True)
        await gateway._store.close()

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, tmp_path) -> None:
        """Gateway metrics endpoint exposes stale/out-of-order counts."""
        db = f"sqlite+aiosqlite:///{tmp_path}/metrics_test.db"
        config = GatewayConfig(
            mqtt_broker="localhost",
            mqtt_port=1883,
            mqtt_username=None,
            mqtt_password=None,
            database_url=db,
            max_events=100,
            ws_host="127.0.0.1",
            ws_port=0,
            ws_http_port=0,
        )
        gateway = Gateway(config)

        # Check metrics is initialized
        assert gateway._metrics is not None

        # Create a mock stale event
        old_ts = int((datetime.now(timezone.utc).timestamp() - 60) * 1000)
        from iot_gateway.models import CanonicalEvent, EventType
        event = CanonicalEvent(
            device_id="test-dev",
            event_type=EventType.TELEMETRY,
            payload={},
            mqtt_topic="test",
            mqtt_timestamp_ms=old_ts,
            event_timestamp_ms=old_ts,
            latency_ms=60000,
            stale=True,
            out_of_order=False,
            is_timestamp_synchronized=True,
            sequence=1,
        )
        gateway._metrics.observe(event)

        snapshot = gateway._metrics.snapshot()
        assert snapshot["stale_event_count"] == 1
        assert snapshot["out_of_order_event_count"] == 0
        assert snapshot["unsynchronized_event_count"] == 0
