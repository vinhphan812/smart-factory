# Architecture Decision Records — Smart Factory

Owner: Issue #82 (ADR prerequisites) | Task t_08672f24 v2

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
| [ADR-0010](adr-0010-mqtt-broker-security.md) | MQTT Broker Identity, TLS, and ACL Authorization | Proposed | 2026-10-15 |
| [ADR-0012](adr-0012-unity-digital-twin-prefab-contracts.md) | Unity Digital Twin Prefab Contracts | Proposed | 2026-10-16 |
| [ADR-0015](adr-0015-yanshee-robot-selection.md) | UBTECH Yanshee as Smart Factory Edge AI Robot | Proposed | 2026-10-17 |

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

> **⚠️ ADR Status Gate — Read Before Acting on This Table:** All ADRs below are currently `Proposed`. Referencing an ADR in a PR does **NOT** automatically approve architecture-impacting work. An ADR must reach `Accepted` status with verifiable architect sign-off evidence (PR approval comment, issue comment, meeting minutes, or signed document) before any implementation PR touching that architectural surface may be merged. The "Prerequisite Gate" column documents the exact requirement per issue. See "ADR Prerequisite Gate Criteria" below.

P1/P2 **open** implementation issues have been audited against the 7 ADR Trigger rules defined above (lines 39–45 of this README). Only issues currently open in the live tracker are included (this table is a manual snapshot as of 2026-10-15 — verify against live tracker before relying on prerequisite gates). Closed and archived issues are listed in the Historical Closed Issues appendix. Every architecture-impacting issue must reference its governing ADR(s) before implementation merge.

