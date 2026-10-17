# Issue #34 — Unity Time Synchronization, Stale Data & Snapshot Resync Contract

**Status:** Draft / Proposed  
**Author:** Agent (delegated task)  
**Reviewer:** vinhphan812  
**Related issues:** #11 #33 #35 #67 #89  
**Related PRs:** #89 (ADR-0003)

> **Scope note:** This document defines the gateway-side time-sync and staleness contract consumed by the Unity Digital Twin. No Unity C# assets are claimed to exist. Unity implementation is gated on #11.

---

## 1. Current Implementation

### 1.1 `is_timestamp_synchronized` — state field

Defined in `iot-gateway/src/iot_gateway/models.py` → `CanonicalEvent`:

```python
@dataclass
class CanonicalEvent:
    received_at_ms: int = 0       # wall-clock UTC ms at gateway ingress
    latency_ms: int = 0           # transit latency in ms; -1 when unsynchronized
    stale: bool = False
    out_of_order: bool = False
    # True = source timestamp is UTC (latency/clock_skew valid)
    # False = source timestamp is uptime/monotonic (latency/clock_skew NOT valid)
    is_timestamp_synchronized: bool = True
    ingested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sequence: int = 0             # monotonically increasing integer from event store
```

**Current behaviour by event type** (`event_normalizer.py`):

| `event_type` | `is_timestamp_synchronized` | `latency_ms` | `received_at_ms` domain |
|---|---|---|---|
| `telemetry` | `False` | `-1` (sentinel) | ESP32 monotonic uptime |
| `command_ack` | `True` (assumed NTP) | computed | wall-clock UTC |
| `status_online` / `status_offline` | `True` | computed | wall-clock UTC |

The normalizer sets `is_timestamp_synchronized=False` for telemetry because the ESP32 bridge's `received_at_ms` field is monotonic milliseconds since bridge boot — **not UTC**. Clock-skew detection and latency computation are structurally invalid for uptime-domain sources until the bridge emits UTC timestamps. This is the root of the time-sync problem.

### 1.2 What is currently implemented

| Component | File | Status |
|---|---|---|
| `CanonicalEvent` dataclass with `is_timestamp_synchronized` | `models.py` | ✅ Implemented |
| Normalizer stamps `is_timestamp_synchronized` per source type | `event_normalizer.py` | ✅ Implemented |
| `TimeBounds` stale threshold + clock-skew config | `time_sync.py` § `TimeBounds` | ✅ Implemented |
| `TimeMetrics` per-device latency, jitter, stale/OOO counters | `time_sync.py` § `TimeMetrics` | ✅ Implemented |
| `TimeMetrics.observe()` checks `is_timestamp_synchronized` flag | `time_sync.py` lines 150-163 | ✅ Implemented (P1 fix) |
| Latency/jitter aggregates exclude unsynchronized events (`latency < 0`) | `time_sync.py` lines 159-172 | ✅ Implemented |
| `EventStore` timing columns: `event_timestamp_ms`, `received_at`, `latency_ms`, `stale`, `out_of_order` | `event_store.py` | ✅ Implemented |
| Schema migration for timing columns | `event_store.py` § `_migrate_schema` | ✅ Implemented |
| `GET /snapshot` with `since_sequence` cursor + `high_watermark` | `api.py` § `get_snapshot` | ✅ Implemented |
| `GET /metrics` exposing `TimeMetrics.snapshot()` | `api.py` | ⚠️ Defined but wiring unconfirmed |
| Stale-event detection logic (threshold comparison) | `event_normalizer.py` | ❌ Not implemented — `stale` always `False` |
| Out-of-order detection logic | `event_normalizer.py` | ❌ Not implemented — `out_of_order` always `False` |
| Configurable per-device or per-event-type stale thresholds | `time_sync.py` § `TimeBounds.threshold_for` | ❌ Stub — returns global value |
| NTP sync at bridge side | ESP32 bridge | ❌ Not implemented |
| UTC timestamp in `mqtt_timestamp_ms` / `timestamp` for telemetry | ESP32 bridge | ❌ Not implemented |
| `is_timestamp_synchronized` field on serialized envelope | `models.py` § `to_dict` | ✅ Implemented |

---

## 2. Proposed Behaviour

### 2.1 Event time vs. receive time

The gateway must distinguish two timestamp domains and carry provenance in the envelope:

```
Source domain (device/bridge):
  - telemetry:   received_at_ms = ESP32 uptime ms          → is_timestamp_synchronized = False
  - command_ack: received_at_ms = UTC ms (assumed NTP)     → is_timestamp_synchronized = True
  - status:      received_at_ms = UTC ms (assumed NTP)     → is_timestamp_synchronized = True

Gateway domain (gateway ingress):
  - ingested_at  = wall-clock ISO8601 UTC at gateway receipt
  - received_at  = wall-clock UTC ms at gateway receipt (mirrors ingested_at)
  - latency_ms   = received_at_ms(UTC) - mqtt_timestamp_ms(UTC)
                   Set to -1 when is_timestamp_synchronized = False
```

