# Physical Factory Module Capability Matrix

**Status:** Proposed design contract (L0 only). Cross-reference document supplementing
[`factory-interface.md`](./factory-interface.md).  
**Owner:** Physical-layer governance — Issues #9 and #174.  
**Schema boundary:** implemented bridge schemas are
[`contracts/v1/schemas/command.schema.json`](../v1/schemas/command.schema.json) and
[`contracts/v1/schemas/telemetry.schema.json`](../v1/schemas/telemetry.schema.json).

All channel IDs are **logical names**. Pin/ADC assignment and electrical validation are
**BLOCKED-L3** pending hardware evidence. Command payloads are **planned
`physical-controller/v0.1`** (not valid v1 bridge payloads).

---

## Matrix conventions

| Column | Content |
|---|---|
| **I/O Channels** | All logical channels from `factory-interface.md` §2–10, grouped by type |
| **Command Interface** | Commands issued through the planned v0.1 `ModuleCommand` boundary |
| **Telemetry Interface** | Planned `PlannedModuleTelemetry` shape (`deviceId`, `state`, `sensors`, `progress`, `activeFaults`); **not** a v1 bridge envelope |
| **Physical Constraints** | Safety limits, cross-module locks, BLOCKED notes |

A cell entry `—` means the module does not expose that I/O type. A `BLOCKED` note means
hardware validation is required before the capability can be used.

---

## Cross-reference matrix

