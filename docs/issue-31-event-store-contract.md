# Issue #31 — Event Store & Snapshots: Implementation Contract

**Status:** Draft spec
**Related issues:** #7, #8, #31, #32
**Reference ADR:** [ADR-0005 Gateway Canonical Event Envelope](./adr/adr-0005-gateway-canonical-events.md)
**Author:** Agent (coordinator)
**Reviewer:** vinhphan812

---

## 1. Overview

The `iot-gateway` event store provides durable, append-only storage for all canonical events ingested from MQTT topics. It is implemented as a single SQLite file using SQLAlchemy 2.x async. It lives at `iot-gateway/src/iot_gateway/event_store.py`.

> **Scope of this document:** It describes what is **currently implemented**, what retention behaviour exists, and what is **not yet implemented** as of the current codebase. Do not assume a feature is live just because it appears in this document — check the Implementation Status tags.

---

## 2. Current Implementation

### 2.1 Database Backend

| Property | Value |
|---|---|
| Engine | SQLite via `sqlalchemy.ext.asyncio` + `aiosqlite` |
| Database URL | Configurable via `DATABASE_URL` env var (default: `sqlite+aiosqlite:///gateway.db`) |
| Async driver | `aiosqlite` |
| Lock timeout | 30 s (SQLite `timeout=30` connect arg) |
| Schema init | `Base.metadata.create_all` — no Alembic migrations |

`migrations/` directory does not exist. Schema is created on first `EventStore.init()` call. This means the schema is not version-controlled via a migration tool.

### 2.2 EventRecord Table (events)

```sql
CREATE TABLE events (
    event_id   TEXT PRIMARY KEY,    -- UUID v4 string
    device_id  TEXT NOT NULL,       -- indexed
    event_type TEXT NOT NULL,       -- indexed
    payload    JSON,                -- SQLite JSON column (SQLAlchemy JSON type)
    mqtt_topic TEXT NOT NULL,
    mqtt_timestamp_ms INTEGER NOT NULL DEFAULT 0,
    ingested_at TEXT NOT NULL,      -- ISO8601 with timezone (stored as naive text)
    sequence   INTEGER NOT NULL    -- indexed
);
```

Columns map 1:1 to `CanonicalEvent.to_dict()` (defined in `iot-gateway/src/iot_gateway/models.py`).

### 2.3 EventType Enum

```python
class EventType(str, Enum):
    COMMAND_ACK  = "command_ack"   -- implemented
    STATUS_ONLINE  = "status_online" -- implemented
    STATUS_OFFLINE = "status_offline" -- implemented
    TELEMETRY    = "telemetry"     -- marked future in models.py
    HEARTBEAT    = "heartbeat"     -- marked future in models.py
```

`TELEMETRY` and `HEARTBEAT` are defined but not wired in the current `EventNormalizer`.

### 2.4 EventStore Class

`EventStore` (`event_store.py`) is the single public class. Key methods:

| Method | Signature | Notes |
|---|---|---|
| `init` | `async init()` | Creates tables via `create_all` |
| `insert` | `async insert(event: CanonicalEvent)` | Converts to dict, calls `insert_dict` |
| `insert_dict` | `async insert_dict(event_dict: dict)` | **Write path.** Inserts then checks retention. Uses separate session for insert vs. purge. |
| `query` | `async query(device_id, event_type, limit)` | Filters + `ORDER BY sequence DESC` |
| `get` | `async get(event_id)` | Lookup by primary key |
| `count` | `async count()` | `SELECT COUNT(*)` |
| `close` | `async close()` | Disposes engine |

**Write queue and workers:** `Gateway` (`gateway.py`) uses an `asyncio.Queue` (max 500) to decouple MQTT callbacks from SQLite writes. Two `_write_worker` tasks drain the queue and call `store.insert_dict()`. This is the only path for event persistence.

**Atomicity note:** `insert_dict` opens two independent sessions — one for the INSERT, one for the retention purge. If the process crashes between them, no rollback occurs. The purge is best-effort, not transactional with the insert.

### 2.5 Sequence Assignment

The `sequence` column exists and is indexed, but **no atomic counter is implemented in the store**. `sequence` is assigned externally — likely by the caller of `CanonicalEvent.to_dict()`. The `EventStore` itself does not call `SELECT MAX(sequence) + 1` or maintain any counter table. Multiple gateway instances writing concurrently would produce duplicate or colliding sequences with no database-level guard.

---

## 3. Retention Policy

### 3.1 Current Mechanism (In-Process, Post-Insert)

Retention is enforced **inline inside `insert_dict`** after each successful INSERT:

