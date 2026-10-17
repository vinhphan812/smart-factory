# Issue #43 — End-to-End Latency, Jitter and Event Loss Measurement Plan

**Author:** agent  
**Reviewer:** vinhphan812  
**Status:** draft  
**Evidence level:** L2–L4  
**Branch:** `feat/issue-43-latency-measurement`  
**Related ADR:** ADR-0005 (Gateway Canonical Event Envelope)  
**Sister plan:** docs/issue-44-integration-test-plan.md  

---

## 1. Purpose and scope

This plan defines how to measure, report and evaluate three scientific KPIs for the Smart Factory pipeline:

1. **End-to-end latency** — time from device emission to consumer-visible update
2. **Jitter** — variance of inter-arrival latency (network/system instability)
3. **Event loss** — fraction of events sent by the bridge that never reach the event store

It covers ESP32 bridge → MQTT broker → IoT gateway → WebSocket broadcast → Unity/Digital Twin consumer. The plan is **L2-first**; L3/L4 criteria are listed but gated by hardware availability.

---

## 2. Measurement definitions

### 2.1 Canonical timestamp chain

```
device_timestamp_ms          ← ESP32 RTC at event emission (UTC epoch ms)
mqtt_received_at_ms           ← gateway time when MQTT message is received (monotonic UTC)
canonical_received_at         ← ISO 8601 UTC string (same instant, stored in envelope)
canonical_event_id            ← UUID v4 (per ADR-0005, deduplication key)
canonical_sequence            ← monotonically incrementing integer per device (store ordering)
```

Derived values (computed at capture time, not stored in envelope):

```
observed_latency_ms = mqtt_received_at_ms - device_timestamp_ms
```

> `observed_latency_ms` may be negative if the ESP32 clock is ahead of the gateway clock. Raw values are recorded; clamping is applied only at the visualisation layer.

### 2.2 Latency segments (for root-cause attribution)

| Segment | Definition | Observable from |
|---------|-----------|-----------------|
| UART→ESP32 process | AMLP frame parsed to internal state | ESP32 serial log |
| ESP32→broker | `device_timestamp_ms` to MQTT `PUBLISH` acked | Broker QoS log or instrumented mock |
| Broker→gateway | MQTT `PUBLISH` to `mqtt_received_at_ms` | Gateway log with timestamp |
| Gateway ingest | `mqtt_received_at_ms` to `canonical_received_at` | `time_sync.py` `TimeMetrics.observe()` |
| Gateway→consumer | `canonical_received_at` to WS frame transmitted | Gateway WS broadcast log |
| Consumer render | WS frame to Unity/Twin display update | Consumer-side instrumentation |

> **Segment 5 (Gateway→consumer)** requires instrumentation in the WS broadcast path. This is **NOT yet implemented** — see §6.

### 2.3 Jitter definition

```
jitter_ms = | observed_latency_ms[n] - observed_latency_ms[n-1] |
```

Computed per device from consecutive events with valid latency (>= 0, `is_timestamp_synchronized=True`). Reported as per-device mean jitter and per-run distribution (p50/p95/p99 of jitter values).

### 2.4 Event loss definition

```
loss_rate = 1 - (msg_count_stored / msg_count_sent)
```

- `msg_count_sent` = events published to the MQTT broker during the measurement window
- `msg_count_stored` = events persisted in the SQLite event store with matching `device_id` prefix
- Loss caused by MQTT QoS-0 drops, gateway write-queue overflow, quarantine rejection, or duplicate deduplication is counted identically

> Events with duplicate `event_id` are **not** counted as loss — they are counted in a separate `duplicate_rate` metric per §3.3.

---

## 3. Methodology

### 3.1 L2 measurement harness (simulated MQTT)

```
[Simulator] --MQTT--> [mosquitto or mock broker] ---> [IoT Gateway]
                                                              |
                                                   +----------+---------+
                                              [SQLite store]  [WS broadcast]
                                                   |
                                              [capture script]
```

1. The simulator injects `N` events at a configurable rate (`--rate msgs/s`) with `device_timestamp_ms` set to the simulator's wall-clock epoch ms.
2. The capture script simultaneously:
   - Subscribes to the MQTT broker and records `mqtt_received_at_ms` for each message.
   - Polls the SQLite store at regular intervals to collect persisted `event_id` and `device_id` records.
