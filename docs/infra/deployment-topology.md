# Smart Factory — Deployment Topology

**Issues:** #182 · #186 · #180  
**Wave:** 4-e2e-hil · **Area:** infra / integration

---

## 1. Service Map

| Service | Language / Runtime | Port(s) | Role |
|---|---|---|---|
| **mqtt-broker** | eclipse-mosquitto:2 | 1883 (plain), 8883 (TLS) | Message bus — all southbound/northbound MQTT traffic |
| **iot-gateway** | Python 3.12 / FastAPI + websockets | 8000 (WS), 8001 (REST) | MQTT ingestion → SQLite → WebSocket/HTTP broadcast |
| **factory-control** | Python 3.12 / asyncio | 8001 (container) / 8002 (host) | Nine-module device adapters, production cycle scheduler |
| **dashboard** | TypeScript / Vite + React | 5173 (dev) / 80 (prod) | Operator UI — telemetry charts, event timeline, incident ACK |
| **edge-ai-robot** | Python 3.12 / httpx + websockets | 8002 (container) / 8003 (host) | MiniAlpha robot adapter, bounded skill definitions |
| **fiware-orion-ld** | Orion-LD 1.5.0 | 1026 (NGSI-LD) | FIWARE context broker — entity registry, subscriptions |
| **fiware-mongodb** | MongoDB 5.0 | 27017 | Orion-LD persistence |
| **fiware-json-ld-ctx** | nginx:alpine | 3000 | Custom NGSI-LD @context documents |

---

## 2. Service Dependency Graph

```
Internet / Operator Browser
        │
        ├──► dashboard (:5173 / :80) ──HTTP/WS──► iot-gateway (:8000 WS, :8001 REST)
        │                                               │
        │                                               ├──► mqtt-broker (:1883) ──Southbound──► ESP32 Bridges
        │                                               │
        │                                               ├──► fiware-orion-ld (:1026)
        │                                               │           │
        │                                               │           └──► fiware-mongodb (:27017)
        │                                               │
        │                                               └──► fiware-json-ld-ctx (:3000)
        │
        ├──► factory-control (:8002 host)
        │
        └──► edge-ai-robot (:8003 host)
                   │
                   └──► mqtt-broker (:1883)
```

### Dependency order at startup

```
fiware-mongodb
      ↓
fiware-orion-ld, fiware-json-ld-ctx
      ↓
mqtt-broker
      ↓
iot-gateway  (depends on mqtt-broker)
      ↓
factory-control, edge-ai-robot  (depend on mqtt-broker + iot-gateway)
      ↓
dashboard  (depends on iot-gateway)
```

---

## 3. Health Check Endpoints

| Service | Endpoint | Expected Response |
|---|---|---|
| mqtt-broker | `mosquitto_pub` probe (authenticated) | publish accepted on `smart-factory/healthcheck` |
| iot-gateway | `GET http://localhost:8001/health` | `200 {"status":"ok","event_count":N,"high_watermark":N}` |
| factory-control | `GET http://localhost:8002/health` | `200 {"status":"ok"}` |
| edge-ai-robot | `GET http://localhost:8003/health` | `200 {"status":"ok"}` |
| fiware-orion-ld | `GET http://localhost:1026/version` | `200 {"orionld version":"1.5.0",...}` |
| fiware-mongodb | `mongo --eval "db.adminCommand('ping')"` | `{ok:1}` |
| fiware-json-ld-ctx | `GET http://localhost:3000/health` | `200` (nginx) |
| dashboard | `GET http://localhost:5173/` | `200` (Vite dev server) |

> **Port notes.** The gateway serves its WebSocket transport on `8000` and its
> REST API on `8001`. Only `8001` exposes `/health`. The compose file maps
> `factory-control` to host port `8002` and `edge-ai-robot` to host port `8003`
> (the container-internal ports are `8001` and `8002` respectively).

> **Orion-LD has no `/health` route.** `GET /health` answers HTTP 400
> (`service not found`). Use `GET /version`, which answers HTTP 200. Any probe
> must use `curl -f` as well: without it `curl` exits 0 on an HTTP 400 and the
> container is reported healthy while the broker is unusable.

### Gateway health payload

