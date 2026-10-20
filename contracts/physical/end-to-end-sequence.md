# Physical Factory End-to-End Material Flow Sequence

**Status:** Proposed design contract (L0 only). Canonical single-unit material flow
supplementing [`factory-interface.md`](./factory-interface.md) and
[`capability-matrix.md`](./capability-matrix.md).  
**Owner:** Physical-layer governance — Issues #9 and #174.  
**Schema boundary:** implemented bridge schemas are
[`contracts/v1/schemas/command.schema.json`](../v1/schemas/command.schema.json) and
[`contracts/v1/schemas/telemetry.schema.json`](../v1/schemas/telemetry.schema.json).

---

## 1. Overview

This document traces one canonical material unit through all nine factory modules from
entry (dump-truck delivery) to exit (dump-truck collection of finished goods). The
canonical path is:

```
Dump Truck → Tower Crane → Conveyor → Sorting → Forklift → Conveyor → Packaging → Brackets → Tower Crane → Dump Truck
```

Not all units pass every module. The `Combine` coordinator observes and manages the
running state of all member modules; it does not physically transport material.

The sequence assumes the factory is in `IDLE` / `PRODUCTION_RUNNING` state and all
member modules have passed their pre-production readiness check (no `E_STOP`, `FAULT`,
or stale telemetry on any member).

**Safety authority:** all safety interlock activations described below are enforced by
local controllers under ADR-0006. Network commands cannot override hardwired E-stop
or jam-response circuits.

---

## 2. Canonical Mermaid sequence diagram

