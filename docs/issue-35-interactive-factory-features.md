# Issue #35 — Interactive Factory Playback, Camera Tours & Alarm Highlighting

**Status:** Proposed (design specification — Unity project not yet scaffolded)
**Reviewer:** vinhphan812
**Related issues:** #11 (Unity scaffold), #34 (time sync / stale / snapshot resync)
**Related ADR:** ADR-0003 (Unity engine)
**Evidence level:** L0 (static / schema design)

---

## 1. Overview

Issue #35 covers three interactive Twin features for the Unity Digital Twin:

1. **Playback modes** — navigate recorded factory history
2. **Camera tour system** — guided and manual scene navigation
3. **Alarm highlighting** — visual severity indicators with acknowledgment flow

All three are scoped to `digital-twin/` and are **not yet implemented** (per issue #11, the Unity project has not been scaffolded). They depend on the gateway event store (implemented in `iot-gateway/`) for historical data and on the time-synchronization work of issue #34 for temporal fidelity.

---

## 2. Playback Modes

### 2.1 Supported Modes

| Mode | Behaviour |
|---|---|
| **Live** | Consume new events via WebSocket; Twin animates in real time. |
| **Paused** | Freeze animation at current playback head; buffer incoming events but do not apply them. |
| **Rewind** | Step backward event-by-event, reverting Twin state. |
| **Seek** | Jump directly to a target timestamp or sequence number, rehydrate Twin state from the event store snapshot. |
| **Playback speed** | 0.25×, 0.5×, 1×, 2×, 4× (live rate multiplier). Direction is always forward; rewind is a separate mode. |

### 2.2 Data Source: Event Store Queries

Playback consumes the gateway event store via the IoT Gateway HTTP/WebSocket API.

**Snapshot bootstrap (seek / initial load):**
- `GET /snapshot?since_sequence=<last_seq>` — returns ordered events with `sequence > since_sequence` up to the current `high_watermark`, plus `per_device_latest` (one event per device at the most recent sequence). **Important:** `/snapshot` returns the current state of the store — it does NOT return the authoritative state at a historical target sequence. It provides catch-up events from the cursor to now, which is the correct primitive for client reconnect/resync, not for historical seek.
- `high_watermark()` — returns the highest committed sequence number in the store.

**Incremental replay:**
- `GET /events?since_sequence=<seq>&limit=<N>` — returns events after the given sequence cursor.
- WebSocket `/ws` — push of new events after the subscribed cursor.

**Retention note:** The event store prunes events beyond `max_events` (default 10 000) oldest-by-sequence. Seek beyond the retention window returns a gap; the client must handle this gracefully (show a warning, offer the nearest available window).

### 2.3 What `/snapshot` Does NOT Do

> **The `/snapshot` endpoint returns current state only.** It is NOT a historical state reconstruction endpoint.

- `/snapshot?since_sequence=N` returns events with `sequence > N` up to the current `high_watermark`. This is a catch-up primitive for reconnecting clients.
- `/snapshot` does **not** accept a target timestamp or historical sequence to reconstruct state at an arbitrary past point. There is no checkpoint/point-in-time snapshot mechanism.
- Historical playback requires event store **replay**: iterate events from a known-good starting sequence to the target sequence, applying each event to the Twin state. This is a client-side or service-layer concern; the gateway provides the ordered event log only.

### 2.4 Historical Playback Requires Event Store Replay

Playback to an arbitrary historical point is achieved by:
1. Establishing a **known-good state anchor** (e.g. a baseline snapshot at sequence S₀, or replay from sequence 0).
2. Replaying events from the anchor forward: `GET /events?since_sequence=<S>&limit=<N>` iterated until `sequence` reaches or exceeds the target.
3. Applying each event to the Twin state reducer in order.

> ⚠️ **Retention policy limitation:** The event store prunes events beyond `max_events` (default 10 000) oldest-by-sequence. Seek or replay beyond the retention window returns a gap; the client must handle this gracefully (show a warning, offer the nearest available window). No separate historical archive is implemented.

### 2.5 Snapshot Strategy (Client Reconnect, Not Historical Seek)

1. On reconnect, request `/snapshot?since_sequence=<last_known_seq>` to get catch-up events to now.
2. If `overflow=True` in the response, request a full snapshot (`since_sequence=0`) to avoid state gaps.
3. Apply the events to Twin GameObjects (device states, actuator positions, sensor values).
4. Subscribe to WebSocket for live events with `sequence > high_watermark`.
5. For **rewind**, walk backward through the cached event list client-side or via a reverse query endpoint (not currently exposed — see open item below).

### 2.5 Open Items (not yet implemented)

- Reverse-chronological event query endpoint (event store `query()` currently returns ascending sequence only).
- Playback head position must track `event_timestamp_ms`, not wall-clock time, to remain accurate across pauses and disconnects (requires issue #34 work).
- Stale indicator: if the WebSocket disconnects during playback, the Twin must show **UNKNOWN/STALE** per the architecture contract — it must not extrapolate forward.
- Historical seek to an arbitrary point in time requires a client-side replay loop — no dedicated endpoint or gateway service provides this.

---

## 3. Camera Tour System

### 3.1 Predefined Routes

- Each route is a Unity `Timeline` asset or C# waypoint sequence: a list of `(position, rotation, fov, dwell_seconds)` tuples associated with a named tour ID.
- Routes are serialised as JSON or ScriptableObject assets under `Assets/Tours/` and loaded at startup.
- A tour plays automatically in sequence when activated; the operator can interrupt at any time.

### 3.2 Auto-Follow

- Auto-follow attaches the active camera to a target device's GameObject (e.g. the currently active conveyor).
- When the target changes state (e.g. a robot arm begins a task), the camera smoothly transitions to track the new focus device.
- Auto-follow can be enabled/disabled independently of tour playback.

### 3.3 Manual Control

- Orbit, pan, zoom (standard Unity Cinemachine or custom controller).
- Manual overrides a running tour; the tour resumes when manual control is released (after a configurable idle timeout, default 10 s).

### 3.4 Relationship to Playback

During replay, camera tours are driven by the playback clock (`event_timestamp_ms`), not wall-clock time. If the playback is paused or rewound, the camera tour pauses or reverses accordingly (routes must support reversible playback or provide a fallback static view).

### 3.5 Open Items (not yet implemented)

- No Cinemachine or camera controller exists in the codebase yet (issue #11 milestone).
- Tour asset format and editor tooling are not defined.

---

## 4. Alarm Highlighting

### 4.1 Alarm Event Types

The gateway canonical event schema (`docs/contracts-and-data.md`) defines `event_type`. Alarms are identified by event type or by payload severity fields:

```json
{
  "event_type": "alarm.triggered",
  "device_id": "conveyor-01",
  "payload": {
    "severity": "critical",
    "message": "OVERSPEED_DETECTED",
    "code": 0x01
  }
}
```

Alarm event types (to be confirmed in `contracts/` once issue #3 review is complete):
- `alarm.triggered`
- `alarm.acknowledged`
- `alarm.cleared`

### 4.2 Severity Levels

| Level | Label | Visual treatment |
|---|---|---|
| `info` | Info | Blue badge, no audio |
| `warning` | Warning | Amber pulse, soft audio chime |
| `critical` | Critical | Red flash + screen-edge vignette, persistent audio until acknowledged |
| `resolved` | — | Green checkmark, auto-clears after 5 s |

### 4.3 Visual Indicators

- **3D scene:** affected device GameObject gets an additive emissive overlay (colour per severity) and an optionally animated exclamation / warning / info icon above it.
- **2D HUD:** a collapsible alarm log panel lists active alarms chronologically with severity chip, device ID, timestamp and message.
- **Timeline bar (playback UI):** alarm events appear as coloured markers on the playback scrubber.

### 4.4 Acknowledgment Flow

```
[Alarm triggered] → shown on HUD + scene
    ↓ operator clicks ACK
[Acknowledged] → visual state changes (pulsing → solid badge), audio stops
    ↓ (optional) operator resolves root cause
[Alarm cleared] → removed from active list after 5 s delay
```

- Acknowledgment is a local UI action; it does **not** send a command to the device (that is a separate operator workflow).
- Multiple unacknowledged critical alarms may stack; the HUD sorts by severity then time.

### 4.5 Open Items (not yet implemented)

- `alarm.*` event types are not yet defined in `contracts/` (issue #3 review pending).
- No alarm UI prefab, no severity-colour theme, no audio assets.
- Acknowledgment state is not persisted in the event store (not a cross-client requirement for v1; local session state only).

---

## 5. Relationship to ADR-0003 and Issue #34

### ADR-0003 (Unity Engine)

ADR-0003 records **Unity** as the sole 3D runtime for the Twin. All three features described in this document are scoped to the Unity `digital-twin/` module and use Unity semantics (GameObjects, C# components, Cinemachine, Timeline). If the ADR's formal governance review changes the engine, this specification must be updated accordingly. The current engineering decision is Unity.

### Issue #34 (Time Synchronization, Stale Data, Snapshot Resync)

Issue #35 is **blocked on issue #34** in the following ways:

| Dependency | Impact on #35 |
|---|---|
| `event_timestamp_ms` fidelity | Playback must use event timestamps, not wall-clock time; issue #34 establishes the clock source. |
| Stale/offline indication | Twin must display UNKNOWN/STALE when the WebSocket stream is interrupted during playback. |
| Snapshot resync protocol | Seek and initial load depend on the `/snapshot` endpoint and `since_sequence` cursor contract defined in issue #34. |
| Offline replay contract | Rewind and reverse playback require the offline replay contract (not yet defined). |

The issue README marks #34 as **OPEN / P1**, dependent on gateway transport adapter (#67) and offline replay contract. This design document inherits those blockers.

---

## 6. What Is NOT Yet Implemented

The following are **not yet implemented** and are out of scope until the listed preconditions are resolved:

| Item | Precondition |
|---|---|
| `digital-twin/` Unity project, scene prefabs, GameObject state mapping | Issue #11 (Unity scaffold) |
| Playback UI (timeline scrubber, speed control, rewind/pause buttons) | Issues #11, #34 |
| Camera tours (Cinemachine, waypoints, Timeline assets) | Issue #11 |
| Alarm highlighting (severity visuals, HUD panel, acknowledgment flow) | Issues #11, #3 (alarm event schema) |
| Reverse event query for rewind | Issue #34 / gateway API extension |
| WebSocket event stream for live/replay | Issue #34 / `iot-gateway/` WebSocket endpoint |
| `alarm.*` event type definitions | Issue #3 schema review |
| Unity scene prefabs for the nine factory modules | Issue #12 |
| **Checkpoint / point-in-time snapshot mechanism** | No mechanism exists to reconstruct Twin state at an arbitrary historical sequence. `/snapshot` returns current state only. Historical playback requires a client-side replay loop (not implemented). |
| **Event store replay service** | No gateway service provides historical replay to a target sequence or timestamp. Clients must implement their own replay logic against `/events`. |
| **Historical retention archive** | Events beyond `max_events` (default 10 000) are pruned. No separate long-term archive exists. Historical playback is bounded by the retention window. |

The IoT Gateway event store (`iot-gateway/src/iot_gateway/event_store.py`) is **implemented** and provides the data source for playback queries. All other components above are planned artefacts in this document only.

---

## 7. Acceptance Criteria (Design Phase)

- [ ] This document is reviewed and approved by vinhphan812.
- [ ] Alarm event type taxonomy is added to `contracts/` after issue #3 review.
- [ ] Reverse-query endpoint design is raised as an issue or included in issue #34 scope.
- [ ] Unity scene prefab naming conventions and camera controller architecture are defined in `docs/twin/prefab-module-contracts.md` (future, after issue #11 scaffold).