| Module | DI | AI | ENC | DO | SERVO | MOTOR | STEP | ESTOP | Command Interface | Telemetry Interface | Physical Constraints |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Conveyor** `conveyor-01` | `CONV_ENTRY`, `CONV_EXIT`, `CONV_JAM` | `CONV_MOTOR_TEMP` | — | — | — | `CONV_MOTOR` | — | `CONV_ESTOP` | `CONVEYOR_START`, `CONVEYOR_STOP`, `RESET` | `RUNNING/IDLE/E_STOP/FAULT`; `speedMmPerSec`, motor thermal | Speed bounds local to controller; jam/E-stop removes motor enable; thermal/watchdog trips `FAULT` |
| **Sorting** `sorting-01` | `SORT_INLET`, `SORT_METAL`, `SORT_JAM` | `SORT_CLASS` | — | — | `SORT_DIVERTER` | — | — | `SORT_ESTOP` | `SORT_ITEM`, `ROUTE_MANUAL`, `SORTING_STOP`, `RESET` | `IDLE/CLASSIFYING/ROUTING/REJECTING/STOPPED/E_STOP/FAULT`; `itemId`, `destination` | Jam/E-stop disables diverter; `STOPPED` reachable from ANY via `SORTING_STOP`; sensor heartbeat loss → `FAULT` |
| **Tower Crane** `tower-crane-01` | `CRANE_X_MIN`, `CRANE_X_MAX`, `CRANE_Z_LOW`, `CRANE_Z_HIGH` | `CRANE_LOAD` | `CRANE_X_ENCODER`, `CRANE_Z_ENCODER` | — | — | `CRANE_HOIST` | `CRANE_TROLLEY` | `CRANE_ESTOP` | `CRANE_MOVE_X`, `CRANE_HOIST`, `CRANE_PICKUP`, `CRANE_DROPOFF`, `CRANE_STOP`, `RESET` | `IDLE/MOVING_X/HOISTING/PICKING/E_STOP/FAULT`; `xMm`, `zMm`, `loadGrams` | Hard limits + E-stop remove motor authority; overload stops hoist; encoder timeout → `FAULT`; crane/forklift shared-zone clearance required |
| **Parking** `parking-01` | `PARK_SLOT_1..N`, `PARK_GATE_CLEAR` | — | — | `PARK_GATE` (or `SERVO` TBD L3) | `PARK_GATE` (TBD L3) | — | — | `PARK_ESTOP` | `GATE_OPEN`, `GATE_CLOSE`, `GET_STATUS`, `RESET` | `IDLE/OPENING/CLOSING/BLOCKED/E_STOP`; `availableSlots` | Gate type (SERVO vs DO) TBD L3; admission denied when no verified free slot; gate must reopen on obstruction |
| **Forklift** `forklift-01` | `FORK_FRONT_OBSTACLE`, `FORK_REAR_OBSTACLE`, `FORK_LIFT_LOW`, `FORK_LIFT_HIGH` | — | — | — | `FORK_STEER` | `FORK_DRIVE`, `FORK_LIFT` | — | `FORK_ESTOP` | `FORK_DRIVE`, `FORK_LIFT`, `FORK_PICKUP`, `FORK_DROPOFF`, `FORK_STOP`, `RESET` | `IDLE/DRIVING/LIFTING/STOPPED/E_STOP`; `x`, `y`, `forkHeightMm` | Obstacle removes drive authority immediately; lift limits remove lift; shared-zone lock prevents crane/forklift concurrency; TRUCK/FORK physical channel sharing **BLOCKED-L3** |
| **Dump Truck** `dump-truck-01` | `TRUCK_FRONT_OBSTACLE`, `TRUCK_REAR_OBSTACLE` | `TRUCK_DUMP_ANGLE`, `TRUCK_LOAD` | — | — | `TRUCK_STEER` | `TRUCK_DRIVE`, `TRUCK_DUMP` | — | `TRUCK_ESTOP` | `TRUCK_DRIVE`, `TRUCK_DUMP_START`, `TRUCK_DUMP_LOWER`, `TRUCK_STOP`, `RESET` | `IDLE/DRIVING/DUMPING/DUMP_COMPLETE/E_STOP`; `loadGrams`, `dumpAngleDeg` | Dump enabled only at verified zero traction; overload + E-stop remove actuation; TRUCK/FORK physical channel sharing **BLOCKED-L3**; A1 ADC — logical channels `TRUCK_DUMP_ANGLE` and `CONV_MOTOR_TEMP` are distinct; hardware multiplexing resolution **BLOCKED-L3** |
| **Packaging** `packaging-01` | `PACK_INLET`, `PACK_OUTLET`, `PACK_JAM` | `PACK_TEMP`, `PACK_PRESSURE` | — | `PACK_SEAL` (or `SERVO` TBD L3) | `PACK_SEAL` (TBD L3) | `PACK_FEED` | — | `PACK_ESTOP` | `PACK_START`, `PACK_STOP`, `SET_TEMP`, `RESET` | `IDLE/FEEDING/SEALING/COMPLETE/E_STOP/FAULT`; `cycleCount` | Jam removes feed/seal authority; thermal/pressure fault → `FAULT`; thermal setpoint range is local config only |
| **Brackets** `brackets-01` | — | `BRACKET_ALIGNMENT`, `BRACKET_LOAD` | — | — | — | — | — | `BRACKET_ESTOP` (optional) | **None** (no remote actuation) | `NOMINAL/FAULT`; `structuralHealth` | No independent actuation; structural hazard must signal hosted module's local interlock; cannot be cleared remotely |
| **Combine** `combine-01` | — | — | — | — | — | — | — | — (logical) | `COMBINE_START_PRODUCTION`, `COMBINE_STOP`, `COMBINE_GET_STATUS` | `IDLE/PRODUCTION_RUNNING/DRAINING/SAFETY_HALT`; `membersReady`, `membersFaulted`, `recipeId` | Coordinator only; observed member `E_STOP` → `SAFETY_HALT`; cannot reset member or claim physical stop without member telemetry confirmation |

---

## I/O channel cross-reference

Every channel listed in the matrix above appears verbatim in
[`factory-interface.md`](./factory-interface.md) §2–10. No channel name is
invented in this document.

