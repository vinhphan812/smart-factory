# Smart Factory — 12-Month Execution Map

**Source:** master backlog issue [#52](https://github.com/vinhphan812/smart-factory/issues/52)  
**Owner:** vinhphan812  
**Engine:** Unity 3D (original proposal specified Unreal Engine; ADR-0003 changed to Unity as current engineering target; institutional approval of technology change PENDING/NOT VERIFIED — see ADR-0003)  
**Status:** living document; update after each quarterly review.

---

## Table of Contents

1. [Quarterly milestone table](#1-quarterly-milestone-table)  
2. [Dependency graph](#2-dependency-graph)  
3. [Delivered, in-progress and pending issues](#3-delivered-in-progress-and-pending-issues)  
4. [Hardware blockers — Issue #98](#4-hardware-blockers--issue-98)  
5. [Simulation vs physical evidence levels](#5-simulation-vs-physical-evidence-levels)  
6. [Validation against source documents](#6-validation-against-source-documents)  

---

## 1. Quarterly Milestone Table

Source: [#52](https://github.com/vinhphan812/smart-factory/issues/52) execution order (Waves 0–4), hardware-readiness gates, and ADR governance milestones.

### Q1 — Foundation & Interfaces (Months 1–3)

| # | Issue | Title | P | Milestone gate | Evidence level | Notes |
|---|---|---|---|---|---|---|
| #79 | CLOSED | Establish ADR governance, canonical template, decision log and lifecycle | P0 | Done | L0 | ADR backfill complete; governance enforced |
| #80 | CLOSED | Implement ADR lint, PR templates and mandatory architecture decision CI gate | P0 | Done | L0/L1 | CI check on architecture-impacting PRs |
| #65 | CLOSED | Bootstrap modular Smart Factory monorepo structure and module boundaries | P0 | Done | L0 | `esp32-ukit-bridge/`, `iot-gateway/`, `contracts/`, module ownership |
| #72 | CLOSED | Specify secure ESP32-S3 OTA architecture, partition layout and release contract | P0 | Done | L0 | ADR-0007; partition layout documented |
| #56 | CLOSED | Audit uKit Explore v1/v2 SDK, Mega pinout, dependencies and licensing | P0 | Done | L0 | ADR-0004; clean-room C99 reference confirmed |
| #4 | CLOSED | Verify actual uKit hardware interface and implement SDK adapter | P0 | Done | L2 | C99 reference endpoint; real SDK blocked by #98 |
| #7 | CLOSED | Implement MQTT ingestion gateway with offline simulator | P0 | Done | L2 | `iot-gateway/`; SQLite snapshots; offline mode |
| #29 | CLOSED | Implement bridge telemetry health, heartbeat and reconnect recovery | P1 | Done | L1/L2 | Diagnostics counters; MQTT reconnect |
| #66 | CLOSED | Implement ESP32 UART TEL → MQTT telemetry publication with contract tests | P0 | Done | L1/L2 | Bridge now publishes TEL frames to MQTT; hardware TBD |
| #81 | CLOSED | Backfill Smart Factory ADRs from existing architecture decisions | P1 | Done | L0 | ADRs 0001–0009 filled |
| #39 | CLOSED | Add telemetry charts, event timeline and incident acknowledgment | P1 | Done | L1/L2 | Dashboard charts and incident log |
| #98 | **OPEN** | **[P0][BRIDGE][UKIT-MEGA] HIL verification and licensing clearance for uKit Mega** | **P0** | **BLOCKED — no physical board** | L3 | Hard blocker for #4 physical firmware, #73 OTA on Mega, all L4+ |
| #82 | OPEN | Enforce ADR prerequisites across existing Issues and architecture reviews | P1 | Blocked on #79/#80 done | L0 | Governance audit; in-progress |

### Q2 — Core Modules & Safety (Months 4–6)

| # | Issue | Title | P | Milestone gate | Evidence level | Notes |
|---|---|---|---|---|---|---|
| #41 | OPEN | Harden MQTT broker authentication, TLS and secret management | P1 | After #7 closed | L1/L2 | TLS, ACLs, secret management; blocks production multi-device |
| #73 | OPEN | Implement authenticated HTTPS OTA client, maintenance gating and rollback on ESP32 bridge | P1 | After #72 closed | L2/L3 | HTTPS OTA; partition A/B; rollback on ESP32 only (not Mega) |
| #37 | OPEN | Add fail-closed safety decision gate between AI and physical actions | P1 | After #36, #38 | L0/L1 | ADR-0006 enforcement; AI cannot bypass local interlocks |
| #33 | OPEN | Model nine factory modules as reusable Unity prefabs and scene objects | P1 | After #11 | L0/L1 | Nine-module prefab set; coordinate/state mapping stubs |
| #34 | OPEN | Implement Unity time synchronization, stale data and snapshot resync | P1 | After #33 | L1/L2 | Twin must show UNKNOWN/STALE on disconnect |
| #67 | OPEN | Define Unity gateway transport adapter and offline replay contract fixture pack | P1 | After #66, #41 | L0/L1 | REST/WebSocket adapter; replay fixtures |
| #42 | OPEN | Create hardware/software capability and simulation fallback matrix | P1 | After #42 | L0 | Integration matrix refresh; see `docs/integration-matrix.md` |
| #74 | OPEN | Build OTA release pipeline, staged rollout and real ESP32-S3 recovery test matrix | P1 | After #73 | L2/L3 | CI firmware release; physical fault-injection |
| #11 | OPEN | Set up Unity project with Digital Twin scaffold, CI and asset conventions | P1 | After #65 | L0/L1 | Unity project, pinned editor, CI, prefab scaffold |
| #68 | OPEN | Calibrate nine-module physical-to-Unity coordinate and state mapping | P1 | After #33, #34 | L3 | Physical measurement required; BLOCKED by #98 |
| #52 | OPEN | Master backlog and 12-month execution map — Smart Factory | P1 | Continuous | L0 | This document; living |

### Q3 — Integration & AI (Months 7–9)

| # | Issue | Title | P | Milestone gate | Evidence level | Notes |
|---|---|---|---|---|---|---|
| #36 | OPEN | Implement robot alert notification skills and typed execution feedback | P1 | After #13, #14 | L1/L2 | MiniAlpha adapter; bounded skills; typed feedback |
| #46 | OPEN | Define reproducible experiments and baseline comparison methods | P1 | After #33, #67 | L0 | Scientific method; reproducibility criteria |
| #33 | OPEN | Model nine factory modules as reusable Unity prefabs and scene objects | P1 | Q2 carry-over | L0/L1 | (see Q2) |
| #34 | OPEN | Implement Unity time synchronization, stale data and snapshot resync | P1 | Q2 carry-over | L1/L2 | (see Q2) |
| #67 | OPEN | Define Unity gateway transport adapter and offline replay contract fixture pack | P1 | Q2 carry-over | L0/L1 | (see Q2) |
| #68 | OPEN | Calibrate nine-module physical-to-Unity coordinate and state mapping | P1 | Q2 carry-over | L3 | BLOCKED by #98 |
| #13 | OPEN | MiniAlpha AI Edge Robot adapter and capability discovery | P1 | After #41, #73 | L0/L1 | MiniAlpha API unknown; capability matrix required |
| #14 | OPEN | Edge AI anomaly detection and bounded action policy | P1 | After #13, #37 | L1 | Anomaly detection; bounded robot action policy |
| #38 | OPEN | Edge AI robot bounded response and escalation skills | P1 | After #14, #36 | L1/L2 | Escalation; no autonomous rescue |
| #15 | OPEN | Dashboard operator display with telemetry, incidents and gated commands | P1 | After #67 | L1 | Role-based; read-only telemetry; incident log |
| #40 | OPEN | Dashboard incident acknowledgment and operator command approval flow | P1 | After #15, #37 | L1/L2 | Gated commands; safety guard integration |

### Q4 — E2E, Research & Handover (Months 10–12)

| # | Issue | Title | P | Milestone gate | Evidence level | Notes |
|---|---|---|---|---|---|---|
| #16 | OPEN | Integration test harness — E2E scenario suite | P1 | After #34, #67, #74 | L2/L3 | E2E scenarios E01–E12 (see `docs/testing-and-acceptance.md`) |
| #42 | OPEN | Create hardware/software capability and simulation fallback matrix | P1 | After #34, #73, #74 | L0 | Refreshed matrix with actual hardware evidence |
| #43 | OPEN | Define latency, reliability and anomaly-detection KPIs and measurement methods | P1 | After #16 | L1/L2 | p50/p95/p99 sync delay; loss; recovery time |
| #44 | OPEN | Conduct reliability and fault-injection test runs | P1 | After #16, #43 | L3/L4 | Fault injection; E-stop; disconnect/reconnect |
| #45 | OPEN | Publish hardware-in-the-loop test evidence and acceptance report | P1 | After #44 | L3/L4 | HIL evidence; acceptance sign-off |
| #47 | OPEN | Draft scientific paper and results analysis | P2 | After #43, #44 | L0 | Research output; reproducibility evidence |
| #48 | OPEN | Produce lab guide and operator training documentation | P2 | After #45 | L0 | Lab guide; training materials |
| #49 | OPEN | Prepare public demo and demonstration script | P2 | After #15, #45 | L0 | Public demo readiness |
| #50 | OPEN | Prepare repository for public release (license, secrets, assets) | P2 | After #47, #49 | L0 | Legal review; no credentials or vendor SDK |
| #51 | OPEN | Backup, rollback and disaster-recovery documentation | P1 | After #74, #41 | L1 | Recovery runbook; snapshot management |

> **P0 = blocks safety/integration foundations. P1 = core feature. P2 = quality, evidence, training and handover.**

---

## 2. Dependency Graph

```
[Q1: Foundation & Interfaces]

 #98 HIL/Mega hardware  ──────┐
       BLOCKS:                │
   #4  physical firmware  ────┤
   #68 physical→Twin mapping  │
   #73 Mega OTA              │
   #44/#45 HIL tests         │
   ALL L4+ evidence           │
                              │
 #79 ADR governance ──────┐  │
 #80 ADR CI gate ────────┤  │
 #65 monorepo bootstrap ─┤  │
 #72 OTA architecture ───┤  │  ← (all done, Q1 closed)
 #56 Mega SDK audit ─────┤  │
 #4  C99 reference ──────┤  │
 #7  MQTT gateway ───────┤  │
 #29 bridge health ──────┤  │
 #66 TEL→MQTT telemetry ─┤  │
 #81 ADR backfill ───────┘  │
                              │
──────────────────────────────┘
              ↓
[Q2: Core Modules & Safety]

 #41 MQTT auth/TLS ────────────────────────────────────────┐
 #73 HTTPS OTA client ───────────────────────────────────┐ │
 #74 OTA CI pipeline ───────────────────────────────────┐ │ │
         └─ require #72 done                              │ │ │
 #37 AI fail-closed guard ──────────────────────────────┐ │ │ │
 #33 Unity prefab model ───────────────────────────────┐ │ │ │ │
 #34 Twin time sync/stale ───────────────────────────┐ │ │ │ │ │
 #67 Unity gateway adapter ───────────────────────┐ │ │ │ │ │ │
 #11 Unity project setup ───────────────────────┐ │ │ │ │ │ │ │
         └─ requires #65 done                    │ │ │ │ │ │ │ │
         └─ blocks #33/#34/#67                   │ │ │ │ │ │ │ │
                                              │ │ │ │ │ │ │ │
 #42 HW/SW capability matrix ─────────────────┘ │ │ │ │ │ │ │ │
         └─ blocks #44/#45                      │ │ │ │ │ │ │ │
                                              └─┘ │ │ │ │ │ │ │
 #82 ADR enforcement audit ────────────────────────┘ │ │ │ │ │ │
                                                        │ │ │ │ │ │
────────────────────────────────────────────────────────┘ │ │ │ │
                ↓                                         │ │ │ │
[Q3: Integration & AI]                                    │ │ │ │
                                                          │ │ │ │
 #13 MiniAlpha adapter ──────────────────────────────────┐ │ │ │
 #14 Edge anomaly detection ───────────────────────────┐ │ │ │
 #36 robot notification skills ────────────────────────┐ │ │ │
         └─ requires #13 done                            │ │ │ │
 #37 fail-closed guard ────────────────────────────────┘ │ │ │
 #38 bounded robot response ───────────────────────────┘ │ │ │
         └─ requires #14/#36 done                       │ │ │
 #15 dashboard telemetry/incidents ────────────────────┐ │ │ │
 #67 Unity adapter ───────────────────────────────────┐ │ │ │
         └─ requires #66/#41 done                      │ │ │
 #40 dashboard command gate ───────────────────────────┘ │ │
         └─ requires #15/#37 done                       │ │
 #46 reproducible experiments ───────────────────────────┘ │
         └─ requires #33/#67                              │
                                                        └─┘
                ↓
[Q4: E2E, Research & Handover]

 #16 E2E test harness ───────────────────────────────────────┐
         └─ requires #34/#67/#74                          │
 #43 KPI measurement ─────────────────────────────────────┐ │
 #44 fault injection runs ───────────────────────────────┐ │ │
 #45 HIL acceptance report ───────────────────────────────┐ │ │
         └─ all require #42/#16 done                      │ │ │
         └─ #44/#45 BLOCKED by #98 (no hardware yet)      │ │ │
 #47 scientific paper ───────────────────────────────────┘ │ │
         └─ requires #43/#44                             │ │
 #48 lab guide / operator training ───────────────────────┘ │
 #49 public demo ────────────────────────────────────────────┘
 #50 public release prep ─────────────────────────────────────┘
 #51 backup/rollback docs ─────────────────────────────────────┘
```

---

## 3. Delivered, In-Progress and Pending Issues

### Delivered (Closed)

| # | Title | Closed | Evidence |
|---|---|---|---|
| #65 | Bootstrap modular Smart Factory monorepo | 2026-10-14 | `esp32-ukit-bridge/`, `iot-gateway/`, `contracts/`, `docs/` |
| #66 | ESP32 UART TEL → MQTT telemetry publication | 2026-10-14 | Bridge publishes TEL frames to `smart-factory/bridge/telemetry` |
| #72 | Secure ESP32-S3 OTA architecture | 2026-10-14 | ADR-0007, `docs/architecture/esp32-ota-design.md` |
| #79 | Establish ADR governance | 2026-10-14 | `docs/adr/` ADRs 0001–0009, lifecycle defined |
| #80 | ADR lint and mandatory CI gate | 2026-10-14 | Branch protection / ruleset with ADR status check |
| #81 | Backfill Smart Factory ADRs | 2026-10-14 | ADRs 0001–0009 filled and linked |
| #56 | Audit uKit Explore v1/v2 SDK | 2026-10-14 | ADR-0004; clean-room C99 reference boundary set |
| #4 | Verify uKit hardware interface | 2026-10-14 | C99 portable reference; physical blocked by #98 |
| #7 | MQTT ingestion gateway | 2026-10-14 | `iot-gateway/`; SQLite snapshots; offline simulator |
| #29 | Bridge telemetry health, heartbeat | 2026-10-14 | Diagnostics counters; MQTT reconnect/retry |
| #39 | Dashboard telemetry charts and incident log | 2026-10-15 | Telemetry charts; event timeline; incident acknowledgment |

### In-Progress (Open, claimed or active worktree)

| # | Title | Worktree / Note |
|---|---|---|
| #82 | Enforce ADR prerequisites across Issues/PRs | `smart-factory/t_08672f24` |
| #41 | Harden MQTT broker auth, TLS and secrets | `feature/issues-41-mqtt-security` / `smart-factory/t_798fbd09` |
| #34 | Unity time sync, stale data, snapshot resync | `smart-factory/t_20e91dd7` / `fix/issue-34-unity-time-sync-recovery` |
| #33 | Unity nine-module prefabs | `fix/issue-33-unity-prefab-contracts` |
| #36 | Robot notification skills | `fix/issue-36-robot-notification` |
| #37 | AI fail-closed safety gate | `fix/issue-37-edge-ai-safety-gate` |
| #46 | Reproducible experiments baseline | `smart-factory/t_07eacc5f` / `feature/issues-46-experiment-baselines` |
| #42 | HW/SW capability matrix | `smart-factory/t_02cd87ae-42-create-hardware-software-capability-a` / `smart-factory/t_c79d83f1-42-delivery-recovery-capability-and-simu` |
| #39 | Dashboard telemetry charts | `smart-factory/t_9d59a1ae-39-add-telemetry-charts-event-timeline-a` / `feat/issues-39-telemetry-charts` |

### Pending (Open, not yet started)

| # | Title | P | Blocked by |
|---|---|---|---|
| **#98** | **[P0] HIL Mega verification & licensing** | **P0** | **No physical board — HARD BLOCKER** |
| #73 | HTTPS OTA client, maintenance gate, rollback | P1 | #72 (done) |
| #74 | OTA release pipeline, staged rollout, recovery matrix | P1 | #73 |
| #11 | Unity project setup, CI, asset conventions | P1 | #65 (done) |
| #33 | Nine-module Unity prefabs | P1 | #11 |
| #34 | Unity time sync, stale data, resync | P1 | #33 |
| #67 | Unity gateway transport adapter, offline replay fixtures | P1 | #66 (done), #41 |
| #68 | Physical-to-Unity coordinate calibration | P1 | #33, #34, **#98** |
| #13 | MiniAlpha AI Edge Robot adapter | P1 | #41, #73 |
| #14 | Edge AI anomaly detection, bounded action policy | P1 | #13, #37 |
| #36 | Robot alert notification skills, typed feedback | P1 | #13, #14 |
| #38 | Bounded robot response and escalation | P1 | #14, #36 |
| #15 | Dashboard telemetry, incidents, gated commands | P1 | #67 |
| #40 | Dashboard incident acknowledgment, operator approval | P1 | #15, #37 |
| #41 | MQTT broker auth, TLS, secrets | P1 | #7 (done) |
| #42 | HW/SW capability and simulation fallback matrix | P1 | Ongoing |
| #46 | Reproducible experiments and baseline methods | P1 | #33, #67 |
| #16 | E2E integration test harness | P1 | #34, #67, #74 |
| #43 | Latency, reliability, anomaly-detection KPIs | P1 | #16 |
| #44 | Fault-injection test runs | P1 | #16, #43, **#98** |
| #45 | HIL test evidence and acceptance report | P1 | #44, **#98** |
| #47 | Scientific paper and results analysis | P2 | #43, #44 |
| #48 | Lab guide and operator training docs | P2 | #45 |
| #49 | Public demo and demonstration script | P2 | #15, #45 |
| #50 | Repository public release prep | P2 | #47, #49 |
| #51 | Backup, rollback, disaster-recovery docs | P1 | #74, #41 |

---

## 4. Hardware Blockers — Issue #98

> **Critical path blocker.** All L4 (hardware-in-the-loop) and L5 (integrated) evidence, physical coordinate calibration, Mega firmware and HIL acceptance are blocked until Issue #98 is resolved.

### Issue #98 summary

| Field | Value |
|---|---|
| **Issue** | [#98](https://github.com/vinhphan812/smart-factory/issues/98) `[P0][BRIDGE][UKIT-MEGA]` Hardware-in-the-loop (HIL) verification and licensing clearance for uKit Mega integration |
| **State** | **OPEN** |
| **Owner** | vinhphan812 |
| **Predecessor** | #56 (CLOSED — SDK audit, clean-room boundary set) |
| **Hard blockers** | No physical Mega board available; no bench test equipment confirmation; licensing decision not finalized |

### Required preconditions (from #98)

- [ ] Physical uKit Mega board available for bench testing
- [ ] Multimeter/oscilloscope available for voltage/serial verification
- [ ] Legal clearance obtained or clean-room abstraction confirmed before touching vendor source code
- [ ] Arduino Mega 2560 board available
- [ ] Bidirectional logic level shifter (3.3 V ↔ 5 V) available
- [ ] Jumper wires and bench power supply

### Blocked downstream issues (cascading)

| Blocked issue | Title | Impact if unblocked |
|---|---|---|
| **#98** | HIL Mega verification | Gateway to all physical work |
| #4 (physical path) | uKit hardware interface — real firmware | Real motor/sensor control on Mega |
| #68 | Physical-to-Unity coordinate calibration | Twin cannot be calibrated against physical |
| #73 | Mega OTA (ESP32 Mega-specific path) | No firmware update path for Mega |
| #44 | Fault-injection test runs | Cannot inject physical faults |
| #45 | HIL acceptance report | Cannot produce L4 evidence |
| All L4/L5 evidence | Hardware-in-the-loop tests | Research KPIs cannot be measured on real HW |

### Mitigation (per current evidence)

- L2 simulation stack is operational: `amlp-sim`, MQTT broker, `iot-gateway/`, Python CLI
- C99 portable reference endpoint enables offline development without physical hardware
- ADR-0004 (clean-room boundary) is established; Mega SDK inclusion path is documented
- Research KPIs can be defined at L0/L1 now (Issue #46); actual measurements deferred to L4/L5
- **Do not claim HIL PASS from simulation results**

### Exclusions from #98 scope (as stated in issue)

- No actuator motion until E-stop and safety guard verified
- No flashing to physical Mega until voltage levels confirmed
- No vendor source imported without confirmed licensing

---

## 5. Simulation vs Physical Evidence Levels

See `docs/testing-and-acceptance.md` for the full definition. This table maps each quarter's evidence ceiling.

| Quarter | Target evidence level | What is proven | What is NOT proven |
|---|---|---|---|
| Q1 | L0/L1/L2 | Schemas, unit tests, protocol parsers, offline simulation | Physical wiring, actual motor control |
| Q2 | L1/L2/L3 (ESP32 bench) | ESP32 bench testing with TCP AMLP simulator; OTA on ESP32; gateway auth | Real Mega firmware; physical factory |
| Q3 | L1/L2/L3 | Continued ESP32 bench; Unity prefab CI; robot adapter mock | Physical factory calibration; real MiniAlpha |
| Q4 | **L4/L5 (hardware-dependent)** | **Only achievable if #98 is resolved** | HIL evidence, physical KPIs, real MiniAlpha |

> **Risk:** If #98 is not resolved before Q4, hardware evidence levels cannot advance past L2. Research KPIs (sync delay, loss rate, physical cycle reliability) cannot be measured.

---

## 6. Validation Against Source Documents

This execution map was validated against the following authoritative sources:

| Source document | Key constraints validated |
|---|---|
| `docs/PROJECT_CONTEXT.md` | Nine-module composition, three-system identity, safety non-goals, Unity target (approval unverified) |
| `docs/architecture/overview.md` | Proposed end-to-end flow, five layers, observation/action path, AMLP ACK semantics |
| `docs/contracts-and-data.md` | Command lifecycle (queued ≠ completed), telemetry envelope, required failure tests |
| `docs/architecture/repository-layout.md` | Module ownership table, boundary rules, Unity vs original proposal flag |
| `docs/ROADMAP.md` | Six-stage A–F proposal, five work packages, relative month mapping |
| `docs/testing-and-acceptance.md` | L0–L5 evidence levels, E01–E12 E2E scenarios, scientific KPIs |
| `docs/hardware-readiness.md` | Per-component status, bring-up prerequisites, level-shifter wiring |
| `docs/integration-matrix.md` | Capability matrix, blocking map, critical path to first hardware test |
| `docs/risks.md` | 13 named risks, mitigations, hardware and SDK availability risks |
| `docs/architecture/components.md` | Module ownership, boundary invariants, ADR-0003 provenance |
| Issue [#52](https://github.com/vinhphan812/smart-factory/issues/52) | Wave execution order, claim workflow, wave-specific issue chains, spec v2.0 |
| Issue [#98](https://github.com/vinhphan812/smart-factory/issues/98) | Hard blockers, preconditions, test cases TC1–TC5, exclusions |
| `docs/adr/adr-0003-digital-twin-engine.md` | Unity selected; institutional approval status unverified |
| `docs/adr/adr-0004-mega-sdk-boundary.md` | Clean-room C99 reference boundary; no vendor SDK in repo |

### Claims not made in this document

- No live Digital Twin pipeline (requires #34, #67, #68)
- No physical HIL evidence (blocked by #98)
- No MiniAlpha API integration (requires #13, #14, #36)
- No research KPIs measured (requires L4 hardware; #43, #46)
- No autonomous rescue capability (explicitly excluded per safety non-goals)
- No Unity institutional approval (flagged as unverified per ADR-0003)

---

*Last validated against source: 2026-10-16. Update after each quarterly review or when Issues change state.*
