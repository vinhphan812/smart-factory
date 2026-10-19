# Issue #67 — Unity Gateway Transport Adapter & Offline Replay Contract

**Status:** Draft / Proposed
**Author:** Agent (delegated task)
**Reviewer:** vinhphan812
**Related issues:** #11 #33 #34 #35 #67

> **Scope note:** This document defines the interface contract. No Unity project code is claimed to exist. The Unity Digital Twin runtime is the selected engineering target (ADR-0003); editor version, assets, and scene bootstrap are tracked in #11. Unity-specific implementation is a future step gated on #11 completion.

---

## 1. Conventions and Prerequisites

- Source of truth for event normalization: `iot-gateway/src/iot_gateway/models.py` → `CanonicalEvent` dataclass.
- Source of truth for HTTP + WebSocket transport: `iot-gateway/src/iot_gateway/api.py`.
- Source of truth for device command/telemetry wire format: `esp32-ukit-bridge/docs/mqtt-contract.md`.
- All timestamps: UTC epoch milliseconds unless `is_timestamp_synchronized == false` (uptime domain).
- `schema_version` field on every fixture and serialized envelope; bump on any field rename or type change with a compatibility break note.

---

## 2. SPEC-1 — Sample Event Fixtures

Fixtures are canonical JSON envelopes produced by the gateway. Unity prefabs deserialize these directly.

### 2.1 `command_ack` — success

```json
{
  "event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "device_id": "ukit-3c61a705",
  "event_type": "command_ack",
  "payload": {
    "command_id": 102,
    "command_name": "CONVEYOR_START",
    "sequence": 42,
    "status": "ok",
    "status_code": 0,
    "attempts": 1
  },
  "mqtt_topic": "smart-factory/ukit-3c61a705/command/ack",
  "mqtt_timestamp_ms": 1750204800000,
  "timestamp": 1750204800000,
  "received_at": "2026-10-17T12:00:00.000Z",
  "received_at_ms": 1750204800050,
  "latency_ms": 50,
  "stale": false,
  "out_of_order": false,
  "is_timestamp_synchronized": true,
  "ingested_at": "2026-10-17T12:00:00.005Z",
  "sequence": 128,
  "schema_version": "1.0"
}
```

### 2.2 `command_ack` — failure (unknown command)

```json
{
  "event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "device_id": "ukit-3c61a705",
  "event_type": "command_ack",
  "payload": {
    "request_id": "abc123",
    "command_name": "CONVEYOR_STOP",
    "sequence": 43,
    "status": "unknown_command",
    "status_code": 1
  },
  "mqtt_topic": "smart-factory/ukit-3c61a705/command/ack",
  "mqtt_timestamp_ms": 1750204860000,
  "timestamp": 1750204860000,
  "received_at": "2026-10-17T12:01:00.000Z",
  "received_at_ms": 1750204860035,
  "latency_ms": 35,
  "stale": false,
  "out_of_order": false,
  "is_timestamp_synchronized": true,
  "ingested_at": "2026-10-17T12:01:00.035Z",
  "sequence": 129,
  "schema_version": "1.0"
}
```

### 2.3 `command_ack` — timeout

```json
{
  "event_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
  "device_id": "ukit-3c61a705",
  "event_type": "command_ack",
  "payload": {
    "request_id": "timeout-xyz",
    "command_name": "CONVEYOR_START",
    "sequence": 44,
    "status": "timeout"
  },
  "mqtt_topic": "smart-factory/ukit-3c61a705/command/ack",
  "mqtt_timestamp_ms": 1750204920000,
  "timestamp": 1750204920000,
  "received_at": "2026-10-17T12:02:00.000Z",
  "received_at_ms": 1750204920010,
  "latency_ms": 10,
  "stale": false,
  "out_of_order": false,
  "is_timestamp_synchronized": true,
  "ingested_at": "2026-10-17T12:02:00.010Z",
  "sequence": 130,
  "schema_version": "1.0"
}
```

