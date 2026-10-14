# AIBOT Smart Factory — Project Context v1.0

## 1. Identity
**Research topic:** “Thiết kế, xây dựng và thử nghiệm mô hình Smart Factory thu nhỏ tích hợp Digital Twin thời gian thực và AI Edge Robot tại Trung tâm AIBOT”.

**Lead environment:** Trung tâm Trí tuệ nhân tạo và Công nghệ Robot (AIBOT), Trường Đại học Công nghệ Đồng Nai (DNTU).

**Planned duration:** 12 months, without a fixed start date inferred from the proposal.

**Outcomes:** A safe miniature Industry 4.0 production/logistics demonstration system supporting AI–Robotics–Automation–IIoT practice, scientific experiments, STEM, teaching and industry collaboration.

## 2. Exactly three principal systems
- **S1 Physical Smart Factory:** nine modular hardware elements, coordinated production/logistics, instrumented state and safely bounded control.
- **S2 Real-time Digital Twin:** a **Unity** 3D model reflecting observed factory states, events, alarms, reconnect and stale/offline conditions. An offline animation is not evidence of synchronization with real machines.
- **S3 AI Edge Robot:** **MiniAlpha** to monitor, receive alerts, provide bounded supported on-site responses and interact with users. AI may not override physical safety interlocks or initiate unapproved physical rescue.

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