```json
{
  "status": "ok",
  "event_count": 42,
  "high_watermark": 42,
  "queue_dropped_count": 0
}
```

---

## 4. Docker Compose — Full-Stack (without HIL)

File: `docker-compose.full.yml` (lives at repo root)

File: `docker-compose.full.yml` (lives at repo root). It is the **source of
truth** — this document does not duplicate its contents, so the two cannot
drift.

```bash
docker compose -f docker-compose.full.yml up -d
docker compose -f docker-compose.full.yml ps
docker compose -f docker-compose.full.yml logs -f iot-gateway
```

### Pinned images and why

| Image | Reason (each was a real failure before it was fixed) |
|---|---|
| `mongo:5.0` | Orion-LD 1.5.0 uses the deprecated MongoDB C++ **legacy driver**, which cannot speak to MongoDB >= 6.0. With `mongo:7.0` the broker logs `Unsupported OP_QUERY command: listDatabases` + `mongo::MsgAssertionException` and never becomes ready. **Important Production Caveat:** This pairing of MongoDB 5.0 with Orion-LD 1.5.0 is strictly an **L2 simulation pairing** chosen to satisfy legacy driver wire compatibility; it must **not** be presented as production-secure (MongoDB 5.0 reached End-of-Life / Extended Support maturity). **Open Upgrade Lifecycle Decision:** When MongoDB is upgraded past 5.0 (e.g. to MongoDB 7.0+), Orion-LD must be upgraded to a release that replaces the legacy C++ driver with a modern MongoDB driver supporting wire protocol version 6+. Compatibility will be verified via automated regression suites (`test_full_topology.py` and FIWARE subscription integration tests). |
| `mongo:5.0` (shell) | `mongo:5.0` ships the legacy `mongo` shell; `mongosh` only exists from `mongo:6.0` onwards, so the health probe must call `mongo`. |
| `quay.io/fiware/orion-ld:1.5.0` | The deployed FIWARE version. Reads `ORIONLD_MONGO_HOST` / `ORIONLD_MONGO_DB` — `ORION_LD_MONGO_HOST` is silently ignored and the broker then tries `localhost:27017` inside its own container. |
| `python:3.12-slim` | Gateway/factory-control/robot runtime. It has **neither `curl` nor `wget`**, so every health probe for a Python service uses the interpreter's own `urllib`. |
| `eclipse-mosquitto:2` | Broker. Runs with `allow_anonymous false`, so the health probe must authenticate. |

### Deployment profiles (#182 SPEC-2)

Selected with `COMPOSE_PROFILES` (comma separated). Services without a
`profiles:` key belong to every profile.

| Profile | Selected by | Contents | Actuation |
|---|---|---|---|
| `LOCAL_SIM` | default | broker, mongo, orion-ld, json-ld-context, iot-gateway, factory-control, edge-ai-robot, dashboard | permitted (software only) |
| `LAB_HIL` | `COMPOSE_PROFILES=LAB_HIL` | everything above **plus** `mock-hil-bridge` (a software device simulator) | permitted (software only) |
| `PRODUCTION_READONLY` | `COMPOSE_PROFILES=PRODUCTION_READONLY` | observation plane; `factory-control-readonly` is deployed **instead of** the actuating `factory-control` | **not available** — no actuation code path exists in this profile |

```bash
# Read-only deployment: observation only, no command path to a device
COMPOSE_PROFILES=PRODUCTION_READONLY docker compose -f docker-compose.full.yml up -d
```

**Physical command unlock requires separately audited approval** and is *not*
granted by any of these profiles. `PRODUCTION_READONLY` additionally runs
without `SAFETY_OPERATOR_TOKEN`, so the operator override path is closed as
well.

> Evidence produced with `LAB_HIL` is **L2 simulation**. The `mock-hil-bridge`
> service is a software simulator; running it does **not** produce HIL (L3/L4)
> or integrated (L5) evidence.

### Verified topology test

`e2e/simulation/test_full_topology.py` starts the advertised full topology and
asserts that **every** required service reaches the `healthy` state:

```bash
python -m pytest e2e/simulation/test_full_topology.py -v
```

---

## 5. Disaster Recovery Drills

### Drill 1 — MQTT Broker Outage

