# Physical Factory Module Interface Contract

**Status:** Proposed design contract (L0 only). It is not a wiring diagram, hardware-validation record, or implementation claim.  
**Owner:** Physical-layer governance — Issues #9 and #174.  
**Compatibility boundary:** the implemented bridge schemas remain [`contracts/v1/schemas/command.schema.json`](../v1/schemas/command.schema.json) and [`contracts/v1/schemas/telemetry.schema.json`](../v1/schemas/telemetry.schema.json).  
**Safety authority:** local controllers and hardwired E-stop circuits remain authoritative under ADR-0006. A command acknowledgement is not proof of physical completion.

All module-specific commands and telemetry projections in this document are **planned controller-contract v0.1**. They are deliberately not described as v1 bridge commands: the present v1 command-name enum supports only `CONVEYOR_START`, `CONVEYOR_STOP`, `RESET`, `PING`, and `SET_OUTPUT`. Similarly, the v1 telemetry schema rejects undeclared top-level fields. A future controller schema/version and compatibility review are required before these planned interfaces are published through the bridge.

## 1. Shared typed vocabulary

### 1.1 Canonical identities

| Module | `device_id` | Role |
|---|---|---|
| Conveyor | `conveyor-01` | Material feed |
| Sorting | `sorting-01` | Classification/routing |
| Tower Crane | `tower-crane-01` | Lift/place |
| Parking | `parking-01` | Vehicle staging |
| Forklift | `forklift-01` | Pallet transport |
| Dump Truck | `dump-truck-01` | Bulk-material delivery |
| Packaging | `packaging-01` | Package/seal |
| Brackets | `brackets-01` | Structural support |
| Combine | `combine-01` | Workflow coordinator |

### 1.2 I/O types and safety semantics

| Type | Direction | Typed value | Meaning |
|---|---|---|---|
| `DI` | input | `boolean` | Binary sensor; polarity must be declared by implementation. |
| `AI` | input | `integer` ADC count or calibrated `number` | Analog sensor. Unit and calibration are controller-owned. |
| `ENC` | input | `integer` count | Quadrature/position feedback. |
| `DO` | output | `boolean` | Switched actuator-enable signal. |
| `SERVO` | output | `integer` microseconds or calibrated degrees | Servo command; local controller owns hard bounds. |
| `MOTOR` | output | `{direction, pwm}` | Motor direction and bounded PWM duty. |
| `STEP` | output | `{direction, steps}` | Stepper trajectory request, never raw remote pulse streaming. |
| `ESTOP` | input | `boolean` | Normally closed hardwired chain; open/fault means unsafe. Not a normal DI. |

All channel IDs below are **logical names**, not pin assignments. Controller/channel allocation and electrical validation are **BLOCKED-L3** pending hardware evidence. A module must not be considered independently operable until its channels, polarity, calibration, and E-stop chain are verified.

### 1.3 Shared command contract (planned `physical-controller/v0.1`)

```ts
interface ModuleCommand {
  commandId: string;                 // idempotency key; payload binding required
  deviceId: string;                  // one canonical ID from §1.1
  name: string;                      // module-specific command token
  args: Record<string, string | number | boolean>;
  issuedAt: string;                  // UTC ISO-8601
  expiresAt: string;                 // controller rejects stale commands
}
```

A controller returns `accepted`, `rejected`, `started`, `completed`, `failed`, or `timed_out`. `accepted`/`started` never mean physical completion. Every controller MUST reject unknown commands, duplicate IDs with a different payload, expired commands, and commands disallowed by its local interlocks.

### 1.4 Telemetry contract boundary

The examples below are **planned module payloads** for a future versioned controller telemetry schema; they are **not valid as top-level v1 telemetry**. Until such a schema exists, an adapter can only emit the strict v1 envelope and encode supported raw readings inside `sensors`:

```json
{
  "device_id": "conveyor-01",
  "timestamp": "2026-10-20T12:00:00.000Z",
  "state": "RUNNING",
  "speed": 50,
  "sensors": {"digital_inputs": 5, "temperature_centi_c": 2500},
  "uptime": 3600000
}
```

Planned telemetry fields use the following common shape:

```ts
interface PlannedModuleTelemetry {
  deviceId: string;
  observedAt: string;
  state: string;
  sequence: number;
  sensors: Record<string, boolean | number | string>;
  progress?: Record<string, boolean | number | string>;
  activeFaults: string[];
}
```

## 2. Conveyor — `conveyor-01`

