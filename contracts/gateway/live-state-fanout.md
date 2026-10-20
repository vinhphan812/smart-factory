# Gateway Northbound Live-State Fanout Contract

**Owner:** Issue #194 (wave: 2-gateway-core, P0)  
**Version:** 1.0.0  
**Status:** Draft  
**Context:** ADR-0013 (Yanshee), ADR-0014 (FIWARE/Orion-LD), Issue #197 (entity schema)

---

## Overview

The IoT Gateway (`iot-gateway/`) is the single fanout point for northbound live-state data. After a canonical event is committed to SQLite, the gateway broadcasts it over three northbound transports simultaneously. Each transport serves different downstream consumers with different delivery semantics.

```
Canonical Event (SQLite commit)
        │
        ├──► WebSocket broadcast  ──► Unity Twin, React Dashboard
        ├──► SSE endpoint          ──► FIWARE Orion-LD, analytics
        └──► MQTT re-publish       ──► Orion-LD ContextSink (NGSI-LD upsert)
                                       Robot (Yanshee) via AlertService
```

The gateway **does not** transform, route, or filter events per-consumer in the northbound path — it fans out the same canonical envelope to all transports. Consumers are responsible for extracting the data they need.

---

## 1. Fanout Transports

### 1.1 WebSocket (Primary real-time transport)

**Endpoint:** `ws://<gateway-host>:<ws_port>/`  
**Protocol:** RFC-6455 WebSocket, JSON frames  
**Implementation:** `iot-gateway/src/iot_gateway/api.py` — `WebSocketServer` class

**Behavior:**
- Every canonical event is serialized to JSON and enqueued in each connected client's per-client queue.
- Clients that overflow their queue (max 64 messages) are disconnected silently (no blocking).
- There is **no per-subscription topic filtering** on the server — all clients receive all events. Clients must filter client-side by `event_type` or `device_id` if needed.
- Heartbeat: server sends no keep-alive frames; clients are responsible for ping/pong and reconnection on silence.

**Connection lifecycle:**
```
CONNECT ws://gateway:8765/
  ← server sends no greeting
  ← server pushes events as JSON objects, one per frame
  ← client sends WebSocket ping (optional, server pong)
DISCONNECT (close frame or TCP drop)
```

### 1.2 Server-Sent Events (SSE) — FIWARE / analytics path

**Endpoint:** `GET /events/stream`  
**Protocol:** `text/event-stream`, SSE per the WHATWG spec  
**Implementation:** future extension; not yet in `iot-gateway/`

**Behavior:**
- Idempotent with WebSocket for the event payload format.
- Each event is sent as a named SSE field:
```
event: canonical
data: {"event_id":"...","event_type":"command_ack",...}

event: heartbeat
data: {"type":"heartbeat","ts":"2026-10-20T10:00:00Z"}
```
- `retry:` field set to `5000` (ms).
- Clients reconnect automatically on disconnect; should send `Last-Event-ID` header to enable replay from last received `event_id`.

### 1.3 MQTT Re-publish (FIWARE / Robot alert path)

**Topics published by the gateway on the southbound broker:**

| Topic | Payload | When |
|---|---|---|
| `smart-factory/gateway/canon/<device_id>/<event_type>` | Canonical envelope JSON | Every committed event |
| `smart-factory/gateway/alert/<severity>` | AlertEvent JSON | AlertService dispatches |
| `smart-factory/gateway/heartbeat` | `{"type":"gateway_hb","ts":"..."}` | Every 30 s |

**Deduplication:** MQTT broker (or subscriber) is responsible for QoS-based deduplication. The gateway does **not** add a broker-level message ID to the payload. Subscribers must use `event_id` as the idempotency key.

---

## 2. Pub/Sub Topics and Channels

### 2.1 Unity Digital Twin

**Transport:** WebSocket  
**Channel:** all events — no topic filter  
**Startup:** `GET /snapshot?since_sequence=0` → apply `per_device_latest` to scene objects → subscribe WebSocket for events with `sequence > high_watermark`

**Filters client-side:**
- `event_type in {telemetry, command_ack, status_online, status_offline}`
- `device_id` maps to named 3D scene objects (see `sync-contracts.md`)

