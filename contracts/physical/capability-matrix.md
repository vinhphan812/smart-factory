# Physical Module Capability Matrix

**Status:** L0 design contract — quick-reference typed IO mapping for deterministic controller implementation.  
**Source contract:** [`factory-interface.md`](./factory-interface.md) (§1–12).  
**Owner:** Physical-layer governance — Issues #9 and #174.  
**Safety authority:** local controllers and hardwired E-stop circuits remain authoritative under ADR-0006.  
**Compatibility boundary:** implemented bridge schemas remain `contracts/v1/schemas/command.schema.json` and `contracts/v1/schemas/telemetry.schema.json`. All module-specific commands and telemetry shapes below are **planned controller-contract v0.1**; they require a future controller schema version and compatibility review before publishing through the bridge.

---

## Reading guide

| Column | Content |
|---|---|
| **IO Type** | Logical channel name → I/O type classification (DI / AI / ENC / DO / SERVO / MOTOR / STEP / ESTOP), direction, and value semantics. |
| **Command Interface** | Command token, argument schema, and rejection codes. |
| **Telemetry Interface** | Planned telemetry payload shape and field semantics for the v0.1 controller schema. |
| **Physical Constraints** | Safety interlocks, hard limits, cross-module guards, and recovery requirements from ADR-0006. |

**I/O type key** (from §1.2):

| Type | Direction | Typed value | Meaning |
|---|---|---|---|
| `DI` | input | `boolean` | Binary sensor; polarity declared by implementation. |
| `AI` | input | `integer` ADC count or calibrated `number` | Analog sensor. Unit and calibration are controller-owned. |
| `ENC` | input | `integer` count | Quadrature/position feedback. |
| `DO` | output | `boolean` | Switched actuator-enable signal. |
| `SERVO` | output | `integer` µs or calibrated degrees | Servo command; local controller owns hard bounds. |
| `MOTOR` | output | `{direction, pwm}` | Motor direction and bounded PWM duty. |
| `STEP` | output | `{direction, steps}` | Stepper trajectory request; no raw remote pulse streaming. |
| `ESTOP` | input | `boolean` | Normally closed hardwired chain; open/fault means unsafe. |

All channel IDs are **logical names**. Controller/channel allocation and electrical validation are **BLOCKED-L3** pending hardware evidence.

---

## 1. Conveyor — `conveyor-01`

> **Role:** Material feed.

### IO Type

| Channel | Type | Dir | Value | Purpose |
|---|---|---|---|---|
| `CONV_ENTRY` | `DI` | input | `boolean` | Material arrival detection. |
| `CONV_EXIT` | `DI` | input | `boolean` | Material departure detection. |
| `CONV_JAM` | `DI` | input | `boolean` | Jam/obstruction detection. |
| `CONV_MOTOR_TEMP` | `AI` | input | calibrated `number` (°C) | Motor thermal monitoring. |
| `CONV_MOTOR` | `MOTOR` | output | `{direction: "fwd"\|"rev", pwm: 0–100}` | Belt drive. |
| `CONV_ESTOP` | `ESTOP` | input | `boolean` | Hardwired stop chain (NC). |

### Command Interface

| Command | Args | Reject codes |
|---|---|---|
| `CONVEYOR_START` | `{speedMmPerSec: number}` | `E_STOP_OPEN`, `JAM_ACTIVE`, `INVALID_SPEED`, `WATCHDOG_TRIPPED` |
| `CONVEYOR_STOP` | — | none (always accepted) |
| `RESET` | — | `ESTOP_PERSISTS`, `JAM_PERSISTS`, `FAULT_PERSISTS` |

**Schema** (planned v0.1):

```ts
interface ConveyorCommand {
  commandId: string;   // idempotency key
  deviceId: "conveyor-01";
  name: "CONVEYOR_START" | "CONVEYOR_STOP" | "RESET";
  args: { speedMmPerSec?: number };
  issuedAt: string;    // UTC ISO-8601
  expiresAt: string;
}
```

