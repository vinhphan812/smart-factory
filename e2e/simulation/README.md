# E2E Simulation Harness

**Issues:** #180 · #186 · #182

Simulates the full Smart Factory stack with mock MQTT devices — no physical hardware required.

---

## Architecture

```
mock-mqtt-publisher ──► mqtt-broker (:1883)
        │                     │
        │              ┌──────┴──────────────────────┐
        │              │                               │
        │         iot-gateway (:8000)          factory-control (:8001)
        │              │                               │
        │              └──────┬──────────────────────┘
        │                     │
        │              ┌──────┴──────┐
        │              │             │
        │         dashboard      orion-ld (:1026)
        │         (:5173)             │
        │                             mongodb (:27017)
        │
        └──► iot-gateway WebSocket (:8000) ──► broadcasts events to dashboard and test clients
```

---

## Quick Start

```bash
# Start all services (from repo root)
docker compose -f e2e/simulation/docker-compose.e2e.yml up -d

# Watch logs
docker compose -f e2e/simulation/docker-compose.e2e.yml logs -f

# Verify health
docker compose -f e2e/simulation/docker-compose.e2e.yml ps

# Stop
docker compose -f e2e/simulation/docker-compose.e2e.yml down
```

---

## Services

| Service | Description |
|---|---|
| `mqtt` | Eclipse Mosquitto broker — all MQTT traffic |
| `mock-mqtt-publisher` | Python script that publishes mock telemetry, status, command/ack, heartbeat events to the broker |
| `iot-gateway` | Gateway — subscribes MQTT, stores in SQLite, broadcasts WebSocket |
| `factory-control` | Factory controller adapters |
| `orion-ld` | FIWARE Orion-LD context broker |
| `mongodb` | Orion-LD persistence |
| `dashboard` | React operator dashboard (dev mode) |
| `smoke-tests` | Runs L0/L1 smoke tests then exits (via `smoke_tests.py`) |

---

## Mock Devices

Three virtual devices publish on these topics every 2 seconds:

| Device ID | Topics |
|---|---|
| `mock-conveyor-a` | `smart-factory/mock-conveyor-a/telemetry`, `smart-factory/mock-conveyor-a/status` |
| `mock-robot-arm-b` | `smart-factory/mock-robot-arm-b/telemetry`, `smart-factory/mock-robot-arm-b/status` |
| `mock-inspection-c` | `smart-factory/mock-inspection-c/telemetry`, `smart-factory/mock-inspection-c/status`, `smart-factory/mock-inspection-c/command/ack` |

---

## Smoke Tests

Run after all services are healthy:

```bash
# Run inside the smoke-tests container
docker compose -f e2e/simulation/docker-compose.e2e.yml run --rm smoke-tests

# Or locally (requires Python 3.11+ and dependencies)
pip install -e iot-gateway[dev]
python -m pytest e2e/simulation/smoke_tests.py -v
```

### L0 — Compose starts without errors

```bash
docker compose -f e2e/simulation/docker-compose.e2e.yml up -d
docker compose -f e2e/simulation/docker-compose.e2e.yml ps  # all running
```

### L1 — Service health endpoints respond

| Test | Command |
|---|---|
| Gateway health | `curl -sf http://localhost:8001/health` |
| Orion-LD health | `curl -sf http://localhost:1026/health` |
| Factory-control health | `curl -sf http://localhost:8001/health` |
| MQTT broker | `docker compose -f e2e/simulation/docker-compose.e2e.yml exec mqtt sh -c "timeout 5 mosquitto_sub -t 'test' -C 1"` |

### L1 — Gateway ingests mock events

```bash
# After 5 seconds of running, gateway should have events
curl -s http://localhost:8001/events?limit=5 | jq '.count'
# Expected: > 0
```

### L1 — WebSocket connection

```bash
# Connect, receive one event, disconnect
python -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://localhost:8000/ws') as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        event = json.loads(msg)
        assert 'event_id' in event, f'Unexpected message: {msg}'
        print('OK: received event', event.get('event_id'))
asyncio.run(test())
"
```

### L1 — Migration regression test

```bash
# Test backup/restore on the gateway's DB volume
docker compose -f e2e/simulation/docker-compose.e2e.yml exec iot-gateway \
  python -m iot_gateway.migrations.backup_restore --backup
```

---

## Configuration

Environment variables can be set in `e2e/simulation/.env` (copy from repo root `.env.example`).

Key variables:

| Variable | Default | Description |
|---|---|---|
| `MOCK_PUBLISH_INTERVAL_S` | `2` | Interval between mock device events |
| `SMOKE_TEST_TIMEOUT_S` | `60` | Timeout for each smoke test |
| `GW_HTTP_PORT` | `8001` | Gateway port (host) |
| `ORION_LD_PORT` | `1026` | Orion-LD port (host) |
| `FC_PORT` | `8002` | Factory-control port (host; avoids the gateway HTTP port) |
| `DASH_PORT` | `5173` | Dashboard port (host) |

---

## Cleanup

```bash
# Stop and remove volumes (resets DB)
docker compose -f e2e/simulation/docker-compose.e2e.yml down -v

# Remove images built for this compose
docker compose -f e2e/simulation/docker-compose.e2e.yml down --rmi local
```