### 2.4 `status_online`

```json
{
  "event_id": "c3d4e5f6-a7b8-9012-cdef-345678901234",
  "device_id": "ukit-3c61a705",
  "event_type": "status_online",
  "payload": { "status": "online" },
  "mqtt_topic": "smart-factory/ukit-3c61a705/status",
  "mqtt_timestamp_ms": 1750200000000,
  "timestamp": 1750200000000,
  "received_at": "2026-10-17T10:00:00.000Z",
  "received_at_ms": 1750200000005,
  "latency_ms": 5,
  "stale": false,
  "out_of_order": false,
  "is_timestamp_synchronized": true,
  "ingested_at": "2026-10-17T10:00:00.005Z",
  "sequence": 1,
  "schema_version": "1.0"
}
```

### 2.5 `status_offline`

```json
{
  "event_id": "d4e5f6a7-b8c9-0123-def0-456789012345",
  "device_id": "ukit-3c61a705",
  "event_type": "status_offline",
  "payload": { "status": "offline" },
  "mqtt_topic": "smart-factory/ukit-3c61a705/status",
  "mqtt_timestamp_ms": 1750210000000,
  "timestamp": 1750210000000,
  "received_at": "2026-10-17T10:16:40.000Z",
  "received_at_ms": 1750210000002,
  "latency_ms": 2,
  "stale": false,
  "out_of_order": false,
  "is_timestamp_synchronized": true,
  "ingested_at": "2026-10-17T10:16:40.002Z",
  "sequence": 90,
  "schema_version": "1.0"
}
```

### 2.6 `telemetry` — conveyor running (unsynchronized, uptime domain)

```json
{
  "event_id": "e5f6a7b8-c9d0-1234-ef01-567890123456",
  "device_id": "ukit-3c61a705",
  "event_type": "telemetry",
  "payload": {
    "values": ["CONVEYOR", "RUNNING", "60"],
    "pairs": { "SENSOR1": "1" }
  },
  "mqtt_topic": "smart-factory/ukit-3c61a705/telemetry",
  "mqtt_timestamp_ms": 123456,
  "timestamp": 123456,
  "received_at": "2026-10-17T10:05:00.000Z",
  "received_at_ms": 1750200300000,
  "latency_ms": -1,
  "stale": false,
  "out_of_order": false,
  "is_timestamp_synchronized": false,
  "ingested_at": "2026-10-17T10:05:00.000Z",
  "sequence": 50,
  "schema_version": "1.0"
}
```

**Note:** `mqtt_timestamp_ms = 123456` is ESP32 monotonic uptime, NOT UTC. `is_timestamp_synchronized = false`. Unity must treat `latency_ms = -1` as "unknown" for this event type. Use `received_at_ms` (wall clock) for ordering across unsynchronized sources.

### 2.7 Negative fixtures (reject at parse boundary)

| Case | Expected behaviour |
|------|-------------------|
| Missing `device_id` | Reject; log schema violation |
| Unknown `event_type` string | Reject; enum gate on parse |
| `is_timestamp_synchronized` absent, older fixture | Default to `true` for backwards compat |
| `schema_version` absent (pre-versioning fixtures) | Accept; emit deprecation warning in adapter |

---

## 3. SPEC-2 — Transport Interface & Auth

### 3.1 Current gateway transport (implemented)

| Transport | Endpoint | Auth | Notes |
|----------|----------|------|-------|
| HTTP REST | `GET /health`, `GET /events`, `GET /events/{id}`, `GET /snapshot`, `GET /metrics` | None | JSON responses |
| HTTP REST | `POST /safety-gate/…` | `X-Operator-Token` header (`SAFETY_OPERATOR_TOKEN`) | Timing-attack-safe compare |
| WebSocket | `ws://<host>:<port>/` | None (no auth on WS upgrade currently) | RFC-6455; broadcast-only, JSON frames |

