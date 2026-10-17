# Edge AI Robot — Smart Factory

**Status: PLANNED** | Related issues: #13 #14 #36–#38

## Purpose

UBTECH Yanshee robot adapter and Edge AI anomaly detection pipeline. Monitors event store for alerts, provides bounded supported on-site responses, and interacts with operators. AI must never override physical safety interlocks or initiate unapproved rescue actions.

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
│   ├── adapter/         ← Yanshee SDK/API adapter (transport subject to #159 verification)
│   ├── detection/       ← anomaly detection pipeline
│   └── skills/          ← bounded robot skill definitions
├── tests/
└── skills/             ← skill configuration
```

## Safety constraints

- All AI-initiated actions are **bounded** and **fail-closed**; E-stop and motion limits are enforced by `factory-control/`, not by AI.
- AI does not initiate unapproved physical rescue or override operator commands.
- Anomaly detection output is advisory; human operators approve or reject responses.


## Platform migration control
**Selected robot: UBTECH Yanshee** (supersedes previous MiniAlpha plan). The supported YanAPI/SDK, exact firmware version, network interface, authentication and permitted skills are subject to #159. A robot-specific adapter must use separate mock/live implementations and safety checks (#160); physical HIL remains blocked until #161 and hardware preflight. Existing MiniAlpha-named code in unmerged PR #145 must not be treated as a deployable Yanshee driver.
