"""Regression tests for iot-gateway DB migrations.

Issue: #186

Tests:
1. Migration 001 applies idempotently (safe to re-run on an already-migrated DB)
2. Migration 001 preserves existing events when adding new columns
3. Migration runs cleanly on a fresh (empty) DB
4. Backup → simulate data loss → restore → verify events
5. Corrupt a byte in a backup → verify error is detected
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

# The run_migrations module lives at the same level as this test file's parent
from iot_gateway.migrations import run_migrations


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db_path():
    """Create a temporary directory with a clean DB file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "gateway.db"


@pytest.fixture
def legacy_db_path(tmp_db_path):
    """Create a pre-migration schema DB (timing columns absent)."""
    conn = sqlite3.connect(f"file:{tmp_db_path}?mode=rwc", uri=True)
    conn.execute("""
        CREATE TABLE events (
            event_id      TEXT PRIMARY KEY,
            device_id     TEXT NOT NULL,
            event_type    TEXT NOT NULL,
            payload       TEXT NOT NULL,
            mqtt_topic    TEXT NOT NULL,
            mqtt_timestamp_ms INTEGER NOT NULL DEFAULT 0,
            ingested_at   TEXT NOT NULL,
            sequence      INTEGER NOT NULL
        )
    """)
    conn.execute("CREATE INDEX ix_events_device_id  ON events(device_id)")
    conn.execute("CREATE INDEX ix_events_event_type ON events(event_type)")
    conn.execute("CREATE INDEX ix_events_sequence   ON events(sequence)")
    conn.commit()
    conn.close()
    yield tmp_db_path


@pytest.fixture
def populated_legacy_db(legacy_db_path):
    """legacy_db_path with a few events pre-inserted."""
    conn = sqlite3.connect(f"file:{legacy_db_path}?mode=rwc", uri=True)
    import time, uuid
    for i in range(5):
        conn.execute(
            "INSERT INTO events (event_id, device_id, event_type, payload, mqtt_topic, mqtt_timestamp_ms, ingested_at, sequence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                f"device-{i}",
                "telemetry",
                '{"value":42}',
                f"smart-factory/device-{i}/telemetry",
                int(time.time() * 1000),
                "2026-01-01T00:00:00+00:00",
                i + 1,
            ),
        )
    conn.commit()
    conn.close()
    yield legacy_db_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_migration_001_idempotent(legacy_db_path):
    """Running migration twice must be a no-op the second time."""
    # First run
    import aiosqlite
    async with aiosqlite.connect(legacy_db_path) as conn:
        changed1 = await run_migrations._apply_migration_001(conn, dry_run=False)
        await conn.commit()
    assert changed1 is True

    # Second run — should be no-op
    async with aiosqlite.connect(legacy_db_path) as conn:
        changed2 = await run_migrations._apply_migration_001(conn, dry_run=False)
        await conn.commit()
    assert changed2 is False

    # Verify all 5 timing columns exist
    conn = sqlite3.connect(f"file:{legacy_db_path}?mode=ro", uri=True)
    cur = conn.execute("PRAGMA table_info(events)")
    cols = {row[1] for row in cur.fetchall()}
    conn.close()
    expected = {
        "event_id", "device_id", "event_type", "payload",
        "mqtt_topic", "mqtt_timestamp_ms",
        "event_timestamp_ms", "received_at", "latency_ms", "stale", "out_of_order",
        "ingested_at", "sequence",
    }
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


