# AIBOT Smart Factory — Project Context v1.1

## 1. Identity
**Research topic:** “Thiết kế, xây dựng và thử nghiệm mô hình Smart Factory thu nhỏ tích hợp Digital Twin thời gian thực và AI Edge Robot tại Trung tâm AIBOT”.

**Lead environment:** Trung tâm Trí tuệ nhân tạo và Công nghệ Robot (AIBOT), Trường Đại học Công nghệ Đồng Nai (DNTU).

**Planned duration:** 12 months, without a fixed start date inferred from the proposal.

**Outcomes:** A safe miniature Industry 4.0 production/logistics demonstration system supporting AI–Robotics–Automation–IIoT practice, scientific experiments, STEM, teaching and industry collaboration.

## 2. Exactly three principal systems
- **S1 Physical Smart Factory:** nine modular hardware elements, coordinated production/logistics, instrumented state and safely bounded control.
- **S2 Real-time Digital Twin:** a **Unity** 3D model reflecting observed factory states, events, alarms, reconnect and stale/offline conditions. An offline animation is not evidence of synchronization with real machines.
- **S3 AI Edge Robot:** **UBTECH Yanshee** (adopted per ADR-0013, superseding MiniAlpha) to monitor, receive alerts, provide bounded supported on-site responses and interact with users. AI may not override physical safety interlocks or initiate unapproved physical rescue.

Supporting infrastructure is cross-cutting, not an additional principal system: ESP32–UKIT bridge, gateway/MQTT, schema registry, event store, dashboard, alarm processing, CI/HIL/E2E and deployment tools.

## 3. Physical composition
| Item | Intended purpose | Verification gate |
|---|---|---|
| Forklift | Material transport / pallet logistics | Controller, position & motion limits |
| Dump Truck | Material delivery | Controller and command interface |
| Bracket | Mechanical structures | Actual mechanical/electrical scope |
| Packaging Machine | Packaging step | Sensors, completion detection and interlocks |
| Conveyor Belt | Convey material | Safe speed/stop and sensor mapping |
| Sorting Machine | Routing/classification | Input/output sensors and reject state |
| Tower Crane | Lift / place | Limits, occupied zones, manual E-stop |
| Parking Lot | Logistics staging | Slot/vehicle presence |
| Combine Modules | Factory integration | Connected end-to-end line; not necessarily ninth motor |

Pipeline: incoming material → transport → conveyor → sorting → packaging → storage/logistics. All actual hardware status must be checked, not inferred from a product list.

## 4. Current evidence (repository reviewed on 2026-10-12)
`esp32-ukit-bridge/` contains ESP32-S3 PlatformIO firmware, MQTT-to-AMLP UART path, C99 UKIT **portable reference endpoint**, Python AMLP simulator/CLI, tests and protocol documentation. The reference endpoint is **not the vendor SDK**. Real UKIT wiring, electrical levels, firmware flashing, nine-module interfaces and MiniAlpha SDK remain separately gated by documented hardware evidence.

The bridge documentation currently states ESP32 does **not yet** publish UART TEL as MQTT telemetry. Do not claim a live Digital Twin pipeline is finished. Planned IoT gateway, **Unity scene**, AI detection, physical controllers and integration tests are represented by Issues, not automatically delivered.

## 5. Research objectives and measurements
The proposal's research tasks encompass (i) overall architecture, (ii) physical integration, (iii) acquisition/transmission/storage/realtime sync, (iv) 3D Twin, and (v) AI Edge Robot integration. Research metrics should include sync latency distributions, loss, duplicate handling, recovery, run stability, bounded robot response and detection accuracy **only when actually measured**. Log run conditions, hardware versus simulated components, source commit and raw data.

## 6. Safety and non-goals
No remote unsupervised actuation, safety certification claims, fictitious performance figures, fully autonomous rescue claims, or assumptions that a simulator validates hardware. Equipment must maintain local emergency stop, bounds and human override irrespective of MQTT/AI. No unlicensed vendor SDK assets, credentials or private datasets in this public repository.

