"""Schema version tracking and versioned migrations for the gateway SQLite DB.

Issue: #186

The gateway database is created by SQLAlchemy ``create_all()`` at startup, which
is *forward*-only and idempotent. That is enough for a fresh install but it
gives an operator no way to answer three questions that matter during an
incident or an upgrade:

1. **What schema is this database actually on?**  → ``gateway_schema_version``
2. **How do I move it to the version the running binary expects, in either
   direction?**  → the upgrade/downgrade plan below.
3. **What happens if a migration dies half way through?**  → every migration is
   applied inside a single transaction together with its version row, so an
   interrupted migration is rolled back atomically and the next run simply
   re-applies it.

Design notes
------------
* The version table is created implicitly by the runner (it is not itself a
  numbered migration), so a database that predates this module still migrates.
* A missing version table means "version 0" — the runner assumes the baseline
  core schema and applies every migration from there.
* Migrations are applied one at a time, each in its own ``BEGIN IMMEDIATE``
  transaction, so two gateways starting at the same time cannot interleave a
  half-applied migration. The loser waits for the lock and then observes the
  already-migrated database.
* Applying a migration writes the version row *in the same transaction*. There
  is therefore no window in which the schema has changed but the version table
  still claims the old version — which is exactly the state that makes
  "interrupted migration" recovery ambiguous.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Literal

import aiosqlite

log = logging.getLogger("schema_version")

#: Name of the table that records the applied schema version.
SCHEMA_VERSION_TABLE = "gateway_schema_version"

#: The schema version this build of the gateway expects.
CURRENT_SCHEMA_VERSION = 2

#: The oldest schema version this build can still serve. Downgrading below
#: this is rejected — the core event columns are required for the gateway to
#: start at all.
MIN_SUPPORTED_VERSION = 1

#: The columns that make up the baseline (version 1) ``events`` table.
#:
#: The declared types deliberately mirror what SQLAlchemy's ``create_all()``
#: produces for the ``EventRecord`` model (JSON payload and DateTime are both
#: stored as TEXT), so a database created by migration 001 and one created by
#: ``create_all()`` are byte-for-byte compatible.
CORE_EVENT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("event_id", "TEXT NOT NULL"),
    ("device_id", "TEXT NOT NULL"),
    ("event_type", "TEXT NOT NULL"),
    ("payload", "TEXT NOT NULL"),
    ("mqtt_topic", "TEXT NOT NULL"),
    ("mqtt_timestamp_ms", "INTEGER NOT NULL DEFAULT 0"),
    ("ingested_at", "TEXT NOT NULL"),
    ("sequence", "INTEGER NOT NULL"),
)

#: Indexes that belong to the baseline schema.
CORE_EVENT_INDEXES: tuple[tuple[str, str], ...] = (
    ("ix_events_device_id", "events(device_id)"),
    ("ix_events_event_type", "events(event_type)"),
    ("ix_events_sequence", "events(sequence)"),
)

#: Timing columns added by migration 002.
TIMING_COLUMNS: tuple[tuple[str, str], ...] = (
    ("event_timestamp_ms", "INTEGER NOT NULL DEFAULT 0"),
    ("received_at", "TEXT NOT NULL DEFAULT ''"),
    ("latency_ms", "INTEGER NOT NULL DEFAULT 0"),
    ("stale", "INTEGER NOT NULL DEFAULT 0"),
    ("out_of_order", "INTEGER NOT NULL DEFAULT 0"),
)

Direction = Literal["upgrade", "downgrade"]


class UnsupportedSchemaVersionError(RuntimeError):
    """The database schema version cannot be served by this build."""


class MigrationError(RuntimeError):
    """A migration failed and was rolled back."""


# ── Migration definitions ────────────────────────────────────────────────────


@dataclass
class Migration:
    """A single numbered, reversible schema change.

    ``up`` and ``down`` are coroutines taking the open connection. They must be
    idempotent with respect to *their own* effect, because a migration that
    was rolled back will be retried on the next run.
    """

    version: int
    name: str
    up: Callable[[aiosqlite.Connection], Awaitable[None]]
    down: Callable[[aiosqlite.Connection], Awaitable[None]]
    description: str = ""


async def _table_exists(conn: aiosqlite.Connection, name: str) -> bool:
    cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    row = await cur.fetchone()
    await cur.close()
    return row is not None


async def _columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    cur = await conn.execute(f"PRAGMA table_info({table})")
    rows = await cur.fetchall()
    await cur.close()
    return {row[1] for row in rows}


async def _up_001_core_schema(conn: aiosqlite.Connection) -> None:
    """Ensure the baseline ``events`` table and its indexes exist."""
    if not await _table_exists(conn, "events"):
        cols = ", ".join(f"{name} {decl}" for name, decl in CORE_EVENT_COLUMNS)
        await conn.execute(f"CREATE TABLE events ({cols})")
    for index_name, index_cols in CORE_EVENT_INDEXES:
        await conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_cols}")
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS gateway_metadata ("
        "  key   TEXT PRIMARY KEY,"
        "  value TEXT NOT NULL"
        ")"
    )


async def _down_001_core_schema(conn: aiosqlite.Connection) -> None:
    """Revert to version 0: drop the baseline indexes.

    The ``events`` table itself is *not* dropped — losing operator data is not
    an acceptable consequence of a schema downgrade, and the columns the
    baseline defines are still required by the running gateway.
    """
    for index_name, _ in CORE_EVENT_INDEXES:
        await conn.execute(f"DROP INDEX IF EXISTS {index_name}")


async def _up_002_timing_columns(conn: aiosqlite.Connection) -> None:
    """Add the timing/staleness columns to ``events``."""
    if not await _table_exists(conn, "events"):
        await _up_001_core_schema(conn)
    existing = await _columns(conn, "events")
    for name, decl in TIMING_COLUMNS:
        if name not in existing:
            await conn.execute(f"ALTER TABLE events ADD COLUMN {name} {decl}")


async def _down_002_timing_columns(conn: aiosqlite.Connection) -> None:
    """Remove the timing columns by rebuilding ``events``.

    SQLite cannot ``ALTER TABLE ... DROP COLUMN`` on every supported version,
    so the table is rebuilt: create the baseline shape, copy the surviving
    columns across, drop the old table, rename, and restore the indexes.
    """
    if not await _table_exists(conn, "events"):
        return
    existing = await _columns(conn, "events")
    if not any(name in existing for name, _ in TIMING_COLUMNS):
        return  # already at the baseline shape

    surviving = [(name, decl) for name, decl in CORE_EVENT_COLUMNS if name in existing]
    cols = ", ".join(f"{name} {decl}" for name, decl in surviving)
    col_names = ", ".join(name for name, _ in surviving)

    await conn.execute("ALTER TABLE events RENAME TO events__pre_002")
    await conn.execute(f"CREATE TABLE events ({cols})")
    await conn.execute(f"INSERT INTO events ({col_names}) SELECT {col_names} FROM events__pre_002")
    await conn.execute("DROP TABLE events__pre_002")
    for index_name, index_cols in CORE_EVENT_INDEXES:
        await conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_cols}")


#: The ordered list of migrations. Index 0 is version 1.
MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="core_schema",
        up=_up_001_core_schema,
        down=_down_001_core_schema,
        description="Baseline events table, indexes and gateway_metadata table.",
    ),
    Migration(
        version=2,
        name="add_timing_columns",
        up=_up_002_timing_columns,
        down=_down_002_timing_columns,
        description="Add event_timestamp_ms/received_at/latency_ms/stale/out_of_order.",
    ),
)

MIGRATIONS_BY_VERSION: dict[int, Migration] = {m.version: m for m in MIGRATIONS}


# ── Version table helpers ────────────────────────────────────────────────────


async def ensure_version_table(conn: aiosqlite.Connection) -> None:
    """Create the schema-version table if it does not exist yet."""
    await conn.execute(
        f"CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE} ("
        "  version    INTEGER PRIMARY KEY,"
        "  name       TEXT NOT NULL,"
        "  applied_at TEXT NOT NULL"
        ")"
    )


async def get_schema_version(conn: aiosqlite.Connection) -> int:
    """Return the applied schema version, or 0 if the table does not exist."""
    if not await _table_exists(conn, SCHEMA_VERSION_TABLE):
        return 0
    cur = await conn.execute(f"SELECT MAX(version) FROM {SCHEMA_VERSION_TABLE}")
    row = await cur.fetchone()
    await cur.close()
    if row is None or row[0] is None:
        return 0
    return int(row[0])


async def applied_migrations(conn: aiosqlite.Connection) -> list[int]:
    """Return the list of individually recorded applied migration versions."""
    if not await _table_exists(conn, SCHEMA_VERSION_TABLE):
        return []
    cur = await conn.execute(f"SELECT version FROM {SCHEMA_VERSION_TABLE} ORDER BY version")
    rows = await cur.fetchall()
    await cur.close()
    return [int(row[0]) for row in rows]


async def _record_version(conn: aiosqlite.Connection, migration: Migration) -> None:
    await conn.execute(
        f"INSERT OR REPLACE INTO {SCHEMA_VERSION_TABLE} (version, name, applied_at) "
        "VALUES (?, ?, ?)",
        (
            migration.version,
            migration.name,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


# ── Planning ─────────────────────────────────────────────────────────────────


@dataclass
class MigrationPlan:
    """An ordered, human-readable description of a schema change."""

    direction: Direction
    from_version: int
    to_version: int
    steps: list[Migration] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.steps

    def describe(self) -> str:
        if self.is_empty:
            return f"schema already at version {self.from_version} — nothing to do"
        lines = [
            f"{self.direction} {self.from_version} -> {self.to_version} "
            f"({len(self.steps)} step(s)):"
        ]
        for step in self.steps:
            lines.append(f"  - {step.version:03d} {step.name}: {step.description}")
        return "\n".join(lines)


def plan_upgrade(current: int, target: int = CURRENT_SCHEMA_VERSION) -> MigrationPlan:
    """Plan the migrations needed to go from ``current`` up to ``target``."""
    if target < current:
        raise UnsupportedSchemaVersionError(
            f"target version {target} is lower than current version {current}; "
            "use a downgrade instead"
        )
    steps = [m for m in MIGRATIONS if current < m.version <= target]
    return MigrationPlan("upgrade", current, target, steps)


def plan_downgrade(current: int, target: int) -> MigrationPlan:
    """Plan the migrations needed to go from ``current`` down to ``target``."""
    if target > current:
        raise UnsupportedSchemaVersionError(
            f"target version {target} is higher than current version {current}; "
            "use an upgrade instead"
        )
    if target < MIN_SUPPORTED_VERSION:
        raise UnsupportedSchemaVersionError(
            f"target version {target} is below the minimum supported version "
            f"{MIN_SUPPORTED_VERSION}"
        )
    steps = [m for m in reversed(MIGRATIONS) if target < m.version <= current]
    return MigrationPlan("downgrade", current, target, steps)


# ── Execution ────────────────────────────────────────────────────────────────


async def _begin_immediate(conn: aiosqlite.Connection) -> None:
    """Start an exclusive write transaction.

    ``BEGIN IMMEDIATE`` takes the write lock up front, so a second migrator
    waits instead of failing halfway through a schema change.
    """
    await conn.execute("BEGIN IMMEDIATE")


async def _apply_one(
    conn: aiosqlite.Connection, migration: Migration, *, dry_run: bool
) -> bool:
    """Apply (or revert) a single migration inside its own transaction."""
    await _begin_immediate(conn)
    try:
        if dry_run:
            await conn.rollback()
            log.info("[DRY-RUN] Would apply migration %03d %s", migration.version, migration.name)
            return False
        await migration.up(conn)
        await _record_version(conn, migration)
        await conn.commit()
    except Exception as exc:
        await conn.rollback()
        raise MigrationError(
            f"migration {migration.version:03d} ({migration.name}) failed and was "
            f"rolled back: {exc}"
        ) from exc
    log.info("Applied migration %03d %s", migration.version, migration.name)
    return True


async def _revert_one(
    conn: aiosqlite.Connection, migration: Migration, *, dry_run: bool
) -> bool:
    """Revert a single migration inside its own transaction."""
    await _begin_immediate(conn)
    try:
        if dry_run:
            await conn.rollback()
            log.info(
                "[DRY-RUN] Would revert migration %03d %s", migration.version, migration.name
            )
            return False
        await migration.down(conn)
        await conn.execute(
            f"DELETE FROM {SCHEMA_VERSION_TABLE} WHERE version = ?", (migration.version,)
        )
        await conn.commit()
    except Exception as exc:
        await conn.rollback()
        raise MigrationError(
            f"downgrade of migration {migration.version:03d} ({migration.name}) failed "
            f"and was rolled back: {exc}"
        ) from exc
    log.info("Reverted migration %03d %s", migration.version, migration.name)
    return True


async def apply_migrations(
    conn: aiosqlite.Connection,
    *,
    target: int = CURRENT_SCHEMA_VERSION,
    dry_run: bool = False,
) -> MigrationPlan:
    """Bring the database up to ``target``, one transactional migration at a time.

    Returns the plan that was executed (or would have been executed).
    """
    await ensure_version_table(conn)
    current = await get_schema_version(conn)

    if current > CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(
            f"database schema version {current} is newer than the maximum supported "
            f"version {CURRENT_SCHEMA_VERSION}; this build cannot serve it"
        )
    if target > CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(
            f"target version {target} is newer than the maximum supported version "
            f"{CURRENT_SCHEMA_VERSION}"
        )
    if current < MIN_SUPPORTED_VERSION and target < MIN_SUPPORTED_VERSION:
        raise UnsupportedSchemaVersionError(
            f"database schema version {current} is below the minimum supported "
            f"version {MIN_SUPPORTED_VERSION}"
        )

    plan = plan_upgrade(current, target)
    if plan.is_empty:
        return plan

    if not dry_run:
        await conn.commit()  # release the ensure_version_table write lock

    for migration in plan.steps:
        await _apply_one(conn, migration, dry_run=dry_run)

    return plan


async def downgrade_migrations(
    conn: aiosqlite.Connection,
    *,
    target: int,
    dry_run: bool = False,
) -> MigrationPlan:
    """Revert migrations down to ``target``."""
    await ensure_version_table(conn)
    current = await get_schema_version(conn)

    if current > CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(
            f"database schema version {current} is newer than the maximum supported "
            f"version {CURRENT_SCHEMA_VERSION}; it cannot be downgraded by this build"
        )

    plan = plan_downgrade(current, target)
    if plan.is_empty:
        return plan

    if not dry_run:
        await conn.commit()

    for migration in plan.steps:
        await _revert_one(conn, migration, dry_run=dry_run)

    return plan
