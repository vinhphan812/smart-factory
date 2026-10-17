# Issue #17 — Local Reproducible Dev Stack: Contract

**Status:** Proposed
**Issue:** #17
**Author:** Infrastructure agent
**Reviewer:** vinhphan812
**Branch:** `issue-17-dev-stack-contract`

---

## 1. Current State — What Infrastructure Exists

The `infrastructure/` directory is **PLANNED** per repository-layout; it is partially provisioned but not yet wired into a complete Compose stack.

| Asset | Status | Location |
|---|---|---|
| `infrastructure/README.md` | Written | `infrastructure/README.md` |
| `docker-compose.yml` | Partial | `docker-compose.yml` (root) |
| `mqtt-broker/entrypoint.d/init.sh` | Implemented | `infrastructure/mqtt-broker/entrypoint.d/init.sh` |
| `mqtt-broker/docs/acl-design.md` | Proposed | `infrastructure/mqtt-broker/docs/acl-design.md` |
| `mqtt-broker/docs/healthcheck-design.md` | Proposed | `infrastructure/mqtt-broker/docs/healthcheck-design.md` |
| `mqtt-broker/docs/tls-setup.md` | Proposed | `infrastructure/mqtt-broker/docs/tls-setup.md` |
| `mqtt-broker/config/tls/generate-certs.sh` | Implemented | `infrastructure/mqtt-broker/config/tls/generate-certs.sh` |
| `mqtt-broker/config/tls/create-creds.sh` | Implemented | `infrastructure/mqtt-broker/config/tls/create-creds.sh` |
| TLS CA/key/cert generation | Implemented | `infrastructure/mqtt-broker/config/tls/` |
| `iot-gateway/` service | Implemented | `iot-gateway/` (root sibling) |
| `esp32-ukit-bridge/` firmware | Implemented | `esp32-ukit-bridge/` |

**Current Compose coverage:** only `mqtt` and `mqtt-tls` services are defined. No gateway, storage, dashboard, or simulator services are wired in.

**Current MQTT broker state:**
- `eclipse-mosquitto:2` image
- Dynamic `mosquitto.conf` generated at container start via `entrypoint.d/init.sh`
- Credentials via env vars (`MQTT_ADMIN_USERNAME`, `MQTT_BRIDGE_USERNAME`, `MQTT_GW_USERNAME` + passwords)
- Per-device ACLs with literal username=deviceId design (documented in `acl-design.md`)
- No container healthcheck (Option B — restart policy only; per `healthcheck-design.md`)
- TLS optional via `--profile tls`

---

## 2. Proposed Compose Stack

### Services

| Service | Image | Profile | Purpose |
|---|---|---|---|
| `mqtt` | `eclipse-mosquitto:2` | default | MQTT broker (plaintext) |
| `mqtt-tls` | `eclipse-mosquitto:2` | tls | MQTT broker (TLS) |
| `gateway` | `iot-gateway/` (local build) | default | MQTT ingest, event normalization, SQLite storage |
| `dashboard` | placeholder | default | Role-specific operator display (PLANNED) |
| `twin` | placeholder | default | Unity Digital Twin (PLANNED) |
| `sim-ukit` | placeholder | default | uKit device simulator (PLANNED) |
| `sim-bridge` | placeholder | default | ESP32 bridge simulator (PLANNED) |

### Network

All services communicate over a single isolated Docker network `smart-factory-net`. No service is directly port-published to the host except the ones intentionally exposed.

```
smart-factory-net (bridge driver: bridge)
  ├── mqtt (1883 plain, 8883 TLS)
  ├── gateway (internal only: 8000 WS, 8001 HTTP)
  ├── dashboard (:3000 → host)
  ├── twin (:8080 → host)
  ├── sim-ukit
  └── sim-bridge
```

### Volumes

| Volume | Service | Purpose |
|---|---|---|
| `mqtt-data` | mqtt | Mosquitto persistence |
| `mqtt-conf` | mqtt | Dynamic mosquitto.conf + passwd + ACL (init.sh writes here) |
| `mqtt-tls-data` | mqtt-tls | TLS variant persistence |
| `mqtt-tls-conf` | mqtt-tls | TLS variant config |
| `gateway-db` | gateway | SQLite event store |

---

## 3. Healthchecks, Environment Files, Ports, Credentials

### Healthchecks

