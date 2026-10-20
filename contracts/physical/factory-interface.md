# Smart Factory — Physical Module Interface Contract

**Owner:** physical layer governance (Issues #9, #174)  
**Status:** Design-only — no hardware required. Hardware status is **BLOCKED-L3** pending Issue #98 (uKit Mega board and licensing clearance) and Issue #160 (Yanshee replacement).  
**Standard:** AMLP v1, `contracts/v1/`, ADR-0006 (fail-closed local safety)  
**Related:** `factory-control/src/adapters/conveyor.py`, `factory-control/src/adapters/sorting.py` (implemented L2)  

---

## 1. Conventions

### 1.1 Device ID Schema

Every module carries a canonical `device_id` of the form `<module-slug>-<instance>` (e.g. `conveyor-01`). The slug is lowercase hyphenated; the instance is a zero-padded two-digit integer.

| Module | Canonical device_id |
|--------|---------------------|
| Conveyor Belt | `conveyor-01` |
| Sorting Machine | `sorting-01` |
| Tower Crane | `tower-crane-01` |
| Parking Lot | `parking-01` |
| Forklift | `forklift-01` |
| Dump Truck | `dump-truck-01` |
| Packaging Machine | `packaging-01` |
| Brackets | `brackets-01` |
| Combine Modules | `combine-01` |

### 1.2 IO Type Taxonomy

| IO Type | Code | Description | Example |
|---------|------|-------------|---------|
| Digital Input | `DI` | Binary sensor, active-HIGH or active-LOW | Photoelectric beam |
| Digital Output | `DO` | Binary actuator signal | Solenoid valve |
| Analog Input | `AI` | Continuous value, 0–4095 ADC counts (12-bit) | Temperature, load cell |
| Servo PWM Output | `SERVO` | 50 Hz PWM, 1 ms–2 ms pulse (≈ −90° to +90°) | Diverter gate |
| DC Motor PWM Output | `MOTOR_PWM` | 0–255 (8-bit) or 0–1023 (10-bit) PWM speed control | Belt drive, wheel drive |
| Stepper Pulse Output | `STEP` | Step + direction pulse train | Crane trolley |
| Encoder Input | `ENC` | Quadrature A/B pulse counter | Position feedback |
| E-Stop Loop | `ESTOP` | Normally-closed relay; OPEN = fault | Hardware safety loop |

### 1.3 Telemetry Envelope

All modules emit telemetry strictly conforming to `contracts/v1/telemetry.schema.json`:

```json
{
  "device_id": "conveyor-01",
  "timestamp": "2026-10-20T12:00:00.000Z",
  "state": "RUNNING",
  "sensors": {},
  "uptime": 3600000
}
```

Module-specific fields (e.g. `speed`, `counts`) are appended as top-level fields. All timestamps are ISO 8601 UTC.

### 1.4 Command Envelope

Inbound commands follow `contracts/v1/command.schema.json`. Every command MUST contain `command_id` (or `request_id`) and `command_name`. Missing correlation ID → `rejected`.

---

## 2. Module 1 — Conveyor Belt

**Specification:** `factory-control/docs/conveyor-adapter.md`  
**Implementation:** `factory-control/src/adapters/conveyor.py` (L2 verified)

### 2.1 IO Mapping

| IO Label | Pin | Type | Direction | Description |
|----------|-----|------|-----------|-------------|
| `CONV_MOTOR_PWM` | D9 | `MOTOR_PWM` | Output | Belt DC motor speed (0–255) |
| `CONV_OPT_ENTRY` | D22 | `DI` | Input | Entry photoelectric sensor |
| `CONV_OPT_EXIT` | D23 | `DI` | Input | Exit photoelectric sensor |
| `CONV_JAM_SENSE` | D24 | `DI` | Input | Mechanical jam / obstruction |
| `CONV_TEMP_AI` | A0 | `AI` | Input | Motor temperature (ADC 0–4095) |
| `CONV_ESTOP_LOOP` | D28 | `ESTOP` | Input | Hardware E-stop normally-closed relay |

### 2.2 State Machine

```
IDLE ──[CONVEYOR_START]──▶ STARTING ──[speed reached]──▶ RUNNING
RUNNING ──[CONVEYOR_STOP / speed=0]──▶ STOPPING ──[done]──▶ STOPPED
STOPPED ──[CONVEYOR_START]──▶ STARTING
ANY ──[jam sensor / E-stop button]──▶ E_STOP
E_STOP ──[RESET & jam cleared & button released]──▶ IDLE
ANY ──[sensor bus loss]──▶ FAULT
FAULT ──[RESET & bus restored]──▶ IDLE
```

**States:** `IDLE`, `STARTING`, `RUNNING`, `STOPPING`, `STOPPED`, `FAULT`, `E_STOP`

### 2.3 Command Interface

| Command | Args | Description | Reject Codes |
|---------|------|-------------|-------------|
| `CONVEYOR_START` | `[speed:int]` | Start belt (10–100 mm/s) | `CANNOT_START_IN_ESTOP`, `CANNOT_START_IN_FAULT`, `JAM_SENSOR_ACTIVE`, `PHYSICAL_ESTOP_ACTIVE`, `SPEED_BELOW_MIN`, `SPEED_EXCEEDS_MAX` |
| `CONVEYOR_STOP` | `[]` | Decelerate and stop | — (always safe) |
| `RESET` | `[]` | Clear E_STOP or FAULT | `PHYSICAL_ESTOP_ACTIVE`, `JAM_OBSTRUCTION_PRESENT` |
| `PING` | `[]` | Health check | — |

### 2.4 Safety Interlocks (ADR-0006)

- **Fail-closed jam interlock:** If `CONV_JAM_SENSE` activates during `RUNNING`/`STARTING`, immediately transition to `E_STOP`, speed → 0.
- **Fail-closed E-stop interlock:** If `CONV_ESTOP_LOOP` opens, transition to `E_STOP` with source `PHYSICAL_HARDWARE`. Cannot be reset via network command.
- **Speed bounds:** `min_speed=10`, `max_speed=100` (mm/s or %). Out-of-range → `rejected`.
- **Watchdog:** 300 s maximum continuous run duration.

### 2.5 Telemetry Fields

```json
{
  "device_id": "conveyor-01",
  "timestamp": "...",
  "state": "RUNNING",
  "speed": 50,
  "sensors": {
    "digital_inputs": 5,
    "temperature_centi_c": 2500
  },
  "uptime": 3600000
}
```

---

## 3. Module 2 — Sorting Machine

**Specification:** `factory-control/docs/sorting-adapter.md`  
**Implementation:** `factory-control/src/adapters/sorting.py` (L2 verified)

### 3.1 IO Mapping

| IO Label | Pin | Type | Direction | Description |
|----------|-----|------|-----------|-------------|
| `SORT_SERVO_PWM` | D10 | `SERVO` | Output | Diverter gate angle (−45° to +90°) |
| `SORT_OPT_INLET` | D25 | `DI` | Input | Item entering sorting station |
| `SORT_IND_METAL` | D26 | `DI` | Input | Inductive metal detection |
| `SORT_JAM_SENSE` | D27 | `DI` | Input | Diverter channel jam |
| `SORT_ESTOP_LOOP` | D28 | `ESTOP` | Input | Hardware E-stop normally-closed relay |

### 3.2 State Machine

```
IDLE ──[SORT_ITEM]──▶ CLASSIFYING ──[valid class]──▶ ROUTING ──[diverter cycle done]──▶ IDLE
CLASSIFYING ──[unknown/defective]──▶ REJECTING ──[reject confirmed]──▶ IDLE
ANY ──[jam / E-stop]──▶ E_STOP
ANY ──[sensor bus heartbeat loss]──▶ FAULT
E_STOP ──[RESET & jam cleared & button released]──▶ IDLE
FAULT ──[RESET & bus restored]──▶ IDLE
```

**States:** `IDLE`, `CLASSIFYING`, `ROUTING`, `REJECTING`, `STOPPED`, `FAULT`, `E_STOP`

### 3.3 Command Interface

| Command | Args | Description | Reject Codes |
|---------|------|-------------|-------------|
| `SORT_ITEM` | `[item_id, item_class]` | Classify and route | `CANNOT_SORT_IN_ESTOP`, `CANNOT_SORT_IN_FAULT`, `JAM_SENSOR_ACTIVE`, `SENSOR_LOSS_FAULT` |
| `ROUTE_MANUAL` | `[destination]` | Set diverter position | `MISSING_DESTINATION`, `INVALID_DESTINATION` |
| `SORTING_STOP` | `[]` | Stop operations | — |
| `RESET` | `[]` | Clear E_STOP/FAULT | `PHYSICAL_ESTOP_ACTIVE`, `JAM_OBSTRUCTION_PRESENT`, `SENSOR_LOSS_ACTIVE` |
| `PING` | `[]` | Health check | — |

### 3.4 Decision Matrix

| Classification | Sensor Trigger | Diverter Angle | Target Bin |
|--------------|----------------|----------------|------------|
| `METAL` | `SORT_IND_METAL` HIGH | −45° | `BIN_1` |
| `PLASTIC` | color code = 1 | 0° (straight) | `BIN_2` |
| `WOOD` | color code = 2 | +45° | `BIN_3` |
| `DEFECTIVE` / `UNKNOWN` | any mismatch | +90° | `REJECT_LANE` |

### 3.5 Safety Interlocks (ADR-0006)

- **Fail-closed jam interlock:** `SORT_JAM_SENSE` → `E_STOP`.
- **Fail-closed E-stop interlock:** `SORT_ESTOP_LOOP` open → `E_STOP` with source `PHYSICAL_HARDWARE`.
- **Sensor bus heartbeat:** Loss of heartbeat → `FAULT`. Not automatically recoverable.

---

## 4. Module 3 — Tower Crane

**Canonical device_id:** `tower-crane-01`

### 4.1 IO Mapping

| IO Label | Pin | Type | Direction | Description |
|----------|-----|------|-----------|-------------|
| `CRANE_STEP_PULSE` | D3 | `STEP` | Output | Trolley step pulse (X axis) |
| `CRANE_STEP_DIR` | D4 | `DI`/`DO` | Output | Trolley direction (HIGH=FWD) |
| `CRANE_HOIST_PWM` | D5 | `MOTOR_PWM` | Output | Hoist motor up/down (0–255) |
| `CRANE_LIMIT_X_MIN` | D30 | `DI` | Input | X-axis minimum limit switch |
| `CRANE_LIMIT_X_MAX` | D31 | `DI` | Input | X-axis maximum limit switch |
| `CRANE_LIMIT_Z_LOW` | D32 | `DI` | Input | Z-axis (height) lower limit |
| `CRANE_LIMIT_Z_HIGH` | D33 | `DI` | Input | Z-axis upper limit (overload) |
| `CRANE_ENC_X` | D40/D41 | `ENC` | Input | Quadrature X position encoder |
| `CRANE_ENC_Z` | D42/D43 | `ENC` | Input | Quadrature Z position encoder |
| `CRANE_ESTOP_LOOP` | D29 | `ESTOP` | Input | Hardware E-stop NC relay |

> ⚠️ **Hardware:** Pin assignments are derived from `esp32-ukit-bridge/` wiring reference. Physical pinout validation is **BLOCKED-L3** (Issue #98). All pin values are **UNVERIFIED** pending HIL.

### 4.2 State Machine

```
IDLE ──[CRANE_MOVE_X]──▶ MOVING_X ──[X target reached / limit]──▶ IDLE
IDLE ──[CRANE_HOIST]──▶ HOISTING ──[Z target reached / limit]──▶ IDLE
IDLE ──[CRANE_PICKUP]──▶ AT_LOAD ──[load confirmed sensor]──▶ IDLE
IDLE ──[CRANE_DROPOFF]──▶ AT_DROP ──[drop confirmed]──▶ IDLE
ANY ──[limit switch OR E-stop OR overload]──▶ E_STOP
E_STOP ──[RESET & limits cleared & button released]──▶ IDLE
IDLE ──[encoder fault timeout]──▶ FAULT
FAULT ──[RESET & encoder restored]──▶ IDLE
```

**States:** `IDLE`, `MOVING_X`, `HOISTING`, `AT_LOAD`, `AT_DROP`, `FAULT`, `E_STOP`

### 4.3 Command Interface

| Command | Args | Description | Reject Codes |
|---------|------|-------------|-------------|
| `CRANE_MOVE_X` | `[target_x:int]` | Move trolley to X position (mm) | `LIMIT_SWITCH_ACTIVE`, `E_STOP_ACTIVE`, `POSITION_OUT_OF_RANGE` |
| `CRANE_HOIST` | `[target_z:int]` | Raise/lower hook to Z position | `LIMIT_SWITCH_ACTIVE`, `E_STOP_ACTIVE`, `OVERLOAD_DETECTED` |
| `CRANE_PICKUP` | `[]` | Engage gripper / magnet | `LOAD_ALREADY_PRESENT`, `E_STOP_ACTIVE` |
| `CRANE_DROPOFF` | `[]` | Release load | `NO_LOAD_PRESENT`, `E_STOP_ACTIVE` |
| `CRANE_STOP` | `[]` | Immediate deceleration | — |
| `RESET` | `[]` | Clear E_STOP/FAULT | `PHYSICAL_ESTOP_ACTIVE`, `LIMIT_SWITCH_STILL_ACTIVE` |
| `PING` | `[]` | Health check + position | — |

### 4.4 Safety Interlocks (ADR-0006)

- **Limit switches:** `CRANE_LIMIT_X_MIN`, `CRANE_LIMIT_X_MAX`, `CRANE_LIMIT_Z_LOW`, `CRANE_LIMIT_Z_HIGH` → `E_STOP` if triggered.
- **Fail-closed E-stop:** `CRANE_ESTOP_LOOP` open → `E_STOP` with source `PHYSICAL_HARDWARE`.
- **Overload detection:** Analog load cell on hoist motor; if current exceeds threshold → `E_STOP` (anti-overload).
- **Zone occupancy:** Crane shall not move into a zone occupied by Parking Lot or Forklift without explicit zone-clear confirmation.

### 4.5 Telemetry Fields

```json
{
  "device_id": "tower-crane-01",
  "timestamp": "...",
  "state": "IDLE",
  "position": { "x": 150, "z": 80 },
  "load_grams": 0,
  "sensors": {
    "limit_x_min": false,
    "limit_x_max": false,
    "limit_z_low": false,
    "limit_z_high": false
  },
  "uptime": 0
}
```

---

## 5. Module 4 — Parking Lot

**Canonical device_id:** `parking-01`

### 5.1 IO Mapping

| IO Label | Pin | Type | Direction | Description |
|----------|-----|------|-----------|-------------|
| `PARK_IR_SLOT_1` | D50 | `DI` | Input | Slot 1 IR occupancy sensor |
| `PARK_IR_SLOT_2` | D51 | `DI` | Input | Slot 2 IR occupancy sensor |
| `PARK_IR_SLOT_3` | D52 | `DI` | Input | Slot 3 IR occupancy sensor |
| `PARK_IR_SLOT_4` | D53 | `DI` | Input | Slot 4 IR occupancy sensor |
| `PARK_GATE_OPEN` | D11 | `DO` | Output | Gate barrier open command |
| `PARK_GATE_CLOSE` | D12 | `DO` | Output | Gate barrier close command |
| `PARK_ESTOP_LOOP` | D34 | `ESTOP` | Input | Hardware E-stop NC relay |

> ⚠️ **Hardware:** 4 parking slots defined. Actual slot count is **UNVERIFIED** pending Issue #98. Gate actuator type (servo vs solenoid) is **UNKNOWN**.

### 5.2 State Machine

```
IDLE ──[GATE_OPEN & slot available]──▶ GATE_OPENING ──[gate open sensor]──▶ IDLE
IDLE ──[GATE_CLOSE & vehicle departed]──▶ GATE_CLOSING ──[gate closed sensor]──▶ IDLE
IDLE ──[slot full & GATE_OPEN]──▶ GATE_BLOCKED ──[slot freed]──▶ IDLE
ANY ──[E-stop]──▶ E_STOP
E_STOP ──[RESET & button released]──▶ IDLE
```

**States:** `IDLE`, `GATE_OPENING`, `GATE_CLOSING`, `GATE_BLOCKED`, `E_STOP`

### 5.3 Command Interface

| Command | Args | Description | Reject Codes |
|---------|------|-------------|-------------|
| `GATE_OPEN` | `[]` | Open entry gate | `GATE_ALREADY_OPEN`, `NO_SLOT_AVAILABLE`, `E_STOP_ACTIVE` |
| `GATE_CLOSE` | `[]` | Close entry gate | `VEHICLE_IN_GATE`, `E_STOP_ACTIVE` |
| `GET_STATUS` | `[]` | Return slot occupancy vector | — |
| `RESET` | `[]` | Clear E_STOP | `PHYSICAL_ESTOP_ACTIVE` |
| `PING` | `[]` | Health check | — |

### 5.4 Safety Interlocks (ADR-0006)

- **Fail-closed E-stop:** `PARK_ESTOP_LOOP` open → `E_STOP`.
- **Vehicle-in-gate interlock:** If IR sensor detects vehicle mid-gate during close → reopen gate.
- **Slot count limit:** Commands to `GATE_OPEN` when all slots occupied → `rejected` with `NO_SLOT_AVAILABLE`.

### 5.5 Telemetry Fields

```json
{
  "device_id": "parking-01",
  "timestamp": "...",
  "state": "IDLE",
  "slots": {
    "slot_1": false,
    "slot_2": true,
    "slot_3": false,
    "slot_4": false
  },
  "available_count": 3,
  "uptime": 0
}
```

---

## 6. Module 5 — Forklift

**Canonical device_id:** `forklift-01`

### 6.1 IO Mapping

| IO Label | Pin | Type | Direction | Description |
|----------|-----|------|-----------|-------------|
| `FORK_DRIVE_PWM` | D6 | `MOTOR_PWM` | Output | Wheel drive motor (0–255) |
| `FORK_STEER_SRV` | D7 | `SERVO` | Output | Steering servo PWM |
| `FORK_LIFT_PWM` | D8 | `MOTOR_PWM` | Output | Fork lift motor up/down |
| `FORK_IR_FRONT` | D45 | `DI` | Input | Front obstacle IR |
| `FORK_IR_REAR` | D46 | `DI` | Input | Rear obstacle IR |
| `FORK_LIMIT_LIFT_LOW` | D35 | `DI` | Input | Fork lowered limit |
| `FORK_LIMIT_LIFT_HIGH` | D36 | `DI` | Input | Fork raised limit |
| `FORK_ESTOP_LOOP` | D37 | `ESTOP` | Input | Hardware E-stop NC relay |

> ⚠️ **Hardware:** Forklift drive, steering, and lift actuators are **UNVERIFIED** pending Issue #98 and dedicated adapter implementation. Steering servo range is **UNKNOWN**.

### 6.2 State Machine

```
IDLE ──[FORK_DRIVE]──▶ DRIVING ──[target reached / obstacle]──▶ IDLE
IDLE ──[FORK_LIFT]──▶ LIFTING ──[lift limit reached]──▶ IDLE
IDLE ──[FORK_PICKUP]──▶ LOADED ──[load confirmed]──▶ IDLE
IDLE ──[FORK_DROPOFF]──▶ UNLOADED ──[drop confirmed]──▶ IDLE
DRIVING ──[obstacle detected]──▶ STOPPED ──[path clear]──▶ IDLE
ANY ──[E-stop / overload]──▶ E_STOP
E_STOP ──[RESET & button released]──▶ IDLE
```

**States:** `IDLE`, `DRIVING`, `STOPPED`, `LIFTING`, `LOADED`, `UNLOADED`, `E_STOP`

### 6.3 Command Interface

| Command | Args | Description | Reject Codes |
|---------|------|-------------|-------------|
| `FORK_DRIVE` | `[x_target, y_target]` | Drive to grid position | `OBSTACLE_DETECTED`, `E_STOP_ACTIVE`, `POSITION_OUT_OF_RANGE` |
| `FORK_LIFT` | `[height_mm:int]` | Raise/lower forks | `LIMIT_SWITCH_ACTIVE`, `E_STOP_ACTIVE` |
| `FORK_PICKUP` | `[]` | Attempt pallet pickup | `LOAD_ALREADY_PRESENT`, `E_STOP_ACTIVE` |
| `FORK_DROPOFF` | `[]` | Release load | `NO_LOAD_PRESENT`, `E_STOP_ACTIVE` |
| `FORK_STOP` | `[]` | Immediate stop | — |
| `RESET` | `[]` | Clear E_STOP | `PHYSICAL_ESTOP_ACTIVE` |
| `PING` | `[]` | Health check + position | — |

### 6.4 Safety Interlocks (ADR-0006)

- **Obstacle detection:** Front/rear IR → immediate deceleration; cannot drive into obstacle.
- **Fail-closed E-stop:** `FORK_ESTOP_LOOP` open → `E_STOP`.
- **Lift limits:** `FORK_LIMIT_LIFT_LOW`, `FORK_LIMIT_LIFT_HIGH` → stop lift motor.

### 6.5 Telemetry Fields

```json
{
  "device_id": "forklift-01",
  "timestamp": "...",
  "state": "IDLE",
  "position": { "x": 0, "y": 0 },
  "fork_height_mm": 0,
  "load_grams": 0,
  "sensors": {
    "obstacle_front": false,
    "obstacle_rear": false
  },
  "uptime": 0
}
```

---

## 7. Module 6 — Dump Truck

**Canonical device_id:** `dump-truck-01`

### 7.1 IO Mapping

| IO Label | Pin | Type | Direction | Description |
|----------|-----|------|-----------|-------------|
| `TRUCK_DRIVE_PWM` | D6 | `MOTOR_PWM` | Output | Wheel drive motor (shared with Forklift TBD) |
| `TRUCK_STEER_SRV` | D7 | `SERVO` | Output | Steering servo PWM |
| `TRUCK_DUMP_PWM` | D8 | `MOTOR_PWM` | Output | Dump bed tilt motor |
| `TRUCK_IR_FRONT` | D47 | `DI` | Input | Front obstacle IR |
| `TRUCK_IR_REAR` | D48 | `DI` | Input | Rear obstacle IR (backup) |
| `TRUCK_DUMP_ANGLE_AI` | A1 | `AI` | Input | Dump bed angle sensor (0–4095 ADC) |
| `TRUCK_LOAD_CELL_AI` | A2 | `AI` | Input | Load cell: bed weight (0–4095 ADC) |
| `TRUCK_ESTOP_LOOP` | D38 | `ESTOP` | Input | Hardware E-stop NC relay |

> ⚠️ **Hardware:** Dump Truck actuator and pin assignments are **UNVERIFIED** pending Issue #98 and dedicated adapter implementation (Issue #70).

### 7.2 State Machine

```
IDLE ──[TRUCK_DRIVE]──▶ DRIVING ──[target reached]──▶ IDLE
IDLE ──[TRUCK_DUMP_START]──▶ DUMPING ──[max angle reached]──▶ DUMPING_COMPLETE
DUMPING_COMPLETE ──[TRUCK_DUMP_STOP]──▶ IDLE
DRIVING ──[obstacle detected]──▶ STOPPED ──[path clear]──▶ IDLE
ANY ──[E-stop / overload]──▶ E_STOP
E_STOP ──[RESET]──▶ IDLE
```

**States:** `IDLE`, `DRIVING`, `STOPPED`, `DUMPING`, `DUMPING_COMPLETE`, `E_STOP`

### 7.3 Command Interface

| Command | Args | Description | Reject Codes |
|---------|------|-------------|-------------|
| `TRUCK_DRIVE` | `[x_target, y_target]` | Drive to position | `OBSTACLE_DETECTED`, `E_STOP_ACTIVE`, `POSITION_OUT_OF_RANGE` |
| `TRUCK_DUMP_START` | `[]` | Begin dump sequence | `E_STOP_ACTIVE`, `VEHICLE_NOT_STOPPED` |
| `TRUCK_DUMP_STOP` | `[]` | Halt dump / lower bed | `E_STOP_ACTIVE` |
| `TRUCK_STOP` | `[]` | Immediate stop | — |
| `RESET` | `[]` | Clear E_STOP | `PHYSICAL_ESTOP_ACTIVE` |
| `PING` | `[]` | Health check | — |

### 7.4 Safety Interlocks (ADR-0006)

- **Overload protection:** Load cell reading above threshold → `E_STOP` before dump.
- **Fail-closed E-stop:** `TRUCK_ESTOP_LOOP` open → `E_STOP`.
- **Obstacle detection:** Front/rear IR → immediate stop.

### 7.5 Telemetry Fields

```json
{
  "device_id": "dump-truck-01",
  "timestamp": "...",
  "state": "IDLE",
  "position": { "x": 0, "y": 0 },
  "dump_angle_deg": 0,
  "load_grams": 0,
  "sensors": {
    "obstacle_front": false,
    "obstacle_rear": false
  },
  "uptime": 0
}
```

---

## 8. Module 7 — Packaging Machine

**Canonical device_id:** `packaging-01`

### 8.1 IO Mapping

| IO Label | Pin | Type | Direction | Description |
|----------|-----|------|-----------|-------------|
| `PACK_SERVO_SEAL` | D13 | `SERVO` | Output | Seal/cut servo PWM |
| `PACK_CONV_FEED` | D14 | `DO` | Output | Feed conveyor enable |
| `PACK_OPT_INLET` | D55 | `DI` | Input | Product entering packaging |
| `PACK_OPT_OUTLET` | D56 | `DI` | Input | Packaged product exit |
| `PACK_TEMP_AI` | A3 | `AI` | Input | Seal heater temperature (ADC) |
| `PACK_PRESSURE_AI` | A4 | `AI` | Input | Pneumatic presssure (ADC) |
| `PACK_JAM_SENSE` | D57 | `DI` | Input | Packaging jam sensor |
| `PACK_ESTOP_LOOP` | D39 | `ESTOP` | Input | Hardware E-stop NC relay |

> ⚠️ **Hardware:** Packaging Machine actuator and sensor pinout are **UNVERIFIED** pending Issue #98 and dedicated adapter implementation (Issue #24).

### 8.2 State Machine

```
IDLE ──[PACK_START]──▶ FEEDING ──[product at inlet sensor]──▶ SEALING ──[seal cycle complete]──▶ COMPLETE ──[product exits]──▶ IDLE
FEEDING ──[jam detected]──▶ E_STOP
SEALING ──[temperature fault]──▶ FAULT
ANY ──[E-stop]──▶ E_STOP
E_STOP ──[RESET & button released]──▶ IDLE
FAULT ──[RESET & fault cleared]──▶ IDLE
```

**States:** `IDLE`, `FEEDING`, `SEALING`, `COMPLETE`, `FAULT`, `E_STOP`

### 8.3 Command Interface

| Command | Args | Description | Reject Codes |
|---------|------|-------------|-------------|
| `PACK_START` | `[package_type]` | Begin packaging cycle | `E_STOP_ACTIVE`, `ALREADY_RUNNING` |
| `PACK_STOP` | `[]` | Abort cycle safely | — |
| `SET_TEMP` | `[temp_c:int]` | Set seal temperature setpoint | `TEMP_OUT_OF_RANGE`, `E_STOP_ACTIVE` |
| `RESET` | `[]` | Clear E_STOP/FAULT | `PHYSICAL_ESTOP_ACTIVE`, `FAULT_NOT_CLEARED` |
| `PING` | `[]` | Health check | — |

### 8.4 Safety Interlocks (ADR-0006)

- **Fail-closed jam interlock:** `PACK_JAM_SENSE` → immediate `E_STOP`.
- **Fail-closed E-stop:** `PACK_ESTOP_LOOP` open → `E_STOP`.
- **Temperature fault:** If `PACK_TEMP_AI` exceeds safe seal temperature → `FAULT`.
- **Pressure fault:** If `PACK_PRESSURE_AI` below minimum → `FAULT`.

### 8.5 Telemetry Fields

```json
{
  "device_id": "packaging-01",
  "timestamp": "...",
  "state": "IDLE",
  "package_type": null,
  "cycle_count": 0,
  "sensors": {
    "seal_temp_adc": 0,
    "pressure_adc": 0
  },
  "uptime": 0
}
```

---

## 9. Module 8 — Brackets (Structural)

**Canonical device_id:** `brackets-01`

### 9.1 Nature of Module

`brackets-01` is a **structural** module — it provides mechanical mounting, alignment, and structural support for other modules. It does not have:
- An independent actuator
- An independent controller
- An independent state machine
- Independent telemetry

It is observable via the state of the modules it structurally supports. Any observable signal from `brackets-01` is delegated to a specific hosted module.

### 9.2 IO Mapping

No independent IO. The Bracket module is mounted to a specific bay on the factory frame. Observable signals are sourced from hosted modules:

| Hosted Module | Observable via |
|---------------|----------------|
| Conveyor Belt alignment | `conveyor-01` position sensor |
| Sorting Machine mount | `sorting-01` alignment sensor |
| Tower Crane base | `tower-crane-01` base load cell |

> ⚠️ **Hardware:** Bracket mechanical and electrical scope is **UNVERIFIED** pending Issue #98 and Issue #69 (structural review).

### 9.3 Safety Interlocks (ADR-0006)

Structural integrity interlocks are owned by the hosted module. Bracket deformation or mounting failure must be detectable by the hosted module's load/alignment sensor and propagated as a `FAULT` on that module.

### 9.4 Telemetry Fields

`brackets-01` emits no independent telemetry. Health of the bracket structure is reported as part of the hosted module's telemetry under `structural_health` (boolean, derived from load/alignment sensors).

```json
{
  "device_id": "brackets-01",
  "timestamp": "...",
  "state": "NOMINAL",
  "hosted_by": "frame-bay-3",
  "structural_health": true,
  "uptime": 0
}
```

---

## 10. Module 9 — Combine Modules (Orchestrated Workflow)

**Canonical device_id:** `combine-01`

### 10.1 Nature of Module

`combine-01` represents the **orchestrated end-to-end workflow** across all 8 physical modules. It is not an independently actuated device. Its "state" is the composite state of the production pipeline. Commands to `combine-01` are decomposed into sub-commands dispatched to the relevant module adapters.

### 10.2 Composition

| Sub-module | Role in Combine |
|-----------|----------------|
| `conveyor-01` | Material feed into pipeline |
| `sorting-01` | Classification and routing |
| `tower-crane-01` | Lift and place between stations |
| `parking-01` | Logistics vehicle staging |
| `forklift-01` | Pallet transport |
| `dump-truck-01` | Material delivery |
| `packaging-01` | Final packaging |
| `brackets-01` | Structural frame (observable) |

### 10.3 State Machine

```
IDLE ──[COMBINE_START_PRODUCTION]──▶ PRODUCTION_RUNNING
PRODUCTION_RUNNING ──[COMBINE_STOP]──▶ DRAINING ──[all items cleared]──▶ IDLE
PRODUCTION_RUNNING ──[any module E_STOP]──▶ SAFETY_HALT ──[RESET all]──▶ IDLE
PRODUCTION_RUNNING ──[all modules idle]──▶ IDLE
IDLE ──[any module active]──▶ PRODUCTION_RUNNING
```

**States:** `IDLE`, `PRODUCTION_RUNNING`, `DRAINING`, `SAFETY_HALT`

### 10.4 Command Interface

| Command | Args | Description | Reject Codes |
|---------|------|-------------|-------------|
| `COMBINE_START_PRODUCTION` | `[recipe_id]` | Begin production run | `MODULE_IN_FAULT`, `MODULE_IN_ESTOP` |
| `COMBINE_STOP` | `[]` | Graceful stop — drain pipeline | — |
| `COMBINE_EMERGENCY_STOP` | `[]` | Immediate halt all modules | — |
| `COMBINE_GET_STATUS` | `[]` | Return all module states | — |
| `RESET` | `[]` | Reset all modules to IDLE | `MODULE_IN_ESTOP` |
| `PING` | `[]` | Composite health check | — |

### 10.5 Safety Interlocks (ADR-0006)

- Any sub-module `E_STOP` → `combine-01` → `SAFETY_HALT` automatically.
- `COMBINE_EMERGENCY_STOP` sends `E_STOP` to all sub-modules simultaneously.
- Individual module reset is independent; `combine-01` monitors and returns to `IDLE` when all sub-modules are `IDLE`.

### 10.6 Telemetry Fields

```json
{
  "device_id": "combine-01",
  "timestamp": "...",
  "state": "IDLE",
  "modules": {
    "conveyor-01": { "state": "IDLE" },
    "sorting-01": { "state": "IDLE" },
    "tower-crane-01": { "state": "IDLE" },
    "parking-01": { "state": "IDLE" },
    "forklift-01": { "state": "IDLE" },
    "dump-truck-01": { "state": "IDLE" },
    "packaging-01": { "state": "IDLE" },
    "brackets-01": { "state": "NOMINAL" }
  },
  "production_counter": 0,
  "uptime": 0
}
```

---

## 11. Cross-Module Safety Rules

1. **Zone exclusion:** Tower Crane and Forklift share physical workspace. No concurrent movement allowed unless zone-clear handshake is confirmed.
2. **Sequential loading:** Dump Truck must be `IDLE` and `DUMPING_COMPLETE` before Forklift attempts `FORK_PICKUP`.
3. **Pipeline drain:** `COMBINE_STOP` waits for all in-flight items to reach a terminal station before declaring `IDLE`.
4. **No cross-module bypass:** AI / Digital Twin / Dashboard may not override any module's local E-stop or jam interlock.
5. **Physical E-stop sovereignty:** All modules implement fail-closed physical E-stop loops that cannot be reset via network command. On-site manual release is always required.

---

## 12. Verification Matrix

| Module | L0 Spec | L1 Unit | L2 Sim | L3 Bench | L4 HIL |
|--------|---------|---------|--------|----------|--------|
| Conveyor Belt | ✅ | ✅ | ✅ | 🔴 BLOCKED-#98 | 🔴 BLOCKED |
| Sorting Machine | ✅ | ✅ | ✅ | 🔴 BLOCKED-#98 | 🔴 BLOCKED |
| Tower Crane | ✅ | 🔴 Planned | 🔴 Planned | 🔴 BLOCKED-#98 | 🔴 BLOCKED |
| Parking Lot | ✅ | 🔴 Planned | 🔴 Planned | 🔴 BLOCKED-#98 | 🔴 BLOCKED |
| Forklift | ✅ | 🔴 Planned | 🔴 Planned | 🔴 BLOCKED-#98 | 🔴 BLOCKED |
| Dump Truck | ✅ | 🔴 Planned | 🔴 Planned | 🔴 BLOCKED-#98 | 🔴 BLOCKED |
| Packaging | ✅ | 🔴 Planned | 🔴 Planned | 🔴 BLOCKED-#98 | 🔴 BLOCKED |
| Brackets | ✅ | — | — | 🔴 BLOCKED-#98 | 🔴 BLOCKED |
| Combine | ✅ | 🔴 Planned | 🔴 Planned | 🔴 BLOCKED-#98 | 🔴 BLOCKED |

**Evidence levels:** L0 = specification, L1 = unit test, L2 = deterministic simulation, L3 = bench/HIL, L4 = integrated system.
