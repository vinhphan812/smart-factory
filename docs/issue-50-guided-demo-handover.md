# Issue #50 — Guided Demo & Operational Handover

**Status:** Implemented (L0 documentation)
**Author:** Agent task
**Reviewer:** vinhphan812
**Last updated:** 2026-10-17

---

## 1 Demo Scenarios

### Scenario A — Normal Production Run
**Prerequisites:** ESP32 bridge powered, MQTT broker up, reference UKIT endpoint connected (or simulator running), `smart-factory/bridge/command` and result/status topics subscribed.

1. Operator presses START on the physical panel (or sends `{"id":102,"fields":["CONVEYOR_START","60"]}` to `smart-factory/bridge/command`).
2. Bridge validates AMLP frame CRC, publishes `{"status":"acknowledged"}` to `smart-factory/bridge/result`.
3. Reference endpoint starts conveyor motor; bridge publishes `{"status":"acknowledged","attempts":1}` when UART ACK received.
4. Operator observes telemetry topic (not yet implemented: firmware→MQTT TEL path; simulated by Python AMLP simulator or observed via result topic).
5. Sequence proceeds: transport → sort → pack → store. Each stage confirmed by independent result/status messages.
6. Demo ends with `CONVEYOR_STOP` and a clean `{"status":"completed"}` trace.

**Evidence level:** L2 simulation (simulator/mock); L3/L4 bench with physical modules pending hardware readiness (see §3).

**Expected outcome:** All command-result pairs traceable in broker logs. No unsafe queued execution after stop command.

---

### Scenario B — Interruption Detection (Sensor Jam / Timeout)
**Prerequisites:** Same as Scenario A; a physical jam or simulated timeout condition.

1. During conveyor run, a sensor fails to change state within the expected window.
2. Per ADR-0006 local physical safety and E01/E05 acceptance criteria: local controller issues safety stop.
3. Bridge publishes incident result: `{"status":"failed","reason":"sensor_timeout","device":"conveyor-01"}`.
4. IoT Gateway (when implemented) generates a `device.state_changed` canonical event with `event_type: "fault.jam_detected"`.
5. Dashboard/twin shows affected module in STALE/UNKNOWN state — **never** a fabricated RUNNING state.
6. Operator acknowledges fault via panel or MQTT command; system enters safe hold.

**Evidence level:** L2 simulation with mock timeout; L4 physical pending hardware test bench.

---