Per `infrastructure/mqtt-broker/docs/healthcheck-design.md` **Option B**: no container-level healthcheck on the MQTT broker. `restart: unless-stopped` handles crashes. For the gateway, a `curl`-based HTTP healthcheck on `GET /health` is used.

Proposed healthcheck for gateway:
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -sf http://localhost:8001/health || exit 1"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 10s
```

Simulator services use `exit 0` / `exit 1` via a lightweight health script; no external port is required.

### Environment Files

**`.env.example`** (committed, no real credentials):
```env
# ── MQTT Broker ─────────────────────────────────────────────
MQTT_PORT=1883
MQTT_BIND_ADDRESS=0.0.0.0
MQTT_ADMIN_USERNAME=admin
MQTT_ADMIN_PASSWORD=changeme
# Per-device bridge credentials (username = deviceId)
MQTT_BRIDGE_USERNAME=ukit-00000000
MQTT_BRIDGE_PASSWORD=bridge_secret_dev
# Gateway credential
MQTT_GW_USERNAME=gateway
MQTT_GW_PASSWORD=gateway_secret_dev

# ── TLS (optional) ────────────────────────────────────────────
MQTT_TLS_ENABLED=false
MQTT_TLS_PORT=8883
MQTT_TLS_LISTENER_ADDRESS=0.0.0.0
MQTT_TLS_BIND=127.0.0.1:8883

# ── Gateway ──────────────────────────────────────────────────
DATABASE_URL=sqlite+aiosqlite:///data/gateway.db
WS_PORT=8000
WS_HTTP_PORT=8001
MQTT_BROKER=mqtt
MAX_EVENTS=10000

# ── Dashboard ────────────────────────────────────────────────
# DASHBOARD_PORT=3000  # PLANNED

# ── Simulators ──────────────────────────────────────────────
# SIM_BRIDGE_DEVICE_ID=ukit-00000000  # PLANNED
# SIM_UKIT_DEVICE_ID=ukit-00000000    # PLANNED
```

**`.env`** (`.gitignore`d):
```env
# Copy from .env.example and fill in real values for local dev.
# NEVER commit this file.
```

### Ports

| Port | Service | Host-exposed | Protocol |
|---|---|---|---|
| 1883 | mqtt | Yes (localhost) | MQTT plaintext |
| 8883 | mqtt-tls | Yes (127.0.0.1) | MQTT TLS |
| 8000 | gateway | No (internal) | WebSocket |
| 8001 | gateway | No (internal) | HTTP REST |
| 3000 | dashboard | Yes (localhost) | HTTP (PLANNED) |
| 8080 | twin | Yes (localhost) | HTTP (PLANNED) |

### Credential Handling

- **Design:** Mosquitto credentials are passed via env vars and written to `passwd` file by `init.sh` at container start. No credentials baked into config files.
- **Per-device isolation:** Bridge username MUST equal deviceId (e.g. `ukit-00000000`). ACL uses literal strings; mosquitto ACL files do not expand env vars.
- **Gateway:** Single credential (`gateway` user) with wildcard subscribe ACLs across all device topics.
- **Secrets:** No secrets in committed files. `.env` is `.gitignore`d. TLS certs generated locally via `generate-certs.sh` and mounted read-only into the TLS container.
- **Not implemented:** credential rotation mechanism, secret injection via Vault/KMS, TLS cert auto-renewal.

---

## 4. One-Command Startup

```bash
# 1. Generate TLS certs (optional, only needed for mqtt-tls profile)
cd infrastructure/mqtt-broker/config/tls && ./generate-certs.sh && cd ../../../..

# 2. Copy and fill env
cp .env.example .env
$EDITOR .env   # set credentials

# 3. Start full stack
docker compose up -d

# 4. Verify
docker compose ps
docker compose logs mqtt --tail=20

# 5. Run smoke test
docker compose run --rm gateway python -m pytest iot-gateway/tests/ -k smoke

