# L2 Evidence — IoT Gateway

**Evidence level:** L2
**Module:** `iot-gateway/`
**Archive version:** smart-factory/t_74cb2b44-47-research-evidence-archive-and-reprodu
**Pinned commit:** `244f333`
**Date:** 2026-10-17

---

## What this evidence covers

The IoT Gateway (`iot-gateway/`) subscribes to the ESP32 bridge MQTT topics, normalizes events into the canonical envelope, stores them durably in SQLite, and exposes them via WebSocket and HTTP. This file records L2 evidence for those claims using simulated MQTT and mock devices.

**Evidence level definitions:**
- **L1** = host unit tests for local algorithms (models, normalizer logic)
- **L2** = simulated MQTT broker + mock bridge, verifying full ingest pipeline

---

## MQTT ingest — L2 evidence

### Normalizer — L2

**Claim:** Gateway correctly normalizes raw MQTT command-ack and status events into the canonical event envelope.

**Canonical envelope schema:**
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

**Evidence:**
- `tests/test_normalizer.py` — all tests PASS
  - Valid MQTT message → canonical envelope with correct fields
  - Malformed JSON → rejection with diagnostic log
  - Missing required field → rejection with error code
  - `event_id` is UUIDv4 and unique
  - `ingested_at` is ISO 8601 UTC
  - `sequence` is monotonically increasing per device_id

**Reproduce:**
```bash
pytest iot-gateway/tests/test_normalizer.py -v
```

---

## Event store — L2 evidence

**Claim:** Gateway stores canonical events durably in SQLite and exposes them via REST API.

**Evidence:**
- `tests/test_store.py` — all tests PASS
  - Event inserted → retrieved by event_id
  - Events retrieved by device_id filter
  - Events retrieved by event_type filter
  - Sequence ordering preserved
  - SQLite write durability verified

**Reproduce:**
```bash
pytest iot-gateway/tests/test_store.py -v
```

---

## HTTP REST API — L2 evidence

**Claim:** REST endpoints return correct canonical events and health status.

**Evidence:**
- `tests/test_api.py` — all tests PASS
  - `GET /events` — returns event list with pagination
  - `GET /events?device_id=X` — filtered by device
  - `GET /events?event_type=X` — filtered by type
  - `GET /events/{event_id}` — returns single event
  - `GET /health` — returns health status

**Reproduce:**
```bash
pytest iot-gateway/tests/test_api.py -v
```

---

## WebSocket broadcast — L2 evidence

**Claim:** Gateway broadcasts canonical events over WebSocket in real time.

**Evidence:**
- `tests/test_gateway.py` — all tests PASS
  - Client connects to `ws://localhost:8000/`
  - MQTT message received → WebSocket broadcast received within 100ms
  - Client receives valid canonical envelope JSON
  - Disconnected client receives no messages (no queue overflow)

**Reproduce:**
```bash
pytest iot-gateway/tests/test_gateway.py -v
```

---

## Alert system — L2 evidence

**Claim:** Gateway routes robot alert notifications through the typed alert system with bounded skill execution feedback.

**Evidence:**
- `tests/test_alerts.py` — all tests PASS
  - Alert event normalized and stored
  - Alert delivered via WebSocket
  - Unsupported skill → explicit failure payload (no silent fallback)
  - Alert with malformed skill name → rejection with diagnostic

**Reproduce:**
```bash
pytest iot-gateway/tests/test_alerts.py -v
```

---

## Safety — L2 evidence

**Claim:** Gateway enforces the command safety model: malformed commands rejected, no queued execution during broker disconnect, role-gated command console.

**Evidence:**
- `tests/test_dashboard_safety.py` — all tests PASS
  - Invalid command payload → rejection; no event emitted
  - Broker disconnect → no queued command executed
  - Role-gated endpoint → unauthorized role receives 403
  - E-stop event → local safety stop event emitted regardless of MQTT state

**Reproduce:**
```bash
pytest iot-gateway/tests/test_dashboard_safety.py -v
```

---

## Security — L2 evidence

### SSRF hardening

**Claim:** Gateway prevents server-side request forgery in webhook and external URI resolution.

**Evidence:**
- `tests/test_ssrf.py` — all tests PASS
  - `http://localhost/` — blocked
  - `http://127.0.0.1/` — blocked
  - `http://0.0.0.0/` — blocked
  - Internal hostname — blocked
  - Redirect chain followed and each hop verified
  - External HTTPS → allowed

**Reproduce:**
```bash
pytest iot-gateway/tests/test_ssrf.py -v
```

---

## Time synchronization — L2 evidence

**Claim:** Gateway records and exposes timestamp metadata allowing latency measurement.

**Evidence:**
- `tests/test_time_sync.py` — all tests PASS
  - `mqtt_timestamp_ms` extracted from raw message
  - `ingested_at` set at gateway receipt
  - Clock skew between `mqtt_timestamp_ms` and `ingested_at` disclosed as `is_timestamp_synchronized` flag
  - Out-of-order events correctly flagged via `sequence` field

**Reproduce:**
```bash
pytest iot-gateway/tests/test_time_sync.py -v
```

**Note:** WS broadcast timestamp instrumentation is NOT YET IMPLEMENTED (see `docs/issue-18-research-milestones.md` §5 gap). Latency p50/p95/p99 cannot be measured from end-to-end at this time.

---

## Models — L1 evidence

**Claim:** Gateway data models correctly validate and serialize canonical event structures.

**Evidence:**
- `tests/test_models.py` — all tests PASS
  - CanonicalEvent model validates all required fields
  - DeviceEvent model validates AMLP telemetry mapping
  - Serialization round-trip (model → JSON → model) preserves fields

**Reproduce:**
```bash
pytest iot-gateway/tests/test_models.py -v
```

---

## CI evidence

| Job | Evidence level | Status | Notes |
|-----|---------------|--------|-------|
| pytest Python 3.11 | L2 | CI green on `244f333` | `.github/workflows/gateway-ci.yml` |
| pytest Python 3.12 | L2 | CI green on `244f333` | `.github/workflows/gateway-ci.yml` |
| coverage report | L2 | CI green | `--cov-report=xml --cov-report=term-missing` |

**Note:** CI runs on `fix/p0-root-module-boundaries` and `master`. Verify against GitHub Actions for the latest status.

---

## Hardware-blocked claims from this module

| Claim | Blocking level | Blocker | Evidence gate |
|-------|---------------|---------|--------------|
| Live bridge → broker → gateway telemetry | BLOCKED-L3 | Bridge firmware TEL→MQTT not implemented; no ESP32 board | Requires ESP32 with real bridge firmware |
| WS broadcast timestamp instrumentation | NOT IMPLEMENTED | Gap identified in `docs/issue-18-research-milestones.md` | Implementation required before E-TA experiment |
| Canonical sequence + snapshot table | NOT IMPLEMENTED | Issue #31 | Event store gap |
| Telemetry schema mismatch | KNOWN GAP | ADR-0009; Issue #66 | Must resolve before L3/L4 evidence |

---

## Related documents

- Gateway README: `iot-gateway/README.md`
- Canonical event contract: `contracts/v1/command-lifecycle.md`
- MQTT contract: `esp32-ukit-bridge/docs/mqtt-contract.md`
- Latency measurement plan: `docs/issue-43-latency-measurement-plan.md`
- Event store contract: `docs/issue-31-event-store-contract.md`
