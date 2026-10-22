# ADR-0016: Dashboard Nine-Module Registry and Derived Visual State Machine

- **Status:** Proposed
- **Date:** 2026-10-22
- **Deciders:** Smart Factory Architecture Team (Proposed during PR #260 review; pending formal merge approval)
- **Related issues:** #149, #148

## Context
The smart factory dashboard requires a canonical representation of the nine physical modules defined in `contracts/physical/factory-interface.md` (`conveyor-01`, `sorting-01`, `tower-crane-01`, `parking-01`, `forklift-01`, `dump-truck-01`, `packaging-01`, `brackets-01`, `combine-01`). Additionally, operators need a deterministic 6-state visual summary (`UNKNOWN`, `STALE`, `OFFLINE`, `SIMULATED`, `RUNNING`, `FAULT`) with specific safety constraints (e.g. structural brackets never reporting running state).

## Decision
1. Implement canonical `MODULE_DEFINITIONS` in `dashboard/src/contracts/modules.ts` matching the nine physical factory modules.
2. Implement `deriveModuleState()` to evaluate real-time gateway device statuses against heartbeat staleness (60s threshold) and raw firmware states.
3. Enforce TC-2 compliance: `brackets-01` is structurally passive and explicitly returns `UNKNOWN` (never `RUNNING`).
4. Provide comprehensive route registry containing all ten operator destinations with explicit read-only safety notices for actuation controls.

## Consequences
- **Positive:** Strict alignment between UI representations and physical factory contracts; robust unit test coverage (TC-1, TC-2).
- **Negative / Tradeoff:** Requires ongoing synchronization if physical module identifiers change in `factory-interface.md`.

## Alternatives considered
- Dynamic discovery via IoT gateway REST endpoints without static fallback (rejected due to offline simulation requirements and startup reliability).

## Evidence
- Unit tests in `dashboard/src/tests/modules.test.ts` pass successfully.
- TypeScript typecheck, ESLint, and production Vite build pass with zero errors.