### Telemetry Interface

```ts
interface ConveyorTelemetry extends PlannedModuleTelemetry {
  deviceId: "conveyor-01";
  state: "IDLE" | "STARTING" | "RUNNING" | "STOPPING" | "E_STOP" | "FAULT";
  sensors: {
    entry: boolean;
    exit: boolean;
    jam: boolean;
    motorTempC: number;
  };
  progress: {
    speedMmPerSec: number;
  };
}
```

**Example payload** (planned v0.1 — not valid as top-level v1 telemetry):

```json
{
  "deviceId": "conveyor-01",
  "state": "RUNNING",
  "sensors": { "entry": false, "exit": false, "jam": false, "motorTempC": 25.0 },
  "progress": { "speedMmPerSec": 50 },
  "activeFaults": []
}
```

### Physical Constraints

| Constraint | Effect |
|---|---|
| Jam active | Removes `CONV_MOTOR` enable locally; command rejected while jam persists. |
| E-stop open | Removes `CONV_MOTOR` enable; transitions to `E_STOP` state. |
| Thermal fault | Transitions to `FAULT`; `RESET` refused until thermal returns to safe range. |
| Watchdog timeout | Transitions to `FAULT`; `CONVEYOR_START` rejected until watchdog is cleared. |
| Loss of motion feedback while running | Fails closed: transitions to `FAULT`. |
| Recovery | Must obtain local safe state and operator clearance before accepting new motion command. |

---

## 2. Sorting — `sorting-01`

> **Role:** Classification/routing of items.

### IO Type

| Channel | Type | Dir | Value | Purpose |
|---|---|---|---|---|
| `SORT_INLET` | `DI` | input | `boolean` | Item presence at inlet. |
| `SORT_METAL` | `DI` | input | `boolean` | Metal classification signal. |
| `SORT_JAM` | `DI` | input | `boolean` | Obstruction detection. |
| `SORT_CLASS` | `AI` | input | calibrated `number` | Optional color/vision classification. |
| `SORT_DIVERTER` | `SERVO` | output | degrees | Route selected item to destination. |
| `SORT_ESTOP` | `ESTOP` | input | `boolean` | Hardwired stop chain (NC). |

### Command Interface

| Command | Args | Reject codes |
|---|---|---|
| `SORT_ITEM` | `{itemId: string, itemClass: string}` | `JAM_ACTIVE`, `E_STOP_OPEN`, `BUSY`, `MISSING_CLASSIFICATION` |
| `ROUTE_MANUAL` | `{destination: string}` | `INVALID_DESTINATION`, `E_STOP_OPEN` |
| `SORTING_STOP` | — | none |
| `RESET` | — | `ESTOP_PERSISTS`, `JAM_PERSISTS`, `FAULT_PERSISTS` |

**Schema** (planned v0.1):

```ts
interface SortingCommand {
  commandId: string;
  deviceId: "sorting-01";
  name: "SORT_ITEM" | "ROUTE_MANUAL" | "SORTING_STOP" | "RESET";
  args: { itemId?: string; itemClass?: string; destination?: string };
  issuedAt: string;
  expiresAt: string;
}
```

### Telemetry Interface

```ts
interface SortingTelemetry extends PlannedModuleTelemetry {
  deviceId: "sorting-01";
  state: "IDLE" | "CLASSIFYING" | "ROUTING" | "REJECTING" | "STOPPED" | "E_STOP" | "FAULT";
  sensors: {
    inlet: boolean;
    metal: boolean;
    jam: boolean;
  };
  progress: {
    itemId?: string;
    destination?: string;
  };
}
```

**Example payload** (planned v0.1):

```json
{
  "deviceId": "sorting-01",
  "state": "ROUTING",
  "sensors": { "inlet": true, "metal": false, "jam": false },
  "progress": { "itemId": "lot-17", "destination": "BIN_2" },
  "activeFaults": []
}
```

### Physical Constraints

