# Downstream Synchronization Contracts

**Owner:** Issue #194 (wave: 2-gateway-core, P0)  
**Version:** 1.0.0  
**Status:** Draft  
**Context:** ADR-0013 (Yanshee), ADR-0014 (FIWARE/Orion-LD), Issue #197 (entity schema), `live-state-fanout.md`

---

## Overview

This document defines the contract between the IoT Gateway and each downstream consumer: Unity Digital Twin, React Dashboard, FIWARE Orion-LD, and the Yanshee Robot. Each section specifies what data the consumer receives, how to map it to its internal representation, and any protocol-specific requirements.

All downstream consumers are **read-only** with respect to the factory. No consumer may issue commands directly to the ESP32 bridge or any physical actuator. Command authority rests solely with the Gateway's command API (`POST /commands`) after safety-gate evaluation.

---

## 1. Unity Digital Twin — `digital-twin/`

**PR #144 merged.** Status: scaffold. Full telemetry-to-3D mapping is pending #176 and #190.

### 1.1 Data Received

The Twin connects to the gateway via WebSocket and HTTP snapshot, receiving the full canonical event envelope described in `live-state-fanout.md` §3.

**Startup sequence:**
```
1. GET /snapshot?since_sequence=0&limit=1000
   → Apply per_device_latest to initialize 3D scene
   → Track high_watermark
2. ws://gateway:8765/
   → Receive events with sequence > high_watermark
   → Sort by sequence ascending; apply in order
3. On disconnect: reconnect per live-state-fanout.md §4.1
```

**Event types consumed by Twin:**

| event_type | Consumed? | Action |
|---|---|---|
| `command_ack` | Yes | Update command feedback overlay; animate state transition |
| `status_online` | Yes | Set module "online" indicator; resume telemetry-driven animation |
| `status_offline` | Yes | Set module "offline" indicator; show disconnected overlay |
| `telemetry` | Yes | Drive real-time animation parameters (speed, position, sensor values) |
| `heartbeat` | Yes | Update last-seen timestamp per device |

**Alert events:** `AlertEvent` objects from the `AlertService` fanout. The Twin renders active alerts as 3D overlay badges or scene annotations.

### 1.2 Module-to-3D Object Mapping

The Twin maintains a **module registry** that maps `device_id` strings (from canonical events) to named 3D scene objects. The registry is authored in `digital-twin/Assets/Config/ModuleRegistry.json` or equivalent.

**Nine-module catalogue mapping:**

| device_id pattern | 3D scene object | moduleType (NGSI-LD) |
|---|---|---|
| `conveyor-a`, `conveyor-b` | `ConveyorA`, `ConveyorB` | `conveyor` |
| `sorting-1` | `SortingMachine` | `sorting` |
| `crane-1` | `TowerCrane` | `crane` |
| `forklift-1` | `Forklift` | `forklift` |
| `dump-truck-1` | `DumpTruck` | `dump_truck` |
| `packaging-1` | `PackagingMachine` | `packaging` |
| `bracket-1` | `Bracket` | `bracket` |
| `parking-lot-1` | `ParkingLot` | `parking` |
| `combine-1` | `CombineModule` | `combine` |

> ⚠️ The Bracket module has no active actuators and no telemetry source confirmed. Do NOT synthesize fake telemetry for Bracket.

### 1.3 Telemetry-to-Animation Mapping

| telemetry field | Unity property | Animation behavior |
|---|---|---|
| `payload.state` | `ModuleState` enum | IDLE / MOVING / STOPPED / ERROR |
| `payload.speed` | `Speed` (float, RPM or mm/s) | Rotation speed, conveyor belt UV scroll |
| `payload.sensors.temperature_centi_c` | `TemperatureC` (float °C) | Color overlay (green→yellow→red) |
| `payload.sensors.humidity_centi_percent` | `HumidityPercent` (float %) | Condensation shader |
| `payload.uptime` | `UptimeSeconds` | Display in debug panel |

