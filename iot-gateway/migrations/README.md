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

The migration runner is located at `iot_gateway.migrations.run_migrations`. It supports inspection (`--status`), dry-runs, upgrades, and audited downgrades.

```bash
# Run against default DB (gateway.db in current directory)
python -m iot_gateway.migrations.run_migrations

# Check current schema version and applied migrations
python -m iot_gateway.migrations.run_migrations --status
# Output:
#   schema version: 2
#   supported range: 1..2
#   applied migrations: [1, 2]

# Dry-run (show upgrade/migration steps without executing them)
python -m iot_gateway.migrations.run_migrations --dry-run --verbose

# Revert schema down to version 1 (downgrade)
python -m iot_gateway.migrations.run_migrations --downgrade-to 1
```

Exit codes:
- `0` — migrations applied (or already current) / status printed
- `1` — error (including an unsupported schema version or failure)

---

## Backup & Restore

```bash
# Backup (creates timestamped .bak file next to the DB and verifies it)
python -m iot_gateway.migrations.backup_restore --backup
python -m iot_gateway.migrations.backup_restore --backup --db /path/to/gateway.db
# Output:
#   Backup created and verified: /app/data/gateway.db.20261022_040123_381631.bak

# List available backups
python -m iot_gateway.migrations.backup_restore --list
# Output:
#   Backups for gateway.db in /app/data:
#     gateway.db.20261022_040123_381631.bak  4596 KB  2026-10-22 04:01:23 UTC

# Verify a backup (reads DB, integrity checks, prints summary, no changes)
python -m iot_gateway.migrations.backup_restore --verify --backup-path /path/to/gateway.db.20261022_040123_381631.bak
# Output:
#   PASSED — database is valid: /app/data/gateway.db.20261022_040123_381631.bak

# Restore (requires both --confirm and --offline attestations)
python -m iot_gateway.migrations.backup_restore --restore \
  --db /path/to/gateway.db \
  --backup-path /path/to/gateway.db.20261022_040123_381631.bak \
  --confirm --offline
# Output:
#   Restore completed; the restored database passed integrity and reopen validation.
#   Restored: /app/data/gateway.db <- /app/data/gateway.db.20261022_040123_381631.bak
#   Retained pre-restore live backup: /app/data/gateway.db.pre-restore.20261022_040507_150589.bak
```

---

## Backup & Restore Safety Model

The backup/restore CLI is **WAL-safe**. The rules are:

### Backup

- Uses SQLite's **online backup API** (`sqlite3.Connection.backup`), not a file
  copy. The snapshot is transactionally consistent even when the database is in
  WAL mode and other connections are committing concurrently.
- The backup is **integrity-verified** (`PRAGMA integrity_check`) before it is
  published to its final path, and it is published with an atomic rename so a
  partial file is never visible as a backup.
- The result is a **single self-contained file** — no `-wal`/`-shm` sidecar is
  needed to read it back.
- **Safe to run against a running gateway.**

### Restore

Restore is an **offline, operator-driven** procedure. The tool never stops a
deployed gateway process.

1. `--confirm` — acknowledges that the live database will be replaced.
2. `--offline` — **operator attestation** that every gateway process using the
   database has been stopped. The tool does **not** stop anything; it only
   *verifies* quiescence (it must be able to obtain an exclusive lock and, in
   WAL mode, complete a `wal_checkpoint`) and refuses to proceed otherwise.
3. The source backup is integrity-verified **before** anything is modified.
4. A **pre-restore snapshot** of the live database is taken with the online
   backup API and retained as `<db>.pre-restore.<timestamp>.bak`.
5. The replacement is staged in the same directory as the target and moved into
   place with an **atomic** `os.replace`.
6. The restored file is reopened and integrity-checked. If validation fails,
   the retained pre-restore snapshot is moved back into place (**rollback**),
   and the rollback is itself validated.
7. A **restore journal** (`.<db>.restore-journal.json`) records each phase. A
   restore killed mid-flight leaves the journal behind so an operator can
   resolve the state deterministically via
   `recover_interrupted_restore()`.

Nothing in this tool deletes the live database or the retained snapshot.

### Interrupted restore recovery

```python
from iot_gateway.migrations.backup_restore import recover_interrupted_restore

outcome = recover_interrupted_restore(Path("/path/to/gateway.db"))
# outcome.action in {"completed", "aborted", "rolled_back", "manual"}
```

- `completed` — the swap had already happened and the database validates.
- `aborted` — the swap never happened; the live database is unchanged.
- `rolled_back` — the live database was unusable; it was restored from the
  retained pre-restore snapshot.
- `manual` — no usable snapshot; manual recovery required.

---

## CI / Regression Test

Run the migration regression suite:

```bash
# From repo root
python -m pytest iot-gateway/tests/test_migrations.py iot-gateway/tests/test_backup_restore.py -v
```

Tests in `test_migrations.py`:
1. `test_migration_001_applies_idempotently` — applies migration twice; second run is a no-op
2. `test_migration_preserves_existing_events` — inserts events before migration, verifies columns added with defaults
3. `test_migration_on_empty_db` — fresh DB, migration creates all tables
4. `test_backup_and_restore_roundtrip` — backup → simulate data loss → restore → verify events
5. `test_backup_verifies_integrity` — corrupt a byte in backup → verify error detected

Tests in `test_backup_restore.py` (WAL / interruption / rollback coverage):
1. `test_backup_of_live_wal_database_is_consistent` — active WAL + in-flight write
2. `test_backup_snapshot_is_self_contained` — no sidecar needed to read the backup
3. `test_backup_rejects_missing_database` — failure produces no artefact
4. `test_backup_verification_rejects_corrupted_file`
5. `test_restore_rejects_corrupt_backup_and_preserves_live_db`
6. `test_restore_requires_explicit_offline_attestation`
7. `test_restore_rejects_database_in_use` — quiescence gate
8. `test_restore_retains_pre_restore_snapshot` — rollback artefact
9. `test_restore_rolls_back_when_post_swap_validation_fails`
10. `test_restore_interrupted_before_swap_leaves_live_db_untouched`
11. `test_restore_interrupted_after_swap_is_recoverable`
12. `test_recover_interrupted_restore_rolls_back_corrupted_live_db`
13. `test_restored_database_reopens_and_serves_queries` — restart/open validation
14. `test_restored_database_is_usable_by_the_event_store` — gateway code path

---

## Docker E2E Drill (L2 simulation)

`e2e/simulation/backup_restore_drill.py` runs the same scenarios against the
**live** gateway database inside the compose stack, sharing the gateway's data
volume while the gateway container is running:

```bash
docker compose -f e2e/simulation/docker-compose.e2e.yml up backup-restore-drill
```

Evidence level: **L2 simulation** (mock MQTT stack). Hardware L3/L4 remains
blocked.

