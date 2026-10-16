# ADR-0012: Unity Digital Twin Prefab Contracts — Coordinate & State Decisions

**Status:** Proposed
**Date:** 2026-10-16
**Deciders:** Issue #33
**Related issues:** #33, #11, #62, #66

---

## Context

The Smart Factory Digital Twin requires well-defined contracts for each physical module so that Unity prefabs can be authored and tested independently of firmware and gateway code. Three architectural decisions must be made:

1. **Telemetry binding** — How the twin binds MQTT telemetry fields to Unity prefab properties. The bridge emits raw `values[]`/`pairs{}` arrays; the canonical `state` object format is planned but not yet implemented (ADR-0009, Issue #66).
2. **Coordinate / transform conventions** — How 3D prefab transforms map to the physical factory layout. ADR-0003 flagged institutional approval as unverified; no coordinate system is currently defined in code.
3. **Command interface** — Whether Unity prefabs may issue commands and what workflow enforces actuator limits before MQTT publish.

The nine-module physical system consists of one shared conveyor and up to eight per-station actuator devices, each an independent ESP32-uKit bridge with its own device ID.

---

## Decision

We make four binding decisions for the Digital Twin prefab contract:

### 1 — Telemetry Binding: Array-Index Convention (Until Canonical Format Promoted)

The twin prefab contract maps telemetry fields by **zero-based array index** and **key name** for `pairs`. This is the only binding possible today given the bridge's current output format.

```
values[0] → module_type   (e.g. "CONVEYOR", "ACTUATOR")
values[1] → state_raw    (e.g. "RUNNING", "IDLE", "CH2")
values[2] → speed / value (e.g. "60", "1")
pairs["SENSOR1"] → bool entry_sensor
pairs["SENSOR2"] → bool exit_sensor
```

- Prefabs **must validate index bounds** before accessing `values[N]` — the bridge silently drops fields beyond 6 plain values.
- Prefabs **must parse all values as strings** before using them as numbers or enums.
- The `received_at_ms` field is used for ordering; no in-order delivery guarantee.
- Telemetry is marked **stale** when no new frame arrives within **60 000 ms** (`kTelemetryTimeoutMs`).
- When ADR-0009 is resolved (canonical `state` object), this binding is replaced; the index convention is retained for the **L0 static contract** phase.

### 2 — Coordinate Conventions: Deferred Until Institutional Approval

No world coordinate system, axis orientation, or scale is defined in code or approved by the institutional owner.

**Decision: defer all transform decisions until ADR-0003 institutional approval is verified.** Prefabs should:

- Store transform values as parameters (not hard-coded constants).
- Apply a **default world origin at (0, 0, 0)** for the shared conveyor's entry sensor.
- Document all transform parameters in the prefab's header comment block.
- **Do not** assume a fixed conveyor axis direction without a physical layout spec reviewed by the institutional owner.

This decision is recorded to prevent hard-coded assumptions from entering prefab assets before review.

### 3 — Command Interface: Twin as Read-Only Until Safety Gate

Unity prefabs act as **observers only** — they consume telemetry and status events. Commands are not issued by the twin.

**Rationale:** Issuing commands from the digital twin bypasses physical actuator limits, operator override, E-stop, and fresh context checks as documented in AGENTS.md. Any future command path from twin to physical must pass through a safety gate (ADR-0011 Dashboard Safety) and the gateway's command topic, with actuator-limit enforcement upstream.

| Capability | Allowed today |
|---|---|
| Read telemetry via WebSocket | Yes |
| Display status / state | Yes |
| Trigger local prefab animation (no physical effect) | Yes |
| Issue `CONVEYOR_START` / `CONVEYOR_STOP` via MQTT | No — safety gate not defined |
| Issue `SET_OUTPUT` via MQTT | No — safety gate not defined |
| Send command via gateway REST API | No — endpoint not exposed |

### 4 — Module Contracts as Specification, Not Implementation

Each module's contract (`docs/twin/prefab-module-contracts.md`) documents the **schema contract** the twin prefab must satisfy. The contracts are:

- **L0 static** — textual schema, no runtime verification.
- **Language-agnostic** — applicable to any twin engine consuming the gateway's WebSocket or REST API.
- **Versioned** — breaking changes require a new ADR and version bump.
- **No Unity C# assets** — no `.prefab`, `.mat`, `.controller`, or script files.

---

## Consequences

**Positive:**
- Prefab authors have a stable, versioned contract to work against before hardware is available.
- Gateway event envelope (`CanonicalEvent`) is fully documented; no ambiguity about `event_type` values.
- Safety boundary between twin observation and physical control is explicit, preventing accidental bypass.
- Schema mismatch is acknowledged and tracked (ADR-0009 / Issue #66), not papered over.

**Negative / Risks:**
- Array-index binding is fragile — adding a new field shifts indices and silently breaks consumers. This is the primary motivation to promote the canonical `state` format (Issue #66).
- Coordinate deferral means prefabs cannot be fully positioned until ADR-0003 is resolved; partial progress only.
- Telemetry topic not in `DEFAULT_TOPICS` in current gateway config — routing must be verified before twin can consume telemetry.
- `mqtt_timestamp_ms` is always 0; `received_at_ms` is relative to bridge boot, not wall-clock — cross-device ordering is unreliable without NTP or offset estimation.
- WebSocket slow-client disconnection (queue full → drop) means telemetry gaps can appear without explicit signalling.

**Neutral:**
- Twin read-only constraint means no simulation-of-control is possible until a safety gate ADR is written and approved.

---

## Alternatives Considered

We considered four alternatives before reaching these decisions.

### Alt A: Bind telemetry by key lookup in `values[]` instead of index

Parse the array as key-value pairs. Rejected because the bridge output is a flat ordered list with no key tags — key lookup requires prepending a known type prefix which requires firmware changes outside the scope of this ADR.

### Alt B: Expose command API from twin now, relying on physical interlock

Issue commands from Unity and trust that MEGA firmware enforces actuator limits. Rejected — AGENTS.md explicitly prohibits AI/twin bypassing of actuator limits; a safety gate ADR is required before any command path is exposed.

### Alt C: Lock coordinate system to +X conveyor, Z depth now

Assume the conveyor runs +X and station spacing is 600 mm. Rejected — institutional approval unverified per ADR-0003; locking a coordinate convention prematurely risks requiring rework when the physical layout is reviewed.

### Alt D: Adopt a JSON Schema for prefab contracts

Define `prefab-module-contracts.schema.json` with `$id`, `$schema`, `type`, `properties`, and required fields. Deferred — the flat `values[]`/`pairs{}` format cannot be validated by a simple JSON Schema without custom keywords; ADR-0009 resolution (canonical `state` object) is the right time to introduce schema validation.

---

## Evidence

- `esp32-ukit-bridge/docs/mqtt-contract.md` — Bridge MQTT/AMLP contract (source of truth)
- `iot-gateway/src/iot_gateway/models.py` — `CanonicalEvent`, `EventType` enum
- `iot-gateway/src/iot_gateway/event_normalizer.py` — `TOPIC_PATTERNS`, `STATUS_CODE_MAP`
- `iot-gateway/src/iot_gateway/api.py` — `WebSocketServer.broadcast()`, `create_http_app()`
- `iot-gateway/src/iot_gateway/config.py` — `DEFAULT_TOPICS` (telemetry not subscribed)
- `docs/adr/adr-0003-digital-twin-engine.md` — Engine decision (Unity), institutional approval unverified
- `docs/adr/adr-0009-telemetry-schema-compatibility.md` — Known bridge/canonical mismatch
- `docs/adr/adr-0011-dashboard-safety.md` — Safety gate for command issuing
- `docs/PROJECT_CONTEXT.md` — AGENTS.md constraints on AI/Twin bypass
- `docs/twin/prefab-module-contracts.md` — Per-module telemetry/command schema contracts
- Issue #33 — Unity prefab contracts
- Issue #66 — Bridge telemetry pipeline (canonical format uplift)
- Issue #11, #62 — Engine decision history
