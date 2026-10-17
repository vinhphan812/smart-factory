## Description
[Provide a clear and concise description of what this PR accomplishes.]

## Architecture & ADR Checklist
- [ ] Does this PR introduce or modify architectural components (`docs/architecture/`, `src/`, `iot-gateway/src/`, `esp32-ukit-bridge/`)?
- [ ] If yes, have you created or updated an Architecture Decision Record (ADR) under `docs/adr/` in accordance with Issue #79 / ADR governance?
- [ ] ADR ID(s) associated with this PR: `ADR-XXXX` (or N/A with justification below)
- [ ] If architecture was modified without an ADR, did you apply the `skip-adr` label or include `[skip-adr]` in the commit message?
- [ ] If any Trigger is checked, is the governing ADR status **`Accepted`** (not just `Proposed`)? If `Proposed` only: **DO NOT MERGE** until architect review completes.
- [ ] Evidence of architect acceptance recorded in ADR Evidence section (PR approval comment, issue comment, meeting minutes, or signed document link)
- [ ] For in-flight PRs merged without ADR: follow-up issue filed to backfill ADR referencing original PR as evidence

## Related Issues
Closes #[Issue Number]

## Testing & CI Evidence
- [ ] All tests passed (`pytest`, etc.)
- [ ] `python scripts/check_adrs.py` passed successfully
- [ ] CI build evidence attached/linked
