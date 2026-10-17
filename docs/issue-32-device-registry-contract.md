# Issue #32 — Device Registry and Configuration Ownership Spec

> **Status:** Proposed  
> **Issue:** [#32](https://github.com/vinhphan812/smart-factory/issues/32)  
> **Author:** Agent  
> **Reviewer:** vinhphan812  
> **Date:** 2026-10-17

---

## Table of Contents

1. [Current State: Device IDs in Use](#1-current-state-device-ids-in-use)
2. [Device Registry Design](#2-device-registry-design)
3. [Configuration Ownership](#3-configuration-ownership)
4. [Telemetry Schema per Device Type](#4-telemetry-schema-per-device-type)
5. [What Is NOT Yet Implemented](#5-what-is-not-yet-implemented)
6. [Relationship to ADR-0002 and ADR-0005](#6-relationship-to-adr-0002-and-adr-0005)

---

## 1. Current State: Device IDs in Use

### 1.1 How Device IDs Are Assigned

**ESP32 bridge (`esp32-ukit-bridge/esp32/`):**  
The device ID is derived from the ESP32 chip's MAC address at compile time in `esp32/src/main.cpp`:

```cpp
void makeClientId() {
  const uint64_t chipId = ESP.getEfuseMac();
  std::snprintf(mqttClientId, sizeof(mqttClientId), "ukit-%08lx",
                static_cast<unsigned long>(chipId & 0xFFFFFFFFULL));
}
```

The result is a lowercase 17-character string of the form `ukit-00000000`. This is used as the MQTT client ID and substituted into all per-device MQTT topic segments.

**IoT gateway (`iot-gateway/`):**  
The gateway does not assign device IDs. It extracts them by regex from inbound MQTT topic paths in `event_normalizer.py`:

```python
# Topic patterns → (device_id extraction regex, event_type)
TOPIC_PATTERNS = [
    (re.compile(r"^smart-factory/([^/]+)/command/ack$"), EventType.COMMAND_ACK),
    (re.compile(r"^smart-factory/([^/]+)/status$"),      None),
    (re.compile(r"^smart-factory/([^/]+)/telemetry$"),   EventType.TELEMETRY),
    (re.compile(r"^smart-factory/([^/]+)/heartbeat$"),   EventType.HEARTBEAT),
]
```

The captured group `([^/]+)` yields the device ID segment from any matching topic. The gateway treats the device ID as an opaque string; it does not validate format or consult a registry.

**Factory default topics (compiled into gateway `config.py`):**

```python
DEFAULT_TOPICS = [
    "smart-factory/+/command/ack",
    "smart-factory/+/status",
    "smart-factory/+/telemetry",
    "smart-factory/+/heartbeat",
]
```

These wildcard subscriptions cover any device ID conforming to the `+`-wildcard path, so the gateway accepts events from any device publishing to the `smart-factory/{deviceId}/...` hierarchy.

### 1.2 Ownership Summary

| Component | Owns device ID? | Assignment method | Mutable? |
|---|---|---|---|
| ESP32 firmware | Yes (chip-derived) | `ESP.getEfuseMac()` at boot | No — hardwired per chip |
| IoT gateway | No | Extracts from topic | No — no registry lookup |
| `device-registry.md` | Design document | Human-assigned names (`bridge-001`, etc.) | Design intent: yes |

**Current gap:** The gateway has no authoritative source of truth for device identity. Any device can publish to any `smart-factory/{deviceId}/...` topic and the event will be accepted. The schema in `docs/device-registry.md` defines an ownership model with `owner.team` and `owner.contact` fields, but this is **not enforced by any code**.

---

## 2. Device Registry Design

### 2.1 Design Document vs. Implementation

The canonical design lives in `docs/device-registry.md` (277 lines). The following subsections extract and annotate the key design decisions against the current codebase.

### 2.2 Device ID Format (Design)

Per `docs/device-registry.md`:

| Property | Value |
|---|---|
| Characters | Lowercase `a`–`z`, digits `0`–`9`, hyphen `-`, underscore `_` |
| Max length | 64 characters |
| Case | Lowercase only |
| Start/end | Must start with a letter; must not end with `-` or `_` |

**Example design IDs:** `bridge-001`, `mega-conveyor-a`, `mega-robot-arm-01`

**Current state:** The firmware uses the `ukit-{mac8}` format (e.g., `ukit-3a4b5c6d`). This is a lowercase hexadecimal string with a prefix, which conforms to the format rules. However, the gateway has no format validation.

### 2.3 Device Types

The registry schema defines four device types:

| Type | Description |
|---|---|
| `esp32_bridge` | ESP32-S3 bridge acting as MQTT↔UART protocol translator |
| `mega_reference` | MEGA microcontroller running UBTEDU firmware (UART peer) |
| `iot_gateway` | Edge/cloud gateway consuming MQTT and exposing WebSocket/REST |
| `simulator` | Software simulator for offline testing |

The `device_type` field is used by the integration matrix and for capability routing. No code currently enforces or checks this field.

### 2.4 Capabilities

Each device type declares a `capabilities[]` array listing commands and telemetry streams it handles. The design specifies:

| Device type | Commands | Telemetry |
|---|---|---|
| `esp32_bridge` | `CONVEYOR_START`, `CONVEYOR_STOP`, `get_telemetry` | `telemetry_periodic` |
| `mega_reference` | `CONVEYOR_START`, `CONVEYOR_STOP` | `telemetry_periodic` |
| `simulator` | `CONVEYOR_START`, `CONVEYOR_STOP`, `get_telemetry` | `telemetry_periodic` |
| `iot_gateway` | `mqtt_publish`, `mqtt_subscribe`, `amlp_decode` | — |

**Current state:** Capabilities are not enforced in the gateway. The `event_normalizer.py` has no capability lookup. The ESP32 bridge hard-codes command allowlist checking in firmware.

### 2.5 State Machine

The design specifies a per-device lifecycle. The ESP32 bridge firmware publishes these retained `status` values on `smart-factory/{deviceId}/status`:

| Status | Meaning |
|---|---|
| `online` | Device is connected to MQTT broker |
| `subscribe_failed` | MQTT subscription failed |
| `invalid_json` | Malformed command received |
| *(others)* | Firmware-defined failure states |

The gateway models these as `EventType.STATUS_ONLINE` / `EventType.STATUS_OFFLINE` derived from the payload `online` boolean.

Command lifecycle (from `contracts-and-data.md`):

```
requested → authorized/rejected → queued → dispatched
  → ack_received → verified_success / failed / timed_out
```

**Current state:** The gateway's `CanonicalEvent` model has fields for `mqtt_timestamp_ms`, `sequence`, and `ingested_at`, but the full command lifecycle state machine is **not implemented**. Only `COMMAND_ACK` (completion ACK), `STATUS_ONLINE`, `STATUS_OFFLINE`, `TELEMETRY`, and `HEARTBEAT` event types exist in `models.py`.

---

## 3. Configuration Ownership

### 3.1 Registry File and Storage

Design intent (per `docs/device-registry.md`):

- **Current:** `esp32/data/device-registry.json` in ESP32 SPIFFS
- **Future:** etcd or MQTT discovery

At startup, the ESP32 bridge loads this file, validates it, and uses `mqtt_topics` entries to configure its MQTT client. If absent or invalid, the bridge falls back to compile-time defaults from `esp32/include/bridge_config.h` and logs a warning.

**Current state:** The firmware uses compile-time topic names in `MqttBridge::begin()`; no SPIFFS registry loading code exists. The JSON file and loading logic are **not implemented**.

### 3.2 Who Can Update Device Config

Per the design:

| Actor | Permission |
|---|---|
| `owner.team` | May update `capabilities`, `mqtt_topics`, `physical_location`, `firmware_version` |
| Device (heartbeat) | Auto-updates `last_seen` |
| Registry admin | May add/remove device entries |

**Current state:** No access control is enforced. Filesystem write access to the JSON source file is the only gate. Broker-level MQTT client authentication and per-topic ACLs are marked future.

### 3.3 Versioning

| Config element | Versioning method |
|---|---|
| Firmware version | Reported via retained status; no semantic version enforcement |
| `device-registry.json` | Rotated into version control with commit messages; no automated version tracking |
| Per-device schema changes | No version field in registry entry |
| Gateway config | Environment variables only (`GatewayConfig.from_env()` in `config.py`); no runtime reload |

The `GatewayConfig` dataclass reads from `MQTT_BROKER`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `DATABASE_URL`, `WS_HOST`, `WS_PORT`, `WS_HTTP_PORT`, `MAX_EVENTS`. There is no device-scoped config — only one gateway instance is assumed.

---

## 4. Telemetry Schema per Device Type

### 4.1 ESP32 Bridge → MQTT Telemetry (Implemented)

As documented in `esp32-ukit-bridge/docs/mqtt-contract.md`, the bridge publishes parsed AMLP telemetry to `smart-factory/{deviceId}/telemetry` (QoS 0, not retained):

```json
{
  "device_id": "ukit-00000000",
  "received_at_ms": 123456,
  "values": ["CONVEYOR", "RUNNING", "60"],
  "pairs": { "SENSOR1": "1" }
}
```

- `values`: raw string array from plain AMLP fields (max 6, excess silently dropped)
- `pairs`: key=value parsed fields stored as `{key: value}` (max 4, excess silently dropped)
- `received_at_ms`: monotonic ESP32 uptime in ms at frame recognition — **not UTC**; the gateway's `event_normalizer.py` detects this and sets `is_timestamp_synchronized = False`
- Backpressure: dropped if MQTT write buffer full; UART poll loop never blocked
- Staleness: Unity marks telemetry stale after `kTelemetryTimeoutMs` (60 s, configurable in `bridge_config.h`)

The raw AMLP UART telemetry format from the MEGA endpoint:

```
TEL,<metric>,<value>[,<value>...]
TEL,CONVEYOR,RUNNING,60,SENSOR1=1
TEL,TEMP,2534,HUMIDITY=6550,SENSOR2=0
```

### 4.2 Gateway Canonical Telemetry (Partially Implemented)

The `event_normalizer.py` maps the bridge telemetry payload into `CanonicalEvent`:

```python
return CanonicalEvent(
    device_id=device_id,
    event_type=EventType.TELEMETRY,
    payload=payload,  # raw bridge payload preserved
    mqtt_topic=topic,
    mqtt_timestamp_ms=...,
    event_timestamp_ms=event_ts_ms,   # = received_at_ms for uptime source
    received_at=received_at_str,
    received_at_ms=received_at_ms,
    latency_ms=-1,  # undefined for uptime source
    stale=is_stale,
    out_of_order=is_out_of_order,
    is_timestamp_synchronized=False,
    sequence=self._next_sequence(),
)
```

The gateway's `models.py` defines the envelope as:

```python
@dataclass
class CanonicalEvent:
    event_id: str        # UUID v4
    device_id: str
    event_type: EventType
    payload: dict
    mqtt_topic: str
    mqtt_timestamp_ms: int
    ingested_at: str     # UTC ISO8601
    sequence: int        # gateway-internal counter
```

### 4.3 Schema Mismatch with contracts/v1/

ADR-0002 §"Harder" notes: `telemetry.schema.json` (in `contracts/v1/`) uses `timestamp`/`state` field names, but the bridge sends `received_at_ms`/`values`/`pairs`. This mismatch is tracked in ADR-0009 (Telemetry Schema Compatibility). A contract normalization layer has not yet been built.

### 4.4 Future Telemetry Types

The design documents `mega_reference` (MEGA-uKit direct telemetry) and `simulator` (simulated telemetry every 1 s). Neither is currently connected to the gateway's MQTT subscription model.

---

## 5. What Is NOT Yet Implemented

The following items are **design only** (stated in `docs/device-registry.md` as 🔒 Planned) and have no corresponding code:

| Item | Design location | Blocker |
|---|---|---|
| SPIFFS JSON registry loading at ESP32 startup | `docs/device-registry.md` §"Where the Registry Lives" | No `device-registry.json` file or loading code in firmware |
| Dynamic topic configuration from registry | `docs/device-registry.md` §"Where the Registry Lives" | `MqttBridge` uses compile-time topic names |
| Ownership/capabilities enforcement in gateway | `docs/device-registry.md` §"Ownership model" | No registry lookup in gateway code |
| etcd-backed central registry | `docs/device-registry.md` §"Future: etcd" | Registry authority service not designed |
| MQTT auto-discovery | `docs/device-registry.md` §"Auto-Discovery" | Registry service, broker config, firmware discovery protocol all absent |
| Command lifecycle state machine | `contracts-and-data.md` §"Commands and safety" | Gateway only tracks completion ACK; no authorized/queued/dispatched/verified states |
| Telemetry schema normalization | ADR-0009 | `contracts/v1/` schema fields (`timestamp`/`state`) don't match bridge output (`received_at_ms`/`values`/`pairs`) |
| Broker-level MQTT ACLs | `docs/device-registry.md` §"Access control" | No username/password or client certificate auth configured |
| `firmware_version` field in status payload | `docs/device-registry.md` §"Example entry" | Firmware does not publish version in retained status |
| Per-device capability validation in gateway | `docs/device-registry.md` §"Device Capability Declarations" | Gateway accepts any command for any device |
| Auto-discovery by gateway of new device IDs | `docs/device-registry.md` §"Onboarding" | Gateway subscribes to `+/+/...` wildcards but registers no new devices |
| Runtime gateway config reload | `iot-gateway/src/iot_gateway/config.py` | Config loaded once at startup from env; no hot reload |

---

## 6. Relationship to ADR-0002 and ADR-0005

### ADR-0002: Bridge MQTT ↔ AMLP Contract

ADR-0002 establishes the wire contract between the ESP32 bridge and the MEGA endpoint, including:

- Downlink: JSON command envelope on `smart-factory/{deviceId}/command/down` → AMLP UART frame
- Uplink: AMLP TEL frames → JSON on `smart-factory/{deviceId}/telemetry`
- ACK/result semantics with `command_id` correlation and retry logic

**Relationship to this spec:**  
The device registry builds on ADR-0002's topic structure. The `{deviceId}` segment in all ADR-0002 topics is precisely the device ID this registry would manage. However, ADR-0002 derives `deviceId` from the ESP32 chip MAC at compile time — the registry cannot override it. If a registry entry specifies `mqtt_topics` for an ESP32 bridge, the `{deviceId}` substitution must match the chip-derived ID, or the device will not receive its own commands.

ADR-0002 also documents the telemetry schema (`values`/`pairs`/`received_at_ms`) that the gateway normalizes. The registry has no schema for device telemetry beyond the `capabilities[]` declaration — the actual payload shapes are defined by the ADR-0002 wire spec and ADR-0009 schema compatibility work.

### ADR-0005: Gateway Canonical Event Envelope

ADR-0005 defines the canonical envelope that the gateway produces after normalizing incoming MQTT events.

**Relationship to this spec:**  
ADR-0005 assumes a known set of device IDs — it does not specify how those IDs are provisioned or validated. This spec fills that gap by defining the registry and ownership model that ADR-0005's normalizer would consult (but currently does not). Specifically:

- ADR-0005's requirement *"Device ID MUST NOT be truncated or remapped without a documented mapping"* requires an authoritative registry to enforce
- ADR-0005's *"Malformed/unknown-device events → quarantine log"* implies device identity validation — which the gateway currently skips
- ADR-0005's routing rules use `event_type` and `device_id` — both come from the registry's `device_type` and `capabilities` in the full design

The gap: ADR-0005's normalizer (`event_normalizer.py`) extracts `device_id` from the topic path but never validates it against a registry. A future integration step is to wire the normalizer to a registry lookup so that unknown device IDs are quarantined instead of forwarded.

### Dependency Summary

```
ADR-0002 (wire contract)
  └── Topic structure: smart-factory/{deviceId}/...
        └── ADR-0005 (canonical envelope) normalizes these topics
              └── This spec (device registry) provides identity and ownership
                    └── Not yet wired: gateway validates device IDs against registry
```

ADR-0002 and ADR-0005 are both in **Proposed** status. Changes to either may require corresponding updates to this spec.

---

*Document does not claim implementation completeness. All "NOT IMPLEMENTED" items are marked as design only pending approved implementation issues.*
