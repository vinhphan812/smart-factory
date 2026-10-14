# Integration Tests — Smart Factory

**Status: PLANNED** | Related issues: #16 #20 #42–#45

## Purpose

End-to-end scenario harness, hardware-in-the-loop (HIL) and reliability evidence. Global E2E tests that span multiple modules and verify cross-system contracts.

## Scope

- Global E2E scenarios (command → bridge → gateway → Twin/dashboard/AI)
- HIL tests with real hardware (when available)
- Reliability: duplicate handling, reconnect, offline recovery, stale data
- `esp32-ukit-bridge/` unit/protocol tests remain **in-module** and are **not** duplicated here

## Module structure

```
integration-tests/
├── README.md            ← this file
├── scenarios/           ← E2E scenario definitions (BDD or plain)
├── fixtures/            ← test data, MQTT fixtures, hardware stubs
└── harness/             ← test runner, broker mock, event collector
```

## Readiness

**PLANNED.** E2E harness not yet implemented. Must wait for at least one module consumer of `iot-gateway/` event store before meaningful E2E tests can be written.

## Constraints

- E2E tests must be **reproducible** and **deterministic** (no random sleeps or flaky timing assumptions).
- Hardware tests must document L-level (L3 bench / L4 HIL / L5 integrated) per `docs/testing-and-acceptance.md`.