| Channel | Defined in factory-interface.md |
|---|---|
| `CONV_ENTRY`, `CONV_EXIT`, `CONV_JAM` | §2 Conveyor |
| `CONV_MOTOR_TEMP` | §2 Conveyor |
| `CONV_MOTOR` | §2 Conveyor |
| `CONV_ESTOP` | §2 Conveyor |
| `SORT_INLET`, `SORT_METAL`, `SORT_JAM` | §3 Sorting |
| `SORT_CLASS` | §3 Sorting |
| `SORT_DIVERTER` | §3 Sorting |
| `SORT_ESTOP` | §3 Sorting |
| `CRANE_X_MIN`, `CRANE_X_MAX`, `CRANE_Z_LOW`, `CRANE_Z_HIGH` | §4 Tower Crane |
| `CRANE_X_ENCODER`, `CRANE_Z_ENCODER` | §4 Tower Crane |
| `CRANE_LOAD` | §4 Tower Crane |
| `CRANE_TROLLEY` | §4 Tower Crane |
| `CRANE_HOIST` | §4 Tower Crane |
| `CRANE_ESTOP` | §4 Tower Crane |
| `PARK_SLOT_1..N`, `PARK_GATE_CLEAR` | §5 Parking |
| `PARK_GATE` | §5 Parking |
| `PARK_ESTOP` | §5 Parking |
| `FORK_FRONT_OBSTACLE`, `FORK_REAR_OBSTACLE`, `FORK_LIFT_LOW`, `FORK_LIFT_HIGH` | §6 Forklift |
| `FORK_DRIVE`, `FORK_LIFT` | §6 Forklift |
| `FORK_STEER` | §6 Forklift |
| `FORK_ESTOP` | §6 Forklift |
| `TRUCK_FRONT_OBSTACLE`, `TRUCK_REAR_OBSTACLE` | §7 Dump Truck |
| `TRUCK_DUMP_ANGLE`, `TRUCK_LOAD` | §7 Dump Truck |
| `TRUCK_DRIVE`, `TRUCK_DUMP` | §7 Dump Truck |
| `TRUCK_STEER` | §7 Dump Truck |
| `TRUCK_ESTOP` | §7 Dump Truck |
| `PACK_INLET`, `PACK_OUTLET`, `PACK_JAM` | §8 Packaging |
| `PACK_TEMP`, `PACK_PRESSURE` | §8 Packaging |
| `PACK_FEED` | §8 Packaging |
| `PACK_SEAL` | §8 Packaging |
| `PACK_ESTOP` | §8 Packaging |
| `BRACKET_ALIGNMENT`, `BRACKET_LOAD` | §9 Brackets |
| `BRACKET_ESTOP` | §9 Brackets |
| `COMBINE_MODULE_STATE`, `COMBINE_DISPATCH` | §10 Combine |

---

## A1 ADC sharing resolution

The compatibility requirements from PR #238 review call out A1 ADC channel sharing between
`CONV` humidity and `TRUCK` dump angle. The canonical `factory-interface.md` defines:

- `CONV_MOTOR_TEMP` (AI, Conveyor §2) — motor thermal monitoring
- `TRUCK_DUMP_ANGLE` (AI, Dump Truck §7) — bed position

These are two **distinct logical channels** on two different device IDs (`conveyor-01` vs
`dump-truck-01`). At the L0 design level there is no shared hardware resource. The
resolution is:

> **BLOCKED-L3.** If a future implementation maps both logical channels to the same
> physical ADC pin (e.g. a shared controller board), that multiplexing decision
> requires verified electrical evidence and a formally reviewed controller-selection
> topology before it may appear in any contract. No logical channel name in this
> matrix encodes a physical pin assignment.

---

## Verification status

| Module | Matrix coverage | Channels verified against factory-interface.md |
|---|---|---|
| Conveyor | ✅ | All 4 channels listed in §2 |
| Sorting | ✅ | All 4 channels listed in §3 |
| Tower Crane | ✅ | All 6 channels listed in §4 |
| Parking | ✅ | All 3 channels listed in §5 |
| Forklift | ✅ | All 4 channels listed in §6 |
| Dump Truck | ✅ | All 5 channels listed in §7 |
| Packaging | ✅ | All 5 channels listed in §8 |
| Brackets | ✅ | All 3 channels listed in §9 |
| Combine | ✅ | Logical channels listed in §10 |
