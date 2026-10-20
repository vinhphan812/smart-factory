# Factory Control — Smart Factory Controller Simulator

**Status: IMPLEMENTED** | Owner: AIBOT / DNTU | Related issues: #9 #10 #22–#27

## Purpose

Nine-module device adapters and production orchestration with a deterministic state machine simulator for offline testing, module adapter mocks, Twin state mapping, and E2E testing.

## Implementation

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
├── src/
│   ├── __init__.py           # Package init
│   ├── state_machine.py      # Deterministic production state machine
│   ├── simulator.py          # Factory simulator for offline testing
│   └── adapters/
│       ├── __init__.py       # DeviceAdapter base class + concrete adapters
│       └── adapters.py        # Re-exports
└── tests/
    ├── conftest.py           # Test configuration
    ├── test_state_machine.py # State machine tests (26 tests)
    ├── test_adapters.py     # Adapter tests (23 tests)
    └── test_simulator.py    # Simulator tests (12 tests)
```

### Key Features

1. **Deterministic Production State Machine**
   - States: IDLE, INITIALIZING, READY, RUNNING, PAUSED, STOPPING, STOPPED, ERROR, ESTOP
   - Valid transitions defined per state
   - Auto-transitions (e.g., INITIALIZING → READY after 10 ticks)
   - Full transition history for traceability

2. **Device Adapters**
   - Base `DeviceAdapter` class
   - Concrete adapters: `ConveyorAdapter`, `RobotAdapter`, `CraneAdapter`
   - Command validation (TTL, correlation ID, state machine)
   - Telemetry generation

3. **Factory Simulator**
   - Multiple device management
   - Command execution interface
   - Event and telemetry callbacks
   - Preset factory configurations (`create_minimal_factory()`, `create_demo_factory()`)

### Usage

```python
from simulator import create_minimal_factory

# Create simulator
sim = create_minimal_factory()

# Execute commands
sim.execute_command("conveyor-01", "RESET", command_id=1)

# Run simulation
sim.run(10)  # Complete initialization

# Get state
state = sim.get_state()
print(state["devices"]["conveyor-01"]["state"])  # "ready"
```

### Inbound Contracts

- MQTT commands from ESP32 bridge (`smart-factory/{deviceId}/command/down`)
- Physical sensor state from device hardware (simulated)

### Outbound Contracts

- MQTT telemetry via ESP32 bridge (simulated)
- Physical actuator commands to device controllers (simulated)

## Tests

```bash
python -m pytest factory-control/tests/ -v
# 61 tests pass
```

## Safety Constraints

- Local E-stop and motion limits enforced by device adapters
- Commands from network must not bypass device-local safety interlocks
- AI/Twin/dashboard cannot initiate unapproved physical actions