| Logical I/O | Type | Direction | Value | Purpose |
|---|---|---|---|---|
| `CONV_ENTRY`, `CONV_EXIT`, `CONV_JAM` | `DI` | input | `boolean` | Material arrival, departure, jam detection. |
| `CONV_MOTOR_TEMP` | `AI` | input | calibrated temperature | Motor thermal monitoring. |
| `CONV_MOTOR` | `MOTOR` | output | `{direction,pwm}` | Belt motion. |
| `CONV_ESTOP` | `ESTOP` | input | `boolean` | Local hardwired stop chain. |

```text
IDLE --[CONVEYOR_START]--> STARTING --[motion feedback]--> RUNNING
RUNNING --[CONVEYOR_STOP or exit complete]--> STOPPING --[zero speed]--> IDLE
ANY --[jam / ESTOP open / watchdog]--> E_STOP
E_STOP --[local release + RESET + clear sensors]--> IDLE
ANY --[sensor/controller fault]--> FAULT --[local repair + RESET]--> IDLE
```

| Commands | Arguments | Local rejection / failure mode |
|---|---|---|
| `CONVEYOR_START` | `speedMmPerSec` | E-stop open, jam active, invalid speed, watchdog already tripped. |
| `CONVEYOR_STOP` | — | Always requests controlled stop. |
| `RESET` | — | Refused while E-stop/jam/fault persists. |

**Interlocks:** jam or E-stop removes motor enable locally; thermal/watchdog fault transitions to `FAULT`; loss of feedback while moving fails closed.

```json
{"deviceId":"conveyor-01","state":"RUNNING","sensors":{"entry":false,"exit":false,"jam":false,"motorTempC":25.0},"progress":{"speedMmPerSec":50},"activeFaults":[]}
```

## 3. Sorting — `sorting-01`

| Logical I/O | Type | Direction | Value | Purpose |
|---|---|---|---|---|
| `SORT_INLET`, `SORT_METAL`, `SORT_JAM` | `DI` | input | `boolean` | Presence, classification, obstruction. |
| `SORT_CLASS` | `AI` | input | calibrated number | Optional color/vision classification signal. |
| `SORT_DIVERTER` | `SERVO` | output | degrees | Route selected item. |
| `SORT_ESTOP` | `ESTOP` | input | `boolean` | Local stop chain. |

```text
IDLE --[SORT_ITEM]--> CLASSIFYING --[valid class]--> ROUTING --[route confirmed]--> IDLE
CLASSIFYING --[unknown item]--> REJECTING --[reject confirmed]--> IDLE
ANY --[SORTING_STOP]--> STOPPED --[SORT_ITEM]--> CLASSIFYING
ANY --[jam / ESTOP open]--> E_STOP --[local release + RESET]--> IDLE
ANY --[sensor heartbeat lost]--> FAULT --[repair + RESET]--> IDLE
```

| Commands | Arguments | Local rejection / failure mode |
|---|---|---|
| `SORT_ITEM` | `itemId`, `itemClass` | Jam, E-stop, busy, missing classification. |
| `ROUTE_MANUAL` | `destination` | Destination outside configured route set. |
| `SORTING_STOP`, `RESET` | — | Reset refused until physical cause is cleared. |

**Interlocks:** jam/E-stop disables diverter motion; sensor heartbeat loss is a latched fault; manual route cannot bypass a safety reject lane.

```json
{"deviceId":"sorting-01","state":"ROUTING","sensors":{"inlet":true,"metal":false,"jam":false},"progress":{"itemId":"lot-17","destination":"BIN_2"},"activeFaults":[]}
```

## 4. Tower Crane — `tower-crane-01`

| Logical I/O | Type | Direction | Value | Purpose |
|---|---|---|---|---|
| `CRANE_X_MIN`, `CRANE_X_MAX`, `CRANE_Z_LOW`, `CRANE_Z_HIGH` | `DI` | input | `boolean` | Travel/hoist limits. |
| `CRANE_X_ENCODER`, `CRANE_Z_ENCODER` | `ENC` | input | count | Position feedback. |
| `CRANE_LOAD` | `AI` | input | calibrated mass | Overload guard. |
| `CRANE_TROLLEY` | `STEP` | output | trajectory | X-axis motion. |
| `CRANE_HOIST` | `MOTOR` | output | `{direction,pwm}` | Raise/lower. |
| `CRANE_ESTOP` | `ESTOP` | input | `boolean` | Local stop chain. |