# Shutdown
docker compose down
```

With TLS enabled:
```bash
docker compose --profile tls up -d
```

---

## 5. What Is NOT Yet Implemented

| Item | Status | Blocker |
|---|---|---|
| `docker-compose.yml` gateway service | **NOT IMPLEMENTED** | gateway service definition missing |
| `docker-compose.yml` dashboard service | **NOT IMPLEMENTED** | `dashboard/` module is PLANNED (#15) |
| `docker-compose.yml` twin service | **NOT IMPLEMENTED** | `digital-twin/` module is PLANNED (#11) |
| `docker-compose.yml` sim-ukit simulator | **NOT IMPLEMENTED** | No simulator written yet |
| `docker-compose.yml` sim-bridge simulator | **NOT IMPLEMENTED** | No simulator written yet |
| `smart-factory-net` Docker network | **NOT IMPLEMENTED** | All services use default bridge |
| Named volume `gateway-db` | **NOT IMPLEMENTED** | SQLite persistence not wired |
| `gateway` Dockerfile / entrypoint | **NOT IMPLEMENTED** | gateway runs locally, not containerized |
| `dashboard` Dockerfile | **NOT IMPLEMENTED** | module does not exist |
| `twin` Dockerfile | **NOT IMPLEMENTED** | module does not exist |
| Per-device bridge ACL for second+ bridge | **NOT IMPLEMENTED** | `init.sh` handles one bridge credential only |
| Credential rotation mechanism | **NOT IMPLEMENTED** | Requires operational design (ADR-0010) |
| TLS trust-anchor rotation | **NOT IMPLEMENTED** | Not designed |
| Broker healthcheck (Option A) | **NOT IMPLEMENTED** | Option B chosen (no healthcheck) |
| Backup/recovery runbooks | **NOT IMPLEMENTED** | Scripts not written |
| CI runner environment setup | **NOT IMPLEMENTED** | Not designed |

---

## 6. Relationship to ADR-0002 (Bridge MQTT ↔ AMLP Contract)

ADR-0002 (`docs/adr/adr-0002-bridge-mqtt-amlp-contract.md`) establishes the wire contract between the ESP32 bridge and the MEGA endpoint. The dev stack implements the **server side** of that contract:

| ADR-0002 topic | Direction | Broker ACL (per ADR-0010) | Dev stack status |
|---|---|---|---|
| `smart-factory/{deviceId}/command/down` | Bridge subscribes | Bridge read-only | Implemented (mqtt broker) |
| `smart-factory/{deviceId}/command/ack` | Bridge publishes | Bridge write-only | Implemented (mqtt broker) |
| `smart-factory/{deviceId}/telemetry` | Bridge publishes | Bridge write-only | Implemented (mqtt broker) |
| `smart-factory/{deviceId}/status` | Bridge publishes | Bridge write-only | Implemented (mqtt broker) |
| `smart-factory/{deviceId}/heartbeat` | Bridge publishes | — | **NOT IMPLEMENTED** (not in ADR-0002 current spec; requires separate decision) |

The dev stack's `mqtt` service enforces the ACL design documented in `infrastructure/mqtt-broker/docs/acl-design.md`, which implements ADR-0010's proposed authorization policy aligned with ADR-0002's topic structure.

**ADR-0002 §"Harder"** notes a schema mismatch: `contracts/v1/schemas/` uses `timestamp`/`state` field names, but the bridge sends `received_at_ms`/`values`/`pairs`. This is tracked separately in ADR-0009. The gateway's `EventNormalizer` must perform this normalization; the compose stack provides the infrastructure but does not implement the normalization logic.

The broker runs as a sibling service to `iot-gateway/` at repository root — it is never nested under `esp32-ukit-bridge/`, consistent with repository boundary rule #3.

---

## 7. Evidence

| Evidence | Type | Location |
|---|---|---|
| Current Compose (mqtt only) | L0 static | `docker-compose.yml` |
| Mosquitto entrypoint script | L0 static | `infrastructure/mqtt-broker/entrypoint.d/init.sh` |
| ACL design rationale | L0 static | `infrastructure/mqtt-broker/docs/acl-design.md` |
| Healthcheck design | L0 static | `infrastructure/mqtt-broker/docs/healthcheck-design.md` |
| TLS cert generation script | L0 static | `infrastructure/mqtt-broker/config/tls/generate-certs.sh` |
| ADR-0002 wire contract | L0 static | `docs/adr/adr-0002-bridge-mqtt-amlp-contract.md` |
| ADR-0010 broker security policy | L0 static | `docs/adr/adr-0010-mqtt-broker-security.md` |
| ADR-0009 telemetry schema compatibility | L0 static | `docs/adr/adr-0009-telemetry-schema-compatibility.md` |
| iot-gateway README | L0 static | `iot-gateway/README.md` |
| Repository layout | L0 static | `docs/architecture/repository-layout.md` |

---

*Reviewer: vinhphan812. Do not merge without review approval.*
