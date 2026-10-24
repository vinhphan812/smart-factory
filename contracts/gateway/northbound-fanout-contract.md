# Gateway Northbound Fanout Contract (consumer-facing, versioned)

**Owner:** dev-architect (Issue #194, wave: 2-gateway-core, P0)
**Contract version:** `northbound-fanout` v1.0.0 (envelope `envelope_version: "1.0"`)
**Status:** **Specification** — normative for the consumer-facing read surface.
**Evidence level:** **L0 (contract / static)** — no deployed, integration or HIL claim.
**Related issue:** #194 (implementation increment is a separate card; this document does **not** close it).

---

## 0. Scope, and how this relates to the contracts that already exist

This document specifies the **versioned northbound fanout contract** that independent consumers
(Unity Digital Twin, React Dashboard, and any future read-only consumer) program against.

It does **not** restate the contracts that already exist in this repository:

| Existing document | What it owns (do not duplicate here) | How this document uses it |
|---|---|---|
| [`live-state-fanout.md`](./live-state-fanout.md) | Transport catalogue (WebSocket / SSE / MQTT re-publish), the v0 canonical envelope field list, subscription lifecycle prose, ordering/dedup/back-pressure prose. | **Normative for transports and the v0 envelope.** This document adds the *versioned* field set, the cursor contract, the subscription-filter contract, the trust boundary, the typed fixtures, and the implemented-vs-planned ledger. |
| [`sync-contracts.md`](./sync-contracts.md) | Per-consumer mapping (Unity module→3D object, telemetry→animation, React endpoint usage, Orion-LD, Yanshee). | **Normative for consumer-side mapping.** This document only pins the *wire* shapes those mappings consume, and adds the parity fixture that makes the Unity and React mappings provably equivalent. |
| [`telemetry-schema-v2.md`](./telemetry-schema-v2.md) + [`contracts/v2/schemas/telemetry.schema.json`](../v2/schemas/telemetry.schema.json) | The `payload` body for telemetry events (`schema_version: "2.0"`). | **Referenced, not re-specified.** The northbound envelope carries the telemetry payload unchanged; this contract never redefines payload internals. |
| [`contracts/v1/schemas/device-event.schema.json`](../v1/schemas/device-event.schema.json) | The **cross-system** device event envelope named by [ADR-0005](../../docs/adr/adr-0005-gateway-canonical-events.md:77) — `device_id`, `timestamp` (ISO-8601 string), `event_type`, `payload`, optional `sequence` / `trace_id`, `additionalProperties: false`. | **Referenced, not re-specified, and deliberately not the northbound wire shape.** The northbound envelope is a *Gateway-canonical, northbound* envelope with a different field set, a different `event_type` vocabulary and a different timestamp representation. The divergence is recorded as D-8 in §7.1; this contract does **not** redefine the v1 schema and does **not** claim conformance to it. |
| [`canonical-flows.md`](./canonical-flows.md) | Cross-system flow catalogue, MQTT topic table, shared constants. | Referenced for topic and port semantics. |
| [`ADR-0005`](../../docs/adr/adr-0005-gateway-canonical-events.md) | The decision that all events are normalised into one canonical envelope, `event_id` as the idempotency key. | Normative background. |

Where this document and an existing document disagree **about the implementation as it exists
today**, this document wins, because it was written against the source. Every such divergence is
listed explicitly in §7.3 — none of them are silently corrected elsewhere.

### 0.1 Machine-readable artefacts

| Artefact | Purpose |
|---|---|
| [`northbound-fanout.schema.json`](./northbound-fanout.schema.json) | JSON Schema (draft-07) for the northbound v1 envelope, the snapshot response, the stream frame, the subscription filter and the read-path error envelope. |
| [`fixtures/README.md`](./fixtures/README.md) | Fixture pack: how to use it, the deterministic projection rule, the parity rule. |
| [`fixtures/fixture.schema.json`](./fixtures/fixture.schema.json) | JSON Schema for the fixture pack itself (language-agnostic). |
| [`fixtures/northbound-fixture.v1.json`](./fixtures/northbound-fixture.v1.json) | The single recorded Gateway fixture both consumers are validated against. |
| [`fixtures/northbound-fixture.v1.json` → `expected_state`](./fixtures/northbound-fixture.v1.json) | The visual/status state each consumer must derive from that fixture, expressed once per consumer language in the `unity` and `react` sections. The two sections are the same content and MUST stay equal. |
| [`fixtures/bindings/GatewayAdapter.cs`](./fixtures/bindings/GatewayAdapter.cs) | Reference-only typed C# binding of the fixture (Unity `GatewayAdapter`). |
| [`fixtures/bindings/gatewayClient.ts`](./fixtures/bindings/gatewayClient.ts) | Reference-only typed TypeScript binding of the fixture (React client). |
| [`fixtures/validate_fixtures.py`](./fixtures/validate_fixtures.py) | Executable check: schema validation, `unity`/`react` equality, and re-running the TypeScript projection. |

The files under `fixtures/bindings/` are **reference artefacts, not production code**. The
production Unity and React clients stay in `digital-twin/` and `dashboard/`.

---

## 1. SPEC-1 — Source-of-truth boundary

### 1.1 The three states, and which one a consumer may trust

| State | Owner | Where it lives | Consumer trust |
|---|---|---|---|
| **Device physical state** | The device (ESP32 bridge / controller). | The device only. The Gateway never reads it directly. | **Not directly observable.** A consumer only ever sees the device's *reported* state. |
| **Gateway persisted canonical state** | The Gateway. | SQLite `events` table (`iot-gateway/src/iot_gateway/event_store.py`, `EventRecord`). | **Authoritative for "what the Gateway has accepted so far"** — i.e. history, ordering, dedup key, cursor. |
| **Consumer-projected state** | The consumer. | Unity scene / React store. | **Derived.** A consumer MUST be able to rebuild it entirely from the Gateway read surface. |

The Gateway is the **only** component that converts a device report into a canonical event
(`EventNormalizer`, `iot-gateway/src/iot_gateway/event_normalizer.py:64`) and the only component
that persists it (`EventStore.insert_dict`, `iot-gateway/src/iot_gateway/event_store.py:238`).
Consumers MUST NOT attempt to reconstruct canonical state from raw MQTT.

### 1.2 Raw envelope versus canonical event

```
raw MQTT frame on smart-factory/{device_id}/{telemetry|status|heartbeat|command/ack}
   │   topic + arbitrary JSON bytes; no ordering guarantee; no units; no clock domain
   ▼
EventNormalizer.normalize()                    event_normalizer.py:64
   │   • topic → device_id, event_type        event_normalizer.py:77-92
   │   • timestamp extraction + CLOCK DOMAIN   event_normalizer.py:105-132
   │   • staleness / out-of-order flags        event_normalizer.py:134-151
   ▼
CanonicalEvent (Python dataclass)              models.py:17
   │   • event_id (uuid4) • device_id • event_type • payload
   │   • observed time • received_at • latency_ms • stale • out_of_order
   │   • is_timestamp_synchronized • sequence
   ▼
EventStore.insert_dict() → SQLite `events`     event_store.py:238
   ▼
EventStore.query() / per_device_latest()       event_store.py:308 / :390
   │
   ├──► GET /events, GET /snapshot              api.py:215, api.py:233
   └──► WebSocket broadcast                     api.py:133 → gateway.py:79
```

The raw envelope is **southbound and private**. It appears in the northbound envelope only as
provenance (`mqtt_topic`, `mqtt_timestamp_ms`) and MUST NOT be used for routing, ordering or
unit interpretation by consumers.

### 1.3 The versioned field set (`envelope_version: "1.0"`)

The v0 envelope (what the code emits today) already carries timing fields but leaves the four
things a consumer most needs **undefined**. Northbound v1 makes them explicit. All four additions
are **SPECIFIED-BUT-NOT-IMPLEMENTED** (§6).

| Field | v1 semantics | Replaces / relates to |
|---|---|---|
| `units` | Object mapping every measured quantity to its unit (`temperature`, `humidity`, `speed`, `position`, `uptime` + free-form extras). A consumer MUST apply these units and MUST NOT infer units from a field name. | New. Today the payload carries raw values with no unit declaration. |
| `boot_id` | Identifier of the device boot session that produced the observation; `null` when the device does not publish one. A **change of `boot_id` means a device restart**: the consumer MUST reset device-local derivations (uptime counters, "since-boot" accumulators) and MUST NOT treat pre-restart and post-restart observations as one continuous series. | New. `boot_id` is already named as the dedup/identity ingredient for the FIWARE context sink in `docs/adr/adr-0014-fiware-orion-ld-context.md:134`, but is never produced by the Gateway. |
| `observed_at` | UTC epoch milliseconds at which the **device** observed the state. `null` when the device supplied no timestamp. Not comparable across devices when `quality.clock_domain != "utc"`. | Formalises the ambiguous v0 `timestamp` alias (`models.py:73`), which silently falls back to `mqtt_timestamp_ms` and therefore can be an uptime counter. |
| `received_at` (+ `received_at_ms`) | UTC instant at which the **Gateway** received the observation. The only timestamp guaranteed to be in the Gateway clock domain; the ordering anchor for everything that follows. | Already present in v0. Retained unchanged. |
| `quality` | Structured verdict: `status` (`good`/`uncertain`/`degraded`/`invalid`), `reason`, `stale`, `out_of_order`, `clock_domain`, `latency_ms`. | Wraps the v0 loose booleans `stale` / `out_of_order` / `is_timestamp_synchronized` (kept in v1 as legacy mirrors for v0 consumers). |

**Ordering rule:** order by `sequence` (Gateway-assigned), never by `observed_at`. `observed_at`
is descriptive only.

**Clock-domain rule (normative):** a consumer MUST NOT compare `observed_at` across devices, MUST
NOT compute transit latency, and MUST NOT use `observed_at` for ordering unless
`quality.clock_domain == "utc"`. When `quality.clock_domain == "device_monotonic"` the source
timestamp is an uptime counter (`received_at_ms` on the ESP32 payload — see
`event_normalizer.py:105-132`) and `quality.latency_ms` is `-1`.

---

## 2. SPEC-2 — The versioned read surface

### 2.1 What actually exists in `iot-gateway/` today

Authoritative inventory, read from `iot-gateway/src/iot_gateway/api.py`. The FastAPI app is
created by `create_http_app()` (`api.py:170`) and served by Uvicorn on **`ws_http_port`**
(default **8001**), `gateway.py:180-190`. The WebSocket server is a **separate** `websockets`
server on **`ws_port`** (default **8000**), `api.py:87-131`, `gateway.py:45`.

| Method | Path | Handler | Auth | Notes |
|---|---|---|---|---|
| GET | `/health` | `api.py:203` | none | `status`, `event_count`, `high_watermark`, `queue_dropped_count`. |
| GET | `/events` | `api.py:215` | none | Query: `device_id`, `event_type`, `limit` (1–10000). **No `since_sequence` on this route.** |
| GET | `/events/{event_id}` | `api.py:226` | none | 404 `{"detail": "Event not found"}` when unknown. |
| GET | `/snapshot` | `api.py:233` | none | Query: `since_sequence` (≥0), `limit` (1–10000, default 1000). Returns `high_watermark`, `snapshot_count`, `events`, `per_device_latest`, `overflow`, `overflow_limit`. |
| GET | `/metrics` | `api.py:297` | none | Latency/jitter histograms, stale & out-of-order rates; `queue_dropped_count` is a **caller-supplied** query parameter, not server state. |
| GET | `/` | `api.py:325` | none | Service name, version `0.1.0`, `/docs`. |
| GET | `/safety-gate/status`, `/safety-gate/audit-log` | `api.py:334`, `api.py:339` | none | Read-only safety views. |
| POST | `/safety-gate/emergency-stop`, `/safety-gate/interlock/{device_id}`, `/safety-gate/operator-override`, `/safety-gate/authorize` | `api.py:354`, `:367`, `:385`, `:399` | `X-Operator-Token` | **Write domain** — see §5. |
| GET | `/incidents`, `/incidents/{id}` | `api.py:415`, `api.py:431` | none | |
| POST | `/incidents/{id}/acknowledge`, `/incidents/{id}/resolve` | `api.py:439`, `api.py:452` | `X-Operator-Token` | **Write domain.** |
| GET/POST/DELETE | `/devices*`, `/provisioning/*`, `/ota/*` | `api.py:471`–`api.py:829` | **none enforced** | **Registered only when `registry` / `provisioning` / `ota` are passed to `create_http_app` (`api.py:469`, `:580`, `:685`).** The running Gateway passes only `store`, `metrics`, `dropped_count_ref` (`gateway.py:46`), so **these routes are absent in the default deployment.** Several of their docstrings state `Requires X-Operator-Token header`, but their handlers carry **no** token dependency — see §7.2-G13. |
| WS | `ws://<host>:8000/` | `api.py:59`–`api.py:168` | **none** | RFC-6455 via the `websockets` library; **any** path is accepted (the handler ignores the request path), no query parameters are parsed, no server greeting, no heartbeat frames, no per-client subscription. |

The gateway's own outbound WS port default is `WS_PORT=8000` and the HTTP default is
`WS_PORT + 1 = 8001` (`iot-gateway/src/iot_gateway/config.py:21`, `config.py:32`).

### 2.2 The northbound v1 read surface

Every consumer read is one of two shapes. Both are covered by
[`northbound-fanout.schema.json`](./northbound-fanout.schema.json).

**(a) Snapshot read — `GET /snapshot`** → `snapshot_response` (schema
`#/definitions/snapshot_response`). The v1 additions to the existing response are `envelope_version`,
`cursor` (`high_watermark`, `last_sequence`, `since_sequence`), `resync_required` and
`oldest_retained_sequence`. The existing fields keep their names and meaning — the v1 snapshot
response is a **superset** of the v0 body, so a v0 client that ignores unknown keys still works.

**(b) Incremental read — the stream** → `stream_frame` (schema `#/definitions/stream_frame`).
`frame_type` is `event`, `gap` or `heartbeat`. A v1 stream carries the same canonical event as
the snapshot, wrapped in a frame so that control information (gaps, liveness) is distinguishable
from data. The v0 WebSocket carries the bare event object; §7.3-G3 records that difference and
§6 states the transition rule.

### 2.3 Subscription filters

v1 defines one filter object (schema `#/definitions/subscription_filter`) used by every incremental
read path:

| Filter field | Semantics | Implemented? |
|---|---|---|
| `device_ids[]` | Restrict to these device identifiers. | **No** — must be applied client-side today (§6, P-3). |
| `module_ids[]` | Restrict to factory modules. Depends on the device→module mapping of Issue #169, which does not exist yet. | **No** — blocked on #169. |
| `event_types[]` | Restrict to canonical event types. | **No** — server-side filter does not exist. |
| `since_sequence` | Resume cursor. Only events with `sequence > since_sequence` are delivered. | **Partially** — `/snapshot` honours it (`api.py:233`); the WebSocket does not (it is a pure broadcast, `api.py:133`). |

Rules: OR within a group, AND across groups. An empty filter means *all devices, all event
types*. Filtering is a **delivery optimisation only** — it MUST NOT change event content, and a
consumer that receives the unfiltered stream MUST reach the same projected state (§1.1).

### 2.4 Replay cursor and high-watermark

| Term | Definition | Implemented? |
|---|---|---|
| `high_watermark` | Highest `sequence` durably persisted in the EventStore at the moment the response was produced. `EventStore.high_watermark()`, `event_store.py:379`. | **Yes.** |
| `last_sequence` | Highest `sequence` actually included in the response body. | **No** — v1 addition. |
| `since_sequence` | The cursor the consumer supplied. `0` means "full snapshot". | **Yes** on `/snapshot`. |
| `oldest_retained_sequence` | Lowest `sequence` still in the store. The store prunes the oldest rows above `MAX_EVENTS` (default 10000), `event_store.py:283-302`, `config.py:33`. | **No** — v1 addition; today a consumer can only infer it by trying a cursor and inspecting the result. |
| `resync_required` | `true` when the consumer MUST discard local state and resynchronise from a full snapshot. | **No** — v1 addition. |

**Consumer cursor rule (normative):** a consumer MUST treat `sequence` as an opaque
*monotonic-within-a-Gateway-incarnation* ordinal and MUST maintain a single
`last_applied_sequence` per device set. It MUST NOT assume the sequence space is stable across
Gateway restarts — see §7.3-G1.

### 2.5 Bounded fanout and back-pressure

| Bound | Value | Source | Behaviour on breach |
|---|---|---|---|
| Write queue (MQTT ingest → SQLite) | 500 events | `gateway.py:32` | Event **dropped**, `_dropped_count` incremented (`gateway.py:115`), surfaced at `GET /health` as `queue_dropped_count` (`api.py:203`). |
| Per-client WebSocket queue | 64 frames | `api.py:75` | The client queue is **removed from the broadcast set** (`api.py:150-156`). See §7.3-G2 — the connection is *not* closed, so the client stalls silently rather than being disconnected. |
| Event retention | `MAX_EVENTS`, default 10000 | `config.py:33`, `event_store.py:283` | Oldest events pruned; a cursor below `oldest_retained_sequence` is unrecoverable. |
| Write workers | 2 concurrent | `gateway.py:31` | Broadcast order across workers is **not** sequence order (§7.3-G4). |

v1 requires the fanout to be **explicitly bounded and observable**: a lagging client MUST receive a
`gap` frame naming the missing range before it can silently skip events, and MUST be closed with a
defined close code. Neither exists today (§6, P-2).

---

## 3. SPEC-3 — Delivery sequence

### 3.1 The normal path

```
consumer                                gateway
   │
   │ 1. GET /snapshot?since_sequence=0&limit=<L>
   │◄──────────────────────────────────── high_watermark = H
   │                                     events[]      (oldest-first, see §7.3-G5)
   │                                     per_device_latest = state anchors
   │                                     cursor.last_sequence
   │
   │ 2. consumer applies per_device_latest, then the events[]
   │    consumer sets last_applied_sequence = cursor.last_sequence
   │
   │ 3. consumer opens the stream
   │    • WS: ws://host:8000/            (v1: resume via ?since_sequence=, §6 P-4)
   │    • SSE: GET /events/stream        (planned, live-state-fanout.md §1.2)
   │
   │ 4. for each frame:
   │      frame_type == "event":
   │        • if event.sequence <= last_applied_sequence → DUPLICATE, drop (idempotency)
   │        • if event.sequence >  last_applied_sequence + 1 → GAP (see §3.2)
   │        • else apply, last_applied_sequence = event.sequence
   │      frame_type == "gap"   → resynchronise (§3.2)
   │      frame_type == "heartbeat" → liveness only, no state change
```

**The cursor N / N+1 rule:** the snapshot and the stream MUST be joined at a single cursor. The
consumer applies the snapshot up to `cursor.last_sequence` and then applies only stream events with
`sequence > cursor.last_sequence`. There MUST be no window in which an event is applied twice or
skipped: the snapshot's `last_sequence` and the stream's resume point are the same number.

**Gapless resync:** if the stream cannot deliver `last_applied_sequence + 1` (retention pruned it,
the client was dropped, or the Gateway restarted), the consumer MUST re-read
`GET /snapshot?since_sequence=0` and rebuild local state from `per_device_latest`, then rejoin the
stream at the new `last_sequence`. The snapshot path (`since_sequence=0`) is the only authoritative
full-state source; `per_device_latest` (`event_store.py:390`) is the anchor set.

### 3.2 Reconnect, deduplication, gap

| Situation | Required consumer behaviour |
|---|---|
| **Reconnect** | On stream close: re-read `GET /snapshot?since_sequence=<last_applied_sequence>`. If the response carries `resync_required: true`, or the returned events do not start exactly at `last_applied_sequence + 1`, or `overflow: true`, fall back to `since_sequence=0` and rebuild from `per_device_latest`. Then rejoin the stream at the new cursor. |
| **Deduplication** | Deduplicate on `event_id` (UUIDv4, `models.py:37`), **not** on `sequence` and **not** on content hash. `sequence` is not unique across Gateway restarts (§7.3-G1). The Gateway does **not** deduplicate on any transport — the consumer owns idempotency (`live-state-fanout.md` §5.2). |
| **Gap detection** | A consumer MUST detect a gap when the next applied event's `sequence` is greater than `last_applied_sequence + 1`, or when a `gap` frame is received. On detection it MUST NOT silently skip: it MUST resynchronise per the reconnect rule above. |
| **Out-of-order delivery** | Events MAY arrive out of `sequence` order (two write workers, `gateway.py:31`, broadcast at `gateway.py:79` and `gateway.py:97`). A consumer MUST sort by `sequence` within its buffer before applying, and MUST NOT assume FIFO delivery. |
| **Duplicate `event_id`, different `sequence`** | Possible after a restart (§7.3-G1). The `event_id` dedup rule wins: the second copy MUST be dropped. |

### 3.3 Device offline, device restart, and clock uncertainty

| Situation | Required behaviour |
|---|---|
| **Device offline** | The device publishes `status_offline` (normaliser maps `online: false` → `EventType.STATUS_OFFLINE`, `event_normalizer.py:90-92`). A consumer MUST move the device to an explicit *offline* visual state and MUST NOT keep animating it from the last known telemetry. It MUST NOT mark the device *stale* and *offline* as the same state — offline is a positive device statement, stale is the absence of one. |
| **Device restart** | Signalled by a change of `boot_id` (§1.3). The consumer MUST reset device-local derivations and MUST NOT treat the pre-restart and post-restart series as continuous. `boot_id` is **not produced by the Gateway today** (§6, P-5). |
| **Clock-domain uncertainty** | The ESP32 bridge publishes `received_at_ms` (uptime), not UTC (`event_normalizer.py:105-110`). The Gateway flags this as `is_timestamp_synchronized = false` (`event_normalizer.py:123`) and sets `latency_ms = -1` (`event_normalizer.py:132`). A consumer MUST: not compute latency, not order across devices by `observed_at`, and must surface `quality.clock_domain != "utc"` rather than presenting a misleading absolute time. |
| **Staleness** | The Gateway flags `stale` when the observation is older than the configured threshold (`event_normalizer.py:134-139`, default 30 000 ms, `time_sync.py:33`). A consumer MUST surface a distinct *stale* visual state and MUST NOT present stale values as current. |
| **Gateway restart** | The sequence space does not survive a restart correctly today (§7.3-G1). A consumer MUST detect the discontinuity (see the `sequence` regression rule below) and MUST resynchronise from a full snapshot. |

---

## 4. SPEC-4 — Typed consumer fixtures

### 4.1 The rule this section exists to enforce

> **One recorded Gateway fixture MUST produce exactly the same visual/status state in the Unity
> C# `GatewayAdapter` and in the React/TypeScript gateway client.**

"Exactly the same" is made checkable by separating three things:

1. **The recorded fixture** — `fixtures/northbound-fixture.v1.json`. A language-agnostic recording
   of what the Gateway emits: a snapshot response followed by a stream of frames, including a
   duplicate, an out-of-order frame and a gap frame.
2. **The projection rule** — a deterministic, purely functional algorithm (defined in
   `fixtures/README.md` §3) that maps a fixture to a projected state. No I/O, no wall-clock reads,
   no randomness. This is what makes "the same state" a well-defined claim.
3. **The expected state** — the `expected_state` block of `fixtures/northbound-fixture.v1.json`,
   the output of the projection rule for the recorded fixture, asserted twice: once with Unity
   semantics and once with React semantics. The two sections MUST be equal field-for-field.

The typed bindings (`fixtures/bindings/GatewayAdapter.cs`, `fixtures/bindings/gatewayClient.ts`)
are the two consumer-side implementations of the projection rule over the same fixture. They are
**reference artefacts**: the production Unity adapter lives at
`digital-twin/unity/Assets/Scripts/Adapters/GatewayAdapter.cs` and the production React client at
`dashboard/src/api/websocket.ts` + `dashboard/src/api/gateway.ts`. The later implementation
increment will wire the fixture into the real test suites of both modules.

### 4.2 What the fixture pack contains

| Artefact | Role |
|---|---|
| `fixtures/fixture.schema.json` | Schema for the fixture pack (snapshot + frames + expected state). |
| `fixtures/northbound-fixture.v1.json` | The recorded fixture: snapshot + 7 stream frames covering online, telemetry, command ack, unsynchronised clock, offline, heartbeat, duplicate, out-of-order and gap. Its `expected_state` block holds the two equal expected projections. |
| `fixtures/bindings/GatewayAdapter.cs` | Typed C# projection over the fixture. |
| `fixtures/bindings/gatewayClient.ts` | Typed TypeScript projection over the fixture. |
| `fixtures/README.md` | The projection rule, the parity rule, and how to run the check. |

### 4.3 Parity obligations on the real consumers

These are the obligations the implementation increment must satisfy so that the fixture stays
meaningful:

| Obligation | Unity | React |
|---|---|---|
| State is derived from the **Gateway envelope**, never from a client-side clock or a hard-coded device list. | `digital-twin/.../GatewayAdapter.cs` | `dashboard/src/api/websocket.ts` |
| Device identity uses `device_id` from the envelope. | `CanonicalEvent.device_id` (`Models/CanonicalEvent.cs`) | `CanonicalEvent.device_id` (`dashboard/src/types/gateway.ts`) |
| Stale, offline and unknown are three distinct visual states. | `OnConnectionStatus` / staleness coroutine | `ConnectionStatus` / stale indicator |
| Events are deduplicated on `event_id`. | Required (not implemented today) | Implemented — `seenEventIds` (`websocket.ts`) |
| Events are ordered by `sequence`, and a gap forces a resync. | Required (not implemented today) | Partially — `lastSequence` tracked, no resync |
| REST base URL points at the **HTTP** port (8001), not the WS port (8000). | **Currently wrong** — `restBaseUrl = "http://localhost:8000"` (`GatewayAdapter.cs:22`) | **Currently wrong** — `DEFAULT_HTTP_URL = 'http://localhost:8000'` (`dashboard/src/api/gateway.ts:18`) |

---

## 5. SPEC-5 — Trust boundary, and separation from the broker

### 5.1 Consumers never touch the broker

A consumer of the northbound fanout **MUST NOT** subscribe to MQTT. Rationale, and the current
state of the boundary:

| Broker topic | Publisher today | Consumer subscription |
|---|---|---|
| `smart-factory/+/command/ack` | Bridge → Gateway | **Forbidden.** Gateway only. |
| `smart-factory/+/status` | Bridge → Gateway | **Forbidden.** Gateway only. |
| `smart-factory/+/telemetry` | Bridge → Gateway | **Forbidden.** Gateway only. |
| `smart-factory/+/heartbeat` | Bridge → Gateway | **Forbidden.** Gateway only. |
| `smart-factory/{device_id}/command` | **Gateway only** — `CommandOrchestrator`, topic built at `command_orchestrator.py:222`, published at `command_orchestrator.py:231-234`. **Not wired into the running Gateway** (§7.2-G11). | **Forbidden for every consumer.** |
| `smart-factory/alerts/...` | Gateway alert outbox — `MqttAlertDispatcher`, topic built at `alert_outbox.py:245-251`, published at `alert_outbox.py:265-268`. **Not wired into the running Gateway** (§7.2-G11). | Forbidden for Unity/React; the robot path is governed by `sync-contracts.md` §4. |

The Gateway is the **sole subscriber** of the device topics (`DEFAULT_TOPICS`,
`iot-gateway/src/iot_gateway/config.py:37-42`, subscribed at `gateway.py:166-172`), and the
command and alert topics are published **only** by Gateway-side modules — no consumer-facing
component publishes to them. A consumer that can reach the broker can therefore bypass the
safety gate; that is precisely the boundary the northbound read surface exists to make
unnecessary.

> **Wiring caveat (important):** the two Gateway-side publishers above exist as modules but are
> **not instantiated by the running Gateway** — `gateway.py:33-48` wires only the store, the
> normaliser, the metrics, the WebSocket server and the HTTP app. See §7.2-G11. The trust
> boundary below therefore describes the **architectural** rule ("only the Gateway publishes"),
> which is what this contract binds future implementations to; it is not a description of a
> command path that is live today.

> The MQTT **re-publish** topics listed in `live-state-fanout.md` §1.3
> (`smart-factory/gateway/canon/...`, `smart-factory/gateway/heartbeat`) are **not produced by the
> Gateway today** — see §7.3-G6. They remain a planned internal transport for FIWARE and MUST NOT
> become a consumer-facing surface.

### 5.2 The read domain and the write domain are separate

```
WRITE domain  (command authority)          READ domain  (northbound fanout)
───────────────────────────────            ─────────────────────────────
POST /safety-gate/*                        GET  /health
POST /incidents/{id}/acknowledge           GET  /events
POST /incidents/{id}/resolve               GET  /events/{event_id}
  X-Operator-Token required                GET  /snapshot
  (api.py:28-51; deps at :357, :371,       GET  /metrics
   :387, :401, :442, :455)                 WS   /  (ws://host:8000/)
```

- The write domain requires the `X-Operator-Token` header and compares it with
  `secrets.compare_digest` (`api.py:28-51`). If `SAFETY_OPERATOR_TOKEN` is unset the server
  answers **503** and the write fails closed (`api.py:38-40`).
- The read domain is **currently unauthenticated** — no token on any `GET`, and no token on the
  WebSocket handshake.
- The **only** component permitted to publish a command is the Gateway-side command orchestrator
  (`command_orchestrator.py:197-252`). Unity and React hold **no** command capability: they are
  readers, and their transport is the read surface only.
- The safety invariant is unchanged by this contract: no northbound read, and no northbound write,
  may override a physical interlock or E-stop.
- **Gap (see §7.2-G12):** the command orchestrator does **not** import or call `safety_gate.py`,
  and `SafetyGate.evaluate(...)` has no non-test call site under `iot-gateway/src/`. The
  "gate every command before it is published" property is therefore an **architectural
  requirement of this contract**, not an implemented capability. The northbound read surface
  MUST NOT be treated as a route to that gate either.
- **Gap (see §7.2-G13):** `api.py` also declares device, provisioning and OTA write routes whose
  docstrings state `Requires X-Operator-Token header`, but their handlers carry **no**
  `Depends(_require_operator_token)` dependency. These routes are only registered when a
  registry, provisioning service or OTA manager is injected (`api.py:469`, `:580`, `:685`), which
  the running Gateway does not do (`gateway.py:46`), so they are absent from the default
  deployment — but they must not be described as token-protected if they are ever enabled. This
  contract does not authorise them and does not rely on them.

### 5.3 Read-path trust boundary — what a consumer may assume

| Property | Requirement | State today |
|---|---|---|
| Transport | The read surface MUST be reachable only from the trusted plant network, or behind an authenticating reverse proxy. The Gateway itself MUST NOT terminate TLS for the read surface in this contract. | No TLS in `iot-gateway/` — deployment responsibility. |
| Authentication | v1 keeps the read surface **unauthenticated by design** (a plant-LAN read surface, matching the existing `GET` routes), but MUST record that decision explicitly so it is not mistaken for an oversight. Any deployment that exposes the read surface beyond the plant boundary MUST front it with an authenticating proxy. | Unauthenticated (`api.py:203-332`, `api.py:87-131`). |
| Authorisation | A read consumer may observe **all** canonical events. There is no per-device read authorisation in v1; `device_ids`/`module_ids` filters are **delivery filters, not access controls** and MUST NOT be relied on to hide data. | n/a — v1. |
| Identity of the source | Every event carries a `device_id` that the consumer may display, but the consumer MUST NOT treat it as an authenticated identity. The Gateway authenticates to the broker, not the other way round. | Broker auth is ADR-0010 scope. |
| Write isolation | The read surface MUST NOT expose any write capability to a read consumer. | Satisfied — the read domain (`GET /health`, `/events`, `/events/{id}`, `/snapshot`, `/metrics`, `/`, and the read-only `/safety-gate/*` and `/incidents` views) contains no `POST`/`DELETE`. The write routes live on separate paths and are token-protected (§5.2). |

---

## 6. Implemented versus planned — the ledger

**Nothing in this document may be read as a delivered capability unless it appears in the
"Implemented" column.**

### 6.1 Already implemented in `iot-gateway/` (evidence: file:line)

| # | Capability | Evidence |
|---|---|---|
| I-1 | Raw MQTT → canonical event normalisation, with clock-domain detection | `event_normalizer.py:64`, `:105-132` |
| I-2 | Canonical envelope model and JSON serialisation | `models.py:17`, `models.py:64` |
| I-3 | Durable persistence with bounded retention and pruning | `event_store.py:238`, `:283-302`, `config.py:33` |
| I-4 | `high_watermark` = highest persisted sequence | `event_store.py:379` |
| I-5 | `per_device_latest` — current-state anchor set per device | `event_store.py:390` |
| I-6 | `GET /snapshot` with `since_sequence` cursor, `overflow`, `overflow_limit` | `api.py:233-295` |
| I-7 | `GET /events` with `device_id` / `event_type` / `limit` | `api.py:215-224` |
| I-8 | `GET /events/{event_id}` | `api.py:226-231` |
| I-9 | `GET /health` incl. `queue_dropped_count` | `api.py:203-213` |
| I-10 | `GET /metrics` — latency/jitter/stale/out-of-order aggregates | `api.py:297-323`, `time_sync.py:174` |
| I-11 | WebSocket broadcast server (RFC-6455, `websockets` library), per-client queue | `api.py:59-131`, `gateway.py:45` |
| I-12 | Bounded write queue (500) with drop counter | `gateway.py:32`, `:111-121` |
| I-13 | Broadcast only after successful persistence | `gateway.py:75-79`, `:95-97` |
| I-14 | Operator-token protection on the **safety-gate and incident write routes**, fail-closed when unset. The device / provisioning / OTA write routes are **not** covered — see §7.2-G13. | `api.py:26-51`; deps at `api.py:357`, `:371`, `:387`, `:401`, `:442`, `:455` |
| I-15 | Staleness / out-of-order flags, per-event latency | `event_normalizer.py:134-151`, `models.py:53-58` |

### 6.2 Specified but NOT implemented (planned — **not** a delivered capability)

| # | Planned capability | Where specified | Blocked by |
|---|---|---|---|
| P-1 | `envelope_version`, `units`, `boot_id`, `observed_at`, `quality` on the envelope | §1.3, schema `canonical_event` | Gateway change |
| P-2 | Bounded fanout with an explicit `gap` frame and a defined close code for lagging clients | §2.2, §2.5 | Gateway change |
| P-3 | Server-side subscription filters (`device_ids`, `event_types`) | §2.3 | Gateway change |
| P-4 | Stream resume: `?since_sequence=` on the WebSocket handshake; `Last-Event-ID` on SSE | §2.3, §3.1 | Gateway change |
| P-5 | `boot_id` propagation from the bridge into the canonical envelope | §1.3 | Bridge change |
| P-6 | `module_ids` filter | §2.3 | Issue #169 (device→module map) |
| P-7 | `cursor`, `last_sequence`, `oldest_retained_sequence`, `resync_required` in the snapshot response | §2.4 | Gateway change |
| P-8 | `GET /events?since_sequence=` (the store already supports the filter; the route does not expose it) | §2.1, §2.3 | Gateway change |
| P-9 | SSE endpoint `GET /events/stream` | `live-state-fanout.md` §1.2 | Gateway change |
| P-10 | Wire the fixture pack into the Unity and React test suites | §4 | Consumer change |
| P-11 | Canonical (v2) telemetry payload production inside the Gateway | `telemetry-schema-v2.md` | Gateway change — the Gateway currently stores the raw payload verbatim |
| P-12 | `SafetyGate.evaluate(...)` applied to every command before it is published | §5.2 | Gateway change — the gate exists (`safety_gate.py:114`, `:202`) but has no production call site (G12) |
| P-13 | Wire the command orchestrator and the alert outbox into the running Gateway | §5.1 | Gateway change — both classes exist but are never constructed (G11) |

---

## 7. Discrepancies found while writing this contract

These were found by reading the implementation against the existing draft contracts. They are
recorded here rather than corrected in place, because the other documents are owned by the same
issue but were merged as design drafts (PR #230) and correcting them is a separate change.

### 7.1 Against `live-state-fanout.md` / `sync-contracts.md`

| ID | Existing claim | Reality | Severity |
|---|---|---|---|
| D-1 | WebSocket endpoint shown as `ws://gateway:8765/` (`live-state-fanout.md:43`, `:276`; `sync-contracts.md:31`, `:124`) | The Gateway's WS default is **8000**; 8765 is the AMLP TCP simulator port (`esp32-ukit-bridge/tools/amlp/cli.py:52`). ADR-0011 explicitly fixed this for the dashboard (`docs/adr/adr-0011-dashboard-safety.md:13`). | Documentation defect |
| D-2 | A per-client queue overflow "disconnects the client" (`live-state-fanout.md` §1.1, §6) | The queue is removed from the broadcast set; the connection is **not** closed (`api.py:150-156`). The client stalls silently. | **Behavioural defect** — see G2 |
| D-3 | The Gateway publishes `smart-factory/gateway/canon/...` and `smart-factory/gateway/heartbeat` (`live-state-fanout.md` §1.3) | No such publish exists in `iot-gateway/`. The only Gateway MQTT publish code is in the alert outbox (`alert_outbox.py:265-268`) and the command orchestrator (`command_orchestrator.py:231-234`) — and neither is wired into the running Gateway (G11). | Documentation defect |
| D-4 | The Gateway publishes a 30 s MQTT heartbeat (`live-state-fanout.md` §4.3) | Not implemented. There is no Gateway heartbeat publisher in `iot-gateway/`. | Documentation defect |
| D-5 | `live-state-fanout.md` §3.1 lists `event_timestamp_ms` as a canonical envelope field | The **WebSocket** payload does not carry `event_timestamp_ms` — it carries the `timestamp` alias (`models.py:64-82`). The **REST** payload carries `event_timestamp_ms` and does **not** carry `timestamp` (`event_store.py:337-352`). The two transports disagree on the field set. | **Contract defect** — see G3 |
| D-6 | `live-state-fanout.md` §1.1 "clients that overflow are disconnected silently (no blocking)" | Implies a disconnect that does not happen (D-2). | Documentation defect |
| D-7 | `sync-contracts.md` §1.1 startup: "Subscribe WebSocket for events with sequence > high_watermark" | The WebSocket accepts **no** filter; every client receives every event (`api.py:133-162`). Filtering is client-side only. | Documentation defect |
| D-8 | ADR-0005 names `contracts/v1/schemas/device-event.schema.json` as *the* canonical event envelope (`adr-0005-gateway-canonical-events.md:77`), and `canonical-flows.md:874` lists it as the schema for flows 2 and 4 | That schema is a **cross-system bridge/application-layer** envelope: `timestamp` is an ISO-8601 *string*, its `event_type` vocabulary is `command_acknowledged` / `command_failed` / `telemetry` / `status_change` / `error`, it carries `trace_id` but **no** `event_id`, and it sets `additionalProperties: false`. The Gateway's own canonical envelope is a different shape (`models.py:64-82`): `timestamp` is epoch **milliseconds**, the vocabulary is `command_ack` / `status_online` / `status_offline` / `telemetry` / `heartbeat`, and `event_id` (the dedup key) is present. The two vocabularies do not overlap except on `telemetry`. | **Scope defect** — the v1 schema is a *cross-system* envelope, not the *northbound* one. This contract specifies the northbound wire shape and **does not** claim conformance to `device-event.schema.json`; reconciling the two vocabularies (or formally scoping the v1 schema to the bridge only) is a separate change and is **not** authorised by this document. |

### 7.2 Implementation gaps (the Gateway's own behaviour)

| ID | Gap | Evidence | Impact on this contract |
|---|---|---|---|
| G1 | **The sequence space does not survive a Gateway restart.** The normaliser owns a per-process counter (`event_normalizer.py:56`, `:61-63`) that starts at 1 on every process start, and `insert_dict` prefers the normaliser's value over the persisted counter (`event_store.py:254-257`). The persisted counter (`gateway_metadata.global_sequence`) is only used when the normaliser's value is missing, and `_load_sequence` / `_save_sequence` are never called anywhere in the tree. After a restart, new events carry sequences that **collide** with persisted rows, and `high_watermark` (max sequence) does not advance. | `event_normalizer.py:56-63`, `event_store.py:254-257`, `event_store.py:186-202` (never called) | `sequence` is **not** a safe global identity and **not** a safe cursor across restarts. §3.3 requires the consumer to resynchronise on a detected regression; §6 P-7 covers the cursor additions. |
| G2 | **Lagging WebSocket clients are silently starved, not disconnected.** `broadcast` discards the full queue from the client set (`api.py:150-156`); the handler task keeps waiting on the orphaned queue (`api.py:107-118`). The socket stays open, the client sees no traffic and no error. | `api.py:133-162` | A consumer cannot distinguish "idle" from "dropped". §2.5 requires a `gap` frame and a defined close code (P-2). |
| G3 | **The two read paths expose different envelope field sets.** WebSocket: `timestamp`, `received_at_ms`, `is_timestamp_synchronized`, no `event_timestamp_ms` (`models.py:64-82`). REST: `event_timestamp_ms`, no `timestamp`, no `received_at_ms`, no `is_timestamp_synchronized` (`event_store.py:337-352`). | `models.py:64-82` vs `event_store.py:337-352` | v1 requires **one** envelope on every read path (§2.2). The reconciliation is part of the implementation increment. |
| G4 | **Broadcast order is not sequence order.** Two write workers insert and broadcast concurrently (`gateway.py:31`, `:75-79`, `:95-97`). | `gateway.py:31-101` | §3.2 requires consumers to sort by `sequence` and to detect gaps. |
| G5 | **`GET /snapshot?since_sequence=0` returns the OLDEST `limit` events, not the newest.** `store.query(limit=limit)` orders ascending (`event_store.py:325`) and takes the first `limit` rows. `per_device_latest` carries the current state. | `event_store.py:308-351`, `api.py:274-277` | The current state is `per_device_latest`; `events[]` is history. The v1 contract must say so unambiguously (§3.1) — the current docstring in `api.py` is ambiguous on this point. |
| G6 | **The MQTT re-publish and Gateway heartbeat described in `live-state-fanout.md` §1.3 / §4.3 do not exist.** | `iot-gateway/src/iot_gateway/` — only `alert_outbox.py:265-268` and `command_orchestrator.py:231-234` contain publish code, and neither is wired (G11) | They are planned internal transports, never consumer-facing (§5.1). |
| G7 | **`GET /snapshot` `overflow` is computed against the whole store, not the requested window.** `overflow = total > limit` (`api.py:271`), where `total` is the count of all retained events, regardless of `since_sequence`. A consumer resuming with a small `since_sequence` can be told `overflow: true` although its window is complete. | `api.py:269-271`, `event_store.py:421-424` | v1 replaces the flag with `resync_required` + `oldest_retained_sequence` (P-7). |
| G8 | **`GET /events` exposes no `since_sequence`**, although `EventStore.query` supports it (`event_store.py:313`). | `api.py:215-224` vs `event_store.py:308-313` | P-8. |
| G9 | **The consumer clients point their REST base URL at the WebSocket port.** The Gateway serves HTTP on `ws_http_port` (default 8001) and WS on `ws_port` (default 8000). Unity uses `restBaseUrl = "http://localhost:8000"` (`GatewayAdapter.cs:22`); React uses `DEFAULT_HTTP_URL = 'http://localhost:8000'` (`dashboard/src/api/gateway.ts:18`), while React's WS default `ws://localhost:8000` is correct. | `config.py:21-32`, `gateway.py:176-190` | §4.3 records the obligation; fixing it belongs to the consumer increment. |
| G10 | **The read surface is unauthenticated** and the WebSocket handshake accepts any path with no query parsing. | `api.py:87-131`, `api.py:203-332` | §5.3 states the boundary explicitly rather than leaving it implied. |
| G11 | **The Gateway-side command and alert publishers are not wired into the running Gateway.** `CommandOrchestrator` (`command_orchestrator.py:255`), `MqttCommandExecutor` (`command_orchestrator.py:197`), `AlertOutbox` (`alert_outbox.py:289`) and `MqttAlertDispatcher` (`alert_outbox.py:219`) exist as classes, but none is constructed anywhere under `iot-gateway/src/`; `gateway.py:33-48` wires only the store, normaliser, metrics, WebSocket server and HTTP app, and `gateway.py` imports neither module. `AlertService` in `alerts.py:147` is likewise unimported by the rest of the package. | `gateway.py:33-48`; no construction site for `CommandOrchestrator(`, `AlertOutbox(`, `MqttCommandExecutor(`, `MqttAlertDispatcher(` under `iot-gateway/src/` | There is **no live command publish path and no live alert publish path** in the Gateway today. §5.1 records the architectural rule ("only the Gateway publishes") that this contract binds future implementations to, and §5.2 states explicitly that it is not a description of a running command path. |
| G12 | **`SafetyGate.evaluate(...)` is never called from production code.** The gate implementation exists (`safety_gate.py:114`, `evaluate` at `safety_gate.py:202`) and is exercised by tests, but there is no non-test call site under `iot-gateway/src/`, and `command_orchestrator.py` does not import `safety_gate` at all (`command_orchestrator.py:18-39`). The safety rules in `SafetyRuleConfig` (`safety_gate.py:88`) are therefore not applied on any command path. | `safety_gate.py:114`, `:202`; no non-test `.evaluate(` call site under `iot-gateway/src/`; `command_orchestrator.py:18-39` imports do not include `safety_gate` | "Gate every command before publishing" is an **architectural requirement of this contract (§5.2)**, not an implemented capability. It is listed as planned (P-12) and MUST NOT be described as a live protection. |
| G13 | **Several write routes declare an operator-token requirement in their docstrings but do not enforce one.** The device, provisioning and OTA handlers under `api.py:469-829` state `Requires X-Operator-Token header`, yet carry no `Depends(_require_operator_token)` dependency. Only six handlers enforce the token: the four `/safety-gate/*` writes (`api.py:357`, `:371`, `:387`, `:401`) and the two `/incidents/{id}` writes (`api.py:442`, `:455`). There is no global middleware or app-level dependency enforcing the token. | `api.py:469-829` (no token dependency) vs `api.py:357`, `:371`, `:387`, `:401`, `:442`, `:455` (token dependency) | These routes are absent from the default deployment because the running Gateway injects neither a registry, a provisioning service nor an OTA manager (`api.py:469`, `:580`, `:685`; `gateway.py:46`). If they are ever enabled, they must be brought under the same token boundary before being described as protected. This contract neither authorises nor relies on them. |

### 7.3 What this means for the implementation increment

The implementation card must, at minimum: reconcile G3 into one envelope across both read paths
(P-1); fix or document G1's sequence behaviour before the cursor contract can be honoured (P-7);
close G2 with a `gap` frame and a close code (P-2); expose the cursor additions on `/snapshot`
(P-7) and `since_sequence` on `/events` (P-8); and wire the fixture pack into both consumer test
suites (P-10).

Separately, and **outside** the northbound read scope of this contract, the Gateway still owes
itself: a wired command path (P-13/G11), a safety gate applied on that path (P-12/G12), and
operator-token enforcement on the device, provisioning and OTA write routes if they are ever
enabled (G13). This contract records them so that no downstream document mistakes them for
delivered capabilities.

---

## 8. L0 validation checklist

- [x] Every route in §2.1 traced to a handler line in `iot-gateway/src/iot_gateway/api.py`.
- [x] Every WebSocket behaviour traced to `api.py:59-168` / `gateway.py:45-101`.
- [x] Every store guarantee (high-watermark, `per_device_latest`, retention, cursor) traced to `event_store.py`.
- [x] Clock-domain handling traced to `event_normalizer.py:105-151` and `models.py:53-58`.
- [x] `northbound-fanout.schema.json` is valid JSON and covers envelope, snapshot, frame, filter and error shapes.
- [x] `units`, `boot_id`, `observed_at`, `quality` are each tied to a defined semantic, not just a name.
- [x] Every implemented capability carries a `file:line` reference (§6.1).
- [x] Every non-implemented capability is labelled planned (§6.2) — no specification is presented as delivered.
- [x] The fixture pack is language-agnostic, schema-documented, and produces one expected state for two consumers.
- [x] The fixture pack is executable: `contracts/gateway/fixtures/validate_fixtures.py` validates the pack against `fixture.schema.json` and against this contract's `canonical_event` definition, asserts `expected_state.unity == expected_state.react`, and re-runs the TypeScript projection to confirm it reproduces `expected_state.react` (all four checks pass locally).
- [x] The C# reference binding reproduces `expected_state.unity` exactly (`dotnet run --project contracts/gateway/fixtures/bindings/csharp/GatewayFixtureParity.csproj -- contracts/gateway/fixtures/northbound-fixture.v1.json` → `C# parity: PASS`). The same recording therefore yields the same projected state in both languages.
- [x] The broker boundary and the read/write domain separation are stated normatively (§5).
- [x] The command/control path and the safety gate are described by their **actual** wiring state, not by the presence of a class: the command orchestrator, the MQTT executors and the alert outbox are recorded as unwired (G11), and `SafetyGate.evaluate(...)` as having no production call site (G12).
- [x] Operator-token enforcement is stated per route: six handlers enforce it, the device/provisioning/OTA routes do not despite their docstrings (G13).
- [x] Every divergence from the existing draft contracts is recorded rather than silently corrected (§7).
- [x] The contract does not duplicate or contradict an existing schema: `contracts/v1/schemas/device-event.schema.json` (ADR-0005) is referenced as the cross-system envelope and the divergence from the northbound envelope is recorded as D-8; `contracts/v2/schemas/telemetry.schema.json` is referenced for the telemetry `payload` body only.
- [ ] Fixture wired into the Unity and React test suites — **planned** (P-10).
- [ ] Envelope v1 emitted by the Gateway — **planned** (P-1).
- [ ] Safety gate applied on the command path — **planned** (P-12).
- [ ] Command orchestrator and alert outbox wired into the running Gateway — **planned** (P-13).

**Evidence ceiling:** L0. This document is a static contract. It contains no deployed,
integration or hardware-in-the-loop evidence, and asserts none. The fixture pack is a
**hand-authored recording** derived from the Gateway source, not a capture from a running
deployment; it proves consumer-parity of the projection, not that the Gateway currently
emits these bytes.