**State machine mapping (canonical `event_type` → Unity state):**

| event_type + payload.status | Unity ModuleState | Visual |
|---|---|---|
| `command_ack` + `acknowledged` | `EXECUTING` | Brief highlight animation |
| `command_ack` + `failed` | `ERROR` | Red flash + error badge |
| `status_offline` | `OFFLINE` | Greyed-out mesh + "DISCONNECTED" overlay |
| `telemetry` + `state: STATE_MOVING` | `MOVING` | Full animation |
| `telemetry` + `state: STATE_IDLE` | `IDLE` | Idle pose |
| `telemetry` + `state: STATE_ERROR` | `ERROR` | Error badge + red glow |
| `heartbeat` missing > 90 s | `STALE` | Pulsing amber outline |

### 1.4 Unknown / Stale / Offline States

The Twin MUST render the following states when real data is unavailable, rather than inferring or inventing a state:

| Condition | Unity State | Rendering |
|---|---|---|
| `stale=true` on any event | `STALE` | Amber pulsing border on scene object |
| `event_type: status_offline` | `OFFLINE` | Grey desaturated mesh; "OFFLINE" text label |
| No event received for device for > 60 s | `UNKNOWN` | Object shown in default scene; no telemetry overlays |
| Gap detected in sequence numbers | `RESYNC` | Fade-to-black transition; re-fetch `/snapshot` |

### 1.5 Non-Functional Requirements

- **Latency:** Twin renders at display refresh rate. Telemetry latency is measured as `received_at - event_timestamp_ms`. Display this in a debug overlay.
- **Reconnect:** Twin must implement the reconnect protocol in `live-state-fanout.md` §4.1. Do not cache or interpolate state between events.
- **No actuation:** Twin never sends commands. Any attempt to use Twin as a command interface is a protocol violation.

---

## 2. React Dashboard — `apps/dashboard/`

**PR #211 merged.** Status: bootstrap. Real-time update integration is pending #148 and #150.

### 2.1 Data Received

Dashboard connects to the gateway via WebSocket (live updates) and REST polling (snapshot and query). The React app uses the same canonical event envelope as the Twin.

**Startup sequence:**
```
1. GET /health            → display gateway status, queue drop count
2. GET /snapshot?since_sequence=0&limit=1000
   → Populate global state store with per_device_latest
   → Track high_watermark
3. ws://gateway:8765/
   → Receive events with sequence > high_watermark
   → Dispatch to Zustand / Redux / React Query store
4. GET /events?device_id=X&event_type=Y&limit=100
   → Historical event log panel
```

**Event types consumed by Dashboard:**

| event_type | Dashboard view | Update behavior |
|---|---|---|
| `command_ack` | Command history table; real-time command status | Append to command log; update status badge |
| `status_online` / `status_offline` | Device status panel; topology view | Update device card; green/red indicator |
| `telemetry` | Module detail view; gauges; charts | Update live gauge values |
| `heartbeat` | Device health panel | Update "last seen" timestamp |
| `AlertEvent` (from fanout) | Alert banner; alert history table | Show banner for CRITICAL; log all |

### 2.2 Module-to-UI Component Mapping

| device_id pattern | UI component | Data displayed |
|---|---|---|
| `conveyor-*` | ConveyorCard | State, speed, sensor readings |
| `sorting-*` | SortingCard | Current sort, input/output counts |
| `crane-*` | CraneCard | Position, load, zone occupancy |
| `forklift-*` | ForkliftCard | Position, battery, task |
| `dump-truck-*` | DumpTruckCard | Position, load status |
| `packaging-*` | PackagingCard | Cycle count, material level |
| `parking-lot-*` | ParkingLotCard | Slot occupancy grid |
| `combine-*` | CombineCard | Pipeline status summary |

