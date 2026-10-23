# iot-gateway — Smart Factory MQTT Ingestion Gateway

Implements `iot-gateway/` per issue #7.

Subscribes to ESP32 bridge MQTT topics, normalizes events into a canonical
envelope, stores them durably in SQLite, and exposes them via WebSocket and
HTTP for the Digital Twin and dashboard (supports verified uKit Explore SDK bridge specifications per issue #56).

## Topics subscribed

| Topic pattern | Purpose |
|---|---|
| `smart-factory/+/command/ack` | Command completion events |
| `smart-factory/+/status` | Device online/offline LWT events |

## Architecture

```
ESP32 Bridge
    │
    ├── MQTT: command/ack ──▶ MqttClient ──▶ EventNormalizer
    │                                       │
    └── MQTT: status (LWT) ─────────────────▶ EventStore (SQLite)
                                                   │
                                          WebSocketServer / HttpServer
                                                   │
                                              Twin / Dashboard
```

## Canonical Event Envelope

```json
{
  "event_id": "uuid-v4",
  "device_id": "sf-bridge-001",
  "event_type": "command_ack",
  "payload": { ... },
  "mqtt_topic": "smart-factory/sf-bridge-001/command/ack",
  "mqtt_timestamp_ms": 1697184000000,
  "ingested_at": "2026-10-13T12:00:00.123Z",
  "sequence": 42
}
```

## Quick Start

From repository root, install `python -m pip install -e "./iot-gateway[dev]"` and run `python -m pytest iot-gateway/tests/`. The service is a root-level module, independent from firmware.


```bash
pip install -e ".[test]"
iot-gateway --broker localhost --port 1883
```

## API

- **WebSocket**: `ws://localhost:8000/` (standalone `websockets` server; port configurable via `WS_PORT`)
- **HTTP REST**: `GET /events` — last N events, filterable by device_id and event_type
- **HTTP REST**: `GET /events/{event_id}` — single event
- **HTTP**: `GET /health` — gateway health check (HTTP defaults to port 8001)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER` | `localhost` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USERNAME` | `None` | MQTT username (optional) |
| `MQTT_PASSWORD` | `None` | MQTT password (optional) |
| `DATABASE_URL` | `sqlite+aiosqlite:///gateway.db` | SQLAlchemy database URL |
| `WS_HOST` | `0.0.0.0` | WebSocket bind host |
| `WS_PORT` | `8000` | WebSocket bind port |
| `WS_HTTP_PORT` | `8001` | HTTP REST bind port (defaults to `WS_PORT + 1`) |
| `MAX_EVENTS` | `10000` | Max events to keep in SQLite |

## FIWARE context layer (Issue #204)

| Module | Role |
|---|---|
| `src/iot_gateway/adapters/orion_robot.py` | Maps a robot capability source onto an NGSI-LD `Robot` entity. An unverified source yields `UNKNOWN` status/battery, an empty `supportedActions` list and `verificationStatus: UNVERIFIED` — it never fabricates status, battery or supported actions. |
| `src/iot_gateway/adapters/orion_incident.py` | Projects a Gateway incident onto an NGSI-LD `Alert` carrying `traceId`, `sourceEventId`, `sourceSystem` and operator state. Read model only; the incident store stays authoritative. |
| `src/iot_gateway/context_query.py` | `ContextQueryFacade` — **read-only** NGSI-LD query facade (HTTP `GET` only). No upsert, delete, publish or command path exists on this class. |

The Gateway incident outbox (`alert_outbox.py`) remains the **sole** Yanshee
notification dispatch path. FIWARE context never dispatches a skill.

Contract: `contracts/fiware/ngsi-ld-yanshee-context.md` (v1.0.0).
Decision record: `docs/adr/adr-0016-fiware-yanshee-context-mapping.md`.