| # | Area | Title | Priority | ADR Trigger(s) | Governing ADR(s) | Status / Prerequisite Gate |
|---|---|---|---|---|---|---|
| #98 | BRIDGE | Hardware-in-the-loop (HIL) verification and licensing clearance for uKit Mega | P0 | Trigger 3, 5, 7 | ADR-0004, ADR-0007, ADR-0008 | Missing ADR: HIL hardware-evidence protocol and licensing clearance decision record required before HIL sign-off |
| #11 | TWIN | Scaffold Unity Digital Twin project, runtime architecture and source-control policy | P1 | Trigger 4 | ADR-0003 | Proposed (Unity selected; institutional approval pending — BLOCKED) |
| #33 | TWIN | Model nine factory modules as reusable Unity prefabs and scene objects | P1 | Trigger 4, 7 | ADR-0003 | Proposed; Unity prefab ownership and scene composition boundary ADR required before merge |
| #34 | TWIN | Implement Unity time synchronization, stale data and snapshot resync | P1 | Trigger 4, 7 | ADR-0003 | Proposed; gateway transport adapter (#67) and offline replay contract required first |
| #67 | TWIN | Define Unity gateway transport adapter and offline replay contract fixture pack | P1 | Trigger 4, 7 | ADR-0003 | Proposed; prerequisite for #12, #34 |
| #68 | TWIN | Calibrate nine-module physical-to-Unity coordinate and state mapping | P1 | Trigger 4, 7 | ADR-0003 | Proposed; prerequisite: physical module interfaces (#9, #25, #26) must be stable first |
| #12 | TWIN | Map live gateway telemetry to deterministic 3D factory state | P1 | Trigger 4 | ADR-0003 | Proposed; prerequisite: #67 transport adapter must be defined first |
| #58 | BRIDGE | Port AMLP v1 endpoint to Arduino Mega HardwareSerial | P1 | Trigger 7 | ADR-0004 | Proposed; prerequisite: Mega SDK audit (#56) must be completed before Mega port |
| #59 | BRIDGE | Implement safe uKit Explore motor servo sensor adapter and conveyor pilot | P1 | Trigger 3, 7 | ADR-0004, ADR-0006 | Proposed; safety guard and SDK boundary ADR required before motor control |
| #60 | BRIDGE | Add Mega CI and hardware-in-loop flash wiring and recovery guide | P1 | Trigger 7 | ADR-0004 | Proposed; prerequisite: #56 Mega SDK audit |
| #73 | BRIDGE | Implement authenticated HTTPS OTA client, maintenance gating and rollback on ESP32 bridge | P1 | Trigger 3, 5 | ADR-0007, ADR-0008 | Proposed |
| #74 | BRIDGE | Build OTA release pipeline, staged rollout and real ESP32-S3 recovery test matrix | P1 | Trigger 5, 6 | ADR-0007, ADR-0008 | Proposed; prerequisite: #73 client implementation |
| #41 | INFRA | Harden MQTT broker authentication, TLS and secret management | P1 | Trigger 3 | **ADR-0010** | **Proposed; ADR-0010 (broker identity, TLS trust chain, ACL matrix) governs this issue and remains reserved for broker security. PR #100 must use ADR-0011.** |
| #9 | PHYSICAL | Define 9-module physical factory interface and end-to-end sequence | P1 | Trigger 3, 7 | ADR-0006 | Proposed; prerequisite for all physical module adapters |
| #25 | PHYSICAL | Forklift and dump-truck telemetry/control abstraction | P1 | Trigger 3, 7 | ADR-0006 | Proposed; prerequisite: #9 interface definition |
| #26 | PHYSICAL | Tower-crane and storage/parking logistics adapter | P1 | Trigger 3, 7 | ADR-0006 | Proposed; prerequisite: #9 interface definition |
| #70 | PHYSICAL | Dump Truck device adapter, transport state and safety test suite | P1 | Trigger 3, 7 | ADR-0006 | Proposed; prerequisite: #9 interface definition |
| #71 | PHYSICAL | Parking Lot occupancy and logistics-slot adapter | P1 | Trigger 3, 7 | ADR-0006 | Proposed; prerequisite: #9 interface definition |
| #69 | PHYSICAL | Bracket structural module inventory, mounting and observability contract | P1 | Trigger 3, 7 | ADR-0006 | Proposed; prerequisite: #9 interface definition |
| #36 | EDGE-AI | Implement robot alert notification skills and typed execution feedback | P1 | Trigger 7 | ADR-0003, ADR-0006 | Proposed; AI capability adapter bounded by fail-closed gate (ADR-0006 Layer 4) |
| #37 | EDGE-AI | Add fail-closed safety decision gate between AI and physical actions | P1 | Trigger 3 | ADR-0006 | Proposed; ADR-0006 Layer 4 AI action guard governs this issue |
| #13 | EDGE-AI | Implement MiniAlpha connectivity and bounded robot capability adapter | P1 | Trigger 3, 7 | ADR-0003, ADR-0006 | **SUPERSEDED** — MiniAlpha replaced by Yanshee per ADR-0015; see #160 for Yanshee adapter |
| #158 | EDGE-AI | [P1][ARCH][YANSHEE] Record UBTECH Yanshee as the Smart Factory Edge AI robot and supersede MiniAlpha assumptions | P1 | Trigger 7 | **ADR-0015** | Proposed; ADR-0015 ratification PR (#207) tracks this decision |
| #159 | EDGE-AI | [P1][EDGE-AI][YANSHEE] Audit actual UBTECH Yanshee robot hardware, SDK/API, network interfaces and licensing | P1 | Trigger 3 | ADR-0015 | Open; must complete before Yanshee adapter implementation (#160) |
| #160 | EDGE-AI | [P1][EDGE-AI][YANSHEE] Implement UBTECH Yanshee typed adapter and safe notification skills with mock/live separation | P1 | Trigger 3, 7 | ADR-0006, ADR-0015 | Open; prerequisite: #159 SDK audit must complete first |
| #161 | EDGE-AI | [P1][INTEGRATION][YANSHEE] Validate Yanshee robot end-to-end alerts, operator approval and physical HIL acceptance | P1 | Trigger 6, 7 | ADR-0006, ADR-0015 | Open; prerequisite: #160 adapter implementation |
| #178 | EDGE-AI | [P1][EDGE-AI] Build robot-independent alert skill contract and Yanshee capability authorization layer | P1 | Trigger 7 | ADR-0006, ADR-0015 | Open; robot-agnostic skill contract after #159/#160 provide concrete API surface |
| #14 | EDGE-AI | Design edge anomaly detection, alert triage and human-safe response pipeline | P1 | Trigger 3 | ADR-0006 | Proposed; fail-closed triage pipeline must be defined before deployment |
| #39 | DASHBOARD | Add telemetry charts, event timeline and incident acknowledgment | P1 | Trigger 2 | ADR-0005, ADR-0009 | Proposed; covered by canonical events and telemetry schema ADRs |
| #16 | INTEGRATION | Create end-to-end acceptance suite: device → bridge → twin → edge robot | P1 | Trigger 6, 7 | ADR-0003, ADR-0005 | Proposed; E2E harness architecture ADR may be required for cross-module integration |
| #42 | INTEGRATION | Create hardware/software capability and simulation fallback matrix | P1 | Trigger 3, 6 | ADR-0006 | Proposed; capability matrix must document safety boundaries under hardware failure |
| #8 | DATA | Implement observability and event replay for Smart Factory | P1 | Trigger 2 | ADR-0005, ADR-0009 | Proposed; telemetry and canonical event ADRs govern observability contract |
| #10 | PHYSICAL | Implement factory controller simulator and deterministic production state machine | P1 | Trigger 3 | ADR-0006 | Proposed; simulator must enforce same safety rules as physical controller |
| #30 | CONTRACT | Define command authorization, lease and acknowledgement lifecycle | P1 | Trigger 3 | ADR-0006 | Proposed; command lifecycle must align with ADR-0006 Layer 2 validation rules |
| #31 | DATA | Implement durable event store, snapshots and retention policy | P1 | Trigger 2 | ADR-0005 | Proposed; event store schema must match canonical event envelope (ADR-0005) |
| #32 | DATA | Define device registry and configuration ownership | P1 | Trigger 7 | ADR-0001 | Proposed; registry ownership must respect module boundary rules from ADR-0001 |
| #17 | INFRA | Deliver local reproducible dev stack and environment configuration | P1 | Trigger 6 | ADR-0001 | Proposed; local stack must match module boundaries and deployment topology |
| #35 | TWIN | Add interactive factory playback, camera tours and alarm highlighting | P2 | Trigger 4 | ADR-0003 | Proposed; Unity playback is within scope of ADR-0003 |
| #38 | EDGE-AI | Evaluate anomaly model/rule quality on repeatable incidents | P2 | — | — | Non-architectural evaluation task; No ADR required |
| #40 | DASHBOARD | Create role-based command request console with confirmation gate | P2 | Trigger 3 | ADR-0006 | Proposed; confirmation gate must respect ADR-0006 Layer 4 AI action guard |
| #43 | INTEGRATION | Measure end-to-end sync latency, jitter and event loss | P2 | Trigger 6 | ADR-0003, ADR-0005 | Proposed; latency SLA requires defined measurement methodology |
| #44 | INTEGRATION | Run extended soak and network fault-injection reliability tests | P2 | Trigger 6 | — | Non-architectural reliability test; No ADR required |
| #45 | QA | Add test coverage, negative-case matrix and PR quality gates | P2 | — | — | Non-architectural QA process; No ADR required |
| #46 | RESEARCH | Define reproducible experiments and baseline comparison methods | P1 | — | — | Non-architectural runbook; No ADR required |
| #47 | RESEARCH | Build research evidence archive and reproducibility package | P2 | — | — | Non-architectural; No ADR required |
| #48 | RESEARCH | Prepare final scientific/technical report and handover dossier | P2 | — | — | Non-architectural; No ADR required |
| #49 | TRAINING | Produce beginner-to-advanced Smart Factory lab exercises | P2 | — | — | Non-architectural; No ADR required |
| #50 | TRAINING | Build guided demo and operational handover for AIBOT visitors | P2 | — | — | Non-architectural; No ADR required |
| #20 | QA | Add hardware-in-the-loop test matrix and safety sign-off protocol | P2 | Trigger 3, 5 | ADR-0007 | Proposed; HIL test matrix must include OTA safety sign-off per ADR-0007 |
| #52 | TRACKING | Master backlog and 12-month execution map | P1 | — | — | Non-architectural project management; No ADR required |