```mermaid
sequenceDiagram
    autonumber
    participant OP as Operator
    participant TRUCK as Dump Truck<br/>dump-truck-01
    participant CRANE as Tower Crane<br/>tower-crane-01
    participant CONV as Conveyor<br/>conveyor-01
    participant SORT as Sorting<br/>sorting-01
    participant FORK as Forklift<br/>forklift-01
    participant PACK as Packaging<br/>packaging-01
    participant BRKT as Brackets<br/>brackets-01
    participant COMBINE as Combine<br/>combine-01
    participant GW as IoT Gateway

    Note over OP,TRUCK: PHASE 1 — Material Intake
    OP->>TRUCK: TRUCK_DRIVE(targetX=entry_zone)
    TRUCK-->>GW: telemetry(state=IDLE→DRIVING, progress=x/y)
    TRUCK-->>GW: telemetry(state=IDLE, sensors=frontObstacle/rearObstacle/loadGrams)
    Note over TRUCK: Obstacle check via TRUCK_FRONT_OBSTACLE, TRUCK_REAR_OBSTACLE
    TRUCK->>OP: DRIVE accepted
    TRUCK-->>GW: telemetry(state=IDLE, progress=targetReached)

    OP->>TRUCK: TRUCK_DUMP_START
    TRUCK-->>GW: telemetry(state=DUMPING, sensors=dumpAngleDeg)
    Note over TRUCK: TRUCK_DUMP_ANGLE monitored; TRUCK_LOAD tracked
    TRUCK->>CRANE: (physical signal via CRANE_LOAD when within range)
    TRUCK-->>GW: telemetry(state=DUMP_COMPLETE, sensors=loadGrams=0)

    Note over OP,CRANE: PHASE 2 — Unload to Conveyor Feed
    OP->>CRANE: CRANE_PICKUP(targetX_mm=entry_pile, targetZ_mm=ground_level)
    CRANE-->>GW: telemetry(state=PICKING, sensors=xMin/xMax/loadGrams)
    Note over CRANE: Limit check: CRANE_X_MIN, CRANE_X_MAX, CRANE_Z_LOW, CRANE_Z_HIGH
    CRANE->>CRANE: CRANE_HOIST(raise to feed_height)
    CRANE-->>GW: telemetry(state=HOISTING, progress=zMm)
    CRANE->>CRANE: CRANE_MOVE_X(targetMm=conveyor_entry)
    CRANE-->>GW: telemetry(state=MOVING_X, progress=xMm)
    CRANE->>CRANE: CRANE_HOIST(lower to conveyor_level)
    CRANE-->>GW: telemetry(state=IDLE, sensors=loadGrams=0)

    Note over OP,CONV: PHASE 3 — Conveyor Feed
    OP->>CONV: CONVEYOR_START(speedMmPerSec=50)
    CONV-->>GW: telemetry(state=STARTING)
    CONV-->>GW: telemetry(state=RUNNING, progress=speedMmPerSec=50)
    Note over CONV: CONV_ENTRY triggers on material arrival; CONV_JAM monitored
    CONV-->>GW: telemetry(state=RUNNING, sensors=entry=true)

    Note over OP,SORT: PHASE 4 — Sorting & Classification
    CONV->>SORT: (physical: material on SORT_INLET sensor)
    OP->>SORT: SORT_ITEM(itemId=lot-N, itemClass=raw)
    SORT-->>GW: telemetry(state=CLASSIFYING, sensors=inlet=true)
    SORT-->>SORT: Local metal/vision classification via SORT_METAL, SORT_CLASS
    alt Classified as metal=true
        SORT-->>SORT: ROUTE destination=BIN_METAL
    else Classified as metal=false
        SORT-->>SORT: ROUTE destination=BIN_STANDARD
    end
    SORT-->>GW: telemetry(state=ROUTING, progress=itemId/lot-N, destination=BIN_*)
    SORT->>CONV: (material diverted off main belt)
    SORT-->>GW: telemetry(state=IDLE, sensors=inlet=false)

    Note over OP,FORK: PHASE 5 — Forklift Staging (PALLET workflow)
    OP->>FORK: FORK_DRIVE(xTarget=sorting_outfeed, yTarget=staging_area)
    FORK-->>GW: telemetry(state=DRIVING, progress=x/y)
    Note over FORK: FORK_FRONT_OBSTACLE, FORK_REAR_OBSTACLE checked
    FORK-->>GW: telemetry(state=IDLE, progress=targetReached)
    OP->>FORK: FORK_PICKUP
    FORK-->>GW: telemetry(state=LIFTING, sensors=liftHigh=false)
    FORK->>FORK: FORK_LIFT(heightMm=pallet_pick_height)
    FORK-->>GW: telemetry(state=LIFTING, progress=forkHeightMm)
    FORK->>FORK: FORK_DRIVE(xTarget=packaging_entry, yTarget=load_position)
    FORK-->>GW: telemetry(state=DRIVING)
    FORK->>FORK: FORK_DROPOFF
    FORK-->>GW: telemetry(state=LIFTING, sensors=liftHigh=true)
    FORK-->>GW: telemetry(state=IDLE)

    Note over OP,PACK: PHASE 6 — Packaging
    OP->>PACK: PACK_START(packageType=standard)
    PACK-->>GW: telemetry(state=FEEDING, sensors=inlet=true)
    PACK->>PACK: PACK_FEED(motor enable)
    PACK-->>GW: telemetry(state=SEALING, sensors=temperatureC=170, pressureKpa=500)
    Note over PACK: PACK_TEMP, PACK_PRESSURE monitored; PACK_JAM checked
    PACK-->>GW: telemetry(state=COMPLETE, progress=cycleCount++)
    PACK-->>GW: telemetry(state=IDLE, sensors=outlet=true)

    Note over OP,BRKT: PHASE 7 — Bracket Assembly (optional structural)
    Note over BRKT: Brackets has no independent actuation.<br/>If a structural sensor BRACKET_ALIGNMENT or<br/>BRACKET_LOAD reports a fault, BRKT transitions to<br/>FAULT and signals the hosted module's local interlock.
    BRKT-->>GW: telemetry(state=NOMINAL, sensors=structuralHealth=ok)

    Note over OP,CRANE: PHASE 8 — Load Out via Tower Crane
    OP->>CRANE: CRANE_PICKUP(targetX_mm=packaging_outlet, targetZ_mm=package_level)
    CRANE-->>GW: telemetry(state=PICKING, sensors=loadGrams>0)
    CRANE->>CRANE: CRANE_MOVE_X(targetMm=staging_bay)
    CRANE-->>GW: telemetry(state=MOVING_X)
    CRANE->>CRANE: CRANE_HOIST(targetMm=dump_truck_bed_level)
    CRANE-->>GW: telemetry(state=HOISTING)
    CRANE->>CRANE: CRANE_DROPOFF
    CRANE-->>GW: telemetry(state=IDLE, sensors=loadGrams=0)

    Note over OP,TRUCK: PHASE 9 — Material Exit
    OP->>TRUCK: TRUCK_DUMP_LOWER
    TRUCK-->>GW: telemetry(state=IDLE, sensors=dumpAngleDeg=0)
    OP->>TRUCK: TRUCK_DRIVE(targetX=exit_gate)
    TRUCK-->>GW: telemetry(state=DRIVING)
    TRUCK-->>GW: telemetry(state=IDLE, progress=exited)

    Note over OP,COMBINE: PHASE 10 — Production Completion
    OP->>COMBINE: COMBINE_STOP(recipeId=recipe-a)
    COMBINE-->>GW: telemetry(state=DRAINING, sensors=membersReady=8)
    Note over COMBINE: All modules must reach terminal/idle telemetry<br/>before COMBINE transitions to IDLE.<br/>Observed completion only; not dispatch ACK.
    COMBINE-->>GW: telemetry(state=IDLE, progress=completedUnits=N)
```

