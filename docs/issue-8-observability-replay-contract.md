# Issue #8 — Observability and Event Replay Contract

**Status:** Proposed (not yet implemented beyond L1 unit tests)
**Author:** vinhphan812 reviewer
**Related:** ADR-0005 (canonical events), ADR-0006 (physical safety), Issue #31 (event store)

---

## 1. Current Observability

### Structured Logs

Every module uses Python's stdlib `logging` with `logging.getLogger(__name__)`. Loggers are instantiated at import time in each module:

| Module | File | Purpose |
|---|---|---|
| `iot_gateway.gateway` | `gateway.py` | MQTT ingest, write queue, worker lifecycle |
| `iot_gateway.mqtt_client` | `mqtt_client.py` | Connection state, subscription, disconnect |
| `iot_gateway.event_normalizer` | `event_normalizer.py` | Malformed payload warnings |
| `iot_gateway.event_store` | `event_store.py` | Schema migration, persistence, pruning |
| `iot_gateway.alerts` | `alerts.py` | Alert routing, webhook URL validation |
| `iot_gateway.api` | `api.py` | HTTP/WS request lifecycle |

Log level is set via `logging.basicConfig(level=logging.INFO)` in `cli.py`; uvicorn is silenced to `WARNING`. Output is plain-text, not JSON.

### Trace IDs

Trace IDs are **not yet implemented** in the gateway. `CanonicalEvent` has a `trace_id` field in its dict output (inherited from ADR-0005), but:
- `EventNormalizer` does not read or generate a `trace_id`
- `MqttSubscriber` does not propagate an ID from the MQTT client
- No middleware injects a correlation token into the write queue or logs
- `test_dashboard_safety.py` mentions `trace_id` only as a sanitization surface (DOM injection), not as an active correlation mechanism

### Event Recording

`EventStore` (SQLite async via aiosqlite + SQLAlchemy) persists canonical events with:
- A restart-proof global sequence counter persisted in `gateway_metadata`
- Timing metadata: `mqtt_timestamp_ms`, `event_timestamp_ms`, `received_at`, `latency_ms`, `stale`, `out_of_order`
- Bounded retention (default 10 000 events); oldest pruned by sequence
- Queries: `query()`, `get()`, `high_watermark()`, `per_device_latest()`, `count()`
- No built-in replay iterator; callers consume via REST (`/snapshot`) or WebSocket broadcast

`CanonicalEvent` (`models.py`) carries `is_timestamp_synchronized` — set `False` for ESP32 uptime/monotonic sources so `latency_ms` is set to `-1` and clock-skew checks are bypassed.

---

## 2. Proposed Observability and Event Replay

### 2a. Correlation-Aware Logs

Introduce a `correlation_id` (UUID4) at the gateway HTTP/WS ingress and propagate it:
- Inject into `CanonicalEvent.trace_id` at ingest
- Attach as `logging.LogRecord` extra field via a custom `Formatter` or `Filter`
- Log line format: `%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s %(message)s`
- Correlation ID also published to WebSocket clients so dashboards can correlate frames

**Not yet implemented:** no `correlation_id` injection, no custom log formatter, no per-request correlation context.

### 2b. End-to-End Trace IDs (Bridge → Gateway → Twin → AI)

Currently the trace starts at MQTT subscribe. Full proposal:

| Stage | Trace ID source | Propagation |
|---|---|---|
| ESP32 bridge | Not generated at UART level | — |
| Bridge → MQTT publish | Optional `X-Trace-ID` in JSON payload | Extracted by gateway normalizer |
| Gateway ingest | Auto-generated UUID4 if absent | Set as `CanonicalEvent.trace_id` |
| Gateway → Twin | Forwarded in WebSocket JSON frame | Twin renders as "origin" label |
| Gateway → AI/edge | Forwarded in alert webhook payload | Used for incident correlation |
| Operator session | Session-scoped UUID4 | Injected on all commands issued |

