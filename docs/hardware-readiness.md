# Hardware Readiness

Status for each physical component in the Smart Factory installation.

## Status Table

| Component | Available | SDK | Tested | Simulation | Notes |
|---|---|---|---|---|---|
| ESP32-S3 (bridge) | Yes | Partial | Partial | N/A | Wi-Fi, MQTT client, and UART AMLP encode/decode are implemented. GPIO sensor reads and PWM actuator writes are stubs. |
| Arduino MEGA 2560 | Yes | No | No | Yes (Python TCP simulator) | C99 reference endpoint implemented; UART and AMLP complete. Real firmware blocked on official uKit SDK/toolchain. |
| uKit actuators (motors, sensors) | No | No | No | Yes (Python simulator) | Procurement not started. Electrical integration with MEGA not designed. |
| MX0508 level shifter | Yes | N/A | No | N/A | 4-channel BSS138 module. Required for MEGA TX0 (5 V) -> ESP32 GPIO18 (3.3 V). Wiring documented in `esp32-ukit-bridge/docs/wiring.md`. |
| Logic analyzer / oscilloscope | Recommended | N/A | N/A | N/A | Not required but highly recommended for UART bring-up. Verify signal levels before connecting. |
| MQTT broker | Yes | N/A | Yes | N/A | External. Any MQTT 3.1.1+ broker works (Mosquitto, EMQX, HiveMQ). Broker ACLs not yet configured. |
| Wi-Fi access point | Yes | N/A | Yes | N/A | Must be on the same LAN as the MQTT broker. ESP32 connects as a standard Wi-Fi client. |

## Component Details

### ESP32-S3 (bridge)

- **Module**: ESP32-S3-WROOM-1 or compatible.
- **Role**: Wi-Fi/MQTT client; AMLP-UART bridge.
- **Firmware**: `esp32/` PlatformIO project.
- **UART**: GPIO17 (TX) -> MEGA RX0; GPIO18 (RX) <- MEGA TX0.
- **UART config**: `115200 8N1`.
- **Status**: AMLP codec, MQTT subscribe/publish, command queue, retry, and deduplication are implemented and CI-tested. GPIO callbacks for sensor reads and actuator writes are stub functions; replace with uKit SDK calls when available.
- **Flashing**: USB-Serial via `pio run -d esp32`. SPIFFS flashing via `pio run -d esp32 -t buildfs` then `esphome esp32/data/`.
- **Blockers for full hardware test**: uKit SDK GPIO API; verified UART logic levels.

### Arduino MEGA 2560

- **Role**: uKit controller endpoint; receives AMLP commands, drives actuators, returns ACK and telemetry.
- **Firmware**: `ukit/` portable C99 reference.
- **UART**: RX0/TX0 at TTL 5 V. RX0 is safe with 3.3 V input from ESP32 GPIO17. TX0 **must** go through a level shifter before connecting to ESP32 GPIO18.
- **Status**: AMLP parser, CRC validation, command dispatch, ACK generation, periodic telemetry emission, and deduplication are implemented. UART and AMLP tested via PlatformIO native build and pytest. GPIO and sensor API stubs replace the missing SDK.
- **Blockers**: Official uKit SDK with UART driver, pinout, and flashing procedure.

### uKit actuators (motors, sensors)

- **Role**: Physical conveyor, robot arm, and other factory floor equipment.
- **Status**: Not procured. Simulation available via `amlp-sim`.
- **Blockers**: Procurement; electrical integration design (power rails, motor driver modules, sensor wiring); MEGA firmware that drives them.

### MX0508 level shifter

- **Role**: Level-shift MEGA TX0 (5 V TTL) down to ESP32 GPIO18 (3.3 V TTL).
- **Connections**:
  - LV = ESP32 3.3 V
  - HV = MEGA 5 V
  - LV1 = ESP32 GPIO17 (TX)
  - HV1 = MEGA RX0
  - LV2 = ESP32 GPIO18 (RX)
  - HV2 = MEGA TX0
  - GND = common ground (ESP32 GND + MEGA GND + MX0508 GND)
- **Status**: Wiring documented in `esp32-ukit-bridge/docs/wiring.md`. Physical connection not yet verified with a multimeter or logic analyzer.
- **Note**: If a level shifter is unavailable, a 1 kΩ + 2 kΩ resistor divider is acceptable as a one-way fallback for MEGA TX0 -> ESP32 RX only. The divider cannot be used in the ESP32 TX -> MEGA RX direction.

### MQTT broker

- **Role**: Central pub/sub hub for command/result/status messages between SCADA and ESP32 bridges.
- **Requirements**: MQTT 3.1.1 or 5.0; supports QoS 1 on the command topic.
- **Status**: Tested with Mosquitto locally and in CI.
- **Blockers**: Per-device MQTT client credentials and broker ACLs not yet configured. Do not expose an unauthenticated broker to an untrusted network.

### Wi-Fi access point

- **Requirements**: 2.4 GHz 802.11b/g/n (ESP32-S3 does not support 5 GHz). WPA2-PSK or WPA3-SAE. ESP32 must have a static IP or a reliable DHCP lease renewal policy.
- **Status**: Tested in lab environment. ESP32 reconnects automatically on Wi-Fi loss with default settings.
- **Blockers**: Production AP configuration (SSID, credentials, firewall rules) not defined in this repo.

## Bring-up Prerequisites

Before running any hardware test:

1. [ ] MQTT broker is running and accessible on the LAN.
2. [ ] Wi-Fi AP credentials are configured in `esp32/include/bridge_config.h` or SPIFFS.
3. [ ] Level shifter is wired per `esp32-ukit-bridge/docs/wiring.md`.
4. [ ] Common GND confirmed between ESP32, MEGA, and level shifter.
5. [ ] UART logic levels verified with a multimeter or oscilloscope.
6. [ ] `device-registry.json` updated with the new device entry.
7. [ ] Bring-up sequence from `esp32-ukit-bridge/docs/wiring.md` (Safe bring-up sequence) followed step by step.
