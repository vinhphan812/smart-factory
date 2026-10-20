# Telemetry Schema v2 — Canonical Gateway Contract

**Status:** Canonical ✅  
**Version:** 2.0  
**Date:** 2026-10-20  
**Supersedes:** `contracts/v1/schemas/telemetry.schema.json`  
**Related Issues:** #166, #65, #66, #163  
**References:** [ADR-0009](./adr-0009-telemetry-schema-compatibility.md)

---

## Overview

This document defines the canonical v2 telemetry schema that resolves the incompatibility between:

1. **ESP32 bridge telemetry** — emits `received_at_ms`, `values[]`, `pairs{}`
2. **v1 canonical schema** — expected `timestamp` (ISO 8601), `state`, `speed`, `sensors{}`

The v2 schema provides a unified canonical format with explicit versioning, time-domain normalization, and a migration path from v1.

---

## Schema Incompatibility Analysis

### Current State

| Aspect | ESP32 Bridge (`publishTelemetry`) | v1 Canonical Schema | Incompatibility |
|--------|----------------------------------|---------------------|-----------------|
| **Timestamp field** | `received_at_ms` (uint32, monotonic ms since boot) | `timestamp` (ISO 8601 UTC string) | **CRITICAL** — Time domain and format differ |
| **Time domain** | Monotonic milliseconds (local uptime) | UTC wall clock | **CRITICAL** — Cannot correlate with external events |
| **Content structure** | `values[]` (array) + `pairs{}` (object) | `state` (string), `speed` (int), `sensors{}` (object) | **MAJOR** — Semantic mapping unclear |
| **Sensor fields** | Generic key-value pairs (e.g., `SENSOR1=1`) | Named fields: `temperature_centi_c`, `humidity_centi_percent`, `digital_inputs` | **MAJOR** — No field-level mapping |
| **Overflow handling** | Explicit `truncated`, `overflow_dropped_values`, `overflow_dropped_pairs` | Not specified | **MINOR** — v1 silent about truncation |

### Evidence

**ESP32 bridge output** (`mqtt_bridge.h:41-91`, `mqtt_bridge.cpp:370-380`):

```json
{
  "device_id": "ukit-00000000",
  "received_at_ms": 123456,
  "values": ["CONVEYOR", "RUNNING", "60"],
  "pairs": { "SENSOR1": "1" },
  "truncated": false,
  "overflow_dropped_values": 0,
  "overflow_dropped_pairs": 0
}
```

**v1 schema expected output** (`contracts/v1/schemas/telemetry.schema.json`):

```json
{
  "device_id": "bridge-001",
  "timestamp": "2026-10-12T08:30:45.123Z",
  "state": "STATE",
  "speed": 60,
  "sensors": {
    "temperature_centi_c": 2534,
    "humidity_centi_percent": 6550,
    "digital_inputs": 5
  },
  "uptime": 123456
}
```

---

