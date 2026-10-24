# Gateway Northbound Consumer Fixture Pack

Language-agnostic recorded fixture for the Gateway northbound read surface, plus the
deterministic **projection rule** that turns it into consumer visual/status state.

Owner contract: [`../northbound-fanout-contract.md`](../northbound-fanout-contract.md) §4
(SPEC-4). Wire shapes: [`../northbound-fanout.schema.json`](../northbound-fanout.schema.json).
Pack schema: [`fixture.schema.json`](./fixture.schema.json).

Status: **Specification**. Evidence level: **L0 (contract / static)** — the recording is
hand-authored from the Gateway source, not captured from a running deployment.

---

## 1. Contents

| File | Role |
|---|---|
| `fixture.schema.json` | JSON Schema (draft-07) for the pack: snapshot + frames + expected state. |
| `northbound-fixture.v1.json` | The recording. `snapshot` is a `GET /snapshot` response body; `frames` is the ordered `WebSocket` frame sequence; `expected_state` holds the two equal expected projections. |
| `bindings/gatewayClient.ts` | Reference TypeScript implementation of the projection rule (§3). |
| `bindings/GatewayAdapter.cs` | Reference C# implementation of the projection rule (§3). |
| `bindings/csharp/` | `GatewayFixtureParity.csproj` + `Program.cs` — compiles `GatewayAdapter.cs`, projects the recording and asserts the result equals `expected_state.unity`. |
| `validate_fixtures.py` | Validates the pack against the schema, asserts `expected_state.unity == expected_state.react`, and re-runs the TypeScript projection to check it reproduces `expected_state.react`. |
| `bindings/projection_cli.ts` | Prints the TypeScript projection of a pack as JSON; used by `validate_fixtures.py`. |

The bindings are **reference artefacts**. Production clients live in
`digital-twin/unity/Assets/Scripts/Adapters/GatewayAdapter.cs` and
`dashboard/src/api/websocket.ts`; the implementation increment wires this pack into their
real test suites.

---

## 2. What the recording exercises

The recording is one **authorised snapshot at cursor 44** followed by **seven stream frames**.

| # | Frame | Sequence | Exercises |
|---|---|---|---|
| snapshot | 7 events | 38–44 | `status_online`, `telemetry` (UTC clock), `command_ack`, `status_offline` not yet seen, a stale/degraded `telemetry`, `per_device_latest` map. |
| 1 | `event` | 45 | Incremental telemetry for `conveyor-a`. |
| 2 | `event` | 46 | `status_offline` for `sorting-1` — device explicitly offline. |
| 3 | `event` | 46 (repeat) | **Exact duplicate** — same `event_id`, same payload. Must be dropped by `event_id`. |
| 4 | `event` | 48 | Telemetry for `press-1` in the **device-monotonic clock domain** — `observed_at` is `null`, `quality.clock_domain = "device_monotonic"`, `quality.status = "uncertain"`. |
| 5 | `event` | 47 | **Out-of-order delivery** — sequence 47 arrives after 48. |
| 6 | `gap` | 49–52 | **Gap** — `reason: "slow_consumer"`. Forces a resync. |
| 7 | `heartbeat` | — | Liveness frame carrying `high_watermark: 52` and `gateway_time`. |

Four devices are covered: `conveyor-a` (online / live), `sorting-1` (offline / live),
`press-1` (unknown connectivity / uncertain data), `weld-1` (unknown connectivity / stale data).

---

## 3. The projection rule (normative)

The rule is **purely functional**: given the pack, it returns the projected state. No I/O, no
wall-clock reads, no randomness, no dependence on the host language's dictionary iteration order
beyond the explicit sort in step 3.

### 3.1 Step 1 — collect candidate events

Candidates are, in this order:

1. every event in `snapshot.events`;
2. every `event` frame's `event`, in `frames` delivery order.

Each candidate carries its **delivery index** (0-based, over the combined list).

### 3.2 Step 2 — deduplicate by `event_id`

Walk the candidates in delivery order. If an `event_id` has already been seen, the candidate is
**dropped** and its `event_id` is appended to `dropped_duplicate_event_ids` (delivery order). The
first occurrence wins. `event_id` is the Gateway's idempotency key (ADR-0005).

### 3.3 Step 3 — order by `sequence`

Sort the surviving candidates by `sequence` ascending; ties keep delivery order (stable sort).
Applied to this recording the surviving events apply in sequence order 38, 39, 40, 41, 42, 43,
44, 45, 46, 47, 48 — frame 5 (sequence 47) is applied **after** frame 4 (sequence 48) was
received, which is what "out-of-order delivery" means on the wire.

`applied_event_ids` is the list of `event_id`s in the order they were applied.
`last_applied_sequence` is the `sequence` of the last applied event.

### 3.4 Step 4 — project per device

For each applied event, keyed by `device_id`:

**Event fields** — taken from the applied event of *any* type:

| Field | Source |
|---|---|
| `last_event_type` | `event_type` |
| `last_sequence` | `sequence` |
| `last_event_id` | `event_id` |
| `boot_id` | `boot_id` |
| `received_at` | `received_at` |

**Observation fields** — taken from the latest applied **`telemetry`** event for that device.
A `status_*`, `command_ack` or `heartbeat` event never overwrites them.

| Field | Source |
|---|---|
| `observed_at` | `observed_at` (may be `null` when the clock domain is not UTC) |
| `clock_domain` | `quality.clock_domain` |
| `quality_status` | `quality.status` |
| `quality_reason` | `quality.reason` |
| `units` | `units` (copied verbatim) |
| `values` | derived from `payload.structured`, see §3.5 |
| `payload_state` | `payload.structured.state`, else `null` |

**Connectivity** — a separate axis from data freshness:

| `connectivity` | Condition |
|---|---|
| `online` | the latest applied `status_*` event for the device is `status_online` |
| `offline` | the latest applied `status_*` event for the device is `status_offline` |
| `unknown` | the device has no applied `status_*` event at all |

**Data freshness** — also separate from connectivity:

| `data_state` | Condition (on the latest applied `telemetry` event) |
|---|---|
| `live` | `quality.status == "good"` and `quality.stale == false` |
| `stale` | `quality.status == "degraded"` **or** `quality.stale == true` |
| `uncertain` | `quality.status == "uncertain"` (e.g. unsynchronised clock domain) |
| `unknown` | the device has no applied `telemetry` event at all |

Connectivity and data freshness are independent on purpose: `weld-1` is *unknown* connectivity
with *stale* data, and `press-1` is *unknown* connectivity with *uncertain* data. Neither may be
rendered as "live".

### 3.5 Step 5 — derive `values`

Read `payload.structured` of the latest applied `telemetry` event. If it is absent, `values` is
`{}` and `payload_state` is `null`.

| `values` key | Source | Present when the `units` map declares it |
|---|---|---|
| `state` | `payload.structured.state` | — (`payload_state` mirrors it) |
| `speed` | `payload.structured.speed` | `speed` |
| `temperature` | `payload.structured.sensors.temperature_centi_c` | `temperature` |
| `humidity` | `payload.structured.sensors.humidity_centi_percent` | `humidity` |

The sensor-key → measurement-name mapping is fixed by this table. `payload.raw` is ignored by the
projection; the Gateway has already normalised the body.

### 3.6 Step 6 — gap and resync

A `gap` frame sets `gap_detected = true` and `resync_required = true`. It does **not** change
`last_applied_sequence`. The `heartbeat` frame is liveness only and changes nothing.

---

## 4. The parity rule

> The **same** recording MUST produce the **same** projected state in the Unity C# consumer and
> the React/TypeScript consumer.

Concretely:

1. `expected_state.unity` and `expected_state.react` are the same content. The only permitted
   difference is the `consumer` label (`"unity"` / `"react"`).
2. Each binding's projection of the recording MUST equal its section of `expected_state`.
3. Any change to the recording that changes the projection MUST change both sections.

`validate_fixtures.py` checks (1) and (2) for the TypeScript binding, and asserts the pack
validates against `fixture.schema.json`.

---

## 5. Running the checks

From the repository root:

```bash
python contracts/gateway/fixtures/validate_fixtures.py
```

The script:

1. validates `northbound-fixture.v1.json` against `fixture.schema.json`;
2. validates every `canonical_event` in the pack against
   `../northbound-fanout.schema.json#/definitions/canonical_event`;
3. asserts `expected_state.unity == expected_state.react` apart from the `consumer` label;
4. runs the TypeScript projection (`bindings/gatewayClient.ts`) and asserts it equals
   `expected_state.react`.

`node` (≥ 22, TypeScript type-stripping) is required for step 4. `jsonschema` (Python) is
required for steps 1–2.

The C# side of the parity rule is checked by the harness in `bindings/csharp/`:

```bash
dotnet run --project contracts/gateway/fixtures/bindings/csharp/GatewayFixtureParity.csproj \
  -- contracts/gateway/fixtures/northbound-fixture.v1.json
```

It prints `C# parity: PASS` and exits 0 when the C# projection equals
`expected_state.unity`. Both checks run in CI (`.github/workflows/contracts-ci.yml`).

---

## 6. Extending the pack

* Bump `fixture_version` (semver) for any change to the pack shape.
* Add new cases as new frames at the end, and extend `expected_state` in both sections.
* Keep the recording internally consistent: `sequence` values are unique per applied event
  except for the deliberate duplicate frame, `received_at`/`ingested_at` are ISO-8601 UTC, and
  `received_at_ms` is the epoch-millisecond form of `received_at`.
* Never add a field to one consumer's projection and not the other's. If a consumer genuinely
  needs an extra field, it belongs in the consumer's own view model, not in `expected_state`.