### Historical Closed Issues Appendix

These issues are closed; their resolution status is recorded for audit trail. They informed ADR backfill but do not gate current implementation.

| Issue | Title | Resolution | Governing ADR(s) | Notes |
|-------|-------|-----------|-----------------|-------|
| #65 | Monorepo Foundation | CLOSED — P0 | ADR-0001 | Root foundation; ADR-0001 Proposed |
| #1 | Fix root GitHub Actions | CLOSED — P0 | — | Infrastructure fix; no ADR trigger |
| #2 | Add root overview & onboarding | CLOSED — P0 | — | Documentation; no ADR trigger |
| #3 | Define canonical contracts | CLOSED — P0 | ADR-0002, ADR-0009 | Contract definitions; ADRs Proposed |
| #4 | Verify uKit hardware interface | CLOSED — P0 | — | Resolved; no ADR trigger hit |
| #5 | Harden bridge command auth | CLOSED — P0 | ADR-0006 | Covered by physical safety ADR |
| #56 | Audit uKit Explore SDK | CLOSED — P0 | ADR-0004 | Covered by SDK boundary ADR |
| #57 | Create Arduino Mega firmware target | CLOSED — P0 | — | Implementation of ADR-0004 |
| #62 | Align docs with Unity decision | CLOSED — P0 | ADR-0003 | Docs alignment; ADR Proposed |
| #66 | ESP32 UART TEL → MQTT telemetry | CLOSED — P0 | ADR-0005 | Covered by gateway events ADR |
| #72 | Secure ESP32-S3 OTA architecture | CLOSED — P0 | ADR-0007 | ADR Proposed; implementation pending #73/#74 |
| #79 | Establish ADR governance | CLOSED — P0 | — | Governance itself; no ADR trigger |
| #80 | Implement ADR lint & CI gate | CLOSED — P0 | — | Meta; no ADR trigger |
| #81 | Backfill Smart Factory ADRs | CLOSED — P1 | — | This audit is its deliverable |
| #28 | Bridge MQTT JSON ↔ AMLP parity | CLOSED — P1 | ADR-0002 | Covered by bridge contract ADR |
| #29 | Bridge telemetry health & recovery | CLOSED — P1 | ADR-0002 | Covered by bridge contract ADR |
| #7 | MQTT ingestion gateway | CLOSED — P0 | ADR-0005 | Covered by gateway events ADR |

