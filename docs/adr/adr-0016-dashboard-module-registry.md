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
5. **Fail-closed derivation (added after maintainer review round #1, finding 2).** `deriveModuleState()` accepts an explicit `DeriveOptions { now, provenance }` and never infers a trustworthy-looking state from absent evidence:
   - a missing, empty or unparsable heartbeat resolves to `UNKNOWN`;
   - a heartbeat dated more than `MAX_CLOCK_SKEW_MS` (5s) in the future resolves to `UNKNOWN`;
   - `SIMULATED` is reachable **only** when `provenance === 'simulated'` or when the gateway itself reports a simulated state token. It is never a fallback for unclassified live data.
6. **No fabricated measurements (added after maintainer review round #1, finding 1).** Module cards and the module detail page must not render invented numeric readings. Until the gateway exposes a verified per-device telemetry source, every measurement cell renders `N/A` together with an explicit reason (`no telemetry source` / `no sensors`).
7. **Freshness is clock-driven (added after maintainer review round #1, finding 4).** Operator views re-derive state on a periodic clock tick (15s) with the evaluation timestamp included in the memo dependency list, so an idle device transitions to `STALE` even when the gateway store has not changed.
8. **Gateway state is carried end to end (added after maintainer review round #1, finding 3).** `DeviceInfo.state` is populated from the canonical event payload (`payload.state`, falling back to `payload.status`) and is preserved across heartbeat events that carry no state token, so `RUNNING` / `FAULT` are derived from real gateway data rather than from a UI-side default.

## Consequences
- **Positive:** Strict alignment between UI representations and physical factory contracts; robust unit test coverage (TC-1, TC-2); an operator can no longer mistake demo or stale data for live production state.
- **Negative / Tradeoff:** Requires ongoing synchronization if physical module identifiers change in `factory-interface.md`. Fail-closed derivation makes the dashboard quieter — most modules read `UNKNOWN` until a gateway is connected — which is the intended trade: absence of evidence is displayed as absence of evidence.

## Alternatives considered
- Dynamic discovery via IoT gateway REST endpoints without static fallback (rejected due to offline simulation requirements and startup reliability).

## Evidence
- Unit tests in `dashboard/src/tests/modules.test.ts` pass successfully.
- Regression tests in `dashboard/src/tests/no-fabricated-telemetry.test.tsx` cover fail-closed derivation, absence of fabricated measurements, gateway state propagation and clock-driven staleness.
- TypeScript typecheck, ESLint, and production Vite build pass with zero errors.