All JSON is UTF-8. `application/json` content type on HTTP.

### 3.2 Proposed C# adapter interface (Unity side)

When the Unity project is created per #11, the following C# interface and implementations are proposed. No Unity C# code is implemented yet; this contract is the prerequisite.

```csharp
// === IGatewayTransport.cs ===
namespace SmartFactory.Unity.Gateway
{
    using System;
    using System.Collections.Generic;
    using System.Threading;
    using System.Threading.Tasks;

    /// <summary>
    /// Canonical event envelope matching CanonicalEvent.to_dict() from
    /// iot-gateway/src/iot_gateway/models.py.
    /// schema_version field must be present; adapters reject unknown major versions.
    /// </summary>
    [Serializable]
    public class CanonicalEventDto
    {
        public string event_id;
        public string device_id;
        public string event_type;          // enum string: command_ack | status_online | status_offline | telemetry | heartbeat
        public Dictionary<string, object> payload;
        public string mqtt_topic;
        public long mqtt_timestamp_ms;
        public long timestamp;             // canonical alias
        public string received_at;         // ISO8601 UTC
        public long received_at_ms;         // wall-clock UTC epoch ms
        public int latency_ms;             // -1 when is_timestamp_synchronized == false
        public bool stale;
        public bool out_of_order;
        public bool is_timestamp_synchronized;
        public string ingested_at;          // ISO8601 UTC
        public int sequence;
        public string schema_version;       // "1.0" — reject on mismatch
    }

    /// <summary>
    /// Snapshot response from GET /snapshot.
    /// </summary>
    [Serializable]
    public class SnapshotDto
    {
        public int high_watermark;
        public int snapshot_count;
        public List<CanonicalEventDto> events;
        public Dictionary<string, CanonicalEventDto> per_device_latest;
        public bool overflow;
        public int overflow_limit;
    }

    public interface IGatewayTransport
    {
        /// <summary>Establish connection to gateway. Throws on network/auth failure.</summary>
        Task ConnectAsync(CancellationToken ct = default);

        /// <summary>Terminate connection cleanly. Idempotent.</summary>
        Task DisconnectAsync();

        /// <summary>True when underlying socket/connection is open.</summary>
        bool IsConnected { get; }

        /// <summary>
        /// Subscribe to live events. Events are delivered to onEvent on the
        /// Unity main thread via AsyncOperationQueue (SPEC-3).
        /// Sequence of first live event must be > snapshot.high_watermark.
        /// </summary>
        void SubscribeToLiveEvents(Action<CanonicalEventDto> onEvent);

        /// <summary>Fetch full or incremental snapshot.</summary>
        Task<SnapshotDto> FetchSnapshotAsync(int sinceSequence = 0, int limit = 1000, CancellationToken ct = default);

        /// <summary>Latest high watermark observed from snapshot or live stream.</summary>
        int HighWatermark { get; }
    }
}
```

### 3.3 Auth

| Auth method | When required | How supplied to adapter |
|-------------|---------------|------------------------|
| None | Live WebSocket subscription, HTTP snapshot/health | — |
| `X-Operator-Token` | Safety gate POSTs only (E-stop, interlock) | Passed as `AuthToken` config param; never hard-coded |

**Design rule:** Unity is a passive consumer for Twin visualization. Operator auth tokens for E-stop belong in a separate operator-service layer, not the Twin adapter.

### 3.4 Proposed concrete implementations

| Class | Transport | Notes |
|-------|-----------|-------|
| `WebSocketTransport` | RFC-6455 WebSocket | Binary or text JSON frames; reconnect on disconnect with exponential back-off; reconnect must call `/snapshot` first |
| `HttpPollingTransport` | HTTP REST + polling | Fallback when WebSocket is unavailable; configurable poll interval; must track `high_watermark` and detect gaps |

