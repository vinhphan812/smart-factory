# Factory Control — Smart Factory

**Status: PLANNED** | Owner: AIBOT / DNTU | Related issues: #9 #10 #22–#27

## Purpose

Nine-module device adapters and production orchestration. Each module driver implements safe state machines, sensor polling, actuator command translation, and local E-stop enforcement.

## Inbound contracts

- MQTT commands from ESP32 bridge (`smart-factory/{deviceId}/command/down`)
- Physical sensor state from device hardware

## Outbound contracts

- MQTT telemetry via ESP32 bridge
- Physical actuator commands to device controllers

## Module structure

```
factory-control/
├── README.md            ← this file
├── src/
│   └── adapters/        ← one adapter per device (forklift, conveyor, crane, etc.)
├── tests/
└── simulators/          ← deterministic offline simulators
```

## Readiness

**PLANNED.** Module is not yet implemented. Hardware wiring, electrical levels and controller interfaces must be verified before production deployment.

## Safety constraints

- Local E-stop and motion limits are enforced by device adapters, not by MQTT or AI.
- Commands from network must not bypass device-local safety interlocks.
- AI/Twin/dashboard cannot initiate unapproved physical actions.
