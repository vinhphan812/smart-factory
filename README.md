# Smart Factory — AIBOT Industrial Automation Platform

A modular industrial automation platform built around a physical 9-module smart factory, a real-time Digital Twin, and an Edge AI co-pilot (MiniAlpha). The project is organized as a monorepo; each module lives in its own subdirectory.

## The Three Systems

### Physical Factory (9 Modules)
A real-world factory floor made of 9 interlocking production-line modules driven by
uKit microcontrollers and Arduino MEGA logic controllers. Each module hosts one or more
actuators (conveyor belts, robotic arms, color sorters, stacking arms, etc.) and
sensors (inductive sensors, color sensors, IR barriers). The ESP32 Bridge translates
network commands into the AMLP v1 serial protocol understood by the MEGA.

### Digital Twin
A near-real-time 3D visualization of the physical factory rendered in a web browser.
The twin subscribes to the same MQTT topics as the physical bridge, mirroring machine
state, telemetry and fault events as they happen on the floor. Operators can watch
the live system without being on the factory floor.

### MiniAlpha (Edge AI)
An on-premises AI co-pilot running on edge hardware (e.g. Raspberry Pi or NVIDIA Jetson)
that observes both the physical and digital layers. MiniAlpha provides anomaly detection,
predictive maintenance alerts and natural-language interaction with the factory.

---

## Repository Status

| Module | Status | Notes |
|---|---|---|
| `esp32-ukit-bridge` | **Implemented** | Wi-Fi/MQTT-to-AMLP bridge for the uKit layer |
| `physical-module-*` | Planned | 9 individual module controllers (MEGA firmware) |
| `digital-twin` | Planned | Web-based 3D twin (Three.js / R3F) |
| `iot-gateway` | Planned | Unified MQTT/OPC-UA gateway for SCADA/cloud |
| `observability` | Planned | Prometheus + Grafana + structured log pipeline |
| `minialpha` | Planned | Edge AI inference service |
| `scada-client` | Planned | Desktop or web SCADA panel |

---

## Architecture

```
                                    +------------+
                                    |  SCADA /   |
                                    |  Cloud     |
                                    +-----+------+
                                          | MQTT JSON / TLS
                                          v
  +----------+  Wi-Fi/MQTT  +-------------------+  UART/AMLP  +-----+
  | Broker  |<-----------> | ESP32 Bridge      | <--------->|MEGA |
  +----------+              | (esp32-ukit-bridge)|            +-----+
                            +-------------------+                   |
                                                                         v
                                    +-------------------+   Digital Twin
                                    | MQTT topics       | <--- (web UI)
                                    | bridge/command    |
                                    | bridge/telemetry  |
                                    | bridge/status     |
                                    +-------------------+
```

**Layers (top → bottom):**

1. **Cloud / SCADA** — publishes JSON commands, receives telemetry.
2. **MQTT Broker** — mosquitto or cloud broker (HiveMQ, AWS IoT Core, etc.).
3. **ESP32 Bridge** — subscribes to `smart-factory/bridge/command`, validates JSON,
   encodes AMLP v1 frames, sends over UART; parses ACK/telemetry from UART,
   publishes results to `smart-factory/bridge/+/+`.
4. **Arduino MEGA** — executes actuator commands, returns ACK, emits telemetry.
5. **Actuators / Sensors** — physical hardware on each factory module.

**Safety boundary:** The ESP32 sits between the network and the MEGA. It validates
and frames all traffic. The MEGA firmware is responsible for debouncing sensors,
enforcing mechanical travel limits and emergency-stop handling locally; network
latency must never block safety-critical responses.

---

## Quick Start — Bridge Simulator

No hardware required. The Python simulator accepts TCP connections and responds
with AMLP ACK/TEL frames, enabling full integration testing from a laptop.

```bash
# 1. Enter the bridge module
cd esp32-ukit-bridge

# 2. Create a virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux / macOS: source .venv/bin/activate

# 3. Install Python tools + test dependencies
python -m pip install -e ".[test]"

# 4. Run tests (Python codec + C99 reference)
python -m pytest tests/python

# 5. Start the TCP simulator (mimics MEGA UART responses)
python -m amlp simulate --telemetry-interval 1
# listens on 127.0.0.1:8765
```

From another terminal, send commands through the CLI:

```bash
python -m amlp command --id 1 --name CONVEYOR_START --arg 60
python -m amlp command --id 2 --name CONVEYOR_STOP
```

Decode raw frames:

```bash
python -m amlp decode "@ACK,1,OK*22A0"
python -m amlp crc "CMD,1,CONVEYOR_START,60"
```

Build the portable C99 reference (no ESP32 hardware needed):

```bash
pio run -d ukit -e native   # compile + run on host
pio test -d ukit -e native  # run unit tests on host
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | CLI tools, simulator, tests |
| PlatformIO Core | latest (`pip install --upgrade platformio`) | Build + test ESP32 and C99 code |
| Git | any recent | Source control |

Optional (hardware integration):

| Hardware | Purpose |
|---|---|
| ESP32-WROOM-32 | Bridge Wi-Fi/MQTT ↔ UART |
| Arduino MEGA 2560 | Module logic controller |
| uKit-compatible actuators/sensors | Physical factory modules |

---

## Module Details

Detailed documentation for each module lives in its own subdirectory:

- [`esp32-ukit-bridge/README.md`](esp32-ukit-bridge/README.md) — Bridge module: wiring,
  MQTT contract, AMLP v1 protocol reference, troubleshooting, development workflow.
- [`esp32-ukit-bridge/docs/`](esp32-ukit-bridge/docs/) — Architecture, wiring diagrams,
  development guide, MQTT contract specification.

---

## License

MIT — see individual module `LICENSE` files.