| Constraint | Effect |
|---|---|
| Jam / E-stop | Disables `SORT_DIVERTER` motion; transitions to `E_STOP`. |
| Sensor heartbeat loss | Transitions to `FAULT`; latched until repair. |
| Manual route | Cannot bypass the safety reject lane. |
| Recovery | `RESET` refused until physical cause is cleared and sensor heartbeat is restored. |

---

## 3. Tower Crane — `tower-crane-01`

> **Role:** Lift and place operations.

### IO Type

| Channel | Type | Dir | Value | Purpose |
|---|---|---|---|---|
| `CRANE_X_MIN` | `DI` | input | `boolean` | X-axis minimum limit. |
| `CRANE_X_MAX` | `DI` | input | `boolean` | X-axis maximum limit. |
| `CRANE_Z_LOW` | `DI` | input | `boolean` | Hoist lower limit. |
| `CRANE_Z_HIGH` | `DI` | input | `boolean` | Hoist upper limit. |
| `CRANE_X_ENCODER` | `ENC` | input | `integer` count | X-axis position feedback. |
| `CRANE_Z_ENCODER` | `ENC` | input | `integer` count | Hoist position feedback. |
| `CRANE_LOAD` | `AI` | input | calibrated `number` (g) | Overload guard. |
| `CRANE_TROLLEY` | `STEP` | output | `{direction, steps}` | X-axis trolley motion. |
| `CRANE_HOIST` | `MOTOR` | output | `{direction, pwm}` | Raise/lower hoist. |
| `CRANE_ESTOP` | `ESTOP` | input | `boolean` | Hardwired stop chain (NC). |

### Command Interface

| Command | Args | Reject codes |
|---|---|---|
| `CRANE_MOVE_X` | `{targetMm: number}` | `OUT_OF_BOUNDS`, `ZONE_OCCUPIED`, `LIMIT_ACTIVE`, `E_STOP_OPEN` |
| `CRANE_HOIST` | `{targetMm: number}` | `OVERLOAD`, `HOIST_LIMIT_ACTIVE`, `E_STOP_OPEN` |
| `CRANE_PICKUP` | — | `LOAD_NOT_CONFIRMED`, `E_STOP_OPEN` |
| `CRANE_DROPOFF` | — | `LOAD_STATE_CONFLICT`, `E_STOP_OPEN` |
| `CRANE_STOP` | — | none |
| `RESET` | — | `ESTOP_PERSISTS`, `ENCODER_TIMEOUT`, `FAULT_PERSISTS` |

**Schema** (planned v0.1):

```ts
interface CraneCommand {
  commandId: string;
  deviceId: "tower-crane-01";
  name: "CRANE_MOVE_X" | "CRANE_HOIST" | "CRANE_PICKUP" | "CRANE_DROPOFF" | "CRANE_STOP" | "RESET";
  args: { targetMm?: number };
  issuedAt: string;
  expiresAt: string;
}
```

### Telemetry Interface

```ts
interface CraneTelemetry extends PlannedModuleTelemetry {
  deviceId: "tower-crane-01";
  state: "IDLE" | "MOVING_X" | "HOISTING" | "PICKING" | "E_STOP" | "FAULT";
  sensors: {
    xMin: boolean;
    xMax: boolean;
    loadGrams: number;
  };
  progress: {
    xMm: number;
    zMm: number;
  };
}
```

**Example payload** (planned v0.1):

```json
{
  "deviceId": "tower-crane-01",
  "state": "MOVING_X",
  "sensors": { "xMin": false, "xMax": false, "loadGrams": 0 },
  "progress": { "xMm": 150, "zMm": 80 },
  "activeFaults": []
}
```

### Physical Constraints

| Constraint | Effect |
|---|---|
| Hard limit active | Removes `CRANE_TROLLEY` / `CRANE_HOIST` authority; command rejected. |
| E-stop open | Removes all motor authority; transitions to `E_STOP`. |
| Overload (`CRANE_LOAD`) | Stops hoist motion; transitions to `E_STOP`. |
| Encoder timeout | Transitions to `FAULT`. |
| Shared zone (crane + forklift) | Zone-clear protocol required before movement; network ACK alone is insufficient. |
| Recovery | `RESET` requires local clearance + verified encoder position. |

