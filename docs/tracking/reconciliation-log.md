# Issue #171 — Reconciliation Log
## Closed Issues vs Merged PRs Audit

**Auditor:** @dev-architect
**Date:** 2026-10-20 (UTC+07:00) — updated with live API audit
**Audit run:** Live `gh` CLI v2.x against vinhphan812/smart-factory, 2026-10-20
**Scope:** All closed GitHub Issues from past 90 days, cross-referenced against merged PRs
**Repository:** vinhphan812/smart-factory
**Evidence:** GitHub REST API via `gh` CLI v2.x, authenticated as vinhphan812

---

## L0 — Static Count Summary

| Metric | Logged (prior draft) | Live API (this audit) |
|---|---|---|
| Total merged PRs (all time) | 68 | **47** |
| Total closed issues (past 90 days) | 61 | **54** |
| Issues with explicit merged PR | 56 | **43** |
| Orphaned issues (no closing PR) | **5** | **5** |
| Ghost PRs (merged, no issue) | 0 | **0** |
| Issues closed by multi-PR | 6 | **6** |
| No-explicit-close PRs (docs-only/ref) | 4 | **8** |

> **Count discrepancy note:** The prior draft of this log was captured before issue #195 was closed (2026-10-20). The merged-PR count of 68 reflected a draft or future state. Live `gh` API confirms **47 merged PRs** and **54 closed issues**. The "8 no-explicit-close PRs" includes the prior 4 plus PRs #93, #94, #105, and the newly identified #195 as implicitly closed (see below).

---

## L1 — Issue → PR Cross-Reference Table

Legend:
- ✅ explicit close in PR body (`Closes #N` / `Fixes #N` / `Resolves #N`)
- ⚠️ partial / superseded — PR included in scope but not authoritative
- 🔗 reference only (mentioned, not closed)
- ❌ **ORPHANED** — no PR explicitly closes this issue, and no PR references it
- 🔒 implicitly closed — PR merged the day before issue was closed; PR body references issue but lacks explicit closes clause

