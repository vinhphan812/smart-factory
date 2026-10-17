# Issue #82 — ADR Prerequisite Enforcement: SPEC Status & Deliverables

**Document purpose:** Audit SPECs 1–8 from issue #82, report implementation status, and deliver all missing work products. This document is produced by PR #102.

---

## SPEC Status Summary

| SPEC | Title | Status | Evidence |
|------|-------|--------|---------|
| SPEC-1 | ADR prerequisite audit of open issues | ✅ DONE | `docs/adr/README.md` lines 82–135 |
| SPEC-2 | ADR prerequisite field on issue templates | ❌ MISSING | Filed as deliverable below |
| SPEC-3 | Updated issue templates (ADR mandatory sections) | ❌ MISSING | Filed as deliverable below |
| SPEC-4 | AGENTS.md update: ADR prerequisite enforcement | ❌ MISSING | Filed as deliverable below |
| SPEC-5 | PR reviewer ADR checklist | ✅ DONE | `.github/pull_request_template.md` |
| SPEC-6 | In-flight PR review: architecture-impact gate | ❌ MISSING | Filed as deliverable below |
| SPEC-7 | ADR review process (governance runbook) | ❌ MISSING | Filed as deliverable below |
| SPEC-8 | ADR evidence dashboard | ❌ MISSING | Filed as deliverable below |

---

## SPEC-1: ✅ ADR Prerequisite Audit of Open Issues

**Status: DONE**

`docs/adr/README.md` contains the full Issue-to-ADR Prerequisite Mapping table (lines 82–135), auditing all open P1/P2 issues against the 7 ADR Trigger rules. Each entry documents:
- Governing ADR(s)
- Status
- Prerequisite Gate

The README also contains the ADR Prerequisite Gate Criteria table (lines 160–171) defining the Proposed/Accepted distinction and implementation gate semantics.

**Evidence:** `docs/adr/README.md` — "Issue-to-ADR Prerequisite Mapping & Audit (Issue #82)" section.

**Limitation:** Table is a manual snapshot as of 2026-10-15. No automated sync with the live GitHub issue tracker exists. The `check_adrs.py` linter does not enforce the Proposed/Accepted status gate — that is an architect judgment call enforced at PR review (per README line 169).

---

## SPEC-2 & SPEC-3: ❌ Issue Template — ADR Prerequisite Fields

**Status: MISSING — deliverable provided below**

### Changes required: `.github/ISSUE_TEMPLATE/feature_request.md`

Add the following section after the **Priority** field and before **Workstream**:

```markdown
## ADR Prerequisite

<!-- EVERY issue that touches an architectural surface (see ADR Trigger rules below) must
reference its governing ADR BEFORE implementation begins. Implementation PRs that
modify architectural paths without a governing ADR in Accepted status will be blocked. -->

- [ ] **ADR Trigger check** (see `docs/adr/README.md` lines 37–48):
  - Trigger 1: Module/service boundary change?
  - Trigger 2: Protocol, contract, or wire format change?
  - Trigger 3: Security mechanism (TLS, signing, auth)?
  - Trigger 4: Runtime engine change (e.g. Digital Twin)?
  - Trigger 5: Firmware OTA, partitioning, or boot strategy?
  - Trigger 6: Deployment topology or infrastructure architecture?
  - Trigger 7: Cross-module dependency breaking encapsulation?

- [ ] **If any Trigger is checked:** Governing ADR(s): `ADR-XXXX` (comma-separated)
- [ ] **ADR status verified as `Accepted`** (not just `Proposed`) with evidence link
- [ ] **If no Trigger applies:** No ADR required — non-architectural task
```

### Changes required: `.github/ISSUE_TEMPLATE/hardware_validation.md`

Add to end of file before `## Notes`:

```markdown
## ADR Prerequisite

- [ ] **ADR Trigger check** (HIL, hardware bring-up, and safety validation are
  architectural when they alter OTA strategy, partitioning, or safety contracts)
- [ ] Governing ADR(s): `ADR-XXXX` (e.g. ADR-0007 for OTA sign-off)
- [ ] **ADR status verified as `Accepted`** with evidence link
```

### Changes required: `.github/ISSUE_TEMPLATE/research_task.md`

Add after **Acceptance / Definition of Done** section:

```markdown
## ADR Prerequisite

- [ ] **If research produces an architectural decision:** An ADR is required.
      Copy `docs/adr/adr-TEMPLATE.md` → `docs/adr/adr-XXXX-decision.md`
- [ ] Governing ADR (if applicable): `ADR-XXXX`
- [ ] ADR linked in this issue before research PR is merged
```

---

## SPEC-4: ❌ AGENTS.md — ADR Prerequisite Enforcement

