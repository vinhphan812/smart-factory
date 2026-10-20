# ADR-0009: Telemetry Schema Compatibility

**Status:** Superseded ✅ by v2 schema
**Date:** 2026-10-14
**Superseded by:** Issue #166 - `contracts/gateway/telemetry-schema-v2.md`
**Deciders:** Issue #65 #66
**Related issues:** #65 #66 #166

## Context

There is a known mismatch between the canonical telemetry schema (`contracts/v1/schemas/telemetry.schema.json`) and the actual telemetry payload produced by the ESP32 bridge firmware.

This ADR documents the current state and the required resolution path.

## Current Schemas

### Canonical schema (`contracts/v1/schemas/telemetry.schema.json`)

```json
{
  "device_id": "string",
  "timestamp": "ISO8601 string",
  "state": "object"
}
```

### Actual bridge telemetry (via `publishTelemetry()` in `mqtt_bridge.cpp`)

```json
{
  "device_id": "string",
  "received_at_ms": 1234567890,
  "values": ["raw", "values"],
  "pairs": {"key": "value"},
  "truncated": false,
  "overflow_dropped_values": 0,
  "overflow_dropped_pairs": 0
}
```

**Key differences:**
| Field | Canonical | Actual bridge |
|-------|----------|-------------|
| Timestamp | `timestamp` (ISO8601 UTC) | `received_at_ms` (milliseconds since boot) |
| Content | `state` (generic object) | `values` (array) + `pairs` (key-value) |
| Overflow | Not specified | Explicit overflow counters |
| `device_id` | Present | Present (correct) |

## Decision

The canonical schema requires a **versioned compatibility bridge** before being promoted as cross-system authoritative:

1. **Short-term:** `telemetry.schema.json` is marked as **proposed** (not canonical) in `contracts/`
2. **Gateway translator** must transform `received_at_ms` → `timestamp` using gateway wall clock + offset estimation
3. **Long-term (Issue #66):** Bridge firmware emits `timestamp` in UTC and `state` field directly, deprecating `received_at_ms`, `values`, and `pairs`

**Acceptance criteria for canonical promotion:**
- `timestamp` is ISO8601 UTC (not `received_at_ms`)
- `state` field contains structured key-value data (not `pairs`)
- `values` (raw array) is either removed or formally documented as a separate variant
- Producer and consumer examples in `contracts/v1/examples/` are validated against the schema

## Resolution (Issue #166)

This ADR was resolved by implementing Option C (versioned schema v2) via Issue #166.

**Resolution artifact:** `contracts/gateway/telemetry-schema-v2.md`

Key decisions implemented:
1. v2 schema wraps raw ESP32 payload (`received_at_ms`, `values[]`, `pairs{}`) alongside structured translation
2. Gateway translator normalizes raw format to structured `state`/`speed`/`sensors`
3. Time domain normalized via gateway wall-clock offset estimation
4. Phase-based migration: gateway translator → dual-format → firmware update
5. v1 telemetry schema marked deprecated; deprecation deadline 2026-12-31

## Consequences

**Until resolved:**
- Gateway must implement a translator from `received_at_ms` to `timestamp`
- Dashboard/twin must handle both `state` and `pairs` fields
- Any new consumer must understand the bridge's non-canonical format

**After resolution:**
- Single canonical schema for all telemetry across all device types
- Schema validation catches format mismatches at the gateway boundary
- `iot-gateway/` consumers can rely on stable field names

## Alternatives considered

**Option A: Update bridge firmware to match canonical schema immediately**
- Rejected: requires firmware version bump, may break existing consumers, out of scope for current sprint

**Option B: Update canonical schema to match bridge output**
- Rejected: canonical schema represents the desired cross-system contract; changing it to match an interim implementation locks in a suboptimal format

**Option C: Version the telemetry schema (v1 vs v2)**
- Bridge emits `telemetry.schema.json` version field with both formats coexisting
- Allows gradual migration
- Recommended as the resolution path; tracked in Issue #66

## Evidence

- `contracts/README.md` Section "Source of truth": explicit note about this mismatch
- `contracts/v1/schemas/telemetry.schema.json` — canonical schema (marked pending)
- `esp32-ukit-bridge/esp32/src/mqtt_bridge.cpp` `publishTelemetry()` — actual telemetry format
- `esp32-ukit-bridge/docs/mqtt-contract.md` — bridge-side contract
- Issue #66: "Bridge MQTT telemetry pipeline" — telemetry uplift