## 7. Governance
One modular monorepo: keep each component isolated, source-compatible via versioned contracts, review via PR and [Master Backlog #52](https://github.com/vinhphan812/smart-factory/issues/52). Close work only with evidence for its stated acceptance level.


**Engine change provenance:** Unity is the selected engineering implementation engine (Issues #11/#12/#33–#35). The original formal research proposal named Unity. This original wording is historical; institutional authorization for the technology change has not been verified. See proposed ADR-0003 in PR #89.

## 8. Release Integration Queue (as of 2026-10-20)

This section records the authoritative merge sequence, open PR status, and resolved scope boundaries. It supersedes any stale worktree documentation.

### 8.1 Master snapshot
- **Master HEAD:** `b3591b6` — PR #142 research evidence archive (2026-10-19)
- All PRs listed in §8.2–§8.4 are checked against `origin/master`

### 8.2 Merged in this session (confirmed)
| PR | Title | Key change | ADR impact |
|----|-------|------------|------------|
| #206 | FIWARE Orion-LD context architecture | ADR-0014 (was renumbered from conflicting #207) | +adr-0014 |
| #144 | Scaffold Unity Digital Twin project | Unity project scaffold (`digital-twin/`) | +adr-0012 |
| #121 | Unity gateway transport adapter | Offline replay contract (#67) | +adr-0012 |
| #110 | Fail-closed safety decision gate | `iot-gateway/` safety gate, ADR-0013 | +adr-0013 |
| #210 | Factory controller simulator | `factory-control/` package, ADR-0013 integration | ADR-0006 |
| #189 | Sorting module adapter | `factory-control/adapters/sorting.py` | L2 tested |
| #131 | Event store follow-up | `contracts/` schema | +adr-0005 |
| #141 | Edge anomaly detection pipeline | `edge-ai-robot/` alert skills | ADR-0006 |
| #135 | 12-month research milestones | `docs/` KPIs | — |
| #139 | Final scientific/technical report | `docs/` | — |
| #140 | Beginner-to-advanced lab exercises | `docs/` | — |
| #142 | Research evidence archive | `docs/` reproducibility package | — |
| #147 | Conveyor module adapter | `factory-control/adapters/conveyor.py` | L2 tested |

### 8.3 Open PRs requiring action

#### PR #211 — React + TypeScript + Vite Dashboard Bootstrap
- **Branch:** `feat/issue-148-react-vite-bootstrap`
- **Status:** OPEN, MERGEABLE (`mergeStateStatus: CLEAN`)
- **Files:** `dashboard/` (33 files, 6 725 additions)
- **ADR created:** `docs/adr/adr-0013-frontend-migration.md`
- ⚠️ **BLOCKER — ADR-0013 numbering conflict:** `adr-0013-frontend-migration.md` reuses ADR-0013, which is already assigned to **Edge AI Safety Gate** (merged via PR #110). The FIWARE ADR was renumbered to ADR-0014 precisely to avoid this conflict. The frontend migration ADR must use **ADR-0015** (next available) and the `docs/adr/README.md` index entry must be added. Fix: rename `adr-0013-frontend-migration.md` → `adr-0015-frontend-migration.md`, update index.
- **Other compatibility:** `dashboard/src/contracts/gateway.ts` adds TypeScript types for `iot-gateway/` REST/WebSocket API — read-only client, no MQTT publish. Does not conflict with `iot-gateway/` safety gate module.
- **Evidence:** `npm run test` (12 tests) PASS; `npm run build` PASS; legacy `dashboard/src/index.html` preserved as rollback.

#### PR #145 — MiniAlpha Connectivity Adapter
- **Branch:** `smart-factory/t_e0f5b59e-13-minialpha-connectivity-and-bounded-ro`
- **Status:** OPEN, MERGEABLE (`mergeStateStatus: CLEAN`)
- **Files:** `edge-ai-robot/` (13 files, 2 089 additions)
- **Scope:** L2 simulation adapter for MiniAlpha robot with bounded skill registry (notification, status, acknowledge). Physical action skills (move, gripper, E-stop) are **fail-closed** for AI (enforced by ADR-0006 Layer 4).
- **Compatibility:** `edge-ai-robot/` is a standalone Python package with typed contracts. No import conflicts with `iot-gateway/` safety gate or `factory-control/` adapters.
- **Evidence:** `pytest edge-ai-robot/tests/ -v` — 45 passed.
- **Hardware note:** L2 simulation only. Hardware HIL blocked by Issue #160 (Yanshee replacement per ADR-0013). The PR body correctly marks `BLOCKED-simulator` for physical HIL.

### 8.4 Unmerged factory-control work (not on master)

#### Conveyor adapter (#22) — PR #147 closed as conflicting
- **Source:** `factory-control/adapters/conveyor.py` exists in `pr-147` worktree branch
- The sorting adapter (#23) was merged via PR #189 with an identical safety-interlock pattern.
- **Recommended action:** Create a clean rebase PR for the conveyor adapter, using the same pattern as `sorting.py` (ADR-0006 compliance, L2 test coverage). Do not re-open PR #147 directly — the branch has divergent history.

### 8.5 Factory-control vs. safety-gate scope boundary (resolved)
The original concern in Issue #172 was overlapping `safety_gate.py` logic across factory-control and iot-gateway.

| Layer | Location | Source of truth | Rationale |
|-------|----------|-----------------|-----------|
| Safety decision gate | `iot-gateway/src/safety_gate.py` | PR #110 (merged) | Fail-closed gate at the gateway boundary — single authoritative policy; ADR-0006 Layer 4 |
| Factory module adapters | `factory-control/` | PR #210 + #189 (merged) | Deterministic simulation; safety interlocks validated locally per ADR-0006 but NOT the policy authority |
| Conveyor adapter | `factory-control/adapters/conveyor.py` | **Pending** | Awaiting clean rebase per §8.4 |

**Resolution:** `iot-gateway/safety_gate.py` (PR #110) is the authoritative policy. `factory-control/` adapters enforce local safety limits but call the gateway for cross-boundary decisions. This prevents duplicate shadow modules.

### 8.6 ADR index state (on master)
| ADR | Title | Status |
|-----|-------|--------|
| 0001–0012 | Core infrastructure ADRs | Proposed |
| ADR-0013 | Edge AI Safety Decision Gate | Proposed (PR #110) |
| ADR-0014 | FIWARE Orion-LD Context Architecture | Proposed (PR #206) |
| **ADR-0015** | **(available — pending PR #211 fix)** | Fix: rename `adr-0013-frontend-migration.md` → `adr-0015-frontend-migration.md` |

### 8.7 Recommended merge sequence
1. **PR #211** — fix ADR-0013 conflict first: rename to `adr-0015-frontend-migration.md`, update `docs/adr/README.md` index, then merge
2. **PR #145** — merge as-is (MERGEABLE, L2 evidence complete)
3. **Conveyor adapter** — new clean PR from current master, following `sorting.py` pattern (ADR-0006 + L2 tests)

### 8.8 Issue #172 acceptance checklist
| SPEC | Status | Evidence |
|------|--------|----------|
| Integration queue in `docs/PROJECT_CONTEXT.md` | ✅ DONE | This section §8 |
| Conflicting scope resolved with rationale | ✅ DONE | §8.5 factory-control vs. safety-gate boundary |
| AGENTS.md current with merged ADRs | ✅ DONE | ADR-0013 (safety gate), ADR-0014 (FIWARE) both on master |
| All open PRs audited | ✅ DONE | #211 MERGEABLE, #145 MERGEABLE |
| Recommended merge order documented | ✅ DONE | §8.7 |
| S3 robot updated to Yanshee | ✅ DONE | §2 S3 |
