# Issue #18 — 12-Month Research Milestones and KPIs

**Author:** agent
**Reviewer:** vinhphan812
**Status:** draft
**Branch:** `docs/issue-18-research-milestones`
**Parent:** Master Backlog [#52](https://github.com/vinhphan812/smart-factory/issues/52)
**Related ADRs:** ADR-0003 (Digital Twin engine), ADR-0006 (local physical safety)
**Proposal basis:** 12-month research proposal, five work packages (16.1–16.5), PROJECT_CONTEXT.md §5
**Sister docs:** `docs/issue-43-latency-measurement-plan.md`, `docs/issue-44-integration-test-plan.md`, `docs/ROADMAP.md`

---

## 1. Research Objectives (Proposal §16.1–16.5)

The research proposal's five scientific work packages map directly to these objectives. Each is scoped to the installed hardware and verified evidence level; no claims are made beyond implemented capability.

### 16.1 — Overall Architecture and System Integration

Design and validate a modular monorepo architecture integrating nine physical factory modules, ESP32–UKIT bridge, IoT gateway, event store, and MQTT contract. Deliverable: architecture specification, module ownership table, versioned cross-system schemas in `contracts/`, and CI pipeline operational at L0–L2.

**Milestone:** Module boundaries defined (ADR-0001); bridge–gateway MQTT contract stable (ADR-0002); gateway canonical event envelope adopted (ADR-0005); repository layout and ownership enforced.

### 16.2 — Physical Factory Integration

Establish and instrument the nine-module physical factory floor: forklift, dump truck, conveyor belt, sorting machine, packaging machine, tower crane, parking lot, bracket structures, and combine modules. Deliverable: wiring documentation, controller firmware, safety interlocks, and E-stop verification. **Hardware evidence gated by Issue #98 (HIL Safety Certification).**

**Milestone:** All nine modules mapped in `device-registry.json`; local safety enforced per ADR-0006 Layer 3; bring-up prerequisites satisfied per `docs/hardware-readiness.md`.

### 16.3 — Data Acquisition, Transmission, and Real-Time Synchronization

Implement and measure the full event pipeline: device sensor → local controller → ESP32 bridge → MQTT broker → IoT gateway → event store → WebSocket broadcast. Deliverable: latency, jitter, loss, and duplicate rate distributions per run manifest (see `docs/issue-43-latency-measurement-plan.md` §5 YAML template).

**Milestone:** Canonical event envelope (ADR-0005) implemented; `canonical_sequence` and snapshot table delivered (Issue #31); telemetry schema mismatch resolved (ADR-0009, Issue #66); L2 measurement harness operational with ≥300 s runs at steady and burst rates.

### 16.4 — 3D Digital Twin (Unity)

Build and verify a Unity 3D scene reflecting real-time factory state, with stale/offline indication, reconnect snapshot, and event replay. Deliverable: Unity project in `digital-twin/`, prefab contracts per ADR-0012, time-sync protocol per `docs/issue-34-unity-time-sync-contract.md`, and transport adapter per `docs/issue-67-unity-gateway-transport-contract.md`. **Institutional approval for Unity over the original proposal engine is PENDING/NOT VERIFIED (ADR-0003).**

**Milestone:** Unity scene renders factory topology; gateway→Twin adapter delivers canonical events; stale state indicator appears within [threshold TBD by sponsor] of broker disconnect; reconnect syncs last known state.

### 16.5 — AI Edge Robot Integration (MiniAlpha)

Integrate MiniAlpha as a bounded alert and response agent. AI may generate proposals; operator approval is required before any action per ADR-0006 Layer 4. Deliverable: skill request/response contract, bounded alert delivery, unsupported capability failure mode, and measured false-alarm rate. **MiniAlpha SDK and procurement are BLOCKED (Issue #98).**

**Milestone:** MiniAlpha mock delivers bounded alerts; approval-gate API designed; unsupported skill returns explicit failure (E09); false-positive/negative counts measured against labeled dataset (planned Lab 6).

---

## 2. Measurable KPIs

All KPI thresholds require sponsor approval before being declared pass/fail criteria. Raw distributions and run manifests are published regardless of outcome. Do not invent thresholds.

### 2.1 Sync Latency (p50 / p95 / p99)

- **Definition:** Per `docs/issue-43-latency-measurement-plan.md` §2: `observed_latency_ms = gateway_mqtt_received_at_ms − device_timestamp_ms`.
- **Segments:** UART→ESP32, ESP32→broker, broker→gateway, gateway→consumer (WS broadcast instrumentation is NOT YET IMPLEMENTED — see §5).
- **Reporting:** Per-device p50/p95/p99; jitter per-device mean and distribution; negative-latency events disclosed (clock offset artifact).
- **Sponsor approval required for:** any p95 or p99 ceiling used in SLO declarations.
- **Current evidence level:** L2 (simulated MQTT); L3/L4 blocked by hardware availability.

### 2.2 Event Loss Rate

- **Definition:** `loss_rate = 1 − (msg_count_stored / msg_count_sent)` over the measurement window.
- **Counted causes:** MQTT QoS-0 drops, gateway write-queue overflow, quarantine rejection. Duplicate event IDs are counted separately in `duplicate_rate`.
- **Reporting:** Per-run; broker type and version; gateway queue capacity config.
- **Sponsor approval required for:** any declared loss-rate ceiling.
- **Current evidence level:** L2 only; hardware-level loss unmeasured until L3.

### 2.3 Operational Stability

- **Stability window:** Continuous run duration without gateway crash or unhandled exception; logged per run manifest `run_duration_s`.
- **Reconnect recovery time:** Time from broker disconnect to first event after reconnect; reported as `reconnect_time_ms` per `docs/issue-43-latency-measurement-plan.md` §5.
- **Out-of-order event count:** Events arriving with `canonical_sequence` lower than the last observed sequence; disclosed per run manifest.
- **Stale event count:** Events marked `is_timestamp_synchronized=False`; must not be silently excluded.
- **Sponsor approval required for:** any stability SLO (e.g., uptime %).

### 2.4 Scenario Coverage (End-to-End Acceptance Scenarios)

Per `docs/testing-and-acceptance.md`, the following scenarios must be exercised and evidence attached:

| ID | Stimulus | Evidence required |
|----|----------|-------------------|
| E01 | Normal production cycle | Correlated transport, sort, pack, store trace |
| E02 | Invalid command payload | Error logged; no physical action |
| E03 | Duplicate correlation ID | Action not re-executed |
| E04 | Bad CRC / oversize AMLP | Rejection and diagnostic logged |
| E05 | Jam / sensor timeout | Local safety stop; incident logged |
| E06 | Broker disconnect | Stale indication; no unsafe queued execution |
| E07 | Out-of-order event | Twin state does not roll backward |
| E08 | Reconnect | Snapshot resync; expired commands rejected |
| E09 | MiniAlpha offline / unsupported skill | Explicit failure; no actuation |
| E10 | AI unsafe action request | Policy gate rejects; audit present |
| E11 | Emergency stop | Works locally without MQTT |
| E12 | Event replay | Reproducible recorded state and trace |

**Sponsor approval required for:** any scenario pass/fail criterion.

### 2.5 Robot Reaction (MiniAlpha)

- **Bounded alert delivery:** Confirmed receipt of alert within [threshold TBD by sponsor].
- **Unsupported capability:** Returns explicit failure (E09); no silent fallback.
- **Approval-gate compliance:** AI proposals held in `requested` state until operator confirms; no bypass observed.
- **False-alarm rate:** `false_positive_count / total_alerts` on labeled anomaly dataset.
- **Sponsor approval required for:** any false-alarm-rate ceiling or response-time SLO.

### 2.6 Usability

- **Lab exercise coverage:** 8 planned labs (L1–L8 in `docs/research-and-training.md`); each requires learning objectives, setup, expected output, negative cases, safe reset, and grading rubric.
- **Recovery documentation:** Operator runbook covering E-stop, reconnect, jam recovery, and state reset.
- **Dashboard usability:** Command console and Twin interface meet criteria TBD by sponsor (Issue #40 contract).

---

## 3. Baseline Methodology — Equipment Readiness vs. Implementation

**Critical rule:** Every run manifest must record whether the run uses simulated or physical components, and the source commit SHA. Simulation results are not evidence of physical performance.

### Equipment Readiness Dimension

Tracks whether physical hardware is procured, wired, and safe to operate:

| Component | Readiness status | Blocker |
|-----------|-----------------|---------|
| ESP32-S3 bridge | Partial | Firmware stubs for GPIO; Wi-Fi tested in lab |
| Arduino MEGA 2560 | Partial | UART tested in native build; real hardware firmware not deployed |
| MX0508 level shifter | Available | Physical logic-level verification BLOCKED |
| Nine factory modules | NOT PROCURED | Issue #98 |
| MiniAlpha Robot | NOT PROCURED | Issue #98 |
| MQTT broker | Available | ACLs not configured |

See `docs/hardware-readiness.md` for full status table. Issue #98 gates all physical HIL testing.

### Implementation Dimension

Tracks which software components are coded, tested, and merged:

| Component | Implementation status | Evidence level |
|-----------|----------------------|---------------|
| ESP32 bridge MQTT contract | Implemented | L1–L2 unit; L3 blocked |
| ESP32→AMLP UART path | Implemented | L1 native build; L3 blocked |
| Python AMLP simulator | Implemented | L2 |
| IoT gateway (event normalize/store/broadcast) | Partial | L2 mock; WS broadcast timestamp instrumentation NOT IMPLEMENTED |
| Canonical event schema (ADR-0005) | Partial | Gap: `canonical_sequence`, snapshot table (Issue #31) |
| Telemetry schema compatibility | KNOWN MISMATCH | ADR-0009; resolved via Issue #66 |
| Unity Digital Twin | NOT IMPLEMENTED | BLOCKED |
| MiniAlpha adapter | NOT IMPLEMENTED | BLOCKED |
| CI/HIL/E2E pipeline | Partial | L0–L2 CI; HIL blocked |

### Run Manifest Declaration

Every experiment run must declare:

```yaml
run_id: "<uuid>"
commit: "<git SHA>"
firmware_version: "<ESP32 tag | L2 simulator>"
start_iso: "<ISO 8601 UTC>"
level: "L2 | L3 | L4"
simulated_components: ["<component>", ...]   # hardware NOT in loop
physical_components: ["<component>", ...]   # hardware in loop
results:
  latency_p50_ms: <float or null>
  latency_p95_ms: <float or null>
  latency_p99_ms: <float or null>
  loss_rate: <float or null>
  duplicate_rate: <float or null>
  reconnect_time_ms: <float or null>
  stale_event_count: <int>
criteria_pass: null   # set by reviewer after evidence review
notes: "<context, anomalies, deviations>"
```

---

## 4. 12-Month Timeline

Months are **relative proposals**, not authorized calendar deadlines. Stages A–F from `docs/ROADMAP.md`. No threshold values are pre-declared as pass/fail; all require sponsor approval.

### Phase 1 — Foundation (Months 1–2)

**Milestone F1:** Architecture and governance stable.

| # | Task | Deliverable | Evidence |
|---|------|-------------|----------|
| F1.1 | Finalize module ownership and monorepo boundaries | `docs/architecture/repository-layout.md` updated | ADR-0001 merged |
| F1.2 | Stabilize bridge–gateway MQTT contract | ADR-0002 merged; `mqtt-contract.md` v1.0 | L1 tests passing |
| F1.3 | Define canonical event envelope | ADR-0005 merged; `contracts/v1/` examples validated | L0 schema review |
| F1.4 | Design local physical safety layers | ADR-0006 merged | Architecture review |
| F1.5 | Assess Unity institutional approval status | ADR-0003 reviewed; amendment status documented | PR to sponsor |
| F1.6 | CI pipeline operational at L0–L2 | GitHub Actions pass on `esp32-ukit-bridge/` | CI green |

**Sponsor action required:** Confirm Unity technology-change approval status.

### Phase 2 — Device and Data Simulation (Months 2–4)

**Milestone F2:** Simulated production pipeline operational end-to-end at L2.

| # | Task | Deliverable | Evidence |
|---|------|-------------|----------|
| F2.1 | Python AMLP simulator with configurable fault injection | `amlp-sim/` with FI-01 to FI-06 scenarios | L2 tests |
| F2.2 | IoT gateway ingest, normalize, event store, WS broadcast | Gateway functional at L2 | Integration tests |
| F2.3 | Resolve telemetry schema mismatch | ADR-0009 resolution path; Issue #66 addressed | Schema validation |
| F2.4 | Device registry wired to gateway normalizer | Issue #32 resolved | Registry lookup tests |
| F2.5 | Event store with `canonical_sequence` and snapshot table | Issue #31 resolved | L2 replay tests |
| F2.6 | Capture latency harness operational | `scripts/capture_latency.py`; ≥300 s runs complete | Run manifests published |

**Sponsor action required:** Review and approve KPI measurement methodology.

### Phase 3 — 3D Twin and Robot Adapters (Months 4–7)

**Milestone F3:** Unity scene reflects simulated factory state; MiniAlpha adapter designed.

| # | Task | Deliverable | Evidence |
|---|------|-------------|----------|
| F3.1 | Unity project bootstrap | Issue #11 resolved; editor version documented | Build artifacts |
| F3.2 | Unity Digital Twin prefab contracts | ADR-0012 merged | L0 contract review |
| F3.3 | Gateway→Unity transport adapter | Issue #67 resolved | L2 event delivery to Twin |
| F3.4 | Unity time synchronization protocol | Issue #34 resolved | Clock-sync test |
| F3.5 | Stale/offline indication in Twin | Twin shows `unknown` when telemetry delayed | L2 disconnect test |
| F3.6 | Reconnect snapshot resync | Issue #34 §6 | L2 reconnect test |
| F3.7 | MiniAlpha adapter contract | Issue #13 design; skill request/response schema | Mock integration |
| F3.8 | AI approval-gate API | ADR-0006 Layer 4 implemented in gateway | E10 scenario passes |
| F3.9 | Command console | Issue #40 resolved; role-based access enforced | E02/E03 scenario passes |

**Sponsor action required:** Approve Unity scene scope and MiniAlpha skill catalogue.

### Phase 4 — Physical Integration (Months 5–9)

**Milestone F4:** Hardware bring-up, local safety verified, staged HIL begins. **Gated by Issue #98.**

| # | Task | Deliverable | Evidence |
|---|------|-------------|----------|
| F4.1 | Physical bring-up prerequisites confirmed | `docs/hardware-readiness.md` §Bring-up Prerequisites satisfied | Hardware checklist |
| F4.2 | ESP32 bridge → MEGA UART verified at L3 | Logic-level confirmed; AMLP round-trip at bench | L3 evidence |
| F4.3 | Local safety interlocks confirmed at L4 | ADR-0006 Layer 3 verified; E-stop works without MQTT | L4 evidence |
| F4.4 | Nine-module wiring and controller firmware | Modules mapped in device registry; firmware deployed | L4 evidence |
| F4.5 | Telemetry pipeline verified at L3 | Bridge→broker→gateway confirmed with real ESP32 | L3 run manifests |
| F4.6 | HIL integration test suite | Issue #98 resolved; safety certification checklist | L4 evidence |

**Sponsor action required:** Approve HIL workspace, operator safety briefing, and E-stop verification sign-off.

### Phase 5 — End-to-End Experiments (Months 8–11)

**Milestone F5:** All 12 E2E scenarios exercised at highest available evidence level; raw data published.

| # | Task | Deliverable | Evidence |
|---|------|-------------|----------|
| F5.1 | All 12 scenarios (E01–E12) exercised | Run manifests for each scenario at L3/L4 | Attached to PR |
| F5.2 | Latency distribution at L3/L4 | Run manifests with p50/p95/p99 published | Sponsor review |
| F5.3 | Event loss and duplicate rate measured | Loss rate and duplicate rate per run manifest | Sponsor review |
| F5.4 | Anomaly dataset and false-alarm measurement | Labeled dataset; false-positive/negative counts | Sponsor review |
| F5.5 | MiniAlpha bounded alert measured | E09, E10 confirmed; false-alarm rate on dataset | Sponsor review |
| F5.6 | Stability and reconnect benchmarks | `reconnect_time_ms`, `stale_event_count`, uptime | Sponsor review |
| F5.7 | E2E reliability and safe-stop experiment | Lab 8 completed; reproducibility confirmed | Run manifest + log |

**Sponsor action required:** Review raw data; approve or adjust KPI thresholds.

### Phase 6 — Education and Handover (Months 11–12)

**Milestone F6:** Scientific report drafted; lab guides complete; handover documentation ready.

| # | Task | Deliverable | Evidence |
|---|------|-------------|----------|
| F6.1 | Scientific report draft | Sections covering all five work packages; raw data cited | Sponsor review |
| F6.2 | Eight lab exercises (L1–L8) | Learning objectives, setup, expected output, grading rubric | Review by educators |
| F6.3 | Operator runbook | E-stop, reconnect, jam recovery, state reset procedures | Tested by operator |
| F6.4 | Recovery and reproducibility documentation | Run manifest templates; reproducible SHA pinned | Audit trail |
| F6.5 | Unity Twin usability assessment | [TBD by sponsor criteria] | User testing |
| F6.6 | Final PR and repository state | All open issues linked; evidence attached | vinhphan812 review |

**Sponsor action required:** Approve final report and lab guide content.

---

## 5. What Is NOT Yet Implementable

The following are explicitly **not** within scope for the current implementation until hardware/procurement/institutional approval evidence exists. Each entry is tracked to an open issue.

| Item | Status | Blocker |
|------|--------|---------|
| ESP32 UART TEL → MQTT publish | NOT IMPLEMENTED | Bridge firmware gap; see `docs/architecture/overview.md` |
| Gateway WS broadcast timestamp instrumentation | NOT IMPLEMENTED | `issue-43-latency-measurement-plan.md` §6 gap |
| `canonical_sequence` in event store | NOT IMPLEMENTED | Issue #31 |
| Telemetry schema canonical promotion | KNOWN MISMATCH | ADR-0009; Issue #66 |
| Unity Digital Twin (scene, prefabs, transport) | NOT IMPLEMENTED | Issue #11/#12/#33/#34/#35; institutional approval unverified (ADR-0003) |
| MiniAlpha AI Edge Robot integration | NOT IMPLEMENTED | Issue #13; procurement BLOCKED (Issue #98) |
| Physical factory module procurement and wiring | NOT PROCURED | Issue #98 |
| uKit actuator firmware (GPIO/motor driver) | NOT IMPLEMENTED | `docs/hardware-readiness.md`; missing vendor SDK |
| L3/L4 hardware-in-the-loop tests | BLOCKED | Issue #98 |
| Physical E-stop and safety interlocks | BLOCKED | ADR-0006 Layer 3; Issue #98 |
| Broker MQTT ACL configuration | Partial | Issue #41 |
| HIL safety certification | BLOCKED | Issue #98 |

**Do not claim these items as delivered until evidence at the appropriate test level is attached to a linked issue or PR.**

---

## 6. Relationship to ADR-0003 and ADR-0006

### ADR-0003 — Digital Twin Engine (Unity vs. Unreal)

ADR-0003 records the engineering decision to use **Unity** as the sole 3D runtime for the Digital Twin. The original formal research proposal named Unity; the formal institutional approval status of this technology decision is **PENDING/NOT VERIFIED**.

**Impact on this document:**
- All Unity Twin deliverables (Phase 3, F3.1–F3.6) proceed on the engineering decision, not on a verified institutional amendment.
- If institutional approval is not granted, the Twin work package may require re-scoping or a formal proposal amendment. This risk is tracked in `docs/risks.md`.
- ADR-0003 §Consequences requires this document to retain a visible historical note about the original proposal engine. That note appears in §4 Phase 3 above.

### ADR-0006 — Local Physical Command Safety

ADR-0006 establishes four safety layers. Physical safety is enforced at the local controller level (Layer 3), not at the cloud/AI/Twin layer.

**Impact on this document:**
- KPI §2.4 scenario E10 (AI unsafe action) and E11 (emergency stop) depend directly on ADR-0006 Layer 4 (AI/Twin fail-closed) and Layer 3 (Mega local safety).
- Phase 4 (Physical Integration, F4.3) requires ADR-0006 Layer 3 verification as a gate before L4 testing.
- Phase 3 (F3.8) requires ADR-0006 Layer 4 implementation in the gateway before MiniAlpha AI proposals can be processed.
- No KPI or milestone relaxes the ADR-0006 requirement that AI/Twin cannot bypass physical safety limits.

---

## 7. KPI Threshold Governance

**No numerical threshold is pre-declared as a pass/fail criterion without written sponsor approval.**

For each KPI category below, the sponsor must confirm acceptance criteria before those values are used in formal evaluations:

| KPI | Measurement exists | Sponsor threshold approved |
|-----|-------------------|---------------------------|
| Sync latency p50/p95/p99 | L2: partial | **No** — sponsor review required |
| Event loss rate ceiling | L2: no (hardware gap) | **No** — sponsor review required |
| Operational stability SLO | L2: no | **No** — sponsor review required |
| Scenario coverage (E01–E12) | Partial (E01–E12 design known) | **No** — evidence-level expectations TBD |
| Robot alert delivery time | L2: mock only | **No** — sponsor review required |
| False-alarm rate ceiling | L2: no | **No** — sponsor review required |
| Usability / dashboard criteria | Planned | **No** — sponsor review required |

Until thresholds are approved, all KPI results are reported as raw distributions in run manifests with `criteria_pass: null`. Reviewers assess plausibility against the methodology in `docs/issue-43-latency-measurement-plan.md` §4.

---

## 8. Open Risks

| ID | Risk | Impact | Mitigation |
|----|------|--------|------------|
| RISK-A | Unity institutional approval not granted | Twin work package requires amendment | Track in sponsor communication log; flag in Phase 3 gate |
| RISK-B | Hardware procurement delayed past Month 5 | Phase 4 and 5 slip; L3/L4 evidence unavailable | Maintain L2 evidence quality; document hardware dependency |
| RISK-C | MiniAlpha SDK not available | F3.7/F5.5 deliverables at risk | Mock-only evidence at L2; procurement tracker in Issue #98 |
| RISK-D | Simulation results accepted as physical evidence | Invalid research conclusions | Mandatory `simulated_components` / `physical_components` in every manifest |
| RISK-E | KPI thresholds invented without sponsor approval | Research findings lack validity | All thresholds declared `null` until sponsor-approved |
| RISK-F | ADR-0009 schema mismatch unresolved | Telemetry pipeline unstable | Gate Phase 3 Twin integration on Issue #66 resolution |