### 2.3 REST Endpoints Consumed

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check; display queue drop count |
| `/events` | GET | Query historical events with filters |
| `/events/{event_id}` | GET | Single event detail |
| `/snapshot` | GET | Scene initialization and resync |
| `/metrics` | GET | Latency histograms; stale event rate |
| `/safety-gate/status` | GET | Safety gate status (read-only) |
| `/safety-gate/audit-log` | GET | Safety audit log (metadata only) |

### 2.4 Staleness and Offline Handling

- **No event for device > 60 s:** Dashboard shows "No data — last seen X ago" with amber warning.
- **`stale=true`:** Show stale indicator badge on the relevant device card.
- **`status_offline`:** Show red "OFFLINE" badge. Do not show last-known values as current.
- **Queue drops detected (`GET /health` → `queue_dropped_count > 0`):** Show admin warning banner.

### 2.5 Non-Functional Requirements

- **Read-only:** Dashboard never sends commands directly. Commands flow through the gateway command API.
- **Responsive:** Live gauges update via WebSocket without page refresh.
- **Historical query:** Event log panel must support pagination via `limit` parameter.

---

## 3. FIWARE Orion-LD — `infrastructure/fiware/`

**ADR-0014 adopted.** Orion-LD integration is pending #196, #197, #198, #199.

### 3.1 Data Received

The gateway does not push directly to Orion-LD via HTTP. Instead, the gateway's MQTT re-publish (`smart-factory/gateway/canon/+/+`) is consumed by the **Orion-LD ContextSink** — an internal component of `iot-gateway/src/iot_gateway/adapters/orion_ld.py`.

```
Gateway canonical event committed
        │
        ├──► MQTT re-publish: smart-factory/gateway/canon/<device_id>/<event_type>
        │                              │
        │    ContextSink (internal)
        │                              │
        └──► Orion-LD NGSI-LD UPSERT (HTTP POST /ngsi-ld/v1/entityOperations/upsert)
                                        │
                                Orion-LD (MongoDB-backed)
                                        │
                                NGSI-LD Subscriptions
                                        │
                            Unity / React / external consumers
```

The ContextSink maps canonical events to NGSI-LD entities using `EventToEntityMapper` in `orion_ld.py`.

### 3.2 Event-to-NGSI-LD Entity Mapping

The `EventToEntityMapper` maps `event_type` to an NGSI-LD entity type:

| Canonical event_type | NGSI-LD entity type | Entity ID pattern |
|---|---|---|
| `command_ack` | `Command` | `urn:ngsi-ld:Command:<device_id>` |
| `status_online` / `status_offline` | `Status` | `urn:ngsi-ld:Status:<device_id>` |
| `telemetry` | `Telemetry` | `urn:ngsi-ld:Telemetry:<device_id>` |
| `heartbeat` | `Device` | `urn:ngsi-ld:Device:<device_id>` |

**However**, the entity schema from Issue #197 defines higher-fidelity entity types (`Module`, `Device`, `Alert`, etc.) that are the **canonical FIWARE entity shapes**. The ContextSink must be extended to map to the Issue #197 entity types, not the interim `EventToEntityMapper` types.

