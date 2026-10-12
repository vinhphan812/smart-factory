# Architecture Overview

This document describes the high-level architecture of the Smart Factory platform:
data flows, control flows, safety boundaries, and the division of responsibility
between modules.

---

## System Layers

```
Layer 5  +---------------------+   External systems (SCADA, cloud dashboards)
         |  SCADA / Cloud      |
         +---------+-----------+
                   | MQTT JSON (TLS)
                   v
Layer 4  +---------------------+   Message broker (mosquitto / HiveMQ / AWS IoT)
         |  MQTT Broker        |   Topics: bridge/command, bridge/telemetry,
         +---------+-----------+   bridge/status, digital-twin/+
                   | MQTT
                   v
Layer 3  +---------------------+   ESP32 firmware (esp32-ukit-bridge)
         |  ESP32 Bridge        |   - Validates incoming JSON
         +---------+-----------+   - Encodes AMLP v1 frames
                   | UART 115200 8N1  - Retries + deduplication
                   v               - Parses ACK + telemetry
Layer 2  +---------------------+   Arduino MEGA firmware (physical-module-*)
         |  MEGA Controller     |   - Executes actuator commands
         +---------+-----------+   - Enforces safety limits locally
                   | GPIO / PWM   - Emits periodic telemetry
                   v
Layer 1  +---------------------+
         |  Actuators / Sensors |
         |  (conveyors, arms,    |  Physical factory floor
         |   sorters, stackers)  |
         +---------------------+
```

---

## Data Flow — Telemetry Path

```
MEGA Controller
  | produces:  @TEL,<uptime>,<temp_c>,<humidity>,<digital_inputs>*CRC4\r\n
  v UART (TX/RX)
ESP32 Bridge
  | parses AMLP, repackages as MQTT JSON:
  | {
  |   "module": "CONVEYOR",
  |   "state": "RUNNING",
  |   "speed": 60,
  |   "sensor_1": 1,
  |   "uptime_ms": 123456,
  |   "temperature_centi_c": 3420,
  |   "humidity_centi_pct": 7650
  | }
  v MQTT publish  →  broker  →  Digital Twin (web UI)
                                 →  MiniAlpha (AI inference)
                                 →  SCADA / historian
```

- Topic convention: `smart-factory/bridge/telemetry/<module_id>`
- Payload: JSON object mirroring the AMLP `TEL` frame fields.
- Latency target: bridge publishes within 50 ms of UART reception.
- The ESP32 does not store telemetry; it is fire-and-forget.

---

## Control Flow — Command Path

```
SCADA / Cloud
  | publishes JSON: { "id": 1, "command": "CONVEYOR_START", "arg": 60 }
  v MQTT subscribe  ←  broker  ←  smart-factory/bridge/command
                        |
ESP32 Bridge
  | validates JSON schema
  | generates AMLP: @CMD,1,CONVEYOR_START,60*<crc4>\r\n
  | retries up to 3x with 500 ms interval on missing ACK
  | deduplicates by correlation id
  v UART TX
                        |
MEGA Controller
  | executes command (starts conveyor at speed 60)
  | sends ACK: @ACK,1,OK*<crc4>\r\n
  v UART RX → bridge parses ACK, stops retry timer
                        |
                        v
  ESP32 Bridge
  | publishes MQTT result:
  | { "id": 1, "status": "OK", "command": "CONVEYOR_START" }
  v MQTT publish  →  broker  →  SCADA / Cloud
```

### Command Retry and Deduplication

- If the MEGA does not respond within 500 ms, the ESP32 retries the exact same
  wire frame (same correlation id) up to 3 times.
- After 3 failures the ESP32 publishes `{ "id": N, "status": "TIMEOUT" }` and
  discards the command.
- The MEGA deduplicates by caching the last 8 correlation ids; a re-delivered
  command returns the cached ACK but does not re-execute actuator logic.

---

## Safety Boundaries

```
Network (MQTT)          ESP32 Bridge          MEGA Controller       Physical
─────────────────────────────────────────────────────────────────────────────
• TLS / auth at broker  • JSON validation     • Hard travel limits  • E-stop
• Rate limiting          • Frame size limit   • Sensor debounce      • Overcurrent
• Idempotency key        • CRC check on AMLP  • Watchdog timer      • Fuses
• No firmware flash      • Command allowlist   • Emergency stop pin   • Enclosures
  over MQTT               enforcement           (GPIO cutoff)         grounded
```

**Critical principle:** Safety-critical logic (travel limits, e-stop, overcurrent
detection) must run on the MEGA locally. Network delays, broker outages or ESP32
failure must never prevent the MEGA from stopping a moving actuator.

---

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `esp32-ukit-bridge` | Wi-Fi, MQTT client, JSON ↔ AMLP translation, retry/dedupe, UART I/O |
| `physical-module-*` | Actuator/sensor control, MEGA firmware, local safety enforcement |
| `digital-twin` | Subscribe telemetry, render 3D scene, expose web UI |
| `iot-gateway` | Protocol translation (OPC-UA ↔ MQTT), authentication proxy for SCADA |
| `observability` | Prometheus exporter, Grafana dashboards, structured log aggregation |
| `minialpha` | On-device AI inference (anomaly detection, NL interface) |
| `scada-client` | Human-machine interface, alarm acknowledgment, historian queries |

---

## Hardware Blockers

| Hardware | Blocker Detail | Workaround |
|---|---|---|
| uKit SDK / firmware | uKit SDK, electrical pinout and flashing procedure have not been provided | `ukit/` portable C99 reference; `simulator.py` TCP endpoint |
| Physical MEGA firmware | 9-module MEGA source not yet in repo | Simulate commands via `amlp` CLI |
| ESP32 real UART | `esp32/platformio.ini` not yet present | Python simulator + C99 native build |
| Actuator drivers | Motor drivers, sensors not wired to MEGA | Stage-by-stage development with simulator |

The ESP32 bridge is functionally complete (Python tools, C99 reference, MQTT contract).
Full hardware integration is blocked pending delivery of the uKit SDK and physical
module specifications.

---

## MQTT Topic Reference

```
smart-factory/bridge/command/<module_id>   # JSON command  (SCADA → Bridge)
smart-factory/bridge/telemetry/<module_id> # JSON telemetry (Bridge → Twin/AI)
smart-factory/bridge/status/<module_id>    # Bridge online/error events
smart-factory/digital-twin/scene/<event>    # Twin rendering events
smart-factory/alarms/<module_id>            # Alarm notifications
```

All topics use QoS 1 for commands and telemetry. Alarm topics use QoS 2.

---

## Protocol Stack Summary

| Layer | Protocol | Format |
|---|---|---|
| Application | MQTT 3.1.1 | JSON |
| Transport | TLS 1.3 (production) | TCP |
| Bridge firmware | AMLP v1 over UART | `@BODY*CRC4\r\n` |
| Physical link | UART 115200 8N1 | 3.3 V TTL (verify uKit levels) |