**Ordering rule:** Unity must use `sequence` (gateway-assigned integer) as the primary ordering key, not `received_at_ms` or `mqtt_timestamp_ms`. The bridge delivers MQTT QoS 0; delivery order is not guaranteed.

**Latency rule:** `latency_ms` is only meaningful when `is_timestamp_synchronized = True`. Do not compute or aggregate `latency_ms` for telemetry events until the bridge emits UTC timestamps.

### 2.2 Stale data detection

Stale detection is applied by the normalizer before the event is persisted and broadcast. The proposed logic:

```
age_ms = utc_now_ms() - received_at_ms(source_domain)
if is_timestamp_synchronized:
    age_ms = utc_now_ms() - received_at_ms(UTC)
else:
    # Cannot compute age from uptime; use wall-clock delta as proxy
    age_ms = gateway_wall_clock_delta  # (ingested_at - event.ingested_at is circular)

stale = age_ms > TimeBounds.stale_threshold_ms
```

**Key constraint:** Until telemetry carries a UTC timestamp, stale detection for telemetry events must use a heuristic. The preferred heuristic is **time since last known event from that device** tracked in `TimeMetrics._last_event_ms`. If no event from device `X` arrives within `stale_threshold_ms` of the last observed event, mark subsequent events as stale.

**Default thresholds** (`TimeBounds`):

| Parameter | Default | Config field |
|---|---|---|
| `stale_threshold_ms` | 30 000 ms | `TIME_SYNC_STALE_THRESHOLD_MS` |
| `max_clock_skew_ms` | 300 000 ms (5 min) | `TIME_SYNC_MAX_CLOCK_SKEW_MS` |

The prefab-module-contracts document (`docs/twin/prefab-module-contracts.md` §4.5) already defines a **60 000 ms** stale timeout for Unity side (`kTelemetryTimeoutMs` in `bridge_config.h`). The gateway threshold (30 s) is intentionally more aggressive — it flags "getting stale" so the Twin can show an amber state before the hard 60 s cutoff.

### 2.3 Out-of-order detection

Out-of-order detection uses `TimeMetrics._last_event_ms` per device:

```
out_of_order = is_timestamp_synchronized and received_at_ms < _last_event_ms[device_id]
```

For unsynchronized sources (`is_timestamp_synchronized=False`), out-of-order cannot be reliably determined from timestamps. Use `sequence` as the authoritative ordering signal instead.

### 2.4 Snapshot reconnect protocol

The protocol is defined in `event_store.py` § Snapshot semantics and `api.py` § `get_snapshot`. Unity must follow this exact sequence on every WebSocket disconnect:

```
1.  Transport detects disconnection.
2.  Call GET /snapshot?since_sequence=<last_known_sequence>&limit=1000
    - If response.overflow == True → retry GET /snapshot?since_sequence=0
    - If response.events has a sequence gap relative to local state → retry GET /snapshot?since_sequence=0
3.  Apply snapshot events to local state, sorted by sequence ascending.
4.  Resume WebSocket subscription; discard any events with sequence <= high_watermark.
```

The `/snapshot` response shape:

```json
{
  "high_watermark": 128,
  "snapshot_count": 50,
  "overflow": false,
  "overflow_limit": 1000,
  "events": [...],
  "per_device_latest": { "ukit-00000000": {...}, "ukit-AABBCCDD": {...} }
}
```

`per_device_latest` gives Unity a current-state anchor per device without replaying the full log. Unity should merge these into local state after replay.

**Retention:** `EventStore` enforces `max_events` (default 10 000). When the store overflows, oldest events by sequence are pruned. Clients that connected before the overflow window will see a sequence gap and must request a full snapshot.

### 2.5 Latency metrics

`GET /metrics` exposes `TimeMetrics.snapshot()`:

```json
{
  "latency_ms": {
    "ukit-00000000": { "count": 142, "min": 8, "max": 240, "mean": 47.3, "samples": [...] },
    "ukit-AABBCCDD": { "count": 89,  "min": 12, "max": 180, "mean": 38.1, "samples": [...] }
  },
  "jitter_ms": {
    "ukit-00000000": 12.4,
    "ukit-AABBCCDD": 9.8
  },
  "stale_event_count": 3,
  "out_of_order_event_count": 7,
  "unsynchronized_event_count": 214,
  "last_event_ms": { "ukit-00000000": 1750204800000, "ukit-AABBCCDD": 1750204799000 }
}
```

`unsynchronized_event_count` tracks telemetry events whose `latency_ms = -1`. These are **excluded from `latency_ms` and `jitter_ms` aggregates** — the mean reflects only synchronized sources. Unity can use this field to monitor the proportion of telemetry events for which latency is unknown.

**Memory bound:** `TimeMetrics` uses `deque(maxlen=1000)` per device. No unbounded growth.

### 2.6 Configurable time bounds

`TimeBounds` is a frozen dataclass instantiated at gateway startup from environment variables:

| Env var | Field | Default |
|---|---|---|
| `TIME_SYNC_STALE_THRESHOLD_MS` | `stale_threshold_ms` | `30000` |
| `TIME_SYNC_MAX_CLOCK_SKEW_MS` | `max_clock_skew_ms` | `300000` |

