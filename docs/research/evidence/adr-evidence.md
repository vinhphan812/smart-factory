# L0 Evidence — ADR Status and Governance Audit

**Evidence level:** L0 (static/schema/review)
**Scope:** `docs/adr/`
**Archive version:** smart-factory/t_74cb2b44-47-research-evidence-archive-and-reprodu
**Pinned commit:** `244f333`
**Date:** 2026-10-17

---

## What this evidence covers

Architecture Decision Records (ADRs) document the rationale, alternatives, and consequences of significant architectural choices. This file audits the current ADR status, prerequisite gate health, and governance compliance at the pinned archive version.

**Evidence level:** L0 (static review, lint, and documentation audit — no code execution required).

---

## ADR index

| ADR | Title | Status | Date | Proposed → Accepted transition |
|-----|-------|--------|------|-------------------------------|
| ADR-0001 | Modular Monorepo Structure | Proposed | 2026-10-14 | No architect sign-off recorded |
| ADR-0002 | Bridge MQTT ↔ AMLP Contract | Proposed | 2026-10-14 | No architect sign-off recorded |
| ADR-0003 | Digital Twin Engine: Unity Selected | Proposed | 2026-10-14 | Institutional approval PENDING |
| ADR-0004 | Mega SDK Boundary | Proposed | 2026-10-14 | No architect sign-off recorded |
| ADR-0005 | Gateway Canonical Event Envelope | Proposed | 2026-10-14 | No architect sign-off recorded |
| ADR-0006 | Local Physical Command Safety | Proposed | 2026-10-14 | No architect sign-off recorded |
| ADR-0007 | Signed HTTPS OTA with A/B Rollback | Proposed | 2026-10-14 | No architect sign-off recorded |
| ADR-0008 | Event-driven OtaManager | Proposed | 2026-10-14 | No architect sign-off recorded |
| ADR-0009 | Telemetry Schema Compatibility | Proposed | 2026-10-14 | No architect sign-off recorded |
| ADR-0010 | MQTT Broker Identity, TLS, ACL Authorization | Proposed | 2026-10-15 | No architect sign-off recorded |
| ADR-0011 | Dashboard Safety, Telemetry Mode Separation & XSS Hardening | Proposed | 2026-10-15 | No architect sign-off recorded |
| ADR-0012 | Unity Digital Twin Prefab Contracts | Proposed | 2026-10-16 | No architect sign-off recorded |

**Critical rule:** All ADRs are currently `Proposed`. None have reached `Accepted` status. Referencing a `Proposed` ADR in an implementation PR does **not** authorize the work. The ADR must first reach `Accepted` with documented architect sign-off evidence.

---

## Lint results — L0 evidence

**Claim:** All ADRs conform to the naming convention, required sections, status values, and README index synchronization.

**Lint tool:** `scripts/check_adrs.py`

**Required sections per ADR template:**
1. Title
2. Status
3. Context
4. Decision
5. Consequences
6. Alternatives considered
7. Evidence (of Proposed → Accepted transition, when applicable)

**Evidence:**
- `scripts/check_adrs.py` — no errors reported for existing ADRs
- `.github/workflows/adr-lint.yml` — CI workflow exists and runs on push/PR

**Reproduce:**
```bash
python scripts/check_adrs.py
```

**ADR naming convention:** `adr-XXXX-short-imperative-decision.md` in kebab-case. IDs are immutable.

---

## Prerequisite gate audit

Per `docs/adr/README.md` §"Issue-to-ADR Prerequisite Mapping & Audit", the following architectural surfaces require an Accepted ADR before implementation PRs touching them may be merged:

