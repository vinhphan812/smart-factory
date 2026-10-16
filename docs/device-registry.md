# Device Registry

This document defines the device registry schema, ownership model, and onboarding process for the Smart Factory installation.

## Implementation Status

| Feature | Status | Evidence |
|---------|--------|---------|
| Device ID format specification | ✅ Implemented | Schema defined here |
| MQTT topic hierarchy (`smart-factory/{deviceId}/...`) | ✅ Implemented | `MqttBridge::begin()` formats topics using chip-derived `deviceId` |
| Dynamic topic configuration from registry | 🔒 Planned | Not wired; `MqttBridge` uses compile-time topic names |
| SPIFFS JSON registry loading at startup | 🔒 Planned | No `device-registry.json` file or loading code; topics are hard-coded |
| Ownership and capabilities fields | 🔒 Planned | Schema defined; no firmware implementation |
| etcd-backed central registry | 🔒 Planned | Design only |
| MQTT auto-discovery | 🔒 Planned | Design only |

---

## Device ID Format

A device identifier is a **UTF-8 string** used in MQTT topics, the registry, and logs.

### Rules

| Property | Value |
|---|---|
| Characters | Lowercase letters `a`–`z`, digits `0`–`9`, hyphen `-`, underscore `_` |
| Max length | **64 characters** |
| Case | Lowercase only |
| Start/end | Must start with a letter; must not end with `-` or `_` |

### Examples

| device_id | Notes |
|---|---|
| `bridge-001` | ESP32 bridge unit |
| `mega-conveyor-a` | MEGA controlling conveyor A |
| `mega-conveyor-b` | MEGA controlling conveyor B |
| `mega-robot-arm-01` | MEGA controlling robot arm |
| `iot-gateway-01` | Cloud/edge IoT gateway host |

A device id is assigned once and must not be reused by a different physical device.

---

## Registry Schema

The registry is a **flat JSON file** named `device-registry.json`. It is a JSON object keyed by `device_id`.

### Schema

```json
{
  "<device_id>": {
    "device_id": "string (matches key)",
    "device_type": "esp32_bridge | mega_reference | iot_gateway | simulator",
    "firmware_version": "string (semver or git hash)",
    "capabilities": ["string", ...],
    "mqtt_topics": {
      "command": "string (MQTT topic, templated with {device_id})",
      "result":  "string",
      "status":  "string",
      "telemetry": "string (future)"
    },
    "physical_location": {
      "factory_zone": "string",
      "line": "string",
      "notes": "string"
    },
    "owner": {
      "team": "string",
      "contact": "string (email alias or username)"
    },
    "registered_at": "ISO 8601 timestamp",
    "last_seen": "ISO 8601 timestamp"
  }
}
```

### Field descriptions

