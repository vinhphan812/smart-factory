# Smart Factory — Deployment Topology

**Issues:** #182 · #186 · #180  
**Wave:** 4-e2e-hil · **Area:** infra / integration

---

## 1. Service Map

| Service | Language / Runtime | Port(s) | Role |
|---|---|---|---|
| **mqtt-broker** | eclipse-mosquitto:2 | 1883 (plain), 8883 (TLS) | Message bus — all southbound/northbound MQTT traffic |
| **iot-gateway** | Python 3.11+ / FastAPI + websockets | 8000 (WS/HTTP) | MQTT ingestion → SQLite → WebSocket/HTTP broadcast |
| **factory-control** | Python 3.10+ / asyncio | 8001 (HTTP) | Nine-module device adapters, production cycle scheduler |
| **dashboard** | TypeScript / Vite + React | 5173 (dev) / 80 (prod) | Operator UI — telemetry charts, event timeline, incident ACK |
| **edge-ai-robot** | Python 3.11+ / httpx + websockets | 8002 (HTTP) | MiniAlpha robot adapter, bounded skill definitions |
| **fiware-orion-ld** | Orion-LD 1.5.0 | 1026 (NGSI-LD) | FIWARE context broker — entity registry, subscriptions |
| **fiware-mongodb** | MongoDB 7.0 | 27017 | Orion-LD persistence |
| **fiware-json-ld-ctx** | nginx:alpine | 3000 | Custom NGSI-LD @context documents |

---

## 2. Service Dependency Graph

```
Internet / Operator Browser
        │
        ├──► dashboard (:5173 / :80) ──HTTP/WS──► iot-gateway (:8000)
        │                                               │
        │                                               ├──► mqtt-broker (:1883) ──Southbound──► ESP32 Bridges
        │                                               │
        │                                               ├──► fiware-orion-ld (:1026)
        │                                               │           │
        │                                               │           └──► fiware-mongodb (:27017)
        │                                               │
        │                                               └──► fiware-json-ld-ctx (:3000)
        │
        ├──► factory-control (:8001)
        │
        └──► edge-ai-robot (:8002)
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
| mqtt-broker | `localhost:1883` | mosquitto starts; TCP open |
| iot-gateway | `GET http://localhost:8000/health` | `200 {"status":"ok","version":"..."}` |
| factory-control | `GET http://localhost:8001/health` | `200 {"status":"ok"}` |
| edge-ai-robot | `GET http://localhost:8002/health` | `200 {"status":"ok"}` |
| fiware-orion-ld | `GET http://localhost:1026/health` | `200 {"orionld version":"..."}` |
| fiware-mongodb | `mongosh --eval "db.adminCommand('ping')"` | `{ok:1}` |
| fiware-json-ld-ctx | `GET http://localhost:3000/health` | `200` (nginx) |
| dashboard | `GET http://localhost/health` (prod) / Vite dev server | `200` |

### Gateway health payload

```json
{
  "status": "ok",
  "version": "0.1.0",
  "mqtt_connected": true,
  "store_event_count": 42,
  "store_high_watermark": 42,
  "uptime_seconds": 3600
}
```

---

## 4. Docker Compose — Full-Stack (without HIL)

File: `docker-compose.full.yml` (lives at repo root)

