# Digital Twin — Smart Factory

**Status: PLANNED** | Engine: **Unreal Engine** | Related issues: #11 #12 #33–#35

## Purpose

Real-time Unreal Engine 3D visualization of the nine-module physical factory. The Twin reflects observed device states, events, alarms, reconnect behavior and stale/offline conditions. An offline animation is **not** evidence of synchronization with real machines.

## Inbound contracts

- Event store snapshots from `iot-gateway/` (REST or WebSocket)
- Normalized device events: telemetry, status, command completions

## Outbound contracts

- None (Twin is read-only; does not issue commands)

## Module structure

```
digital-twin/
├── README.md            ← this file
├── Assets/              ← Unreal Engine assets (actors, materials, blueprints)
├── Config/             ← Engine and project settings
├── Source/             ← C++ Twin logic
└── Tests/              ← Twin synchronization tests
```

## Design note

The original research proposal specifies **Unreal Engine** (not Unity). This module uses Unreal Engine 5+. Issue #11 tracks bootstrap and architecture decisions.

## Readiness

**PLANNED.** No Twin implementation exists yet. Hardware event wiring, topic subscription, latency requirements and synchronization protocol must be defined before implementation.