---

## 3. Step-by-step annotation

### Phase 1 — Material Intake (Dump Truck)

| Step | Actor | Action | Trigger | Telemetry output | Safety |
|---|---|---|---|---|---|
| 1.1 | Operator | `TRUCK_DRIVE(entry_zone)` | Human dispatch | `state=DRIVING, progress=x/y` | `TRUCK_FRONT_OBSTACLE` / `TRUCK_REAR_OBSTACLE` checked; blocked if obstacle |
| 1.2 | Dump Truck | Drive to unload position | Command accepted | `state=IDLE, targetReached` | E-stop chain active |
| 1.3 | Operator | `TRUCK_DUMP_START` | Entry gate clear, zero traction verified | `state=DUMPING, dumpAngleDeg` | `TRUCK_DUMP` motor disabled if traction > 0 |
| 1.4 | Dump Truck | Monitor bed angle + mass | `TRUCK_DUMP_ANGLE`, `TRUCK_LOAD` | `state=DUMP_COMPLETE, loadGrams=0` | Overload → `E_STOP` |

### Phase 2 — Unload to Conveyor (Tower Crane)

| Step | Actor | Action | Trigger | Telemetry output | Safety |
|---|---|---|---|---|---|
| 2.1 | Operator | `CRANE_PICKUP(entry_pile)` | `TRUCK_DUMP_COMPLETE` | `state=PICKING, loadGrams` | `CRANE_X_MIN/MAX`, `CRANE_Z_LOW/HIGH` limit check |
| 2.2 | Tower Crane | Raise via `CRANE_HOIST` | Pickup confirmed | `state=HOISTING, zMm` | `CRANE_LOAD` overload guard |
| 2.3 | Tower Crane | Traverse via `CRANE_MOVE_X` | Hoist at safe height | `state=MOVING_X, xMm` | Zone lock: crane/forklift concurrency blocked |
| 2.4 | Tower Crane | Lower via `CRANE_HOIST` | At conveyor level | `state=IDLE, loadGrams=0` | `CRANE_Z_LOW` limit |

### Phase 3 — Conveyor Feed

| Step | Actor | Action | Trigger | Telemetry output | Safety |
|---|---|---|---|---|---|
| 3.1 | Operator | `CONVEYOR_START(speedMmPerSec=50)` | Crane at conveyor | `state=STARTING` | `CONV_ESTOP`, `CONV_JAM` must be clear |
| 3.2 | Conveyor | Belt runs, material arrives at exit | Motion feedback | `state=RUNNING, sensors=entry=true` | `CONV_MOTOR_TEMP` monitored; thermal → `FAULT` |
| 3.3 | Conveyor | Material detected at exit sensor | `CONV_EXIT` DI true | `state=RUNNING` | `CONV_JAM` → `E_STOP` removes `CONV_MOTOR` enable |

### Phase 4 — Sorting & Classification

| Step | Actor | Action | Trigger | Telemetry output | Safety |
|---|---|---|---|---|---|
| 4.1 | Sorting | `SORT_ITEM(itemId, itemClass)` | `CONV_EXIT` or direct | `state=CLASSIFYING, sensors=inlet=true` | `SORT_ESTOP`, `SORT_JAM` checked |
| 4.2 | Sorting | Classify: metal vs standard | `SORT_METAL`, `SORT_CLASS` | — | Unknown class → `REJECTING` |
| 4.3 | Sorting | Route via `SORT_DIVERTER` | Valid class | `state=ROUTING, destination` | Diverter disabled under jam/E-stop |
| 4.4 | Sorting | Divert + confirm | Route confirmed | `state=IDLE, sensors=inlet=false` | Sensor heartbeat lost → `FAULT` |

### Phase 5 — Forklift Staging

