# Issue #27 — Combine-Module Orchestration & Production-Cycle Scheduler

**Status:** DESIGN ONLY — not implemented
**Issue:** #27
**Author:** Agent (design spec)
**Reviewer:** vinhphan812
**Related ADRs:** ADR-0002 (MQTT/AMLP contract), ADR-0006 (physical safety), ADR-0005 (canonical events), ADR-0013 (AI safety gate)

---

## 1. Production Cycle Model

### What is a cycle?

A **production cycle** is one end-to-end pass of one work item (raw material, semi-finished part, or package) through the Smart Factory's physical modules, from intake to output or parking. The cycle is complete when the work item reaches its terminal station (parking lot, output buffer) or a fault halts it mid-flow.

A cycle is defined by:

| Field | Description |
|---|---|
| `cycle_id` | UUID assigned at cycle creation |
| `item_type` | Classification of the work item (e.g. `raw-A`, `semi-B`) |
| `current_module` | Module ID currently holding or processing the item |
| `next_module` | Module ID queued to receive the item next |
| `state` | `IDLE | STARTING | RUNNING | COMPLETING | FAULT | RECOVERY` |
| `started_at` | Canonical timestamp (UTC, synchronized source) |
| `target_completion_at` | Deadline for the cycle (derived from throughput SLA) |
| `fault_reason` | Populated only when state = `FAULT` |

### How modules interact

Modules do not share memory. All cross-module signalling passes through the **orchestrator** (a stateful process, co-located with `factory-control`):

```
Module A (conveyor)                    Module B (sorter)
    │                                        │
    │── item sensor: ITEM_DETECTED@A ────────►│
    │                                        │ (sorting logic)
    │◄── MODULE_B_READY ─────────────────────│
    │                                        │
    │── ACTUATOR_COMPLETE ───────────────────►│
    │                                        │
    │  (A-gate opens; item moves to B)       │
```

Module interactions are mediated by the orchestrator's **module dependency graph** (see §3). No module commands another module directly.

### What triggers transitions

Transitions are triggered by **canonical events** flowing through the IoT gateway (`iot-gateway/src/iot_gateway/models.py` / `CanonicalEvent`):

| Event type | Trigger | Effect |
|---|---|---|
| `telemetry` | Sensor detects item at module | `MODULE_READY` flag set |
| `command_ack` | Module confirms actuator action | Orchestrator advances state machine |
| `status_offline` | Module heartbeat times out | Orchestrator enters `FAULT` state |
| `safety_gate` | ADR-0013 evaluation result | Permits or denies module command |

The orchestrator subscribes to `smart-factory/{deviceId}/telemetry` and `smart-factory/{deviceId}/command/ack` per device, per ADR-0002 topic patterns. Telemetry staleness (TTL = 5 s, configurable) transitions the device to `status_offline`.

---

## 2. Orchestration State Machine

```
                    ┌──────────────────────────────────────┐
                    │              IDLE                   │
                    │  (no active cycle; waiting for start)│
                    └──────────────┬───────────────────────┘
                                   │ START_CYCLE (operator or auto-trigger)
                                   ▼
                    ┌──────────────────────────────────────┐
                    │            STARTING                  │
                    │  (reserving first module; sending    │
                    │   MODULE_READY probe; safety check)  │
                    └──────┬───────────────────┬───────────┘
                           │ ack + sensor OK    │ timeout or safety DENY
                           ▼                    ▼
                    ┌──────────────┐    ┌──────────────────────────────────┐
                    │   RUNNING    │    │              FAULT                │
                    │ (item moving │    │  (module timeout, sensor miss,  │
                    │  through DAG)│    │   safety gate DENY, offline)    │
                    └──────┬───────┘    └──────┬───────────────────────────┘
                          │                     │
            DAG complete  │                     │ operator ACK + RESET_CMD
            or last ack   │                     ▼
                          ▼         ┌──────────────────────────────────┐
                    ┌───────────────────────────┐│           RECOVERY              │
                    │        COMPLETING         ││  (re-send unacked commands;     │
                    │ (final module confirmed;  ││   drain partial state;          │
                    │  cycle closed; event logged)││   then return to IDLE)          │
                    └───────────────────────────┘└──────────────────────────────────┘
```

