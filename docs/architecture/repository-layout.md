# Repository Layout — Module Map

**Owner:** monorepo foundation, Issue #65.

## Modules

| Module path | Purpose | Inbound contracts | Outbound contracts | Status | Related issues |
|---|---|---|---|---|---|
| `esp32-ukit-bridge/` | ESP32–uKit firmware, AMLP, bridge tests | MQTT JSON commands | MQTT JSON results/status/telemetry | **Implemented** | #4 #5 #28 #29 #66 |
| `iot-gateway/` | MQTT ingest, normalization, event store, WebSocket/HTTP | MQTT broker | REST, WebSocket, SQLite snapshots | **Implemented** | #7 #8 #31 #32 |
| `factory-control/` | Nine-module device adapters, safe state machines, production orchestration | MQTT commands (via bridge) | MQTT telemetry, physical actuators | **PLANNED** | #9 #10 #22–#27 |
| `digital-twin/` | Unreal Engine 3D Digital Twin, telemetry-to-state mapping, reconnect/replay | Event store snapshots, REST/WebSocket | — | **PLANNED** | #11 #12 #33–#35 |
| `edge-ai-robot/` | MiniAlpha adapter, anomaly detection, bounded robot skills, action guard | Event store snapshots, alerts | MQTT (bounded commands) | **PLANNED** | #13 #14 #36–#38 |
| `dashboard/` | Role-specific operator display, read-only telemetry, incident log | Event store snapshots, REST/WebSocket | — | **PLANNED** | #15 #39 #40 |
| `integration-tests/` | E2E scenario harness, HIL/E2E reliability evidence | All module outputs | — | **PLANNED** | #16 #20 #42–#45 |
| `infrastructure/` | Local deployment, Docker Compose, secrets management, recovery | — | All module dependencies | **PLANNED** | #17 #41 #51 |
| `scripts/` | Repository-wide tooling, CI helpers, smoke checks | — | — | **PLANNED** | #65 |

## Root modules

| Path | Purpose | Status |
|---|---|---|
| `contracts/` | Cross-system event/command/telemetry schemas, validated against actual wire format | **Foundation** |
| `docs/` | Architecture, project context, research, development, testing and acceptance | **Maintained** |
| `shared/` | Shared tooling that spans multiple modules | Per-module ownership |

## Boundary rules

1. **Module private:** code in one module must not be imported by another without an explicit versioned contract.
2. **Cross-system schemas:** only in `contracts/`, with validated producer/consumer examples.
3. **No nested services:** backend services MUST NOT be placed under `esp32-ukit-bridge/`.
4. **No duplicate AMLP:** the AMLP protocol spec stays in `esp32-ukit-bridge/shared/protocol-spec/`, not copied into `contracts/`.
5. **Physical safety:** local device controllers own motion limits and E-stop; AI/Twin/dashboard cannot bypass these.
6. **Evidence over claims:** mark status as **Implemented**, **Simulated**, **Planned**, **Blocked**, or **Verified hardware**.

## Design note: Unity selected; original proposal specified Unreal Engine

The original 2026 research proposal specifies **Unreal Engine**, but the project's CURRENT engineering decision is **Unity**, confirmed by Unity-specific Issues #11/#12/#33–#35. Unity is the intended implementation in `digital-twin/`; see #11 for project setup and ADR-0003 proposed in PR #89. Any required institutional approval of the proposal's technology change remains **PENDING / NOT VERIFIED**; historical proposal text is not an active engineering requirement.

## Ownership

Each module owner-role and test levels are defined in `AGENTS.md`. New agents must read `docs/PROJECT_CONTEXT.md`, the relevant module docs, and the linked Issue before changing code.