```text
IDLE --[CRANE_MOVE_X]--> MOVING_X --[target/limit]--> IDLE
IDLE --[CRANE_HOIST]--> HOISTING --[target/limit]--> IDLE
IDLE --[CRANE_PICKUP]--> PICKING --[load confirmed]--> IDLE
ANY --[limit / overload / zone occupied / ESTOP open]--> E_STOP
ANY --[encoder timeout]--> FAULT
E_STOP or FAULT --[local clearance + RESET]--> IDLE
```

| Commands | Arguments | Local rejection / failure mode |
|---|---|---|
| `CRANE_MOVE_X` | `targetMm` | Target outside bounds, occupied zone, active limit/E-stop. |
| `CRANE_HOIST` | `targetMm` | Overload or hoist limit active. |
| `CRANE_PICKUP`, `CRANE_DROPOFF`, `CRANE_STOP`, `RESET` | — | Load-state or safety-state conflict. |

**Interlocks:** hard limits and E-stop remove motor authority; overload stops hoist; crane/forklift shared-zone clearance is required before movement.

```json
{"deviceId":"tower-crane-01","state":"MOVING_X","sensors":{"xMin":false,"xMax":false,"loadGrams":0},"progress":{"xMm":150,"zMm":80},"activeFaults":[]}
```

## 5. Parking — `parking-01`

| Logical I/O | Type | Direction | Value | Purpose |
|---|---|---|---|---|
| `PARK_SLOT_1..N`, `PARK_GATE_CLEAR` | `DI` | input | `boolean` | Occupancy and barrier-clear feedback. |
| `PARK_GATE` | `SERVO` or `DO` | output | bounded position/enable | Gate type is TBD at L3. |
| `PARK_ESTOP` | `ESTOP` | input | `boolean` | Local stop chain. |

```text
IDLE --[GATE_OPEN and slot available]--> OPENING --[open feedback]--> IDLE
IDLE --[GATE_CLOSE and gate clear]--> CLOSING --[closed feedback]--> IDLE
ANY --[slot full while admit requested]--> BLOCKED --[slot available]--> IDLE
ANY --[ESTOP open]--> E_STOP --[local release + RESET]--> IDLE
```

| Commands | Arguments | Local rejection / failure mode |
|---|---|---|
| `GATE_OPEN` | — | No slot, E-stop, gate fault. |
| `GATE_CLOSE` | — | Vehicle/gate obstruction present. |
| `GET_STATUS`, `RESET` | — | Reset refused while E-stop remains open. |

**Interlocks:** gate must reopen if obstruction is detected; admission is denied when no verified free slot exists.

```json
{"deviceId":"parking-01","state":"IDLE","sensors":{"slot1":false,"slot2":true,"gateClear":true},"progress":{"availableSlots":1},"activeFaults":[]}
```

## 6. Forklift — `forklift-01`

| Logical I/O | Type | Direction | Value | Purpose |
|---|---|---|---|---|
| `FORK_FRONT_OBSTACLE`, `FORK_REAR_OBSTACLE`, `FORK_LIFT_LOW`, `FORK_LIFT_HIGH` | `DI` | input | `boolean` | Collision and lift limits. |
| `FORK_DRIVE`, `FORK_LIFT` | `MOTOR` | output | `{direction,pwm}` | Traction and lift. |
| `FORK_STEER` | `SERVO` | output | degrees | Steering. |
| `FORK_ESTOP` | `ESTOP` | input | `boolean` | Local stop chain. |

```text
IDLE --[FORK_DRIVE]--> DRIVING --[target reached]--> IDLE
IDLE --[FORK_LIFT]--> LIFTING --[limit/target]--> IDLE
DRIVING --[obstacle]--> STOPPED --[path clearance + new command]--> IDLE
ANY --[ESTOP open / overload]--> E_STOP --[local release + RESET]--> IDLE
```

| Commands | Arguments | Local rejection / failure mode |
|---|---|---|
| `FORK_DRIVE` | `xTarget`, `yTarget` | Obstacle, occupied crane zone, out-of-bounds target. |
| `FORK_LIFT` | `heightMm` | Lift limit or overload. |
| `FORK_PICKUP`, `FORK_DROPOFF`, `FORK_STOP`, `RESET` | — | Invalid load/safety state. |

**Interlocks:** obstacle input immediately requests local drive stop; lift limits remove lift motion; shared-zone lock prevents crane/forklift concurrency.

```json
{"deviceId":"forklift-01","state":"DRIVING","sensors":{"frontObstacle":false,"rearObstacle":false,"liftHigh":false},"progress":{"x":2,"y":4,"forkHeightMm":80},"activeFaults":[]}
```