Both implement `IGatewayTransport`. Swapping is a configuration-time concern, not a code change.

---

## 4. SPEC-3 — Main-Thread Dispatch

Unity enforces that `MonoBehaviour` lifecycle methods and `GameObject` manipulation run on the main thread. All gateway events must be marshalled from the transport thread/task context onto the main thread before updating prefab state.

### 4.1 Pattern

```csharp
// === MainThreadDispatcher.cs ===
namespace SmartFactory.Unity.Gateway
{
    using System;
    using System.Collections.Concurrent;
    using UnityEngine;

    public class MainThreadDispatcher : MonoBehaviour
    {
        private readonly ConcurrentQueue<Action> _pending = new();

        void Update()
        {
            while (_pending.TryDequeue(out var action))
                action.Invoke();  // guaranteed main thread
        }

        public void Enqueue(Action action) => _pending.Enqueue(action);
    }
}
```

### 4.2 Adapter integration

`WebSocketTransport` (or `HttpPollingTransport`) calls `mainThreadDispatcher.Enqueue(() => onEvent(canonicalEvent))` for each received event before any `GameObject` or prefab interaction.

### 4.3 Stale / offline signalling on main thread

When `is_timestamp_synchronized == false` and `received_at_ms` is older than `kTelemetryTimeoutMs` (60 000 ms by default per `mqtt-contract.md` § Telemetry), the adapter sets `stale = true`. Unity must reflect this as an amber/offline visual state on the relevant prefab — not a guessed running state.

### 4.4 Reconnect protocol (main-thread safe)

1. Transport detects disconnection.
2. Adapter calls `FetchSnapshotAsync(highWatermark)` on background thread.
3. On completion, enqueues snapshot application on main thread.
4. Resumes live subscription from `highWatermark + 1`.

---

## 5. SPEC-4 — Entity Mapping & schema_version

### 5.1 Device-ID to prefab mapping

`device_id` from `CanonicalEvent` maps to a named `GameObject` or prefab instance. The mapping is maintained by a `DeviceRegistry` component:

```csharp
public class DeviceRegistry : MonoBehaviour
{
    [SerializeField] private string deviceId;
    [SerializeField] private GameObject prefabInstance;

    public string DeviceId => deviceId;
    public GameObject PrefabInstance => prefabInstance;
}
```

The registry is populated at scene load from a `DeviceRegistryConfig` ScriptableObject or JSON asset. Unknown `device_id` events are logged and discarded (no silent prefab creation).

### 5.2 Event-type to prefab method dispatch

| `event_type` | Prefab method |
|---|---|
| `command_ack` | `OnCommandAck(CanonicalEventDto)` |
| `status_online` | `OnStatusOnline()` |
| `status_offline` | `OnStatusOffline()` |
| `telemetry` | `OnTelemetry(CanonicalEventDto)` |
| `heartbeat` | `OnHeartbeat()` |

Each method signature is defined on a `IDeviceAdapter` interface that prefab scripts implement. The dispatcher uses reflection-free interface dispatch for performance.

### 5.3 schema_version governance

- Current version: `"1.0"`
- Field rename or type change: bump minor version + backward compat entry in this document.
- Major version bump (breaking): adapter must detect via `schema_version` prefix and log a fatal error; Twin halts with an upgrade prompt.
- Unknown `schema_version` field absent: treat as `"1.0"` (pre-versioning fixtures from older gateway).

### 5.4 Sequence and ordering

`sequence` is a monotonically increasing integer assigned by the gateway event store. Unity uses `sequence` for two purposes:
1. Detecting gaps: if `incoming.sequence > highWatermark + 1`, a gap exists — request full snapshot.
2. Replay ordering: sort events by `sequence` ascending before applying to state.

Do not use `mqtt_timestamp_ms` or `received_at_ms` as ordering keys for unsynchronized sources.

---

## 6. SPEC-5 — Offline Fixture Player