### 2.2 React Dashboard

**Transport:** WebSocket (live) + REST polling fallback  
**Channel:** all events — same as Unity  
**Startup:** same snapshot protocol as Unity  

**Additional REST endpoints consumed:**
- `GET /events?device_id=X&event_type=Y&limit=100` — historical query
- `GET /snapshot` — scene init
- `GET /health` — gateway health, queue drop count
- `GET /metrics` — latency histograms

### 2.3 FIWARE Orion-LD

**Transport:** MQTT re-publish → Orion-LD NGSI-LD adapter  
**Channel:** `smart-factory/gateway/canon/+/+` (all devices, all event types)  

The gateway re-publishes canonical events as MQTT messages that the Orion-LD ContextSink subscribes to and maps to NGSI-LD entity upserts. The ContextSink is internal to `iot-gateway/` and is NOT exposed on public networks.

See `contracts/fiware/ngsi-ld-entity-schema.md` for entity shapes.

### 2.4 Robot (Yanshee)

**Transport:** MQTT re-publish OR direct AlertService handler injection  
**Channel:** `smart-factory/gateway/alert/critical` and `smart-factory/gateway/alert/warning`

The gateway's `AlertService` (`iot-gateway/src/iot_gateway/alerts.py`) dispatches `AlertEvent` objects. Handlers are pluggable; the Yanshee adapter registers as an `AlertHandler` and receives only alerts at or above the configured minimum severity threshold.

---

## 3. Live-State Event Message Format

Every event broadcast via WebSocket, SSE, and MQTT re-publish uses the canonical envelope defined in `iot-gateway/src/iot_gateway/models.py`.