```
count = SELECT COUNT(*) FROM events
if count > max_events:
    excess = count - max_events
    DELETE FROM events WHERE sequence IN (
        SELECT sequence FROM events ORDER BY sequence ASC LIMIT excess
    )
```

`max_events` defaults to `10000`, configurable via `MAX_EVENTS` env var.

### 3.2 Properties

- **Scope:** Single-process only. No background cleanup job.
- **Trigger:** On every `insert_dict` call.
- **Unit of deletion:** `excess` oldest events by ascending `sequence`.
- **No age-based retention:** No TTL, no purge by `ingested_at` date.
- **Gap risk:** If the process crashes after insert but before the DELETE, the count can temporarily exceed `max_events`.

---

## 4. Snapshot Format

> **Status: NOT IMPLEMENTED**

ADR-0005 §"Retained MQTT status messages → event store snapshot table" references a snapshot table that does not exist in the current codebase.

The `events` table stores all canonical events, including `STATUS_ONLINE` / `STATUS_OFFLINE`. A lightweight "latest status per device" snapshot read is achievable by querying `events` filtered by `device_id` + `event_type` ordered by `sequence DESC LIMIT 1`, but no separate snapshot table or materialized view exists.

No dedicated snapshot write path, snapshot read API, or snapshot-specific storage format has been implemented.

---

## 5. What Is NOT Yet Implemented

| Gap | Description | Severity |
|---|---|---|
| **No `GatewayMetadata` / atomic counter table** | No SQLite table tracks `global_sequence`. `sequence` is assigned externally. Concurrent multi-instance writers will produce collisions. | High |
| **No dedicated snapshot table** | ADR-0005 references a snapshot table for retained MQTT status messages. This does not exist. | Medium |
| **No background cleanup / retention job** | Retention is enforced inline per insert in-process only. No cron/worker, no TTL-based purge. If `insert_dict` is never called, no cleanup runs. | Medium |
| **No Alembic migrations** | Schema is created via `create_all`. No migration history, no rollback path for schema changes. | Low |
| **`TELEMETRY` and `HEARTBEAT` event types not wired** | Enum values exist in `models.py` but the `EventNormalizer` does not route MQTT topics to these types. | Low |
| **No sequence uniqueness constraint** | `sequence` column has no `UNIQUE` or `AUTOINCREMENT` guard. Deduplication is via `event_id` primary key only. | Medium |

---

## 6. Relationship to ADR-0005

ADR-0005 ("Gateway Canonical Event Envelope") is the **design foundation** for this event store. Key alignment points:

| ADR-0005 Commitment | Current Implementation Status |
|---|---|
| `event_id` — UUID v4 for deduplication | ✅ Implemented (`CanonicalEvent.event_id`, `events.event_id TEXT PRIMARY KEY`) |
| `device_id` MUST NOT be truncated | ✅ Implemented (`events.device_id TEXT NOT NULL`) |
| Original fields preserved in `payload` | ✅ Implemented (`events.payload JSON`) |
| `mqtt_topic` retained | ✅ Implemented (`events.mqtt_topic TEXT NOT NULL`) |
| `mqtt_timestamp_ms` (producer-side time) | ✅ Implemented |
| `ingested_at` (gateway wall clock) | ✅ Implemented |
| `sequence` for ordering | ✅ Column exists; atomic counter NOT implemented |
| Quarantine for malformed events | ⚠️ Logged only; no quarantine table |
| Retained MQTT status → snapshot table | ❌ Snapshot table not implemented |
| Trace / correlation ID field | ❌ `trace_id` not present in `CanonicalEvent` model |

ADR-0005's snapshot table reference (consequences section) is **unresolved** in the current implementation. This spec should be updated when the snapshot feature is implemented.

---

## 7. Evidence & References

| Artifact | Location |
|---|---|
| EventStore source | `iot-gateway/src/iot_gateway/event_store.py` |
| CanonicalEvent model | `iot-gateway/src/iot_gateway/models.py` |
| Gateway orchestration | `iot-gateway/src/iot_gateway/gateway.py` |
| Config + defaults | `iot-gateway/src/iot_gateway/config.py` |
| Event store unit tests | `iot-gateway/tests/test_store.py` |
| ADR-0005 | `docs/adr/adr-0005-gateway-canonical-events.md` |
| Project context | `docs/PROJECT_CONTEXT.md` |

---

## 8. Open Questions

1. Should `sequence` be an auto-increment primary key instead of a separate indexed column, given that `event_id` already serves as PK?
2. Is the inline retention purge acceptable for production, or should a background task be added?
3. Does the snapshot table need a separate TTL independent of event retention?
4. Should `GatewayMetadata` (atomic counter) be added before multi-instance deployment?