3. After the run window closes, the capture script computes latency, jitter and loss from the aligned dataset.

**Test parameters (L2 required):**

| Parameter | Value |
|-----------|-------|
| Run duration | ≥ 300 s continuous |
| Event rate | 1 msg/s (steady) and 10 msg/s (burst, 1 s burst every 10 s) |
| Events per run | ≥ 300 steady; ≥ 600 burst |
| Broker | mosquitto on localhost or equivalent mock |
| Gateway config | default (queue capacity 500, retention 100) |

### 3.2 Computing p50 / p95 / p99 latency

Raw latency values (valid only — excludes `latency < 0` and unsynced events) are collected in a list. After the run:

```python
sorted_latencies = sorted(raw_latency_list)
p50 = sorted_latencies[int(len(sorted_latencies) * 0.50)]
p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
max  = sorted_latencies[-1]
```

The same method applies to jitter values.

### 3.3 Duplicate rate

```
duplicate_rate = count(event_id seen before) / msg_count_stored
```

`TimeMetrics.snapshot()` does not currently expose `duplicate_rate`. This metric must be added — see §6.

---

## 4. Pass / fail criteria per run manifest

Criteria are set **per run** by the reviewer after observing raw numbers. The plan mandates raw distributions are published; it does not pre-define pass thresholds. Reviewers assess against:

| Criterion | Requirement |
|-----------|-------------|
| Raw distribution published | Yes — all percentiles, min, max per device |
| `loss_rate` plausible | ≤ configured queue overflow or broker drop rate |
| `duplicate_rate` bounded | No more than 1 duplicate per 10 000 events |
| `unsynchronized_event_count` disclosed | Events with `is_timestamp_synchronized=False` must not be silently excluded |
| No fabricated events | Store sequence gaps must not be back-filled |
| Gateway stayed alive | No crash or unhandled exception in logs |

**Do not pre-declare a run as PASS.** The reviewer marks `criteria_pass: true/false` in the run manifest after reviewing evidence.

---

## 5. Per-run reporting template

```yaml
run_id: "<uuid>"
commit: "<git SHA of iot-gateway at run time>"
firmware_version: "<ESP32 firmware tag or 'L2 simulator'>"
start_iso: "<ISO 8601 UTC>"
end_iso: "<ISO 8601 UTC>"
level: "L2"  # L2 | L3 | L4
broker: "<broker type + version>"
gateway: "<Python version + commit>"
test_mode: "steady | burst"
results:
  latency_p50_ms: <float>
  latency_p95_ms: <float>
  latency_p99_ms: <float>
  latency_max_ms: <float>
  latency_min_ms: <float>
  jitter_p50_ms:  <float>
  jitter_p95_ms:  <float>
  jitter_p99_ms:  <float>
  loss_rate:      <float 0-1>
  duplicate_rate:  <float 0-1>
  stale_event_count:    <int>
  unsynchronized_event_count: <int>
  out_of_order_event_count:   <int>
  reconnect_time_ms: <float or null>
  msg_sent:    <int>
  msg_stored:  <int>
  run_duration_s: <float>
criteria_pass: null  # set by reviewer
notes: "<reviewer notes>"
```

---

## 6. What is NOT yet implemented

| Gap | File / Location | Status | Tracker |
|-----|----------------|--------|---------|
| WS broadcast timestamp instrumentation | `iot-gateway/src/iot_gateway/ws_handler.py` or equivalent | **NOT IMPLEMENTED** | Issue #43 |
| `duplicate_rate` in `TimeMetrics.snapshot()` | `iot-gateway/src/iot_gateway/time_sync.py` | **NOT IMPLEMENTED** | Issue #43 |
| `canonical_sequence` population | `iot-gateway/src/iot_gateway/event_store.py` | **NOT IMPLEMENTED** | Issue #31 |
| Latency capture script | `iot-gateway/scripts/capture_latency.py` | **NOT IMPLEMENTED** | Issue #43 |
| Snapshot table (retained MQTT status) | SQLite event store | **NOT IMPLEMENTED** | Issue #31 |
| Normaliser wired to device registry | `iot-gateway/src/iot_gateway/event_normalizer.py` | Not wired | Issue #32 |
| L3/L4 hardware environment | Physical ESP32 + bench | **BLOCKED** | — |

