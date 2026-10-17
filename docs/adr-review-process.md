# ADR Review Process — Governance Runbook

**Owner:** Issue #79 (ADR governance) | **Applies to:** All ADRs under `docs/adr/`

---

## Author Workflow

1. **Identify the ADR Trigger** — does the work fall under any of the 7 ADR Trigger rules
   (`docs/adr/README.md` lines 37–48)?
2. **Copy the template** — `docs/adr/adr-TEMPLATE.md` → `docs/adr/adr-XXXX-short-decision.md`
3. **Fill all sections** — no `[...]` placeholders in Decision or Consequences. Write actual
   sentences in active voice ("We will...", "We have chosen...").
4. **Add to the index** — insert entry in `docs/adr/README.md` index table with status `Proposed`
   and date.
5. **Link from the triggering issue** — add `Related issues: #N` to ADR metadata and comment
   on the GitHub issue linking to the ADR file.
6. **Open PR** targeting `master`; label with `adr`.
7. **Request architect review** (@vinhphan812).
8. **Address review comments**; re-request review.

---

## Architect Review Checklist

For every ADR PR, verify all of the following before approving:

- [ ] All required sections present and non-empty:
      Context, Decision, Consequences, Alternatives considered, Evidence
- [ ] Decision rationale is stated in active voice (not passive or placeholder)
- [ ] At least one alternative considered with explicit trade-offs vs. the chosen option
- [ ] Evidence section contains verifiable links (issue links, PR links, meeting notes,
      documents). "Will be added later" is not acceptable evidence.
- [ ] Status transition is valid: `Proposed` → `Accepted` OR `Proposed` → `Rejected`
- [ ] If the DNTU institutional proposal is involved: amendment status is explicitly stated
      (`BLOCKED: formal approval pending` or confirmed approval with evidence link)
- [ ] ADR ID is not already assigned (check `docs/adr/README.md` index)
- [ ] Filename ID and heading ID match
- [ ] README index is updated with this ADR entry
- [ ] ADR is linked from the triggering GitHub issue

---

## Acceptance Evidence Requirements

An ADR may only transition from `Proposed` to `Accepted` when the Evidence section contains
**at least one** of:

| Evidence type | Example |
|---------------|---------|
| PR approval comment | Architect approves in PR review thread |
| Issue comment | Architect signs off with rationale on the triggering issue |
| Meeting minutes | Dated doc with decision record, attendees, and architect signature |
| Signed document | Scanned PDF with architect name, date, and explicit approval |

**"Implemented" ≠ "Accepted".** Code merged against a `Proposed` ADR does not constitute
acceptance. The ADR must reach `Accepted` status with a recorded evidence link before the
architectural surface may be considered cleared for implementation.

---

## Rejection Process

1. Architect closes the ADR PR with documented reason (a comment explaining the rejection
   rationale is required — not just closing the PR silently).
2. Architect comments on the triggering GitHub issue explaining why the decision was
   rejected.
3. The ADR file is **not merged** into `docs/adr/`.
4. Author may revise and reopen if new evidence or rationale becomes available.

---

## Post-Acceptance Maintenance

| Situation | Action |
|-----------|--------|
| ADR is superseded by a later decision | Update status to `Superseded`, add link to replacement ADR in Evidence section |
| ADR is no longer applicable | Update status to `Deprecated` with architect sign-off comment |
| ADR needs clarification | Open a follow-up ADR; do not rewrite the original decision |
| Architectural surface changes significantly | Open a new ADR; do not revise the old one |

**Never delete old ADRs.** Preserve all decision records for audit trail, even superseded
or deprecated ones.

---

## Escalation: Proposed ADR Referenced in Implementation PR

If an implementation PR references a `Proposed` ADR (not yet `Accepted`):

1. **Reviewer must not approve.** Request architect review of the ADR first.
2. **Architect accelerates review** or explicitly rejects the implementation PR with
   justification.
3. **Do not merge** the implementation PR until the ADR reaches `Accepted`.

The CI `adr-lint.yml` workflow does not enforce the `Proposed`/`Accepted` distinction —
that is a human judgment call enforced at PR review. The linter only checks that *some*
ADR is present when architectural paths are modified.

---

## Evidence Dashboard

See `docs/issue-82-adr-prerequisites.md` (from PR #102) for the live ADR evidence dashboard tracking
all ADRs, their gate status, and open issues they govern.

---

*Last reviewed: 2026-10-17 | Owner: @vinhphan812*