The fixture player enables EditMode and PlayMode tests in Unity without a live gateway. It is a `MonoBehaviour` that implements `IGatewayTransport` and replays a fixed fixture list deterministically.

### 6.1 Interface

```csharp
// === FixturePlayer.cs ===
namespace SmartFactory.Unity.Gateway
{
    using System;
    using System.Collections.Generic;
    using UnityEngine;

    [CreateAssetMenu(fileName = "ReplayFixtureSet", menuName = "SmartFactory/ReplayFixtureSet")]
    public class ReplayFixtureSet : ScriptableObject
    {
        [Tooltip("Canonical event fixtures in ascending sequence order.")]
        public List<CanonicalEventDto> fixtures;
    }

    /// <summary>
    /// Offline replay driver implementing IGatewayTransport.
    /// Use in EditMode tests and PlayMode stub scenes.
    /// </summary>
    public class FixturePlayer : MonoBehaviour, IGatewayTransport
    {
        [SerializeField] private ReplayFixtureSet fixtureSet;
        [SerializeField] private float playbackSpeedMultiplier = 1.0f;
        [SerializeField] private bool loop = false;

        public bool IsConnected => _connected;
        public int HighWatermark { get; private set; }
        public event Action<CanonicalEventDto> OnLiveEvent;

        private bool _connected;
        private int _nextIndex;

        public async Task ConnectAsync(CancellationToken ct = default)
        {
            _connected = true;
            _nextIndex = 0;
            await Task.CompletedTask;
        }

        public Task DisconnectAsync()
        {
            _connected = false;
            return Task.CompletedTask;
        }

        public void SubscribeToLiveEvents(Action<CanonicalEventDto> onEvent)
        {
            OnLiveEvent += onEvent;
        }

        public async Task<SnapshotDto> FetchSnapshotAsync(
            int sinceSequence = 0, int limit = 1000, CancellationToken ct = default)
        {
            await Task.CompletedTask;
            var events = fixtureSet.fixtures
                .FindAll(e => e.sequence > sinceSequence)
                .GetRange(0, Math.Min(limit, fixtureSet.fixtures.Count));
            var perDevice = new Dictionary<string, CanonicalEventDto>();
            foreach (var e in fixtureSet.fixtures)
                perDevice[e.device_id] = e; // last occurrence = latest
            return new SnapshotDto
            {
                high_watermark = fixtureSet.fixtures.Count > 0
                    ? fixtureSet.fixtures[^1].sequence : 0,
                snapshot_count = events.Count,
                events = events,
                per_device_latest = perDevice,
                overflow = fixtureSet.fixtures.Count > limit,
                overflow_limit = limit
            };
        }

        // Internal playback loop — called from Update for main-thread delivery
        private float _elapsedMs;

        void Update()
        {
            if (!_connected || fixtureSet == null || fixtureSet.fixtures.Count == 0) return;
            _elapsedMs += Time.deltaTime * 1000f * playbackSpeedMultiplier;
            while (_nextIndex < fixtureSet.fixtures.Count)
            {
                var evt = fixtureSet.fixtures[_nextIndex];
                // Reconstruct inter-arrival delay from timestamps if available
                // For offline fixtures with no live clock, use fixture list order
                OnLiveEvent?.Invoke(evt);
                HighWatermark = Math.Max(HighWatermark, evt.sequence);
                _nextIndex++;
            }
            if (loop && _nextIndex >= fixtureSet.fixtures.Count)
                _nextIndex = 0;
        }
    }
}
```

### 6.2 Fixture asset creation

Fixture JSON files are authored as `.json` text assets under `Assets/Fixtures/` and converted to `ReplayFixtureSet` ScriptableObjects via `CreateAssetMenu`. The six fixtures in §2 are the minimum required baseline set.

### 6.3 Replay test cases

