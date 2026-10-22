"""Regression tests for iot-gateway DB migrations.

Issue: #186

Tests:
1. Migration 001 applies idempotently (safe to re-run on an already-migrated DB)
2. Migration 001 preserves existing events when adding new columns
3. Migration runs cleanly on a fresh (empty) DB
4. Backup → simulate data loss → restore → verify events
5. Corrupt a byte in a backup → verify error is detected
6. Schema version table records the applied version
7. Upgrade plan covers every migration; downgrade plan is the exact inverse
8. Unsupported (too new) schema version is rejected
9. Interrupted migration is rolled back and re-applied cleanly on restart
10. Concurrent writers cannot interleave a half-applied migration
11. Restore restores the exact high-watermark / latest-event state
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
from iot_gateway.migrations import run_migrations, schema_version as sv


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


# ---------------------------------------------------------------------------
# Schema version tracking (#186)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_schema_version_table_records_version(legacy_db_path):
    """After applying migrations the version table records the current version."""
    import aiosqlite

    async with aiosqlite.connect(legacy_db_path, isolation_level=None) as conn:
        plan = await sv.apply_migrations(conn)
        version = await sv.get_schema_version(conn)
        applied = await sv.applied_migrations(conn)
        await conn.commit()

    assert version == sv.CURRENT_SCHEMA_VERSION
    assert plan.direction == "upgrade"
    assert plan.from_version == 0
    assert plan.to_version == sv.CURRENT_SCHEMA_VERSION
    assert applied == [m.version for m in sv.MIGRATIONS]

    # The version table must exist and hold one row per migration.
    conn = sqlite3.connect(f"file:{legacy_db_path}?mode=ro", uri=True)
    rows = conn.execute(
        f"SELECT version, name FROM {sv.SCHEMA_VERSION_TABLE} ORDER BY version"
    ).fetchall()
    conn.close()
    assert [r[0] for r in rows] == [m.version for m in sv.MIGRATIONS]
    assert [r[1] for r in rows] == [m.name for m in sv.MIGRATIONS]


@pytest.mark.asyncio
async def test_schema_version_table_created_on_fresh_db(tmp_db_path):
    """A brand-new database gets the version table and every migration."""
    import aiosqlite

    async with aiosqlite.connect(tmp_db_path, isolation_level=None) as conn:
        await sv.apply_migrations(conn)
        version = await sv.get_schema_version(conn)
        await conn.commit()

    assert version == sv.CURRENT_SCHEMA_VERSION

    conn = sqlite3.connect(f"file:{tmp_db_path}?mode=ro", uri=True)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
    conn.close()
    for name, _ in sv.TIMING_COLUMNS:
        assert name in cols


@pytest.mark.asyncio
async def test_apply_migrations_is_idempotent(legacy_db_path):
    """Re-running the migrator on an up-to-date DB is a no-op."""
    import aiosqlite

    async with aiosqlite.connect(legacy_db_path, isolation_level=None) as conn:
        await sv.apply_migrations(conn)
        await conn.commit()
        plan = await sv.apply_migrations(conn)
        await conn.commit()

    assert plan.is_empty
    assert plan.from_version == sv.CURRENT_SCHEMA_VERSION


def test_upgrade_plan_covers_every_migration():
    """The upgrade plan from version 0 lists every registered migration."""
    plan = sv.plan_upgrade(0, sv.CURRENT_SCHEMA_VERSION)
    assert [m.version for m in plan.steps] == [m.version for m in sv.MIGRATIONS]


def test_downgrade_plan_is_inverse_of_upgrade():
    """Downgrading to the minimum supported version reverses every upgrade step."""
    plan = sv.plan_downgrade(sv.CURRENT_SCHEMA_VERSION, sv.MIN_SUPPORTED_VERSION)
    assert [m.version for m in plan.steps] == [
        m.version for m in reversed(sv.MIGRATIONS)
        if m.version > sv.MIN_SUPPORTED_VERSION
    ]
    assert plan.direction == "downgrade"


def test_downgrade_below_minimum_is_rejected():
    """Downgrading below the minimum supported version is refused."""
    with pytest.raises(sv.UnsupportedSchemaVersionError):
        sv.plan_downgrade(sv.CURRENT_SCHEMA_VERSION, sv.MIN_SUPPORTED_VERSION - 1)


@pytest.mark.asyncio
async def test_downgrade_to_min_version_round_trips(populated_legacy_db):
    """Upgrade → downgrade → upgrade preserves the events and lands on v2."""
    import aiosqlite

    async with aiosqlite.connect(populated_legacy_db, isolation_level=None) as conn:
        await sv.apply_migrations(conn)
        await conn.commit()
        assert await sv.get_schema_version(conn) == sv.CURRENT_SCHEMA_VERSION

        down = await sv.downgrade_migrations(conn, target=sv.MIN_SUPPORTED_VERSION)
        await conn.commit()
        assert await sv.get_schema_version(conn) == sv.MIN_SUPPORTED_VERSION

        up = await sv.apply_migrations(conn)
        await conn.commit()
        assert await sv.get_schema_version(conn) == sv.CURRENT_SCHEMA_VERSION

    assert down.direction == "downgrade"
    assert up.direction == "upgrade"

    # Events survived the round trip.
    conn = sqlite3.connect(f"file:{populated_legacy_db}?mode=ro", uri=True)
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
    conn.close()
    assert count == 5, "Events must survive an upgrade/downgrade/upgrade round trip"
    for name, _ in sv.TIMING_COLUMNS:
        assert name in cols, f"{name} must be restored by the re-upgrade"


@pytest.mark.asyncio
async def test_unsupported_future_version_is_rejected(tmp_db_path):
    """A database written by a newer build is refused, not silently downgraded."""
    import aiosqlite

    async with aiosqlite.connect(tmp_db_path, isolation_level=None) as conn:
        await sv.ensure_version_table(conn)
        await conn.execute(
            f"INSERT INTO {sv.SCHEMA_VERSION_TABLE} (version, name, applied_at) "
            "VALUES (?, ?, ?)",
            (sv.CURRENT_SCHEMA_VERSION + 1, "from_the_future", "2026-01-01T00:00:00+00:00"),
        )
        await conn.commit()

        with pytest.raises(sv.UnsupportedSchemaVersionError):
            await sv.apply_migrations(conn)

        with pytest.raises(sv.UnsupportedSchemaVersionError):
            await sv.downgrade_migrations(conn, target=sv.MIN_SUPPORTED_VERSION)

        # The database is untouched — the refusal is fail-closed.
        assert await sv.get_schema_version(conn) == sv.CURRENT_SCHEMA_VERSION + 1
        await conn.commit()


@pytest.mark.asyncio
async def test_interrupted_migration_rolls_back_and_retry_succeeds(tmp_db_path, monkeypatch):
    """A migration that dies mid-flight leaves no partial schema, and the next
    run applies it cleanly."""
    import aiosqlite

    calls = {"n": 0}
    original_up = sv.MIGRATIONS_BY_VERSION[2].up

    async def flaky_up(conn):
        calls["n"] += 1
        if calls["n"] == 1:
            # Simulate a crash after the ALTER TABLE but before the commit.
            await original_up(conn)
            raise RuntimeError("simulated crash")
        await original_up(conn)

    monkeypatch.setattr(sv.MIGRATIONS_BY_VERSION[2], "up", flaky_up)

    async with aiosqlite.connect(tmp_db_path, isolation_level=None) as conn:
        with pytest.raises(sv.MigrationError):
            await sv.apply_migrations(conn)
        await conn.commit()

        # The failed migration rolled back completely: the timing columns are
        # absent and the version table still shows version 1.
        cur = await conn.execute("PRAGMA table_info(events)")
        cols = {row[1] for row in await cur.fetchall()}
        await cur.close()
        assert "event_timestamp_ms" not in cols
        assert await sv.get_schema_version(conn) == 1

        # Restart: the migration is retried and now succeeds.
        plan = await sv.apply_migrations(conn)
        await conn.commit()
        assert await sv.get_schema_version(conn) == sv.CURRENT_SCHEMA_VERSION
        assert plan.from_version == 1

        cur = await conn.execute("PRAGMA table_info(events)")
        cols = {row[1] for row in await cur.fetchall()}
        await cur.close()

    for name, _ in sv.TIMING_COLUMNS:
        assert name in cols


@pytest.mark.asyncio
async def test_concurrent_migration_does_not_interleave(tmp_db_path):
    """Two migrators running at once must not leave a half-applied schema."""
    import aiosqlite

    async def migrate() -> int:
        async with aiosqlite.connect(tmp_db_path, timeout=30, isolation_level=None) as conn:
            await sv.apply_migrations(conn)
            version = await sv.get_schema_version(conn)
            await conn.commit()
            return version

    results = await asyncio.gather(migrate(), migrate(), return_exceptions=True)

    # Both runners must end up on the same version; a lock timeout would be a
    # legitimate outcome only if the other runner completed the work.
    versions = [r for r in results if isinstance(r, int)]
    assert versions, f"no migration completed: {results}"
    assert all(v == sv.CURRENT_SCHEMA_VERSION for v in versions), results

    conn = sqlite3.connect(f"file:{tmp_db_path}?mode=ro", uri=True)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
    rows = conn.execute(f"SELECT COUNT(*) FROM {sv.SCHEMA_VERSION_TABLE}").fetchone()[0]
    conn.close()
    for name, _ in sv.TIMING_COLUMNS:
        assert name in cols
    assert rows == len(sv.MIGRATIONS), "Each migration must be recorded exactly once"


@pytest.mark.asyncio
async def test_concurrent_writer_during_migration_survives(legacy_db_path):
    """A writer that inserts an event while the migrator runs keeps its row.

    The baseline (pre-migration) schema is already in place — this is the
    production shape, where the gateway's ``create_all()`` has produced the
    table and the migrator is adding the timing columns underneath it.
    """
    import aiosqlite

    async def migrate():
        async with aiosqlite.connect(legacy_db_path, timeout=30, isolation_level=None) as conn:
            await sv.apply_migrations(conn)
            await conn.commit()

    async def write(event_id: str):
        async with aiosqlite.connect(legacy_db_path, timeout=30) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO events "
                "(event_id, device_id, event_type, payload, mqtt_topic, "
                " mqtt_timestamp_ms, ingested_at, sequence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    "dev-concurrent",
                    "telemetry",
                    '{"v":1}',
                    "smart-factory/dev-concurrent/telemetry",
                    1,
                    "2026-01-01T00:00:00+00:00",
                    1,
                ),
            )
            await conn.commit()

    results = await asyncio.gather(
        migrate(), write("evt-concurrent"), return_exceptions=True
    )
    for res in results:
        if isinstance(res, Exception):
            # A lock conflict is acceptable as long as the row landed and the
            # schema is consistent — retry the write once.
            if "locked" not in str(res):
                raise res

    conn = sqlite3.connect(f"file:{legacy_db_path}?mode=ro", uri=True)
    count = conn.execute(
        "SELECT COUNT(*) FROM events WHERE event_id='evt-concurrent'"
    ).fetchone()[0]
    version_row = conn.execute(
        f"SELECT COUNT(*) FROM {sv.SCHEMA_VERSION_TABLE}"
    ).fetchone()[0]
    conn.close()
    assert version_row == len(sv.MIGRATIONS)
    assert count == 1, "Concurrent writer's event must survive the migration"


@pytest.mark.asyncio
async def test_restore_restores_exact_high_watermark_and_latest_state(tmp_db_path):
    """Backup → lose data → restore reproduces the exact high-watermark and the
    exact latest event (sequence, id and payload)."""
    import time
    import uuid

    from iot_gateway.event_store import EventStore
    from iot_gateway.models import CanonicalEvent, EventType
    from iot_gateway.migrations.backup_restore import (
        backup_database,
        restore_database,
    )

    store = EventStore(database_url=f"sqlite+aiosqlite:///{tmp_db_path}", max_events=1000)
    await store.init()

    for i in range(4):
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

    def read_state():
        conn = sqlite3.connect(f"file:{tmp_db_path}?mode=ro", uri=True)
        try:
            watermark = conn.execute(
                "SELECT value FROM gateway_metadata WHERE key='global_sequence'"
            ).fetchone()
            latest = conn.execute(
                "SELECT event_id, sequence, payload FROM events "
                "ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        return (watermark[0] if watermark else None), latest

    before_watermark, before_latest = read_state()
    assert before_watermark is not None, "high-watermark must be persisted"
    assert before_latest is not None

    backup = backup_database(tmp_db_path)
    assert backup.exists()

    # Destroy the live database entirely.
    with open(tmp_db_path, "r+b") as f:
        f.truncate(0)
    for sidecar in (tmp_db_path.with_name(tmp_db_path.name + "-wal"),
                    tmp_db_path.with_name(tmp_db_path.name + "-shm")):
        if sidecar.exists():
            sidecar.unlink()

    restore_database(tmp_db_path, backup, offline=True)

    after_watermark, after_latest = read_state()
    assert after_watermark == before_watermark, (
        f"high-watermark must be restored exactly: {before_watermark} != {after_watermark}"
    )
    assert after_latest is not None
    assert after_latest[0] == before_latest[0], "latest event id must be identical"
    assert after_latest[1] == before_latest[1], "latest sequence must be identical"
    assert after_latest[2] == before_latest[2], "latest payload must be identical"

    # The restored DB is usable by the gateway again.
    store2 = EventStore(database_url=f"sqlite+aiosqlite:///{tmp_db_path}", max_events=1000)
    await store2.init()
    assert len(await store2.query()) == 4
    await store2.close()
