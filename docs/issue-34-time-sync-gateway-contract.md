# Issue #34: Gateway Time Synchronization, Stale State, and Snapshot Resync

## Summary

This implementation provides the **gateway-side contract** for time synchronization, stale event detection, and snapshot-based client resync. It is renderer-agnostic and provides a testable API contract that any client (Unity, web, etc.) can consume.

**Status**: Gateway implementation complete and tested. Unity consumer not yet implemented (blocked - no Unity project exists).

## What Was Implemented

### 1. Per-Device Time/Sequence State

- **Stale event detection**: Events exceeding `TimeBounds.stale_threshold_ms` (default: 30 seconds) are flagged with `stale: true`
- **Out-of-order detection**: Events with timestamps earlier than the last-seen timestamp for that device are flagged with `out_of_order: true`
- **Latency tracking**: Transit latency (gateway receive time - source timestamp) is computed and stored
- Events are NOT rejected — they are stored with metadata so clients can make informed decisions

### 2. Timestamp Provenance and Synchronization State

**P1 fix — clock skew validity:**

The ESP32 telemetry bridge publishes `received_at_ms` as a **monotonic/uptime** timestamp, not UTC. Transit latency and clock-skew detection are NOT valid for these sources.

| Source field | Domain | Latency valid? | Clock skew valid? |
|---|---|---|---|
| `received_at_ms` present | Uptime / monotonic | ❌ `latency_ms = -1` | ❌ `is_clock_skew()` → False |
| `timestamp_ms` / `timestamp` only | UTC (NTP-synced host) | ✅ | ✅ if `is_timestamp_synchronized = True` |

`is_timestamp_synchronized: bool` is now an explicit field in `CanonicalEvent`:
- `True` → source timestamp is UTC; transit latency and clock skew are meaningful
- `False` → source timestamp is uptime; latency_ms = -1, clock skew always False

The normalizer detects unsynchronized sources by presence of `received_at_ms` in the MQTT payload (ESP32 telemetry wire format).

### 3. Canonical Snapshots / Reconnect Contract

**P2 fix — proper snapshot with watermarks and per-device state:**

- **GET /snapshot**: Returns events with `sequence > since_sequence`, sorted ascending
  - `since_sequence=N` → replay from cursor N (clients pass their last-known seq on reconnect)
  - `since_sequence=0` → full snapshot up to `limit`
- **high_watermark**: highest confirmed sequence in the store; clients compare against their local seq to detect gaps
- **per_device_latest**: most recent event per device_id (by sequence) — current state without replay
- **overflow**: True when store holds more events than `limit`; clients must request full snapshot
- **Overflow/resync behavior**: When retention limit is reached, oldest events are purged. Clients that missed events see a sequence gap (watermark > their max seq) and must call `/snapshot?since_sequence=0` to re-synchronize.
- **Interleaved writes during snapshot**: The store query is a consistent snapshot read; concurrent writes during the request do not corrupt the response.

### 4. SQLite Migration (P3 fix)

New columns added to `events` table (`event_timestamp_ms`, `received_at`, `latency_ms`, `stale`, `out_of_order`) are applied via `_migrate_schema()` on every `EventStore.init()`. Uses `PRAGMA table_info` to detect which columns exist and issues `ALTER TABLE ADD COLUMN` only for missing ones. Idempotent and safe on both fresh and pre-migration databases.

See: `iot-gateway/migrations/001_add_timing_columns.sql` for the raw SQL and `iot-gateway/src/iot_gateway/event_store.py::_migrate_schema()` for the Python implementation.

### 5. Sequence Persistence (P4 fix)

The global event sequence is persisted in a `gateway_metadata` table (`key='global_sequence'`, `value=<last_seq>`). On process restart, `EventStore._load_sequence()` reads the last value from DB, and subsequent inserts continue from that sequence. This makes ordering deterministic across restarts.

Limitation: the sequence counter is not globally atomic across concurrent gateway instances (single-process assumption). Multi-instance deployment requires an external atomic counter (Redis INCR, PostgreSQL sequence, etc.).

### 6. Metrics Accuracy (P5 fix)

