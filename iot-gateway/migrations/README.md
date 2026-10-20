# iot-gateway — Database Migrations

**Issue:** #186

---

## Overview

Migrations are applied **automatically** by `EventStore.init()` on every gateway startup.
No manual steps are required for normal operation.

For ops/CI use cases (e.g. verifying migrations against a production backup), the
scripts in this directory provide deterministic, repeatable, auditable control.

---

## Migration Strategy

| Approach | When it runs | Idempotent? |
|---|---|---|
| **Python in-process** | Every `EventStore.init()` | ✅ Yes |
| **`run_migrations.py`** | Manual / CI | ✅ Yes |

SQLite `ALTER TABLE ADD COLUMN` is used; existing data is preserved via `NOT NULL DEFAULT <value>`.
No `UPDATE` statements; no table rewrites.

---

## Migration 001 — Timing Columns (applied)

Adds timing metadata columns to the `events` table and creates the `gateway_metadata` table.

Columns added to `events`:

| Column | Type | Default | Purpose |
|---|---|---|---|
| `event_timestamp_ms` | INTEGER | 0 | Source timestamp ms |
| `received_at` | TEXT | '' | Gateway receive time ISO 8601 |
| `latency_ms` | INTEGER | 0 | Transit latency ms; `-1` if unsynced |
| `stale` | INTEGER | 0 | 1 if event age > threshold |
| `out_of_order` | INTEGER | 0 | 1 if event precedes last-seen for device |

Created table `gateway_metadata`:

```sql
CREATE TABLE gateway_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

---

## Running Migrations Manually

```bash
# Run against default DB (gateway.db in current directory)
python -m iot_gateway.migrations.run_migrations

# Run against a specific DB path
python -m iot_gateway.migrations.run_migrations --db /path/to/gateway.db

# Verbose output
python -m iot_gateway.migrations.run_migrations --verbose

# Dry-run (show what would be executed, no changes)
python -m iot_gateway.migrations.run_migrations --dry-run
```

Exit codes:
- `0` — migrations applied (or already current)
- `1` — error

---

## Backup & Restore

```bash
# Backup (creates timestamped .bak file next to the DB)
python -m iot_gateway.migrations.backup_restore --backup
python -m iot_gateway.migrations.backup_restore --backup --db /path/to/gateway.db

# Restore (requires --confirm flag to prevent accidental restores)
python -m iot_gateway.migrations.backup_restore --restore --backup-path /path/to/gateway.db.20260101_120000.bak
python -m iot_gateway.migrations.backup_restore --restore --backup-path /path/to/gateway.db.20260101_120000.bak --confirm

# List available backups
python -m iot_gateway.migrations.backup_restore --list

# Verify a backup (reads DB, prints summary, no changes)
python -m iot_gateway.migrations.backup_restore --verify --backup-path /path/to/gateway.db.20260101_120000.bak
```

---

## CI / Regression Test

Run the migration regression suite:

```bash
# From repo root
python -m pytest iot-gateway/tests/test_migrations.py -v
```

Tests in `test_migrations.py`:
1. `test_migration_001_applies_idempotently` — applies migration twice; second run is a no-op
2. `test_migration_preserves_existing_events` — inserts events before migration, verifies columns added with defaults
3. `test_migration_on_empty_db` — fresh DB, migration creates all tables
4. `test_backup_and_restore_roundtrip` — backup → simulate data loss → restore → verify events
5. `test_backup_verifies_integrity` — corrupt a byte in backup → verify error detected