Open questions:
- Does the ESP32 bridge emit any correlation token in its AMLP frames? (Not yet specified.)
- Should Twin/AI propagate trace IDs upstream on actuator commands? (ADR-0006 safety guard should log the original request's trace ID.)

### 2c. Event Replay from Event Store

Replay support requires a deliberate consumer-side protocol:

```
1. Client → GET /snapshot?since_sequence=<N>
   ← { "events": [...], "high_watermark": H }

2. Client connects WebSocket

3. Gateway streams: every new event (sequence > H) as it arrives

4. On reconnect after gap:
   - Client computes gap = last_received_sequence + 1
   - Client calls GET /snapshot?since_sequence=<gap>
   - Client resumes WebSocket stream
```

Replay is **not implemented** as a dedicated iterator or CLI command. The `/snapshot` REST endpoint and WebSocket broadcast together provide the necessary primitives, but replay orchestration (replay speed control, filtering by device/type, pause/resume) is TBD.

### 2d. Sample Datasets

Produce:
- `tests/fixtures/sample_events.jsonl` — 50 canonical events (mixed device_id, event_type, stale/out-of-order flags, non-synchronized timestamps)
- `tests/fixtures/sample_trace.jsonl` — a 10-event sequence sharing the same `trace_id` to demonstrate correlation
- `tests/fixtures/stale_events.jsonl` — 10 events with `stale=True` for dashboard "unknown/stale" rendering tests
- A `scripts/replay_events.py` tool that reads a JSONL fixture and POSTs events to the gateway's REST ingest endpoint, useful for local simulation without an MQTT broker

### 2e. Mock Clocks

`models.py` already documents the `is_timestamp_synchronized = False` semantics for ESP32 uptime sources. Proposal:
- Add `tests/fixtures/mock_clock_events.py` — a pytest fixture that patches `datetime.now(timezone.utc)` to a fixed `T0` so timing-dependent tests (latency bounds, staleness) are deterministic
- Document that `TimeBounds` (`time_sync.py`) is the single clock-source boundary — tests should not mock `time.time()` directly but instead inject a `TimeBounds` with controlled bounds

---

## 3. Credential Masking in Logs

Current implementation (`alerts.py`, `_mask_url()`):
- Uses `urllib.parse.urlparse` to split netloc
- Redacts `username:password@` before logging webhook URLs
- Falls back to `"***"` on parse failure

**Gaps:**
- `mqtt_client.py` logs `broker:port` only (no credentials shown) — safe
- `gateway.py` logs `event_type.value`, `device_id`, `event_id` — safe
- **No global credential filter** — if a future module accidentally logs a full config dict or a webhook URL without calling `_mask_url()`, credentials may leak
- No `logging.Filter` that scans all log record `msg`/`args` for known secret field names (`password`, `token`, `secret`, `api_key`)

Proposed mitigations:
1. Add `CredFilter(logging.Filter)` in `iot_gateway/logging_utils.py` that redacts any `str` value in `record.args` matching `r'(password|token|secret|api_key|auth)=([^&\s]{1,})'` → `$1=***`
2. Register filter in `cli.py` after `basicConfig`
3. All webhook/alert URLs logged must go through `_mask_url()` — enforce via code review + test `test_alert_handler_protocol`

---

## 4. What Is NOT Yet Implemented

| Feature | Status | Blocker |
|---|---|---|
| Correlation ID injection | Not implemented | Requires design decision on UUID4 vs propagated |
| Custom structured log formatter | Not implemented | TBD |
| End-to-end trace IDs bridge→gateway→twin→AI | Not implemented | Bridge does not emit trace tokens; Twin/AI not wired |
| Event replay iterator / CLI | Not implemented | Consumer-side protocol exists; orchestrator not built |
| Sample event datasets | Not implemented | Needed for L2 simulation tests |
| Mock clock fixtures | Not implemented | Needed for deterministic timing tests |
| Global credential `logging.Filter` | Not implemented | Non-critical; only `_mask_url()` guards alerts |
| `trace_id` in `CanonicalEvent.from_dict` | Not implemented | Field missing in `from_dict`; `to_dict` outputs it as `None`/missing |
| Telemetry event type (`EventType.TELEMETRY`) | Planned (models.py comment) | Bridge MQTT telemetry path not established |

---

## 5. Relationship to ADR-0005 and ADR-0006

### ADR-0005 — Gateway Canonical Events

ADR-0005 defines the canonical event envelope including `trace_id` and `payload` normalization. This document extends ADR-0005 with:
- Runtime correlation context (correlation ID injection, structured log propagation)
- Replay protocol built on top of the canonical sequence number
- Credential masking as a log-safety requirement for the envelope

ADR-0005's preservation rules (original field names in `payload`, device_id integrity) remain binding for any future trace/correlation extension.

### ADR-0006 — Local Physical Safety

ADR-0006's four safety layers generate events (command ACK, status, telemetry) that flow through the observability pipeline described here. The trace ID of a command request must survive through to its safety-verified execution and be logged at each layer for incident reconstruction. Conversely, the credential masking requirement is orthogonal to safety — safety-critical log lines must not be silenced, but they must not expose credentials either.

---

*This document describes the current L1-implemented state and a proposed L2/L3 observability and replay design. Implementation requires separate issues/PRs for each major section above.*
