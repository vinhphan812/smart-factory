# Contribution guide

Read [AGENTS.md](AGENTS.md), [project context](docs/PROJECT_CONTEXT.md) and [test levels](docs/testing-and-acceptance.md). All source is in one Git repository.

## Claim an Issue
Browse [Master Backlog #52](https://github.com/vinhphan812/smart-factory/issues/52), choose an open unassigned task, inspect dependencies, comment `/claim` + username, plan, ETA, intended tests and known blockers. **No automation is installed by this document**; wait for maintainer assignment.

## Submit changes
Branch `feat/issue-N-name`, `fix/issue-N-name`, or `docs/...`. Small PR with issue link, design choice, changed modules, tests and exact commands, evidence, hardware status, security/safety assessment and updated docs/contracts. Never commit credentials, unlicensed SDK sources, private data, generated build caches or very large Unreal binaries without approved Git LFS.

## Definition of Done
- [ ] Acceptance checklist from Issue addressed
- [ ] Positive + negative and failure tests run and documented
- [ ] Relevant CI green and reviewer approval
- [ ] Interfaces and docs consistent
- [ ] Simulation/bench/HIL evidence accurately identified
- [ ] Unavailable hardware remains BLOCKED and is not reported as PASS