### State descriptions

| State | Entry condition | Exit condition |
|---|---|---|
| `IDLE` | System boot or cycle completion | `START_CYCLE` received |
| `STARTING` | `START_CYCLE` event | Module ack + sensor ready, or timeout |
| `RUNNING` | First module confirmed running | All modules ack complete OR fault detected |
| `COMPLETING` | All module completions acknowledged | Cycle record persisted; → IDLE |
| `FAULT` | Any unhandled error | Operator `RESET_CMD`; → RECOVERY |
| `RECOVERY` | Fault cleared by operator | Stale commands flushed; → IDLE |

**Safety override:** In any state, a physical E-stop or ADR-0006 safety deny immediately drives the orchestrator to `FAULT`. The `RECOVERY` path requires explicit operator intervention — no auto-resume.

---

## 3. Module Dependency Graph

```
                    ┌─────────────┐
                    │  INTAKE     │
                    │  (raw feed) │  ← cycle starts here
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  CONVEYOR   │──► (upstream feeder belt)
                    │   BELT      │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ SORTING  │ │ SORTING  │ │ SORTING  │  ← parallel lanes (routing by item_type)
        │  LANE A  │ │  LANE B  │ │  LANE C  │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             └────────────┼────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ PACKAGING   │  ← item assembled/boxed
                   └──────┬──────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  OUTPUT /   │
                   │  PARKING    │  ← terminal station; cycle ends here
                   │    LOT      │
                   └─────────────┘
```

### Dependency constraints