---

## 4. Parking — `parking-01`

> **Role:** Vehicle staging at entry/exit.

### IO Type

| Channel | Type | Dir | Value | Purpose |
|---|---|---|---|---|
| `PARK_SLOT_1..N` | `DI` | input | `boolean` | Per-slot occupancy detection. |
| `PARK_GATE_CLEAR` | `DI` | input | `boolean` | Gate path obstruction check. |
| `PARK_GATE` | `SERVO` or `DO` | output | bounded position or enable | Gate open/close. Actuator type TBD-L3. |
| `PARK_ESTOP` | `ESTOP` | input | `boolean` | Hardwired stop chain (NC). |

### Command Interface

| Command | Args | Reject codes |
|---|---|---|
| `GATE_OPEN` | — | `NO_SLOT_AVAILABLE`, `E_STOP_OPEN`, `GATE_FAULT` |
| `GATE_CLOSE` | — | `OBSTRUCTION_PRESENT`, `E_STOP_OPEN` |
| `GET_STATUS` | — | none |
| `RESET` | — | `ESTOP_PERSISTS` |

**Schema** (planned v0.1):

```ts
interface ParkingCommand {
  commandId: string;
  deviceId: "parking-01";
  name: "GATE_OPEN" | "GATE_CLOSE" | "GET_STATUS" | "RESET";
  args: Record<string, never>;
  issuedAt: string;
  expiresAt: string;
}
```

### Telemetry Interface

```ts
interface ParkingTelemetry extends PlannedModuleTelemetry {
  deviceId: "parking-01";
  state: "IDLE" | "OPENING" | "CLOSING" | "BLOCKED" | "E_STOP";
  sensors: {
    slot1: boolean;
    slot2: boolean;
    gateClear: boolean;
  };
  progress: {
    availableSlots: number;
  };
}
```

**Example payload** (planned v0.1):

```json
{
  "deviceId": "parking-01",
  "state": "IDLE",
  "sensors": { "slot1": false, "slot2": true, "gateClear": true },
  "progress": { "availableSlots": 1 },
  "activeFaults": []
}
```

### Physical Constraints

| Constraint | Effect |
|---|---|
| Obstruction detected on close | Gate must reopen automatically. |
| No verified free slot | Admission denied. |
| E-stop open | Transitions to `E_STOP`; `RESET` refused until estop cleared. |
| Actuator type TBD | `PARK_GATE` is `SERVO` or `DO` — BLOCKED-L3 pending hardware validation. |

---

## 5. Forklift — `forklift-01`

> **Role:** Pallet transport within the factory floor.

### IO Type

| Channel | Type | Dir | Value | Purpose |
|---|---|---|---|---|
| `FORK_FRONT_OBSTACLE` | `DI` | input | `boolean` | Forward collision guard. |
| `FORK_REAR_OBSTACLE` | `DI` | input | `boolean` | Rear collision guard. |
| `FORK_LIFT_LOW` | `DI` | input | `boolean` | Lower fork lift limit. |
| `FORK_LIFT_HIGH` | `DI` | input | `boolean` | Upper fork lift limit. |
| `FORK_DRIVE` | `MOTOR` | output | `{direction, pwm}` | Traction drive. |
| `FORK_LIFT` | `MOTOR` | output | `{direction, pwm}` | Fork raise/lower. |
| `FORK_STEER` | `SERVO` | output | degrees | Steering angle. |
| `FORK_ESTOP` | `ESTOP` | input | `boolean` | Hardwired stop chain (NC). |

### Command Interface