**Scenario:** mosquitto container crashes.

```bash
# 1. Kill broker
docker compose -f docker-compose.full.yml kill mqtt

# 2. Verify iot-gateway reports MQTT disconnection
docker compose -f docker-compose.full.yml logs iot-gateway | grep -i "disconnect\|error"

# 3. Restart broker
docker compose -f docker-compose.full.yml up -d mqtt

# 4. Verify iot-gateway reconnects automatically
sleep 5
docker compose -f docker-compose.full.yml logs iot-gateway | grep -i "connected\|reconnect"

# 5. Verify no events lost (check high watermark)
curl -s http://localhost:8001/health | jq .high_watermark
```

**Recovery SLA:** Gateway reconnects within 10 s; zero event loss.

### Drill 2 — Gateway DB Corruption (safe DR drill)

**Scenario:** `gateway.db` becomes unreadable.

> ⚠️ **Never copy a live SQLite database file.** The gateway database runs in
> WAL mode. A raw `cp` of a live `gateway.db` can capture a torn file that is
> missing committed transactions still resident in the `-wal` sidecar, and it
> can race a writer mid-page. Always use the canonical
> `python -m iot_gateway.migrations.backup_restore` tool, which uses SQLite's
> online backup API, verifies integrity, and restores atomically. The full
> contract is documented in
> [`iot-gateway/migrations/README.md`](../../iot-gateway/migrations/README.md).

```bash
# ── 1. BACKUP (safe against a running gateway) ────────────────────────────
# The online backup API takes a transactionally consistent snapshot even
# while the gateway is writing, and verifies it before publishing it.
docker compose -f docker-compose.full.yml exec iot-gateway \
  python -m iot_gateway.migrations.backup_restore --backup --db /app/data/gateway.db

# ── 2. VERIFY the backup before relying on it ─────────────────────────────
docker compose -f docker-compose.full.yml exec iot-gateway \
  python -m iot_gateway.migrations.backup_restore --verify \
    --backup-path /app/data/gateway.db.<timestamp>.bak

# ── 3. QUIESCENCE: stop every process that touches the database ──────────
docker compose -f docker-compose.full.yml stop iot-gateway

# ── 4. CORRUPT the live database (simulate the incident) ──────────────────
docker compose -f docker-compose.full.yml run --rm --no-deps \
  --entrypoint sh iot-gateway -c 'echo "corrupt" > /app/data/gateway.db'

# ── 5. RESTORE atomically from the verified backup ───────────────────────
# --offline is the operator attestation that the gateway is stopped.
# --confirm is required because the live database is replaced.
# The pre-restore snapshot is retained automatically for rollback.
docker compose -f docker-compose.full.yml run --rm --no-deps \
  --entrypoint sh iot-gateway -c \
  'python -m iot_gateway.migrations.backup_restore --restore \
     --db /app/data/gateway.db \
     --backup-path /app/data/gateway.db.<timestamp>.bak \
     --confirm --offline'

# ── 6. POST-RESTORE VALIDATION ───────────────────────────────────────────
# The restore tool already re-opens and integrity-checks the restored file.
# Re-verify it independently, then restart the gateway and confirm the
# event count and high watermark match the backup.
docker compose -f docker-compose.full.yml exec iot-gateway \
  python -m iot_gateway.migrations.backup_restore --verify \
    --backup-path /app/data/gateway.db.<timestamp>.bak

docker compose -f docker-compose.full.yml up -d iot-gateway
curl -s http://localhost:8001/health | jq '{event_count, high_watermark}'
```

**Interrupted restore recovery.** If a restore is killed mid-flight, a journal
(`.<db>.restore-journal.json`) is left behind. Resolve it deterministically:

```python
from iot_gateway.migrations.backup_restore import recover_interrupted_restore
from pathlib import Path

outcome = recover_interrupted_restore(Path("/app/data/gateway.db"))
# outcome.action in {"completed", "aborted", "rolled_back", "manual"}
```

**Recovery SLA:** < 60 s RTO; the backup/restore path is covered by
`iot-gateway/tests/test_backup_restore.py` and by the L2 compose drill
`e2e/simulation/backup_restore_drill.py`.

### Drill 3 — FIWARE Orion-LD Unavailable

