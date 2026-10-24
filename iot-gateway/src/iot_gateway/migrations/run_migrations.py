"""CLI to apply migrations to the gateway SQLite database.

Usage:
    python -m iot_gateway.migrations.run_migrations [--db PATH] [--verbose] [--dry-run]
    python -m iot_gateway.migrations.run_migrations --status [--db PATH]
    python -m iot_gateway.migrations.run_migrations --downgrade-to N [--db PATH]

Exit codes:
    0  migrations applied (or already current) / status printed
    1  error (including an unsupported schema version)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import aiosqlite

from iot_gateway.migrations import schema_version as sv

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("run_migrations")


async def _apply_migration_001(conn: aiosqlite.Connection, *, dry_run: bool = False) -> bool:
    """Apply migration 001: add timing columns + create gateway_metadata.

    Returns True if a change was made, False if already up-to-date.
    """
    changed = False

    # 1. Add timing columns to events (if missing)
    TIMING_COLUMNS = dict(sv.TIMING_COLUMNS)

    # Check if events table exists
    cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
    )
    events_exists = await cur.fetchone() is not None
    await cur.close()

    if events_exists:
        cur = await conn.execute("PRAGMA table_info(events)")
        existing_cols = {row[1] for row in await cur.fetchall()}
        await cur.close()

        for col_name, col_def in TIMING_COLUMNS.items():
            if col_name not in existing_cols:
                stmt = f"ALTER TABLE events ADD COLUMN {col_name} {col_def}"
                if dry_run:
                    log.info("[DRY-RUN] Would execute: %s", stmt)
                else:
                    log.info("Applying: %s", stmt)
                    await conn.execute(stmt)
                    changed = True
    else:
        log.warning("events table not found — skipping column migration")

    # 2. Create gateway_metadata table
    create_meta = (
        "CREATE TABLE IF NOT EXISTS gateway_metadata ("
        "  key   TEXT PRIMARY KEY,"
        "  value TEXT NOT NULL"
        ")"
    )
    if dry_run:
        log.info("[DRY-RUN] Would execute: %s", create_meta)
    else:
        await conn.execute(create_meta)
        # CREATE TABLE IF NOT EXISTS is always idempotent — don't flag as changed

    return changed


def _normalise_db_path(db_url: str) -> str:
    """Convert sqlite+aiosqlite:/// or sqlite:/// to a plain filesystem path."""
    if db_url.startswith("sqlite"):
        return db_url.split("///", 1)[-1]
    return db_url


async def run_migrations(
    db_url: str,
    *,
    dry_run: bool = False,
    verbose: bool = False,
    downgrade_to: int | None = None,
    status_only: bool = False,
) -> int:
    """Apply (or revert) migrations on the database at db_url.

    db_url may be an aiosqlite-compatible path (absolute or relative).
    """
    if verbose:
        log.setLevel(logging.DEBUG)

    db_path = _normalise_db_path(db_url)

    log.info("Database: %s", db_path)
    log.info("Mode:    %s", "DRY-RUN" if dry_run else "LIVE")

    # isolation_level=None puts the driver in autocommit mode so the runner
    # can issue explicit BEGIN IMMEDIATE transactions. Without it sqlite3
    # implicitly opens a transaction before the first DML statement and the
    # explicit BEGIN fails with "cannot start a transaction within a
    # transaction".
    async with aiosqlite.connect(db_path, timeout=30, isolation_level=None) as conn:
        await sv.ensure_version_table(conn)
        current = await sv.get_schema_version(conn)
        await conn.commit()

        if status_only:
            print(f"schema version: {current}")
            print(f"supported range: {sv.MIN_SUPPORTED_VERSION}..{sv.CURRENT_SCHEMA_VERSION}")
            print(f"applied migrations: {await sv.applied_migrations(conn)}")
            return 0

        if downgrade_to is not None:
            plan = await sv.downgrade_migrations(
                conn, target=downgrade_to, dry_run=dry_run
            )
        else:
            plan = await sv.apply_migrations(conn, dry_run=dry_run)

        log.info("%s", plan.describe())

    if plan.is_empty:
        log.info("Already up-to-date (schema version %d).", current)
    else:
        log.info("Schema version now %d.", plan.to_version)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply pending iot-gateway DB migrations."
    )
    parser.add_argument(
        "--db",
        default="gateway.db",
        help="Path to the SQLite database (default: gateway.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show statements without executing them.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print the current schema version and exit.",
    )
    parser.add_argument(
        "--downgrade-to",
        type=int,
        default=None,
        metavar="N",
        help=(
            f"Revert the schema down to version N "
            f"(minimum supported: {sv.MIN_SUPPORTED_VERSION})."
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    try:
        return asyncio.run(
            run_migrations(
                args.db,
                dry_run=args.dry_run,
                verbose=args.verbose,
                downgrade_to=args.downgrade_to,
                status_only=args.status,
            )
        )
    except Exception as exc:
        log.error("Migration failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