| Step | Actor | Action | Trigger | Telemetry output | Safety |
|---|---|---|---|---|---|
| 5.1 | Forklift | `FORK_DRIVE(sorting_outfeed)` | Sort routing complete | `state=DRIVING, progress=x/y` | `FORK_FRONT_OBSTACLE` / `FORK_REAR_OBSTACLE` blocked |
| 5.2 | Forklift | `FORK_PICKUP` + `FORK_LIFT` | At pickup position | `state=LIFTING, forkHeightMm` | `FORK_LIFT_LOW/HIGH` limits; zone lock |
| 5.3 | Forklift | `FORK_DRIVE(packaging_entry)` | Pallet lifted | `state=DRIVING` | Zone lock: crane path blocked |
| 5.4 | Forklift | `FORK_DROPOFF` | At packaging entry | `state=IDLE` | `FORK_LIFT_HIGH` confirmed before release |

### Phase 6 — Packaging

| Step | Actor | Action | Trigger | Telemetry output | Safety |
|---|---|---|---|---|---|
| 6.1 | Packaging | `PACK_START(packageType)` | Forklift at entry | `state=FEEDING, sensors=inlet=true` | `PACK_ESTOP`, `PACK_JAM` clear |
| 6.2 | Packaging | Feed motor enable | Inlet sensor | `state=FEEDING` | Jam → `E_STOP` removes `PACK_FEED` |
| 6.3 | Packaging | Seal via `PACK_SEAL` | Inlet confirmed | `state=SEALING, tempC/pressureKpa` | Thermal/pressure fault → `FAULT` |
| 6.4 | Packaging | Complete + outlet | Seal confirmed | `state=COMPLETE, cycleCount++` | `PACK_ESTOP` always allowed |
| 6.5 | Packaging | Return to idle | Outlet cleared | `state=IDLE, sensors=outlet=true` | — |

### Phase 7 — Bracket Assembly

| Step | Actor | Action | Trigger | Telemetry output | Safety |
|---|---|---|---|---|---|
| 7.1 | Brackets | Passive monitoring | Continuous | `state=NOMINAL, structuralHealth` | No actuation; hosted module owns stop |
| 7.2 | Brackets | Structural fault detected | `BRACKET_LOAD` / `BRACKET_ALIGNMENT` anomaly | `state=FAULT` | Signals hosted module's local interlock |

### Phase 8 — Load Out (Tower Crane)

| Step | Actor | Action | Trigger | Telemetry output | Safety |
|---|---|---|---|---|---|
| 8.1 | Tower Crane | `CRANE_PICKUP(packaging_outlet)` | Packaging complete | `state=PICKING, loadGrams>0` | Limits + load guard |
| 8.2 | Tower Crane | Traverse to staging bay | Pickup confirmed | `state=MOVING_X` | Zone lock |
| 8.3 | Tower Crane | Lower to truck bed level | At staging bay | `state=HOISTING` | `CRANE_Z_LOW` |
| 8.4 | Tower Crane | `CRANE_DROPOFF` | At bed level | `state=IDLE, loadGrams=0` | — |

### Phase 9 — Material Exit (Dump Truck)

| Step | Actor | Action | Trigger | Telemetry output | Safety |
|---|---|---|---|---|---|
| 9.1 | Dump Truck | `TRUCK_DUMP_LOWER` | Load placed | `state=IDLE, dumpAngleDeg=0` | Zero traction required |
| 9.2 | Dump Truck | `TRUCK_DRIVE(exit_gate)` | Bed lowered | `state=DRIVING` | Obstacle sensors |
| 9.3 | Dump Truck | Exit factory | Target reached | `state=IDLE, exited` | — |

### Phase 10 — Production Completion (Combine)

| Step | Actor | Action | Trigger | Telemetry output | Safety |
|---|---|---|---|---|---|
| 10.1 | Combine | `COMBINE_STOP(recipeId)` | Human or recipe end | `state=DRAINING, membersReady=8` | Waits for all modules to reach `IDLE` |
| 10.2 | Combine | Observe per-module terminal telemetry | All `state=IDLE` | `state=IDLE, completedUnits=N` | Observed completion only (not dispatch ACK) |

---

## 4. Safety interlock activations and recovery paths

### 4.1 Per-module interlock matrix

