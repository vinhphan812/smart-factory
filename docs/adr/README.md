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

## Issue-to-ADR Prerequisite Mapping & Audit (Issue #82)

P1/P2 open implementation issues have been audited against the 7 ADR Trigger rules defined above. Every architecture-impacting issue must reference its governing ADR(s) before implementation merge.

| Issue | Title | Priority | Architectural Impact / Trigger | Governing ADR(s) | Status / Prerequisite Note |
|---|---|---|---|---|---|
| #65 | Monorepo Foundation | P1 | Module / service boundary (Trigger 1) | ADR-0001 | Proposed (Foundation established) |
| #7, #22, #28, #29, #30 | Bridge MQTT & AMLP Contracts | P1 | Protocol / contract / wire format (Trigger 2) | ADR-0002, ADR-0009 | Proposed (Schema mismatch documented) |
| #11, #12, #33–#35 | Digital Twin Engine & Scene | P1 | Runtime engine change (Trigger 4) | ADR-0003 | Proposed (Unity selected; institutional approval pending) |
| #1, #2, #3, #56 | Mega & uKit Explore SDK Audit | P1 | Cross-module dependency / SDK boundary (Trigger 7) | ADR-0004 | Proposed (Portable C99 vs UBTEDU) |
| #5, #66 | Gateway Canonical Events | P1 | Protocol envelope & event store (Trigger 2) | ADR-0005, ADR-0009 | Proposed |
| #4, #9, #42 | Local Physical Safety & HIL | P0/P1 | Local physical command safety (Trigger 3, 5, 6) | ADR-0006 | Proposed (Fail-closed interlocks) |
| #20, #72 | Signed HTTPS OTA & A/B Rollback | P1 | Firmware OTA, partitioning, boot strategy (Trigger 5) | ADR-0007, ADR-0008 | Proposed |
| #41 | MQTT Broker Auth & TLS | P1 | Security mechanism (Trigger 3) | ADR-0006, ADR-0007 | Covered under security baseline |
| #39 | Telemetry Charts & Event Timeline | P2 | Dashboard / Gateway integration (Trigger 2) | ADR-0005, ADR-0009 | Covered by canonical events |
| #46 | Reproducible Experiments | P2 | Test/evaluation runbook (Exempt) | None | Non-architectural runbook (No ADR required) |

### Missing-ADR Findings & Recommendations
1. **Security & Broker Auth (#41):** TLS and MQTT broker authentication are currently governed under transport safety (ADR-0006/0007). Recommendation: Maintain current coverage; split into a dedicated ADR-0010 only if broker deployment topology changes.
2. **Status Enforcement:** All ADRs remain at `Proposed` status. In accordance with governance rules, no Proposed ADR is retroactively marked `Accepted` without verifiable review evidence and explicit architect sign-off.
3. **Hardware & Engine Limitations:** Unity digital twin selection (#11) and hardware module interfaces remain subject to hardware-evidence and unverified institutional amendment rules (`BLOCKED: formal approval pending` where applicable).
