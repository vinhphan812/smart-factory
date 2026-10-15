# Smart Factory Hardware/Software Capability and Simulation Fallback Matrix

This document establishes the authoritative hardware and software capability matrix, simulation fallback mechanisms, and evidence-level definitions for the Smart Factory monorepo (Issue #42 delivery recovery).

---

## 1. Evidence Levels & Verification Standard (Canonical Taxonomy)

Every module, capability, and integration path in the Smart Factory project is categorized strictly by its verification evidence level in accordance with `docs/testing-and-acceptance.md`:

| Level | Evidence Category | Description | Verification Method / Evidence Link |
|---|---|---|---|
| **L0** | **Static / Schema** | Documented architecture, interface contract, schema, or requirements issue. No executable code. | Design review, ADR lint (`scripts/check_adrs.py`), schema check. |
| **L1** | **Host Unit** | Python/C99/C++ host unit tests, local algorithms, and parsers. | Unit test suite execution (`pytest`, PlatformIO native tests). |
| **L2** | **Simulated / Mocked** | Standalone code, mock adapters, or Python simulators (`amlp-sim`, mock broker) running locally or in CI without physical hardware. | Automated integration tests (`python3 -m pytest ../iot-gateway/tests/`, CI workflows). |
| **L3** | **Bench Tested (Partial)** | Firmware running on physical microcontrollers (ESP32-S3, Arduino Mega) with mocked sensors/actuators or partial stubs. **NOT VERIFIED** / **BLOCKED** where bench logs are absent. | Benchtop test runs, serial log inspection, local broker inspection (requires cited bench test logs). |
| **L4** | **Hardware-in-the-Loop (HIL)** | Fully integrated physical hardware (microcontrollers + level shifters + physical actuators/sensors). **NOT VERIFIED / BLOCKED by Issue #98** (pending procurement, electrical validation, and official SDK integration). | Physical inspection, oscilloscope validation, HIL test suite execution. |
| **L5** | **Integrated Production** | End-to-end operational factory floor connected to gateway, Unity Digital Twin, and MiniAlpha edge AI under safety interlocks. **NOT VERIFIED / BLOCKED by Issue #98**. | Full-system acceptance test report. |

---

## 2. Comprehensive Component Capability Matrix

> **P2-1 column mapping:** The capability columns below (MQTT · AMLP v1 · UART · GPIO · WS/API · Event Store · Safety Interlocks · FLASH) are the historical protocol/subsystem coverage columns. The **Evidence Level** column uses the canonical taxonomy from Section 1 (L0–L5). These are orthogonal axes: a component may have an "Implemented" protocol capability at one evidence level while a different subsystem on the same component remains "Planned" at a lower evidence level.

**Capability column key:**
| Column | Maps to evidence taxonomy | Notes |
|---|---|---|
| MQTT | L2 — simulated MQTT broker in CI | Also L1 for host-unit publish/subscribe mocks |
| AMLP v1 | L1 — host-unit protocol parser tests | L2 for end-to-end AMLP simulation |
| UART | L3 (bench) / blocked | Physical UART HIL blocked by #98 |
| GPIO | L3 (bench) / blocked | ESP32 GPIO blocked by official uKit SDK |
| WS / API | L2 — gateway REST/WS in CI | Also L1 for host-unit route tests |
| Event Store | L2 — SQLite persistence in CI | Also L1 for unit tests |
| Safety Interlocks | L2 (stub) / **PLANNED** | Firmware interlock blocked by #98; contracts in ADR-0006/0007 |
| Simulation Fallback | L2 | Explicit offline/loopback path per component |
| FLASH | L3 (bench) / blocked | OTA FLASH blocked by #98; design in ADR-0007/0008 |

| Component | Target System | Evidence Level | MQTT | AMLP v1 | UART | GPIO | WS / API | Event Store | Safety Interlocks | FLASH | Simulation Fallback | Status / Notes & Evidence Link |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **ESP32 Bridge** | Firmware (`esp32/`) | **L2** (Simulated / Host Unit) / **L3** (Bench: **NOT VERIFIED / BLOCKED**) | Implemented | Implemented | Implemented | Stub | N/A | Stub | Stub (Firmware) | STUB — OTA FLASH design in ADR-0007; no HIL yet (BLOCKED by #98) | TCP AMLP loopback (`amlp-sim`) | Wi-Fi & MQTT client implemented; UART telemetry -> MQTT operational in simulation. GPIO sensor/actuator reads are stubs pending uKit SDK (BLOCKED by #98). |
| **Arduino MEGA 2560 (Reference)** | Firmware (`ukit/`) | **L1** (Host Unit) / **L2** (Simulated) / **L3** (Bench: **NOT VERIFIED / BLOCKED**) | N/A | Implemented | Implemented | N/A | N/A | N/A | N/A | N/A | Python TCP Simulator (`amlp-sim`) | Portable C99 reference endpoint; AMLP parsing, CRC, ACK, and telemetry generation tested via unit tests (L1/L2). Real hardware firmware blocked on official uKit SDK & pinout (#98). |
| **Nine Physical Modules** | Factory Floor (`factory-control/`) | **L0** (Static / Schema) | Planned | Planned | Planned | Planned | Planned | Planned | Planned | Planned | Python software module mocks | Modular factory cells (conveyors, sorters, robotic arms). No executable code yet. Interface contracts, schema, and requirements documented (**BLOCKED by #98**). |
| **Unity Digital Twin** | Digital Twin (`digital-twin/`) | **L0** (Static / Schema) | Planned | N/A | N/A | N/A | Planned (REST/WS) | Planned (Snapshots) | Read-only view | N/A | Offline animation / mock telemetry playback | Unity selected as engineering engine per ADR-0003. Scene prefabs, state reducers, reconnect logic, and event snapshot schema are documented design artefacts — no executable code yet. Live real-time synchronization is **NOT VERIFIED / BLOCKED**. |
| **MiniAlpha Edge AI** | Edge Robot (`edge-ai-robot/`) | **L0** (Static / Schema) | Planned | N/A | N/A | N/A | Planned (MQTT/API) | Planned | Bounded Action Guard | N/A | Mock LLM / synthetic vision responses | On-site assistant and anomaly detection. Hardware procurement and official SDK pending (**BLOCKED by #98**). Bounded action guard prevents unauthorized physical override. No executable code yet — only documented design artefacts and API schema. |
| **MQTT Ingestion Gateway** | SCADA / Cloud (`../iot-gateway/`) | **L2** (Simulated / CI Tested) | Implemented | N/A | N/A | N/A | Implemented | Implemented (SQLite) | N/A | N/A | Local Mosquitto broker + `mqtt-cli` | MQTT subscriber, event store, WebSocket and HTTP REST API operational in CI (`python3 -m pytest ../iot-gateway/tests/`). TLS auth planned. |
| **Safety Gate / Interlocks** | Safety & OTA (`shared/` / Firmware) | **L2** (Simulated) / **PLANNED** (Firmware) | STUB — abort signals in MQTT payload schema ([`architecture/esp32-ota-design.md`](architecture/esp32-ota-design.md)) | N/A | N/A | N/A | N/A | STUB — `EventStore` records all events; no dedicated safety-audit log schema yet ([`../iot-gateway/src/iot_gateway/event_store.py:1`](../iot-gateway/src/iot_gateway/event_store.py)) | STUB — firmware interlock contract in ADR-0006; no executable logic yet ([`adr/adr-0006-local-physical-safety.md`](adr/adr-0006-local-physical-safety.md)) | STUB — ADR-0007/0008 describe watchdog/estop; no simulation impl. | All Safety Gate capabilities are **STUB or PLANNED**. No executable abort, safety audit log, or firmware interlock in code. ADR contracts define required behaviour; implementation pending Issue #98. |

---

## 3. Hardware-in-the-Loop (HIL) Status & Blocking Dependencies

All physical Hardware-in-the-Loop (HIL) requirements across the monorepo are **explicitly BLOCKED by Issue #98** (Hardware-in-the-Loop Integration & Safety Certification).

### Blocking Dependencies Map
1. **ESP32 GPIO / Sensor Read-out**: Blocked until official uKit SDK GPIO API is available.
2. **Arduino MEGA 2560 HIL Deployment**: Blocked until physical procurement, MX0508 level-shifter signal verification, and vendor toolchain integration are complete.
3. **Nine Physical Modules**: Blocked on procurement and electrical rail design.
4. **MiniAlpha Robot Integration**: Blocked on hardware acquisition and API documentation.
5. **Unity Real-time Telemetry Synchronization**: Blocked on IoT Gateway live WebSocket push from physical bridge telemetry.

---

## 4. Partial Development Smoke & Test Validation Procedures

To enable continuous development, testing, and CI verification without physical hardware (L2 evidence level), the project provides explicit executable tests and verification commands:

### A. IoT Gateway & Storage Integration Tests (L2)
Verifies MQTT message normalization, SQLite event store persistence, and REST/WS API endpoints against unit and integration fixtures:
```bash
python3 -m pytest ../iot-gateway/tests/ -v
```
*(Source: `../iot-gateway/tests/` — CI tests passing; exact count varies by Python version matrix)*

### B. Python AMLP Codec & TCP Simulator (L2)
Exercises protocol framing, CRC validation, command ACK generation, duplicate request rejection, and TCP socket communication locally:
```bash
python -m pip install -e ".[test]"
pytest esp32-ukit-bridge/tests/python
python -m amlp simulate --host 127.0.0.1 --port 8765
```
*(Source: `esp32-ukit-bridge/tools/amlp/` and `esp32-ukit-bridge/tests/python/`)*

### C. C99 Reference Firmware Native Build & Test (L1/L2)
Verifies portable C99 protocol parsing and checksum logic on the host platform:
```bash
pio test -d esp32-ukit-bridge/ukit -e native
pio run -d esp32-ukit-bridge/ukit -e native
```
*(Source: `esp32-ukit-bridge/ukit/`)*

---

## 5. Matrix Maintenance and Update Procedure

1. **Trigger**: Any change to component implementation status, SDK availability, or hardware procurement.
2. **Evidence Requirement**: Status transitions (e.g., `Stub` -> `Implemented`, `L2` -> `L3`) require passing CI logs, test artifacts, or verified hardware test reports. No speculative status upgrades are permitted.
3. **Review Gate**: Modifications to this matrix require review and approval by project architecture (`@vinhphan812`).
