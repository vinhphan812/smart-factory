# Smart Factory — Module Capability Matrix

**Owner:** physical layer governance (Issues #9, #174)  
**Purpose:** Cross-cutting typed IO mapping, command interface, and telemetry interface for all nine modules. Used by: `factory-control/` adapters, `iot-gateway/` command dispatch, Digital Twin prefab mapping, schema registry.  
**Status:** Design-only — no hardware required. Physical pinout values are **UNVERIFIED** pending Issue #98 (L3 HIL gate).  

---

## 1. Legend

| Symbol | Meaning |
|--------|---------|
| `✓` | Implemented (L2 verified) |
| `△` | Planned (no adapter yet) |
| `—` | Not applicable (structural module) |
| `🔴` | Blocked (hardware gate) |
| `R/O` | Read-only |
| `R/W` | Read-write |
| `WO` | Write-only |

---

## 2. IO Type Summary Table

| Module | device_id | DI count | DO count | AI count | SERVO | MOTOR_PWM | STEP/ENC | ESTOP | HIL Status |
|--------|-----------|----------|----------|----------|-------|-----------|----------|-------|------------|
| Conveyor Belt | `conveyor-01` | 3 | 1 | 1 | — | 1 | — | 1 | 🔴 BLOCKED-#98 |
| Sorting Machine | `sorting-01` | 3 | 1 | — | 1 | — | — | 1 | 🔴 BLOCKED-#98 |
| Tower Crane | `tower-crane-01` | 5 | 3 | — | — | 1 | 2 | 1 | 🔴 BLOCKED-#98 |
| Parking Lot | `parking-01` | 4 | 2 | — | — | — | — | 1 | 🔴 BLOCKED-#98 |
| Forklift | `forklift-01` | 4 | — | — | 1 | 2 | — | 1 | 🔴 BLOCKED-#98 |
| Dump Truck | `dump-truck-01` | 2 | — | 2 | 1 | 2 | — | 1 | 🔴 BLOCKED-#98 |
| Packaging Machine | `packaging-01` | 3 | 1 | 2 | 1 | — | — | 1 | 🔴 BLOCKED-#98 |
| Brackets | `brackets-01` | — | — | — | — | — | — | — | 🔴 BLOCKED-#98 |
| Combine | `combine-01` | — | — | — | — | — | — | — | 🔴 BLOCKED-#98 |

---

## 3. Typed IO Mapping — Detail

### 3.1 Conveyor Belt (`conveyor-01`)

**Adapter:** `factory-control/src/adapters/conveyor.py` — ✅ L2 verified

| Signal Name | Pin / Channel | IO Type | Range | Units | Access | Description |
|------------|---------------|---------|-------|-------|--------|-------------|
| `CONV_MOTOR_PWM` | D9 | `MOTOR_PWM` | 0–255 | count | R/W | Belt drive PWM duty |
| `CONV_OPT_ENTRY` | D22 | `DI` | 0/1 | bool | R/O | Entry photoelectric beam |
| `CONV_OPT_EXIT` | D23 | `DI` | 0/1 | bool | R/O | Exit photoelectric beam |
| `CONV_JAM_SENSE` | D24 | `DI` | 0/1 | bool | R/O | Mechanical jam / obstruction |
| `CONV_TEMP_AI` | A0 | `AI` | 0–4095 | ADC | R/O | Motor temperature sensor |
| `CONV_HUMIDITY_AI` | A1 | `AI` | 0–4095 | ADC | R/O | Ambient humidity |
| `CONV_ESTOP_LOOP` | D28 | `ESTOP` | NC/OPEN | bool | R/O | Hardware E-stop NC relay |

> ⚠️ **A1 temporal multiplexing (design rationale):** `CONV_HUMIDITY_AI` (A1) and `TRUCK_DUMP_ANGLE_AI` (A1) share ADC channel A1. This is intentional: the dump truck and conveyor belt are never active simultaneously in the canonical production sequence — the truck delivers material to the forklift before the crane places it on the conveyor. The ESP32 firmware must configure A1 muxer select based on active module context. This must be enforced in the adapter implementation and documented in Issue #98 hardware verification.

**Safety envelope:** Speed 10–100 mm/s. Jam → `E_STOP`. E-stop loop OPEN → `E_STOP`.

---

### 3.2 Sorting Machine (`sorting-01`)

**Adapter:** `factory-control/src/adapters/sorting.py` — ✅ L2 verified

| Signal Name | Pin / Channel | IO Type | Range | Units | Access | Description |
|------------|---------------|---------|-------|-------|--------|-------------|
| `SORT_SERVO_PWM` | D10 | `SERVO` | 1 ms–2 ms | pulse | R/W | Diverter gate angle (−45° to +90°) |
| `SORT_OPT_INLET` | D25 | `DI` | 0/1 | bool | R/O | Item entering sorting station |
| `SORT_IND_METAL` | D26 | `DI` | 0/1 | bool | R/O | Inductive metal detection |
| `SORT_JAM_SENSE` | D27 | `DI` | 0/1 | bool | R/O | Diverter channel jam |
| `SORT_ESTOP_LOOP` | D28 | `ESTOP` | NC/OPEN | bool | R/O | Hardware E-stop NC relay |

**Safety envelope:** Jam → `E_STOP`. E-stop loop OPEN → `E_STOP`. Sensor bus heartbeat loss → `FAULT`.

---

### 3.3 Tower Crane (`tower-crane-01`)

**Adapter:** Not yet implemented — △ Planned (Issue #26)

| Signal Name | Pin / Channel | IO Type | Range | Units | Access | Description |
|------------|---------------|---------|-------|-------|--------|-------------|
| `CRANE_STEP_PULSE` | D3 | `STEP` | 0/1 | pulse | WO | Trolley X step pulse |
| `CRANE_STEP_DIR` | D4 | `DO` | 0/1 | bool | WO | Trolley X direction |
| `CRANE_HOIST_PWM` | D5 | `MOTOR_PWM` | 0–255 | count | R/W | Hoist motor up/down |
| `CRANE_LIMIT_X_MIN` | D30 | `DI` | 0/1 | bool | R/O | X minimum limit switch |
| `CRANE_LIMIT_X_MAX` | D31 | `DI` | 0/1 | bool | R/O | X maximum limit switch |
| `CRANE_LIMIT_Z_LOW` | D32 | `DI` | 0/1 | bool | R/O | Z lower limit |
| `CRANE_LIMIT_Z_HIGH` | D33 | `DI` | 0/1 | bool | R/O | Z upper limit / overload |
| `CRANE_ENC_X_A` | D40 | `ENC` | A phase | pulse | R/O | Quadrature X position A |
| `CRANE_ENC_X_B` | D41 | `ENC` | B phase | pulse | R/O | Quadrature X position B |
| `CRANE_ENC_Z_A` | D42 | `ENC` | A phase | pulse | R/O | Quadrature Z position A |
| `CRANE_ENC_Z_B` | D43 | `ENC` | B phase | pulse | R/O | Quadrature Z position B |
| `CRANE_ESTOP_LOOP` | D29 | `ESTOP` | NC/OPEN | bool | R/O | Hardware E-stop NC relay |

> ⚠️ Pin assignments are **UNVERIFIED** pending Issue #98. Step/DIR and ENC counts are based on standard Mega 2560 pinout conventions.

**Safety envelope:** Any limit switch → `E_STOP`. E-stop loop OPEN → `E_STOP`. Zone occupancy handshake required before entering Forklift zone.

---

### 3.4 Parking Lot (`parking-01`)

**Adapter:** Not yet implemented — △ Planned (Issue #71)

| Signal Name | Pin / Channel | IO Type | Range | Units | Access | Description |
|------------|---------------|---------|-------|-------|--------|-------------|
| `PARK_IR_SLOT_1` | D50 | `DI` | 0/1 | bool | R/O | Slot 1 IR occupancy |
| `PARK_IR_SLOT_2` | D51 | `DI` | 0/1 | bool | R/O | Slot 2 IR occupancy |
| `PARK_IR_SLOT_3` | D52 | `DI` | 0/1 | bool | R/O | Slot 3 IR occupancy |
| `PARK_IR_SLOT_4` | D53 | `DI` | 0/1 | bool | R/O | Slot 4 IR occupancy |
| `PARK_GATE_OPEN` | D11 | `DO` | 0/1 | bool | WO | Gate barrier open |
| `PARK_GATE_CLOSE` | D12 | `DO` | 0/1 | bool | WO | Gate barrier close |
| `PARK_ESTOP_LOOP` | D34 | `ESTOP` | NC/OPEN | bool | R/O | Hardware E-stop NC relay |

> ⚠️ Gate actuator type (servo/solenoid) and slot count are **UNVERIFIED** pending Issue #98.

**Safety envelope:** E-stop loop OPEN → `E_STOP`. Vehicle-in-gate → gate reopen.

---

### 3.5 Forklift (`forklift-01`)

**Adapter:** Not yet implemented — △ Planned (Issue #25)

| Signal Name | Pin / Channel | IO Type | Range | Units | Access | Description |
|------------|---------------|---------|-------|-------|--------|-------------|
| `FORK_DRIVE_PWM` | D6 | `MOTOR_PWM` | 0–255 | count | R/W | Wheel drive motor |
| `FORK_STEER_SRV` | D7 | `SERVO` | 1 ms–2 ms | pulse | R/W | Steering servo |
| `FORK_LIFT_PWM` | D8 | `MOTOR_PWM` | 0–255 | count | R/W | Fork lift motor |
| `FORK_IR_FRONT` | D45 | `DI` | 0/1 | bool | R/O | Front obstacle IR |
| `FORK_IR_REAR` | D46 | `DI` | 0/1 | bool | R/O | Rear obstacle IR |
| `FORK_LIMIT_LIFT_LOW` | D35 | `DI` | 0/1 | bool | R/O | Fork lowered limit |
| `FORK_LIMIT_LIFT_HIGH` | D36 | `DI` | 0/1 | bool | R/O | Fork raised limit |
| `FORK_ESTOP_LOOP` | D37 | `ESTOP` | NC/OPEN | bool | R/O | Hardware E-stop NC relay |

**Safety envelope:** IR obstacle → immediate stop. Limit switches stop lift. E-stop → `E_STOP`.

---

### 3.6 Dump Truck (`dump-truck-01`)

**Adapter:** Not yet implemented — △ Planned (Issue #70)

| Signal Name | Pin / Channel | IO Type | Range | Units | Access | Description |
|------------|---------------|---------|-------|-------|--------|-------------|
| `TRUCK_DRIVE_PWM` | D6 | `MOTOR_PWM` | 0–255 | count | R/W | Wheel drive |
| `TRUCK_STEER_SRV` | D7 | `SERVO` | 1 ms–2 ms | pulse | R/W | Steering servo |
| `TRUCK_DUMP_PWM` | D8 | `MOTOR_PWM` | 0–255 | count | R/W | Dump bed tilt |
| `TRUCK_IR_FRONT` | D47 | `DI` | 0/1 | bool | R/O | Front obstacle IR |
| `TRUCK_IR_REAR` | D48 | `DI` | 0/1 | bool | R/O | Rear obstacle IR |
| `TRUCK_DUMP_ANGLE_AI` | A1 | `AI` | 0–4095 | ADC | R/O | Dump bed angle sensor |
| `TRUCK_LOAD_CELL_AI` | A2 | `AI` | 0–4095 | ADC | R/O | Load cell (bed weight) |
| `TRUCK_ESTOP_LOOP` | D38 | `ESTOP` | NC/OPEN | bool | R/O | Hardware E-stop NC relay |

**Safety envelope:** Load cell overload → `E_STOP` before dump. E-stop → `E_STOP`. Obstacle IR → immediate stop.

---

### 3.7 Packaging Machine (`packaging-01`)

**Adapter:** Not yet implemented — △ Planned (Issue #24)

| Signal Name | Pin / Channel | IO Type | Range | Units | Access | Description |
|------------|---------------|---------|-------|-------|--------|-------------|
| `PACK_SERVO_SEAL` | D13 | `SERVO` | 1 ms–2 ms | pulse | R/W | Seal/cut servo |
| `PACK_CONV_FEED` | D14 | `DO` | 0/1 | bool | WO | Feed conveyor enable |
| `PACK_OPT_INLET` | D55 | `DI` | 0/1 | bool | R/O | Product entering |
| `PACK_OPT_OUTLET` | D56 | `DI` | 0/1 | bool | R/O | Packaged product exit |
| `PACK_TEMP_AI` | A3 | `AI` | 0–4095 | ADC | R/O | Seal heater temperature |
| `PACK_PRESSURE_AI` | A4 | `AI` | 0–4095 | ADC | R/O | Pneumatic pressure |
| `PACK_JAM_SENSE` | D57 | `DI` | 0/1 | bool | R/O | Packaging jam |
| `PACK_ESTOP_LOOP` | D39 | `ESTOP` | NC/OPEN | bool | R/O | Hardware E-stop NC relay |

**Safety envelope:** Jam → `E_STOP`. Temperature fault → `FAULT`. Pressure fault → `FAULT`. E-stop → `E_STOP`.

---

### 3.8 Brackets (`brackets-01`)

**Type:** Structural — no independent actuator or IO. Observable via hosted module sensors.

| Hosted Module | Bracket Signal | IO Type | Access | Source |
|---------------|---------------|---------|--------|--------|
| Conveyor Belt | `BRK_ALIGN_CONV` | `AI` | R/O | Conveyor alignment sensor |
| Sorting Machine | `BRK_ALIGN_SORT` | `AI` | R/O | Sorting alignment sensor |
| Tower Crane | `BRK_LOAD_CRANE` | `AI` | R/O | Crane base load cell |

No E-stop loop on `brackets-01` independently. Structural failure is propagated as `FAULT` on the hosted module.

---

### 3.9 Combine Modules (`combine-01`)

**Type:** Orchestrated — no independent actuator or IO. Composed of all 8 physical modules.

| Sub-module | Composition Type | IO Access |
|-----------|-----------------|-----------|
| `conveyor-01` | Pipeline feed | Delegated |
| `sorting-01` | Classification | Delegated |
| `tower-crane-01` | Lift/place | Delegated |
| `parking-01` | Logistics staging | Delegated |
| `forklift-01` | Pallet transport | Delegated |
| `dump-truck-01` | Material delivery | Delegated |
| `packaging-01` | Final packaging | Delegated |
| `brackets-01` | Structural frame | Delegated |

---

## 4. Command Interface Summary

| Module | Start | Stop | Reset | Move/Lift | Config | Ping |
|--------|-------|------|-------|-----------|--------|------|
| Conveyor Belt | `CONVEYOR_START` | `CONVEYOR_STOP` | `RESET` | — | speed | `PING` |
| Sorting Machine | `SORT_ITEM` | `SORTING_STOP` | `RESET` | `ROUTE_MANUAL` | — | `PING` |
| Tower Crane | — | `CRANE_STOP` | `RESET` | `CRANE_MOVE_X`, `CRANE_HOIST`, `CRANE_PICKUP`, `CRANE_DROPOFF` | — | `PING` |
| Parking Lot | `GATE_OPEN` | `GATE_CLOSE` | `RESET` | — | — | `PING` |
| Forklift | — | `FORK_STOP` | `RESET` | `FORK_DRIVE`, `FORK_LIFT`, `FORK_PICKUP`, `FORK_DROPOFF` | — | `PING` |
| Dump Truck | — | `TRUCK_STOP` | `RESET` | `TRUCK_DRIVE`, `TRUCK_DUMP_START`, `TRUCK_DUMP_STOP` | — | `PING` |
| Packaging | `PACK_START` | `PACK_STOP` | `RESET` | — | `SET_TEMP` | `PING` |
| Brackets | — | — | — | — | — | `PING` |
| Combine | `COMBINE_START_PRODUCTION` | `COMBINE_STOP` | `RESET` | — | recipe_id | `PING` |

---

## 5. Telemetry Interface Summary

| Module | State Field | Key Metrics | Sensors |
|--------|------------|-------------|---------|
| `conveyor-01` | `state` | `speed` | `digital_inputs`, `temperature_centi_c` |
| `sorting-01` | `state` | `counts` (bin_1/2/3/reject) | `diverter_angle` |
| `tower-crane-01` | `state` | `position.x`, `position.z`, `load_grams` | `limit_*` flags |
| `parking-01` | `state` | `slots`, `available_count` | gate sensors |
| `forklift-01` | `state` | `position`, `fork_height_mm`, `load_grams` | `obstacle_*` |
| `dump-truck-01` | `state` | `position`, `dump_angle_deg`, `load_grams` | `obstacle_*` |
| `packaging-01` | `state` | `cycle_count` | `seal_temp_adc`, `pressure_adc` |
| `brackets-01` | `state` | `structural_health` | delegated |
| `combine-01` | `state` | `production_counter`, per-module `state` | — |

All telemetry conforms to `contracts/v1/telemetry.schema.json`.

---

## 6. Deterministic Controller Contracts

### 6.1 Idempotency Contract

Every module adapter MUST implement command deduplication:

1. Incoming command contains `command_id` (int ≥ 0) or `request_id` (string).
2. Cache stores `(command_id, command_name, args)` → result for `idempotency_window_seconds` (default 300 s).
3. Duplicate with identical payload → return cached result with `duplicate: true`.
4. Duplicate with **different** payload → `rejected` with error code `CONFLICTING_COMMAND_REUSE`.

### 6.2 State Transition Contract

Each module enforces an explicit FSM. Only the following transitions are valid:

- Any state → `E_STOP`: triggered by local sensor (jam, obstacle, limit switch) or `ESTOP` loop.
- Any state → `FAULT`: triggered by sensor bus loss, temperature fault, or encoder fault.
- `E_STOP` → `IDLE`: only via `RESET` command AND all trigger conditions cleared AND physical E-stop button released.
- `FAULT` → `IDLE`: only via `RESET` command AND fault condition cleared.

**No network command may bypass hardware E-stop or jam interlocks.**

### 6.3 Telemetry Contract

Each module emits telemetry on:
1. Every command completion.
2. Every state transition.
3. Every 1-second tick (minimum heartbeat interval).

Telemetry topic: `smart-factory/telemetry/{device_id}`

---

## 7. Schema Registry Integration

All modules are pre-registered in the schema registry with the following canonical IDs:

| Module | registry_key | version | schema_file |
|--------|-------------|---------|------------|
| `conveyor-01` | `device:factory:conveyor` | 1.0.0 | `factory-control/src/factory_control/models.py` |
| `sorting-01` | `device:factory:sorting` | 1.0.0 | `factory-control/src/factory_control/models.py` |
| `tower-crane-01` | `device:factory:tower-crane` | 1.0.0 | — (planned) |
| `parking-01` | `device:factory:parking` | 1.0.0 | — (planned) |
| `forklift-01` | `device:factory:forklift` | 1.0.0 | — (planned) |
| `dump-truck-01` | `device:factory:dump-truck` | 1.0.0 | — (planned) |
| `packaging-01` | `device:factory:packaging` | 1.0.0 | — (planned) |
| `brackets-01` | `device:factory:brackets` | 1.0.0 | — (structural) |
| `combine-01` | `device:factory:combine` | 1.0.0 | — (orchestrated) |

> See Issue #169 for schema registry implementation.
