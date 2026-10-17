# ADR-0013: UBTECH Yanshee as Smart Factory Edge AI Robot

**Status:** Proposed
**Date:** 2026-10-17
**Deciders:** Project leadership (authoritative); dev-architect review (t_b76af23e)
**Related issues:** #158, #159, #160, #161, #13 (superseded), #145 (blocked)
**Supersedes:** MiniAlpha references in ADR-0004, ADR-0006, overview.md, components.md, PROJECT_CONTEXT.md
**ADR IDs already used in this repo:** 0001-0012 (0010=MQTT broker security, 0011=Dashboard safety, 0012=Unity prefab contracts)

---

## Context

The Smart Factory Edge AI Robot module (`edge-ai-robot/`) was originally designed around **MiniAlpha** as the target physical platform (Issue #13, PR #145). As of 2026-10-17, project leadership has made an authoritative engineering decision to replace MiniAlpha with **UBTECH Yanshee** as the sole planned Edge AI robot.

This decision has the following implications:
- PR #162 (docs: adopt Yanshee across 13 engineering docs) is open but blocked with CHANGES REQUESTED
- PR #145 (MiniAlpha adapter + mock + tests) is open and must NOT be merged as-is
- Issue #13 is closed but explicitly superseded by the Yanshee migration (historical record preserved)
- Several open Issues (#158, #159, #160, #161, #178) track the Yanshee-specific implementation work
- The ADR backfill (ADR governance, #79-#82) must record this as a formal ADR

**Current state of documentation after PR #162 (HEAD 5aa2215):**
PR #162 claims to replace MiniAlpha across 13 docs, but the reviewer correctly identified that `docs/PROJECT_CONTEXT.md` still contains an incorrect provenance claim ("original proposal named Unity" instead of the verified "Unreal Engine"). All other docs correctly reference Yanshee post-merge. The PR itself is CHANGES REQUESTED and not yet merged.

**Remaining stale MiniAlpha references (confirmed by grep, 2026-10-17):**

| File | Stale MiniAlpha reference | Status |
|---|---|---|
| `docs/PROJECT_CONTEXT.md` | S3 AI Edge Robot: **MiniAlpha** | Must change to Yanshee |
| `docs/architecture/overview.md` | mermaid node `MiniAlpha notification / bounded skills` | Must change to Yanshee |
| `docs/architecture/overview.md` | "current engineering target uses **Unity 3D** and **MiniAlpha**" | Must change to Yanshee |
| `docs/architecture/overview.md` | `~~ADR-004~~: MiniAlpha API → see Issue #13` | Update to point to #160 |
| `docs/architecture/components.md` | `edge-ai-robot/ (planned) \| MiniAlpha and Edge AI` | Must change to Yanshee |
| `docs/architecture/repository-layout.md` | `edge-ai-robot/ \| MiniAlpha adapter` | Must change to Yanshee |
| `docs/experiment-baselines.md` | E2E (L5) table references MiniAlpha | Must change to Yanshee |
| `docs/hardware-readiness.md` | MiniAlpha Robot row in hardware table | Must change to Yanshee |
| `docs/integration-matrix.md` | L5 row and MiniAlpha-specific integration row | Must change to Yanshee |
| `docs/integration-matrix.md` | Section 4: MiniAlpha Robot Integration | Must change to Yanshee |
| `docs/issue-44-integration-test-plan.md` | E09, L5 row references MiniAlpha | Must change to Yanshee |
| `docs/issue-45-qa-test-plan.md` | Unity and MiniAlpha integration | Must change to Yanshee |
| `docs/research-and-training.md` | "MiniAlpha AI Edge response" | Must change to Yanshee |
| `docs/risks.md` | MiniAlpha hardware/software API unknown row | Update to Yanshee (or combine with existing Yanshee risk) |
| `README.md` | "AI Edge MiniAlpha Robot" | Must change to Yanshee |
| `edge-ai-robot/README.md` | "MiniAlpha robot adapter" | Must change to Yanshee |
| `edge-ai-robot/` | Python adapter code (`MiniAlphaAdapterBase`, `MockMiniAlphaAdapter`) | Must be renamed to Yanshee equivalents |

---

## Decision

**UBTECH Yanshee is designated as the Smart Factory Edge AI Robot platform.** MiniAlpha is removed from the active implementation scope. The decision is:

1. **Yanshee wins** over MiniAlpha: Yanshee is the sole planned Edge AI robot. The original research proposal used the term "AI Edge Robot" without naming a specific vendor; the engineering selection of Yanshee is authoritative.

2. **MiniAlpha is historical**: Its PR (#145) and Issues (#13, #36) are closed/archived but preserved as audit records. They do not constitute valid Yanshee implementation evidence.

3. **Yanshee is architecturally distinct from uKit Mega**: Yanshee is a standalone AI/robotics platform. Its YanAPI REST/Python3 SDK must not be routed through `esp32-ukit-bridge` or conflated with the UKIT Mega factory controller. Yanshee connects independently to the MQTT broker or gateway.

4. **Evidence levels are mandatory**: No claims of live Yanshee HIL, SDK authentication, or physical connectivity until Issues #159 (SDK audit), #160 (typed adapter), and #161 (E2E/HIL acceptance) are completed with verifiable evidence.

5. **PR #145 is blocked and must not merge**: The MiniAlpha adapter must be replaced with a Yanshee equivalent. The bounded skill contract (ADR-0006) is valid; only the robot-specific implementation changes.

---

## Consequences

### Immediate actions required

| Action | Owner | Blocking |
|---|---|---|
| Fix PROJECT_CONTEXT.md typo (Unity → Unreal) | PR #162 author | Required for PR #162 merge |
| Merge PR #162 with corrected docs | Reviewer | Unblocks ADR-0010 ratification |
| Close PR #145 (MiniAlpha adapter) with explanation | Maintainer | Required to prevent stale merge |
| Create #160 PR for Yanshee adapter | EDGE-AI developer | After #159 SDK audit |
| Write ADR-0010 ratification evidence in docs/adr/ | dev-architect | This document |

### Module changes (edge-ai-robot/)

The `edge-ai-robot/` module needs:
- Rename `MiniAlphaAdapterBase` → `YansheeAdapterBase`
- Rename `MockMiniAlphaAdapter` → `MockYansheeAdapter`
- Update inbound/outbound contract imports
- Replace MiniAlpha-specific API calls with YanAPI equivalents (pending #159)
- Update skill definitions from MiniAlpha to Yanshee capability matrix
- Rename test files: `test_adapter.py` (verify Yanshee adapter behavior)
- Update `README.md` to reflect Yanshee target

### Skill contract (robot-independent, ADR-0006 compliant)

The bounded skill architecture is robot-agnostic and valid for Yanshee:
- `SkillDefinition`, `SkillCategory`, `SkillStatus`, `get_allowed_skills_for_ai()` — unchanged
- `BOUNDED_SKILLS` registry — update with Yanshee-specific permitted actions
- Physical action skills (move, gripper, E-stop) remain **fail-closed** for AI
- Notification/status/acknowledge skills are the AI-allowed surface

### ADR updates required

| ADR | Change needed |
|---|---|
| ADR-0004 | Update Mega SDK boundary doc note; no change to decision |
| ADR-0006 | Confirm skill contract is robot-independent (Yanshee-valid) |
| Overview.md ADR table | Replace `~~ADR-004~~: MiniAlpha` with `ADR-0010: Yanshee` |
| ADR README | Add ADR-0010 to registry |

### Risk: Yanshee-specific unknowns

| Risk | Mitigation | Issue |
|---|---|---|
| YanAPI SDK version/auth unknown | Hardware audit required before adapter dev | #159 |
| Yanshee battery/network failure modes | Mock must cover offline/low-battery states | #160 |
| Yanshee physical E-stop must not be AI-overridable | ADR-0006 fail-closed enforcement | #37 |
| Yanshee SDK deprecated Raspi variant vs. current YanAPI | #159 must validate actual SDK | #159 |
| Yanshee not conflated with uKit Mega | Separate module, separate network path | #160 |

---

## Options considered

### Option A: Adopt Yanshee (chosen)
- Yanshee is the authoritative engineering selection
- Full migration path defined (Issues #158-#161)
- Bounded skill contract (ADR-0006) reusable for Yanshee
- Risk: SDK/HIL unknowns must be resolved before live deployment

### Option B: Retain MiniAlpha
- MiniAlpha adapter code exists in PR #145
- **Rejected**: Project leadership has superseded MiniAlpha; no active procurement path
- Risk: implementing a robot with no confirmed hardware availability

### Option C: Robot-agnostic abstraction
- Define `RobotAdapterBase` interface, implement for both MiniAlpha and Yanshee
- **Rejected for now**: The project has no live hardware for either robot; premature abstraction before SDK reality is known. Revisit after #159/#160 provide concrete Yanshee API surface.

---

## Verification checklist

- [ ] `docs/PROJECT_CONTEXT.md` S3 line updated from MiniAlpha to Yanshee
- [ ] `docs/architecture/overview.md` mermaid and text updated
- [ ] `docs/architecture/components.md` edge-ai-robot row updated
- [ ] `docs/architecture/repository-layout.md` edge-ai-robot row updated
- [ ] `docs/experiment-baselines.md` E2E row updated
- [ ] `docs/hardware-readiness.md` robot row updated
- [ ] `docs/integration-matrix.md` L5 and MiniAlpha rows updated
- [ ] `docs/issue-44-integration-test-plan.md` MiniAlpha references updated
- [ ] `docs/issue-45-qa-test-plan.md` MiniAlpha references updated
- [ ] `docs/research-and-training.md` MiniAlpha reference updated
- [ ] `docs/risks.md` MiniAlpha risk row updated or merged with Yanshee risk
- [ ] `README.md` AI Edge Robot line updated
- [ ] `edge-ai-robot/README.md` adapter description updated
- [ ] `edge-ai-robot/` Python adapter renamed (MiniAlpha → Yanshee equivalents)
- [ ] PR #145 closed with explanation, not merged
- [ ] ADR-0010 ratification evidence captured (this document)