`TimeBounds.threshold_for(device_id, event_type)` currently returns the global value. Future extension (not yet implemented): per-device or per-event-type overrides loaded from `device-registry.md` or a config map.

---

## 3. What Is NOT Yet Implemented

| Gap | Location | Blocker |
|---|---|---|
| Stale flag computation in normalizer | `event_normalizer.py` | Needs `TimeBounds` injected; needs UTC timestamp for telemetry |
| Out-of-order flag computation in normalizer | `event_normalizer.py` | Needs `TimeMetrics._last_event_ms` state shared across events |
| UTC timestamp in bridge telemetry (`mqtt_timestamp_ms`) | ESP32 bridge firmware | Bridge does not have NTP; `received_at_ms` is uptime |
| `is_timestamp_synchronized = True` for telemetry | Bridge + normalizer | Depends on bridge UTC support |
| `GET /metrics` wired to FastAPI | `api.py` | Endpoint may not be registered in `create_http_app` |
| Per-device stale threshold override | `time_sync.py` § `threshold_for` | Config map not defined |
| Clock-skew correction (NTP offset application) | Normalizer | Requires UTC source timestamp |
| Unity `IGatewayTransport` snapshot integration | Unity project (#11) | Project not yet created |

---

## 4. Relationship to ADR-0003 and Issue #67

### ADR-0003 — Unity Engine Decision

ADR-0003 (`docs/adr/adr-0003-digital-twin-engine.md`) selects Unity as the sole 3D runtime and mandates:

> *"Integrate normalized gateway data via a contract-bound transport adapter, deterministic state reducer and Unity main-thread visualization; support stale/offline indication, reconnect snapshots, playback and EditMode/PlayMode tests."*

This contract provides the gateway-side half of that mandate. The Unity-side adapter contract is defined in **issue #67 § SPEC-2–SPEC-5** (`docs/issue-67-unity-gateway-transport-contract.md`). Specifically:

- **ADR-0003 § "stale/offline indication"** → `CanonicalEvent.stale` + `is_timestamp_synchronized` (this document §2.2, §2.3).
- **ADR-0003 § "reconnect snapshots"** → `GET /snapshot` + reconnect protocol (this document §2.4).
- **ADR-0003 § "deterministic state reducer"** → Gateway sequence + Unity-side `sequence` sorting (issue #67 § SPEC-4 §5.4).
- **ADR-0003 § "EditMode/PlayMode tests"** → `FixturePlayer` (issue #67 § SPEC-5), backed by fixtures with `is_timestamp_synchronized` set appropriately.

ADR-0003 is **Proposed** pending governance review (#79/#80). Institutional approval for Unity over the original Unreal proposal is **not verified**.

### Issue #67 — Gateway Transport Contract

Issue #67 (`docs/issue-67-unity-gateway-transport-contract.md`) defines the Unity-side transport adapter. It references this contract's fields directly:

| From this document | Consumed by #67 |
|---|---|
| `is_timestamp_synchronized`, `latency_ms` | `CanonicalEventDto.is_timestamp_synchronized`, `latency_ms`; SPEC-4 § staleness note |
| `stale`, `out_of_order` | `CanonicalEventDto.stale`, `CanonicalEventDto.out_of_order`; SPEC-3 §4.3 stale signalling |
| `sequence`, `high_watermark` | `SnapshotDto.high_watermark`; SPEC-4 §5.4 sequence ordering |
| `GET /snapshot` response shape | `IGatewayTransport.FetchSnapshotAsync`; SPEC-6 compatibility matrix |
| `per_device_latest` | `SnapshotDto.per_device_latest`; SPEC-2 § snapshot DTO |

**Open question from #67 §8 row 5:** *"Deterministic state reducer for command_ack ordering"* — gated on Unity project creation (#11). This contract does not define the reducer; it only guarantees `sequence` is the authoritative ordering key.

---

## 5. References

- `iot-gateway/src/iot_gateway/models.py` — `CanonicalEvent` dataclass, `is_timestamp_synchronized` field
- `iot-gateway/src/iot_gateway/event_normalizer.py` — timestamp stamping, `is_synchronized` flag
- `iot-gateway/src/iot_gateway/time_sync.py` — `TimeBounds`, `TimeMetrics`
- `iot-gateway/src/iot_gateway/event_store.py` — timing columns, snapshot semantics, sequence persistence
- `iot-gateway/src/iot_gateway/api.py` — `GET /snapshot`, `GET /metrics` endpoints
- `docs/twin/prefab-module-contracts.md` — Unity stale policy (`kTelemetryTimeoutMs = 60 000 ms`)
- `docs/issue-67-unity-gateway-transport-contract.md` — Unity transport adapter, `IGatewayTransport`, `FixturePlayer`
- `docs/adr/adr-0003-digital-twin-engine.md` — Unity engine selection, transport adapter requirement
- `esp32-ukit-bridge/docs/mqtt-contract.md` — wire format, `received_at_ms` uptime semantics
