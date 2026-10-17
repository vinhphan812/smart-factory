# Factory Control — Smart Factory

**Status: IN PROGRESS** | Owner: AIBOT / DNTU | Related issues: #9 #10 #22–#27

## Purpose

Nine-module device adapters and production orchestration. Each module driver implements safe state machines, sensor polling, actuator command translation, and local E-stop enforcement.

## Implemented Adapters

| Adapter | Status | Evidence Level | Specification |
|---|---|---|---|
| `ConveyorAdapter` | **Implemented** | L1 Unit Tests, L2 Simulation | [docs/conveyor-adapter.md](docs/conveyor-adapter.md) (Fixes #22) |
| `SortingAdapter` | **Implemented** | L1 Unit Tests, L2 Simulation | [docs/sorting-adapter.md](docs/sorting-adapter.md) (Fixes #23) |
| `PackagingAdapter` | Planned | — | #24 |
| `ForkliftAdapter` | Planned | — | #25 |
| `TowerCraneAdapter` | Planned | — | #26 |

## Inbound contracts

- MQTT commands from ESP32 bridge (`smart-factory/{deviceId}/command/down`)
- Physical sensor state from device hardware

## Outbound contracts

- MQTT telemetry via ESP32 bridge
- Physical actuator commands to device controllers

## Module structure

```
factory-control/
├── README.md
├── pyproject.toml
├── docs/
│   ├── conveyor-adapter.md
│   └── sorting-adapter.md
├── src/
│   ├── __init__.py
│   ├── models.py
│   └── adapters/
│       ├── __init__.py
│       ├── base.py
│       ├── conveyor.py
│       └── sorting.py
└── tests/
    ├── __init__.py
    ├── test_conveyor_adapter.py
    └── test_sorting_adapter.py
```

## Readiness

- **Software Implementation (L1/L2):** Implemented with deterministic FSM, payload-bound command idempotency, item deduplication, and sensor safety interlocks.
- **Hardware Integration (L3/L4):** Physical wiring, electrical levels, and uKit actuators remain **BLOCKED-L3** pending Issue #98 and Issue #9.

## Safety constraints

- Local E-stop and motion limits are enforced by device adapters, not by MQTT or AI.
- Commands from network must not bypass device-local safety interlocks.
- Physical hardware E-Stop button press cannot be cleared by network software reset (ADR-0006).
- AI/Twin/dashboard cannot initiate unapproved physical actions.