## 7. Dump Truck — `dump-truck-01`

| Logical I/O | Type | Direction | Value | Purpose |
|---|---|---|---|---|
| `TRUCK_FRONT_OBSTACLE`, `TRUCK_REAR_OBSTACLE` | `DI` | input | `boolean` | Collision guard. |
| `TRUCK_DUMP_ANGLE`, `TRUCK_LOAD` | `AI` | input | calibrated number | Bed position and mass. |
| `TRUCK_DRIVE`, `TRUCK_DUMP` | `MOTOR` | output | `{direction,pwm}` | Traction and tipper. |
| `TRUCK_STEER` | `SERVO` | output | degrees | Steering. |
| `TRUCK_ESTOP` | `ESTOP` | input | `boolean` | Local stop chain. |

```text
IDLE --[TRUCK_DRIVE]--> DRIVING --[target reached]--> IDLE
IDLE --[TRUCK_DUMP_START]--> DUMPING --[target angle]--> DUMP_COMPLETE
DUMP_COMPLETE --[TRUCK_DUMP_LOWER]--> IDLE
ANY --[obstacle / overload / ESTOP open]--> E_STOP --[local release + RESET]--> IDLE
```

| Commands | Arguments | Local rejection / failure mode |
|---|---|---|
| `TRUCK_DRIVE` | `xTarget`, `yTarget` | Obstacle, out-of-bounds target, E-stop. |
| `TRUCK_DUMP_START`, `TRUCK_DUMP_LOWER` | — | Vehicle moving, overload, E-stop. |
| `TRUCK_STOP`, `RESET` | — | Reset refused while fault persists. |

**Interlocks:** dump is enabled only at verified zero traction; overload and E-stop remove actuation; no physical channel sharing with Forklift is permitted until a controller-selection topology is L3-verified.

```json
{"deviceId":"dump-truck-01","state":"DUMPING","sensors":{"frontObstacle":false,"loadGrams":500,"dumpAngleDeg":32},"progress":{"targetAngleDeg":35},"activeFaults":[]}
```

## 8. Packaging — `packaging-01`

| Logical I/O | Type | Direction | Value | Purpose |
|---|---|---|---|---|
| `PACK_INLET`, `PACK_OUTLET`, `PACK_JAM` | `DI` | input | `boolean` | Material tracking and jam sensing. |
| `PACK_TEMP`, `PACK_PRESSURE` | `AI` | input | calibrated number | Thermal/pneumatic health. |
| `PACK_FEED` | `MOTOR` | output | `{direction,pwm}` | Product feed. |
| `PACK_SEAL` | `SERVO` or `DO` | output | bounded position/enable | Seal operation; final actuator TBD. |
| `PACK_ESTOP` | `ESTOP` | input | `boolean` | Local stop chain. |

```text
IDLE --[PACK_START]--> FEEDING --[inlet]--> SEALING --[seal complete]--> COMPLETE
COMPLETE --[outlet]--> IDLE
ANY --[jam / ESTOP open]--> E_STOP
SEALING --[temperature or pressure fault]--> FAULT
E_STOP or FAULT --[local clearance + RESET]--> IDLE
```

| Commands | Arguments | Local rejection / failure mode |
|---|---|---|
| `PACK_START` | `packageType` | E-stop, jam, unavailable pressure/temperature. |
| `PACK_STOP` | — | Controlled abort; local safety stop always allowed. |
| `SET_TEMP` | `targetC` | Setpoint outside locally configured bounds. |
| `RESET` | — | Fault/E-stop remains active. |

**Interlocks:** jam removes feed/seal authority; unsafe temperature or low pressure latches `FAULT`; thermal setpoint range is a local configuration, not a remote override.

```json
{"deviceId":"packaging-01","state":"SEALING","sensors":{"inlet":true,"outlet":false,"jam":false,"temperatureC":170,"pressureKpa":500},"progress":{"cycleCount":7},"activeFaults":[]}
```

## 9. Brackets — `brackets-01`

Brackets are a structural module, not an independent actuator/controller. They have **no independent physical command, telemetry producer, or state machine**. A future structural-monitoring add-on may use these planned inputs:

| Logical I/O | Type | Direction | Value | Purpose |
|---|---|---|---|---|
| `BRACKET_ALIGNMENT`, `BRACKET_LOAD` | `AI` | input | calibrated number | Optional structural condition measurement. |
| `BRACKET_ESTOP` | `ESTOP` | input | `boolean` | Optional mechanical safety chain, if designed. |

