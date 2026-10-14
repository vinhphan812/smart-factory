# Architecture Decision Records (ADRs) — Smart Factory

## Overview

This directory (`docs/adr/`) contains the Architecture Decision Records (ADRs) for the AIBOT Smart Factory monorepo. An Architectural Decision Record captures a significant architectural decision along with its context and consequences, adhering to the Nygard ADR format.

Governed by GitHub Issue #79.

---

## Decision Index

| ADR ID | Title | Status | Date |
|--------|-------|--------|------|
| [ADR-0001](adr-0001-modular-monorepo.md) | Modular Monorepo Structure | Proposed | 2026-10-14 |
| [ADR-0002](adr-0002-bridge-mqtt-amlp-contract.md) | Bridge MQTT ↔ AMLP Contract | Proposed | 2026-10-14 |
| [ADR-0003](adr-0003-digital-twin-engine.md) | Digital Twin Engine: Unreal vs Unity | Proposed | 2026-10-14 |
| [ADR-0004](adr-0004-mega-sdk-boundary.md) | Mega SDK Boundary: Portable C99 vs UBTEDU | Proposed | 2026-10-14 |
| [ADR-0005](adr-0005-gateway-canonical-events.md) | Gateway Canonical Event Envelope | Proposed | 2026-10-14 |
| [ADR-0006](adr-0006-local-physical-safety.md) | Local Physical Command Safety | Proposed | 2026-10-14 |
| [ADR-0007](adr-0007-signed-ota-ab-rollback.md) | Signed HTTPS OTA with A/B Rollback | Proposed | 2026-10-14 |
| [ADR-0008](adr-0008-ota-manager-event-driven.md) | Event-driven OtaManager (No Dedicated FreeRTOS Task) | Proposed | 2026-10-14 |
| [ADR-0009](adr-0009-telemetry-schema-compatibility.md) | Telemetry Schema Compatibility | Proposed | 2026-10-14 |

---

## Governance & Specification (Issue #79)

### SPEC-1: Canonical Directory Structure & Index
- All ADRs reside in `docs/adr/`.
- The decision index is maintained directly in this `README.md` file.

### SPEC-2: Canonical Template Structure
Every ADR must follow [adr-TEMPLATE.md](adr-TEMPLATE.md), including:
- Metadata header: ADR ID, Title, Status, Date, Deciders, Approver, Related Issues, Supersedes, Superseded By.
- Context & forces at play.
- Decision Drivers (requirements, constraints, quality attributes).
- Considered Alternatives and trade-offs.
- Decision (stated in active voice).
- Consequences (easier/harder, risks introduced/mitigated).
- Evidence & references (source files, test runs, issues, PRs).

### SPEC-3: Naming & Numbering Convention
- Format: `0001-short-imperative-decision.md` (four-digit zero-padded integer, followed by lowercase kebab-case description).
- Immutable Unique IDs: Once assigned, an ADR number is never reused or reordered.
- Stable Paths: Filenames must not change once merged to maintain persistent deep links.

### SPEC-4: Status Lifecycle & Allowed Transitions
- **Proposed:** Newly authored, under review or awaiting implementation consensus.
- **Accepted:** Reviewed and formally approved by project architecture lead.
- **Deprecated:** Applicable historically but discouraged or superseded in current practice.
- **Superseded:** Replaced by a newer ADR (must link to the successor).
- **Rejected:** Considered but formally discarded during evaluation.

**Allowed State Transitions:**
```
[Proposed] ──┬──> [Accepted] ──┬──> [Deprecated]
             ├──> [Rejected]   └──> [Superseded]
             └──> [Superseded]
```

### SPEC-5: Single Decision Rule & Traceability
- Each record describes exactly one primary architectural decision and its rationale.
- Historical decisions are never rewritten in place; a new ADR supersedes the old one to preserve complete project evolution history.

### SPEC-6: ADR Triggers (When an ADR is Required)
An ADR is mandatory for any change affecting:
1. **Module Boundaries:** Adding, removing, or restructuring modules in the monorepo.
2. **Protocol & Schema:** Modifying AMLP framing, MQTT topics, or cross-system event envelopes.
3. **Framework Selection:** Changing core frameworks (e.g. Unreal Engine version, ESP-IDF version, Python gateway framework).
4. **Security & Cryptography:** Authentication, token mechanisms, or signature verification.
5. **Actuator Safety & Interlocks:** Overrides, E-stop, or local physical safety barriers.
6. **Storage & State:** Event stores, persistence engines, or state machine invariants.
7. **CI/Release Pipeline:** Core build, packaging, or release strategies.
8. **OTA & Firmware Management:** Bootloader, A/B partition layout, rollback logic.
9. **Robotics & AI Integration:** Edge AI model boundaries or MiniAlpha capabilities.

*Exemptions:* Trivial bug fixes, formatting cleanups, internal refactorings within a single module's private code that do not cross public interfaces or architectural boundaries.

### SPEC-7: Approval Workflow & DNTU Proposal Amendments
- **Architect/Reviewer Approval:** Proposed ADRs require review by `dev-architect` or designated technical leads.
- **Human Safety Review:** Any ADR impacting physical actuators, E-stop, or OTA safety must undergo explicit human safety sign-off.
- **DNTU Proposal Amendment Handling:** Any amendment relating to research scope shifts (e.g. Unreal Engine vs Unity selection, hardware SDK capabilities) must be formally recorded via an ADR supersession or amendment rather than informal chat or code edits.
- **Cross-Linking:** ADRs must be referenced in module documentation (`docs/architecture/components.md`, `docs/README.md`) and relevant GitHub issues/PRs.

---

## Creating a New ADR

1. Copy `adr-TEMPLATE.md` to `adr-XXXX-short-title.md` (incrementing the next available 4-digit ID).
2. Fill out all sections completely.
3. Add a row to the index table in this `README.md`.
4. Open a PR for architectural review.