```yaml
# docker-compose.full.yml
# Full-stack Smart Factory — all services except hardware-in-the-loop.
# No ESP32, no physical uKit motors. Mock MQTT publisher drives the simulation.
#
# Usage:
#   docker compose -f docker-compose.full.yml up -d
#   docker compose -f docker-compose.full.yml ps
#   docker compose -f docker-compose.full.yml logs -f iot-gateway
#
# Teardown:
#   docker compose -f docker-compose.full.yml down -v

services:
  # ── Infrastructure ────────────────────────────────────────────────────────

  mqtt:
    image: eclipse-mosquitto:2
    container_name: sf-mqtt
    restart: unless-stopped
    ports:
      - "${MQTT_PORT:-1883}:1883"
    volumes:
      - mqtt-data:/mosquitto/data
      - mqtt-conf:/mosquitto/config
      - ./infrastructure/mqtt-broker/entrypoint.d:/docker-entrypoint.d:ro
    env_file:
      - .env
    entrypoint: ["sh", "/docker-entrypoint.d/init.sh"]
    healthcheck:
      test: ["CMD", "mosquitto_pub", "-t", "test", "-m", "ping", "-h", "localhost", "-p", "1883"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 10s
    networks:
      - sf-net

  # ── FIWARE Context Broker ─────────────────────────────────────────────────

  mongodb:
    image: mongo:7.0
    container_name: sf-mongodb
    restart: unless-stopped
    ports:
      - "${MONGODB_PORT:-27017}:27017"
    volumes:
      - mongodb-data:/data/db
      - mongodb-config:/data/configdb
    env_file:
      - fiware/mongodb.env
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - sf-net

  orion-ld:
    image: quay.io/fiware/orion-ld:1.5.0
    container_name: sf-orion-ld
    restart: unless-stopped
    ports:
      - "${ORION_LD_PORT:-1026}:1026"
    environment:
      ORION_LD_HOST: 0.0.0.0
      ORION_LD_PORT: 1026
      ORION_LD_MONGO_HOST: mongodb
      ORION_LD_MONGO_DB: ${MONGODB_DB:-orion}
      ORION_LD_LOG_LEVEL: info
      ORION_LD_USE_NGSI_LD_API: "true"
      ORION_LD_INFORMATION_MODEL: ngsi-ld
      ORION_LD_CORS_ORIGINS: "*"
      ORION_LD_MAX_LIFETIME: 0
      ORION_LD_ENTITY_ID_REGEX: ".*"
    env_file:
      - fiware/orion-ld.env
    depends_on:
      mongodb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-s", "http://localhost:1026/health"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    networks:
      - sf-net
    extra_hosts:
      - "host.docker.internal:host-gateway"

  json-ld-context:
    image: nginx:alpine
    container_name: sf-json-ld-ctx
    restart: unless-stopped
    ports:
      - "${JSON_LD_PORT:-3000}:80"
    volumes:
      - ./fiware/contexts:/usr/share/nginx/html:ro
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 5s
    networks:
      - sf-net

  # ── Core Services ────────────────────────────────────────────────────────

  iot-gateway:
    image: python:3.12-slim
    container_name: sf-iot-gateway
    restart: unless-stopped
    working_dir: /app
    command: >
      sh -c "pip install -e .[dev] &&
             uvicorn iot_gateway.api:app --host 0.0.0.0 --port 8000"
    ports:
      - "${GW_PORT:-8000}:8000"
    volumes:
      - ./iot-gateway:/app
      - gw-data:/app/data
    env_file:
      - .env
    environment:
      MQTT_BROKER: mqtt
      MQTT_PORT: "1883"
      MQTT_USERNAME: "${MQTT_GW_USERNAME:-gateway}"
      MQTT_PASSWORD: "${MQTT_GW_PASSWORD:-changeme}"
      DATABASE_URL: "sqlite+aiosqlite:///data/gateway.db"
      WS_HOST: "0.0.0.0"
      WS_PORT: "8000"
      MAX_EVENTS: "10000"
      SAFETY_OPERATOR_TOKEN: "${SAFETY_OPERATOR_TOKEN:-}"
    depends_on:
      mqtt:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-s", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 20s
    networks:
      - sf-net

  factory-control:
    image: python:3.12-slim
    container_name: sf-factory-control
    restart: unless-stopped
    working_dir: /app
    command: >
      sh -c "pip install -e . &&
             uvicorn factory_control.api:app --host 0.0.0.0 --port 8001"
    ports:
      - "${FC_PORT:-8001}:8001"
    volumes:
      - ./factory-control:/app
    environment:
      MQTT_BROKER: mqtt
      MQTT_PORT: "1883"
      MQTT_GATEWAY_URL: "http://iot-gateway:8000"
    depends_on:
      mqtt:
        condition: service_healthy
      iot-gateway:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-s", "http://localhost:8001/health"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 15s
    networks:
      - sf-net

  edge-ai-robot:
    image: python:3.12-slim
    container_name: sf-edge-ai-robot
    restart: unless-stopped
    working_dir: /app
    command: >
      sh -c "pip install -e . &&
             uvicorn edge_ai_robot.api.app:app --host 0.0.0.0 --port 8002"
    ports:
      - "${ROBOT_PORT:-8002}:8002"
    volumes:
      - ./edge-ai-robot:/app
    environment:
      MQTT_BROKER: mqtt
      MQTT_PORT: "1883"
      GATEWAY_URL: "http://iot-gateway:8000"
    depends_on:
      mqtt:
        condition: service_healthy
      iot-gateway:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-s", "http://localhost:8002/health"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 15s
    networks:
      - sf-net

  # ── Dashboard ─────────────────────────────────────────────────────────────

  dashboard:
    image: node:20-alpine
    container_name: sf-dashboard
    restart: unless-stopped
    working_dir: /app
    command: >
      sh -c "npm install &&
             npm run dev -- --host 0.0.0.0"
    ports:
      - "${DASH_PORT:-5173}:5173"
    volumes:
      - ./dashboard:/app
      - /app/node_modules
    environment:
      VITE_GATEWAY_WS_URL: "ws://iot-gateway:8000/ws"
      VITE_GATEWAY_HTTP_URL: "http://iot-gateway:8000"
    depends_on:
      iot-gateway:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:5173/"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 30s
    networks:
      - sf-net

# ── Volumes & Networks ───────────────────────────────────────────────────

volumes:
  mqtt-data:
  mqtt-conf:
  mongodb-data:
  mongodb-config:
  gw-data:

networks:
  sf-net:
    driver: bridge
    name: sf-net
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
curl -s http://localhost:8000/health | jq .store_high_watermark
```