| Test case | Method | Expected |
|-----------|--------|---------|
| Positive: full fixture sequence | `FetchSnapshotAsync(0)` returns all 6 fixtures | `HighWatermark == max sequence` |
| Incremental: sinceSequence=128 | Returns fixtures with sequence > 128 | 3 fixtures (129, 130, offline) |
| Stale telemetry detection | Event with `stale=true` dispatched | Prefab enters stale visual state |
| Unknown device_id | Unknown device event replayed | Logged warning; no prefab created |
| schema_version mismatch | Set version to `"99.0"` in one fixture | Adapter logs fatal; halts replay |
| Loop mode | `loop=true`, run past last fixture | Playback restarts from index 0 |

---

## 7. SPEC-6 — Compatibility Matrix

| Gateway endpoint | Transport | Auth | Unity adapter call | Expected response |
|-----------------|-----------|------|--------------------|--------------------|
| `GET /health` | HTTP | None | `HttpPollingTransport.Head()` | `{status, event_count, high_watermark, queue_dropped_count}` |
| `GET /snapshot?since_sequence=0` | HTTP | None | `FetchSnapshotAsync(0)` | Full `SnapshotDto` |
| `GET /snapshot?since_sequence=N` | HTTP | None | `FetchSnapshotAsync(N)` | Incremental `SnapshotDto` |
| `ws://host:port/` | WebSocket | None | `WebSocketTransport.ConnectAsync()` | JSON frames on live events |
| `GET /events` | HTTP | None | Debug/audit only | Event list |
| `POST /safety-gate/emergency-stop` | HTTP | `X-Operator-Token` | Not called by Twin adapter | `{"emergency_stop_active": "true"}` |
| `POST /safety-gate/interlock/{id}` | HTTP | `X-Operator-Token` | Not called by Twin adapter | `{"device_id": "...", "interlock_active": "true"}` |

### 7.1 Compatibility rules

- **Gateway version 0.1.0 → Twin schema 1.0**: Compatible. No field renames or type changes observed.
- **schema_version "1.0" → gateway response**: Compatible. All response fields are present.
- **schema_version absent (pre-versioning)**: Accept with deprecation warning in adapter.
- **WebSocket unavailable**: `WebSocketTransport` falls back to `HttpPollingTransport` automatically.
- **Duplicate event_id on replay**: Adapter deduplicates by `event_id` within a session; duplicate is dropped silently.
- **Out-of-order delivery (WS)**: Unity sorts by `sequence` before applying state; `out_of_order` flag on envelope is informational.

---

## 8. Open Questions / Future Tasks

| # | Question | Owner | Gated by |
|---|----------|-------|----------|
| 1 | Unity editor LTS version for `digital-twin/` | #11 | #11 |
| 2 | `digital-twin/` repo root layout (ADR-0003 § Assets) | #11 | #11 |
| 3 | TLS for WebSocket (wss://) | future | security review |
| 4 | Prefab inventory — which physical devices map to which prefabs | #33 | #11 |
| 5 | Deterministic state reducer for command_ack ordering | #34 | #11 |
| 6 | Safety gate interlocks visualization in Twin | #35 | #11 |

---

## 9. References

- `iot-gateway/src/iot_gateway/models.py` — `CanonicalEvent`, `EventType` enum
- `iot-gateway/src/iot_gateway/api.py` — `WebSocketServer`, `create_http_app`, `GET /snapshot`, `GET /events`, `GET /health`
- `iot-gateway/src/iot_gateway/event_store.py` — `high_watermark`, `per_device_latest`, `query(since_sequence=)`
- `esp32-ukit-bridge/docs/mqtt-contract.md` — wire format, topic structure, telemetry duplicate/out-of-order policy
- `docs/adr/adr-0003-digital-twin-engine.md` — Unity engine selection, transport adapter requirement
- `docs/adr/adr-0005-gateway-canonical-events.md` — canonical event envelope design
- `docs/contracts-and-data.md` — schema versioning policy, stale state requirement
