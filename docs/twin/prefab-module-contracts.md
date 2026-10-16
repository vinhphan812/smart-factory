# Nine-Module Prefab Contracts — Digital Twin Telemetry & Command Schema

> **Scope:** Schema documentation only. No Unity C# assets, no prefab implementations.
> Twin engine: see [ADR-0003 Digital Twin Engine](./adr-0012-unity-digital-twin-prefab-contracts.md).
> AMLP/Bridge wire contract: `esp32-ukit-bridge/docs/mqtt-contract.md`.
> Gateway canonical event: `iot-gateway/src/iot_gateway/models.py` → `CanonicalEvent`.
> Known schema mismatch (bridge → canonical): [ADR-0009 Telemetry Schema Compatibility](../adr/adr-0009-telemetry-schema-compatibility.md).

---

## 1  Source-of-Truth Stack

```
Physical ESP32-uKit Bridge
  UART (AMLP frames)  →  MQTT Broker  →  iot-gateway  →  FastAPI / WebSocket
                                                                   ↓
                                             CanonicalEvent {event_type, payload}
                                                                   ↓
                                              Digital Twin Engine (adr-0003)
                                                                   ↓
                                                      Unity Prefab (contract consumer)
```

**Critical chain:** `esp32-ukit-bridge/docs/mqtt-contract.md` → `iot-gateway/src/iot_gateway/event_normalizer.py` (TOPIC_PATTERNS) → `iot-gateway/src/iot_gateway/models.py` (CanonicalEvent) → Twin.

The bridge emits raw `values[]` / `pairs{}` telemetry. The gateway does NOT currently transform to a canonical `state` object — this is the known mismatch documented in ADR-0009. The prefab contracts below reflect what the twin will receive **today**, i.e. the gateway's canonical event payload as-is.

---

## 2  Nine-Module Physical Inventory

The Smart Factory has **one shared CONVEYOR module** (one device, one bridge) and **up to eight per-station actuator modules** (each a separate ESP32-uKit device/bridge).

| Module | Device ID prefix | Bridge | Commands | Telemetry metric |
|---|---|---|---|---|
| Shared Conveyor | `ukit-00000000` (provisioned MAC) | 1 | `CONVEYOR_START`, `CONVEYOR_STOP` | `CONVEYOR` |
| Station 1 Actuator | `ukit-XXXXXXXX` (per device MAC) | 1 per device | `SET_OUTPUT` (channel + value) | `ACTUATOR` / raw sensors |
| Station 2 Actuator | `ukit-XXXXXXXX` | 1 per device | `SET_OUTPUT` | `ACTUATOR` / raw sensors |
| Station 3 Actuator | `ukit-XXXXXXXX` | 1 per device | `SET_OUTPUT` | `ACTUATOR` / raw sensors |
| Station 4 Actuator | `ukit-XXXXXXXX` | 1 per device | `SET_OUTPUT` | `ACTUATOR` / raw sensors |
| Station 5 Actuator | `ukit-XXXXXXXX` | 1 per device | `SET_OUTPUT` | `ACTUATOR` / raw sensors |
| Station 6 Actuator | `ukit-XXXXXXXX` | 1 per device | `SET_OUTPUT` | `ACTUATOR` / raw sensors |
| Station 7 Actuator | `ukit-XXXXXXXX` | 1 per device | `SET_OUTPUT` | `ACTUATOR` / raw sensors |
| Station 8 Actuator | `ukit-XXXXXXXX` | 1 per device | `SET_OUTPUT` | `ACTUATOR` / raw sensors |

Device IDs are provisioned from ESP32 chip MAC at `main.cpp`. Exact IDs must be provisioned and registered in `docs/device-registry.md`.

---

## 3  MQTT Topic Layout

All topics follow `smart-factory/{deviceId}/…`. The gateway subscribes with wildcard `smart-factory/+/command/ack` and `smart-factory/+/status`. Telemetry is not currently in `DEFAULT_TOPICS` (gateway code — `config.py`); confirm routing before relying on it.

| Topic | Direction | QoS | Retain | Notes |
|---|---|---|---|---|
| `smart-factory/{deviceId}/command/down` | Bridge subscribes | 1 | No | Command target |
| `smart-factory/{deviceId}/command/ack` | Bridge publishes | best effort | No | ACK / completion |
| `smart-factory/{deviceId}/telemetry` | Bridge publishes | best effort | No | Telemetry frames |
| `smart-factory/{deviceId}/status` | Bridge publishes | best effort | Yes | Online/offline |

---

## 4  Prefab Contract: Shared Conveyor

**Device type:** `CONVEYOR`
**deviceId:** provisioned from MAC, e.g. `ukit-00000000`

### 4.1  Commands

Command topic: `smart-factory/{deviceId}/command/down`

#### CONVEYOR_START

