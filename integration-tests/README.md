# Integration Tests — Smart Factory

**Status: PARTIAL (L2 simulation)** | Related issues: #16 #20 #42–#45 #204

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
├── conftest.py          ← sys.path injection for both module src trees
├── scenarios/           ← E2E scenario definitions (BDD or plain)
├── fixtures/            ← test data, MQTT fixtures, hardware stubs
├── harness/             ← test runner, broker mock, event collector
└── fiware/              ← FIWARE context ↔ Yanshee controlled scenario (Issue #204)
```

## Readiness

**PARTIAL (L2 simulation).** The full E2E harness is still PLANNED. One
controlled cross-module scenario exists (see below); it uses an in-memory
NGSI-LD broker double rather than a live stack.

## FIWARE → Yanshee controlled scenario (Issue #204)

`fiware/test_fiware_yanshee_scenario.py` executes the SPEC-4 scenario:

```
anomalous sensor value → Gateway alert → NGSI-LD Alert Property
→ Dashboard/Unity subscriber → Yanshee approved notification
```

The broker is an in-memory NGSI-LD double and the robot is a mock, so this is
**L2 simulation** — it does not verify a real Orion-LD deployment or a real
Yanshee SDK. The scenario records a transport and provenance trace for every
hop, which is the raw evidence attached to the PR.

**Evidence:** L2 simulation. Real Orion-LD is **not** verified here (Issue #202
owns the containerised E2E harness); the real Yanshee SDK is **BLOCKED** on
Issue #159/#160.

## Constraints

- E2E tests must be **reproducible** and **deterministic** (no random sleeps or flaky timing assumptions).
- Hardware tests must document L-level (L3 bench / L4 HIL / L5 integrated) per `docs/testing-and-acceptance.md`.
