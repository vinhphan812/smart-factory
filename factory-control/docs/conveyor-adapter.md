# Conveyor Module Adapter Specification (Issue #22)

**Module:** `factory-control/src/factory_control/adapters/conveyor.py`  
**Status:** Implemented (L1 Unit Tests, L2 Software Simulation) | Hardware L3 Blocked (Issue #98)  
**Standard:** AMLP v1 & `contracts/v1` compliant  

---

## 1. Overview & Responsibilities

The `ConveyorAdapter` provides safe, deterministic control of the Smart Factory Conveyor Belt module (Module 1).

Key capabilities:
- **Finite State Machine (FSM):** Enforces 7 discrete operating states (`IDLE`, `STARTING`, `RUNNING`, `STOPPING`, `STOPPED`, `FAULT`, `E_STOP`).
- **Speed Bounds Enforcement:** Ensures speeds remain within safe operational bounds (default: `10` to `100` mm/s). Rejects negative, zero, and over-range speed values.
- **Fail-Closed Safety Interlocks (ADR-0006):** Photoelectric and mechanical jam sensors automatically trigger an immediate, non-bypassable local Emergency Stop (`E_STOP`).
- **Idempotency & Deduplication:** Caches execution results by `command_id` / `request_id`. Duplicate arrivals return cached results without re-actuating the motor.
- **Canonical Telemetry:** Emits telemetry payloads strictly matching `contracts/v1/schemas/telemetry.schema.json`.

---

## 2. State Machine Diagram

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> STARTING: CONVEYOR_START (valid speed)
    STARTING --> RUNNING: target speed reached
    RUNNING --> STOPPING: CONVEYOR_STOP / speed=0
    STOPPING --> STOPPED: speed=0
    STOPPED --> STARTING: CONVEYOR_START (valid speed)
    
    RUNNING --> E_STOP: Jam Sensor Active / Manual E-Stop
    STARTING --> E_STOP: Jam Sensor Active / Manual E-Stop
    IDLE --> E_STOP: Manual E-Stop
    STOPPED --> E_STOP: Manual E-Stop
    
    E_STOP --> IDLE: RESET (when jam sensor cleared)
    FAULT --> IDLE: RESET (when cleared)
```

---

## 3. Command Interface

Inbound commands follow `contracts/v1/schemas/command.schema.json`:

| Command Name | Arguments | Description | Failure Codes |
|---|---|---|---|
| `CONVEYOR_START` | `[speed]` | Start conveyor at target speed (10–100 mm/s) | `CANNOT_START_IN_ESTOP`, `CANNOT_START_IN_FAULT`, `JAM_SENSOR_ACTIVE`, `SPEED_BELOW_MIN`, `SPEED_EXCEEDS_MAX`, `NEGATIVE_SPEED_NOT_ALLOWED`, `INVALID_SPEED_FORMAT` |
| `CONVEYOR_STOP` | `[]` | Decelerate and stop conveyor | None (always safe) |
| `RESET` | `[]` | Reset adapter from E_STOP or FAULT to IDLE | `JAM_OBSTRUCTION_PRESENT` (if jam sensor still active) |
| `PING` | `[]` | Health check, returns current state and speed | None |

---

## 4. Hardware Pinout Reference (Arduino Mega 2560 & uKit)

| Signal | Device Pin | Logic Level | Description |
|---|---|---|---|
| Motor PWM | Pin D9 | 5V TTL (via driver) | Conveyor belt DC motor drive |
| Optical Entry Sensor | Pin D22 | 5V TTL (active HIGH) | Detects incoming material entering belt |
| Optical Exit Sensor | Pin D23 | 5V TTL (active HIGH) | Detects material reaching downstream station |
| Jam Detection Sensor | Pin D24 | 5V TTL (active HIGH) | Detects mechanical obstruction or backlog |

> ⚠️ **HIL Note:** Physical bench validation and flashing are **BLOCKED-L3** pending Issue #98 (uKit Mega board and licensing clearance).

---

## 5. Verification Evidence

- **L1 (Unit Tests):** 18 passing tests in `factory-control/tests/test_conveyor_adapter.py`.
- **L2 (Software Simulation):** Deterministic mock adapter verifies FSM transitions, sensor trips, and idempotency.
