# AIBOT Smart Factory — Final Scientific and Technical Report

**Document version:** 1.0  
**Generated:** 2026-10-17  
**Authors:** AIBOT Smart Factory Project Team (DNTU)  
**Repository:** [vinhphan812/smart-factory](https://github.com/vinhphan812/smart-factory)  
**Source commit:** `244f333` (branch `smart-factory/t_f04d64a0-48-final-scientific-technical-report-and`)  
**Status:** L2 deliverable — physical sections marked BLOCKED pending hardware procurement

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Research Context and Objectives](#2-research-context-and-objectives)
3. [System Architecture](#3-system-architecture)
4. [Principal System S1 — Physical Smart Factory](#4-principal-system-s1--physical-smart-factory)
5. [Principal System S2 — Real-time Digital Twin](#5-principal-system-s2--real-time-digital-twin)
6. [Principal System S3 — AI Edge Robot (MiniAlpha)](#6-principal-system-s3--ai-edge-robot-minialpha)
7. [Supporting Infrastructure](#7-supporting-infrastructure)
8. [Evidence Levels and Verification Framework](#8-evidence-levels-and-verification-framework)
9. [Scientific KPIs and Measurement Protocol](#9-scientific-kpis-and-measurement-protocol)
10. [Safety and Non-goals](#10-safety-and-non-goals)
11. [Research Evidence and Reproducibility](#11-research-evidence-and-reproducibility)
12. [Training and Lab Exercises](#12-training-and-lab-exercises)
13. [Open Issues and Hardware Blockers](#13-open-issues-and-hardware-blockers)
14. [Governance and Repository Policy](#14-governance-and-repository-policy)
15. [Handover Checklist](#15-handover-checklist)
16. [References](#16-references)

---

## 1. Executive Summary

This report documents the scientific and technical deliverables of the AIBOT Smart Factory project, a 12-month research initiative at the Centre for Artificial Intelligence and Robotics Technology (AIBOT), Dong Nai University of Technology (DNTU). The project aims to design, build, and validate a safe miniature Industry 4.0 production and logistics demonstration system integrating real-time Digital Twin technology and an AI Edge Robot.

The system comprises three principal systems:

- **S1 — Physical Smart Factory:** nine modular hardware elements (conveyor, sorting, packaging, forklift, dump truck, tower crane, parking lot, combine modules, bracket) with instrumented state and bounded control.
- **S2 — Real-time Digital Twin:** a Unity 3D model that reflects observed factory states, events, alarms, reconnect and stale/offline conditions in real time.
- **S3 — AI Edge Robot:** MiniAlpha to monitor factory status, receive alerts, provide bounded on-site responses, and interact with operators. AI may not override physical safety interlocks.

**Current status (as of 2026-10-17):** The ESP32–UKIT bridge firmware, MQTT contract, AMLP v1 protocol specification, IoT gateway with typed alert notification system, operator dashboard with telemetry charts, and event store contract are implemented and peer-reviewed. The Unity Digital Twin, factory simulator, all nine module adapters, MiniAlpha adapter, edge anomaly detection pipeline, HIL integration suite, and physical factory are **BLOCKED** pending hardware procurement, procurement surveys, and institutional approvals detailed in Section 13.

This report is a **Level 2 (L2) deliverable**: the report structure, all implemented-system sections, architecture documentation, contracts, and evidence framework are complete. Physical-result sections are explicitly marked **BLOCKED** with clear unblocking actions and owners assigned.

---

## 2. Research Context and Objectives

### 2.1 Research Topic

**"Thiết kế, xây dựng và thử nghiệm mô hình Smart Factory thu nhỏ tích hợp Digital Twin thời gian thực và AI Edge Robot tại Trung tâm AIBOT"**

*(Design, construction and testing of a miniature Smart Factory model integrating real-time Digital Twin and AI Edge Robot at the AIBOT Centre)*

### 2.2 Lead Environment

- **Institution:** Centre for Artificial Intelligence and Robotics Technology (AIBOT), Dong Nai University of Technology (DNTU)
- **Duration:** 12 months (proposal without fixed start date)
- **Repository:** `https://github.com/vinhphan812/smart-factory` (public, no credentials or private data)

### 2.3 Research Objectives

| Objective | Description | Evidence Required |
|---|---|---|
| O1 — Architecture | Modular system architecture with defined contracts between all layers | ADRs, component boundaries, contract docs |
| O2 — Physical integration | Nine-module physical factory coordinated and instrumented | BLOCKED — procurement + wiring + coordinate survey required |
| O3 — Data pipeline | Real-time acquisition, transmission, storage and synchronization | L2 gateway, event store, MQTT contracts implemented; physical path BLOCKED |
| O4 — Digital Twin | Unity 3D model reflecting live factory state with stale/offline indicators | BLOCKED — requires S1 coordinate survey + Unity institutional approval |
| O5 — AI Edge Robot | MiniAlpha integration with bounded skills and safety guard | BLOCKED — MiniAlpha unit confirmation + skill API boundary required |
| O6 — OTA and CI/CD | Signed HTTPS OTA with A/B rollback and automated pipeline | Partially implemented (contracts + state machine); physical flash BLOCKED |
| O7 — Reproducibility | Versioned evidence archive with run manifests and raw data | Planned (Issue #47) |
| O8 — Lab exercises | Beginner-to-advanced exercises from simulator + contracts | Planned (Issue #49) |

### 2.4 Original vs. Current Specification

The formal research proposal named **Unreal Engine** as the Digital Twin technology. The engineering team selected **Unity 3D** after evaluation. The formal institutional authorization status of this technology change (ADR-0003) is **not verified** and is listed as a hard blocker in the open issues register.

---

## 3. System Architecture

### 3.1 Modular Monorepo Structure

The repository follows a modular monorepo architecture (ADR-0001). Component isolation and source compatibility are maintained via versioned contracts. All cross-component changes go through pull request review.

```
smart-factory/
├── esp32-ukit-bridge/       # ESP32-S3 firmware, AMLP protocol, Python simulator
├── factory-control/          # Factory simulator and mock module adapters
├── iot-gateway/             # MQTT broker, event normalization, routing
├── event-store/             # Snapshot persistence and event replay
├── digital-twin/             # Unity Digital Twin project (BLOCKED)
├── edge-ai-robot/           # MiniAlpha adapter and anomaly detection (BLOCKED)
├── dashboard/               # Operator dashboard with telemetry charts
├── infrastructure/           # Docker Compose, CI/CD pipelines
├── integration-tests/        # E2E orchestration suite (BLOCKED L2 partial)
├── contracts/               # Shared JSON schemas, type definitions
└── docs/                    # ADRs, specifications, runbooks, this report
```

### 3.2 End-to-End Data Flow

```
Factory[9 physical modules + local controllers]
  │
  │ sensors / bounded commands
  ▼
Bridge[ESP32 UKIT Bridge / other adapters]
  │
  │ authenticated MQTT (TLS)
  ▼
Broker[MQTT Broker — TLS-configured]
  │
  ├──► Gateway[IoT Gateway: validate, normalize, trace]
  │         │
  │         ├──► Event Store[snapshots + event log]
  │         ├──► Unity Twin[3D state visualization]  ← BLOCKED
  │         ├──► Dashboard[operator telemetry + charts]
  │         └──► Edge AI[anomaly detector]          ← BLOCKED
  │                   │
  │                   ▼
  │              Robot[MiniAlpha — bounded skills]    ← BLOCKED
  │
  └──► Guard[Safety authorization + fresh context guard]
            ▲
            │ request only
            │
      Edge AI or Operator
```

### 3.3 Five Conceptual Layers

| Layer | Description | Examples |
|---|---|---|
| L1 — Physical | Hardware factory and actuators | 9 modules, motors, sensors, E-stop |
| L2 — Industrial comms | UART AMLP, MQTT; OPC UA potential extension | ESP32 UART, TLS MQTT broker |
| L3 — Edge/control | ESP32, local UKIT controllers, safe motion | Bridge firmware, command safety gate |
| L4 — Data/AI | Gateway, event store, anomaly conditions, robot adapter | iot-gateway, edge-ai-robot |
| L5 — Applications | Unity Twin, dashboard, educational interfaces | digital-twin, dashboard |

### 3.4 Architecture Decisions (ADRs)

All significant architectural decisions are captured as Architecture Decision Records:

| ADR | Title | Status |
|---|---|---|
| ADR-0001 | Modular monorepo structure and module boundaries | Accepted |
| ADR-0002 | Bridge MQTT ↔ AMLP contract and topic patterns | Accepted |
| ADR-0003 | Digital Twin engine: Unity selected | **Pending institutional approval** |
| ADR-0004 | Mega SDK boundary: portable C99 vs UBTECH vendor SDK | Accepted |
| ADR-0005 | Gateway canonical event envelope and normalization | Accepted |
| ADR-0006 | Local physical command safety and AI fail-closed guard | Accepted |
| ADR-0007 | Signed HTTPS OTA with A/B rollback | Accepted |
| ADR-0008 | Event-driven OtaManager (no dedicated FreeRTOS task) | Accepted |
| ADR-0009 | Telemetry schema compatibility | **Known mismatch — requires resolution** |
| ADR-0010 | MQTT broker security | Accepted |
| ADR-0011 | Dashboard safety | Accepted |
| ADR-0012 | Unity Digital Twin prefab contracts | **BLOCKED** |

Full ADR texts are available in `docs/adr/`.

---

## 4. Principal System S1 — Physical Smart Factory

> **⚠️ BLOCKED (L4/L5):** This section describes the target physical system. No physical hardware has been procured, wired, or verified. All claims in this section require the unblocking actions listed below.

### 4.1 Nine-Module Composition

| Module | Intended Purpose | Verification Gate | Status |
|---|---|---|---|
| Conveyor Belt | Convey material between stations | Safe speed/stop, sensor mapping | **BLOCKED** — unit procurement pending |
| Sorting Machine | Routing/classification by type | Input/output sensors, reject state | **BLOCKED** — unit procurement pending |
| Packaging Machine | Packaging step | Sensors, completion detection, interlocks | **BLOCKED** — unit procurement pending |
| Forklift | Material transport / pallet logistics | Controller, position & motion limits | **BLOCKED** — unit procurement pending |
| Dump Truck | Material delivery | Controller and command interface | **BLOCKED** — unit not in procurement plan |
| Tower Crane | Lift / place items | Limits, occupied zones, manual E-stop | **BLOCKED** — unit not in procurement plan |
| Parking Lot | Logistics staging | Slot/vehicle presence detection | **BLOCKED** — unit not in procurement plan |
| Combine Modules | Factory integration | Connected end-to-end line | **BLOCKED** — depends on all above |
| Bracket / Frame | Mechanical structures | Actual mechanical/electrical scope | **BLOCKED** — procurement pending |

**Production pipeline:** incoming material → transport → conveyor → sorting → packaging → storage/logistics.

### 4.2 Physical Integration Requirements (BLOCKED)

Before any physical module can be integrated, the following are required:

1. **Module procurement** — all 9 units must be acquired and inventoried.
2. **Device ID assignment** — each module receives a unique, immutable device ID used across controllers, bridge, gateway, Twin, and logs.
3. **Physical wiring specification** — voltage levels, connector types, grounding, E-stop chain topology documented and verified.
4. **Coordinate survey** — physical dimensions, positions, and orientations measured for Twin calibration (Issue #9, owner: dev-pm).
5. **Local controller firmware** — each module's controller programmed with safe-motion limits and E-stop handling.
6. **Prefabric contracts** — defined in `docs/twin/prefab-module-contracts.md`; physical calibration data must fill the placeholder fields.

**Pipeline owner:** dev-pm  
**Blocking issues:** #9 (procurement + wiring), #22/23/24/25/26/70/71 (module adapters), #68 (Twin coordinate calibration)

---

## 5. Principal System S2 — Real-time Digital Twin

> **⚠️ BLOCKED (L4/L5):** The Unity Digital Twin project is scaffolded (Issue #11, `digital-twin/` directory created) but not connected to live telemetry. The prefab contracts are defined (ADR-0012, `docs/twin/prefab-module-contracts.md`). Full implementation requires Issue #9 (physical coordinate survey) and Issue #10 (factory simulator) before live Twin mapping is possible.

### 5.1 Current State (L2)

| Component | Status | Evidence |
|---|---|---|
| Unity project scaffold (Issue #11) | Done — in-progress worktree `fix-issue35-clean` | Branch `fix/issue-35-interactive-factory-features` |
| Unity prefab contracts (ADR-0012) | Done | `docs/twin/prefab-module-contracts.md` |
| Mock event adapter | **BLOCKED** — depends on #10 (factory simulator) | Issue #12 |
| Live gateway-to-Twin event adapter | **BLOCKED** — depends on #3, #7, #11, #10 | Issue #12 |
| Coordinate calibration fixtures | **BLOCKED** — depends on #9 (physical dimensions) | Issue #68 |

### 5.2 Twin Requirements

- Must show **unknown/stale** (not invent a running state) when telemetry is disconnected or delayed.
- Must reflect observed state only — no speculative animation.
- Must display reconnect and stale/offline conditions explicitly.
- Twin state must never roll backward during out-of-order events.
- Full Twin calibration requires physical module measurements from Issue #9.

### 5.3 Unity Institutional Approval

The formal research proposal named Unreal Engine. Unity was selected by the engineering team. The institutional deviation approval (ADR-0003) has **not been verified**. This is a hard blocker: no institutional approval means no approved Twin engine.

**Owner:** dev-pm (institutional liaison)  
**Blocking issues:** #11 ADR verification

---

## 6. Principal System S3 — AI Edge Robot (MiniAlpha)

> **⚠️ BLOCKED (L4/L5):** The MiniAlpha adapter (Issue #13) has a typed mock implementation. Physical HIL integration requires a confirmed MiniAlpha unit and verified skill API boundary.

### 6.1 MiniAlpha Responsibilities

- Monitor factory status via gateway events.
- Receive alerts from edge anomaly detector.
- Provide bounded on-site responses within approved skill boundaries.
- Reject unsupported skills explicitly without actuation.
- Never override physical safety interlocks or initiate unapproved physical rescue.

### 6.2 Current State

| Component | Status | Evidence |
|---|---|---|
| Typed mock robot adapter (Issue #13) | **L2 implementable now** | `edge-ai-robot/` |
| Bounded command interface | **L2 implementable now** | `edge-ai-robot/` |
| Unsupported-skill rejection | **L2 implementable now** | `edge-ai-robot/` |
| Notification contract | Done | `docs/alerts/notification-contract.md` |
| Physical MiniAlpha unit | **BLOCKED** — unit availability unconfirmed | Issue #13, owner: dev-pm |
| Real skill API boundary | **BLOCKED** — depends on unit confirmation | Issue #13 |

---

## 7. Supporting Infrastructure

### 7.1 ESP32–UKIT Bridge

**Location:** `esp32-ukit-bridge/`

The bridge firmware runs on ESP32-S3 (PlatformIO) and provides an authenticated MQTT-to-AMLP UART path.

**Implemented:**
- Subscribe topic: `smart-factory/bridge/command` — JSON command dispatch (e.g., `{"id":102,"fields":["CONVEYOR_START","60"]}`)
- Publish topics: `smart-factory/bridge/result` (queued, duplicate, invalid, acknowledged, failed, attempts) and `smart-factory/bridge/status` (retained)
- AMLP v1 protocol: `@BODY*CRC4\r\n` frames with CMD/ACK/TEL types, CRC-16/CCITT-FALSE, correlation IDs, duplicate protection
- C99 UKIT portable reference endpoint (not the vendor SDK)
- Python AMLP simulator and CLI for offline validation

**NOT implemented (BLOCKED):**
- UART TEL-to-MQTT telemetry publishing — firmware does not yet confirm TEL frames are published as MQTT events. A live Digital Twin pipeline is **not finished**.
- Real UKIT wiring, electrical level verification, and firmware flashing with approved controller

**Reference documents:**
- `esp32-ukit-bridge/docs/mqtt-contract.md`
- `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md`
- ADR-0002 (MQTT↔AMLP contract)
- ADR-0004 (Mega SDK boundary)

### 7.2 IoT Gateway

**Location:** `iot-gateway/`

**Implemented:**
- MQTT broker with TLS configuration (runtime-configurable bind, certs, credentials) — ADR-0010
- Event normalization and validation against canonical schema (ADR-0005)
- Command authorization lifecycle with role/capability checks, expiry, idempotency — `docs/issue-30-command-authz-contract.md`
- Typed robot alert notification system — `docs/alerts/notification-contract.md`
- Fail-closed webhook allowlist with hostname normalization and redirect disabled (P0 SSRF fix)

**NOT implemented:**
- Per-device MQTT topics (not yet established; see `docs/contracts-and-data.md`)
- Physical telemetry ingestion from verified device controllers

### 7.3 Event Store

**Location:** `event-store/` (planned), contracts in `docs/issue-31-event-store-contract.md`

**Implemented:**
- Event store implementation contract (ADR-0005) defining snapshot and event log semantics
- Follow-up: completed items, top 3 gaps, verification checklist (`docs/issue-31-followup.md`)

**NOT implemented:**
- Live event store service — depends on gateway validation layer

### 7.4 Operator Dashboard

**Location:** `dashboard/`

**Implemented:**
- Operator telemetry charts (sensor data visualization)
- Event timeline
- Incident acknowledgement workflow
- Mock gateway API adapter for L2 testing

**Reference:** `docs/issue-44-integration-test-plan.md`, `docs/issue-45-qa-test-plan.md`

### 7.5 OTA Manager

**Location:** `esp32-ukit-bridge/` (OtaManager), `infrastructure/` (CI pipeline)

**Implemented:**
- OtaManager state machine with event-driven design (no dedicated FreeRTOS task) — ADR-0008
- Signed HTTPS OTA with A/B rollback — ADR-0007
- Authenticated HTTPS OTA client state machine (Issue #73, L1/L2) — **BLOCKED** physical flash by #74
- CI release pipeline scaffolding — **BLOCKED** physical OTA bench tests by #73 + ESP32-S3 boards

### 7.6 uKit Bridge (Mega)

**Location:** `esp32-ukit-bridge/` (mega adapter)

**Implemented:**
- AMLP v1 endpoint portable reference (C99) — not vendor SDK
- Mega SDK boundary defined — ADR-0004

**BLOCKED (L3):**
- Port AMLP endpoint to Arduino Mega HardwareSerial — Issue #58: requires Mega board + level shifter + license clearance (#98) + verified SDK
- Motor/servo/sensor adapter — Issue #59: depends on #9 (inventory) + #58 (Mega UART)
- Mega CI and flash/recovery guide — Issue #60: depends on #98 (board verification + license)

**Critical blocker:** Issue #98 (HIL verification + licensing clearance for uKit Mega). Without it, #58/#59/#60 cannot advance past code review.

---

## 8. Evidence Levels and Verification Framework

Every test and result is labelled with an evidence level from `docs/testing-and-acceptance.md`. Levels are mutually exclusive — simulator results are never pooled with hardware results.

| Level | Environment | What It Proves | Smart Factory Status |
|---|---|---|---|
| L0 | Static/schema | Shape and code review | Not formally tracked |
| L1 | Python/C99/C++ host unit | Local algorithms and parsers | Implemented (AMLP parser, CRC, MQTT contract tests) |
| L2 | Simulated UART/MQTT, mock device | Software protocol and application behavior | Implemented (gateway, dashboard, bridge firmware tests); simulator in progress (#10) |
| L3 | ESP32 + real controller (bench) | Electrical and link interoperability | **BLOCKED** — bridge connected to reference endpoint only; no real controller |
| L4 | Moving 9-module subsystem, operator, E-stop | Physical safety and bounded actuation | **BLOCKED** — no physical modules |
| L5 | Factory → gateway → Unity → MiniAlpha (declared mix) | End-to-end scenarios with real/mock declared | **BLOCKED** — all components are physical or blocked |

### 8.1 End-to-End Acceptance Scenarios

| ID | Stimulus | Expected Result | Evidence Level | Status |
|---|---|---|---|---|
| E01 | Normal production | Correlated transport, sort, pack, store completion trace | L5 | **BLOCKED** |
| E02 | Invalid command payload | Error; no physical action | L2 | Implemented (gateway validation) |
| E03 | Duplicate correlation ID | Device action not re-executed | L2 | Implemented (AMLP deduplication) |
| E04 | Bad CRC/oversize AMLP | Rejection and diagnostic | L1/L2 | Implemented (AMLP parser tests) |
| E05 | Jam / sensor timeout | Local safety stop and incident | L4 | **BLOCKED** |
| E06 | Broker disconnect | Stale indication; no unsafe queued execution | L2 | Implemented (gateway stale indicators) |
| E07 | Out-of-order event | Twin state does not roll backward | L5 | **BLOCKED** |
| E08 | Reconnect | Snapshot resync; expired commands rejected | L2 | Implemented (event store contract) |
| E09 | MiniAlpha offline/unsupported skill | Explicit failure; no actuation | L2 | Implemented (mock adapter) |
| E10 | AI unsafe action request | Policy gate rejects; audit present | L2 | Implemented (ADR-0006 safety gate) |
| E11 | Emergency stop | Works locally even without MQTT | L4 | **BLOCKED** |
| E12 | Event replay | Reproducible recorded state and trace | L2 | Implemented (event store contract) |

### 8.2 Issue Definition of Done

Every issue PR must satisfy:
- [x] Scope implemented and linked PR reviewed
- [x] Tests from issue executed and evidence attached
- [x] Negative paths, safety, and disconnect behavior checked
- [x] Schema and documentation updated
- [ ] Hardware tests (when required) include verified voltage, grounding, controlled workspace, operator and E-stop precheck
- [x] Hardware-blocked requirements clearly remain BLOCKED, not skipped as PASS

---

## 9. Scientific KPIs and Measurement Protocol

Research metrics are defined in `docs/experiment-baselines.md` and must only be measured and claimed when actually measured.

### 9.1 Required Metrics

| Metric | Description | When Available |
|---|---|---|
| Sync latency p50/p95/p99 | Gateway → Twin round-trip delay | L5 (physical factory + Twin connected) |
| Message loss rate | Fraction of telemetry events not reaching Twin/dashboard | L5 |
| Duplicate rate | Fraction of duplicate events delivered | L2 (simulator), L5 (physical) |
| Recovery time | Time from broker disconnect to full resync | L2 |
| Anomalous-event detection accuracy | TP/FP/TN/FN on labeled incident dataset | L5 (requires #38 dataset) |
| Robot alert response time | MiniAlpha notification → bounded response | L5 (requires MiniAlpha unit) |
| Production cycle reliability | Fraction of cycles completing without incident | L4/L5 (physical modules required) |

**Critical rule:** Do not invent thresholds or claim PASS without evidence. Every result must be accompanied by a run manifest (run_id, UTC timestamps, commit SHA, branch, schema versions, firmware ID, configuration hash, evidence level, scenario seed, repetition count, fault schedule, clock method, operator/E-stop checklist result, raw-data URI, analysis-script SHA, and status: PASS/FAIL/INCONCLUSIVE/BLOCKED).

### 9.2 Experiment Designs

Five experiment designs are defined in `docs/experiment-baselines.md`:

| Experiment | Question | Status |
|---|---|---|
| E-TA — Telemetry accuracy | Does normalization preserve source event without loss/duplication? | **BLOCKED** physical corpus — L2 contract tests exist |
| E-CL — Command latency | What is the distribution from command creation to acknowledgement and completion? | L2 measurable now; physical BLOCKED |
| E-TS — Twin synchronization fidelity | Does the Twin converge to authoritative state without rollback? | **BLOCKED** — Twin not connected to live pipeline |
| E-SG — Safety-gate false positives/negatives | Does the safety policy reject every unsafe request? | L2 implemented (ADR-0006 gate); HIL verification BLOCKED |
| E-OTA — OTA reliability | Does authenticated update complete safely across fault injection? | **BLOCKED** — physical ESP32-S3 boards not available |

---

## 10. Safety and Non-goals

### 10.1 Safety Requirements

- All physical modules must maintain a **local emergency stop** that operates independently of MQTT, gateway, Twin, or AI.
- Motion bounds and human override must be enforced at the local controller level, not just in software.
- No remote unsupervised actuation is permitted.
- No safety certification claims are made for this research prototype.
- The safety guard (ADR-0006) is **fail-closed**: any request without valid authorization, stale context, or unsupported capability is rejected without physical action.

### 10.2 Explicit Non-goals

- No safety certification claims for production use.
- No fully autonomous rescue claims.
- No fictitious performance figures.
- No simulator results claimed as hardware validation.
- No unlicensed vendor SDK assets, credentials, or private datasets in the public repository.
- No assumptions that a simulator validates physical hardware behavior.

### 10.3 AI Safety Constraints

- AI (MiniAlpha) may not override physical safety interlocks.
- AI may not initiate unapproved physical rescue.
- AI requests are routed through the safety authorization guard (ADR-0006) before any actuator command is emitted.
- Unsupported skills are rejected explicitly with a diagnostic response, not silently ignored.

---

## 11. Research Evidence and Reproducibility

### 11.1 Evidence Archive (Issue #47)

The research evidence archive (Issue #47) is **L2-unblocked** and should be implemented as a follow-up task. It includes:

- Versioned evidence schema
- CI artifact export pipeline
- Version-gated reproducibility manifest
- Raw event logs and command traces retained with releases
- Run manifests for all experiments (Section 9)

### 11.2 Reproducibility Requirements

A result is reproducible only if a clean checkout can:
1. Resolve the recorded dependency versions (repo SHA, firmware image, schema version, simulator/model version, broker version, OS/toolchain)
2. Replay the seed/fault schedule
3. Regenerate the reported values within stated numerical tolerance

Large or sensitive data may be stored outside Git, but its immutable URI, access class, and SHA-256 checksum must remain in the manifest.

### 11.3 Known Data Issues

- **ADR-0009 (Telemetry schema compatibility):** A known mismatch exists between the expected and actual telemetry schema. This requires resolution before the live telemetry pipeline can be validated.
- **ADR-0003 (Unity institutional approval):** The technology deviation from the original Unreal Engine proposal requires formal administrative approval.

---

## 12. Training and Lab Exercises

Eight lab exercises are planned (Issue #49, `docs/research-and-training.md`). All labs beyond the existing bridge are **planned**, not currently delivered.

| Lab | Topic | Mode | Prerequisite |
|---|---|---|---|
| L1 | MQTT command, status, and telemetry concepts | Simulator | None |
| L2 | AMLP frame, CRC, and deduplication | Python/C99 tests | None |
| L3 | Safe conveyor/sorting controller | Mock initially | #10 (simulator) |
| L4 | IoT gateway schema and registry | Synthetic messages | None |
| L5 | Unity 3D factory state + stale indicators | Event replay | #11 (Unity scaffold) |
| L6 | AI anomaly triage and measured errors | Labeled datasets | #14 (anomaly pipeline) |
| L7 | MiniAlpha skill request, terminal feedback | Mock then HIL | #13 (robot adapter) |
| L8 | E2E reliability and safe-stop experiment | Bench/HIL after approval | Physical modules |

For each lab, the deliverable includes: learning objectives, setup instructions, expected output, negative test cases, safe reset procedure, and grading rubric. Technical demos must explicitly state which actions are simulated.

**Owner:** dev-qa  
**Status:** Planned (Issue #49) — **BLOCKED** at L5+ by hardware dependencies

---

## 13. Open Issues and Hardware Blockers

This section is the authoritative hardware blocker register, sourced from `docs/hardware-blocked-issues-audit.md` (generated 2026-10-17, reviewer: vinhphan812, scope: all 24 open issues).

### 13.1 Issues Ready to Claim Now (L2-Unblocked)

| Issue | Title | Owner | Status |
|---|---|---|---|
| #10 | Factory controller simulator | dev-backend | In-progress |
| #11 | Unity Digital Twin project scaffold | dev-backend | In-progress (branch `fix/issue-35-interactive-factory-features`) |
| #15 | Smart Factory dashboard | dev-backend | Implemented (PR #39) |
| #47 | Research evidence archive | devops | Not started |
| #48 | **This report** | dev-pm | This document |
| #49 | Beginner-to-advanced lab exercises | dev-qa | Not started |
| #13 | MiniAlpha mock adapter | dev-backend | L2 mock implementable |
| #14 | Edge anomaly detection pipeline | dev-backend | L2 deterministic rules implementable |
| #73 | Authenticated HTTPS OTA client | dev-backend | L1/L2 state machine implementable |

### 13.2 Hard Physical Blockers

| Blocker | Blocks | Required Action | Owner | Priority |
|---|---|---|---|---|
| No 9-module physical inventory (#9) | #12, #22–26, #68, #20 | Procurement + dimension survey + device IDs + wiring spec | dev-pm | **P0** |
| No Mega board + license clearance (#98) | #58, #59, #60 | Board procurement + UBTECH licensing + voltage measurement | dev-pm | **P0** |
| No ESP32-S3 bench boards (#74) | #73 physical OTA tests | 2× ESP32-S3 for OTA bench matrix | devops | P1 |
| No MiniAlpha unit (#13) | #13 real HIL | Confirm MiniAlpha availability + skill API | dev-pm | P1 |
| No dump truck (#70) | #70 physical | Procurement decision | dev-pm | P2 |
| No parking lot (#71) | #71 physical | Procurement decision | dev-pm | P2 |
| No Unity institutional approval (#11 ADR) | #11 ADR-0003 | Formal deviation approval | dev-pm | **P0** |
| ADR-0009 schema mismatch | Live telemetry pipeline | Schema reconciliation and migration | dev-backend | P1 |

### 13.3 Blocking Dependency Graph

```
L2-unblockable (no hardware needed):
  #10 ──► #22/23/24/25/26 adapter mocks
  #11 ──► #12 (Unity adapter)
  #15   (dashboard — implemented)
  #47/48/49 (docs, report, exercises)
  #13/14 (mock robot + alarm rules)

Simulator chain (#10 is the critical path):
  #10 (factory simulator)
    ├── #12 (Twin state mapping)
    ├── #16 (E2E integration suite)
    ├── #22..26 (module adapter mocks)
    └── #38 (anomaly evaluation fixtures)

Physical chain (#9 is the critical path):
  #9 (9-module inventory + procurement)
    ├── #68 (Unity coordinate calibration)
    ├── #22..26 physical adapters
    └── #20 (HIL test plan)

Mega chain (#98 is the hard blocker):
  #98 (hardware verification + license)
    ├── #58 (Mega UART port)
    ├── #59 (motor/servo adapter)
    └── #60 (CI + recovery guide)

Bridge OTA chain:
  #73 (#74 depends on it)
    └── #74
      └── OTA pipeline + bench tests
```

### 13.4 Recommendations (from hardware-blocked-issues-audit.md)

1. **#10 (factory simulator) is the highest-leverage unblock.** All module adapters (#22–26), integration tests (#16), and Twin state mapping (#12) depend on it. Assign immediately.
2. **#11 (Unity scaffold) is independently unblockable.** Parallel track to #10; no shared dependency.
3. **#98 (Mega hardware + license) is the hardest blocker.** Without it, #58/#59/#60 cannot advance past code review. Requires procurement + legal.
4. **Do not mark simulator-only tests as L4/L5 PASS.** All issues with mixed evidence levels must label each test case L2 vs. L3/L4/L5 explicitly.
5. **#9 procurement is P0 for the physical path.** Until the 9-module inventory exists, #12, #68, #20, and all module adapters remain blocked at L4/L5.

---

## 14. Governance and Repository Policy

### 14.1 Modular Monorepo

The repository follows a modular monorepo structure (ADR-0001). Each component is isolated; cross-component dependencies use versioned contracts. All changes go through pull request review. Work is organized on the Kanban board at `~/.hermes/kanban.db`.

### 14.2 Branch Strategy

- `master` — production-ready, protected, no direct commits
- `feat/...` — new feature delivery branches
- `fix/...` — bug fix and patch delivery branches
- `smart-factory/t_...` — Kanban worktree branches (ephemeral, for task execution)
- `fix/issue-NNN-clean` — issue delivery branches (PR target)
- All PRs require review and CI passing before merge

### 14.3 Issue Lifecycle

1. Issue created with scope, blocking factors, and owner
2. Card created on Kanban board with evidence-level acceptance criteria
3. Work proceeds through: Ready → In Progress → Review → Verification → Done
4. Hardware-blocked issues remain in Backlog until unblocked; they are never closed as PASS without physical evidence
5. Definition of Done includes: tests pass at declared evidence level, documentation updated, BLOCKED items explicitly marked

### 14.4 Master Backlog

All work is triaged through the Master Backlog: [Issue #52](https://github.com/vinhphan812/smart-factory/issues/52)

---

## 15. Handover Checklist

The following items are required to move from the current L2 deliverable state to a complete research output. Items are grouped by principal system and infrastructure.

### 15.1 Critical Path (blocks all physical research claims)

- [ ] **#9 — 9-module procurement and inventory** (owner: dev-pm, P0)
  - [ ] All 9 modules acquired and inventoried
  - [ ] Device IDs assigned and registered in `docs/device-registry.md`
  - [ ] Physical wiring specification produced (voltage, connectors, grounding, E-stop chain)
  - [ ] Coordinate survey completed (dimensions, positions, orientations)
  - [ ] Local controller firmware loaded with safe-motion limits

- [ ] **#98 — Mega hardware + licensing** (owner: dev-pm, P0)
  - [ ] Arduino Mega board + level shifter procured
  - [ ] Voltage measured and documented
  - [ ] UBTECH licensing clearance obtained
  - [ ] Partition layout documented for #58/#60

- [ ] **ADR-0003 — Unity institutional approval** (owner: dev-pm, P0)
  - [ ] Formal deviation from Unreal Engine to Unity approved in writing

- [ ] **ADR-0009 — Telemetry schema reconciliation** (owner: dev-backend, P1)
  - [ ] Known mismatch resolved
  - [ ] Migration plan documented
  - [ ] Schema tests updated

### 15.2 S1 Physical Factory

- [ ] **#22/23/24 — Conveyor/Sorting/Packaging module adapters** (L3 physical)
  - [ ] Real adapter implementation against physical controllers
  - [ ] Voltage-verified wiring
  - [ ] HIL test card with E-stop precheck
- [ ] **#25/26 — Forklift + Tower crane logistics** (L4 physical)
  - [ ] Dump truck (#70) and parking lot (#71) procurement decisions made
  - [ ] Mock adapters L2 complete (no hardware needed)
  - [ ] Physical L4 adapters implemented when units available

### 15.3 S2 Digital Twin

- [ ] **#11 — Unity scaffold** (L2)
  - [ ] Interactive factory features merged
  - [ ] EditMode/PlayMode tests passing
  - [ ] Mock event adapter implemented (depends on #10)
- [ ] **#12 — Live gateway-to-Twin mapping** (L5)
  - [ ] Mock adapter (L2) complete
  - [ ] Physical adapter (L5) BLOCKED by #9 + #11 + #10
- [ ] **#68 — Coordinate calibration** (L4)
  - [ ] Calibration format defined (L2)
  - [ ] Physical calibration BLOCKED by #9

### 15.4 S3 AI Edge Robot

- [ ] **#13 — MiniAlpha unit confirmation** (owner: dev-pm, P1)
  - [ ] Physical unit available
  - [ ] Skill API boundary verified
  - [ ] Real HIL integration

### 15.5 Infrastructure

- [ ] **#47 — Research evidence archive** (L2, owner: devops)
  - [ ] Evidence schema designed
  - [ ] CI artifact export pipeline implemented
  - [ ] Version-gated reproducibility manifest produced
- [ ] **#49 — Lab exercises** (L2, owner: dev-qa)
  - [ ] All 8 labs designed and documented
  - [ ] Exercises validated against simulator
- [ ] **#16 — E2E integration suite** (L2/L5)
  - [ ] L2 mock orchestration implemented
  - [ ] L5 suite BLOCKED by all physical dependencies
- [ ] **#20 — HIL test matrix** (L4)
  - [ ] L1/L2/L3/L4/L5 taxonomy in `docs/qa/hil-plan.md`
  - [ ] Physical test cards BLOCKED until bench ready

### 15.6 OTA Pipeline

- [ ] **#74 — OTA release pipeline + staged rollout** (L3)
  - [ ] CI release job implemented
  - [ ] Physical OTA bench tests BLOCKED by #73 + ESP32-S3 boards

---

## 16. References

### Architecture Decisions

- ADR-0001: Modular monorepo structure — `docs/adr/adr-0001-modular-monorepo.md`
- ADR-0002: Bridge MQTT↔AMLP contract — `docs/adr/adr-0002-bridge-mqtt-amlp-contract.md`
- ADR-0003: Digital Twin engine (Unity) — `docs/adr/adr-0003-digital-twin-engine.md` ⚠️
- ADR-0004: Mega SDK boundary — `docs/adr/adr-0004-mega-sdk-boundary.md`
- ADR-0005: Gateway canonical events — `docs/adr/adr-0005-gateway-canonical-events.md`
- ADR-0006: Local physical safety — `docs/adr/adr-0006-local-physical-safety.md`
- ADR-0007: Signed OTA A/B rollback — `docs/adr/adr-0007-signed-ota-ab-rollback.md`
- ADR-0008: Event-driven OtaManager — `docs/adr/adr-0008-ota-manager-event-driven.md`
- ADR-0009: Telemetry schema compatibility — `docs/adr/adr-0009-telemetry-schema-compatibility.md` ⚠️
- ADR-0010: MQTT broker security — `docs/adr/adr-0010-mqtt-broker-security.md`
- ADR-0011: Dashboard safety — `docs/adr/adr-0011-dashboard-safety.md`
- ADR-0012: Unity prefab contracts — `docs/adr/adr-0012-unity-digital-twin-prefab-contracts.md`

### Specifications and Contracts

- Project Context: `docs/PROJECT_CONTEXT.md`
- Architecture Overview: `docs/architecture/overview.md`
- Contracts and Data: `docs/contracts-and-data.md`
- Testing and Acceptance: `docs/testing-and-acceptance.md`
- Experiment Baselines: `docs/experiment-baselines.md`
- Research and Training: `docs/research-and-training.md`
- Device Registry: `docs/device-registry.md`
- Command Authorization Contract: `docs/issue-30-command-authz-contract.md`
- Event Store Contract: `docs/issue-31-event-store-contract.md`
- Event Store Follow-up: `docs/issue-31-followup.md`
- Unity Prefab Contracts: `docs/twin/prefab-module-contracts.md`
- Robot Notification Contract: `docs/alerts/notification-contract.md`
- Integration Test Plan: `docs/issue-44-integration-test-plan.md`
- QA Test Plan: `docs/issue-45-qa-test-plan.md`
- 12-Month Research Milestones: `docs/issue-18-research-milestones.md`
- Hardware Blocked Issues Audit: `docs/hardware-blocked-issues-audit.md` ← primary blocker register

### Source Code

- ESP32–UKIT Bridge: `esp32-ukit-bridge/`
- Factory Simulator: `factory-control/` (in progress — Issue #10)
- IoT Gateway: `iot-gateway/`
- Dashboard: `dashboard/`
- Digital Twin: `digital-twin/` (scaffold — Issue #11)
- Edge AI Robot: `edge-ai-robot/` (mock — Issue #13)
- Integration Tests: `integration-tests/`
- Infrastructure: `infrastructure/`

### Related Issues

| # | Title | Status |
|---|---|---|
| #9 | 9-module physical factory interface | BLOCKED |
| #10 | Factory controller simulator | In-progress |
| #11 | Unity Digital Twin project scaffold | In-progress |
| #12 | Live gateway-to-Unity state mapping | BLOCKED |
| #13 | MiniAlpha connectivity | L2 mock done; physical BLOCKED |
| #14 | Edge anomaly detection pipeline | L2 implementable |
| #15 | Smart Factory dashboard | Implemented |
| #16 | E2E acceptance suite | L2 partial; L5 BLOCKED |
| #20 | HIL test matrix | BLOCKED |
| #22–26 | Module adapters | BLOCKED |
| #38 | Anomaly model evaluation | BLOCKED |
| #47 | Research evidence archive | Not started |
| #48 | This report | **This document** |
| #49 | Lab exercises | Not started |
| #52 | Master Backlog | [GitHub Issue](https://github.com/vinhphan812/smart-factory/issues/52) |
| #58/59/60 | Mega adapter + CI | BLOCKED by #98 |
| #68 | Twin coordinate calibration | BLOCKED |
| #70/71 | Dump truck + parking lot | BLOCKED (not in procurement plan) |
| #73 | Authenticated HTTPS OTA client | L1/L2 implementable |
| #74 | OTA release pipeline | BLOCKED |
| #81 | ADR backfill | In progress |
| #98 | Mega HIL verification + license | BLOCKED (hardest blocker) |

---

*This report was generated as a Level 2 deliverable (Issue #48). Physical-result sections are marked BLOCKED pending hardware procurement and institutional approvals. The report will be updated with physical evidence as hardware blockers are resolved. All claims in this document are backed by linked ADR, contract, or issue references. No simulator result is claimed as hardware evidence.*
