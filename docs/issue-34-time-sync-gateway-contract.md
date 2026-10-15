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

### 2. Canonical Snapshots / Reconnect Contract

- **GET /snapshot**: Returns all stored events sorted by ascending `sequence` for deterministic replay
- **GET /metrics**: Returns latency histograms, jitter, stale event count, and out-of-order event count
- Events include:
  - `event_timestamp_ms`: Authoritative source timestamp
  - `received_at`: Gateway receive time (ISO 8601)
  - `latency_ms`: Transit latency in milliseconds
  - `stale`: Boolean flag for stale events
  - `out_of_order`: Boolean flag for out-of-order events

### 3. Explicit Stale/Offline Data State

- Configurable staleness threshold via `TimeBounds(stale_threshold_ms=N)`
- Events store `stale` and `out_of_order` flags in SQLite
- API responses include these flags so clients can distinguish fresh vs. stale data

## Files Changed

| File | Description |
|------|-------------|
| `iot-gateway/src/iot_gateway/models.py` | Added timing fields to CanonicalEvent |
| `iot-gateway/src/iot_gateway/time_sync.py` | New: TimeBounds and TimeMetrics classes |
| `iot-gateway/src/iot_gateway/event_normalizer.py` | Added staleness/out-of-order detection |
| `iot-gateway/src/iot_gateway/event_store.py` | Added timing columns to EventRecord |
| `iot-gateway/src/iot_gateway/gateway.py` | Integrated time bounds and metrics |
| `iot-gateway/src/iot_gateway/api.py` | Added /snapshot and /metrics endpoints |
| `iot-gateway/tests/test_time_sync.py` | New: 22 tests covering all acceptance criteria |

## Test Results

```
22 passed (time sync tests)
36 passed (existing gateway tests)
Total: 58 passed
```

## Unity Consumer Limitation

**No Unity project exists in this repository.** The gateway contract is complete and provides:

1. WebSocket events with timing metadata
2. REST endpoints for snapshot and metrics
3. Comprehensive test coverage

A Unity consumer would need to:

1. Connect to WebSocket at `ws://<gateway>/ws` to receive real-time events
2. Call `GET /snapshot` on reconnect to restore state
3. Check `stale` and `out_of_order` flags before treating data as authoritative
4. Use `event_timestamp_ms` for display/visualization timestamps

This is left as future work until a Unity project is created in the repository.

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
  "latency_ms": 150,
  "stale": false,
  "out_of_order": false,
  "ingested_at": "2024-01-01T12:00:00+00:00",
  "sequence": 42
}
```

### Endpoints

- `GET /events` — Query events with optional filters
- `GET /events/{id}` — Get single event
- `GET /snapshot` — Full scene snapshot (sorted by sequence)
- `GET /metrics` — Latency/jitter/stale/out-of-order counts

## Acceptance Criteria Check

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Per-device time/sequence state, reject/flag stale events | ✅ Implemented |
| 2 | Canonical snapshots for client resync | ✅ /snapshot endpoint |
| 3 | Explicit stale/offline data state | ✅ stale/out_of_order flags |
| 4 | Tests cover late/out-of-order/duplicate, clock skew, reconnect | ✅ 22 tests |
| 5 | Exercise Python test suite | ✅ 58 passed |
| 6 | Minimal docs explaining gateway contract | ✅ This document |