- Metrics (`/metrics`) reflect only events that were **successfully persisted** — observe is called in the write worker AFTER `insert_dict` returns
- Queue overflow drops are tracked in `gateway._dropped_count` and exposed via `/health?queue_dropped_count`
- Pre-enqueue metrics call was removed; only post-persistence counts are reported
- `unsynchronized_event_count` in `/metrics` tracks events with `is_timestamp_synchronized=False`

## Files Changed

| File | Description |
|------|-------------|
| `iot-gateway/src/iot_gateway/models.py` | Added `is_timestamp_synchronized`, `received_at_ms` to CanonicalEvent |
| `iot-gateway/src/iot_gateway/time_sync.py` | `is_clock_skew()` → False when unsynced; added `unsynchronized_event_count` |
| `iot-gateway/src/iot_gateway/event_normalizer.py` | Detects uptime timestamps via `received_at_ms`; sets `is_timestamp_synchronized=False` |
| `iot-gateway/src/iot_gateway/event_store.py` | Schema migration, sequence persistence, `high_watermark()`, `per_device_latest()`, `since_sequence` query |
| `iot-gateway/src/iot_gateway/gateway.py` | Post-persistence metrics observe; `_dropped_count` counter |
| `iot-gateway/src/iot_gateway/api.py` | `/snapshot` with watermark/sequence; `/metrics` with queue_dropped; `/health` with watermark+dropped |
| `iot-gateway/src/iot_gateway/migrations/001_add_timing_columns.sql` | Raw SQL migration for manual DB upgrades |
| `iot-gateway/tests/test_time_sync.py` | P1-P5 tests: unsync detection, migration, sequence persistence, interleaved snapshot, post-persist metrics |

## API Contract

### Event Envelope

```json
{
  "event_id": "uuid",
  "device_id": "sf-bridge-001",
  "event_type": "telemetry",
  "payload": { ... },
  "mqtt_topic": "smart-factory/sf-bridge-001/telemetry",
  "mqtt_timestamp_ms": 1699999999000,
  "timestamp": 1699999999000,
  "received_at": "2024-01-01T12:00:00+00:00",
  "received_at_ms": 1699999999000,
  "latency_ms": 150,
  "stale": false,
  "out_of_order": false,
  "is_timestamp_synchronized": true,
  "ingested_at": "2024-01-01T12:00:00+00:00",
  "sequence": 42
}
```

For ESP32 telemetry (uptime source):
```json
{
  "device_id": "ukit-00000000",
  "mqtt_topic": "smart-factory/ukit-00000000/telemetry",
  "received_at_ms": 123456,
  "event_timestamp_ms": 123456,
  "latency_ms": -1,
  "is_timestamp_synchronized": false,
  "sequence": 43
}
```

### Endpoints

- `GET /events` — Query events with optional filters
- `GET /events/{id}` — Get single event
- `GET /snapshot?since_sequence=0&limit=1000` — Full or incremental snapshot with watermark
- `GET /metrics?queue_dropped_count=N` — Latency/jitter/stale/out-of-order/unsync counts
- `GET /health` — Event count, high watermark, queue dropped count

## Acceptance Criteria Check

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Per-device time/sequence state, reject/flag stale events | ✅ Implemented |
| 2 | Canonical snapshots for client resync (watermark + replay cursor) | ✅ `/snapshot` with high_watermark + since_sequence |
| 3 | Explicit stale/offline data state + timestamp domain flag | ✅ `stale`, `out_of_order`, `is_timestamp_synchronized` |
| 4 | Timestamp provenance: UTC vs uptime detection | ✅ `received_at_ms` detection, latency=-1 for uptime |
| 5 | SQLite migration for existing DBs | ✅ `_migrate_schema()` via PRAGMA table_info |
| 6 | Sequence persistence across restarts | ✅ `gateway_metadata` table |
| 7 | Post-persistence metrics (no pre-enqueue counting) | ✅ `observe()` moved to write worker |
| 8 | Queue overflow drop counter | ✅ `_dropped_count` + `/health` |
| 9 | Tests cover P1-P5 reviewer findings | ✅ New tests in `test_time_sync.py` |