| Interlock trigger | Affected module(s) | Effect | Recovery |
|---|---|---|---|
| `CONV_JAM` DI true | Conveyor | `CONV_MOTOR` disabled, `E_STOP` FSM transition | Clear jam, `CONVEYOR_RESET`, observe `IDLE` |
| `CONV_ESTOP` open | Conveyor | All outputs disabled, `E_STOP` FSM transition | Local release, `RESET`, operator clearance |
| `CONV_MOTOR_TEMP` fault | Conveyor | FSM → `FAULT` | Local repair, `RESET`, observe `IDLE` |
| `SORT_JAM` DI true | Sorting | `SORT_DIVERTER` disabled, `E_STOP` | Clear jam, `SORTING_RESET`, observe `IDLE` |
| `SORT_ESTOP` open | Sorting | All outputs disabled, `E_STOP` | Local release, `RESET`, observe `IDLE` |
| Sensor heartbeat lost | Sorting | FSM → `FAULT` | Repair sensor, `RESET` |
| `SORTING_STOP` command | Sorting | FSM → `STOPPED` (reachable from ANY) | New `SORT_ITEM` resumes |
| `CRANE_*_LIMIT` DI true | Tower Crane | Motion halted, `E_STOP` | Clear path, `RESET` |
| `CRANE_LOAD` overload | Tower Crane | Hoist stopped, `E_STOP` | Unload, `RESET` |
| Encoder timeout | Tower Crane | FSM → `FAULT` | Repair encoder, `RESET` |
| `CRANE_ESTOP` open | Tower Crane | All outputs disabled, `E_STOP` | Local release, `RESET` |
| Zone conflict (crane/fork) | Crane + Forklift | Zone lock: one blocked | Clear zone protocol, retry |
| No free `PARK_SLOT` | Parking | FSM → `BLOCKED` | Slot released, auto-retry |
| `PARK_ESTOP` open | Parking | Gate motion disabled, `E_STOP` | Local release, `RESET` |
| `FORK_*_OBSTACLE` DI true | Forklift | Drive halted, `STOPPED` FSM state | Clear path, new command |
| `FORK_*_LIMIT` DI true | Forklift | Lift motion disabled | Retry with valid height |
| `FORK_ESTOP` open | Forklift | All outputs disabled, `E_STOP` | Local release, `RESET` |
| `TRUCK_*_OBSTACLE` DI true | Dump Truck | Drive halted, `E_STOP` | Clear path, `RESET` |
| `TRUCK_LOAD` overload | Dump Truck | Dump disabled, `E_STOP` | Unload, `RESET` |
| Traction during dump | Dump Truck | `TRUCK_DUMP` disabled | Zero traction, retry |
| `TRUCK_ESTOP` open | Dump Truck | All outputs disabled, `E_STOP` | Local release, `RESET` |
| `PACK_JAM` DI true | Packaging | `PACK_FEED` + `PACK_SEAL` disabled, `E_STOP` | Clear jam, `RESET` |
| `PACK_TEMP` / `PACK_PRESSURE` fault | Packaging | FSM → `FAULT` | Repair, `RESET` |
| `PACK_ESTOP` open | Packaging | All outputs disabled, `E_STOP` | Local release, `RESET` |
| Structural fault (AI) | Brackets | FSM → `FAULT`, signals hosted interlock | Physical inspection + hosted `RESET` |
| Any member `E_STOP` observed | Combine | FSM → `SAFETY_HALT` | Per-module local release + `RESET` + observe `IDLE` |
| Member stale telemetry | Combine | Block new `COMBINE_START_PRODUCTION` | Refresh telemetry, retry |

### 4.2 Cross-module interlock sequences

**Forklift ↔ Tower Crane shared zone:**
1. Crane issues `CRANE_MOVE_X` → controller checks zone lock → if Forklift `DRIVING`, command rejected.
2. Forklift issues `FORK_DRIVE` → controller checks zone lock → if Crane `MOVING_X`/`HOISTING`/`PICKING`, command rejected.
3. Zone lock is enforced locally by both controllers; network ACK is insufficient per §11 invariant #3.

**Dump Truck traction guard:**
1. `TRUCK_DUMP_START` issued → local controller verifies `TRUCK_DRIVE` speed = 0 via encoder (or `TRUCK_STEER` at 0).
2. If traction detected, `TRUCK_DUMP` motor enable is withheld; command returns `rejected`.
3. After dump, `TRUCK_DUMP_LOWER` must confirm bed at 0° before `TRUCK_DRIVE` is accepted.