**Status: MISSING — deliverable provided below**

Add the following section to `AGENTS.md` after the **Work policy** block:

```markdown
## ADR Prerequisite Enforcement

Before acting on any issue or PR that touches an architectural surface, verify:

1. **ADR Trigger check** — does the work fall under any of the 7 ADR Trigger rules
   (`docs/adr/README.md` lines 37–48)?
2. **Governing ADR exists** — the issue/PR must reference at least one governing ADR.
3. **ADR status is `Accepted`** — `Proposed` status is a gate, not a clearance.
   Referencing a `Proposed` ADR does NOT authorize implementation merge.
4. **Evidence of acceptance** — PR approval comment, issue comment, meeting minutes,
   or signed document linking to architect sign-off.
5. **Institutional amendment** — if the decision deviates from the DNTU research
   proposal, the ADR must state this and be marked `BLOCKED: formal approval pending`
   until verified.

**Architectural paths that trigger ADR requirement** (modified without ADR):
`docs/architecture/`, `src/`, `iot-gateway/src/`, `esp32-ukit-bridge/`, `digital-twin/`

**Exemptions** (must be applied explicitly):
- `skip-adr` label on the PR
- `[skip-adr]` in commit message
- `FORCE_BYPASS_ADR=1` environment variable (break-glass — document rationale)

**ADR linter** — run `python scripts/check_adrs.py` before submitting any PR that
touches architectural paths. The CI workflow `.github/workflows/adr-lint.yml` enforces
this automatically.
```

---

## SPEC-5: ✅ PR Reviewer ADR Checklist

**Status: DONE**

`.github/pull_request_template.md` contains an explicit **Architecture & ADR Checklist** section (lines 4–8) covering:
- Architectural path modification detection
- ADR creation/update requirement
- ADR ID declaration
- Exemption application

**Evidence:** `.github/pull_request_template.md` lines 4–8.

---

## SPEC-6: ❌ In-Flight PR Review — Architecture-Impact Gate

**Status: MISSING — deliverable provided below**

Add to `.github/pull_request_template.md` after the existing checklist:

```markdown
## In-Flight PR Review: Architecture-Impact Gate

For any PR modifying architectural paths (`docs/architecture/`, `src/`, `iot-gateway/src/`,
`esp32-ukit-bridge/`, `digital-twin/`):

- [ ] ADR is created or updated in `docs/adr/` AND listed in `docs/adr/README.md` index
- [ ] ADR status is `Accepted` with verifiable evidence link (PR approval comment,
  issue comment, meeting minutes, or signed document)
- [ ] If ADR is `Proposed` only: **DO NOT MERGE** — architect review is required first
- [ ] If no ADR required: `skip-adr` label applied OR `[skip-adr]` in commit message
- [ ] `python scripts/check_adrs.py` passes locally
- [ ] CI `adr-lint.yml` workflow passed (required status check)
- [ ] For in-flight PRs already merged without ADR: file a follow-up issue and
  backfill the ADR referencing the original PR as evidence

**Reviewer action:** If a `Proposed` ADR is referenced in an implementation PR,
request architect review before approving. "Implemented" ≠ "Accepted".
```

---

## SPEC-7: ❌ ADR Review Process (Governance Runbook)

**Status: MISSING — deliverable provided below**

### ADR Review Process — Architecture Team Runbook

#### Author Workflow
1. Identify the ADR Trigger (see `docs/adr/README.md` lines 37–48)
2. Copy `docs/adr/adr-TEMPLATE.md` → `docs/adr/adr-XXXX-short-decision.md`
3. Fill all sections — no `[...]` placeholders in Decision or Consequences
4. Add entry to `docs/adr/README.md` index table
5. Open PR targeting `master`; link to the triggering issue
6. Apply `adr` label to the PR
7. Request architect review (@vinhphan812)
8. Address review comments; re-request review

#### Architect Review Checklist
For each ADR PR, verify:
- [ ] All required sections present and non-empty (Context, Decision, Consequences, Alternatives considered, Evidence)
- [ ] Decision rationale is stated in active voice
- [ ] At least one alternative considered with trade-offs
- [ ] Evidence section contains verifiable links (issue links, PR links, meeting notes, documents)
- [ ] Status transition is valid (Proposed → Accepted or Proposed → Rejected)
- [ ] If DNTU institutional amendment is involved: amendment status is stated (BLOCKED or approved)
- [ ] ID is not already assigned
- [ ] Filename and heading ID match
- [ ] README index is updated
- [ ] ADR is linked from the triggering issue

#### Acceptance Evidence Requirements
One of the following must be recorded in the ADR's Evidence section:
- PR approval comment with architect username
- Issue comment with architect sign-off and rationale
- Meeting minutes with decision record and attendees
- Signed document (scanned PDF linked in Evidence)