**Scenario:** Orion-LD pod crashes; gateway should degrade gracefully (buffer events locally).

```bash
# 1. Stop Orion-LD
docker compose -f docker-compose.full.yml stop orion-ld

# 2. Verify gateway continues ingesting MQTT events
docker compose -f docker-compose.full.yml logs iot-gateway | grep -i "forward\|orion\|503"

# 3. Restart Orion-LD
docker compose -f docker-compose.full.yml up -d orion-ld

# 4. Health check (Orion-LD has no /health route — use /version)
curl -sf http://localhost:1026/version | jq '."orionld version"'
```

**Recovery SLA:** Gateway buffers locally; Orion-LD restores within 30 s.

### Drill 4 — Full-Stack Restart

```bash
# Stop everything gracefully
docker compose -f docker-compose.full.yml down

# Start in dependency order (docker compose resolves automatically)
docker compose -f docker-compose.full.yml up -d

# Wait for all health checks
docker compose -f docker-compose.full.yml ps
```

**Durable restart evidence.** The gateway persists events and the sequence
high-watermark in SQLite, so a restart preserves them. Verify:

```bash
# Before restart
curl -s http://localhost:8001/health | jq '{event_count, high_watermark}'

docker compose -f docker-compose.full.yml restart iot-gateway

# After restart — event_count and high_watermark must be >= the values above
curl -s http://localhost:8001/health | jq '{event_count, high_watermark}'
```

The automated equivalent is `e2e/simulation/scenarios/test_restart_durability.py`
(L2 simulation).

---

## 6. Backup & Restore

The canonical tool is `python -m iot_gateway.migrations.backup_restore`:

| Command | Purpose |
|---|---|
| `--backup [--db PATH]` | Online, WAL-safe, integrity-verified snapshot (safe against a running gateway) |
| `--verify --backup-path PATH` | Integrity-check a backup before relying on it |
| `--list [--db PATH]` | List available backups |
| `--restore --backup-path PATH --confirm --offline` | Atomic, verified restore; retains a pre-restore snapshot for rollback |

**Never copy a live SQLite database file.** See
[`iot-gateway/migrations/README.md`](../../iot-gateway/migrations/README.md) for
the full safety model, the interrupted-restore recovery procedure, and the
regression suite.

---

## 7. Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `MQTT_PORT` | `1883` | MQTT broker plain-text port |
| `MQTT_TLS_BIND` | `127.0.0.1` | TLS port binding host |
| `MQTT_ADMIN_USERNAME` | `admin` | Broker admin credential |
| `MQTT_ADMIN_PASSWORD` | `changeme` | Broker admin password |
| `MQTT_GW_USERNAME` | `gateway` | Gateway MQTT credential |
| `MQTT_GW_PASSWORD` | `changeme` | Gateway MQTT password |
| `GW_WS_PORT` | `8000` | Gateway WebSocket transport port (host) |
| `GW_HTTP_PORT` | `8001` | Gateway REST API port (host) — serves `/health` |
| `FC_PORT` | `8002` | Factory-control port (host) |
| `FC_RO_PORT` | `8004` | Read-only factory-control port (host, `PRODUCTION_READONLY` profile) |
| `ROBOT_PORT` | `8003` | Edge-AI robot port (host) |
| `DASH_PORT` | `5173` | Dashboard dev port |
| `ORION_LD_PORT` | `1026` | FIWARE Orion-LD port |
| `MONGODB_PORT` | `27017` | MongoDB port |
| `MONGODB_DB` | `orion` | MongoDB database name |
| `JSON_LD_PORT` | `3000` | JSON-LD context service port |
| `DATABASE_URL` | `sqlite+aiosqlite:///gateway.db` | Gateway DB URL |
| `MAX_EVENTS` | `10000` | Gateway event retention limit |
| `SAFETY_OPERATOR_TOKEN` | `""` | Operator auth token for gateway |
| `DEPLOYMENT_PROFILE` | `LOCAL_SIM` | Active deployment profile (`LOCAL_SIM`, `LAB_HIL`, `PRODUCTION_READONLY`) |
| `COMPOSE_PROFILES` | *(unset)* | Compose profile selector — see §4 |
