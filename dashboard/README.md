# Dashboard — Smart Factory

**Status: PLANNED** | Related issues: #15 #39 #40

## Purpose

Role-specific operator display: read-only telemetry, incident log, authorized request submission. The dashboard does not bypass device safety interlocks or issue direct physical commands.

## Inbound contracts

- Event store snapshots from `iot-gateway/` (REST or WebSocket)
- Normalized device events, command completions, alarms

## Outbound contracts

- Authorized command requests via `iot-gateway/` (role-restricted, fail-closed)

## Module structure

```
dashboard/
├── README.md            ← this file
├── src/                 ← web UI (framework TBD)
├── tests/
└── deployment/          ← container or static hosting config
```

## Readiness

**PLANNED.** UI framework, data binding and role permissions not yet selected. Hardware event topics must be confirmed before UI development.