- **CONVEYOR** depends on nothing; it is the first module in every cycle.
- **SORTING** (any lane) depends on CONVEYOR reaching `sensor_ready`.
- **PACKAGING** depends on at least one SORTING lane completing. All lanes may run in parallel.
- **OUTPUT/PARKING LOT** depends on PACKAGING completion.
- **Forklift** (planned, Issue #9/10) moves items between stations; its own dependency is OUTSIDE this DAG — it is a separate actuator invoked by the orchestrator when the dependency graph signals a move gate open.

### Module readiness model

Each module exposes a **readiness vector** via telemetry:

```json
{
  "device_id": "sorter-lane-A",
  "event_type": "telemetry",
  "data": {
    "ready": true,
    "holding_item": false,
    "fault": false,
    "sensor_states": {"entry": "CLEAR", "exit": "CLEAR"}
  }
}
```

The orchestrator blocks DAG transitions until all downstream module `ready = true`.

---

## 4. Scheduler Design

### Event-driven (primary)

The orchestrator is primarily **event-driven**, not polling-based. Each MQTT telemetry or command-ack event triggers an evaluation pass:

```
on event →
  1. validate event schema (CanonicalEvent)
  2. check staleness / out_of_order (models.py flags)
  3. advance dependency graph state
  4. if next module ready → dispatch command via ADR-0002 topic
  5. log transition in event store
```

**Why event-driven?** Physical telemetry arrives sporadically. Polling a stopped conveyor would produce false negatives and add latency. Event-driven also aligns with the gateway's existing `CanonicalEvent` model.

### Round-robin as fallback

For **multiple concurrent cycles** (throughput > 1 item at a time), a **weighted round-robin** scheduler selects the next cycle to advance when two or more cycles are `RUNNING` and have ready downstream modules. Priority weights are derived from `item_type` (higher value items get higher weight).

Round-robin is a **tiebreaker**, not the primary scheduler. If only one cycle is active, it always advances.

### Priority handling

| Priority level | Trigger | Behavior |
|---|---|---|
| P0 — E-stop | Physical estop signal (ADR-0006) | Abort all cycles; halt all actuators |
| P1 — Fault | Any module fault | Pause affected cycle; others continue if safe |
| P2 — Operator override | Human command via dashboard | Bypass DAG ordering (requires explicit safety re-check) |
| P3 — Normal cycle | Auto-trigger or operator start | Standard DAG progression |
| P4 — Idle drain | No active cycles, modules idle | No scheduling action; enter IDLE |

---

## 5. What Is NOT Yet Implemented

The following are **planned / not yet committed**:

| Component | Status | Blocker |
|---|---|---|
| `factory-control/` module adapters | **PLANNED** — no code | Hardware wiring, electrical levels, controller interfaces unverified |
| Module dependency graph (DAG executor) | **NOT IMPLEMENTED** | Needs factory-control adapter contracts |
| Orchestration state machine | **NOT IMPLEMENTED** | Needs state machine framework + event routing |
| Production cycle model (`cycle_id`, `item_type`, etc.) | **NOT IMPLEMENTED** | Needs schema + event store schema |
| Event-driven scheduler | **NOT IMPLEMENTED** | Needs gateway event subscription |
| Round-robin fallback | **NOT IMPLEMENTED** | Blocked on cycle model |
| MQTT command dispatch per ADR-0002 (`smart-factory/{deviceId}/command/down`) | **NOT YET WIRED** | Bridge telemetry pipeline incomplete (Issue #66) |
| Staleness TTL enforcement per module | **NOT IMPLEMENTED** | Needs `received_at_ms` + TTL logic in orchestrator |
| Physical E-stop → orchestrator `FAULT` wiring | **NOT IMPLEMENTED** | Requires ADR-0006 Layer 3 Mega firmware integration |
| Multi-cycle concurrency | **NOT IMPLEMENTED** | Blocked on DAG executor |

**No code exists yet** for the orchestrator or scheduler. The `factory-control/README.md` explicitly marks the module as `PLANNED`.

---

## 6. Relationship to ADR-0002 and ADR-0006

### ADR-0002 — Bridge MQTT ↔ AMLP Contract

The orchestrator consumes telemetry events published by the bridge on `smart-factory/{deviceId}/telemetry` (ADR-0002 §Uplink). It dispatches commands on `smart-factory/{deviceId}/command/down` (ADR-0002 §Downlink). All orchestrator commands MUST conform to the ADR-0002 envelope:

```json
{
  "command_id": "<uint32, dedup key>",
  "command_name": "CONVEYOR_START" | "CONVEYOR_STOP" | "SET_OUTPUT" | "PING" | "RESET",
  "arguments": [<channel>, <value>]
}
```

The orchestrator does NOT bypass the bridge to send raw AMLP frames. Module commands travel MQTT → bridge → UART → Mega → sensors → bridge → MQTT → gateway → orchestrator.

**ADR-0009 schema mismatch** (`timestamp`/`state` vs `received_at_ms`/`values`/`pairs`) means the orchestrator must handle both legacy and canonical telemetry shapes until schema compatibility is resolved.

### ADR-0006 — Local Physical Safety

ADR-0006 enforces safety at four layers. The orchestrator sits at **Layer 1 (MQTT ACL)** and must enforce:

1. **No actuator command may issue without a valid `command_ack` window** — the orchestrator holds commands in `PENDING` until a safety gate (`SafetyGate`, ADR-0013) evaluates them.
2. **Physical E-stop from Mega firmware (Layer 3) immediately drives the orchestrator to `FAULT`** — the bridge publishes `status_offline` on disconnect; the orchestrator treats this as `FAULT`, not merely `IDLE`.
3. **The orchestrator cannot override Mega's safety decisions** — it receives the Mega-enforced result and adapts the DAG accordingly.
4. **No module receives a command while in `FAULT` state** — all pending commands are held until `RECOVERY` completes.

The orchestrator does NOT replace Mega firmware safety enforcement. It is a **logical sequencing layer**, not a safety-critical controller.

---

## Open Questions

- **Concurrent cycle limit:** How many simultaneous in-flight items can the factory physically support? Needs hardware capacity analysis (blocked on Issue #9/10 adapter specs).
- **Cycle abort vs. retry:** On fault, does the item remain at its last module (retry) or return to intake (abort)? Decision depends on module reset behavior.
- **Gateway ↔ orchestrator co-location:** Should the orchestrator run inside `iot-gateway` or as a separate `factory-control` service? Affects fault isolation and deployment topology.
- **ADR-0009 schema resolution:** Telemetry schema mismatch must be resolved before the orchestrator can reliably parse module state.
