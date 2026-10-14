# Smart Factory Hardware/Software Capability and Simulation Fallback Matrix

This document establishes the authoritative hardware and software capability matrix, simulation fallback mechanisms, and evidence-level definitions for the Smart Factory monorepo (Issue #42 delivery recovery).

---

## 1. Evidence Levels & Verification Standard

Every module, capability, and integration path in the Smart Factory project is categorized strictly by its verification evidence level:

| Level | Evidence Category | Description | Verification Method |
|---|---|---|---|
| **L1** | **Specified / Planned** | Documented architecture, interface contract, or requirements issue. No executable code. | Design review, ADR lint, schema check. |
| **L2** | **Simulated / Mocked** | Standalone code, mock adapters, or Python simulators (`amlp-sim`) running locally or in CI without physical hardware. | Automated unit/integration tests (`pytest`, PlatformIO native tests). |
| **L3** | **Bench Tested (Partial)** | Firmware running on physical microcontrollers (ESP32-S3, Arduino Mega) with mocked sensors/actuators or partial stubs. | Benchtop test runs, serial log inspection, local broker inspection. |
| **L4** | **Hardware-in-the-Loop (HIL)** | Fully integrated physical hardware (microcontrollers + level shifters + physical actuators/sensors). **Currently BLOCKED by Issue #98** (pending procurement, electrical validation, and official SDK integration). | Physical inspection, oscilloscope validation, HIL test suite execution. |
| **L5** | **Integrated Production** | End-to-end operational factory floor connected to gateway, Unity Digital Twin, and MiniAlpha edge AI under safety interlocks. | Full-system acceptance test report. |

---

## 2. Comprehensive Component Capability Matrix

| Component | Target System | Evidence Level | MQTT | AMLP v1 | UART | WS / API | Event Store | Safety Interlocks | Simulation Fallback | Status / Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| **ESP32 Bridge** | Firmware (`esp32/`) | **L3** (Bench partial) | Implemented | Implemented | Implemented | N/A | Stub | Stub (Firmware) | TCP AMLP loopback (`amlp-sim`) | Wi-Fi & MQTT client implemented; UART telemetry -> MQTT operational. GPIO sensor/actuator reads are stubs pending uKit SDK. |
| **Arduino MEGA 2560 (Reference)** | Firmware (`ukit/`) | **L2** (Simulated) / **L3** (C99 ref) | N/A | Implemented | Implemented | N/A | N/A | N/A (Firmware) | Python TCP Simulator (`amlp-sim`) | Portable C99 reference endpoint; AMLP parsing, CRC, ACK, and telemetry generation tested via unit tests. Real hardware firmware blocked on official uKit SDK & pinout. |
| **Nine Physical Modules** | Factory Floor (`factory-control/`) | **L1** (Planned) | Planned | Planned | Planned | Planned | Planned | Planned | Python software module mocks | Modular factory cells (conveyors, sorters, robotic arms). Hardware procurement and interface mapping pending. |
| **Unity Digital Twin** | Digital Twin (`digital-twin/`) | **L1** (Planned) | Planned | N/A | N/A | Planned (REST/WS) | Planned (Snapshots) | Read-only view | Offline animation / mock telemetry playback | Unity selected as engineering engine (ADR-0003). Scene prefabs, state reducers, and reconnect logic planned. Offline animations do not constitute live synchronization. |
| **MiniAlpha Edge AI** | Edge Robot (`edge-ai-robot/`) | **L1** (Planned) | Planned | N/A | N/A | Planned (MQTT/API) | Planned | Bounded Action Guard | Mock LLM / synthetic vision responses | On-site assistant and anomaly detection. Hardware procurement and official SDK pending. Bounded action guard prevents unauthorized physical override. |
| **MQTT Ingestion Gateway** | SCADA / Cloud (`iot-gateway/`) | **L2** (Simulated) / **L3** (Bench) | Implemented | N/A | N/A | Implemented | Implemented (SQLite) | N/A | Local Mosquitto broker + `mqtt-cli` | MQTT subscriber, event store, WebSocket and HTTP REST API operational in CI. TLS auth planned. |
| **Safety Gate / Interlocks** | Safety & OTA (`shared/` / Firmware) | **L2** (Simulated) | Implemented (Abort signals) | N/A | N/A | N/A | Implemented (Audit log) | Implemented (Firmware check) | Software simulation of watchdog and emergency stop | Monitors UART/MQTT health; aborts OTA staging and halts actuation if telemetry degrades. |

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

## 4. Simulation Fallback Procedures

To enable continuous development, testing, and CI verification without physical hardware (L2 evidence level), the project provides robust simulation fallbacks:

### A. Python AMLP TCP Simulator (`amlp-sim`)
Replaces physical Arduino MEGA and UART cabling with a TCP socket endpoint.
- **What works**: AMLP packet encoding/decoding, CRC validation, command ACK generation, duplicate request rejection, and periodic telemetry emission.

### B. Full-Stack Local Simulation Workflow
```bash
# Terminal 1: Start local MQTT broker (e.g. Mosquitto)
mosquitto -p 1883

# Terminal 2: Start Python AMLP simulator
python -m amlp simulate --host 127.0.0.1 --port 8765

# Terminal 3: Run gateway or test suite against local broker
pytest tests/
```

---

## 5. Matrix Maintenance and Update Procedure

1. **Trigger**: Any change to component implementation status, SDK availability, or hardware procurement.
2. **Evidence Requirement**: Status transitions (e.g., `Stub` -> `Implemented`, `L2` -> `L3`) require passing CI logs, test artifacts, or verified hardware test reports. No speculative status upgrades are permitted.
3. **Review Gate**: Modifications to this matrix require review and approval by project architecture (`@vinhphan812`).
