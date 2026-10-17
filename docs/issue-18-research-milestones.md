# Issue #18 — 12-Month Research Milestones and KPIs

**Issue:** [#18](https://github.com/vinhphan812/smart-factory/issues/18)
**Owner:** vinhphan812
**Status:** Living document — update after each quarterly review.
**Source documents:** `docs/PROJECT_CONTEXT.md`, `docs/architecture/overview.md`, `docs/testing-and-acceptance.md`, `docs/roadmap/smart-factory-execution-map.md`, `docs/experiment-baselines.md`

---

## Table of Contents

1. [Research objective and three-system scope](#1-research-objective-and-three-system-scope)
2. [Quarterly milestones](#2-quarterly-milestones)
3. [Scientific KPIs and measurement methods](#3-scientific-kpis-and-measurement-methods)
4. [Evidence level requirements per KPI](#4-evidence-level-requirements-per-kpi)
5. [Hard blockers and risk-adjusted targets](#5-hard-blockers-and-risk-adjusted-targets)
6. [Validation against source documents](#6-validation-against-source-documents)

---

## 1. Research Objective and Three-System Scope

The project delivers three principal systems over 12 months at the AIBOT Center, DNTU:

| System | Description | Research contribution |
|---|---|---|
| **S1 — Physical Smart Factory** | Nine modular hardware elements with bounded control and safety interlocks | Hardware-in-the-loop integration, physical cycle reliability |
| **S2 — Real-time Digital Twin** | Unity 3D model reflecting observed factory states, alarms and reconnect/stale conditions | Sync latency, convergence, state fidelity |
| **S3 — AI Edge Robot** | MiniAlpha with bounded monitoring, alert and escalation skills | Anomaly detection accuracy, robot response latency and bounded-action compliance |

Supporting infrastructure (ESP32 bridge, MQTT broker, IoT gateway, event store, dashboard) is cross-cutting and serves all three systems.

**What is not a research claim:** autonomous rescue, safety certification, hardware KPI figures without L4+ evidence, or a live Twin pipeline before Issues #33/#34/#67/#68 are resolved.

---

## 2. Quarterly Milestones

Milestones map directly to the execution map (`docs/roadmap/smart-factory-execution-map.md`). Each milestone gates the KPIs that can be measured at its evidence level.

### Q1 — Foundation & Interfaces (Months 1–3)

*Gate: L0/L1/L2 evidence. No physical hardware KPIs are measurable this quarter.*

| Milestone | Issue | Criteria | Evidence level |
|---|---|---|---|
| ADR governance established | #79 | Decision log live, template enforced in PRs | L0 |
| ADR CI gate operational | #80 | Architecture-impacting PRs blocked without ADR status | L0 |
| Modular monorepo bootstrapped | #65 | `esp32-ukit-bridge/`, `iot-gateway/`, `contracts/` with CI | L0 |
| ESP32 OTA architecture documented | #72 | ADR-0007 signed OTA with A/B rollback | L0 |
| uKit Mega SDK boundary set | #56 | ADR-0004 clean-room C99 boundary confirmed | L0 |
| C99 reference endpoint delivered | #4 | AMLP v1 parser, CRC, dispatch, ACK, telemetry stubs pass L1/L2 tests | L1/L2 |
| MQTT ingestion gateway delivered | #7 | Offline simulator, SQLite snapshots, broker reconnect | L2 |
| Bridge telemetry health implemented | #29 | Diagnostics counters, heartbeat, MQTT reconnect | L1/L2 |
| Bridge publishes TEL as MQTT | #66 | `smart-factory/bridge/telemetry` topic with contract tests | L1/L2 |
| ADR backfill complete | #81 | ADRs 0001–0009 filled and linked | L0 |
| Dashboard telemetry charts live | #39 | Charts, event timeline, incident acknowledgment | L1/L2 |

> **Research KPI readiness Q1:** Latency and reliability KPIs (Section 3, KPI-1 through KPI-4) are defined and reviewed. Measurement tooling is implemented in simulation (L2). No physical measurement is claimed.

### Q2 — Core Modules & Safety (Months 4–6)

*Gate: L1/L2/L3 (ESP32 bench). First measurement of telemetry-sync KPIs in simulated environment.*

| Milestone | Issue | Criteria | Evidence level |
|---|---|---|---|
| MQTT broker auth, TLS, secrets | #41 | TLS, ACLs, per-device credentials configured | L1/L2 |
| HTTPS OTA client on ESP32 | #73 | Authenticated update, A/B partition, rollback | L2/L3 |
| OTA release pipeline and recovery matrix | #74 | CI firmware release, fault-injection on ESP32 | L2/L3 |
| Unity project scaffolded | #11 | Editor pinned, CI, prefab directory, conventions | L0/L1 |
| Nine-module Unity prefabs | #33 | Reusable prefab set, coordinate/state mapping stubs | L0/L1 |
| Unity time sync and stale indicators | #34 | Twin shows UNKNOWN/STALE on disconnect | L1/L2 |
| Unity gateway transport adapter | #67 | REST/WebSocket adapter, offline replay fixtures | L1/L2 |
| AI fail-closed safety gate | #37 | ADR-0006 enforced; no AI bypass of interlocks | L0/L1 |
| HW/SW capability matrix | #42 | Integration matrix refresh with available evidence | L0 |
| ADR prerequisites enforced | #82 | All architecture-impacting PRs pass ADR gate | L0 |

> **Research KPI readiness Q2:** KPI-1 (sync delay) and KPI-4 (duplicate handling) measured at L2 (simulated). KPI-2 (loss rate) measured at L2. KPI-3 (recovery time) measured at L2. KPI-5 (anomaly detection accuracy) is **BLOCKED** — requires #14 (not started). KPI-6 (robot response) is **BLOCKED** — requires #13/#36.

### Q3 — Integration & AI (Months 7–9)

*Gate: L1/L2/L3. Robot adapter and AI detection enter the measurement pipeline.*

| Milestone | Issue | Criteria | Evidence level |
|---|---|---|---|
| MiniAlpha adapter and capability discovery | #13 | API boundary, capability matrix, mock device | L0/L1 |
| Edge AI anomaly detection | #14 | Anomaly score, threshold, bounded action policy | L1 |
| Robot alert notification skills | #36 | Bounded skills, typed execution feedback | L1/L2 |
| Bounded robot response and escalation | #38 | Escalation chain; no autonomous rescue | L1/L2 |
| Dashboard telemetry and incident display | #15 | Role-based telemetry, incident log | L1 |
| Dashboard command approval gate | #40 | Gated commands, safety guard integration | L1/L2 |
| Physical-to-Unity coordinate calibration | #68 | **BLOCKED by #98** — deferred to Q4 | L3 |
| Reproducible experiments baseline | #46 | Experiment corpus, baseline methodology, reproducibility criteria | L0 |

> **Research KPI readiness Q3:** KPI-5 (anomaly detection accuracy/false alarms) measured at L1 with mock. KPI-6 (robot alert response) begins L1/L2 measurement. KPI-7 (production cycle reliability) remains **BLOCKED** — requires physical hardware (#98). KPI-1 through KPI-4 continue L2 measurement with expanded scenario set.

### Q4 — E2E, Research & Handover (Months 10–12)

*Gate: L4/L5 — achievable only if Issue #98 (physical Mega board) is resolved before Q4.*

| Milestone | Issue | Criteria | Evidence level |
|---|---|---|---|
| E2E integration test harness | #16 | Scenarios E01–E12 executed with declared real/mock mix | L2/L3/L4 |
| KPI measurement campaign | #43 | All KPI baselines recorded per experiment-baselines.md protocol | L1/L2/L4 |
| Fault-injection test runs | #44 | Disconnect, reconnect, E-stop, jam injected; **BLOCKED by #98** | L3/L4 |
| HIL acceptance report | #45 | L4 evidence, hardware test log, operator/E-stop checklist | L4 |
| Scientific paper draft | #47 | Results analysis, reproducibility evidence, raw data linked | L0 |
| Lab guide and operator training | #48 | Procedures, safety checklist, fault runbook | L0 |
| Public demo readiness | #49 | Demo script, live demonstration environment | L0 |
| Repository public release | #50 | Legal review, no credentials, no vendor SDK | L0 |
| Backup and disaster-recovery docs | #51 | Recovery runbook, snapshot management | L1 |

> **Research KPI readiness Q4 (full):** All KPIs measured at highest available evidence level. KPI-7 (production cycle reliability) and KPI-3 (recovery time under physical faults) require L4 and are **BLOCKED** until #98 is resolved.

---

## 3. Scientific KPIs and Measurement Methods

All KPI definitions and measurement methods are grounded in `docs/testing-and-acceptance.md` (Scientific KPIs) and `docs/experiment-baselines.md`. **Thresholds are not invented in this document; they are defined before data collection in the experiment protocol and reviewed against source constraints.**

### KPI-1 — Sync Delay Distribution

**Question:** What is the distribution of end-to-end delay from device telemetry emission to Twin state update?

**Metrics:** p50, p95, p99 latency (ms). Measured at each boundary: device → bridge → broker → gateway → Twin.

**Method:** Per experiment-baselines.md Section 4, E-CL. Timestamp at device UART emission (or simulator injection), monotonic clock at each hop, Twin state update. Run warm-up, then 30+ paired repetitions per seed. Report separately for idle and loaded conditions.

**Baseline comparators:** B0 (in-process simulator), B1 (gateway/broker path with mock), B2 (bench physical — L3+ only).

**Pass criterion (defined pre-run):** Pre-registered p95 threshold must be approved before collection. Any run with incomplete timestamps is discarded.

**Evidence levels where claimable:** L1/L2 (simulated), L3 (ESP32 bench), L4 (HIL physical — blocked until #98).

---

### KPI-2 — Message Loss Rate

**Question:** What proportion of device telemetry events are lost between emission and Twin state update?

**Metrics:** Loss rate with count and denominator. Reported per scenario and aggregate.

**Method:** Per E-CL in experiment-baselines.md. Emit N events with unique correlation IDs. Count events arriving at Twin within the declared observation window. Stale-state transitions are not loss events — record them separately.

**Pass criterion (defined pre-run):** Pre-registered maximum loss proportion. Any unexplained loss (not attributed to declared fault injection) requires incident investigation.

**Evidence levels:** L2 (simulated broker/device loss), L3 (ESP32 bench), L4 (HIL physical — blocked until #98).

---

### KPI-3 — Recovery Time After Disconnect

**Question:** How long does it take from broker reconnection to Twin convergence after a declared disconnect?

**Metrics:** Time-to-converge (ms), time-to-healthy (events per second restored), rollback count during recovery.

**Method:** Per E-TS in experiment-baselines.md. Inject controlled disconnect at declared point. Measure from first event received post-reconnect to convergence criterion (Twin version matches device sequence within tolerance). Record rollback events and stale-indicator duration.

**Pass criterion (defined pre-run):** Pre-registered maximum recovery time. Rollback count of zero (no backward state) is a safety-relevant criterion — any rollback during recovery is FAIL regardless of timing.

**Evidence levels:** L2 (simulated disconnect), L3 (ESP32 Wi-Fi reset), L4 (physical HIL — blocked until #98).

---

### KPI-4 — Duplicate Handling Rate

**Question:** How often does a correlated command get executed more than once on the device despite idempotency measures?

**Metrics:** Duplicate execution count, proportion of duplicate-correlation commands, false positive deduplication rate.

**Method:** Per E-CL in experiment-baselines.md. Send N commands with declared duplicate-correlation-ID strategy. Verify device execution count per correlation ID. False positive deduplication (legitimate retry rejected) is a separate failure mode.

**Pass criterion:** Pre-registered maximum duplicate rate. Zero unsafe duplicate execution on safety-relevant commands is a hard requirement.

**Evidence levels:** L1/L2 (simulated), L3 (ESP32 bench), L4 (HIL physical — blocked until #98).

---

### KPI-5 — Anomaly Detection Accuracy and False Alarm Rate

**Question:** Does the edge anomaly detector correctly classify normal, anomalous and safety-relevant events?

**Metrics:** True positive rate (recall), false positive rate, precision. Confusion matrix per event class.

**Method:** Per E-SG in experiment-baselines.md. Evaluate on a reviewed, labelled corpus (safe, unsafe, stale-context, malformed, unsupported-capability) blinded and randomized. Record policy decision, reason and whether any actuator command was emitted. Run adversarial and replay cases separately.

**Pass criterion:** Pre-registered minimum TP rate; maximum acceptable FP rate. Any false negative that permits unsafe actuation is a **safety failure** regardless of aggregate score — it is reported in the FP/TP matrix but triggers an incident record.

**Evidence levels:** L1 (policy simulation with mock corpus), L2 (online gateway with injected faults), L3/L4 (physical HIL — blocked until #98).

---

### KPI-6 — Robot Alert Response Latency and Bounded-Action Compliance

**Question:** Does MiniAlpha receive alerts, respond within the declared bound and never execute an unapproved skill?

**Metrics:** Alert-to-response latency (ms), response correctness rate, unapproved-action count.

**Method:** Per E-SG (bounded-action compliance) and E-CL (latency) from experiment-baselines.md. Trigger alert scenarios E01–E12 as applicable. Record MiniAlpha response timestamp and action. Any action outside the approved skill set or safety policy is a compliance failure.

**Pass criterion:** Pre-registered maximum response latency. **Zero unapproved actions** is a hard requirement — any violation is a safety incident regardless of latency score.

**Evidence levels:** L1 (mock MiniAlpha), L2 (gateway with mock robot), L3/L4 (physical robot integration — blocked until #13, #14, #36, #98).

---

### KPI-7 — Production Cycle Reliability

**Question:** What is the end-to-end reliability of a declared production scenario (transport → sort → pack → store)?

**Metrics:** Cycle completion rate, cycle time mean/variance, failure mode breakdown.

**Method:** Per E01 (Normal production) in `docs/testing-and-acceptance.md`. Run declared number of complete cycles. Record all failure modes, corrective actions and operator interventions. Report separately for simulated (L2) and physical (L4) runs.

**Pass criterion:** Pre-registered minimum completion rate and maximum cycle time variance. Physical hardware runs require operator and E-stop precheck.

**Evidence levels:** L2 (simulated factory), L4 (HIL physical — **BLOCKED until #98**). No L3 for full cycle reliability (partial hardware does not constitute a production cycle).

---

## 4. Evidence Level Requirements per KPI

|| KPI | L1 (unit) | L2 (sim) | L3 (ESP32 bench) | L4 (HIL) | L5 (E2E) |
|---|---|---|---|---|---|---|
| KPI-1 Sync Delay | Parser timing | Simulated path | ESP32 bench | Physical (blocked #98) | Full E2E (blocked #98) |
| KPI-2 Loss Rate | — | Simulated loss | ESP32 bench | Physical (blocked #98) | Full E2E (blocked #98) |
| KPI-3 Recovery | — | Sim disconnect | Wi-Fi reset | Physical fault (blocked #98) | Full E2E (blocked #98) |
| KPI-4 Duplicates | Command logic | Sim retry | ESP32 bench | Physical (blocked #98) | Full E2E (blocked #98) |
| KPI-5 Anomaly | Policy unit | Mock corpus | ESP32 + mock | Physical HIL (blocked #98) | Full E2E (blocked #98) |
| KPI-6 Robot | Mock response | Gateway mock | Gateway + mock robot | Physical (blocked #13/#98) | Full E2E (blocked #98) |
| KPI-7 Cycle Reliability | — | Sim factory | **Not applicable** | Physical (blocked #98) | Full E2E (blocked #98) |

> **Key:** A cell marked "blocked #98" means the KPI cannot be measured at that evidence level until Issue #98 (physical Mega board) is resolved. Do not claim that level's results from a lower level.

---

## 5. Hard Blockers and Risk-Adjusted Targets

### #98 — Physical Mega Board (P0 Hard Blocker)

Issue #98 blocks all L4 and L5 KPI measurement. If #98 is not resolved before Q4, KPI-1 through KPI-4 and KPI-7 cannot advance past L2/L3. The research paper (Issue #47) must disclose this limitation and present L2 results with explicit "hardware evidence unavailable" caveats.

See `docs/roadmap/smart-factory-execution-map.md` Section 4 for full blocker cascade.

### #13 — MiniAlpha API Unknown

MiniAlpha API and capability matrix are undocumented. KPI-6 cannot be measured against real hardware until #13 delivers the API boundary and mock/real capability matrix. Mitigation: use mock responses at L1/L2.

### Threshold Not Invented Here

This document does not set performance thresholds. Per `docs/testing-and-acceptance.md`:

> *"Do not invent thresholds or claim PASS without evidence."*

Every KPI threshold must be:
1. Defined in the experiment protocol before data collection.
2. Reviewed against source constraints (e.g. `docs/architecture/overview.md` latency requirements, if any).
3. Approved via PR or documented ADR.
4. Logged in the run manifest alongside results.

---

## 6. Validation Against Source Documents

This document was validated against the following authoritative sources:

| Source | Key constraints validated |
|---|---|
| `docs/PROJECT_CONTEXT.md` | 12-month duration, three-system identity, nine-module composition, safety non-goals |
| `docs/architecture/overview.md` | Five-layer architecture, observation/action paths, AMLP ACK semantics, stale/UNKNOWN requirement |
| `docs/testing-and-acceptance.md` | L0–L5 evidence levels, E01–E12 acceptance scenarios, Scientific KPIs paragraph |
| `docs/roadmap/smart-factory-execution-map.md` | Q1–Q4 issue mapping, dependency graph, hardware blockers, evidence ceiling per quarter |
| `docs/experiment-baselines.md` | E-CL, E-TS, E-SG, E-OTA experiment designs, baseline comparators, run manifest schema |
| `docs/hardware-readiness.md` | Per-component status, bring-up prerequisites, level-shifter wiring |
| Issue [#98](https://github.com/vinhphan812/smart-factory/issues/98) | Hard blockers, cascading downstream impact, mitigation strategy |

### Claims explicitly not made in this document

- No physical KPI values without L4 evidence
- No HIL test results without #98 resolved
- No MiniAlpha integration without #13, #14, #36 resolved
- No autonomous rescue capability (explicitly excluded per PROJECT_CONTEXT.md safety non-goals)
- No Unity institutional approval (flagged as unverified per ADR-0003)
- No live Digital Twin pipeline before Issues #33/#34/#67/#68 are resolved
- No threshold values without pre-registered, approved experiment protocols

---

*Document created: 2026-10-17. Update after each quarterly review or when #98 or other blockers change state.*
