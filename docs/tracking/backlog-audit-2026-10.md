# Smart Factory — Backlog Audit
**Date:** 2026-10-20
**Auditor:** dev-architect (Kanban t_b5a06c53)
**Scope:** All open issues as of 2026-10-20, GitHub API query
**Reference:** Issues #171 (reconciliation) and #172 (integration queue)

---

## 1. Executive Summary

| Metric | Count |
|--------|-------|
| Total issues (open + closed) | ~128 |
| **Open issues** | **75** |
| Closed issues | 53 |
| Open PRs | 2 (PR #211 dashboard bootstrap, PR #145 MiniAlpha adapter) |
| Merged PRs (cumulative) | 47 |
| ADRs in `docs/adr/` | 13 (ADR-0001–ADR-0013, plus template) |
| Open `gate:hardware` issues | 16 |
| Wave 0 unblocked issues | 6 |
| Wave 0 blocked by hardware | 2 |

**Overall state:** The wave:0-foundation layer is partially complete (ADRs done, monorepo bootstrapped, bridge telemetry delivered). The critical gap is the lack of hardware verification — Issue #98 (HIL verification & licensing) and #173 (ESP32–uKit pinout) gate the entire physical layer. The FIWARE epic (#195–#205) is newly active and its wave:0 decisions must land before wave:2-gateway-core work begins. No wave:0-foundation issue is completely stranded; the two hardware-gated ones (#173, #98) have concrete dependency paths through #56/#57/#58.

---

## 2. Issue Audit Table

### Format: `# | Wave | Priority | Area | Gate | Action`

Legend: `[W]` = worktree exists, `[PR]` = open PR, `[C]` = closed, `[E]` = epic child, `[BLOCKED]` = hardware/software dependency not met, `[READY]` = unblocked and ready for action, `[IN PROGRESS]` = assigned and active.

---

#### Wave 0 — Foundation

| # | Priority | Area | Gate | Action | Notes |
|---|----------|------|------|--------|-------|
| 188 | P0 | tracking | — | **THIS EPIC** | Backlog audit delivery |
| 195 | P0 | fiware | — | **[READY]** Start FIWARE EPIC | ADR + context architecture before wave:2 FIWARE work |
| 163 | P0 | gateway | — | **[READY]** Define nine canonical flows | Dependency for all gateway modules; review existing docs/contracts-and-data.md first |
| 171 | P0 | foundation | — | **[READY]** Reconcile closed issues vs merged PRs | Manual audit; verify each closed issue has a merged PR |
| 172 | P0 | foundation | — | **[READY]** Create release integration queue | Depends on #171 |
| 173 | P0 | hardware | **gate:hardware** | **[BLOCKED]** ESP32–uKit pinout & electrical safety | Blocked by #56 (SDK audit done), #57 (Mega firmware target), #58 (AMLP port); all wave:1 |
| 98 | P0 | hardware | **gate:hardware** | **[BLOCKED]** HIL verification & licensing | Requires #57+#58+#59; hardware procurement |

**Wave 0 action items (unblocked):** #195 → #163 → #171 → #172 (sequential: FIWARE EPIC decision, gateway flows, reconciliation, integration queue). #173 and #98 are correctly blocked on wave:1 deliverables.

---

#### Wave 1 — Device Link

| # | Priority | Area | Gate | Action | Notes |
|---|----------|------|------|--------|-------|
| 192 | P0 | bridge | — | **[READY]** ESP32 secure bootstrap & enrollment | Requires #57+#58 done first |
| 191 | P0 | bridge | **gate:hardware** | **[BLOCKED]** Mega SDK telemetry (motors, servos, sensors) | Requires #57 (Mega firmware target); telemetry interface spec needed first |
| 57 | P0 | bridge | **gate:hardware** | **[BLOCKED]** Create Arduino Mega firmware target + official SDK integration | Depends on #56 (SDK audit done ✓) |
| 58 | P0 | bridge | **gate:hardware** | **[BLOCKED]** Port AMLP v1 endpoint to Arduino Mega HardwareSerial | Depends on #57 |
| 59 | P0 | bridge | **gate:hardware** | **[BLOCKED]** Safe uKit Explore motor/servo/sensor adapter | Depends on #58 |
| 9 | P1 | physical | — | **[READY]** Define 9-module physical factory interface & end-to-end sequence | Design doc; no hardware needed yet |
| 174 | P1 | physical | — | **[READY]** Design factory module capability matrix, typed IO mapping | Depends on #9 |

**Wave 1 action items:** #9 and #174 are design-only, unblocked now. #192 can start once #57+#58 land (or run in parallel on the simulator path). #57→#58→#59→#191→#192 is the hardware-critical chain.

---

#### Wave 2 — Gateway Core

| # | Priority | Area | Gate | Action | Notes |
|---|----------|------|------|--------|-------|
| 198 | P0 | fiware | — | **[READY after #195]** Gateway → Orion-LD context adapter | Depends on #195 (FIWARE entity graph defined) + #197 |
| 197 | P0 | fiware | — | **[READY after #195]** Define NGSI-LD entity graph & registry | Depends on #195; parallel with #196 |
| 196 | P0 | fiware | — | **[READY after #195]** Deploy Orion-LD + MongoDB + JSON-LD context service | Depends on #195; infra work |
| 194 | P0 | gateway | — | **[READY after #163]** Gateway northbound fanout & downstream contracts | Depends on #163 |
| 169 | P0 | gateway | — | **[READY]** Device registry, provisioning & OTA control | Core gateway work; no external deps |
| 166 | P0 | gateway | — | **[READY]** Resolve ESP32 telemetry schema mismatch (ADR-0009) | ADR-0009 exists; implementation pending; affects #165 |
| 165 | P0 | gateway | — | **[READY]** Harden event ingestion durability, ordering, overflow, dead-letter | Depends on #166 (schema must be stable) |
| 164 | P1 | gateway | — | **[READY]** Server-authorized command orchestrator & durable state machine | P1; #165 precedent |
| 167 | P1 | gateway | — | **[READY]** Gateway HTTP/WebSocket service authentication & scoped access | Auth work |
| 98 | P0 | hardware | **gate:hardware** | **[BLOCKED]** HIL verification | See wave:0 |
| 60 | P1 | bridge | **gate:hardware** | **[BLOCKED]** Mega CI + HIL flash wiring | Depends on #57+#58 |

**Wave 2 action items:** All FIWARE issues (#196–198, #200, #201, #202, #203) are gated on #195. All gateway-core P0 issues (#169, #166, #165, #194) are unblocked now. #164 and #167 are P1, ready.

---

#### Wave 3 — Applications

| # | Priority | Area | Gate | Action | Notes |
|---|----------|------|------|--------|-------|
| 157 | P1 | dashboard | — | **[READY]** React + Vite operations console (EPIC) | Depends on #148 (bootstrap) + #152 (auth) |
| 148 | P1 | dashboard | — | **[READY — PR #211 open]** Bootstrap React + TypeScript + Vite | PR #211 open; needs review+merge |
| 152 | P1 | dashboard | — | **[READY]** Auth operator session, RBAC, scoped access | Depends on #163 (gateway flows) |
| 150 | P1 | dashboard | — | **[READY]** Typed Gateway HTTP/WebSocket client & contracts | Depends on #169 (device registry) |
| 154 | P1 | dashboard | — | **[READY after #152+#150]** Safety-gated operator command center | Depends on auth + client |
| 155 | P1 | dashboard | — | **[READY after #152]** Device registry, diagnostics, commissioning UI | Depends on #169 |
| 151 | P1 | dashboard | — | **[READY after #150]** Operations telemetry, trend analytics, event timeline | Depends on client |
| 153 | P1 | dashboard | — | **[READY after #152+#150]** Persistent incident lifecycle & acknowledgment | Depends on auth + client |
| 149 | P1 | dashboard | — | **[READY after #148]** Responsive design system, navigation, layout | Depends on bootstrap |
| 156 | P1 | dashboard | — | **[READY after #148+#152]** React dashboard CI, E2E, production build | Depends on bootstrap + auth |
| 176 | P1 | twin | — | **[READY after #68]** Unity source project + Gateway state reducer | Depends on #68 |
| 68 | P1 | twin | — | **[READY]** Calibrate 9-module physical-to-Unity coordinate & state mapping | Prefab contracts in ADR-0012 |
| 12 | P1 | twin | — | **[READY after #68+#176]** Map live gateway telemetry to 3D factory state | Live sync; needs #176 first |
| 175 | P1 | physical | — | **[READY]** Production job & material lineage state machine | No external deps |
| 159 | P1 | edge-ai | — | **[READY]** Audit UBTECH Yanshee robot hardware, SDK, network | ADR-0013 adopted Yanshee; SDK audit pending |
| 160 | P1 | edge-ai | — | **[READY after #159]** Yanshee typed adapter & safe notifications | Depends on SDK audit |
| 178 | P1 | edge-ai | — | **[READY after #159+#160]** Robot-independent alert skill contract & Yanshee capabilities | Depends on adapter |
| 168 | P1 | gateway | — | **[READY]** Persistent incident & Yanshee alert dispatch outbox | Core gateway work |
| 199 | P1 | fiware | — | **[READY after #195+#197]** NGSI-LD subscriptions, notifications | Depends on entity graph |
| 200 | P1 | fiware | — | **[READY after #195]** Authenticated FIWARE context API boundary | Depends on #195 |
| 204 | P1 | fiware | — | **[READY after #195+#200]** Map FIWARE context to Yanshee notifications | Depends on #200 |
| 25 | P1 | physical | **gate:hardware** | **[BLOCKED]** Forklift & dump-truck telemetry/control abstraction | Physical modules not procured |
| 26 | P1 | physical | **gate:hardware** | **[BLOCKED]** Tower-crane & storage/parking logistics adapter | Physical modules not procured |
| 71 | P1 | physical | **gate:hardware** | **[BLOCKED]** Parking Lot occupancy & logistics-slot adapter | Physical modules not procured |
| 70 | P1 | physical | **gate:hardware** | **[BLOCKED]** Dump Truck device adapter, transport state, safety | Physical modules not procured |
| 24 | P1 | physical | **gate:hardware** | **[BLOCKED]** Packaging module adapter: cycle & completion telemetry | Physical modules not procured |
| 22 | P1 | physical | — | **[READY]** Conveyor module adapter: speed, sensors, stop interlock | PR #147 merged ✓; firmware integration pending |
| 23 | P1 | physical | — | **[CLOSED]** Sorting module adapter | PR #189 merged ✓ |
| 27 | P1 | physical | — | **[READY after #9+#22-#26]** Combine-module orchestration & production-cycle scheduler | Depends on all 9 module adapters |
| 190 | P1 | twin | — | **[READY after #12]** Licensed nine-module Unity 3D asset pipeline, prefab library | Depends on live telemetry |
| 145 | P1 | edge-ai | — | **[IN PROGRESS — PR #145 open]** MiniAlpha connectivity & bounded robot adapter | PR #145 open |

---

#### Wave 4 — E2E / HIL

| # | Priority | Area | Gate | Action | Notes |
|---|----------|------|------|--------|-------|
| 202 | P1 | fiware | — | **[READY after #195]** FIWARE contract integration tests & benchmark | Depends on #195 |
| 203 | P1 | fiware | — | **[READY after #195]** Assess FIWARE IoT Agent JSON/MQTT interoperability | Depends on #195 |
| 201 | P1 | fiware | — | **[READY after #195]** Evaluate NGSI-LD history & FIWARE time-series connector | Depends on #195 |
| 179 | P1 | security | — | **[READY]** E2E threat model & safety abuse-cases | Threat modeling; no hardware needed |
| 182 | P1 | infra | — | **[READY]** Reproducible deployment topology, service health checks, dashboards | Infra work |
| 186 | P1 | data | — | **[READY]** Executable DB schema migrations & backup/restore regression suite | DB work |
| 187 | P1 | quality | — | **[READY]** Verify required CI checks & module-to-test coverage on master | QA work |
| 183 | P1 | quality | — | **[READY after #27]** Complete 9-module scenario catalogue with traceable acceptance | Depends on all module adapters |
| 180 | P1 | integration | — | **[READY]** Runnable full-stack simulation & multi-service E2E test harness | E2E work |
| 170 | P1 | gateway | — | **[READY]** E2E trace observability, replay compatibility & logging | Depends on #165 |
| 16 | P1 | integration | — | **[READY after #180]** E2E acceptance suite: device → bridge → twin → edge AI | E2E final |
| 20 | P1 | quality | **gate:hardware** | **[BLOCKED]** HIL test matrix & safety sign-off protocol | Requires physical hardware |
| 74 | P1 | bridge | **gate:hardware** | **[BLOCKED]** OTA release pipeline, staged rollout & real ESP32-S3 regression | Requires HIL |
| 60 | P1 | bridge | **gate:hardware** | **[BLOCKED]** Mega CI + HIL flash wiring & recovery | Requires HIL |
| 181 | P1 | integration | **gate:hardware** | **[BLOCKED]** Physical bench HIL harness & module commissioning evidence | Physical hardware required |
| 161 | P1 | integration | **gate:hardware** | **[BLOCKED]** Yanshee robot end-to-end alert & operator approval validation | Physical robot required |
| 98 | P0 | hardware | **gate:hardware** | **[BLOCKED]** HIL verification & licensing | Master hardware gate |
| 156 | P1 | dashboard | — | **[READY after #148+#152]** React dashboard CI, E2E, production build | Wave 3 dash dep |

---

#### Wave 5 — Extensions

| # | Priority | Area | Gate | Action | Notes |
|---|----------|------|------|--------|-------|
| 193 | P2 | bridge | — | **[READY]** Evaluate secure ESP32 OTA remote update via bootloader | Design-only |
| 185 | P2 | devex | — | **[READY]** Module developer onboarding, agent ownership, cross-service runbooks | DX work |
| 184 | P2 | research | — | **[READY]** Reproducible experimental metrics pipeline & measured digit-twin fidelity | Research |
| 177 | P2 | twin | — | **[READY]** Safe Unity operator interaction & deterministic replay bounds | Design doc |
| 38 | P2 | edge-ai | — | **[READY after #178]** Evaluate anomaly model/rule quality on repeatable incidents | Depends on #178 |

---

## 3. Gap Analysis

### 3.1 Documentation Gaps

| Gap | Severity | Issue(s) | Status |
|-----|----------|----------|--------|
| FIWARE Orion-LD NGSI-LD context architecture | **HIGH** | #195–#205 | PR #206 merged (ADR); EPIC just started |
| Canonical telemetry schema mismatch (ADR-0009 flagged) | **HIGH** | #166 | ADR-0009 documented; implementation not started |
| Gateway canonical flows & ownership boundaries | **HIGH** | #163 | Not started; gateway implementation proceeding without it |
| Gateway northbound fanout & downstream contracts | **HIGH** | #194 | Blocked on #163 |
| ESP32–uKit electrical pinout & safety | **HIGH** | #173 | Hardware gate |
| Release integration queue | **MEDIUM** | #172 | Not started |
| Issue vs PR reconciliation | **MEDIUM** | #171 | Not started |
| Device registry contract (partially done) | **MEDIUM** | #32 | PR #119 merged; implementation pending #169 |
| Event store implementation (partially done) | **MEDIUM** | #31 | PR #114 merged; gaps noted in issue-31 followup docs |
| Command authorization lifecycle (partially done) | **MEDIUM** | #30 | PR #118 merged; gaps noted |
| Unity gateway transport contract (partially done) | **MEDIUM** | #67 | PR #121 merged; live sync pending #68+#176 |
| Yanshee SDK/API audit | **MEDIUM** | #159 | ADR-0013 adopted Yanshee; SDK specifics not audited |
| React dashboard bootstrap | **MEDIUM** | #148 | PR #211 open |
| 9-module physical factory interface spec | **MEDIUM** | #9 | Not started (design doc only) |
| Capability matrix & IO mapping | **MEDIUM** | #174 | Blocked on #9 |
| UBTECH Yanshee as edge AI robot decision | **LOW** | #158 | ADR-0013 adopted; PRs #162/#207/#209 closed (replaced by #206) |

### 3.2 Contract Gaps

| Contract | Status | Gap |
|----------|--------|-----|
| Bridge MQTT ↔ AMLP | **L2 — implemented** | ADR-0002 ✓; firmware tested in CI |
| Canonical event envelope | **L0 — proposed** | ADR-0005 ✓; not yet published to production |
| Telemetry schema v1 | **⚠ KNOWN MISMATCH** | ADR-0009; bridge emits `received_at_ms`/`values`/`pairs` not `timestamp`/`state` |
| Command authorization lifecycle | **L0 — specified** | PR #118 merged; implementation pending #164 |
| Device registry | **L0 — specified** | PR #119 merged; implementation pending #169 |
| Event store | **L2 — partial** | PR #114 merged; gaps in snapshots/retention |
| Unity prefab contracts | **L0 — specified** | ADR-0012 + PR #108 merged; live sync not verified |
| Unity gateway transport | **L0 — specified** | PR #121 merged; real-time WebSocket push not verified |
| Yanshee alert skill contract | **L0 — partial** | ADR-0013 adopted; #178 not started |
| FIWARE NGSI-LD entity graph | **L0 — proposed** | PR #206 merged; entity graph not defined yet (#197) |

### 3.3 Test Gaps

| Test Category | Coverage | Gap |
|--------------|----------|-----|
| Bridge MQTT JSON ↔ AMLP parity (C++, C99, Python) | L2 | Issue #28 closed ✓; maintained |
| Bridge telemetry health, heartbeat, reconnect | L2 | Issue #29 closed ✓ |
| ESP32 OTA authenticated (ADR-0007/0008) | L0 design only | No HIL test (#74 blocked) |
| Gateway event ingestion | L2 CI | Partial; #165 not implemented |
| Gateway command orchestrator | L0 design only | #164 not started |
| Unity Digital Twin live sync | L0 design only | #12, #176 not started |
| Full-stack E2E simulation | L0 design only | #180 not started |
| Physical HIL | Not started | All HIL blocked by #98 |
| FIWARE integration | Not started | All FIWARE E2E blocked by #195 |

### 3.4 Known Technical Debt

| Item | ADR | Issue | Status |
|------|-----|-------|--------|
| Telemetry schema mismatch | ADR-0009 | #166 | Proposed; implementation not started |
| Gateway flows undefined | — | #163 | Not started |
| Release integration queue missing | — | #172 | Not started |
| Issue/PR reconciliation | — | #171 | Not started |
| MiniAlpha → Yanshee robot pivot | ADR-0013 | #145 | PR #145 open; evidence not verified |
| Unity real-time sync verification | ADR-0003 | #11/#12/#176 | Unity scaffolded (PR #144); live sync not verified |
| FIWARE Orion-LD integration | — | #195–#205 | ADR #206 merged; implementation not started |

---

## 4. Hardware Gate Audit

**Total open `gate:hardware` issues: 16**

| # | Priority | Area | Wave | Hardware Requirement | Dependency Path |
|---|----------|------|------|---------------------|-----------------|
| 98 | **P0** | hardware | 0 | Master HIL gate: ESP32 + Mega + uKit modules + MX0508 level shifter + physical actuators | Blocks: #60, #74, #20, #181, #161 |
| 173 | **P0** | hardware | 0 | ESP32–uKit Explore V2.0 pinout, electrical safety, power rails | Blocks: #57 → #58 → #59 → #191 |
| 57 | P0 | bridge | 1 | Arduino Mega 2560 firmware target + official uKit SDK integration | Blocks: #58, #59, #191, #60 |
| 58 | P0 | bridge | 1 | Port AMLP v1 endpoint to Arduino Mega HardwareSerial | Blocks: #59, #191 |
| 59 | P0 | bridge | 1 | Safe uKit Explore motor/servo/sensor adapter | Blocks: #191, #98 |
| 191 | P0 | bridge | 1 | Versioned Mega SDK telemetry (motors, servos, sensors) | Blocks: #98 |
| 22 | P1 | physical | 3 | Conveyor module (physical hardware); PR #147 merged for simulator | Partial: simulator-only until hardware |
| 24 | P1 | physical | 3 | Packaging module physical hardware | Blocks: #27 (combine orchestrator) |
| 25 | P1 | physical | 3 | Forklift & dump-truck physical hardware | Blocks: #27 |
| 26 | P1 | physical | 3 | Tower crane & storage/parking physical hardware | Blocks: #27 |
| 70 | P1 | physical | 3 | Dump Truck device adapter | Blocks: #25 |
| 71 | P1 | physical | 3 | Parking Lot occupancy sensor hardware | Blocks: — |
| 60 | P1 | bridge | 4 | Mega CI + HIL flash wiring | Blocked by #57; blocks #98 |
| 74 | P1 | bridge | 4 | OTA release pipeline + real ESP32-S3 regression | Blocked by #98 |
| 20 | P1 | quality | 4 | HIL test matrix & safety sign-off protocol | Blocked by #98 |
| 161 | P1 | integration | 4 | Yanshee robot end-to-end alert validation | Requires physical Yanshee robot |
| 181 | P1 | integration | 4 | Physical bench HIL harness & module commissioning | Blocked by #98 |

**Critical path through hardware gates:**
```
#56 (done ✓) → #57 → #58 → #59 → #191 → #173
                                      ↓
#57 → #60 → #98 → #20, #74, #181, #161
              ↓
        #27 (combine orchestrator) ← #22, #24, #25, #26, #70, #71
```

**Hardware procurement status** (per docs/hardware-readiness.md):
- ESP32-S3: Available ✓
- Arduino MEGA 2560: Available ✓
- MX0508 level shifter: Available ✓
- uKit actuators (motors, sensors): **NOT procured**
- Nine physical factory modules: **NOT procured**
- MiniAlpha / UBTECH Yanshee robot: **NOT procured**

---

## 5. Triage Summary

### 5.1 Immediate Action (unblocked wave:0 work)

| Priority | # | Action | Owner signal |
|----------|---|--------|-------------|
| **P0** | #195 | Start FIWARE EPIC: ADR decision + context architecture | FIWARE EPIC owner |
| **P0** | #163 | Define nine canonical Gateway flows, ownership, execution model | Gateway owner |
| **P0** | #171 | Reconcile closed issues vs merged PRs | dev-architect |
| **P0** | #172 | Create release integration queue | After #171 |
| **P0** | #166 | Implement telemetry schema fix per ADR-0009 | Gateway owner |
| **P0** | #169 | Implement authoritative device registry, provisioning, OTA control | Gateway owner |
| **P1** | #148 | Review+merge PR #211 (React dashboard bootstrap) | Dashboard owner |
| **P1** | #9 | Define 9-module physical factory interface & end-to-end sequence | Physical owner |
| **P1** | #145 | Review+merge PR #145 (MiniAlpha/Yanshee adapter) | Edge-AI owner |

### 5.2 Near-term unblocked (wave:2 gateway core)

| Priority | # | Action |
|----------|---|--------|
| **P0** | #165 | Harden event ingestion durability (after #166 schema stable) |
| **P0** | #194 | Gateway northbound fanout (after #163) |
| **P1** | #167 | Gateway HTTP/WebSocket authentication |
| **P1** | #164 | Server-authorized command orchestrator |
| **P1** | #168 | Persistent incident & alert dispatch outbox |
| **P1** | #174 | Factory module capability matrix (after #9) |

### 5.3 Correctly blocked (hardware-gated)

These issues should **not** be started until hardware dependencies are resolved:

| # | Blocks on |
|---|-----------|
| #57 | #56 (done ✓) — Mega firmware target |
| #58 | #57 |
| #59 | #58 |
| #191 | #59 |
| #173 | #57→#58→#59 chain |
| #98 | Full #57→#59→#191 chain + hardware procurement |
| #22, #24, #25, #26, #27, #70, #71 | Physical module procurement + HIL harness |
| #60, #74, #20, #181, #161 | #98 |

### 5.4 Orphaned / Needs Triage

| # | Label | Issue |
|---|-------|-------|
| #145 | edge-ai | PR #145 open; MiniAlpha pivot to Yanshee — needs evidence of actual robot API |
| #22 | physical | PR #147 merged; marked gate:hardware but simulator PR merged — clarify simulator path |
| #12 | twin | Unity live sync — blocked by #68+#176; not blocked by hardware |
| #190 | twin | Licensed Unity 3D assets — clarify license/commercial asset situation |

---

## 6. Recommendations

1. **Start #195 (FIWARE EPIC) immediately.** It is the sole gate for 9 FIWARE issues. The context architecture decision must land before any wave:2 FIWARE work begins.
2. **Prioritize #163 (Gateway canonical flows).** Multiple P0 gateway issues (#169, #165, #194) are proceeding without a defined ownership model. Resolving #163 unblocks #194 and gives #165 and #169 clearer boundaries.
3. **Close #171 and #172 sequentially.** #172 (integration queue) is a prerequisite for any coordinated release. #171 reconciles the current state.
4. **Resolve ADR-0009 telemetry mismatch (#166).** The schema divergence between bridge output and canonical contract is a ticking incompatibility. Gate it behind a gateway translator or fix the firmware — decide now.
5. **Clarify #22 simulator path.** PR #147 merged for the conveyor simulator, but #22 is labeled `gate:hardware`. Separate the simulator-only delivery from the HIL delivery to avoid false blocking.
6. **Consolidate the MiniAlpha → Yanshee robot decision.** PR #145 is open for the MiniAlpha adapter, but the project pivoted to UBTECH Yanshee (ADR-0013). The PR must either be updated to Yanshee evidence or closed and replaced.
7. **Do not start wave:4 HIL issues.** All HIL work (#98, #60, #74, #20, #181, #161) is blocked by hardware procurement. Document the procurement checklist as a separate action.
8. **Add wave label to #163 explicitly.** It is labeled `wave:0-foundation` but describes wave:2-gateway-core scope. Consistency avoids confusion in triage.

---

## Appendix A: Wave Distribution of Open Issues

| Wave | Count | Notes |
|------|-------|-------|
| wave:0-foundation | 6 | 2 blocked (hardware), 4 ready |
| wave:1-device-link | 6 | 5 blocked (hardware), 1 ready (#9) |
| wave:2-gateway-core | 10 | All ready (FIWARE gated on #195) |
| wave:3-apps | 25 | 6 hardware-gated, 1 PR open (#211) |
| wave:4-e2e-hil | 17 | 6 hardware-gated; FIWARE gated on #195 |
| wave:5-extensions | 5 | All ready |
| No wave label | 6 | Including #188 epic, #145 (PR open) |
| **Total open** | **75** | |

## Appendix B: Open PRs

| PR | Title | Closes | Status |
|----|-------|--------|--------|
| #211 | feat(dashboard): bootstrap React + TypeScript + Vite | #148 | **OPEN** — needs review |
| #145 | feat: #13 MiniAlpha connectivity & bounded robot adapter | #13 | **OPEN** — evidence gap vs Yanshee ADR-0013 |

---

*Generated: 2026-10-20 | Smart Factory Monorepo | Issue #188 delivery*

---

## Addendum — Current Position as at 2026-10-21

> **The audit above is a point-in-time snapshot captured on 2026-10-20. It is not current and must not be read as current.** The counts in §1 Executive Summary, Appendix A and Appendix B were measured on 2026-10-20 and are now stale. They have been left unedited deliberately: the audit's wave, priority and gate triage was performed against the issue set as it stood on 2026-10-20, and re-deriving it later would invalidate its stated scope. The figures below supersede the 2026-10-20 counts **for counting purposes only** — the triage judgments above remain those of 2026-10-20 and have not been re-verified.

**Addendum date:** 2026-10-21 (UTC+07:00)
**Method:** Live GitHub REST API queries via `gh` CLI v2.92.0, authenticated as `vinhphan812`, against `vinhphan812/smart-factory`. Counts taken from `gh issue list` / `gh pr list` (full pagination limits, not truncated), plus label tallies derived from the same issue set. No triage was re-performed.

### L0 — Current Counts

| Metric | 2026-10-20 snapshot (above) | Current (2026-10-21) | Command |
|---|---|---|---|
| Total issues (open + closed) | ~128 | **133** | `gh issue list --state all --limit 500 --json number --jq 'length'` |
| Open issues | 75 | **64** | `gh issue list --state open --limit 500 --json number --jq 'length'` |
| Closed issues | 53 | **69** | `gh issue list --state closed --limit 1000 --json number --jq 'length'` |
| Open PRs | 2 | **7** | `gh pr list --state open --limit 100 --json number --jq 'length'` |
| Merged PRs (cumulative) | 47 | **64** | `gh pr list --state merged --limit 1000 --json number --jq 'length'` |
| ADRs in `docs/adr/` | 13 (+ template) | **15** (+ template) | `ls docs/adr/adr-0*.md \| wc -l` |
| Open `gate:hardware` issues | 16 | **20** | `gh issue list --state open --label gate:hardware --limit 200 --json number --jq 'length'` |

### L0 — Current Open-Issue Label Distribution

Replaces Appendix A's wave distribution for counting purposes only.

| Wave label | 2026-10-20 (Appendix A) | Current (2026-10-21) |
|---|---|---|
| wave:0-foundation | 6 | 5 |
| wave:1-device-link | 6 | 10 |
| wave:2-gateway-core | 10 | 3 |
| wave:3-apps | 25 | 22 |
| wave:4-e2e-hil | 17 | 19 |
| wave:5-extensions | 5 | 5 |
| No wave label | 6 | 0 |
| **Total open** | **75** | **64** |

Priority labels: P0 = 13, P1 = 45, P2 = 6 (total 64, matching the open-issue count above).
Also labelled `critical-path` = 12 and `gate:hardware` = 20 of the 64 open issues.

### L0 — Current Open PRs

Replaces Appendix B's open-PR table.

| PR | Title |
|---|---|
| #245 | feat(security): #179 End-to-end threat model and safety abuse-case regression suite |
| #244 | feat(#182 #186 #180): deployment topology, DB migrations, E2E simulation |
| #242 | feat(#152 #175): Dashboard auth/RBAC + job/material lineage |
| #240 | feat(contracts): end-to-end material flow sequence through all 9 modules |
| #239 | feat(contracts): add physical module capability matrix with typed IO mapping |
| #238 | docs(physical): define typed factory module interface |
| #234 | docs(qa): #187 CI checks & module-to-test coverage audit |

### Provenance Note

This document was committed on 2026-10-20 as `d441c89` on branch `smart-factory/t_b5a06c53-188-epic-close-system-spec-gaps-backlog` and delivered via PR #212, which was **closed without merging**. Issue #188 was consequently closed on a delivery that never reached `origin/master`. The audit body above is byte-identical to `d441c89`; only this addendum has been added. See `docs/tracking/reconciliation-log.md` for the reconciliation method established under Issue #171.

---

*Addendum added: 2026-10-21 | Live `gh` API audit | Issue #188 delivery to `origin/master`*
