# Integration Matrix

This document maps every module and component in the Smart Factory project against each integration capability, showing implementation status, blocking dependencies, and simulation fallbacks.

## Capability Reference

| Abbreviation | Full name |
|---|---|
| MQTT | MQTT broker communication (publish/subscribe, QoS, retain) |
| AMLP | AMLP v1 wire protocol (encode/decode, CRC, framing) |
| UART | Serial UART transport (ESP32 <-> MEGA) |
| WS | WebSocket client/server (future: remote dashboards) |
| EVSTORE | Event store (audit log, command history) |
| AUTH | Authentication / authorisation |
| GPIO | GPIO / sensor access on ESP32 |
| SIM | Simulation fallback (runs without hardware) |
| HLW | Hardware-level wiring (physical connections) |
| FLASH | OTA or SPIFFS firmware/asset flashing |

---

## Module / Component Matrix

| Component | Type | MQTT | AMLP | UART | WS | EVSTORE | AUTH | GPIO | SIM | HLW | FLASH | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ESP32 Bridge firmware | Firmware | Implemented | Implemented | Implemented | N/A | Stub | Stub | Stub | N/A | Implemented | Stub | Wi-Fi and MQTT client are implemented; GPIO/telemetry stubs must be replaced with uKit SDK. |
| MEGA reference (C99) | Firmware | N/A | Implemented | Implemented | N/A | N/A | N/A | Stub | N/A | Stub | N/A | Portable C99; UART and AMLP complete; GPIO/sensor stubs replace real SDK calls. |
| Python AMLP codec (`tools/amlp/`) | Tool | N/A | Implemented | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | Pure codec, no transport. |
| Python CLI (`amlp`) | Tool | N/A | Implemented | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | CRC, encode, decode, command generation. |
| Python TCP simulator (`amlp-sim`) | Tool | Stub | Implemented | N/A | N/A | N/A | N/A | N/A | Implemented | N/A | N/A | Replaces UART with TCP for bridge dev; valid ACK responses; periodic fake telemetry. |
| IoT Gateway | External | Implemented | N/A | N/A | Implemented | Implemented | Stub | N/A | N/A | N/A | N/A | MQTT subscriber; event store (bounded SQLite); WebSocket and HTTP REST API. Auth (TLS) planned. |
| Device Registry | Data | Stub | N/A | N/A | N/A | N/A | Stub | N/A | N/A | N/A | Planned | Flat JSON in SPIFFS (current); etcd or MQTT discovery planned. See `esp32-ukit-bridge/docs/device-registry.md`. |
| Shared protocol spec (`esp32-ukit-bridge/shared/protocol-spec/`) | Spec | N/A | Implemented | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | Canonical AMLP v1 spec and golden test vectors. |

### Status legend

| Status | Meaning |
|---|---|
| **Implemented** | Working code or spec exists; CI passes. |
| **Stub** | Placeholder code present; behaviour is incomplete or not wired to real transport. |
| **Planned** | Design documented; no code written yet. |
| **Blocked** | Cannot proceed until another item is resolved (see Blocking Dependencies). |
| **N/A** | Not applicable to this component. |

---

## Hardware Readiness Summary

See `esp32-ukit-bridge/docs/hardware-readiness.md` for the full per-component table.

| Component | Has Hardware? | Has SDK? | Tested? |
|---|---|---|---|
| ESP32-S3 (bridge) | Yes | Partial (Wi-Fi/MQTT done; GPIO/sensor missing) | Partial |
| Arduino MEGA 2560 | Yes | No (C99 reference only) | No |
| uKit actuators | No | No | No |
| Level shifter (MX0508) | Yes | N/A | No |
| MQTT broker | Yes (external) | N/A | Yes |

---

## Simulation Fallback

Each simulation layer describes what works without physical hardware.

| Layer | Simulation | What works |
|---|---|---|
| ESP32 bridge | Run firmware on ESP32 with TCP AMLP endpoint instead of UART | Full MQTT round-trip; AMLP encode/decode; retry and deduplication |
| MEGA reference | Python TCP simulator (`amlp-sim`) | Valid ACK for any recognised command; fake periodic telemetry; dedupe cache |
| IoT gateway | Any MQTT client (e.g., `mqtt-cli`, `mosquitto_pub`) publishing to broker | End-to-end command/result flow without any device |
| uKit actuators | Python simulator + TCP AMLP stream | Command acceptance; fake telemetry values; timing simulation |
| Full stack | `amlp simulate` + MQTT broker on localhost | Everything except real GPIO, physical wiring, and motor control |

### Running the full simulation

```bash
# Terminal 1: start the MQTT broker (e.g., Mosquitto)
mosquitto -p 1883

# Terminal 2: start the Python AMLP TCP simulator
python -m amlp simulate --host 127.0.0.1 --port 8765

# Terminal 3: configure ESP32 bridge to connect to localhost broker
# and point UART TCP client at port 8765, or use the simulator
# directly from the IoT gateway

# Terminal 4: publish a command
mosquitto_pub -t smart-factory/bridge-001/command/down -m '{"command_id":1,"command_name":"CONVEYOR_START","arguments":["60"]}'
```

---

## Blocking Dependencies

Items that must be resolved before another item can move from Planned/Stub to Implemented.

### Blocking map

| Item | Blocked by | Blocking |
|---|---|---|
| ESP32 GPIO telemetry (Stub) | uKit SDK with GPIO/sensor API | Firmware end-to-end test on hardware |
| MEGA GPIO integration (Stub) | Official uKit SDK, toolchain, pinout | Real hardware integration |
| ESP32 OTA flashing (Stub) | Partition table layout; Wi-Fi reliability testing | Fleet firmware updates |
| MQTT broker ACLs (Stub) | Per-device MQTT client auth design | Multi-device secure deployment |
| Event store (Stub) | Time-series DB or log sink selection | Command audit trail |
| IoT Gateway WS (Planned) | WS server in gateway host | Remote browser dashboard |
| etcd registry (Planned) | Registry authority service design | Scalable multi-device deployment |
| MQTT auto-discovery (Planned) | Registry authority; broker support | Zero-touch device onboarding |
| AUTH (Stub) | Broker-level TLS/client cert design | Production multi-tenant access |
| uKit actuators (No hardware) | Procurement; electrical integration | Physical factory floor operation |

### Critical path to first hardware test

```
MEGA reference (C99 Implemented)
  + uKit SDK (Blocked: No SDK)        --> Real MEGA firmware (Blocked)
  + ESP32 GPIO stubs (Stub)           --> ESP32 telemetry handler (Blocked)
  + Level shifter wiring (Implemented hardware, not tested)
                                          --> Full UART loopback test (Blocked)
                                               --> End-to-end command on hardware (Blocked)
```

The Python TCP simulator and MQTT broker enable full-stack development and CI testing **without** waiting for the uKit SDK or physical hardware.

---

## Keeping this matrix current

- Update the matrix when a component's status changes.
- Status transitions: Stub -> Implemented when CI passes on real hardware or the code is merged and tested.
- Add a row for each new component or service added to the project.
- Remove "Planned" rows once implementation begins; move to "Stub" or "Implemented" as appropriate.