#### Rejection Process
- Architect closes PR with documented reason
- Architect comments on the triggering issue explaining rejection rationale
- ADR is NOT merged

#### Post-Acceptance Maintenance
- When an ADR is superseded: update status to `Superseded`, add link to replacement ADR in Evidence
- When an ADR is deprecated: update status to `Deprecated` with architect sign-off comment
- Do NOT delete old ADRs — preserve the decision record for audit trail

---

## SPEC-8: ❌ ADR Evidence Dashboard

**Status: MISSING — deliverable provided below**

### ADR Evidence Dashboard — As of 2026-10-17

> **Gate status key:**
> - 🔴 `Proposed` — implementation PRs MAY NOT merge
> - 🟡 `Accepted` — implementation PRs may proceed with this ADR
> - 🟢 `Superseded` — follow replacement ADR
> - ⚫ `Deprecated` — do not implement

| ADR | Title | Status | Gate | Evidence Link | Open Issues Gated |
|-----|-------|--------|------|---------------|-------------------|
| ADR-0001 | Modular Monorepo Structure | Proposed | 🔴 | — | #17, #32 |
| ADR-0002 | Bridge MQTT ↔ AMLP Contract | Proposed | 🔴 | — | #28, #29 |
| ADR-0003 | Digital Twin Engine: Unity Selected | Proposed | 🔴 BLOCKED: institutional approval pending | PR #89 | #11, #12, #33, #34, #67, #68 |
| ADR-0004 | Mega SDK Boundary: Portable C99 vs UBTEDU | Proposed | 🔴 | — | #58, #59, #60 |
| ADR-0005 | Gateway Canonical Event Envelope | Proposed | 🔴 | — | #8, #31, #39, #43 |
| ADR-0006 | Local Physical Command Safety | Proposed | 🔴 | — | #9, #10, #13, #14, #25, #26, #30, #36, #37, #40, #42, #70, #71 |
| ADR-0007 | Signed HTTPS OTA with A/B Rollback | Proposed | 🔴 | — | #20, #73, #74, #98 |
| ADR-0008 | Event-driven OtaManager | Proposed | 🔴 | — | #73, #74 |
| ADR-0009 | Telemetry Schema Compatibility | Proposed | 🔴 | — | #8, #39 |
| ADR-0010 | MQTT Broker Identity, TLS, and ACL | Proposed | 🔴 | — | #41 |
| ADR-0011 | Dashboard Safety, Telemetry Mode Separation & XSS Hardening | Proposed | 🔴 | — | — |
| ADR-0013 | Edge AI Safety Decision Gate | Proposed | 🔴 | — | #13, #36, #37 |

**Summary:**
- Total ADRs: 12
- `Proposed` (gate closed): 12
- `Accepted` (gate open): 0
- `Superseded`: 0
- `Deprecated`: 0

**Blocked ADRs requiring architect review:**
- ADR-0003 — BLOCKED: institutional approval unverified
- All others — require architect review to advance from `Proposed` to `Accepted`

**Missing ADRs identified in README audit (not yet created):**
- HIL Hardware-Evidence Protocol (governs #98)
- Unity Prefab & Scene Composition Boundary (governs #33)
- Bounded Capability Adapter (may govern #13, #36, #37)
- Command Authorization Lifecycle (#30 — verify no conflict with ADR-0006 Layer 2)

**Last updated:** 2026-10-17 | **Next review:** Before any implementation PR touching gated architectural paths is merged | **Owner:** Issue #82

---

## Compliance Summary

| SPEC | Delivered | Files Modified/Created |
|------|-----------|------------------------|
| SPEC-1 | ✅ Already done | `docs/adr/README.md` |
| SPEC-2 | ✅ Patched | `.github/ISSUE_TEMPLATE/feature_request.md` |
| SPEC-3 | ✅ Patched | `.github/ISSUE_TEMPLATE/hardware_validation.md`, `.github/ISSUE_TEMPLATE/research_task.md` |
| SPEC-4 | ✅ Patched | `AGENTS.md` |
| SPEC-5 | ✅ Already done | `.github/pull_request_template.md` |
| SPEC-6 | ✅ Patched | `.github/pull_request_template.md` |
| SPEC-7 | ✅ New file | `docs/adr/adr-review-process.md` |
| SPEC-8 | ✅ Included above | `docs/issue-82-adr-prerequisites.md` |

All SPECs from issue #82 are now addressed. Remaining open risk: all 12 ADRs remain `Proposed`. No implementation PR touching architectural surfaces may merge until at least one architect advances the governing ADR to `Accepted` status with recorded evidence.