| Command | Args | Reject codes |
|---|---|---|
| `FORK_DRIVE` | `{xTarget: number, yTarget: number}` | `OBSTACLE_PRESENT`, `CRANE_ZONE_OCCUPIED`, `OUT_OF_BOUNDS`, `E_STOP_OPEN` |
| `FORK_LIFT` | `{heightMm: number}` | `LIFT_LIMIT_ACTIVE`, `OVERLOAD`, `E_STOP_OPEN` |
| `FORK_PICKUP` | — | `INVALID_LOAD_STATE`, `E_STOP_OPEN` |
| `FORK_DROPOFF` | — | `INVALID_LOAD_STATE`, `E_STOP_OPEN` |
| `FORK_STOP` | — | none |
| `RESET` | — | `ESTOP_PERSISTS`, `FAULT_PERSISTS` |

**Schema** (planned v0.1):

```ts
interface ForkliftCommand {
  commandId: string;
  deviceId: "forklift-01";
  name: "FORK_DRIVE" | "FORK_LIFT" | "FORK_PICKUP" | "FORK_DROPOFF" | "FORK_STOP" | "RESET";
  args: { xTarget?: number; yTarget?: number; heightMm?: number };
  issuedAt: string;
  expiresAt: string;
}
```

### Telemetry Interface

```ts
interface ForkliftTelemetry extends PlannedModuleTelemetry {
  deviceId: "forklift-01";
  state: "IDLE" | "DRIVING" | "LIFTING" | "STOPPED" | "E_STOP" | "FAULT";
  sensors: {
    frontObstacle: boolean;
    rearObstacle: boolean;
    liftHigh: boolean;
  };
  progress: {
    x: number;
    y: number;
    forkHeightMm: number;
  };
}
```

**Example payload** (planned v0.1):

```json
{
  "deviceId": "forklift-01",
  "state": "DRIVING",
  "sensors": { "frontObstacle": false, "rearObstacle": false, "liftHigh": false },
  "progress": { "x": 2, "y": 4, "forkHeightMm": 80 },
  "activeFaults": []
}
```

### Physical Constraints

| Constraint | Effect |
|---|---|
| Obstacle detected | Immediately requests local drive stop; transitions to `STOPPED`. |
| Lift limit active | Removes lift motion authority; `FORK_LIFT` rejected. |
| Shared zone (crane + forklift) | Zone-lock protocol required; crane and forklift cannot move simultaneously in shared zone. |
| E-stop / overload | Transitions to `E_STOP`; removes all actuator authority. |
| Recovery | `RESET` refused until obstacle cleared, estop released, and safe load state confirmed. |

---

## 6. Dump Truck — `dump-truck-01`

> **Role:** Bulk material delivery.

### IO Type

| Channel | Type | Dir | Value | Purpose |
|---|---|---|---|---|
| `TRUCK_FRONT_OBSTACLE` | `DI` | input | `boolean` | Forward collision guard. |
| `TRUCK_REAR_OBSTACLE` | `DI` | input | `boolean` | Rear collision guard. |
| `TRUCK_DUMP_ANGLE` | `AI` | input | calibrated `number` (°) | Bed position angle. |
| `TRUCK_LOAD` | `AI` | input | calibrated `number` (g) | Bed mass. |
| `TRUCK_DRIVE` | `MOTOR` | output | `{direction, pwm}` | Traction. |
| `TRUCK_DUMP` | `MOTOR` | output | `{direction, pwm}` | Tipper actuator. |
| `TRUCK_STEER` | `SERVO` | output | degrees | Steering. |
| `TRUCK_ESTOP` | `ESTOP` | input | `boolean` | Hardwired stop chain (NC). |

### Command Interface

| Command | Args | Reject codes |
|---|---|---|
| `TRUCK_DRIVE` | `{xTarget: number, yTarget: number}` | `OBSTACLE_PRESENT`, `OUT_OF_BOUNDS`, `E_STOP_OPEN` |
| `TRUCK_DUMP_START` | — | `VEHICLE_MOVING`, `OVERLOAD`, `E_STOP_OPEN` |
| `TRUCK_DUMP_LOWER` | — | `VEHICLE_MOVING`, `E_STOP_OPEN` |
| `TRUCK_STOP` | — | none |
| `RESET` | — | `ESTOP_PERSISTS`, `FAULT_PERSISTS` |

