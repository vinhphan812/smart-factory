# Edge AI Robot — Smart Factory

**Status: IMPLEMENTED (L2 simulation)** | Related issues: #13 #14 #36–#38 #204

## Purpose

MiniAlpha robot adapter and Edge AI anomaly detection pipeline. Monitors event store for alerts, provides bounded supported on-site responses, and interacts with operators. AI must never override physical safety interlocks or initiate unapproved rescue actions.

The FIWARE response policy (Issue #204) proposes notification-only robot responses from read-only Orion-LD context; it never dispatches a skill by itself.

## Inbound contracts

- Event store snapshots from `iot-gateway/` (REST or WebSocket)
- Normalized device events: telemetry, alarms, command completions

## Outbound contracts

- Bounded MQTT commands via `iot-gateway/` (actions must be pre-authorized and fail-closed)

## Module structure

```
edge-ai-robot/
├── README.md            ← this file
├── src/
│   ├── adapter/         ← MiniAlpha REST/WebSocket adapter
│   ├── context/         ← FIWARE context response policy (read-only, notification-only)
│   ├── detection/       ← anomaly detection pipeline
│   └── skills/          ← bounded robot skill definitions
├── tests/
└── skills/             ← skill configuration
```

## Safety constraints

- All AI-initiated actions are **bounded** and **fail-closed**; E-stop and motion limits are enforced by `factory-control/`, not by AI.
- AI does not initiate unapproved physical rescue or override operator commands.
- Anomaly detection output is advisory; human operators approve or reject responses.

## FIWARE context response policy (Issue #204)

`src/edge_ai_robot/context/` consumes the FIWARE/Orion-LD context layer through
the structural `ContextReader` protocol. It **does not import `iot-gateway`**
(ADR-0001 module boundary rule).

| Rule | Behaviour |
|---|---|
| Context alone never dispatches | A `GatewayApproval` record from the incident outbox is always required. Otherwise `DENIED` / `NO_GATEWAY_APPROVAL`. |
| Notification-only | Only `notification`-category skills are proposable. |
| Physical skills blocked | `move_robot`, `activate_gripper`, `emergency_stop` and the topics `yanshee/movement`, `yanshee/grabbing`, `yanshee/navigation` are permanently `BLOCKED`. |
| Stale context refused | Context older than 120 s (default) or without a timestamp → `DENIED` / `CONTEXT_STALE`. |
| Unverified capability refused | Robot `verificationStatus != VERIFIED` → `DENIED` / `ROBOT_CAPABILITY_UNVERIFIED`. |
| E-stop independent | The policy refuses while the E-stop is active and never clears it. The hardwired E-stop remains the authority (ADR-0006). |

Contract: `contracts/fiware/ngsi-ld-yanshee-context.md` (v1.0.0).
Decision record: `docs/adr/adr-0016-fiware-yanshee-context-mapping.md`.