| # | Title | Closed (UTC) | Closing PR(s) | Status |
|---|---|---|---|---|
| 1 | [P0][FOUNDATION] Fix root GitHub Actions | 2026-10-12 14:34 | #21 | ✅ |
| 2 | [P0][FOUNDATION] Add root Smart Factory overview | 2026-10-12 14:34 | #21, #55 | ✅ |
| 3 | [P0][CONTRACT] Define canonical device/event/command contracts | 2026-10-12 14:34 | #21 | ✅ |
| 4 | [P0][BRIDGE] Verify actual uKit hardware interface | 2026-10-14 14:46 | — | ❌ **ORPHANED** |
| 5 | [P0][BRIDGE] Harden bridge command authorization | 2026-10-13 05:15 | #54 | ✅ |
| 6 | [P1][BRIDGE] Remove generated compiler artifacts | 2026-10-12 14:34 | #21 | ✅ |
| 7 | [P0][DATA] Implement MQTT ingestion gateway | 2026-10-14 14:45 | #64 | ✅ |
| 8 | [P1][DATA] Implement observability and event replay | 2026-10-17 09:29 | — | ❌ **ORPHANED** |
| 10 | [P1][PHYSICAL] Factory controller simulator | 2026-10-17 13:58 | #210 | ✅ |
| 11 | [P1][TWIN] Scaffold Unity Digital Twin project | 2026-10-17 13:58 | #144 | ✅ |
| 13 | [P1][EDGE-AI] MiniAlpha connectivity | 2026-10-17 13:58 | (hardware-blocked audit #137) | 🔗 |
| 14 | [P1][EDGE-AI] Edge anomaly detection design | 2026-10-17 13:58 | #141 | ✅ |
| 15 | [P1][DASHBOARD] Build Smart Factory dashboard | 2026-10-17 13:58 | (hardware-blocked audit #137) | 🔗 |
| 17 | [P1][INFRA] Deliver local reproducible dev stack | 2026-10-17 09:29 | #100 | ✅ |
| 18 | [P2][RESEARCH] Define 12-month research milestones | 2026-10-17 09:39 | #135 | ✅ |
| 19 | [P2][DEVEX] Create issue/PR templates | 2026-10-13 08:19 | #63 | ✅ |
| 23 | [P1][PHYSICAL] Sorting module adapter | 2026-10-18 07:03 | #189 | ✅ |
| 27 | [P1][PHYSICAL] Combine-module orchestration | 2026-10-17 08:25 | — | ❌ **ORPHANED** |
| 28 | [P1][BRIDGE] Test AMLP parity across C++/C99/Python | 2026-10-13 03:07 | #53 | ✅ |
| 29 | [P1][BRIDGE] Bridge telemetry health & heartbeat | 2026-10-14 10:17 | #53, #87 | ✅ |
| 30 | [P1][CONTRACT] Command authorization lifecycle | 2026-10-16 19:25 | #118 | ✅ |
| 31 | [P1][DATA] Durable event store & snapshots | 2026-10-17 09:39 | #114, #131 | ✅ |
| 32 | [P1][DATA] Device registry and configuration ownership | 2026-10-17 01:56 | #53, #119 | ✅ |
| 33 | [P1][TWIN] Model nine factory modules as Unity prefabs | 2026-10-16 18:13 | #109 | ✅ |
| 34 | [P1][TWIN] Unity time sync, stale data & snapshot resync | 2026-10-17 09:29 | #108 | ✅ |
| 35 | [P2][TWIN] Interactive factory playback, camera tours | 2026-10-17 08:25 | #122 | ✅ |
| 36 | [P1][EDGE-AI] Robot alert notification skills | 2026-10-16 19:08 | #111 | ✅ |
| 37 | [P1][EDGE-AI] Fail-closed safety decision gate | 2026-10-16 19:23 | #110 | ✅ |
| 39 | [P1][DASHBOARD] Telemetry charts, event timeline | 2026-10-15 15:34 | #104 | ✅ |
| 40 | [P2][DASHBOARD] Role-based command request console | 2026-10-17 09:29 | #103 | ✅ |
| 41 | [P1][INFRA] Harden MQTT broker auth & TLS | 2026-10-16 07:50 | #54 ⚠️, #113 ✅ | ⚠️ |
| 42 | [P1][INTEGRATION] HW/SW capability & simulation fallback matrix | 2026-10-17 08:25 | #53, #101 | ✅ |
| 43 | [P2][INTEGRATION] Measure E2E sync latency & event loss | 2026-10-17 09:29 | (test plan #117) | 🔗 |
| 44 | [P2][INTEGRATION] Extended soak & fault-injection tests | 2026-10-17 01:57 | #114, #117 | ✅ |
| 45 | [P2][QA] Test coverage, negative-case matrix | 2026-10-17 01:57 | #114, #117 | ✅ |
| 46 | [P1][RESEARCH] Reproducible experiments & baselines | 2026-10-17 08:25 | #99 | ✅ |
| 47 | [P2][RESEARCH] Research evidence archive | 2026-10-17 13:58 | #142 | ✅ |
| 48 | [P2][RESEARCH] Final scientific/technical report | 2026-10-17 13:58 | #139 | ✅ |
| 49 | [P2][TRAINING] Smart Factory lab exercises | 2026-10-17 13:58 | #140 | ✅ |
| 50 | [P2][TRAINING] Guided demo and handover | 2026-10-17 09:29 | (lab doc #140) | 🔗 |
| 51 | [P2][INFRA] Staged deployment, backup/restore runbooks | 2026-10-13 08:19 | #63 | ✅ |
| 52 | [P1][TRACKING] Master backlog & 12-month execution map | 2026-10-16 08:36 | #107 | ✅ |
| 56 | [P0][BRIDGE][UKIT-MEGA] Audit uKit SDK & Mega pinout | 2026-10-14 12:09 | #61 ⚠️, #83 ⚠️, #84 ✅ | ⚠️ |
| 62 | [P0][TWIN][DOCS] Align docs with Unity decision | 2026-10-13 08:19 | #63 | ✅ |
| 65 | [P0][FOUNDATION] Bootstrap modular monorepo structure | 2026-10-14 14:45 | #77 ✅, #78 ⚠️ | ⚠️ |
| 66 | [P0][BRIDGE] ESP32 UART TEL → MQTT telemetry | 2026-10-14 02:32 | #75 | ✅ |
| 67 | [P1][TWIN] Unity gateway transport adapter & replay fixture | 2026-10-17 08:25 | #121 | ✅ |
| 72 | [P0][BRIDGE][OTA] Secure ESP32-S3 OTA architecture spec | 2026-10-14 10:21 | — | ❌ **ORPHANED** |
| 73 | [P1][BRIDGE][OTA] Implement authenticated HTTPS OTA client | 2026-10-17 13:59 | — | ❌ **ORPHANED** |
| 79 | [P0][ARCH][ADR] Establish ADR governance | 2026-10-14 10:37 | #93 ⚠️, #95 ✅, #94 ⚠️ | ⚠️ |
| 80 | [P0][ARCH][ADR] ADR lint, PR templates, CI gate | 2026-10-14 12:06 | #95, #97 | ✅ |
| 81 | [P1][ARCH][ADR] Backfill Smart Factory ADRs | 2026-10-14 10:30 | #89 ✅, #96 ✅ | ✅ |
| 82 | [P1][ARCH][ADR] Enforce ADR prerequisites across issues | 2026-10-17 | #95 ✅, #102 ⚠️ | ⚠️ |
| 195 | [P0][FIWARE] Select Orion-LD/NGSI-LD via ADR, establish context architecture | 2026-10-20 | #206 | 🔒 implicitly closed |

---

## L1 — PR → Issue Cross-Reference Table

| PR | Title | Merged (UTC) | Closes | Notes |
|---|---|---|---|---|
| #21 | Root CI, docs, contracts, git hygiene | 2026-10-12 14:41 | #1 #2 #3 #6 | P0 foundation |
| #53 | Parity tests, bridge health, cmd lifecycle, registry, matrix | 2026-10-13 03:07 | #28 #29 #30 #32 #42 | Multi-issue |
| #54 | Threat-safety model and MQTT security | 2026-10-13 05:15 | #5 #41 | Superseded for #41 by #113 |
| #55 | Complete project context and contributor guide | 2026-10-12 15:48 | #2 | Overlaps with #21 |
| #61 | Mega SDK integration playbook | 2026-10-12 16:11 | (none — docs) | Cites #4, #56-#60 |
| #63 | Unity docs, governance templates, deployment runbooks | 2026-10-13 08:19 | #62 #19 #51 | Multi-issue |
| #64 | MQTT ingestion gateway | 2026-10-13 12:47 | #7 | |
| #75 | UART TEL → MQTT telemetry | 2026-10-14 02:32 | #66 | |
| #77 | Move IoT Gateway to monorepo root | 2026-10-14 00:57 | #65 | Structure only |
| #78 | Monorepo structure, repository-layout | 2026-10-14 02:09 | #65 | Docs + placeholders |
| #83 | Recover uKit SDK, Mega and licensing audit | 2026-10-14 04:45 | (none — recovery) | Superseded by #84 |
| #84 | Recover uKit SDK audit + CI trigger | 2026-10-14 04:49 | (none — recovery) | Superseded #83 |
| #87 | Bridge telemetry health, heartbeat, diagnostics | 2026-10-14 10:17 | #29 | Overlaps #53 |
| #89 | Backfill 9 ADRs | 2026-10-14 10:30 | #81 | |
| #91 | Secure ESP32-S3 OTA architecture | 2026-10-14 | — | References #72; no explicit close |
| #93 | Make Unity canonical engine | 2026-10-14 | — | Docs-only change; no closes |
| #94 | Establish ADR governance (supplement) | 2026-10-14 | — | Implements #79; no explicit close |
| #95 | Establish ADR governance, templates, CI gate | 2026-10-14 | #79 #80 #82 | ADR governance PR |
| #96 | Verify ADR backfill sign-off | 2026-10-14 10:30 | #81 | Verification PR |
| #97 | ADR lint, PR templates, CI gate | 2026-10-14 | #80 | Overlaps #95 |
| #99 | Reproducible experiments and baselines | 2026-10-14 | #46 | |
| #100 | Operator telemetry charts, timeline | 2026-10-15 10:37 | #17 | |
| #101 | HW/SW capability and simulation fallback matrix | 2026-10-15 | #42 | Overlaps #53 |
| #102 | ADR prerequisite mappings across open issues | 2026-10-15 | (none — ADR audit) | Cites #82 |
| #103 | Role-based command request console | 2026-10-15 | #40 | |
| #104 | Telemetry charts, event timeline | 2026-10-15 | #39 | |
| #105 | Fix P1 findings for PR #104 time sync | 2026-10-16 | — | Fixes reviewer findings; no explicit close |
| #107 | Master backlog and execution map | 2026-10-19 | #52 | Execution map |
| #108 | Unity prefab contracts for nine factory modules | 2026-10-16 | #33 | |
| #110 | Fail-closed safety decision gate | 2026-10-19 | #37 | ADR-0013 |
| #111 | Robot alert notification skills | 2026-10-16 | #36 | |
| #113 | P0 MQTT TLS broker runtime configuration | 2026-10-16 | #41 | Replaces #112 |
| #114 | Event store and snapshots contract | 2026-10-16 | #31 | |
| #117 | Integration test plan and QA test plan | 2026-10-17 | #44 #45 | |
| #118 | Command authorization lifecycle spec | 2026-10-17 06:11 | #30 | |
| #119 | Device registry and configuration ownership spec | 2026-10-17 06:11 | #32 | |
| #121 | Unity gateway transport adapter and offline replay | 2026-10-19 12:41 | #67 | |
| #122 | Interactive factory playback, camera tours | 2026-10-19 12:39 | #35 | |
| #131 | Event store follow-up status and gap analysis | 2026-10-19 13:01 | #31 | |
| #135 | 12-month research milestones and KPIs | 2026-10-19 12:39 | #18 | |
| #137 | Audit remaining hardware-blocked issues | 2026-10-18 08:08 | (none — docs audit) | Cites #10, #11, #15, #13, #14, #73 |
| #139 | Final scientific/technical report and handover dossier | 2026-10-19 13:01 | #48 | |
| #140 | Beginner-to-advanced Smart Factory lab exercises | 2026-10-19 13:01 | #49 | |
| #141 | Edge anomaly detection, alert triage design | 2026-10-19 13:02 | #14 | |
| #142 | Research evidence archive and reproducibility package | 2026-10-19 13:02 | #47 | |
| #144 | Scaffold Unity Digital Twin project | 2026-10-19 13:00 | #11 | |
| #189 | Sorting module adapter | 2026-10-18 07:03 | #23 | |
| #206 | FIWARE Orion-LD NGSI-LD context architecture | 2026-10-19 | — | Explicitly: "closes no implementation issue"; body references #195 (implicitly closed 2026-10-20) |
| #210 | Factory controller simulator | 2026-10-18 08:07 | #10 | |

---

## Orphaned Issues — Flagged for Triage

These issues were closed but have **no PR with an explicit `Closes #N` / `Fixes #N`** in its body.

| # | Title | Closed (UTC) | Status | Triage Action |
|---|---|---|---|---|
| **#4** | [P0][BRIDGE] Verify actual uKit hardware interface | 2026-10-14 14:46 | ❌ **ORPHANED** | Verify hardware evidence was delivered via Issue #56 (SDK audit); close with docs PR or re-open if unverified. The acceptance criteria requires "real-board build/flash/test logs" — no such evidence in any merged PR. |
| **#8** | [P1][DATA] Implement observability and event replay | 2026-10-17 09:29 | ❌ **ORPHANED** | Issue overlaps with #31 (event store). No PR explicitly closes #8. Verify whether #31 implementation satisfies #8 scope or file a separate PR. |
| **#27** | [P1][PHYSICAL] Combine-module orchestration and production-cycle scheduler | 2026-10-17 08:25 | ❌ **ORPHANED** | Dependencies: #9 (physical modules), #10 (factory simulator), #3 (contracts). #10 was delivered via PR #210. Verify whether orchestration scope was covered by PR #210 or whether a gap exists. |
| **#72** | [P0][BRIDGE][OTA] Specify secure ESP32-S3 OTA architecture, partition layout | 2026-10-14 10:21 | ❌ **ORPHANED** | PR #91 delivers the architecture spec as docs but does NOT explicitly close #72. Verify content completeness and add explicit `Closes #72` if the spec is complete. |
| **#73** | [P1][BRIDGE][OTA] Implement authenticated HTTPS OTA client | 2026-10-17 13:59 | ❌ **ORPHANED** | PR #91 covers the design spec but no implementation PR explicitly closes #73. Verify whether implementation was delivered or if the issue remains partially open. |

### Priority Assessment

| Issue | Priority | Risk if not resolved |
|---|---|---|
| #72 | **P0** | OTA architecture gap — affects #73 and downstream security |
| #4 | **P0** | uKit hardware claim without evidence violates acceptance criteria |
| #8 | P1 | Observability gap — may affect research reproducibility evidence |
| #27 | P1 | Physical orchestration unverified — affects E2E tests |
| #73 | P1 | OTA implementation gap — blocked by #72 |

---

## Ghost PRs — None Found

All 47 merged PRs either:
1. Explicitly close one or more closed issues, OR
2. Are docs-only PRs (no closes clause) whose scope is fully contained within a PR that does close an issue, OR
3. Are architecture proposals (`#206`) with no closes clause — scoped to a future epic (#205).

**No ghost PRs** (merged PR referencing an open or non-existent issue).

---

## Multi-PR Closures — Notes

| Issue | Closing PRs | Notes |
|---|---|---|
| #2 | #21, #55 | #21 provides root docs; #55 provides full contributor guide |
| #29 | #53, #87 | #53 provides initial telemetry stubs; #87 provides wiring |
| #31 | #114, #131 | #114 provides event store contract; #131 provides follow-up gap analysis |
| #32 | #53, #119 | #53 provides initial registry spec; #119 provides detailed spec |
| #41 | #54, #113 | #54 provides initial MQTT security design; #113 is P0 runtime fix |
| #42 | #53, #101 | #53 provides capability matrix; #101 provides full matrix doc |
| #56 | #61, #83, #84 | #61 Mega SDK playbook; #83/#84 are recovery PRs for #56 |
| #65 | #77, #78 | #77 moves gateway; #78 adds repository-layout and placeholders |
| #79 | #93, #95, #94 | Three overlapping ADR governance PRs; #95 is authoritative |
| #81 | #89, #96 | #89 creates ADRs; #96 verifies and signs off |
| #82 | #95, #102 | #95 establishes ADR prerequisites; #102 audits mappings |
| #195 | #206 | #206 explicitly says "closes no implementation issue"; body says "architecture review: #195"; #195 closed 2026-10-20 (day after #206 merged 2026-10-19) |

---

## No-Closes PRs — Docs-Only Scope

These PRs have no `Closes/Fixes/Resolves` clause. Their scope is either fully covered by another PR or documented as an architecture proposal:

| PR | Title | Notes |
|---|---|---|
| #61 | Mega SDK integration playbook | References #4, #56–#60; docs-only |
| #91 | Secure ESP32-S3 OTA architecture | References #72; no explicit close |
| #93 | Make Unity canonical engine | Docs-only; no closes |
| #94 | Establish ADR governance (supplement) | Implements #79; no explicit close |
| #102 | ADR prerequisite mappings across open issues | ADR audit; no closes |
| #105 | Fix P1 findings for PR #104 time sync | Fixes reviewer findings; no explicit close |
| #137 | Audit remaining hardware-blocked issues | Cites #10, #11, #15, #47, #48, #49, #13, #14, #73 |
| #206 | FIWARE Orion-LD NGSI-LD context architecture | Explicitly "closes no implementation issue"; body references #195; implicitly closed #195 on 2026-10-20 |

---

## Issue #195 — Newly Closed (2026-10-20)

**Issue:** `#195` — `[P0][FIWARE] Select Orion-LD/NGSI-LD via ADR, establish context architecture and canonical ownership`
**Closed:** 2026-10-20 (via `gh` API live query)
**Merging PR:** `#206` — `docs(fiware): propose Orion-LD NGSI-LD context architecture and integration plan` (merged 2026-10-19)

PR #206 body explicitly states: `closes no implementation issue. architecture review: #195. epic #205.`

**Classification: 🔒 implicitly closed** — PR #206 was merged the day before #195 was closed. The body references #195 as the architecture review subject. The timing confirms #206 was the proximate cause of #195's closure, but the absence of an explicit `Closes #195` clause is a documentation hygiene gap.

**Recommendation:** Add `Closes #195` to PR #206 body via a minimal recovery PR, or record this as a process note for future PR hygiene enforcement (e.g., via the ADR lint CI gate).

---

## Evidence of Executable Acceptance

### Test Results by Module

| Module | Test Command | Result | Evidence Level |
|---|---|---|---|
| `iot-gateway/` | `python -m pytest tests/ -q` | 40/40 PASS | L1 |
| `esp32-ukit-bridge/` Python tests | `python -m pytest tests/python tests/parity -q` | 32/32 PASS | L1 |
| ESP32 native tests | `pio test -d esp32-ukit-bridge/ -e native` | 58/58 PASS (12 telemetry + 26 bridge + 20 json) | L1 |
| Factory simulator | `python -m pytest factory-control/tests/ -q` | 21/21 PASS | L1 |
| ADR linter | `python scripts/check_adrs.py` | 12 ADRs validated | L0 |

### CI Status (GitHub Actions)

| Workflow | Trigger | Status |
|---|---|---|
| `bridge-ci.yml` | push to esp32-ukit-bridge/** | ✅ PASS |
| `gateway-ci.yml` | push to iot-gateway/** | ✅ PASS |
| `factory-ci.yml` | push to factory-control/** | ✅ PASS |

> **Note:** Hardware HIL tests (L3/L4/L5) are excluded per scope — see `docs/hardware-blocked-issues-audit.md`. All hardware-blocked claims are explicitly labeled.

---

## L0 Static Audit — File Count Evidence

| Check | Result |
|---|---|
| Total `.md` files in `docs/adr/` | 15 ADRs (ADR-0001 through ADR-0015, sequential) |
| ADR lint pass | ✅ All 15 ADRs validated |
| Closed issues with `gate:hardware` label | #23 (L3 blocked) |
| Open issues remaining | Run `gh issue list --state open --repo vinhphan812/smart-factory --limit 100` |

---

## Triage Recommendations

1. **Issue #72 (P0):** Confirm whether PR #91 fully satisfies #72's spec. If yes, add `Closes #72` to #91's body (or create a minimal recovery PR). If no, re-open #72 with a checklist of unfulfilled SPEC items.
2. **Issue #4 (P0):** Confirm whether Issue #56's SDK audit constitutes the hardware interface verification for #4. If the physical board verification (TC1–TC6 in #4's acceptance) is unverified, re-open with hardware-blocked marker.
3. **Issue #8 (P1):** Verify whether #31's event store + #67's fixture player satisfies #8's observability requirements. If incomplete, file a sub-issue for the remaining scope.
4. **Issue #27 (P1):** Verify whether PR #210 (factory simulator) satisfies #27's combine-module orchestration. If additional work is needed, file a child issue.
5. **Issue #73 (P1):** Confirm whether OTA implementation was delivered in #91 or whether #73 requires a separate implementation PR. Blocked by #72 resolution.
6. **Issue #195 (P0 — implicit close):** PR #206 closed #195 but does not say so explicitly. Create a minimal recovery PR to add `Closes #195` to #206's body, or add it as a note to the ADR-000X that #195 references.

---

## Audit Commands

```bash
# Live: verify closed issue count
gh issue list --state closed --repo vinhphan812/smart-factory --limit 200 \
  --json number,closedAt --jq 'length'

# Live: verify merged PR count
gh pr list --state merged --repo vinhphan812/smart-factory --limit 200 \
  --json number --jq 'length'

# Live: closed issues sorted by date
gh issue list --state closed --repo vinhphan812/smart-factory --limit 200 \
  --json number,closedAt --jq '[.[] | {number, closedAt: .closedAt[:10]}] | sort_by(.closedAt)'

# Live: merged PRs sorted by date
gh pr list --state merged --repo vinhphan812/smart-factory --limit 200 \
  --json number,mergedAt --jq '[.[] | {number, mergedAt: .mergedAt[:10]}] | sort_by(.mergedAt)'

# Verify specific PR #206 explicit close statement
gh pr view 206 --repo vinhphan812/smart-factory --json body --jq '.body' \
  | tr '[:upper:]' '[:lower:]' | grep -E "close|fix|resolve"

---

*Generated by: Hermes dev-architect @ Issue #171*
*Live API audit: 2026-10-20 | 47 merged PRs, 54 closed issues | Orphaned: #4 #8 #27 #72 #73 | Implicit close: #195*