| Field | Required | Description |
|---|---|---|
| `device_id` | Yes | Matches the JSON key. |
| `device_type` | Yes | Classifier used by the integration matrix. |
| `firmware_version` | Yes | Changes whenever the device firmware is updated. |
| `capabilities` | Yes | List of command names and telemetry streams the device declares it can handle. See [Device Capability Declarations](#device-capability-declarations). |
| `mqtt_topics` | Yes (esp32_bridge) | MQTT topic template. `{device_id}` is substituted at runtime. |
| `physical_location` | Recommended | Human-readable placement for operations and wiring docs. |
| `owner` | Yes | Team and contact responsible for this device's configuration. |
| `registered_at` | Auto | UTC timestamp set by the registration authority when the entry is first created. |
| `last_seen` | Auto | UTC timestamp updated by the device's status heartbeat. |

### Example entry

```json
{
  "bridge-001": {
    "device_id": "bridge-001",
    "device_type": "esp32_bridge",
    "firmware_version": "v1.2.0",
    "capabilities": [
      "CONVEYOR_START",
      "CONVEYOR_STOP",
      "get_telemetry"
    ],
    "mqtt_topics": {
      "command":  "smart-factory/{device_id}/command",
      "result":   "smart-factory/{device_id}/result",
      "status":   "smart-factory/{device_id}/status",
      "telemetry": "smart-factory/{device_id}/telemetry"
    },
    "physical_location": {
      "factory_zone": "Assembly Line 1",
      "line": "Conveyor A",
      "notes": "Wall-mounted cabinet, left door"
    },
    "owner": {
      "team": "controls",
      "contact": "controls@factory.local"
    },
    "registered_at": "2025-09-01T08:00:00Z",
    "last_seen": "2025-10-11T14:32:01Z"
  }
}
```

---

## Where the Registry Lives

### Current: flat JSON in ESP32 SPIFFS

The registry is distributed as `device-registry.json` on the ESP32 SPIFFS partition.

```
esp32/data/
  device-registry.json
```

At startup the ESP32 bridge loads the file, validates it against this schema, and uses the `mqtt_topics` entries to configure its MQTT client. If the file is absent or invalid, the bridge falls back to compile-time defaults defined in `esp32/include/bridge_config.h` and logs a warning.

The JSON file is the **single source of truth** for topic configuration. Do not edit `bridge_config.h` to set per-device topics; update the registry instead and flash the updated SPIFFS image.

### Future: etcd or MQTT discovery

When the installation scales beyond a handful of devices, the flat JSON will be replaced by:

- **etcd** — distributed key-value store for registry + configuration versioning. Enables atomic updates, TTL-based heartbeat, and watch-based change propagation.
- **MQTT discovery** — devices publish a birth message to a discovery topic on boot. A registry service subscribes, reconciles state, and writes the canonical JSON. Requires a registry service to be deployed alongside the MQTT broker.

Both future options are blocked until:
1. The etcd/MQTT broker integration is evaluated for the target environment.
2. A registry authority service is designed and implemented.
3. The ESP32 firmware is updated to support dynamic reconfiguration without a restart.

Track progress in the integration matrix (`integration-matrix.md`).

---

## Device Capability Declarations

Each `device_type` defines the commands and telemetry streams it supports. These are listed in the `capabilities` array of the registry entry and are used by the IoT gateway to validate commands before publishing them.

### esp32_bridge

| Capability | Type | Description |
|---|---|---|
| `CONVEYOR_START` | command | Start conveyor at given speed. Argument: `speed` (integer, 1–255). |
| `CONVEYOR_STOP` | command | Stop conveyor immediately. No argument. |
| `get_telemetry` | command | Request a telemetry snapshot. Returns `TEL,STATE,...` asynchronously. |
| `telemetry_periodic` | telemetry stream | Bridge emits `TEL,STATE,...` on a fixed interval. |

### mega_reference

| Capability | Type | Description |
|---|---|---|
| `CONVEYOR_START` | command | Same as bridge. |
| `CONVEYOR_STOP` | command | Same as bridge. |
| `telemetry_periodic` | telemetry stream | `TEL,STATE,...` emitted every ~5 s. |

### simulator

| Capability | Type | Description |
|---|---|---|
| `CONVEYOR_START` | command | Accepted; returns `ACK,OK` after 50 ms simulated latency. |
| `CONVEYOR_STOP` | command | Accepted; returns `ACK,OK` immediately. |
| `get_telemetry` | command | Returns a simulated `TEL,STATE,...`. |
| `telemetry_periodic` | telemetry stream | `TEL,STATE,...` emitted every 1 s. |

### iot_gateway

| Capability | Type | Description |
|---|---|---|
| `mqtt_publish` | command | Gateway can forward command JSON to the bridge topic. |
| `mqtt_subscribe` | command | Gateway subscribes to result and status topics. |
| `amlp_decode` | utility | Gateway can decode/encode AMLP frames (for logging/debug). |

---

## Onboarding: Registering a New Device

### Manual Provisioning (current, flat JSON)

1. Assign a `device_id` following the format rules above.
2. Add an entry to `device-registry.json` with all required fields.
3. For an ESP32 bridge: populate `mqtt_topics` with topics containing `{device_id}`.
4. Flash the updated SPIFFS image to the ESP32.
5. Update `integration-matrix.md` and `esp32-ukit-bridge/docs/hardware-readiness.md` to reflect the new device.
6. The device registers its presence by publishing a retained status message on its `status` topic on boot. Confirm `last_seen` updates in the registry.

### Auto-Discovery (future)

Devices broadcast a discovery payload on a well-known MQTT topic (e.g., `smart-factory/discover/birth`):

```json
{
  "device_id": "mega-conveyor-c",
  "device_type": "mega_reference",
  "firmware_version": "v0.9.1",
  "capabilities": ["CONVEYOR_START", "CONVEYOR_STOP", "telemetry_periodic"],
  "mqtt_topics": {
    "command":  "smart-factory/mega-conveyor-c/command",
    "result":   "smart-factory/mega-conveyor-c/result",
    "status":   "smart-factory/mega-conveyor-c/status"
  }
}
```

A registry service listens on this topic, validates the payload against the schema, merges it into the canonical registry, and acknowledges the device. The device then configures its MQTT client from the merged response.

This is **not yet implemented**. Blocked by: registry authority service, MQTT broker availability for discovery topics, and firmware support for the discovery protocol.

---

## Ownership and Change Propagation

### Ownership model

Each device entry has an `owner` block:

```json
"owner": {
  "team": "controls",
  "contact": "controls@factory.local"
}
```

| Role | Permission |
|---|---|
| `owner.team` | May update `capabilities`, `mqtt_topics`, `physical_location`, and `firmware_version` for their device. |
| Any team member | May update `last_seen` (automated, by the device heartbeat). |
| Registry admin | May add or remove device entries. |

### How changes propagate

| Change | Propagation |
|---|---|
| `firmware_version` update | Device self-reports via status message; registry is updated by the heartbeat. |
| `mqtt_topics` change | ESP32 bridge must be reflashed with updated SPIFFS. Reboot required. |
| `capabilities` change | ESP32 bridge must be reflashed. Changes take effect on next boot. |
| `physical_location` / `owner` | Updated in `device-registry.json` by the owning team; no firmware flash required. |
| New device added | ESP32 bridge reflashed with updated SPIFFS; `integration-matrix.md` and `hardware-readiness.md` updated. |

### Access control

Currently: filesystem-level (write access to the `esp32/data/device-registry.json` source file and SPIFFS flashing permissions). No runtime authentication or per-device MQTT ACLs are configured on the broker.

Future: broker-level MQTT client authentication (username/password or client certificates) and per-topic ACLs to enforce that only the bridge device can publish to its result/status topics.

---

## Configuration Ownership Matrix

Beyond the device registry, the Smart Factory system has multiple configuration domains. Each is owned by a specific team/module with defined boundaries.

### Ownership by Domain

| Configuration Domain | Owner | Location | Change Process |
|---------------------|-------|----------|----------------|
| Device registry (`device-registry.json`) | controls team | `esp32/data/` | SPIFFS flash; version control |
| ESP32 bridge compile-time config | firmware team | `esp32-ukit-bridge/esp32/include/bridge_config.h` | Firmware build + flash |
| MQTT broker settings | infrastructure team | `infrastructure/config/` (future) | Broker restart required |
| Gateway runtime config | gateway team | `iot-gateway/config/` (future) | Hot reload or restart |
| Dashboard settings | ops team | `dashboard/config/` (future) | Dashboard restart |
| Telemetry retention policy | data team | `contracts/v1/` + DB migration | Coordinated with #31 |

### Module Boundary Rules (per ADR-0001)

Configuration ownership respects the modular monorepo boundaries:

- **esp32-ukit-bridge** owns: bridge compile-time config, device capabilities, topic templates
- **iot-gateway** owns: event transformation rules, MQTT subscription config, REST API config
- **dashboard** owns: UI configuration, chart preferences, alert thresholds
- **digital-twin** owns: 3D model config, simulation parameters
- **factory-control** owns: PLC logic, safety interlock rules

Cross-module configuration (e.g., shared MQTT broker settings) must be documented in `infrastructure/config/` and approved by the infrastructure team.

### Configuration Change Workflow

1. **Propose** change in the owning module's PR
2. **Review** for cross-module impact (check ADRs, integration matrix)
3. **Test** in isolation first, then integration environment
4. **Deploy** with rollback plan documented
5. **Audit** configuration drift quarterly

---

## Maintenance

- **Rotate** `device-registry.json` copies into version control with meaningful commit messages describing what changed and why.
- **Audit** the registry quarterly: remove entries for decommissioned devices, flag stale `last_seen` values (no heartbeat for >7 days).
- **Validate** the registry against this schema before flashing. A JSON schema (`device-registry.schema.json`) in `esp32/data/` can be used by CI to catch field-level errors.
- **Review** configuration ownership matrix annually or when module boundaries change.
