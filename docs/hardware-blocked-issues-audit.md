# Hardware-Blocked Issues Audit

**Generated:** 2026-10-17  
**Reviewer:** vinhphan812  
**Scope:** All 24 open issues from `gh issue list --state open`  
**Blocking taxonomy (per `docs/testing-and-acceptance.md`):**
- **BLOCKED-simulator** — L2 simulation can unblock (mock device, simulated UART/MQTT)
- **BLOCKED-L3** — needs bench hardware (ESP32 + real controller, voltage-verified wiring)
- **BLOCKED-L4** — needs HIL (actual moving 9-module subsystem + operator + E-stop)
- **BLOCKED-L5** — needs integrated factory (full chain: physical → gateway → Unity → MiniAlpha)

---

## Summary Table

| # | Title | Category | Blocking Factor | Unblock Action | Owner |
|---|---|---|---|---|---|
| 9 | Define 9-module physical factory interface | PHYSICAL | BLOCKED-L4/L5: awaiting module procurement, wiring, coordinate survey | Procure + inventory all 9 modules; assign device IDs; produce physical wiring spec | dev-pm |
| 10 | Implement factory controller simulator | PHYSICAL | **Unblockable L2** — simulator IS the unblock path; depends on #9 contract definition | Write `factory-control/` with mock adapters; deterministic state machine; upstream of all other L2 work | dev-backend |
| 11 | Scaffold Unity Digital Twin project | TWIN | **Unblockable L2** — no live hardware required; mock events sufficient for scaffold | Create Unity project, state reducer stubs, mock event adapter, EditMode/PlayMode tests | dev-backend |
| 12 | Map live gateway telemetry to Unity 3D state | TWIN | BLOCKED-simulator: depends on #3 (gateway contracts) + #7 (gateway impl) + #11 (Unity scaffold) + #10 (simulator events); L5 needs #9 physical calibration | Build Unity event adapter with mock gateway stream; real hardware L5 blocked by #9 | dev-backend |
| 13 | Implement MiniAlpha connectivity | EDGE-AI | BLOCKED-simulator: L1 mock adapter implementable now; L5 needs physical MiniAlpha unit + approved skill boundary | Write typed mock adapter, bounded command interface, unsupported-skill rejection; physical HIL blocked until unit confirmed | dev-backend |
| 14 | Design edge anomaly detection pipeline | EDGE-AI | BLOCKED-simulator: rule-based detector trainable on scripted fixtures without physical factory; L5 needs #10 + #13 mock events | Build deterministic alarm taxonomy with mock sensor fixtures; ML evaluation requires #38 dataset | dev-backend |
| 15 | Build Smart Factory dashboard | DASHBOARD | **Unblockable L2** — read-only API mock sufficient; role-gate tests can use mock auth | Implement `dashboard/` against mock gateway API; stale/offline UI verifiable with mock data | dev-backend |
| 16 | Create end-to-end acceptance suite | INTEGRATION | BLOCKED-simulator: requires #3 + #7 + #10 + #12 + #13 + #15; orchestrate simulated command→ACK→event→Twin→robot; L5 blocked by all physical dependencies | Build `integration-tests/` orchestration with mock fixtures; tag each test L2 vs L5 | dev-qa |
| 20 | Add HIL test matrix and safety sign-off | QA | BLOCKED-L4: depends on #4 + #5 + #9; test cards + wiring preflight only meaningful with physical bench | Define L1/L2/L3/L4/L5 taxonomy in `docs/qa/hil-plan.md`; L4 test cards remain BLOCKED until bench ready | dev-qa |
| 22 | Conveyor module adapter | PHYSICAL | BLOCKED-simulator → BLOCKED-L3: needs #10 mock interface first; real adapter needs conveyor hardware + level-safe wiring | Mock adapter L2 now; physical adapter L3 blocked by conveyor unit procurement | dev-backend |
| 23 | Sorting module adapter | PHYSICAL | BLOCKED-simulator → BLOCKED-L3: same as #22 | Mock adapter L2 now; physical L3 blocked by sorting machine unit | dev-backend |
| 24 | Packaging module adapter | PHYSICAL | BLOCKED-simulator → BLOCKED-L3: same as #22 | Mock adapter L2 now; physical L3 blocked by packaging unit | dev-backend |
| 25 | Forklift + dump-truck abstraction | PHYSICAL | BLOCKED-simulator → BLOCKED-L4: no physical units listed in procurement plan | Mock L2 now; physical L4 blocked by #70 (Dump Truck) + forklift procurement | dev-pm |
| 26 | Tower-crane + storage/parking logistics | PHYSICAL | BLOCKED-simulator → BLOCKED-L4: tower crane + parking lot units not in procurement plan | Mock L2 now; physical L4 blocked by #71 (Parking Lot) + crane procurement | dev-pm |
| 38 | Evaluate anomaly model quality on incidents | EDGE-AI | BLOCKED-simulator → BLOCKED-L5: depends on #14 (rule taxonomy) + labeled dataset; evaluation runnable on scripted fixtures | Build labeled scenario fixtures; ML evaluation blocked until #14 complete and incidents recorded | dev-qa |
| 47 | Build research evidence archive | RESEARCH | **Unblockable L2** — archival design + reproducibility package from existing contracts/docs; no hardware dependency | Design evidence schema, export CI artifacts, version-gated reproducibility manifest | devops |
| 48 | Prepare final scientific/technical report | RESEARCH | **Unblockable L2** — report structure from existing specs; physical results substituted as BLOCKED markers | Draft report skeleton referencing #47 evidence archive; fill with BLOCKED markers for physical sections | dev-pm |
| 49 | Produce beginner-to-advanced lab exercises | TRAINING | **Unblockable L2** — simulator + documented contracts sufficient for exercise design | Write exercises using `factory-control/` mock + existing AMLP/MQTT contract docs | dev-qa |
| 58 | Port AMLP v1 endpoint to Arduino Mega HardwareSerial | BRIDGE | BLOCKED-L3: needs Mega board + level shifter + license clearance (#98) + verified SDK; firmware code portable but bench verification required | Implement Mega adapter in `esp32-ukit-bridge/`; code reviewable L1; physical L3 blocked until #98 resolved | dev-backend |
| 59 | Implement safe uKit Explore motor/servo/sensor adapter | BRIDGE | BLOCKED-L3: depends on #9 (inventory) + #58 (Mega UART); real actuator calls need bench wiring + E-stop precheck | Write typed adapter with mock; real motor calls blocked by Mega board + wiring + license | dev-backend |
| 60 | Add Mega CI and HIL flash wiring/recovery guide | BRIDGE | BLOCKED-L3: CI build implementable now; flash/recovery guide needs actual board flash_id + partition layout from #98 | CI toolchain setup L1 now; physical wiring/recovery guide blocked by #98 board verification | devops |
| 68 | Calibrate 9-module physical-to-Unity coordinate mapping | TWIN | BLOCKED-L4/L5: depends on #9 (physical dimensions) + #11 (Unity scaffold); coordinate calibration requires actual module CAD/measurements | Define calibration format + synthetic fixture L2 now; physical calibration blocked by #9 module procurement | dev-backend |
| 70 | Dump Truck device adapter | PHYSICAL | BLOCKED-L4: no dump truck unit in procurement plan; simulator mock implementable L2 | Mock adapter L2 now; physical L4 blocked by dump truck procurement | dev-pm |
| 71 | Parking Lot occupancy and logistics-slot adapter | PHYSICAL | BLOCKED-L4: parking lot module not in procurement plan | Mock L2 now; physical L4 blocked by parking lot unit procurement | dev-pm |
| 73 | Implement authenticated HTTPS OTA client | BRIDGE | BLOCKED-simulator → BLOCKED-L3: L1 state-machine + unit tests implementable now; physical OTA requires real ESP32-S3 partition layout from #74 | Write `OtaManager` state machine with mock partition API; real flash testing blocked by #74 | dev-backend |
| 74 | Build OTA release pipeline + staged rollout | DEVOPS | BLOCKED-L3: CI release job implementable; real ESP32-S3 bench matrix needs actual boards; SPEC-6 bench tests blocked by OTA client (#73) + real hardware | CI pipeline L1/L2 now; physical OTA bench tests blocked by #73 implementation + ESP32-S3 boards | devops |
| 98 | HIL verification + licensing clearance for uKit Mega | BRIDGE | BLOCKED-L3: requires physical Mega board, multimeter, logic analyzer, legal clearance; prerequisite for #58, #59, #60 physical work | Procure Mega + level shifter; measure voltage; obtain license clearance; document partition layout | dev-pm |

---

## Blocking Dependency Graph (key paths)

```
L2-unblockable (no hardware needed):
  #10 ──► #22/23/24/25/26 adapter mocks
  #11 ──► #12 (Unity adapter)
  #15   (dashboard mock API)
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

Bridge OTA chain:
  #73 (#74 depends on it)
    └── #74
      └── OTA pipeline + bench tests

Mega chain (#98 is the hard blocker):
  #98 (hardware verification + license)
    ├── #58 (Mega UART port)
    ├── #59 (motor/servo adapter)
    └── #60 (CI + recovery guide)
```

---

## Issues Ready to Claim Now (L2-unblocked)

| # | Owner | Why unblocked |
|---|---|---|
| 10 | dev-backend | Simulator is the L2 deliverable itself; no physical dependency |
| 11 | dev-backend | Unity scaffold with mock events; no hardware dependency |
| 15 | dev-backend | Dashboard against mock API; read-only role tests |
| 47 | devops | Evidence archive design from existing artifacts |
| 48 | dev-pm | Report skeleton; physical results inserted as BLOCKED markers |
| 49 | dev-qa | Lab exercises from contracts + simulator |
| 13 | dev-backend | Typed mock robot adapter; physical call HIL when unit confirmed |
| 14 | dev-backend | Deterministic alarm rules on scripted fixtures |
| 73 | dev-backend | OtaManager state machine; physical flash blocked by #74 |

---

## Hard Physical Blockers (require procurement or bench access)

| Blocker | Blocks | Required Action | Owner |
|---|---|---|---|
| No 9-module physical inventory (#9) | #12, #22–26, #68, #20 | Procurement + dimension survey | dev-pm |
| No Mega board + license clearance (#98) | #58, #59, #60 | Board procurement + UBTECH licensing | dev-pm |
| No ESP32-S3 bench boards (#74) | #73 physical OTA tests | 2× ESP32-S3 for OTA matrix | devops |
| No MiniAlpha unit (#13) | #13 real HIL | Confirm MiniAlpha availability + skill API | dev-pm |
| No dump truck (#70) | #70 physical | Procurement decision | dev-pm |
| No parking lot (#71) | #71 physical | Procurement decision | dev-pm |
| No Unity institutional approval (#11 ADR) | #11 ADR-0003 | Formal deviation approval | dev-pm |

---

## Recommendations

1. **#10 (factory simulator) is the highest-leverage unblock.** All module adapters (#22–26), integration tests (#16), and Twin state mapping (#12) depend on it. Assign immediately.
2. **#11 (Unity scaffold) is independently unblockable.** Parallel track to #10; no shared dependency.
3. **#98 (Mega hardware + license) is the hardest blocker.** Without it, #58/#59/#60 cannot advance past code review. Requires procurement + legal.
4. **Do not mark simulator-only tests as L4/L5 PASS.** All issues with mixed evidence levels must label each test case L2 vs L3/L4/L5 explicitly.
5. **#9 procurement is P0 for the physical path.** Until the 9-module inventory exists, #12, #68, #20, and all module adapters remain blocked at L4/L5.