### Scenario C — MiniAlpha Response
**Prerequisites:** MiniAlpha adapter (#13) implemented; MiniAlpha service reachable; MQTT topics subscribed by adapter.

1. Edge anomaly detector identifies a fault (Scenario B) and generates an `AlertEvent`.
2. MiniAlpha adapter (fail-closed per ADR-0006) maps the alert to a bounded notification skill.
3. MiniAlpha executes: sends alert to configured channel/endpoint with the bounded payload only.
4. **No actuator commands are sent to the factory from MiniAlpha** — robot adapter is notification-only per current design.
5. If MiniAlpha is offline, adapter logs explicit failure and **does not** queue or retry unsafe actions.

**Evidence level:** L1/L2 (adapter unit + mock MiniAlpha); MiniAlpha hardware integration is PENDING (#13, #36).

---

## 2 Safety Brief & Start/Stop/Reset Checklist

### Safety Brief (Pre-Demo)
- [ ] Confirm E-stop is accessible, tested, and operator knows its location.
- [ ] Confirm bridge power and MQTT broker are on isolated circuits or documented.
- [ ] No unauthorized personnel in hazard zones during actuator operation.
- [ ] AI/dashboard cannot bypass physical E-stop or local interlocks (ADR-0006 fail-closed gate).
- [ ] All MQTT commands are idempotent; duplicate correlation IDs do not re-execute actions (E03, E07).
- [ ] Do not interpret `queued` or `acknowledged` as confirmed physical completion.
- [ ] Disconnect MQTT: system must **not** queue unsafe commands for later (E06).

### Start Checklist
- [ ] ESP32 bridge powered and UART link to UKIT confirmed (LED or serial output).
- [ ] MQTT broker running; `smart-factory/bridge/command`, `result`, `status` topics accessible.
- [ ] Python AMLP simulator running (if no physical UKIT endpoint present).
- [ ] Telemetry subscribers active (result/status topics; TEL path is simulated/not yet confirmed firmware).
- [ ] IoT Gateway (when implemented) receiving and validating events.
- [ ] Safety gate logs accessible for audit (ADR-0006 Layer 4).
- [ ] MiniAlpha adapter online (if Scenario C is rehearsed).

### Stop Checklist
- [ ] Issue `CONVEYOR_STOP` command; wait for result/status `acknowledged` before removing power.
- [ ] Do **not** yank power while actuators are moving.
- [ ] Confirm all modules return to idle/home state (confirmed via sensor feedback, not MQTT ACK alone).
- [ ] Disconnect MQTT if leaving system unattended (no silent queued execution).
- [ ] Log demo run: timestamp, commands issued, events received, any anomalies.

### Reset After Fault
- [ ] Operator presses E-stop → physical stop confirmed → fault acknowledged.
- [ ] Clear jam / reset sensor (physical step).
- [ ] Issue `CONVEYOR_STOP` again to clear any stale queued state.
- [ ] Confirm bridge result/status topic shows `idle`/`completed` before next start.
- [ ] Record incident in demo log: time, fault type, resolution, operator.

---

## 3 Fallbacks for Missing Hardware

| Component | Missing fallback | Demo mode | Evidence level |
|---|---|---|---|
| Physical UKIT endpoint | Python AMLP simulator (`esp32-ukit-bridge/simulator/`) | `python -m simulator --port /dev/ttyUSB0 --speed 115200` | L2 |
| ESP32 bridge | MQTT broker + simulator bridge mock | Publish commands directly to broker; use mock result/status responses | L2 |
| MiniAlpha robot | Mock adapter + log inspection | Adapter logs notification payload; no actual HTTP/WS call | L1/L2 |
| IoT Gateway | Direct MQTT subscription | Subscribe `smart-factory/bridge/status`; inspect raw JSON events | L2 |
| Unity Digital Twin | Mock 3D playback or static diagram | Use `digital-twin/mock-telemetry.json` for scripted replay; twin shows STALE | L2 |
| Physical factory modules | Firmware-only / bench test | ESP32 connected to scope/power meter; no moving parts | L3 |
| MQTT broker | localhost mosquitto | `mosquitto -v` on loopback; all topics local | L1/L2 |

**Rule:** Always declare which components are real vs. simulated vs. absent. Never let the demo imply a physical completion that was only simulated.

---

## 4 Demo Script (10–15 Minute Rehearsable)

> Read-through time ~10 min; hands-on execution ~15 min with Q&A pauses.

| Time | Step | Who | Action | Visual / Evidence |
|---|---|---|---|---|
| 0:00 | Welcome & Safety Brief | Operator | State E-stop location, power isolation, no bypass rules | Safety checklist (§2) signed/acknowledged |
| 1:00 | System Topology | Presenter | Show architecture diagram (overview.md §1); name each layer | 5-layer diagram on screen |
| 2:00 | Bridge Baseline | Operator | Power ESP32; show UART TX/RX on scope/log | Serial output visible |
| 3:00 | MQTT Connection | Operator | `mosquitto_sub -t 'smart-factory/bridge/#'` — show connected | Broker log shows CONNECT/DISCONNECT |
| 4:00 | Scenario A — Start | Operator | `mosquitto_pub -t smart-factory/bridge/command -m '{"id":102,"fields":["CONVEYOR_START","60"]}'` | Result topic shows `acknowledged` |
| 5:30 | Telemetry Observation | Presenter | Note: firmware→MQTT TEL path is **simulated**; show simulator output or explain absence | Simulator log; no fabricated live data |
| 7:00 | Scenario B — Jam | Operator | Trigger jam or use mock timeout command | Result shows `failed`; explain local safety stop |
| 8:30 | Reset Procedure | Operator | STOP → clear → acknowledge → confirm idle | Status shows `idle`; clean log |
| 10:00 | Scenario C — MiniAlpha (planned) | Presenter | Show MiniAlpha adapter log structure; explain bounded skill design; **MiniAlpha hardware NOT connected** | Adapter mock log; no live robot call |
| 11:00 | Fallbacks & Modes | Presenter | Show simulator running vs. missing hardware table (§3) | Fallback table on screen |
| 12:00 | Twin State / Stale | Presenter | Explain Unity Twin is scaffolded (#11); current demo shows STALE when disconnected per ADR-0003 | `digital-twin/mock-telemetry.json` or static diagram |
| 13:00 | What Is NOT Yet Built | Presenter | Read §5 aloud; mark each item | Section §5 on screen |
| 14:00 | Q&A + Handover | All | Walk through handover checklist; hand off credentials/access docs | Handover checklist (§6) signed |

---

## 5 What Is NOT Yet Implemented

This section is authoritative. Items listed here are **not** part of the current demo deliverable.

| Item | Status | Blocking issue |
|---|---|---|
| Firmware TEL → MQTT publish (live telemetry from ESP32 to broker) | **NOT VERIFIED** — blocked hardware L3 | #9, #25, #26 |
| IoT Gateway (validate, normalize, route events) | **NOT BUILT** | #3, #67 |
| Unity Digital Twin runtime, scenes, prefabs | **NOT BUILT** — PLANNED per #11; institutional approval unverified | #11, #33, #34, ADR-0003 |
| MiniAlpha connectivity and adapter | **NOT BUILT** — PLANNED | #13, #36 |
| Edge anomaly detector | **NOT BUILT** | #14 |
| Canonical event envelope v1.0.0 (schema) | **DESIGN ONLY** — #3 review pending | #3 |
| Safety authorization gate (ADR-0006 Layer 4) | **DESIGN ONLY** | ADR-0006 |
| Signed OTA with A/B rollback | **NOT BUILT** | ADR-0007 |
| Event store and snapshot resync | **NOT BUILT** | #31 |
| Full nine-module physical installation | **HARDWARE PENDING** — voltage, grounding, E-stop verification required | #4, #65 |
| End-to-end acceptance suite (L5) | **NOT BUILT** | #16 |
| Scientific KPI measurement (sync delay, loss rate, etc.) | **NOT MEASURED** — no thresholds claimed | #43 |
| MQTT telemetry per-device topics | **NOT VERIFIED** — existing topics are bridge-level only | ADR-0009 (known mismatch) |

**Do not claim live 3D Twin or real MiniAlpha alerts in the demo.** The demo runs on bridge-level MQTT commands + simulator + mock adapters only.

---

## 6 Relationship to ADR-0003 and Issue #11

### ADR-0003 — Digital Twin Engine
ADR-0003 selects **Unity** as the engineering implementation engine for the Digital Twin. It is **PROPOSED** (PR #89); institutional approval is **UNVERIFIED / PENDING**. This document does not build Unity assets. The Unity scene, prefab inventory, state reducer, and transport adapter are all **PLANNED** (Issues #11, #12, #33, #34, #67). The demo's Twin panel shows **STALE** or a static diagram to make this explicit.

**ADR-0003 consequence for this doc:** The operational handover assumes the Twin is offline until #11 is resolved and Unity bootstrapped. The demo cannot claim a live synchronized Twin.

### Issue #11 — Unity Project Bootstrap
Issue #11 tracks: Unity editor version selection, project layout in `digital-twin/`, source-control policy, and CI setup. It is **BLOCKED** on ADR-0003 institutional approval. Until #11 is closed:
- No Unity project code exists in `digital-twin/`.
- Twin playback in the demo is simulated via `mock-telemetry.json`.
- Fallback: static architecture diagram or mock 3D screenshot.

### Dependency chain
```
ADR-0003 (PROPOSED, approval PENDING) → #11 (OPEN, blocked) → #33/#34/#67 → #12 → L5 E2E suite
#50 (this doc) depends on: bridge L1/L2 evidence, not on Unity bootstrap.
```

---

## 7 Handover Checklist

- [ ] Safety brief delivered and acknowledged (§2).
- [ ] Demo script rehearsed end-to-end with declared real/simulated/ absent components (§4).
- [ ] Fallback modes verified and documented (§3).
- [ ] All six demo scenarios' evidence levels declared; no overstated claims (§1).
- [ ] NOT-YET-IMPLEMENTED list reviewed with operator; no implied live Twin or MiniAlpha (§5).
- [ ] ADR-0003/#11 status confirmed; Twin absence is explained, not hidden (§6).
- [ ] E-stop tested, operator confirmed location.
- [ ] Demo run logged (timestamp, commands, events, anomalies).
- [ ] Credentials and access docs transferred (broker, simulator, gateway endpoints).
- [ ] Repository documentation updated (this file linked from `#50` in `docs/roadmap/`).

---

## References

- [Architecture overview](architecture/overview.md) — five-layer model, observation/action paths
- [Testing & acceptance](testing-and-acceptance.md) — L0–L5 evidence levels, E01–E12 scenarios
- [Contracts & data](contracts-and-data.md) — AMLP spec, MQTT topics, canonical event envelope
- [ADR-0003](adr/adr-0003-digital-twin-engine.md) — Unity engine selection; institutional approval unverified
- [ADR-0006](adr/adr-0006-local-physical-safety.md) — fail-closed safety gate design
- [ADR-0009](adr/adr-0009-telemetry-schema-compatibility.md) — known telemetry schema mismatch
- [Issue #11](https://github.com/.../issues/11) — Unity project bootstrap (OPEN; blocked)
- [Issue #13](https://github.com/.../issues/13) — MiniAlpha connectivity (PROPOSED)
- [Issue #67](issue-67-unity-gateway-transport-contract.md) — Unity-gateway transport contract (PROPOSED)