## v2 Canonical Schema

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://smart-factory.example.com/contracts/v2/schemas/telemetry.schema.json",
  "title": "Telemetry v2",
  "description": "Canonical telemetry payload emitted by ESP32 bridge and consumed by iot-gateway, Digital Twin, and dashboard.",
  "type": "object",
  "required": ["schema_version", "device_id", "timestamp", "source_format"],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "2.0",
      "description": "Schema version identifier. Must be '2.0' for v2 canonical format."
    },
    "device_id": {
      "type": "string",
      "description": "Bridge device identifier (e.g., 'ukit-00000000').",
      "examples": ["ukit-00000000"]
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp (UTC) when the telemetry was captured at the gateway boundary. Converted from ESP32 received_at_ms + gateway wall-clock offset."
    },
    "source_format": {
      "type": "string",
      "enum": ["amlp-raw", "amlp-structured"],
      "description": "Indicates the original telemetry format from the bridge. 'amlp-raw' = v1 legacy (values/pairs); 'amlp-structured' = future structured format."
    },
    "uptime_ms": {
      "type": "integer",
      "minimum": 0,
      "description": "ESP32 monotonic timestamp (milliseconds since boot) at telemetry capture. Identical to received_at_ms from raw payload."
    },
    "raw": {
      "type": "object",
      "description": "Original ESP32 telemetry payload (v1 bridge output). Present when source_format is 'amlp-raw'.",
      "properties": {
        "received_at_ms": {
          "type": "integer",
          "description": "Monotonic millisecond timestamp from ESP32."
        },
        "values": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Raw string values from AMLP TEL frame."
        },
        "pairs": {
          "type": "object",
          "additionalProperties": { "type": "string" },
          "description": "Key-value pairs from AMLP TEL frame."
        },
        "truncated": {
          "type": "boolean",
          "description": "True if any telemetry fields were dropped due to buffer overflow."
        },
        "overflow_dropped_values": {
          "type": "integer",
          "minimum": 0,
          "description": "Number of raw values dropped due to overflow."
        },
        "overflow_dropped_pairs": {
          "type": "integer",
          "minimum": 0,
          "description": "Number of key-value pairs dropped due to overflow."
        }
      },
      "required": ["received_at_ms"],
      "additionalProperties": false
    },
    "structured": {
      "type": "object",
      "description": "Normalized sensor and state data. Populated by gateway translator from raw payload.",
      "properties": {
        "state": {
          "type": "string",
          "description": "Current device state (e.g., 'RUNNING', 'IDLE', 'FAULT').",
          "examples": ["RUNNING", "IDLE", "STOPPED"]
        },
        "speed": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100,
          "description": "Conveyor speed setting (0 when stopped)."
        },
        "sensors": {
          "type": "object",
          "description": "Normalized sensor readings.",
          "properties": {
            "digital_inputs": {
              "type": "integer",
              "minimum": 0,
              "maximum": 65535,
              "description": "16-bit bitmask of digital input states."
            },
            "temperature_centi_c": {
              "type": "integer",
              "description": "Temperature in hundredths of degrees Celsius (divide by 100)."
            },
            "humidity_centi_percent": {
              "type": "integer",
              "minimum": 0,
              "maximum": 10000,
              "description": "Relative humidity in hundredths of a percent (divide by 100)."
            },
            "custom": {
              "type": "object",
              "description": "Additional sensor key-value pairs not mapped to standard fields.",
              "additionalProperties": { "type": "string" }
            }
          },
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    },
    "metadata": {
      "type": "object",
      "description": "Gateway-side metadata.",
      "properties": {
        "gateway_id": {
          "type": "string",
          "description": "Identifier of the gateway that processed this telemetry."
        },
        "translated_at": {
          "type": "string",
          "format": "date-time",
          "description": "ISO 8601 timestamp when the gateway performed translation."
        },
        "translation_errors": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Any errors encountered during translation."
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

### Example v2 Payloads

#### AMLP Raw Format (v1 Legacy)

```json
{
  "schema_version": "2.0",
  "device_id": "ukit-00000000",
  "timestamp": "2026-10-20T14:30:45.123Z",
  "source_format": "amlp-raw",
  "uptime_ms": 123456,
  "raw": {
    "received_at_ms": 123456,
    "values": ["CONVEYOR", "RUNNING", "60"],
    "pairs": { "SENSOR1": "1" },
    "truncated": false,
    "overflow_dropped_values": 0,
    "overflow_dropped_pairs": 0
  },
  "structured": {
    "state": "RUNNING",
    "speed": 60,
    "sensors": {
      "digital_inputs": 1,
      "custom": { "SENSOR1": "1" }
    }
  },
  "metadata": {
    "gateway_id": "gateway-001",
    "translated_at": "2026-10-20T14:30:45.200Z"
  }
}
```

#### Future Structured Format (amlp-structured)

```json
{
  "schema_version": "2.0",
  "device_id": "ukit-00000000",
  "timestamp": "2026-10-20T14:30:45.123Z",
  "source_format": "amlp-structured",
  "uptime_ms": 123456,
  "structured": {
    "state": "RUNNING",
    "speed": 60,
    "sensors": {
      "temperature_centi_c": 2534,
      "humidity_centi_percent": 6550,
      "digital_inputs": 5
    }
  }
}
```

---

## Migration Path: v1 → v2

### Phase 1: Gateway Translator (Current → v2)

**Location:** `iot-gateway/src/translators/telemetry_translator.py`

The gateway must implement a translator that:

1. Receives ESP32 telemetry (`received_at_ms`, `values[]`, `pairs{}`)
2. Converts `received_at_ms` to ISO 8601 `timestamp` using gateway wall-clock offset estimation
3. Normalizes `values[]` and `pairs{}` into `structured` object
4. Wraps everything in the v2 envelope with `schema_version: "2.0"`

**Translation rules:**

| ESP32 Field | v2 Canonical Field | Notes |
|-------------|-------------------|-------|
| `device_id` | `device_id` | Pass-through |
| `received_at_ms` | `timestamp` | Convert: `gateway_utc_now - (gateway_uptime - received_at_ms)` |
| `received_at_ms` | `uptime_ms` | Preserved as-is |
| `values[0]` | `structured.state` | First value is typically state identifier |
| `values[N]` | `structured.speed` | If numeric, parse as speed (0-100) |
| `pairs{KEY=VAL}` | `structured.sensors.custom[KEY]` | Unmapped pairs go to custom |
| `pairs{SENSOR1..SENSOR8}` | `structured.sensors.digital_inputs` | Bitmask construction |
| `pairs{TEMP}` | `structured.sensors.temperature_centi_c` | If value is numeric |
| `pairs{HUMIDITY}` | `structured.sensors.humidity_centi_percent` | If value is numeric |
| `truncated` | `raw.truncated` | Pass-through |

### Phase 2: Dual-Format Support (6 months)

During transition:
- Gateway accepts both v1-style raw payloads (direct from ESP32) and v2 payloads (from updated firmware)
- All outbound telemetry is v2 format
- Dashboard/Twin must be updated to consume v2

### Phase 3: Firmware Update (Future)

ESP32 firmware update to emit v2-structured format directly:
- Eliminates translation overhead
- Reduces MQTT payload size
- Provides explicit sensor field names

---

## Time Domain Normalization

### Problem

ESP32 uses **monotonic milliseconds since boot** (`received_at_ms`), which:
- Cannot be correlated with UTC wall-clock events
- Wraps after ~49.7 days (uint32 overflow)
- Provides no timezone information

### Solution

Gateway maintains an offset estimation:

```
gateway_offset_ms = gateway_utc_now_ms - gateway_uptime_ms
telemetry_timestamp_utc = received_at_ms + gateway_offset_ms
```

**Constraints:**
- Gateway must track its own uptime accurately
- Offset is estimated, not guaranteed precise (< 1 second tolerance)
- For precision requirements, use NTP-synchronized ESP32 timestamps (future enhancement)

---

## Backward Compatibility

### v1 Schema Deprecation

The v1 schema (`contracts/v1/schemas/telemetry.schema.json`) is **deprecated** and marked as:

```
"status": "deprecated - use v2 schema"
```

Consumers should migrate to v2 by **2026-12-31**.

### Legacy Support

- Gateway accepts v1-style raw payloads until deprecation date
- Dashboard/Twin must handle `source_format: "amlp-raw"` vs `source_format: "amlp-structured"`
- All new development must use v2 schema

---

## Validation

### JSON Schema Validation

```bash
# Validate v2 telemetry against schema
ajv validate -s contracts/v2/schemas/telemetry.schema.json -d examples/telemetry-v2-raw.json
ajv validate -s contracts/v2/schemas/telemetry.schema.json -d examples/telemetry-v2-structured.json
```

### Test Cases

| Test | Description | Expected |
|------|-------------|----------|
| TC1 | Valid raw AMLP payload | Parses successfully, `source_format: "amlp-raw"` |
| TC2 | Truncated telemetry | `truncated: true`, overflow counts preserved |
| TC3 | Empty values/pairs | Valid v2 with empty `raw` object |
| TC4 | Custom sensor pairs | Mapped to `structured.sensors.custom` |
| TC5 | Missing optional fields | Valid per JSON Schema |
| TC6 | Invalid timestamp format | Rejected with validation error |
| TC7 | Unknown source_format | Rejected with validation error |

---

## File Locations

| File | Purpose |
|------|---------|
| `contracts/gateway/telemetry-schema-v2.md` | This document |
| `contracts/v2/schemas/telemetry.schema.json` | JSON Schema definition |
| `contracts/v2/examples/telemetry-v2-raw.json` | AMLP raw format example |
| `contracts/v2/examples/telemetry-v2-structured.json` | Structured format example |
| `iot-gateway/src/translators/telemetry_translator.py` | Gateway translation implementation |
| `esp32-ukit-bridge/esp32/include/telemetry_frame.h` | ESP32 TelemetryFrame struct |
| `esp32-ukit-bridge/esp32/include/mqtt_bridge.h` | ESP32 publishTelemetry function |

---

## Changelog

| Date | Version | Change |
|------|---------|--------|
| 2026-10-20 | 2.0 | Initial canonical schema with migration path |
| 2026-10-14 | 1.0-proposed | ADR-0009 documented incompatibility |

---

## References

- [ADR-0009: Telemetry Schema Compatibility](../docs/adr/adr-0009-telemetry-schema-compatibility.md)
- [ESP32 TelemetryFrame](../esp32-ukit-bridge/esp32/include/telemetry_frame.h)
- [ESP32 publishTelemetry](../esp32-ukit-bridge/esp32/include/mqtt_bridge.h)
- [AMLP Protocol Specification](../esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md)
- [MQTT Contract](../esp32-ukit-bridge/docs/mqtt-contract.md)