**Recovery SLA:** Gateway reconnects within 10 s; zero event loss.

### Drill 2 — Gateway DB Corruption

**Scenario:** `gateway.db` becomes unreadable.

```bash
# 1. Backup current DB
cp data/gateway.db data/gateway.db.backup

# 2. Corrupt DB (simulate)
echo "corrupt" > data/gateway.db

# 3. Restart gateway — it should reinitialise an empty DB
docker compose -f docker-compose.full.yml restart iot-gateway

# 4. Restore from backup
docker compose -f docker-compose.full.yml exec iot-gateway \
  cp /app/data/gateway.db.backup /app/data/gateway.db

# 5. Restart to load restored DB
docker compose -f docker-compose.full.yml restart iot-gateway
```

**Recovery SLA:** < 60 s RTO; backup script tested monthly.

### Drill 3 — FIWARE Orion-LD Unavailable

**Scenario:** Orion-LD pod crashes; gateway should degrade gracefully (buffer events locally).

```bash
# 1. Stop Orion-LD
docker compose -f docker-compose.full.yml stop orion-ld

# 2. Verify gateway continues ingesting MQTT events
docker compose -f docker-compose.full.yml logs iot-gateway | grep -i "forward\|orion\|503"

# 3. Restart Orion-LD
docker compose -f docker-compose.full.yml up -d orion-ld

# 4. Health check
curl -s http://localhost:1026/health | jq .version
```

**Recovery SLA:** Gateway buffers locally; Orion-LD restores within 30 s.

### Drill 4 — Full-Stack Restart

```bash
# Stop everything gracefully
docker compose -f docker-compose.full.yml down

# Start in dependency order (docker compose resolves automatically)
docker compose -f docker-compose.full.yml up -d

# Wait for all health checks
for svc in mqtt iot-gateway factory-control edge-ai-robot dashboard; do
  echo "Waiting for $svc..."
  docker compose -f docker-compose.full.yml wait "$svc" 120
done

# Verify all healthy
docker compose -f docker-compose.full.yml ps
```

---

## 6. Backup & Restore

See [`iot-gateway/migrations/README.md`](https://github.com/vinhphan812/smart-factory/blob/feat/issue-182-deployment-e2e/iot-gateway/migrations/README.md) for the executable backup/restore tool and regression test.

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
| `GW_PORT` | `8000` | Gateway HTTP/WS port |
| `FC_PORT` | `8001` | Factory-control port |
| `ROBOT_PORT` | `8002` | Edge-AI robot port |
| `DASH_PORT` | `5173` | Dashboard dev port |
| `ORION_LD_PORT` | `1026` | FIWARE Orion-LD port |
| `MONGODB_PORT` | `27017` | MongoDB port |
| `MONGODB_DB` | `orion` | MongoDB database name |
| `JSON_LD_PORT` | `3000` | JSON-LD context service port |
| `DATABASE_URL` | `sqlite+aiosqlite:///gateway.db` | Gateway DB URL |
| `MAX_EVENTS` | `10000` | Gateway event retention limit |
| `SAFETY_OPERATOR_TOKEN` | `""` | Operator auth token for gateway |
