# Digital Twin — Smart Factory

**Status: IN PROGRESS** | Engine: **Unity 2022.3 LTS** | Related issues: #11 #12 #33–#35

## Purpose

Real-time Unity 3D visualization of the nine-module physical factory. The Twin reflects observed device states, events, alarms, reconnect behavior and stale/offline conditions. An offline animation is **not** evidence of synchronization with real machines.

## Implementation Status

**Scaffold complete per Issue #11** (branch `smart-factory/t_0376bf21-11-scaffold-unity-digital-twin-project`):

- Unity project structure with `Assets/Scripts/`, `Packages/`, `ProjectSettings/`
- Runtime architecture: `TwinOrchestrator`, `GatewayAdapter`, `DeviceManager`
- Prefab controllers: `ConveyorController`, `ActuatorController`
- Mock adapter for L2 simulation (`MockGatewayAdapter`)
- EditMode/PlayMode test stubs
- Source control policy (tracked/ignored files)
- See `unity/README.md` for full architecture documentation

## Inbound contracts

- Event store snapshots from `iot-gateway/` (REST or WebSocket)
- Normalized device events: telemetry, status, command completions

## Outbound contracts

- None (Twin is read-only; does not issue commands)

## Module structure

```
digital-twin/
├── README.md            ← this file
├── unity/               ← Unity project (scaffolded)
│   ├── Assets/
│   │   ├── Scripts/     ← C# components (Adapters, Core, Models, Prefabs, Mocks)
│   │   ├── Prefabs/    ← Unity prefabs (placeholder)
│   │   ├── Scenes/     ← Unity scenes
│   │   ├── Materials/  ← Visual materials
│   │   └── Tests/      ← EditMode & PlayMode tests
│   ├── Packages/       ← Unity package dependencies
│   ├── ProjectSettings/← Engine configuration
│   └── README.md       ← Unity-specific documentation
```

## Design note

**Current implementation target: Unity.** The original research proposal named Unity Engine; that historical reference is not a requirement to build Unity. Issue #11 tracks Unity bootstrap and exact editor version. Formal institutional approval of the research-proposal scope change remains unverified; see ADR-0003 in PR #89.

## Readiness

**IN PROGRESS.** Unity project scaffolded with:
- WebSocket gateway adapter (stub)
- Deterministic state reducer (`DeviceManager`)
- Conveyor and actuator prefab controllers
- Mock adapter for L2 testing
- Test infrastructure

Remaining work:
- Implement actual gateway WebSocket connection
- Add prefab 3D models
- Physical coordinate calibration (blocked by #9)
- Integration with factory-control simulator (Issue #10)

## References

- `unity/README.md` — Full Unity project documentation
- `docs/adr/adr-0003-digital-twin-engine.md` — Engine selection rationale
- `docs/twin/prefab-module-contracts.md` — Telemetry/command schemas
- `docs/hardware-blocked-issues-audit.md` — Issue #11 is L2-unblocked
