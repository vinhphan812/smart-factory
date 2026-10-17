# Issue #31 — Event Store Implementation Follow-up

**Date:** 2026-10-17
**Author:** dev-backend
**Task:** t_c90cc980
**Status:** Complete

---

## Purpose

This document is a follow-up to [issue-31-event-store-contract.md](./issue-31-event-store-contract.md). It compares the contract doc's "NOT IMPLEMENTED" items against the current codebase and reports the implementation status.

---

## Implementation Status vs. Contract Doc

### ✅ RESOLVED — Previously NOT IMPLEMENTED

| Gap (from contract doc) | Current Status | Evidence |
|---|---|---|
| **No `GatewayMetadata` / atomic counter table** | ✅ RESOLVED | `GatewayMetadata` class at `event_store.py:90-99`. Sequence persisted in `gateway_metadata` table. `_increment_sequence()` method (lines 204-228) provides atomic counter using `UPDATE ... RETURNING`. |
| **No sequence assignment** | ✅ RESOLVED | Sequence is now assigned atomically via `_increment_sequence()`. If caller provides no sequence, store auto-assigns via atomic increment (see `insert_dict` lines 254-257). |
| **No `high_watermark()` method** | ✅ RESOLVED | Implemented at `event_store.py:379-388`. Returns max sequence. Exposed via `/snapshot` API endpoint (`api.py:161-165`). |
| **No `per_device_latest()` method** | ✅ RESOLVED | Implemented at `event_store.py:390-419`. Returns most recent event per device. Exposed via `/snapshot` API (`api.py:237-246`). |
| **No snapshot read API** | ✅ RESOLVED | `/snapshot` endpoint implemented in `api.py`. Returns `high_watermark`, `per_device_latest`, and event list with sequence cursors. |
| **Timing columns missing** | ✅ RESOLVED | Schema migration adds columns: `event_timestamp_ms`, `received_at`, `latency_ms`, `stale`, `out_of_order`. Migration runs idempotently via `_migrate_schema()` (lines 126-170). |

### ❌ STILL NOT IMPLEMENTED

| Gap | Description | Severity |
|---|---|---|
| **No dedicated snapshot table** | ADR-0005 references a snapshot table for retained MQTT status messages. Still not implemented — query `events` table for latest status per device instead. | Medium |
| **No Alembic migrations** | Schema is created via `create_all` + PRAGMA-based migration. No Alembic history. | Low |
| **TELEMETRY and HEARTBEAT not wired** | Enum values exist in `models.py` but `EventNormalizer` does not route MQTT topics to these types. | Low |
| **No background cleanup job** | Retention is still enforced inline per `insert_dict`. No cron/worker. | Medium |
| **No trace_id field** | `trace_id` not present in `CanonicalEvent` model. | Low |

---

## Summary

The contract doc identified **6 major gaps** in the original implementation. As of this review:

- **5 gaps are RESOLVED** — atomic sequence counter, `high_watermark()`, `per_device_latest()`, snapshot API, timing columns.
- **5 gaps remain OPEN** — snapshot table, Alembic, event type wiring, background retention, trace_id.

The event store now provides restart-proof sequence numbering and a functional snapshot read API, satisfying the core requirements for issue #31.

---

## References

| Artifact | Location |
|---|---|
| EventStore (current) | `iot-gateway/src/iot_gateway/event_store.py` |
| API endpoints | `iot-gateway/src/iot_gateway/api.py` |
| CanonicalEvent model | `iot-gateway/src/iot_gateway/models.py` |
| Original contract | `docs/issue-31-event-store-contract.md` |
