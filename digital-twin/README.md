# Digital Twin — Smart Factory

**Status: PLANNED** | Engine: **Unreal Engine** | Related issues: #11 #12 #33–#35

## Purpose

Real-time Unity 3D visualization of the nine-module physical factory. The Twin reflects observed device states, events, alarms, reconnect behavior and stale/offline conditions. An offline animation is **not** evidence of synchronization with real machines.

## Inbound contracts

- Event store snapshots from `iot-gateway/` (REST or WebSocket)
- Normalized device events: telemetry, status, command completions

## Outbound contracts

- None (Twin is read-only; does not issue commands)

## Module structure

```
digital-twin/
├── README.md            ← this file
├── Assets/              ← Unity scenes, prefabs, scripts, materials
├── Config/             ← Engine and project settings
├── Source/             ← C++ Twin logic
└── Tests/              ← Twin synchronization tests
```

## Design note

**Current implementation target: Unity.** The original research proposal named Unreal Engine; that historical reference is not a requirement to build Unreal. Issue #11 tracks Unity bootstrap and exact editor version. Formal institutional approval of the research-proposal scope change remains unverified; see ADR-0003 in PR #89.

## Readiness

**PLANNED.** No Twin implementation exists yet. Hardware event wiring, topic subscription, latency requirements and synchronization protocol must be defined before implementation.