**Target entity mapping (per Issue #197):**

| Canonical event | Issue #197 entity type | Entity ID |
|---|---|---|
| `telemetry` from conveyor | `Module` | `urn:ngsi-ld:Module:conveyor-a` |
| `status_online/offline` from bridge | `Device` | `urn:ngsi-ld:Device:bridge-001` |
| `AlertEvent` from AlertService | `Alert` | `urn:ngsi-ld:Alert:<alert_id>` |
| Production job events | `Job` | `urn:ngsi-ld:Job:<job_id>` |

The `Module` entity `status` attribute maps to:
- `idle` — no recent telemetry, no command active
- `running` — recent `telemetry` with `state: STATE_MOVING`
- `error` — `telemetry` with `state: STATE_ERROR` OR `command_ack` with `status: failed`
- `emergency_stop` — safety gate E-stop active (from safety gate status endpoint)
- `maintenance` — device in maintenance mode

### 3.3 ContextSink Behavior

**Contract for the ContextSink (to be implemented in `iot-gateway/src/iot_gateway/fiware/context_sink.py`):**

1. Consumes MQTT re-publish messages from `smart-factory/gateway/canon/+/+`
2. Maps canonical event to NGSI-LD entity per Issue #197 schema
3. Performs idempotent NGSI-LD `POST /ngsi-ld/v1/entityOperations/upsert`
4. Uses `event_id` as the idempotency key (Orion-LD handles upsert semantics)
5. On upsert failure: enqueue to dead-letter queue; retry with exponential backoff (max 3 attempts)
6. After successful upsert: advance checkpoint (persisted durable cursor)
7. On gap detected: reconcile from SQLite event store snapshot

**Synchronisation lag contract:**
- Between SQLite commit and Orion-LD upsert: up to `batch_timeout_seconds` (default 5 s) + network latency.
- Consumers of Orion-LD subscriptions see a lag of up to 10 s behind live WebSocket events.
- This lag is acceptable for UI state display but NOT for safety-critical feedback loops.

### 3.4 Orion-LD NGSI-LD Subscription Notifications

External consumers (Unity, React, external FIWARE clients) subscribe to Orion-LD for notifications:

```bash
POST /ngsi-ld/v1/subscriptions/
Content-Type: application/ld+json
Link: <https://smart-factory.example.com/ngsi-context.jsonld>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"

{
  "type": "Subscription",
  "entities": [{ "type": "Module" }],
  "watchedAttributes": ["status", "state", "speed"],
  "notification": {
    "endpoint": {
      "uri": "http://consumer.example.com/notifications",
      "accept": "application/json"
    },
    "attributes": ["name", "moduleType", "status", "state", "speed", "location"]
  }
}
```

### 3.5 Non-Functional Requirements

- **Orion-LD is not the command authority.** A context attribute update never dispatches a command.
- **Orion-LD is not the event history authority.** SQLite event store is the source of truth for temporal queries.
- **Context staleness:** If Orion-LD entity `dateModified` is older than 60 s, consumers must show `UNKNOWN` state, not cached values.
- **Batch upsert:** `OrionLdClient.upsert_batch()` batches up to 100 entities per HTTP request for efficiency.

---

## 4. Robot (Yanshee) — `edge-ai-robot/`

**ADR-0013 adopted.** Yanshee integration is pending #160, #168, and hardware SDK verification.

### 4.1 Alert Dispatch Contract

The gateway's `AlertService` (`iot-gateway/src/iot_gateway/alerts.py`) is the sole mechanism for dispatching notifications to the robot. The robot is **never** a subscriber of raw canonical events. Only typed `AlertEvent` objects are dispatched.

```
AlertService.publish(AlertEvent)
        │
        ├──► AlertHandler (YansheeAdapter)
        │              │
        │    YansheeAdapter.handle(alert)
        │              │
        │    ┌─────────▼──────────────────┐
        │    │ Approved skill invocation │
        │    │ (via incident policy only) │
        │    └────────────────────────────┘
        │
        └──► WebhookNotification (if configured)
                     │
              MQTT re-publish: smart-factory/gateway/alert/<severity>
```

### 4.2 Alert Severity Routing

| Severity | YansheeAdapter behavior |
|---|---|
| `critical` | Immediate notification; approved bounded skill invoked (e.g., `MOVE_TO_SAFE_POSITION`, `ACTIVATE_WARNING_LIGHT`) |
| `warning` | Notification queued; operator acknowledgment required before skill invocation |
| `info` | Logged only; no robot action |

**Yanshee bounded skills** are pre-approved, parameterised actions that the robot can execute without operator approval (within defined safety limits). Skills are registered in `edge-ai-robot/skills/registry.json`.

### 4.3 AlertEvent Contract

The `AlertEvent` shape is defined in `live-state-fanout.md` §3.3. The Yanshee adapter extracts the following fields:

| Field | Used by YansheeAdapter | Notes |
|---|---|---|
| `alert_id` | Yes | Correlation ID for acknowledgment tracking |
| `severity` | Yes | Determines skill invocation policy |
| `source` | Yes | Maps to robot attention zone |
| `timestamp` | Yes | Age-of-alert check (> 5 min → stale, skip skill) |
| `message` | Yes | Passed to robot TTS/display |
| `device_id` | Yes | Maps to robot's spatial awareness system |
| `metadata` | Yes | Passed to skill as parameters |

### 4.4 YansheeAdapter Interface

```python
class YansheeAdapter(AlertHandler):
    """AlertHandler that dispatches approved skills to the Yanshee robot."""

    async def handle(self, alert: AlertEvent) -> bool:
        """Return True if skill was dispatched successfully."""
        ...
        # 1. Check skill availability for this alert source
        # 2. Verify alert age (reject if > 5 minutes old)
        # 3. Invoke approved skill via robot SDK
        # 4. Log skill invocation to audit trail
        # 5. Return True on success, False on failure
```

**Skill invocation is never autonomous.** All skill invocations go through the incident policy defined in `#160/#168`. The policy specifies which skills are approved per alert source and severity, maximum invocation frequency, and escalation path.

### 4.5 Non-Functional Requirements

- **No command authority:** Yanshee never sends commands to the factory. Skills are read-only or safe environmental actions (lights, display, movement to safe zone).
- **Alert age:** Alerts older than 5 minutes are not acted upon; they are logged and marked stale.
- **Rate limiting:** YansheeAdapter enforces a maximum of 1 skill invocation per 30 s per `device_id` to prevent rapid re-triggering.
- **Audit trail:** Every skill invocation is logged with `alert_id`, `skill_name`, `timestamp`, and `result`.

---

## 5. Contract Versioning and Compatibility

| Consumer | Min gateway version | Breaking change trigger |
|---|---|---|
| Unity Twin | v0.1.0 | New required field in canonical envelope; new `event_type` value |
| React Dashboard | v0.1.0 | Same as Twin |
| Orion-LD ContextSink | v0.2.0 (pending) | Change in event-to-entity mapping |
| YansheeAdapter | v0.1.0 | New required field in `AlertEvent` |

Consumers MUST ignore unknown fields in both canonical events and `AlertEvent` objects (forward-compatibility).

Schema evolution process:
1. New optional fields: additive, no version bump required.
2. New required fields: bump `schema_version` in canonical envelope, phased rollout with consumer migration window.
3. Deprecated fields: announced 2 sprints before removal; consumers updated within that window.

---

## 6. L0 Validation Checklist

- [ ] Unity Twin: startup snapshot + WebSocket resync protocol defined
- [ ] Unity Twin: device_id → 3D object mapping table defined for all 9 modules
- [ ] Unity Twin: telemetry field → animation property mapping defined
- [ ] Unity Twin: UNKNOWN/STALE/OFFLINE state rendering defined
- [ ] React Dashboard: startup sequence and REST endpoint usage defined
- [ ] React Dashboard: device_id → UI component mapping defined
- [ ] FIWARE Orion-LD: ContextSink flow documented (MQTT → upsert → subscriptions)
- [ ] FIWARE Orion-LD: event-to-Issue-197-entity mapping defined
- [ ] FIWARE Orion-LD: staleness lag and UNKNOWN state handling defined
- [ ] Yanshee: AlertService as sole dispatch mechanism documented
- [ ] Yanshee: severity routing table defined
- [ ] Yanshee: AlertEvent field extraction defined; bounded skill policy referenced
- [ ] No contradictions with ADR-0013, ADR-0014, Issue #197 schema
