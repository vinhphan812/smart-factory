# Contribution guide

Read [AGENTS.md](AGENTS.md), [project context](docs/PROJECT_CONTEXT.md) and [test levels](docs/testing-and-acceptance.md). All source is in one Git repository.

## Claim an Issue
Browse [Master Backlog #52](https://github.com/vinhphan812/smart-factory/issues/52), choose an open unassigned task, inspect dependencies, comment `/claim` + username, plan, ETA, intended tests and known blockers. **No automation is installed by this document**; wait for maintainer assignment.

## Submit changes
Branch `feat/issue-N-name`, `fix/issue-N-name`, or `docs/...`. Small PR with issue link, design choice, changed modules, tests and exact commands, evidence, hardware status, security/safety assessment and updated docs/contracts.

**Architecture Decision Records (ADRs) & Lint Gate (Issue #80):**
- Any PR modifying architectural components (`docs/architecture/`, `src/`, `iot-gateway/src/`, `esp32-ukit-bridge/`, `digital-twin/`) MUST be accompanied by an Architecture Decision Record (ADR) under `docs/adr/` following `docs/adr/adr-TEMPLATE.md` and registered in `docs/adr/README.md`.
- Run local check: `python scripts/check_adrs.py` and `pytest scripts/tests/test_check_adrs.py`.
- Exemptions: PRs without architectural impact or emergency bypasses can use the `skip-adr` PR label or include `[skip-adr]` in commit messages. Break-glass override available via `FORCE_BYPASS_ADR=1`.
- Branch protection: `master` requires passing CI checks including ADR lint and code tests before merge.

## Definition of Done
- [ ] Acceptance checklist from Issue addressed
- [ ] Positive + negative and failure tests run and documented
- [ ] Relevant CI green and reviewer approval
- [ ] Interfaces and docs consistent
- [ ] Simulation/bench/HIL evidence accurately identified
- [ ] Unavailable hardware remains BLOCKED and is not reported as PASS