**Schema** (planned v0.1):

```ts
interface DumpTruckCommand {
  commandId: string;
  deviceId: "dump-truck-01";
  name: "TRUCK_DRIVE" | "TRUCK_DUMP_START" | "TRUCK_DUMP_LOWER" | "TRUCK_STOP" | "RESET";
  args: { xTarget?: number; yTarget?: number };
  issuedAt: string;
  expiresAt: string;
}
```

### Telemetry Interface

```ts
interface DumpTruckTelemetry extends PlannedModuleTelemetry {
  deviceId: "dump-truck-01";
  state: "IDLE" | "DRIVING" | "DUMPING" | "DUMP_COMPLETE" | "E_STOP" | "FAULT";
  sensors: {
    frontObstacle: boolean;
    rearObstacle: boolean;
    loadGrams: number;
    dumpAngleDeg: number;
  };
  progress: {
    targetAngleDeg: number;
  };
}
```

**Example payload** (planned v0.1):

```json
{
  "deviceId": "dump-truck-01",
  "state": "DUMPING",
  "sensors": { "frontObstacle": false, "loadGrams": 500, "dumpAngleDeg": 32 },
  "progress": { "targetAngleDeg": 35 },
  "activeFaults": []
}
```

### Physical Constraints

| Constraint | Effect |
|---|---|
| Dump enabled | Only when `TRUCK_DRIVE` is at zero speed; verified via telemetry. |
| Overload / E-stop | Removes all actuator authority; transitions to `E_STOP`. |
| Channel sharing | No physical channel sharing with `forklift-01` until controller-selection topology is L3-verified. |
| Recovery | `RESET` refused until fault is cleared and vehicle is in safe stationary state. |

---

## 7. Packaging — `packaging-01`

> **Role:** Package and seal products.

### IO Type

| Channel | Type | Dir | Value | Purpose |
|---|---|---|---|---|
| `PACK_INLET` | `DI` | input | `boolean` | Product entry detection. |
| `PACK_OUTLET` | `DI` | input | `boolean` | Product exit detection. |
| `PACK_JAM` | `DI` | input | `boolean` | Obstruction/jam detection. |
| `PACK_TEMP` | `AI` | input | calibrated `number` (°C) | Heater temperature. |
| `PACK_PRESSURE` | `AI` | input | calibrated `number` (kPa) | Pneumatic pressure. |
| `PACK_FEED` | `MOTOR` | output | `{direction, pwm}` | Product feed. |
| `PACK_SEAL` | `SERVO` or `DO` | output | bounded position or enable | Seal actuator. Final type TBD. |
| `PACK_ESTOP` | `ESTOP` | input | `boolean` | Hardwired stop chain (NC). |

### Command Interface

| Command | Args | Reject codes |
|---|---|---|
| `PACK_START` | `{packageType: string}` | `E_STOP_OPEN`, `JAM_ACTIVE`, `PRESSURE_UNSAFE`, `TEMP_OUT_OF_RANGE` |
| `PACK_STOP` | — | none (local safety stop always allowed) |
| `SET_TEMP` | `{targetC: number}` | `TARGET_OUT_OF_BOUNDS` (controller-owned range) |
| `RESET` | — | `ESTOP_PERSISTS`, `JAM_PERSISTS`, `FAULT_PERSISTS` |

**Schema** (planned v0.1):

```ts
interface PackagingCommand {
  commandId: string;
  deviceId: "packaging-01";
  name: "PACK_START" | "PACK_STOP" | "SET_TEMP" | "RESET";
  args: { packageType?: string; targetC?: number };
  issuedAt: string;
  expiresAt: string;
}
```

### Telemetry Interface

```ts
interface PackagingTelemetry extends PlannedModuleTelemetry {
  deviceId: "packaging-01";
  state: "IDLE" | "FEEDING" | "SEALING" | "COMPLETE" | "E_STOP" | "FAULT";
  sensors: {
    inlet: boolean;
    outlet: boolean;
    jam: boolean;
    temperatureC: number;
    pressureKpa: number;
  };
  progress: {
    cycleCount: number;
  };
}
```

