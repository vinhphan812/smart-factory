# Unity Digital Twin — Smart Factory

**Status: IN PROGRESS** | Engine: **Unity 2022.3 LTS** (recommended) | Related issues: #11 #12 #33 #34 #35

> **Important:** This project is scaffolded per Issue #11. The Unity editor version and build platform targets are set to the recommended 2022.3 LTS. Adjust `Packages/manifest.json` to match your installed Unity version.

## Purpose

Real-time Unity 3D visualization of the nine-module physical factory. The Twin reflects observed device states, events, alarms, reconnect behavior and stale/offline conditions. An offline animation is **not** evidence of synchronization with real machines.

## Runtime Architecture

```
                    ┌─────────────────────────────────────────┐
                    │          TwinOrchestrator               │
                    │    (Main scene coordinator)             │
                    └─────────────┬───────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  GatewayAdapter │   │  DeviceManager   │   │  (Future: REST)  │
│  WebSocket      │   │  State Reducer  │   │  Snapshot API    │
│  Client         │   │                  │   │                  │
└────────┬────────┘   └────────┬────────┘   └─────────────────┘
         │                     │
         │  CanonicalEvent    │  DeviceState
         │  (JSON from WS)   │  (reduced)
         ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Prefab Controllers                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ ConveyorCtrl │  │ActuatorCtrl │  │ (future)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `TwinOrchestrator` | Main scene coordinator; wires GatewayAdapter events to DeviceManager and prefabs |
| `GatewayAdapter` | WebSocket/REST connectivity to iot-gateway; handles reconnection, staleness |
| `DeviceManager` | Deterministic state reducer; applies canonical events → device state |
| `ConveyorController` | Conveyor prefab visual mapping (belt animation, sensors, status) |
| `ActuatorController` | Station actuator prefab visual mapping (channels, sensors) |
| `MockGatewayAdapter` | L2 simulation for testing without hardware (per Issue #11) |

## Data Flow

1. **Gateway → Twin:** `iot-gateway` publishes `CanonicalEvent` via WebSocket (port 8000)
2. **Parse:** `GatewayAdapter` deserializes JSON → `CanonicalEvent`
3. **Reduce:** `DeviceManager.ProcessEvent()` applies event to produce `DeviceState`
4. **Visualize:** Prefab controllers read `DeviceState` and update Unity transforms/materials
5. **Staleness:** `GatewayAdapter` monitors `received_at_ms`; marks stale after 60s timeout

## Contracts & Schemas

- **Event envelope:** `docs/twin/prefab-module-contracts.md` Section 6
- **Conveyor telemetry:** Section 4.3
- **Actuator telemetry:** Section 5.3
- **MQTT topics:** Section 3
- **Gateway REST API:** Section 8
- **ADR-0003:** Engine selection rationale

## Source Control Policy

### Tracked Files (version controlled)

```gitignore
# Track source code
Assets/Scripts/**/*.cs
Assets/Scripts/**/*.shader

# Track project configuration
ProjectSettings/ProjectSettings.asset
ProjectSettings/TimeManager.asset
Packages/manifest.json

# Track tests
Assets/Tests/**/*.cs
```

### Ignored Files (generated/local)

```gitignore
# Unity auto-generated
Library/
Temp/
Obj/
Logs/
UserSettings/

# Build outputs
Build/
Builds/
*.exe
*.dll
*.app

# IDE
.vscode/
.idea/
*.user
*.suo
```

### Branch Naming

Follow Smart Factory conventions:
- `feat/issue-{number}-{short-description}` — new features
- `fix/issue-{number}-{short-description}` — bug fixes
- `docs/issue-{number}-...` — documentation updates

### Editor Version

- **Recommended:** Unity 2022.3 LTS (Long Term Support)
- **Minimum:** Unity 2021.3 LTS
- **Editor path:** Open `digital-twin/unity/` as the project root

## Testing

### EditMode Tests (no play required)

```bash
# Run EditMode tests via Unity CLI (headless)
unity -batchmode -projectPath digital-twin/unity -runEditorTests
```

### PlayMode Tests (runtime)

```bash
# Run PlayMode tests
unity -batchmode -projectPath digital-twin/unity -runPlayModeTests
```

### Mock Adapter (L2 Simulation)

- **Purpose:** Test Twin without physical hardware or gateway
- **Component:** `SmartFactory.DigitalTwin.Mocks.MockGatewayAdapter`
- **Activation:** Add to scene, set `enableSimulation = true`
- **Use case:** CI tests, development, Issue #11 deliverable

## Build Targets

| Platform | Status | Notes |
|----------|--------|-------|
| Windows (x64) | Supported | Primary dev target |
| macOS | Supported | Cross-platform CI |
| Linux | Supported | Server/container builds |
| WebGL | Planned | Browser deployment |
| Android | Future | Tablet operator view |
| iOS | Future | Tablet operator view |

## Known Limitations

- **ADR-0009:** Telemetry schema mismatch (`values[]`/`` pairs{}` vs canonical `state{}`)
- **Physical coordinates:** Not yet calibrated; prefabs use synthetic positions
- **Unity version:** Project scaffold assumes 2022.3 LTS; adjust manifest.json for your version

## Dependencies

- **Unity 2022.3+** (editor)
- **WebSocketSharp** (WebSocket client) — or Unity's built-in `UnityWebRequest` with custom WebSocket
- **NUnit** (included via Unity Test Framework package)

## Quick Start

1. Open `digital-twin/unity/` in Unity Hub
2. Open scene `Assets/Scenes/Main.unity` (or create new)
3. Add `TwinOrchestrator` prefab to scene
4. Add `MockGatewayAdapter` for L2 testing (no gateway required)
5. Press Play to see simulated conveyor/actuator telemetry

## References

- [ADR-0003: Digital Twin Engine](../adr/adr-0003-digital-twin-engine.md)
- [Prefab Module Contracts](../twin/prefab-module-contracts.md)
- [Hardware-Blocked Issues Audit](../hardware-blocked-issues-audit.md) — Issue #11 is L2-unblocked
- [Gateway Canonical Event Model (`iot-gateway`)](../iot-gateway/src/iot_gateway/models.py)