```json
{
  "command_id": 102,
  "command_name": "CONVEYOR_START",
  "arguments": ["60"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `command_id` | uint32 | Either this OR `request_id` | Preferred correlation ID; converted to string for deduplication |
| `request_id` | string (≤64 bytes) | Either this OR `command_id` | For UUID / legacy callers |
| `command_name` | string | Yes | Must be exactly `CONVEYOR_START` |
| `arguments` | string[] | No | `["speed"]` — printable ASCII 0x21..0x7E, max 64 bytes each |

#### CONVEYOR_STOP

```json
{
  "command_id": 103,
  "command_name": "CONVEYOR_STOP",
  "arguments": []
}
```

Same fields; `arguments` must be an empty array.

### 4.2  Command ACK

Topic: `smart-factory/{deviceId}/command/ack`

**Immediate (synchronous):**

```json
{
  "request_id": "102",
  "status": "unknown_command",
  "status_code": 1
}
```

Status codes: `0` = ok, `1` = unknown_command, `2` = invalid_argument, `3` = internal_error, `4` = queue_full.

**Completion (asynchronous, after UART round-trip):**

```json
{
  "request_id": "102",
  "sequence": 42,
  "command": "CONVEYOR_START",
  "status": "ok",
  "status_code": 0,
  "attempts": 1
}
```

On MEGA failure: `status_code` reflects MEGA status; `status` is the canonical label (e.g. `"unknown_command"`). On timeout (no MEGA ACK after 3 retries × 1000 ms): `status: "timeout"`, no `status_code`.

### 4.3  Telemetry

Topic: `smart-factory/{deviceId}/telemetry`
QoS: best effort; **not retained**; frames may arrive out-of-order.

#### Example: Running

```json
{
  "device_id": "ukit-00000000",
  "received_at_ms": 123456,
  "values": ["CONVEYOR", "RUNNING", "60"],
  "pairs": { "SENSOR1": "1" }
}
```

#### Example: Idle

```json
{
  "device_id": "ukit-00000000",
  "received_at_ms": 123789,
  "values": ["CONVEYOR", "IDLE", "0"],
  "pairs": { "SENSOR1": "0" }
}
```

| Field | Type | Present when |
|---|---|---|
| `device_id` | string | Always |
| `received_at_ms` | integer | Always; monotonic ms since bridge boot |
| `values` | string[] | At least one plain field; first 6 plain fields kept |
| `pairs` | object | Any `key=value` fields; up to 4 pairs kept |

**Field mapping for conveyor prefab:**

| `values[N]` | Meaning | Prefab property |
|---|---|---|
| `values[0]` | Metric type | `"CONVEYOR"` constant |
| `values[1]` | State | `"RUNNING"` \| `"IDLE"` \| `"FAULT"` |
| `values[2]` | Speed | integer string; `"0"` when idle |

| `pairs` key | Meaning | Prefab property |
|---|---|---|
| `SENSOR1` | Entry photo-sensor | `bool` — `"1"` = blocked, `"0"` = clear |
| `SENSOR2` | Exit photo-sensor | `bool` — `"1"` = blocked, `"0"` = clear |
| (arbitrary) | Other sensor keys | Forward-slash-separated multi-sensor key mapping per `device-registry.md` |

### 4.4  Status

Topic: `smart-factory/{deviceId}/status` (retained)

```json
{ "status": "online" }
```

Possible values: `"online"`, `"subscribe_failed"`, `"invalid_json"`, or other bridge states. No Last Will currently configured.

### 4.5  Staleness Policy

Unity must mark telemetry stale when no new frame arrives within `kTelemetryTimeoutMs` = **60 000 ms** (configured in `bridge_config.h`, adjustable). Use `received_at_ms` for ordering — frames are not guaranteed in-order delivery.

### 4.6  Duplicate / Idempotency

Bridge stores results for the last **16** command IDs. MQTT publishers must not reuse a `command_id` while it could still be in the cache. Duplicate ACK: same JSON payload re-delivered; client should de-duplicate by `command_id`.

---

## 5  Prefab Contract: Station Actuator (×8)

**Device type:** `ACTUATOR` (generic)
**deviceId:** per-station MAC-provisioned ID, e.g. `ukit-AABBCCDD`

### 5.1  Commands

#### SET_OUTPUT

```json
{
  "command_id": 200,
  "command_name": "SET_OUTPUT",
  "arguments": ["2", "1"]
}
```

| Argument index | Meaning | Example |
|---|---|---|
| `arguments[0]` | Channel (port number) | `"1"`–`"4"` |
| `arguments[1]` | Value (0 = off, 1 = on) | `"0"` or `"1"` |

Only the **first 2 arguments** are processed by the firmware. Additional arguments are silently dropped.

### 5.2  Command ACK

Same schema as conveyor (Section 4.2). `command` field will be `"SET_OUTPUT"`.

### 5.3  Telemetry

```json
{
  "device_id": "ukit-AABBCCDD",
  "received_at_ms": 234567,
  "values": ["ACTUATOR", "CH2", "ON"],
  "pairs": { "PRESSURE": "512", "TEMP": "2534" }
}
```

**Field mapping for actuator prefab:**

| `values[N]` | Meaning | Prefab property |
|---|---|---|
| `values[0]` | Metric type | `"ACTUATOR"` constant |
| `values[1]` | Channel / state | `"CH1"`–`"CH4"`, `"ON"`, `"OFF"`, or sensor label |
| `values[2]` | Value | integer or status string |

| `pairs` | Sensor readings | Per-station sensor mapping from `device-registry.md` |

**Known mismatch (ADR-0009):** The `values` array is a raw ordered list; semantic indexing (`values[1]` = channel) relies on convention not enforced by schema. Prefabs must validate index bounds before accessing. When the canonical telemetry format (ADR-0009 resolution) is promoted, a structured `state` object will replace the array.

### 5.4  Status

Same as conveyor (Section 4.4).

### 5.5  Staleness / Duplicate

Same policy as conveyor (Section 4.5 / 4.6).

---

## 6  Gateway Canonical Event Envelope

All events arrive at the twin via the gateway's WebSocket broadcast and FastAPI REST endpoint as `CanonicalEvent` objects (`iot-gateway/src/iot_gateway/models.py`):

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "device_id": "ukit-00000000",
  "event_type": "telemetry",
  "payload": {
    "device_id": "ukit-00000000",
    "received_at_ms": 123456,
    "values": ["CONVEYOR", "RUNNING", "60"],
    "pairs": { "SENSOR1": "1" }
  },
  "mqtt_topic": "smart-factory/ukit-00000000/telemetry",
  "mqtt_timestamp_ms": 0,
  "ingested_at": "2026-10-16T12:00:00.000+00:00",
  "sequence": 42
}
```