@pytest.mark.asyncio
async def test_migration_preserves_existing_events(populated_legacy_db):
    """After migration, pre-existing events are still readable and intact."""
    import aiosqlite
    async with aiosqlite.connect(populated_legacy_db) as conn:
        await run_migrations._apply_migration_001(conn, dry_run=False)
        await conn.commit()

    conn = sqlite3.connect(f"file:{populated_legacy_db}?mode=ro", uri=True)
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.close()
    assert count == 5, "Migration must not delete existing events"

    # Check a sample event — old columns intact
    conn = sqlite3.connect(f"file:{populated_legacy_db}?mode=ro", uri=True)
    row = conn.execute(
        "SELECT event_id, device_id, event_type, mqtt_timestamp_ms, sequence FROM events LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[2] == "telemetry"
    assert row[4] in range(1, 6)


@pytest.mark.asyncio
async def test_migration_on_empty_db(tmp_db_path):
    """Migration runs cleanly on a fresh DB (create_all handles table creation)."""
    # Import EventStore to use its init() which calls create_all then migrate
    from iot_gateway.event_store import EventStore

    store = EventStore(database_url=f"sqlite+aiosqlite:///{tmp_db_path}", max_events=100)
    await store.init()

    conn = sqlite3.connect(f"file:{tmp_db_path}?mode=ro", uri=True)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()

    assert "events" in tables
    assert "gateway_metadata" in tables
    await store.close()


@pytest.mark.asyncio
async def test_backup_and_restore_roundtrip(tmp_db_path):
    """Backup → data loss → restore → events present."""
    from iot_gateway.event_store import EventStore

    # Create store and insert events
    store = EventStore(database_url=f"sqlite+aiosqlite:///{tmp_db_path}", max_events=100)
    await store.init()

    from iot_gateway.models import CanonicalEvent, EventType
    import time, uuid
    for i in range(3):
        ev = CanonicalEvent(
            event_id=str(uuid.uuid4()),
            device_id=f"dev-{i}",
            event_type=EventType.TELEMETRY,
            payload={"v": i},
            mqtt_topic=f"sf/dev-{i}/t",
            mqtt_timestamp_ms=int(time.time() * 1000),
            ingested_at="2026-01-01T00:00:00+00:00",
            sequence=0,
        )
        await store.insert(ev)
    await store.close()

    # Create a backup copy
    bak_path = tmp_db_path.parent / f"{tmp_db_path.name}.test.bak"
    shutil.copy2(tmp_db_path, bak_path)

    # Simulate data loss — truncate the DB file
    with open(tmp_db_path, "r+b") as f:
        f.truncate(0)

    # Restore from backup
    shutil.copy2(bak_path, tmp_db_path)

    # Verify events are back
    store2 = EventStore(database_url=f"sqlite+aiosqlite:///{tmp_db_path}", max_events=100)
    await store2.init()
    restored_count = len(await store2.query())
    await store2.close()

    bak_path.unlink()
    assert restored_count == 3, f"Expected 3 events after restore, got {restored_count}"


def test_backup_verify_detects_corruption(tmp_db_path):
    """Corrupting a backup byte is detected by integrity_check."""
    from iot_gateway.migrations.backup_restore import _integrity_check

    # Create a valid DB
    conn = sqlite3.connect(f"file:{tmp_db_path}?mode=rwc", uri=True)
    conn.execute("CREATE TABLE events (id TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

    # Copy to backup
    bak_path = tmp_db_path.parent / f"{tmp_db_path.name}.corrupt_test.bak"
    shutil.copy2(tmp_db_path, bak_path)

    # Replace the SQLite header, guaranteeing an integrity/open failure.
    with open(bak_path, "r+b") as f:
        f.seek(0)
        f.write(b"CORRUPTED SQLITE!")

    # Integrity check must fail
    ok = _integrity_check(bak_path)
    bak_path.unlink()
    assert ok is False, "Integrity check should detect a corrupted backup"


def test_backup_verify_passes_for_valid_db(tmp_db_path):
    """A valid DB passes integrity check."""
    from iot_gateway.migrations.backup_restore import _integrity_check

    conn = sqlite3.connect(f"file:{tmp_db_path}?mode=rwc", uri=True)
    conn.execute("CREATE TABLE events (id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE gateway_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    conn.close()

    ok = _integrity_check(tmp_db_path)
    assert ok is True, "Valid DB should pass integrity check"
