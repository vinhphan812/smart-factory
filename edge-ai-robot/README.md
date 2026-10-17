# Edge AI Robot — Smart Factory

**Status: IMPLEMENTED (L2 simulation)** | Related issues: #13 #14 #36–#38

## Purpose

MiniAlpha robot adapter and Edge AI anomaly detection pipeline. Monitors event store for alerts, provides bounded supported on-site responses, and interacts with operators. AI must never override physical safety interlocks or initiate unapproved rescue actions.

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
│   ├── detection/       ← anomaly detection pipeline
│   └── skills/          ← bounded robot skill definitions
├── tests/
└── skills/             ← skill configuration
```

## Safety constraints

- All AI-initiated actions are **bounded** and **fail-closed**; E-stop and motion limits are enforced by `factory-control/`, not by AI.
- AI does not initiate unapproved physical rescue or override operator commands.
- Anomaly detection output is advisory; human operators approve or reject responses.