```text
NOMINAL --[hosted-module structural fault]--> FAULT
FAULT --[physical inspection + hosted controller RESET]--> NOMINAL
```

| Commands | Arguments | Local rejection / failure mode |
|---|---|---|
| None | — | No remote actuation is permitted. |
| `GET_STATUS` (future monitor only) | — | Not a v1 bridge command. |

**Interlocks:** hosted equipment owns the stop action. If a verified structural monitor detects a hazard, it must signal the hosted module's local interlock; it cannot be cleared remotely without inspection.

```json
{"deviceId":"brackets-01","state":"NOMINAL","sensors":{"structuralHealth":"unknown"},"activeFaults":[]}
```

## 10. Combine — `combine-01`

Combine is a workflow coordinator across the eight physical/structural modules; it has no independent motor, servo, or physical E-stop circuit. It consumes observed module states and issues only authorized, per-module commands through the controller boundary.

| Logical I/O | Type | Direction | Value | Purpose |
|---|---|---|---|---|
| `COMBINE_MODULE_STATE` | logical input | input | module state | Aggregate observed states; not raw GPIO. |
| `COMBINE_DISPATCH` | logical output | output | command reference | Delegated command request; not direct actuation. |

```text
IDLE --[COMBINE_START_PRODUCTION + all modules ready]--> PRODUCTION_RUNNING
PRODUCTION_RUNNING --[COMBINE_STOP]--> DRAINING --[all modules terminal/idle]--> IDLE
ANY --[any observed E_STOP]--> SAFETY_HALT
SAFETY_HALT --[each local controller safely reset + observed IDLE]--> IDLE
```

| Commands | Arguments | Local rejection / failure mode |
|---|---|---|
| `COMBINE_START_PRODUCTION` | `recipeId` | A member module is stale, faulted, E-stopped, or unavailable. |
| `COMBINE_STOP` | — | Requests per-module drain; completion requires observations. |
| `COMBINE_GET_STATUS` | — | Returns aggregate observations/staleness. |

**Interlocks:** an observed member `E_STOP` produces `SAFETY_HALT`; Combine cannot reset a member E-stop or claim physical stop before member telemetry verifies it.

```json
{"deviceId":"combine-01","state":"PRODUCTION_RUNNING","sensors":{"membersReady":8,"membersFaulted":0},"progress":{"recipeId":"recipe-a","completedUnits":12},"activeFaults":[]}
```

## 11. Cross-module invariants and failure behavior

1. **Local safety wins:** network loss, stale commands, digital-twin state, dashboard actions, and AI recommendations cannot energize an actuator or release an E-stop.
2. **No unverified channel reuse:** different mobile modules require distinct verified controller channels or a formally verified controller-selection interlock. Placeholder pin maps are prohibited from this contract.
3. **Zone lock:** Crane and Forklift movement require a local/verified zone-clear protocol. Network acknowledgement alone is insufficient.
4. **Observed completion:** orchestration moves forward only on fresh observed terminal telemetry, not command dispatch or protocol ACK.
5. **Staleness:** consumers must surface telemetry whose freshness is unknown as `UNKNOWN` rather than infer a running or safe state.
6. **Recovery:** after E-stop, power/bus loss, or controller restart, each module must obtain local safe state and operator clearance before accepting a new motion command.

## 12. Verification status

| Module | L0 contract | L1/L2 software evidence | L3 electrical/bench | L4 physical motion |
|---|---|---|---|---|
| Conveyor | Defined | Existing adapter evidence must be checked separately | BLOCKED | BLOCKED |
| Sorting | Defined | Existing adapter evidence must be checked separately | BLOCKED | BLOCKED |
| Tower Crane, Parking, Forklift, Dump Truck, Packaging | Defined | Planned | BLOCKED | BLOCKED |
| Brackets, Combine | Defined | Planned coordination/monitoring tests | BLOCKED where physical sensing applies | Not applicable as independent actuator |

This file itself establishes **L0 static design evidence only**. Any implementation must add versioned schemas, producer/consumer examples, malformed/duplicate/stale/offline safety tests, and applicable L1–L4 evidence.

## References

- **PR #238** (this document) — Physical Factory Module Interface Contract
- **PR #239** — [`capability-matrix.md`](capability-matrix.md) — Typed I/O capability per module
- **PR #240** — [`end-to-end-sequence.md`](end-to-end-sequence.md) — Canonical material flow through all 9 modules