### ADR Prerequisite Gate Criteria

| ADR Status | Meaning | Implementation Gate |
|------------|---------|--------------------|
| **Proposed** | Drafted; pending architect review | **MAY NOT** merge implementation PRs that alter this architectural surface. ADR must first reach `Accepted`. |
| **Accepted** | Architect has reviewed and recorded verifiable approval evidence | Implementation PRs referencing this ADR may proceed to merge, subject to other prerequisite gates. |
| **Superseded** | Replaced by a later ADR | Implementation must follow the replacement ADR; original is deprecated. |
| **Deprecated** | No longer applicable | Do not implement against this architectural surface. |

**Rule:** Referencing an ADR in a PR does NOT automatically approve architectural work. The ADR must be `Accepted` with documented evidence. "Proposed" status is a gate, not a clearance. The CI architecture-impact gate (`scripts/check_adrs.py`) does not enforce the Proposed/Accepted distinction — that is an architect judgment call enforced at PR review.

**Required evidence for Accepted status** (per "Status Lifecycle" section above): PR approval comment, issue comment, meeting minutes, or signed document. "Implemented" does not equal "Accepted".

### Missing-ADR Findings & Recommendations

1. **HIL Hardware-Evidence Protocol (#98):** Hardware-in-the-loop verification for uKit Mega integration requires a dedicated ADR defining the HIL evidence protocol, licensing clearance decision record, and hardware-evidence acceptance criteria before P0 HIL sign-off. No current ADR covers this.
2. **Unity Prefab & Scene Composition Boundary (#33):** Prefab ownership and scene composition rules require a dedicated ADR before merging the Unity prefab module. ADR-0003 covers engine selection but not internal asset architecture.
3. **Bounded Capability Adapter (#13, #36, #37):** The edge-AI MiniAlpha capability adapter, robot alert skills, and fail-closed safety gate interact across multiple layers. While ADR-0006 Layer 4 covers the AI action guard, a dedicated ADR may be required to document the full capability boundary and bounded execution contract.
4. **Command Authorization Lifecycle (#30):** The command authorization, lease, and acknowledgement lifecycle is closely coupled with ADR-0006 Layer 2 bridge validation. Verify no conflict between the two ADRs before implementation.
5. **Status Enforcement:** All ADRs remain at `Proposed` status. No Proposed ADR is retroactively marked `Accepted` without verifiable review evidence and explicit architect sign-off. `Implemented` does not equal `Accepted`.
6. **Hardware-Evidence and Institutional Amendment Limitations:** Unity digital twin (#11, #33, #34, #67, #68) and hardware module interfaces remain subject to hardware-evidence requirements and unverified institutional amendment rules (`BLOCKED: formal approval pending` where applicable). Issues #1, #2, #3, #5, #7, #28, #29, #65 and other closed/archived issues are excluded from the open-issues table as they are no longer open. Issues #22 and #30 remain OPEN and are included in the open-issues table.
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
| [ADR-0011](adr-0011-dashboard-safety.md) | Dashboard Safety, Telemetry Mode Separation & XSS Hardening | Proposed | 2026-10-15 |

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