| Architectural surface | Governing ADR(s) | Current status | Implementation gate |
|-----------------------|-----------------|---------------|---------------------|
| Module boundaries | ADR-0001 | Proposed | CLOSED — do not merge PRs altering module boundaries until ADR-0001 Accepted |
| Protocol/wire format | ADR-0002, ADR-0005 | Proposed | CLOSED — no protocol changes until Accepted |
| Security mechanism | ADR-0006, ADR-0010 | Proposed | CLOSED — no security changes until Accepted |
| Digital Twin engine | ADR-0003 | Proposed | CLOSED — Unity work blocked by institutional approval |
| OTA/boot strategy | ADR-0007, ADR-0008 | Proposed | CLOSED — no OTA changes until Accepted |
| Deployment topology | ADR-0001 | Proposed | CLOSED — no topology changes until Accepted |

---

## Open findings

### Finding 1 — All ADRs at Proposed status

No ADR has reached `Accepted` status with documented architect sign-off evidence. The `Proposed` status is a gate, not a clearance. Implementation PRs referencing these ADRs should not be merged until the ADRs reach `Accepted`.

**Evidence:** Manual review of all ADR files and `docs/adr/README.md` §"ADR Prerequisite Gate Criteria" (lines 161–172). None of the 12 ADRs contain a documented sign-off link (PR approval comment, issue comment, meeting minutes, or signed document).

### Finding 2 — Unity institutional approval not verified (ADR-0003)

ADR-0003 records the engineering decision to use Unity as the Digital Twin engine. The original research proposal named Unity. The formal institutional approval status of this technology change is **PENDING/NOT VERIFIED**.

**Impact:** All Digital Twin work (#11, #12, #33, #34, #67, #68) is blocked by this unverified approval. The Twin execution path should not proceed until formal amendment is confirmed or denied.

**Evidence:** ADR-0003 §"DNTU Research Proposal Amendment" requires formal institutional amendment verification. The ADR currently states "BLOCKED: formal approval pending" per `docs/adr/README.md` §"DNTU Research Proposal Amendment".

### Finding 3 — HIL hardware-evidence protocol ADR missing (#98)

Hardware-in-the-loop verification for uKit Mega integration requires a dedicated ADR defining the HIL evidence protocol, licensing clearance decision record, and hardware-evidence acceptance criteria. No current ADR covers this.

**Evidence:** `docs/adr/README.md` §"Missing-ADR Findings & Recommendations" item 1.

### Finding 4 — Missing ADR for Unity prefab and scene composition boundary (#33)

ADR-0003 covers engine selection but not internal asset architecture (prefab ownership, scene composition rules). A dedicated ADR is required before merging Unity prefab module work.

**Evidence:** `docs/adr/README.md` §"Missing-ADR Findings & Recommendations" item 2.

### Finding 5 — Canonical sequence and snapshot table not implemented (ADR-0005, ADR-0009)

The canonical event envelope defined in ADR-0005 lacks `canonical_sequence` and snapshot table implementation. Telemetry schema mismatch (ADR-0009) is not yet resolved. These gaps block L3/L4 evidence collection.

**Evidence:** `docs/issue-18-research-milestones.md` §"Equipment Readiness Dimension".

---

## ADR lifecycle state machine

```
Proposed
    │
    ├──► Accepted  (architect sign-off documented)
    │         │
    │         ├──► Superseded  (replaced by later ADR)
    │         │
    │         └──► Deprecated  (no longer applicable)
    │
    └──► Rejected  (architect documented reason)
```

**Transition rules:**
- `Proposed` → `Accepted` requires documented architect sign-off (PR approval, issue comment, meeting minutes, or signed document).
- `Proposed` → `Rejected` requires documented architect reason.
- `Accepted` → `Superseded` requires link to replacement ADR.
- `Deprecated` is terminal.

**Current state:** All 12 ADRs are `Proposed`. No transitions have been recorded.

---

## Related documents

- ADR governance: `docs/adr/README.md`
- ADR template: `docs/adr/adr-TEMPLATE.md`
- Lint script: `scripts/check_adrs.py`
- ADR lint workflow: `.github/workflows/adr-lint.yml`
- ADR prerequisite audit: `docs/adr/README.md` §"Issue-to-ADR Prerequisite Mapping & Audit"
