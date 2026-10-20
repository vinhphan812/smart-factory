"""CLI to apply migrations to the gateway SQLite database.

Usage:
    python -m iot_gateway.migrations.run_migrations [--db PATH] [--verbose] [--dry-run]

Exit codes:
    0  migrations applied or already current
    1  error
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import aiosqlite

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("run_migrations")


async def _apply_migration_001(conn: aiosqlite.Connection, *, dry_run: bool = False) -> bool:
    """Apply migration 001: add timing columns + create gateway_metadata.

    Returns True if a change was made, False if already up-to-date.
    """
    changed = False

    # 1. Add timing columns to events (if missing)
    TIMING_COLUMNS = {
        "event_timestamp_ms": "INTEGER NOT NULL DEFAULT 0",
        "received_at":        "TEXT NOT NULL DEFAULT ''",
        "latency_ms":         "INTEGER NOT NULL DEFAULT 0",
        "stale":              "INTEGER NOT NULL DEFAULT 0",
        "out_of_order":       "INTEGER NOT NULL DEFAULT 0",
    }

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


async def run_migrations(db_url: str, *, dry_run: bool = False, verbose: bool = False) -> int:
    """Apply all pending migrations to the database at db_url.

    db_url may be an aiosqlite-compatible path (absolute or relative).
    """
    if verbose:
        log.setLevel(logging.DEBUG)

    # Convert sqlite+aiosqlite:/// or sqlite:/// to plain path
    if db_url.startswith("sqlite"):
        db_url = db_url.split("///", 1)[-1]

    log.info("Database: %s", db_url)
    log.info("Mode:    %s", "DRY-RUN" if dry_run else "LIVE")

    async with aiosqlite.connect(db_url, timeout=30) as conn:
        changed = await _apply_migration_001(conn, dry_run=dry_run)
        if not dry_run:
            await conn.commit()

    if changed:
        log.info("Migration 001 applied — timing columns added.")
    else:
        log.info("Already up-to-date (migration 001 already applied or events table absent).")

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
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    try:
        return asyncio.run(run_migrations(args.db, dry_run=args.dry_run, verbose=args.verbose))
    except Exception as exc:
        log.error("Migration failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