**Sorting `STOPPED` state reachability:**
Per the FSM in `factory-interface.md` §3:
```
ANY --[SORTING_STOP]--> STOPPED --[SORT_ITEM]--> CLASSIFYING
```
`STOPPED` is reachable from any active state via `SORTING_STOP`. Recovery from `STOPPED` requires `SORT_ITEM` which re-enters `CLASSIFYING`. This satisfies the compatibility requirement.

### 4.3 Staleness and recovery

| Condition | Detection | Effect | Recovery |
|---|---|---|---|
| Telemetry freshness unknown | Gateway staleness monitor | Surface as `UNKNOWN` state, do not infer safe/running | Wait for fresh telemetry or query `GET_STATUS` |
| Command expired (`expiresAt` passed) | Controller rejects | Command returns `timed_out` | Re-issue with fresh `issuedAt`/`expiresAt` |
| Duplicate command ID with different payload | Controller rejects | Command returns `rejected` | Use idempotent `commandId` |
| Post-E-stop controller restart | Controller self-reports | All modules require local safe state + operator clearance | `RESET` only accepted after physical inspection |
| Bus/cable loss | Controller watchdog | Watchdog trips → local `E_STOP` per module FSM | Repair bus, local release, `RESET` |

---

## 5. Module participation summary

| Module | Role in canonical path | Commands issued | Telemetry emitted | Standalone-safe |
|---|---|---|---|---|
| Dump Truck | Entry / Exit transport | `TRUCK_DRIVE`, `TRUCK_DUMP_START`, `TRUCK_DUMP_LOWER`, `TRUCK_STOP` | `IDLE`, `DRIVING`, `DUMPING`, `DUMP_COMPLETE`, `E_STOP` | Yes |
| Tower Crane | Lift / place between zones | `CRANE_PICKUP`, `CRANE_DROPOFF`, `CRANE_MOVE_X`, `CRANE_HOIST`, `CRANE_STOP` | `IDLE`, `PICKING`, `MOVING_X`, `HOISTING`, `E_STOP`, `FAULT` | No (requires zone lock) |
| Conveyor | Material transport | `CONVEYOR_START`, `CONVEYOR_STOP`, `RESET` | `IDLE`, `STARTING`, `RUNNING`, `STOPPING`, `E_STOP`, `FAULT` | Partial |
| Sorting | Classification / routing | `SORT_ITEM`, `ROUTE_MANUAL`, `SORTING_STOP`, `RESET` | `IDLE`, `CLASSIFYING`, `ROUTING`, `REJECTING`, `STOPPED`, `E_STOP`, `FAULT` | Partial |
| Forklift | Pallet / load transport | `FORK_DRIVE`, `FORK_PICKUP`, `FORK_DROPOFF`, `FORK_LIFT`, `FORK_STOP` | `IDLE`, `DRIVING`, `LIFTING`, `STOPPED`, `E_STOP` | No (zone lock required) |
| Packaging | Seal / package | `PACK_START`, `PACK_STOP`, `SET_TEMP`, `RESET` | `IDLE`, `FEEDING`, `SEALING`, `COMPLETE`, `E_STOP`, `FAULT` | Yes |
| Brackets | Structural support (passive) | None | `NOMINAL`, `FAULT` | Yes (passive) |
| Combine | Workflow orchestration | `COMBINE_START_PRODUCTION`, `COMBINE_STOP`, `COMBINE_GET_STATUS` | `IDLE`, `PRODUCTION_RUNNING`, `DRAINING`, `SAFETY_HALT` | No (requires all members) |

---

## 6. L0 acceptance checklist

- [ ] All 9 modules appear in the sequence diagram and step annotations
- [ ] Every command cited appears in `factory-interface.md` §2–10
- [ ] Every telemetry state cited appears in `factory-interface.md` §2–10 FSM text
- [ ] `SORTING_STOP` → `STOPPED` transition is documented (sorting reachability)
- [ ] A1 ADC sharing (CONV humidity vs TRUCK dump angle) has explicit resolution or BLOCKED note
- [ ] Safety interlock activations are documented per-module with recovery paths
- [ ] No v1 schema paths cited as non-existent (`contracts/v1/schemas/telemetry.schema.json` — correct)
- [ ] No v1 conformance claimed for planned controller payloads
- [ ] Combine `SAFETY_HALT` triggered by any observed member `E_STOP` is documented
- [ ] Observed completion (not dispatch ACK) is the gate for Combine state transitions
