# Migration 001: Add Timing Columns

**File:** `iot-gateway/migrations/001_add_timing_columns.md`
**Type:** Informational reference — not a runnable SQL script
**Applied by:** `EventStore.init()` via `_migrate_schema()` (Python/aiosqlite)
**Status:** Informational only; see Application migration section below

---

## Schema Changes

### `events` table — add columns

| Column | Type | Default | Description |
|---|---|---|---|
| `event_timestamp_ms` | INTEGER NOT NULL | 0 | Source timestamp ms (UTC or uptime — see `is_timestamp_synchronized`) |
| `received_at` | TEXT NOT NULL | '' | Gateway receive time (ISO 8601, UTC) |
| `latency_ms` | INTEGER NOT NULL | 0 | Transit latency ms; `-1` if unsynchronized |
| `stale` | INTEGER NOT NULL | 0 | 1 if event age > threshold, 0 otherwise |
| `out_of_order` | INTEGER NOT NULL | 0 | 1 if timestamp precedes last-seen for device, 0 otherwise |

### `gateway_metadata` table — create

```sql
CREATE TABLE IF NOT EXISTS gateway_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Stores key/value pairs for gateway state that must survive restarts.
Currently used for: `global_sequence` counter.

---

## Application Migration (how it actually runs)

`EventStore._migrate_schema()` applies this change using Python/aiosqlite:

1. `PRAGMA table_info(events)` — detect already-present columns
2. `ALTER TABLE events ADD COLUMN <name> <type> NOT NULL DEFAULT <default>` — for each missing column (idempotent)
3. `CREATE TABLE IF NOT EXISTS gateway_metadata(...)` — for sequence persistence

```python
# Pseudocode
TIMING_COLUMNS = {
    "event_timestamp_ms": "INTEGER NOT NULL DEFAULT 0",
    "received_at":        "TEXT NOT NULL DEFAULT ''",
    "latency_ms":         "INTEGER NOT NULL DEFAULT 0",
    "stale":              "INTEGER NOT NULL DEFAULT 0",
    "out_of_order":       "INTEGER NOT NULL DEFAULT 0",
}

async def _migrate_schema(self):
    async with self._engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(events)"))
        existing = {row[1] for row in result.fetchall()}
        for col_name, col_def in TIMING_COLUMNS.items():
            if col_name not in existing:
                await conn.execute(
                    text(f"ALTER TABLE events ADD COLUMN {col_name} {col_def}")
                )
```

Columns use `NOT NULL DEFAULT <value>` so existing rows receive valid defaults
without any `UPDATE` statement — zero data loss, zero table rewrite.

---

## Why this file is `.md` and not `.sql`

SQLite `ALTER TABLE ADD COLUMN` has restrictions (no `FOREIGN KEY`, no `CHECK`,
no defaults referencing other columns). Using a Python application migration avoids
the sqlite3 shell wrapper (which the `.headers on` / `.mode list` directives
require) and keeps the idempotency logic in the same language as the rest of the
application.

This file documents the schema change for review and manual verification.
Do NOT run it with `sqlite3 gateway.db < 001_add_timing_columns.sql` —
use the application migration instead.

---

## Rollback

To rollback on a development/pre-production system:

```sql
-- Not supported natively by SQLite.
-- Recreate the table without the new columns:
CREATE TABLE events_old AS
  SELECT event_id, device_id, event_type, payload, mqtt_topic,
         mqtt_timestamp_ms, ingested_at, sequence
  FROM events;

DROP TABLE events;
ALTER TABLE events_old RENAME TO events;
CREATE INDEX IF NOT EXISTS ix_events_device_id ON events(device_id);
CREATE INDEX IF NOT EXISTS ix_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS ix_events_sequence  ON events(sequence);

-- gateway_metadata can remain (it's used for sequence persistence).
```

---

## Usage Examples

### Read current global sequence

```sql
SELECT value FROM gateway_metadata WHERE key = 'global_sequence';
```

### Manual sequence increment (use in a transaction with your INSERT)

```sql
INSERT OR REPLACE INTO gateway_metadata (key, value)
  VALUES ('global_sequence', COALESCE(
    (SELECT CAST(value AS INTEGER) + 1 FROM gateway_metadata WHERE key = 'global_sequence'),
    1
  ));
```