### 3.1 Canonical Envelope (canonical JSON)

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "device_id": "conveyor-a",
  "event_type": "command_ack",
  "payload": {
    "id": 102,
    "status": "acknowledged",
    "fields": ["CONVEYOR_START", "60"]
  },
  "mqtt_topic": "smart-factory/bridge/result",
  "mqtt_timestamp_ms": 1730000000000,
  "event_timestamp_ms": 1730000000000,
  "received_at": "2026-10-20T10:00:00.000Z",
  "received_at_ms": 1730000000100,
  "latency_ms": 100,
  "stale": false,
  "out_of_order": false,
  "is_timestamp_synchronized": false,
  "ingested_at": "2026-10-20T10:00:00.010Z",
  "sequence": 42
}
```

**Field semantics:**

| Field | Type | Required | Description |
|---|---|---|---|
| `event_id` | UUID string | Yes | Globally unique idempotency key. Consumers MUST deduplicate on this field. |
| `device_id` | string | Yes | Originating device/bridge ID. Maps to scene object in Unity and UI widget in React. |
| `event_type` | `command_ack \| status_online \| status_offline \| telemetry \| heartbeat` | Yes | Discriminator for consumers. |
| `payload` | object | Yes | Event-type-specific data. Never mutate after emission. |
| `mqtt_topic` | string | Yes | Original MQTT topic (provenance). |
| `mqtt_timestamp_ms` | integer | Yes | Source timestamp in ms UTC epoch (or ESP32 uptime if `is_timestamp_synchronized=false`). |
| `event_timestamp_ms` | integer | Yes | Canonical event timestamp. Same as `mqtt_timestamp_ms` unless re-normalized. |
| `received_at` | ISO 8601 string | Yes | Gateway receive time in UTC. |
| `received_at_ms` | integer | Yes | Gateway receive time in ms UTC epoch. Use for latency computation. |
| `latency_ms` | integer | Yes | `received_at_ms - mqtt_timestamp_ms`. Set to `-1` when `is_timestamp_synchronized=false`. |
| `stale` | boolean | Yes | True when source timestamp is older than the configured staleness window. Twin shows STALE/UNKNOWN. |
| `out_of_order` | boolean | Yes | True when `event_timestamp_ms` is older than the last-seen timestamp for this `device_id`. |
| `is_timestamp_synchronized` | boolean | Yes | True = UTC source clock; False = ESP32 monotonic uptime. |
| `ingested_at` | ISO 8601 string | Yes | When the gateway first ingested this event. |
| `sequence` | integer | Yes | Monotonically increasing global sequence. Used for gap detection and replay ordering. |

### 3.2 Event-Type-Specific Payload Shapes

#### `command_ack`
```json
{
  "payload": {
    "id": 102,
    "status": "acknowledged | queued | failed | invalid",
    "fields": ["CONVEYOR_START", "60"],
    "attempts": 1
  }
}
```
`status` values: `queued` (command accepted), `acknowledged` (frame received by bridge), `failed` (bridge rejected), `invalid` (schema validation failed at gateway).

> ⚠️ ACK does NOT mean physical task completion. `acknowledged` means the bridge received the AMLP frame.

#### `status_online` / `status_offline`
```json
{
  "payload": {
    "status": "online | offline",
    "reason": "keepalive_timeout | manual | startup"
  }
}
```

#### `telemetry`
```json
{
  "payload": {
    "state": "STATE_MOVING",
    "speed": 120,
    "sensors": {
      "temperature_centi_c": 2850,
      "humidity_centi_percent": 6500
    },
    "uptime": 3600000
  }
}
```
`sensors` is optional and module-dependent. Units: temperature in centi-°C (divide by 100 for °C), humidity in centi-% (divide by 100 for %).

#### `heartbeat`
```json
{
  "payload": {
    "version": "v1.2.0",
    "rssi": -65,
    "heap_free": 40960
  }
}
```

### 3.3 Alert Payload (dispatched via AlertService)

Alerts are separate events emitted through the `AlertService` handler chain. They are NOT part of the canonical event envelope but share the same fanout path.

```json
{
  "alert_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "severity": "critical | warning | info",
  "source": "conveyor | robot | temperature | humidity | sensor | system",
  "timestamp": "2026-10-20T10:35:00.000Z",
  "message": "Conveyor A speed deviation >15% from setpoint",
  "recommended_action": "Inspect conveyor belt and motor assembly",
  "status": "pending | acknowledged | resolved",
  "device_id": "conveyor-a",
  "metadata": {
    "deviation_percent": 18.3,
    "setpoint": 120,
    "actual": 98
  }
}
```

---

## 4. Subscription Lifecycle

### 4.1 WebSocket — Connect and Reconnect Protocol

**Step 1 — Full snapshot (required before subscribing):**
```
GET /snapshot?since_sequence=0&limit=1000
```
Response:
```json
{
  "high_watermark": 142,
  "snapshot_count": 50,
  "events": [...],
  "per_device_latest": { "conveyor-a": {...}, ... },
  "overflow": false,
  "overflow_limit": 1000
}
```
If `overflow: true` → client must request full snapshot again with `since_sequence=0` to avoid state gaps.

**Step 2 — Open WebSocket:**
```
ws://gateway:8765/
```

**Step 3 — Apply incremental events:**
Client tracks `last_sequence = high_watermark`. Every WebSocket event with `event.sequence > last_sequence` is applied in ascending sequence order. Events may arrive out of delivery order; sort by `sequence` before applying.

**Step 4 — Reconnect on gap:**
```
on WebSocket close/disconnect:
  1. Close current WebSocket
  2. GET /snapshot?since_sequence=<last_sequence>&limit=1000
  3. If overflow=true OR gap detected → retry with since_sequence=0
  4. Re-open WebSocket
  5. Continue from Step 3
```

### 4.2 SSE — Connect with Last-Event-ID

```
GET /events/stream
Headers:
  Accept: text/event-stream
  Last-Event-ID: <last event_id received>   (optional, for replay)