**Example payload** (planned v0.1):

```json
{
  "deviceId": "packaging-01",
  "state": "SEALING",
  "sensors": { "inlet": true, "outlet": false, "jam": false, "temperatureC": 170, "pressureKpa": 500 },
  "progress": { "cycleCount": 7 },
  "activeFaults": []
}
```

### Physical Constraints

| Constraint | Effect |
|---|---|
| Jam active | Removes `PACK_FEED` and `PACK_SEAL` authority; transitions to `E_STOP`. |
| Temperature fault | Transitions to `FAULT`; latched until temperature returns to safe range. |
| Pressure fault | Transitions to `FAULT`; latched until pressure is restored. |
| Thermal setpoint | `SET_TEMP` range is local controller configuration — not a remote override. |
| Recovery | `RESET` refused until jam cleared, temperature and pressure are in safe range. |

---

## 8. Brackets — `brackets-01`

> **Role:** Structural support module. No independent actuator or state machine.

### IO Type

| Channel | Type | Dir | Value | Purpose |
|---|---|---|---|---|
| `BRACKET_ALIGNMENT` | `AI` | input | calibrated `number` | Optional structural alignment measurement. |
| `BRACKET_LOAD` | `AI` | input | calibrated `number` | Optional load measurement. |
| `BRACKET_ESTOP` | `ESTOP` | input | `boolean` | Optional mechanical safety chain (if designed). |

> **Note:** `BRACKET_ALIGNMENT` and `BRACKET_LOAD` are future optional monitoring inputs; no remote actuation is permitted on this module.

### Command Interface

| Command | Args | Reject codes |
|---|---|---|
| *(none)* | — | No remote actuation permitted. |
| `GET_STATUS` (future monitor) | — | Not a v1 bridge command; planned v0.1 only. |

**Schema** (planned v0.1):

```ts
interface BracketsCommand {
  commandId: string;
  deviceId: "brackets-01";
  name: "GET_STATUS";
  args: Record<string, never>;
  issuedAt: string;
  expiresAt: string;
}
```

### Telemetry Interface

```ts
interface BracketsTelemetry extends PlannedModuleTelemetry {
  deviceId: "brackets-01";
  state: "NOMINAL" | "FAULT";
  sensors: {
    structuralHealth: string;  // "nominal" | "monitoring" | "fault" — TBD
  };
}
```

**Example payload** (planned v0.1):

```json
{
  "deviceId": "brackets-01",
  "state": "NOMINAL",
  "sensors": { "structuralHealth": "unknown" },
  "activeFaults": []
}
```

### Physical Constraints

| Constraint | Effect |
|---|---|
| No actuation | No remote commands can energize any actuator. |
| Structural fault detected | Hosted module's local interlock is signaled by the structural monitor; cannot be cleared remotely without physical inspection. |
| Recovery | `FAULT` requires physical inspection + hosted controller `RESET`. |

---

## 9. Combine — `combine-01`

> **Role:** Workflow coordinator across all physical modules. No independent motor, servo, or E-stop circuit.

### IO Type

| Channel | Type | Dir | Value | Purpose |
|---|---|---|---|---|
| `COMBINE_MODULE_STATE` | logical input | input | module state aggregate | Consumes observed member module states. Not raw GPIO. |
| `COMBINE_DISPATCH` | logical output | output | command reference | Delegates commands to member modules; not direct actuation. |

### Command Interface

| Command | Args | Reject codes |
|---|---|---|
| `COMBINE_START_PRODUCTION` | `{recipeId: string}` | `MEMBER_STALE`, `MEMBER_FAULTED`, `MEMBER_ESTOPPED`, `MEMBER_UNAVAILABLE` |
| `COMBINE_STOP` | — | none (requests per-module drain) |
| `COMBINE_GET_STATUS` | — | none |

