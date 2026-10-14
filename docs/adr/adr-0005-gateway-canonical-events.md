# ADR-0005: Gateway Canonical Event Envelope

**Status:** Proposed
**Date:** 2026-10-14
**Deciders:** Issue #7
**Related issues:** #7 #8 #31 #32

## Context

The ESP32 bridge publishes telemetry to MQTT topics (`smart-factory/{deviceId}/telemetry`). The iot-gateway consumes these topics and must normalize them into a canonical event envelope for downstream consumers (dashboard, digital twin, AI robot).

Different producers (ESP32 bridge, future controllers, simulators) may use different field names, timestamps, and event structures. The gateway must normalize these to a single canonical format.

## Decision

The iot-gateway normalizes all incoming events into a **canonical event envelope** with the following structure:

```json
{
  "event_id": "uuid-v4",
  "device_id": "string",
  "event_type": "telemetry|status|command_result|alert",
  "timestamp": "ISO8601 UTC",
  "received_at": "ISO8601 UTC (gateway ingest time)",
  "payload": { ... },
  "trace_id": "optional correlation ID"
}
```

**Key properties:**
- `event_id` — UUID v4 generated at ingest; used for deduplication
- `timestamp` — original event time in UTC (producer-side, not gateway clock)
- `received_at` — gateway wall clock at ingest (monotonicity guarantee)
- `payload` — producer-specific content, schema-validated
- `trace_id` — bridges MQTT correlation to distributed trace (if provided)

**Preservation requirements:**
- `device_id` MUST NOT be truncated or remapped without a documented mapping
- Original field names preserved in `payload`; transformation documented in `contracts/v1/`
- Duplicate detection via `event_id` (not timestamp or content hash)

**Routing:**
- Validated events → WebSocket stream, HTTP REST API
- Malformed/unknown-device events → quarantine log (not silently dropped)
- Retained MQTT status messages → event store snapshot table

## Consequences

**Easier:**
- Dashboard/twin consume a single canonical format regardless of source
- New device types can be added by implementing a translator (not rewriting consumers)
- Deduplication via UUID prevents double-display in dashboards

**Harder:**
- Gateway must validate and transform events — adds latency
- Schema changes require coordinated updates across all consumers
- `event_id` UUID generation adds storage overhead

## Alternatives considered

**Option A: Pass-through (no normalization)**
- Gateway forwards MQTT payloads verbatim
- Rejected: consumers must understand all producer formats; adding a new device requires updating all consumers

**Option B: Per-device envelopes with device-type prefixes**
- `{"sensor.temperature": {...}, "device": "sensor-01"}`
- Rejected: no unified schema validation, harder to query across device types

**Option C: Protobuf/AVRO binary canonical format**
- Efficient binary encoding
- Rejected: human-unreadable, harder to debug, requires schema registry deployment

## Evidence

- `iot-gateway/src/` — current gateway implementation
- `iot-gateway/tests/` — integration tests (TC1–TC6 in Issue #7)
- `contracts/v1/schemas/device-event.schema.json` — event envelope schema
- Issue #7: "Implement MQTT ingestion gateway with offline simulator"
- Issue #31: "Implement durable event store, snapshots and retention policy"
- Issue #32: "Define device registry and configuration ownership"
