# Smart Factory — 12-Month Execution Map

> **Source:** Master Issue [#52](https://github.com/vinhphan812/smart-factory/issues/52) | Last updated: 2026-10-16
> **Branch:** `fix/issue-52-backlog-execution-map` (this document)
> **Evidence basis:** live GitHub issue tracker, merged PR log, `docs/adr/README.md`, `docs/integration-matrix.md`, `docs/experiment-baselines.md`

---

## 1. Scope and Purpose

This document is the authoritative 12-month execution map for the Smart Factory project. It supersedes the earlier `docs/ROADMAP.md` proposal with a fully grounded, evidence-backed view derived from the live issue tracker and completed PRs.

All claims are traceable to a specific GitHub issue, PR, ADR, or contract document. No claims are invented. Items marked BLOCKED reference the exact hardware or SDK dependency that prevents progress.

---

## 2. Master Backlog Snapshot (2026-10-16)

### 2.1 Open Issues by Priority

| #  | Priority | Area      | Title                                                                     | Status        | ADR Required | Key Dependency                                      |
|----|----------|-----------|--------------------------------------------------------------------------|---------------|--------------|----------------------------------------------------|
| 98 | P0       | BRIDGE    | HIL verification & licensing clearance for uKit Mega                     | **BLOCKED**   | Yes          | Physical board + legal clearance                   |
| 98 | P0       | BRIDGE    | HIL verification & licensing clearance for uKit Mega                     | BLOCKED       | Yes          | Physical board + legal clearance                   |
| 82 | P1       | ARCH      | Enforce ADR prerequisites across open Issues                              | Open          | No           | ADR governance in place (#79, #80)                |
| 74 | P1       | BRIDGE/OTA| Build OTA release pipeline, staged rollout, recovery test matrix          | Open          | Yes          | #73 client first                                  |
| 73 | P1       | BRIDGE/OTA| Authenticated HTTPS OTA client, maintenance gating, rollback               | Open          | Yes          | ADR-0007/0008                                     |
| 71 | P1       | PHYSICAL  | Parking Lot occupancy and logistics-slot adapter                          | Open          | Yes          | #9 interface, #32 registry, #33 Unity prefabs     |
| 70 | P1       | PHYSICAL  | Dump Truck device adapter, transport state, safety test suite             | Open          | Yes          | #9 interface, #25 abstraction                     |
| 69 | P1       | PHYSICAL  | Bracket structural module inventory, mounting, observability               | Open          | Yes          | #9 interface, #42 capability matrix               |
| 68 | P1       | TWIN      | Calibrate nine-module physical-to-Unity coordinate mapping                | Open          | Yes          | #9, #33, #42; physical modules required           |
| 67 | P1       | TWIN      | Define Unity gateway transport adapter & offline replay fixture pack      | Open          | Yes          | #3, #7, #34; coordinate PR #64                    |
| 60 | P1       | BRIDGE    | Add Mega CI and hardware-in-loop flash wiring guide                      | Open          | Yes          | #56 Mega SDK audit done                           |
| 59 | P1       | BRIDGE    | Safe uKit Explore motor servo sensor adapter & conveyor pilot             | Open          | Yes          | #98 (HIL), ADR-0004/0006                          |
| 58 | P1       | BRIDGE    | Port AMLP v1 endpoint to Arduino Mega HardwareSerial                     | Open          | Yes          | #56 Mega SDK audit (done)                         |
| 52 | P1       | TRACKING  | Master backlog and 12-month execution map (this document)                  | Open          | No           | —                                                 |
| 50 | P2       | TRAINING  | Build guided demo and operational handover for AIBOT visitors              | Open          | No           | #11, #13, #15, #16                                |
| 49 | P2       | TRAINING  | Produce beginner-to-advanced Smart Factory lab exercises                   | Open          | No           | #9, #15, #16                                      |
| 48 | P2       | RESEARCH  | Prepare final scientific/technical report and handover dossier             | Open          | No           | #18, #45, #46                                     |
| 47 | P2       | RESEARCH  | Build research evidence archive and reproducibility package               | Open          | No           | #18, #45, #8                                      |
| 46 | P1       | RESEARCH  | Define reproducible experiments and baseline comparison methods             | Open          | No           | #18, #16, #42                                     |
| 45 | P2       | QA        | Add test coverage, negative-case matrix and PR quality gates              | Open          | No           | #1, #16, #19                                      |
| 44 | P2       | INTEGRATION| Run extended soak and network fault-injection reliability tests           | Open          | No           | #16, #17, #8                                      |
| 43 | P2       | INTEGRATION| Measure end-to-end sync latency, jitter and event loss                    | Open          | Yes          | #7, #8, #12, #16                                  |
| 42 | P1       | INTEGRATION| Create hardware/software capability and simulation fallback matrix         | Open          | Yes          | #4, #9, #13, #16                                 |
| 41 | P1       | INFRA     | Harden MQTT broker authentication, TLS and secret management               | **In PR #106**| Yes          | ADR-0010 (Proposed)                              |
| 40 | P2       | DASHBOARD | Role-based command request console with confirmation gate                  | Open          | Yes          | #15, #5, #27; ADR-0011                           |
| 38 | P2       | EDGE-AI   | Evaluate anomaly model/rule quality on repeatable incidents               | Open          | No           | #14, #8                                          |
| 37 | P1       | EDGE-AI   | Add fail-closed safety decision gate between AI and physical actions       | Open          | Yes          | ADR-0006 Layer 4; #5, #13, #14, #27             |
| 36 | P1       | EDGE-AI   | Implement robot alert notification skills and typed execution feedback     | Open          | Yes          | #13, #14; ADR-0003/0006                          |
| 35 | P2       | TWIN      | Interactive factory playback, camera tours and alarm highlighting          | Open          | Yes          | ADR-0003                                         |
| 34 | P1       | TWIN      | Unity time synchronization, stale data, snapshot resync                   | **In PR #104**| Yes          | ADR-0003; PR #105 pending ADR review              |
| 33 | P1       | TWIN      | Model nine factory modules as reusable Unity prefabs and scene objects     | Open          | Yes          | ADR-0003; missing prefab ADR                     |

> **Note:** The live tracker may have additional or changed issues. Verify at
> https://github.com/vinhphan812/smart-factory/issues?q=is%3Aissue+is%3Aopen+sort%3Aupdated-desc

---

## 3. Completed Deliverables (Merged PRs — Evidence)

The following milestones have been delivered and merged into `master`. Evidence links are to the merged PRs.

| PR  | Date       | Area       | Deliverable                                                     | Evidence Link                                      |
|-----|------------|------------|----------------------------------------------------------------|----------------------------------------------------|
| #21 | 2026-10-12 | FOUNDATION | Root CI, docs, contracts, git hygiene                           | https://github.com/vinhphan812/smart-factory/pull/21 |
| #53 | 2026-10-12 | INTEGRATION| Parity tests, bridge health, command lifecycle, registry, matrix | https://github.com/vinhphan812/smart-factory/pull/53 |
| #54 | 2026-10-12 | INFRA      | Threat-safety model and MQTT security                           | https://github.com/vinhphan812/smart-factory/pull/54 |
| #55 | 2026-10-12 | DOCS       | Project context and contributor guide                           | https://github.com/vinhphan812/smart-factory/pull/55 |
| #61 | 2026-10-12 | DOCS       | uKit Mega official integration playbook for coding agents        | https://github.com/vinhphan812/smart-factory/pull/61 |
| #63 | 2026-10-13 | DOCS       | Unity docs, governance templates, deployment runbooks           | https://github.com/vinhphan812/smart-factory/pull/63 |
| #64 | 2026-10-13 | GATEWAY    | MQTT ingestion gateway (issue #7)                               | https://github.com/vinhphan812/smart-factory/pull/64 |
| #75 | 2026-10-13 | BRIDGE     | ESP32 UART TEL → MQTT telemetry publication (issue #66)         | https://github.com/vinhphan812/smart-factory/pull/75 |
| #77 | 2026-10-13 | INFRA      | P0: move independent IoT Gateway to monorepo root               | https://github.com/vinhphan812/smart-factory/pull/77 |
| #78 | 2026-10-13 | DOCS       | Complete monorepo structure with repository-layout              | https://github.com/vinhphan812/smart-factory/pull/78 |
| #83 | 2026-10-14 | DOCS       | uKit Explore SDK, Mega and licensing evidence audit            | https://github.com/vinhphan812/smart-factory/pull/83 |
| #84 | 2026-10-14 | DOCS       | uKit Explore SDK audit CI verification                          | https://github.com/vinhphan812/smart-factory/pull/84 |
| #87 | 2026-10-14 | BRIDGE     | Bridge telemetry health, heartbeat, diagnostics counters (#29)   | https://github.com/vinhphan812/smart-factory/pull/87 |
| #89 | 2026-10-14 | DOCS/ADR   | Backfill 9 architecture decision records (ADR-0001 to ADR-0009) | https://github.com/vinhphan812/smart-factory/pull/89 |
| #91 | 2026-10-14 | ARCH       | Secure ESP32-S3 OTA architecture and release contract (#72)     | https://github.com/vinhphan812/smart-factory/pull/91 |
| #93 | 2026-10-14 | ARCH       | Make Unity the canonical Smart Factory Digital Twin engine      | https://github.com/vinhphan812/smart-factory/pull/93 |
| #95 | 2026-10-14 | DOCS/ADR   | Establish ADR governance, canonical template, decision log (#79)  | https://github.com/vinhphan812/smart-factory/pull/95 |
| #97 | 2026-10-14 | DOCS       | ADR lint, PR templates and mandatory architecture decision CI gate| https://github.com/vinhphan812/smart-factory/pull/97 |
| #99 | 2026-10-14 | DOCS       | Reproducible experiments and baseline comparison runbook (#46)  | https://github.com/vinhphan812/smart-factory/pull/99 |
| #100| 2026-10-14 | DASHBOARD  | Operator telemetry charts, event timeline, incident acknowledgment | https://github.com/vinhphan812/smart-factory/pull/100|
| #101| 2026-10-14 | INTEGRATION| Hardware/software capability and simulation fallback matrix (#42) | https://github.com/vinhphan812/smart-factory/pull/101|
| #102| 2026-10-15 | DOCS/ADR   | Enforce ADR prerequisite mappings across open Issues (#82)       | https://github.com/vinhphan812/smart-factory/pull/102|

### ADR Index (Source: `docs/adr/README.md`)

All 11 ADRs are currently **Proposed**. None have yet reached **Accepted** status with architect sign-off evidence. This is a hard gate: no implementation PR touching an architectural surface may be merged until the governing ADR reaches `Accepted`.

| ADR  | Title                                                        | Status     | Governing Issues                        |
|------|-------------------------------------------------------------|------------|-----------------------------------------|
| 0001 | Modular Monorepo Structure                                   | Proposed   | #65, #17, #32                          |
| 0002 | Bridge MQTT ↔ AMLP Contract                                 | Proposed   | #7, #28, #29                           |
| 0003 | Digital Twin Engine: Unity Selected                         | Proposed   | #11, #12, #33, #34, #67, #68, #35      |
| 0004 | Mega SDK Boundary: Portable C99 vs UBTEDU                   | Proposed   | #56, #58, #59, #60                     |
| 0005 | Gateway Canonical Event Envelope                             | Proposed   | #7, #8, #31, #39, #43                  |
| 0006 | Local Physical Command Safety                                | Proposed   | #5, #9, #25, #26, #37, #70, #71, #69  |
| 0007 | Signed HTTPS OTA with A/B Rollback                          | Proposed   | #72, #73, #74, #98                     |
| 0008 | Event-driven OtaManager (No Dedicated FreeRTOS Task)       | Proposed   | #73, #74                               |
| 0009 | Telemetry Schema Compatibility                               | Proposed   | #8, #39, #66                           |
| 0010 | MQTT Broker Identity, TLS, and ACL Authorization             | Proposed   | #41                                    |
| 0011 | Dashboard Safety, Telemetry Mode Separation & XSS Hardening  | Proposed   | #40                                    |

---

## 4. In-Progress Work

### PR #104 — Unity Time Sync, Stale Detection, Snapshot Resync (Issue #34)
- **Branch:** `fix/issue-34-unity-time-sync-recovery`
- **Status:** OPEN, under review
- **ADR prerequisite:** ADR-0003 (Proposed — blocking gate)
- **Sibling PR #105** (fixes P1 review findings for #104): `fix/pr104-time-sync-v2`, OPEN

### PR #106 — MQTT Broker ACL Init, TLS Profile, Healthcheck (Issue #41)
- **Branch:** `fix/pr103-mqtt-security-v3`
- **Status:** OPEN, under review
- **ADR prerequisite:** ADR-0010 (Proposed — blocking gate)
- **Source:** PR #103 (CLOSED, test suite replacement)

---

## 5. 12-Month Execution Roadmap

### Milestone Legend

| Symbol | Meaning                                   |
|--------|-------------------------------------------|
| **[DONE]** | Merged to `master`                        |
| **[IN-PR]** | Open PR, awaiting review                  |
| **[CODE]**  | Implementation code required              |
| **[RESEARCH]** | Research / experiment design           |
| **[BLOCKED]** | Waiting on external dependency          |
| **[HIL]**   | Hardware-in-the-loop required             |

### Phase Roadmap

```
MONTH:     1   2   3   4   5   6   7   8   9   10  11  12
           |---|---|---|---|---|---|---|---|---|---|---|---|
PHASE A: Foundation & Core Infrastructure
PHASE B: Safety, OTA, and Telemetry
PHASE C: Digital Twin Implementation
PHASE D: Physical Module Integration (HIL)
PHASE E: Integration, Experiments & Validation
PHASE F: Research, Training & Handover
```

---

### Phase A — Foundation & Core Infrastructure (Months 1–3)

| Item | Type   | Issue | Owner | Dependencies | Evidence |
|------|--------|-------|-------|-------------|----------|
| ADR acceptance across all architectural surfaces | RESEARCH | #82 | — | #79, #80 (done) | PR #102 |
| Hardened MQTT broker: ACL, TLS, secrets | CODE | #41 | — | ADR-0010 Accepted | PR #106 [IN-PR] |
| Unity project scaffold, runtime architecture | CODE | #11 | — | ADR-0003 Accepted | BLOCKED |
| Unity prefab and scene composition boundary ADR | RESEARCH | #33 | — | ADR-0003 Accepted | BLOCKED |
| ADR prerequisite audit for all open issues | RESEARCH | #82 | — | — | PR #102 |
| Monorepo module boundaries and CI scope | CODE | #65 | — | ADR-0001 | [DONE] PR #77, #78 |
| ADR lint CI gate and PR templates | CODE | #80 | — | #79 | [DONE] PR #97 |

**Phase A Gate:** All ADRs must reach `Accepted` status before Phase B/C implementation begins.

---

### Phase B — Safety, OTA, and Telemetry (Months 3–6)

| Item | Type | Issue | Dependencies | Evidence |
|------|------|-------|-------------|----------|
| ESP32 authenticated HTTPS OTA client | CODE | #73 | ADR-0007/0008 Accepted | BLOCKED |
| OTA release pipeline, staged rollout, recovery matrix | CODE | #74 | #73 first | BLOCKED |
| Fail-closed safety decision gate (AI ↔ physical) | CODE | #37 | ADR-0006 Accepted | BLOCKED |
| Robot alert notification skills, typed feedback | CODE | #36 | #13, ADR-0003/0006 | BLOCKED |
| MiniAlpha bounded capability adapter | CODE | #13 | ADR-0006 Accepted | BLOCKED |
| Telemetry charts, event timeline, incident ack | CODE | #39 | ADR-0005/0009 | [DONE] PR #100 |
| UART TEL → MQTT telemetry publication | CODE | #66 | ADR-0005 | [DONE] PR #75 |
| Canonical event envelope and schema | CODE | #7, #8 | ADR-0005 | [DONE] PR #64 |
| End-to-end sync latency measurement | RESEARCH | #43 | ADR-0003/0005, #12 | BLOCKED |

**Note:** #41 (MQTT broker) is actively in PR and can proceed in parallel once ADR-0010 is Accepted. The OTA track (#73 → #74) is sequential and cannot overlap.

---

### Phase C — Digital Twin Implementation (Months 4–8)

| Item | Type | Issue | Dependencies | Evidence |
|------|------|-------|-------------|----------|
| Unity gateway transport adapter + offline replay fixtures | CODE | #67 | ADR-0003, #64 (done) | BLOCKED |
| Unity time sync, stale detection, snapshot resync | CODE | #34 | ADR-0003, #67 | PR #104 [IN-PR] |
| Map live gateway telemetry to deterministic 3D state | CODE | #12 | ADR-0003, #67 | BLOCKED |
| Nine factory modules as Unity prefabs and scene objects | CODE | #33 | ADR-0003, prefab ADR | BLOCKED |
| Physical-to-Unity coordinate calibration (9 modules) | CODE | #68 | #9, #33, #42 | BLOCKED |
| Interactive factory playback, camera tours, alarms | CODE | #35 | ADR-0003, #34 | BLOCKED |
| Role-based command console with confirmation gate | CODE | #40 | ADR-0006/0011, #37 | BLOCKED |

**Parallelism:** #67 (transport adapter) must complete before #34 (time sync) and #12 (telemetry mapping). #33 (prefabs) can run in parallel with #67 but needs the prefab ADR first.

---

### Phase D — Physical Module Integration (Months 6–10)

> **HARD BLOCKER:** All items in Phase D are blocked by Issue #98 (P0). #98 requires physical uKit Explore board availability, electrical validation, and licensing clearance. No HIL work can proceed until #98 is resolved.

| Item | Type | Issue | Dependencies | Evidence |
|------|------|-------|-------------|----------|
| **P0: HIL verification and licensing clearance** | **HIL** | **#98** | Physical board + legal | **BLOCKED** |
| uKit Mega AMLP v1 → Arduino Mega HardwareSerial | CODE | #58 | #56 done, #98 | BLOCKED |
| Mega CI and HIL flash wiring / recovery guide | CODE | #60 | #56 done, #98 | BLOCKED |
| uKit Explore motor/servo/sensor adapter, conveyor pilot | CODE | #59 | #98, ADR-0004/0006 | BLOCKED |
| Nine-module physical interface definition | CODE | #9 | ADR-0006 Accepted, #98 | BLOCKED |
| Dump Truck device adapter, transport state, safety suite | CODE | #70 | #9 | BLOCKED |
| Parking Lot occupancy and logistics-slot adapter | CODE | #71 | #9, #32, #33 | BLOCKED |
| Bracket structural module inventory, mounting | CODE | #69 | #9, #42 | BLOCKED |
| Capability and simulation fallback matrix | CODE | #42 | #4, #9, #13, #16 | Open (PR #101 merged, needs update) |

---

### Phase E — Integration, Experiments & Validation (Months 8–11)

| Item | Type | Issue | Dependencies | Evidence |
|------|------|-------|-------------|----------|
| E2E acceptance suite: device → bridge → twin → AI | CODE | #16 | #34, #37, #67 | BLOCKED |
| Reproducible experiments and baseline methods | RESEARCH | #46 | #42 | [DONE] PR #99 (runbook) |
| Research evidence archive and reproducibility package | RESEARCH | #47 | #8 | Open |
| Extended soak and fault-injection reliability tests | RESEARCH | #44 | #16, #17, #8 | BLOCKED |
| Anomaly model/rule quality evaluation on incidents | RESEARCH | #38 | #14 | BLOCKED |
| PR quality gates, coverage, negative-case matrix | CODE | #45 | #1, #16, #19 | Open |

---

### Phase F — Research, Training & Handover (Months 10–12)

| Item | Type | Issue | Dependencies | Evidence |
|------|------|-------|-------------|----------|
| Final scientific/technical report and handover dossier | RESEARCH | #48 | #18, #45, #46 | Open |
| Guided demo and operational handover for AIBOT visitors | TRAINING | #50 | #11, #13, #15, #16 | BLOCKED |
| Beginner-to-advanced Smart Factory lab exercises | TRAINING | #49 | #9, #15, #16 | BLOCKED |

---

## 6. Dependency Graph Notes

### Critical Path (Longest Chain)

```
ADR Acceptance (all Proposed → Accepted)
  → #67 Unity transport adapter (#34, #12 prerequisites)
    → #34 Unity time sync + stale detection (PR #104 in review)
      → #33 Unity prefabs (needs prefab ADR first)
        → #9 Physical module interfaces
          → #98 HIL clearance (P0 hard blocker)
            → #59 uKit motor/servo adapter
              → #37 Fail-closed safety gate
                → #16 E2E acceptance suite
                  → #48 Final report + #50 Demo
```

### Parallelisable Tracks

| Track A | Track B | Track C |
|---------|---------|---------|
| #41 MQTT broker hardening (in PR #106) | #73 OTA client implementation | #67 Unity transport adapter |
| #82 ADR prerequisite audit (done PR #102) | #82 full ADR enforcement | #33 Unity prefabs (after prefab ADR) |
| #42 capability matrix update | #74 OTA release pipeline (after #73) | #68 physical calibration (after #33, #9) |
| #46 experiment design (done PR #99) | #58 Mega AMLP port (after #56 done) | #35 Unity playback (after #34) |
| | #60 Mega CI + wiring guide | #40 role-based dashboard |

### Hardware / HIL Blockers

All physical hardware integration is gated by #98. The following workstreams are independently executable in simulation/mock until hardware arrives:

- Gateway (done: PR #64)
- Telemetry schema and event envelope (done: PR #75, ADR-0005)
- ADR governance and CI (done: PR #95, #97, #102)
- OTA architecture design (done: ADR-0007/0008)
- Unity time sync in mock/simulation (PR #104)
- MQTT broker hardening (PR #106)
- Capability matrix documentation (PR #101)
- Experiment baseline runbook (PR #99)

---

## 7. Open Questions

| # | Question | Blocking? | Notes |
|---|----------|----------|-------|
| OQ-1 | Can ADR acceptance be expedited? All 11 ADRs are `Proposed`. No implementation PR touching an architectural surface may merge until at least the governing ADR reaches `Accepted`. | Yes — gates #73, #34, #67, #41 | Architect sign-off required with verifiable evidence. |
| OQ-2 | When will the physical uKit Mega board be available for #98 HIL verification? | Yes — gates entire Phase D | All physical module work (#58, #59, #60, #9, #70, #71, #69) is blocked. |
| OQ-3 | Has the Unity engine choice (Unreal → Unity) been formally amended in the DNTU institutional proposal? | Yes — gates #11, #33, #34, #67 | ADR-0003 is marked BLOCKED: formal approval pending per `docs/adr/README.md`. |
| OQ-4 | Is the ADR-0010 (MQTT broker security) PR #106 expected to unblock #41 before ADR acceptance, or must ADR-0010 reach `Accepted` first? | Yes — gates #41 | ADR-0010 is Proposed. Implementation PR #106 is in review; architect should confirm whether Proposed ADRs may gate open PRs or only merged implementations. |
| OQ-5 | Who owns the prefab/scene composition ADR needed before #33 Unity prefabs can be merged? | Yes — gates #33 | Missing-ADR finding from #82 audit. |
| OQ-6 | Is the MiniAlpha robot hardware available or on order? | Partial — gates #13, #36, #37, #38, #50 | Module adapter (#13) can begin with mock; hardware tests need procurement. |
| OQ-7 | What is the target evidence level (L3 bench vs L4 HIL) for the OTA reliability tests in #74? | Partial — affects #74 scope | ADR-0007 mandates HIL validation for physical rollback claims. |
| OQ-8 | Should #42 (capability matrix) be updated to reflect current PR #104/#106 state? | No — low priority | PR #101 merged; matrix needs refresh with latest evidence levels. |
| OQ-9 | Can #58 (Mega AMLP port) proceed now that #56 (Mega SDK audit) is closed? | Partial | #56 CLOSED; #98 HIL gate still applies for physical Mega; C99 reference firmware can proceed. |
| OQ-10 | Is there a defined Unity editor CI license for automated PlayMode/EditMode tests in #45? | Partial — gates Unity CI quality gates | Issue #45 SPEC-45.2 requires pinned Unity version and CI activation. |

---

## 8. Limitations and Evidence Caveats

1. **ADR Acceptance Gap:** All 11 ADRs are `Proposed`. Implementation PRs for architectural surfaces (OTA, Twin, Safety Gate, MQTT Broker) cannot be merged until ADRs reach `Accepted`. This is the single largest delivery risk.
2. **HIL Hard Blocker (#98):** No physical module work can advance without physical hardware. The entire Phase D timeline is contingent on #98 resolution.
3. **Unity Institutional Approval:** The engine migration from Unreal to Unity has not received formal institutional amendment confirmation. ADR-0003 is marked BLOCKED pending this.
4. **Simulation ≠ Physical:** Items marked `[DONE]` in simulation/mock (e.g. OTA client design in ADR-0007) do not constitute physical validation. L3/L4 evidence requires real hardware.
5. **Evidence Level Accuracy:** This document reflects the issue tracker as of 2026-10-16. Verify live status at https://github.com/vinhphan812/smart-factory/issues before making delivery commitments.
6. **PR #104/#105 Ordering:** PR #104 (Unity time sync) is in review. PR #105 (P1 review fixes) depends on #104. Both are blocked on ADR-0003 reaching `Accepted`.

---

## 9. Delivery Summary

This document was produced as part of Kanban task `t_5249453b` on branch `fix/issue-52-backlog-execution-map`.

- **File:** `docs/roadmap/smart-factory-execution-map.md`
- **Source issues surveyed:** all 29 open issues as of 2026-10-16
- **Source PRs:** all 29 merged PRs + 3 open PRs (#104, #105, #106)
- **Source ADRs:** 11 records in `docs/adr/README.md`
- **Source contracts:** `docs/integration-matrix.md`, `docs/experiment-baselines.md`
- **Scope:** master backlog survey, phase decomposition, dependency graph, open questions
- **Exclusions (per task AC):** no PR merge, no issue close