**`event_type` values** (from `EventType` enum in `models.py`):

| Enum value | When |
|---|---|
| `command_ack` | ACK published on `smart-factory/{deviceId}/command/ack` |
| `status_online` | `status: "online"` on `smart-factory/{deviceId}/status` |
| `status_offline` | Any other status value |
| `telemetry` | Telemetry frame on `smart-factory/{deviceId}/telemetry` |
| `heartbeat` | Future: `smart-factory/{deviceId}/heartbeat` |

The twin should ignore `heartbeat` events until wired. Telemetry `mqtt_timestamp_ms` is always 0 (bridge does not emit it); use `received_at_ms` for ordering.

---

## 7  WebSocket Broadcast Contract

The gateway's `WebSocketServer` (`api.py`) broadcasts every `CanonicalEvent.to_dict()` as a JSON string to all connected clients on port `WS_PORT` (default 8000).

- Max queue per client: **64** messages.
- Slow client handling: lagging clients are **disconnected** (queue full → `put_nowait` raises `QueueFull` → client removed).
- Twin must consume faster than the gateway write rate; dropped connections indicate consumer saturation.

```text
Client connects → ws://host:8000
Server pushes → raw JSON string per event (no wrapping envelope)
```

---

## 8  REST API Contract

| Endpoint | Method | Returns |
|---|---|---|
| `/health` | GET | `{"status": "ok", "event_count": N}` |
| `/events` | GET | `{"events": [...], "count": N}` |
| `/events?device_id=X&event_type=telemetry&limit=100` | GET | Filtered events |
| `/events/{event_id}` | GET | Single event or 404 |

Query parameters: `device_id` (string), `event_type` (string — one of the `EventType` enum values), `limit` (int, 1–10000, default 100).

---

## 9  Coordinate & Transform Conventions

These are **planned / simulated** — not yet implemented. Flag institutional approval as unverified per ADR-0003.

| Convention | Value | Source |
|---|---|---|
| World origin | Physical factory origin (0,0,0) | Physical layout spec |
| Conveyor travel axis | +X (left-to-right) | Physical layout spec |
| Station spacing | 600 mm | Physical layout spec |
| Y-axis | Vertical | Physical layout spec |
| Z-axis | Depth (out of floor plan) | Physical layout spec |
| Twin update rate | ≤ `received_at_ms` resolution | Telemetry |
| Interlock override | E-stop signal → all actuators OFF | Physical safety spec |

**No coordinate system is currently defined in code.** The prefab must defer transform initialization until ADR-0003 is resolved (institutional approval unverified).

---

## 10  Compatibility & Versioning Notes

| Concern | Current state | Resolution |
|---|---|---|
| Telemetry schema mismatch | `values[]`/`pairs{}` vs canonical `state{}` | ADR-0009; Issue #66 |
| Telemetry topic subscription | Not in `DEFAULT_TOPICS` | Verify gateway routing before wiring twin |
| Heartbeat topic | Defined in normalizer; not in `DEFAULT_TOPICS` | Wire when broker supports it |
| AMLP field limits | Max 6 plain values, 4 pairs per frame | Prefab must handle partial data |
| Duplicate/out-of-order telemetry | Bridge QoS 0, no retransmission | Use `received_at_ms` ordering; mark stale at 60 s |
| Staleness | No expiry encoded in payload | Twin-side timer: 60 s timeout |

All field values are **raw strings**. Prefabs must parse to the appropriate type before use. No null coercion is performed by the gateway.