Until WS broadcast instrumentation is added, end-to-end latency is measured only to the **gateway ingest point** (`mqtt_received_at_ms` — the current `observed_latency_ms` definition in `time_sync.py`). The segment gateway→Unity/Twin is **out of scope for initial L2** but documented above for future work.

---

## 7. Relationship to Issue #44 (Integration Test Plan)

Issue #44 defines the integration test suite for the same pipeline. This plan (#43) provides the **observability layer** that #44's latency tests depend on:

| #44 Section | #43 Input |
|------------|-----------|
| §4 Soak test | `loss_rate`, `duplicate_rate`, `stale_event_count` from run manifest |
| §5.1 Broker disconnect | `reconnect_time_ms` from run manifest |
| §5.2 Message loss | `loss_rate` metric; FI-05 injects drops for direct verification |
| §5.3 Message reorder | `out_of_order_event_count` from `TimeMetrics` |
| §6 Latency | Full p50/p95/p99 distribution; jitter; per-device breakdown |
| §6.3 Per-run template | Identical YAML template (shared format) |

This plan (#43) provides the **methodology and instrumented measurement**; #44 provides the **test scenarios and execution topology**. Both plans share the same pass/fail review workflow and evidence requirements.

---

## 8. Relationship to ADR-0005

ADR-0005 defines the canonical event envelope fields that are the **basis for all measurement timestamps**:

| ADR-0005 field | Used in #43 measurement |
|----------------|------------------------|
| `event_id` (UUID v4) | Deduplication; `duplicate_rate` |
| `timestamp` | `device_timestamp_ms` source |
| `received_at` | `canonical_received_at` — the authoritative ingest instant |
| `payload` | Not used in latency computation |
| `trace_id` | Optional correlation; not required for latency |

ADR-0005's requirement that `received_at` uses a monotonicity-guaranteed gateway clock aligns with `time_sync.py`'s `utc_now()`. ADR-0005's reference to a **snapshot table** for retained MQTT status is unresolved in the current implementation (Issue #31 gap) — this does not block L2 latency measurement.

---

## 9. Execution commands (L2)

```bash
# Start mosquitto (or mock broker)
mosquitto -p 1883

# Start gateway
cd iot-gateway
python -m uvicorn iot_gateway.main:app --host 0.0.0.0

# Run L2 latency capture (requires capture script — NOT YET IMPLEMENTED, see §6)
python scripts/capture_latency.py \
  --run-id "$(uuidgen)" \
  --duration 300 \
  --rate 1 \
  --level L2 \
  --output results/run_l2_steady.yaml

# Burst run
python scripts/capture_latency.py \
  --run-id "$(uuidgen)" \
  --duration 300 \
  --rate 10 \
  --burst-on 1 \
  --burst-every 10 \
  --level L2 \
  --output results/run_l2_burst.yaml
```

---

## 10. Evidence requirements

For every test run the following must be attached to the PR or linked issue:

1. Run manifest YAML (per §5) — required for all levels
2. Gateway log excerpt (startup to shutdown) — required for all levels
3. SQLite dump of stored events — required for all levels
4. Raw latency/jitter value lists (CSV or JSON) — required for L2
5. Broker QoS log / Wireshark capture — required for L3/L4
6. Hardware pre-check sign-off — required for L3/L4

**Do not claim a run as PASS without evidence attached.** Reviewer sets `criteria_pass` in the manifest after reviewing raw numbers.

---

## 11. Open issues and risks

| ID | Description | Impact | Mitigation |
|----|-------------|--------|------------|
| RISK-01 | WS broadcast segment not instrumented — end-to-end only measured to gateway ingest | Incomplete latency picture for consumer-facing latency | Document in §6; instrument before L3 |
| RISK-02 | `duplicate_rate` not in `TimeMetrics` — cannot report without code change | Duplicate events not measured | Implement per §6 gap list |
| RISK-03 | ESP32 telemetry→MQTT not confirmed end-to-end (RISK-02 in #44) | Simulator may not reflect real timing | Use simulator for L2; track hardware gap in Issue #66 |
| RISK-04 | L3/L4 hardware tests blocked until physical subsystem available | Cannot run hardware-level latency tests | Mark BLOCKED; use L2 for initial measurement |
| RISK-05 | ADR-0005 snapshot table missing — retained MQTT status snapshot not available | Short-term state snapshot not queryable | Track in Issue #31; not a blocker for latency measurement |