**Schema** (planned v0.1):

```ts
interface CombineCommand {
  commandId: string;
  deviceId: "combine-01";
  name: "COMBINE_START_PRODUCTION" | "COMBINE_STOP" | "COMBINE_GET_STATUS";
  args: { recipeId?: string };
  issuedAt: string;
  expiresAt: string;
}
```

### Telemetry Interface

```ts
interface CombineTelemetry extends PlannedModuleTelemetry {
  deviceId: "combine-01";
  state: "IDLE" | "PRODUCTION_RUNNING" | "DRAINING" | "SAFETY_HALT";
  sensors: {
    membersReady: number;
    membersFaulted: number;
  };
  progress: {
    recipeId?: string;
    completedUnits: number;
  };
}
```

**Example payload** (planned v0.1):

```json
{
  "deviceId": "combine-01",
  "state": "PRODUCTION_RUNNING",
  "sensors": { "membersReady": 8, "membersFaulted": 0 },
  "progress": { "recipeId": "recipe-a", "completedUnits": 12 },
  "activeFaults": []
}
```

### Physical Constraints

| Constraint | Effect |
|---|---|
| Any member `E_STOP` observed | Transitions to `SAFETY_HALT`; Combine cannot reset member estop. |
| Member stale telemetry | `COMBINE_START_PRODUCTION` rejected; staleness surfaced as `UNKNOWN` state. |
| Orchestration completion | Moves forward only on fresh observed terminal telemetry — not command dispatch or protocol ACK. |
| Recovery | `SAFETY_HALT` clears only after each local controller is safely reset and observed at `IDLE`. |

---

## Cross-module Quick Reference

### IO Type Distribution Summary

| Module | DI | AI | ENC | DO | SERVO | MOTOR | STEP | ESTOP |
|---|---|---|---|---|---|---|---|---|
| Conveyor | 3 | 1 | — | — | — | 1 | — | 1 |
| Sorting | 3 | 1 | — | — | 1 | — | — | 1 |
| Tower Crane | 4 | 1 | 2 | — | — | 1 | 1 | 1 |
| Parking | N+1 | — | — | TBD | TBD | — | — | 1 |
| Forklift | 4 | — | — | — | 1 | 2 | — | 1 |
| Dump Truck | 2 | 2 | — | — | 1 | 2 | — | 1 |
| Packaging | 3 | 2 | — | TBD | TBD | 1 | — | 1 |
| Brackets | — | 2 | — | — | — | — | — | opt. |
| Combine | — | — | — | — | — | — | — | — |

### Shared-zone Cross-module Invariants

| Guard | Modules | Rule |
|---|---|---|
| Zone lock | Crane + Forklift | Movement in shared zone requires verified zone-clear protocol; network ACK insufficient. |
| Channel uniqueness | Forklift + Dump Truck | Distinct verified controller channels required; no placeholder pin maps. |
| Observed completion | All | Orchestration advances only on fresh terminal telemetry. |
| Staleness | All | Unknown freshness → `UNKNOWN` state; never infer safe/running. |

---

## Planned Module Telemetry Base Type

All module telemetry payloads extend this common interface (planned v0.1):

```ts
interface PlannedModuleTelemetry {
  deviceId: string;
  observedAt: string;                                // UTC ISO-8601
  state: string;
  sequence: number;                                  // monotonic per-module
  sensors: Record<string, boolean | number | string>;
  progress?: Record<string, boolean | number | string>;
  activeFaults: string[];
}
```

---

## ADR-0006 Safety Interlock Summary

| Interlock rule | Applies to |
|---|---|
| Local safety wins over network | All modules. |
| No unverified channel reuse | Forklift, Dump Truck. |
| Zone lock protocol | Crane, Forklift. |
| Observed completion required | All modules. |
| Staleness surfaced as `UNKNOWN` | All modules. |
| Recovery requires local safe state + operator clearance | All modules. |

See [`factory-interface.md`](./factory-interface.md) §11 for full invariant text.
