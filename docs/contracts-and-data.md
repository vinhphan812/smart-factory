# Integration contracts, identity and temporal semantics

## Current contract — authoritative bridge sources
Read `esp32-ukit-bridge/docs/mqtt-contract.md` and `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md` before implementation. Current ESP32 command: topic `smart-factory/bridge/command` with `{"id":102,"fields":["CONVEYOR_START","60"]}`; bridge result/status use `smart-factory/bridge/result` and `smart-factory/bridge/status`. Existing MQTT telemetry handling is not yet established as implemented. Do **not** assume per-device topics exist.

AMLP serial frames are `@BODY*CRC4\r\n` with CRC-16/CCITT-FALSE, CMD/ACK/TEL types, size bounds, correlation IDs and duplicate protection. UART ACK is not proof that the requested movement reached its final state.

## Proposed canonical event envelope (DESIGN ONLY; do not publish without issue #3 review)
```json
{
  "schema_version": "1.0.0",
  "event_id": "demo-001",
  "event_type": "device.state_changed",
  "factory_id": "aibot-lab",
  "device_id": "conveyor-01",
  "source": "simulator",
  "occurred_at": "2026-10-12T10:00:00Z",
  "received_at": "2026-10-12T10:00:00.100Z",
  "sequence": 1,
  "trace_id": "trace-001",
  "data": {"state": "RUNNING", "speed": 60}
}
```

Device IDs must be unique and shared across controllers, gateway, 3D actors, logs and robot target mapping. Sequence and clock behavior must be explicitly specified; MQTT arrival order is not a hardware clock. Stale state must be marked unknown. New versions require schema, golden examples, negative tests, compatibility notes and an upgrade plan.

## Commands and safety
Desired lifecycle: requested → authorized/rejected → queued → dispatched → ack_received → verified_success/failed/timed_out. Authorize identity, role, allowed capability, recent state, expiry/lease, safety policy, idempotence and recovery. No direct browser/AI MQTT actuation bypass; failed/missing validation is denied.

## Required tests
Malformed JSON, missing ID, over-range speed, unknown device, old command, duplicate ID, late ACK, malformed CRC, out-of-order telemetry, disconnect, resync, unsafe action and physical E-stop. Traces must clearly separate software simulation from actual device results.
