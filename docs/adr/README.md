# Architecture Decision Records — Smart Factory

Owner: Issue #65 (monorepo foundation) | Task t_e6179730 verification

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-0001](adr-0001-modular-monorepo.md) | Modular Monorepo Structure | Proposed | 2026-10-14 |
| [ADR-0002](adr-0002-bridge-mqtt-amlp-contract.md) | Bridge MQTT ↔ AMLP Contract | Proposed | 2026-10-14 |
| [ADR-0003](adr-0003-digital-twin-engine.md) | Digital Twin Engine: Unity Selected | Proposed | 2026-10-14 |
| [ADR-0004](adr-adr-0004-mega-sdk-boundary.md) | Mega SDK Boundary: Portable C99 vs UBTEDU | Proposed | 2026-10-14 |
| [ADR-0005](adr-0005-gateway-canonical-events.md) | Gateway Canonical Event Envelope | Proposed | 2026-10-14 |
| [ADR-0006](adr-0006-local-physical-safety.md) | Local Physical Command Safety | Proposed | 2026-10-14 |
| [ADR-0007](adr-0007-signed-ota-ab-rollback.md) | Signed HTTPS OTA with A/B Rollback | Proposed | 2026-10-14 |
| [ADR-0008](adr-0008-ota-manager-event-driven.md) | Event-driven OtaManager (No Dedicated FreeRTOS Task) | Proposed | 2026-10-14 |
| [ADR-0009](adr-0009-telemetry-schema-compatibility.md) | Telemetry Schema Compatibility | Proposed | 2026-10-14 |

## Status Lifecycle

Every ADR MUST contain one of the following statuses:

| Status | Meaning | Required before moving |
|--------|---------|------------------------|
| **Proposed** | Recorded, pending explicit approval evidence | Initial state |
| **Accepted** | Approved by architect with documented acceptance evidence | Verifiable approval link or recorded decision |
| **Rejected** | Explicitly declined | Architect sign-off |
| **Superseded** | Replaced by a later ADR | Link to replacement ADR |
| **Deprecated** | No longer applicable | Architect sign-off |

**Allowed transitions:** Proposed → Accepted | Proposed → Rejected | Accepted → Superseded | Deprecated is terminal.

**Rule:** Never mark an ADR Accepted without a verifiable link (PR approval, meeting minutes, issue comment, or signed document). "Implemented" does not equal "Accepted".

## ADR Trigger

An ADR is required BEFORE implementing any of the following changes:

1. Adding or removing a module or service boundary
2. Changing a protocol, contract, or wire format (MQTT topic, AMLP frame, API schema, event envelope)
3. Introducing, removing or materially changing a security mechanism (TLS, signing, authentication)
4. Changing the runtime engine for an existing system (e.g. Digital Twin)
5. Altering firmware OTA, partitioning, or boot strategy
6. Changing the deployment topology or infrastructure architecture
7. Changing a cross-module dependency that breaks encapsulation

ADR is NOT required for: bug fixes within existing contracts, documentation corrections, test additions, CI improvements, or cosmetic refactoring that does not alter external behaviour.

## Creating a New ADR

1. Copy `adr-TEMPLATE.md` to `adr-XXXX-short-imperative-decision.md`
2. Use kebab-case IDs: `adr-XXXX-short-imperative-decision.md`
3. Fill in all sections; do not leave `[...]` placeholders in Decision or Consequences
4. Add entry to this index
5. Link from relevant GitHub issues
6. ID is immutable once assigned — never renumber

## Approval Process

- **Author:** writes ADR, opens PR, links to trigger issue
- **Architect:** reviews decision rationale, alternatives, consequences and evidence
- **Acceptance:** architect merges PR and records evidence link
- **Rejection:** architect closes PR with documented reason

## DNTU Research Proposal Amendment

If a decision deviates from the original DNTU research proposal scope, the ADR MUST explicitly state:
- What the proposal originally specified
- What the engineering decision changes
- Whether formal institutional amendment has been verified

Unverified institutional amendment MUST be marked as: **BLOCKED: formal approval pending** in the ADR.

## Governance

ADRs are governed by Issue #79 (ADR governance). CI lint checks and architecture gates are implemented in Issue #80:
- **Linter script:** `scripts/check_adrs.py` validates ADR naming, metadata, required sections (Context, Decision, Consequences, Alternatives considered, Evidence), status values, and README index synchronization.
- **Architecture Impact Gate:** Any PR modifying architectural paths (`docs/architecture/`, `src/`, `iot-gateway/src/`, `esp32-ukit-bridge/`, `digital-twin/`) requires an accompanying ADR in `docs/adr/` unless exempted via `skip-adr` label, `[skip-adr]` commit message, or `FORCE_BYPASS_ADR=1` break-glass exception.
- **Workflow:** `.github/workflows/adr-lint.yml` runs automated linter checks and pytest fixture tests (TC-1 through TC-6) on push and pull requests.