```

Server responds with SSE frames. On reconnect, client sends `Last-Event-ID` so the server can resume from the last acknowledged event.

### 4.3 Heartbeat

The gateway publishes a MQTT heartbeat every 30 s to `smart-factory/gateway/heartbeat`. Subscribers should consider the gateway offline if no message is received for 90 s (3 × heartbeat interval).

Consumers that receive no events for > 60 s should:
1. Open a new connection (do not wait indefinitely on a silent socket).
2. Request a fresh `/snapshot` to re-sync state before processing new live events.

---

## 5. Ordering and Deduplication Guarantees

### 5.1 Ordering

| Transport | Ordering guarantee | Mechanism |
|---|---|---|
| WebSocket | Per-client FIFO | Single-threaded broadcast loop in `WebSocketServer.broadcast()` |
| SSE | Per-connection FIFO | Sequential frame writes |
| MQTT re-publish | At-most-once delivery (QoS 0) by default | Subscribers should use `event_id` for dedup |

**Cross-device ordering is NOT guaranteed.** Two events from different `device_id`s may be delivered in either order. Consumers that need cross-device causality must use `sequence` (global ordering within the SQLite event store) or `event_timestamp_ms` with caution around `is_timestamp_synchronized=false`.

> ⚠️ **Clock domain warning:** When `is_timestamp_synchronized=false`, `mqtt_timestamp_ms` is ESP32 uptime — not UTC. Do not use it for cross-device ordering. Use `sequence` (monotonically increasing integer) for ordering within the gateway.

### 5.2 Deduplication

- **WebSocket:** The gateway does NOT deduplicate. Per-client queue overflow causes disconnection, not message drop. The reconnect-and-resync protocol recovers state.
- **MQTT:** Subscribers must use `event_id` as the idempotency key. The gateway does not add a separate deduplication layer for MQTT.
- **Reconnection:** On reconnect, the snapshot protocol (`since_sequence`) returns all events after the cursor, including potential duplicates from in-flight messages. Consumers MUST deduplicate on `event_id`.

### 5.3 Staleness and Gap Detection

| Condition | Gateway behavior | Consumer behavior |
|---|---|---|
| ESP32 uptime clock skew | `is_timestamp_synchronized=false` set by normalizer | Do not compute latency or cross-device ordering |
| Gap in `sequence` | N/A (gateway does not detect) | Client detects `sequence[N+1] > sequence[N] + 1` → request full snapshot |
| `stale=true` on event | Set by normalizer when `mqtt_timestamp_ms` is old | Twin shows UNKNOWN/STALE overlay; UI shows stale indicator |
| No events for 60 s | No automatic action | Consumer initiates reconnect + full snapshot |

---

## 6. Back-pressure and Overflow

- **WebSocket client queue:** max 64 messages per client (`WebSocketServer.MAX_QUEUE_PER_CLIENT`). Overflow causes immediate disconnection. Clients must process events faster than the gateway emits them or reconnect.
- **Write queue (SQLite persistence):** max 500 events. Overflow drops events and increments `_dropped_count`. Consumers should poll `GET /health` and expose queue-dropped count in UI.
- **MQTT re-publish:** fire-and-forget QoS 0. No back-pressure. Failed publishes are logged but do not block the write path.

---

## 7. Compatibility Notes

- The canonical envelope schema is versioned at the field level. New optional fields may be added without a breaking change. New required fields require a schema version bump and consumer migration plan.
- `event_type` is an open enum (`EventType` in `models.py`). Consumers MUST ignore unknown `event_type` values gracefully (forward-compatibility).
- `payload` structure is event-type-specific. Consumers MUST use `event_type` as the discriminator before parsing `payload`.
- `sequence` is a 32-bit signed integer. It wraps after 2,147,483,647. Consumers that need longer-running sequences should use `event_id` as the primary identity key.
- Orion-LD ContextSink (`iot-gateway/src/iot_gateway/adapters/orion_ld.py`) maps events to NGSI-LD entities asynchronously. The NGSI-LD entity `dateModified` reflects the gateway `received_at` time, not the source `mqtt_timestamp_ms`.

---

## 8. L0 Validation Checklist

- [ ] All event types from `CanonicalEvent` are documented in §3.2
- [ ] WebSocket, SSE, MQTT re-publish transport shapes are defined
- [ ] Per-consumer topic/channel assignments are documented in §2
- [ ] Snapshot + reconnect protocol is defined (critical for Unity/React)
- [ ] Ordering guarantees are documented with clock-domain caveats
- [ ] Deduplication is documented with `event_id` as idempotency key
- [ ] Staleness and gap-detection behavior is documented
- [ ] No contradictions with merged ADR-0013, ADR-0014, or Issue #197 entity schema
