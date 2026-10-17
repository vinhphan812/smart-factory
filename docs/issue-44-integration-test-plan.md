# Issue #44 — Integration Test Plan

**Author:** agent  
**Reviewer:** vinhphan812  
**Status:** draft  
**Evidence level:** L0–L4  
**Branch:** `feat/issues-44-45-test-plans`

---

## 1. Purpose and scope

This plan covers end-to-end integration tests for the Smart Factory system:
**ESP32 bridge → MQTT broker → IoT gateway → event store → WebSocket clients (dashboard, Digital Twin)**.

It addresses:
- Soak/stress testing under sustained load
- Network fault injection (broker disconnect, reconnect, packet loss, message reordering)
- Sync-latency measurement and publication
- A simulator vs hardware execution matrix
- Explicit pass/fail criteria per scenario

Hardware tests (L3/L4) are gated by the pre-check requirements in `docs/testing-and-acceptance.md`. Blocked hardware requirements are marked **BLOCKED** and must not be claimed as PASS.

---

## 2. Evidence level definitions (from `docs/testing-and-acceptance.md`)

| Level | Environment |
|-------|-------------|
| L0 | static / schema review |
| L1 | Python / C99 host unit |
| L2 | simulated UART/MQTT, mock device |
| L3 | ESP32 + real controller on bench |
| L4 | actual moving 9-module subsystem with operator / E-stop |
| L5 | integrated factory → gateway → Unity → MiniAlpha |

---

## 3. System under test topology

```
[ESP32 UKIT Bridge] --MQTT JSON--> [MQTT Broker] ---> [IoT Gateway]
                                                           |
                                          +----------------+-----------------+
                                          |                |                 |
                                    [Event Store]    [WS Broadcast]    [Alert Service]
                                         SQLite           |
                                     (SQLite/JSON)        +---> [Dashboard]
                                                        +---> [Digital Twin]
                                                        +---> [MiniAlpha Edge]
```

**Key observables for integration testing:**
- MQTT topic matches `smart-factory/<device_id>/<event_type>`
- Canonical event envelope fields: `event_id`, `device_id`, `event_type`, `payload`, `mqtt_topic`, `mqtt_timestamp_ms`, `ingested_at`, `sequence`
- Gateway is read-only; it never publishes MQTT commands
- Store persists all events accepted before shutdown signal

---

## 4. Soak test

### 4.1 Objective
Verify the gateway sustains continuous event throughput over extended runtime without memory growth, queue overflow, or silent event loss.

### 4.2 Environment
L2 — simulated MQTT broker (e.g. `testcontainers/python` with mosquitto or a mock broker), gateway in-process or containerised, SQLite ephemeral store.

### 4.3 Test scenarios

| ID | Scenario | Rate | Duration |
|----|----------|------|----------|
| ST-01 | Normal continuous telemetry stream | 1 msg/s | 1 hour |
| ST-02 | Bursty command ACK stream | 10 msg/s burst, 1 s every 10 s | 30 min |
| ST-03 | Mixed telemetry + status + heartbeat | 5 msg/s combined | 2 hours |
| ST-04 | Soak + concurrent WS client connections (dashboard + twin) | 5 msg/s | 30 min |

### 4.4 Pass/fail criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Gateway RSS at T=0 vs T=end | Δ < 10 % | Δ ≥ 10 % |
| SQLite DB row count vs expected | 100 % received | < 100 % |
| WS broadcast delivery to all connected clients | all received | any dropped |
| Write queue overflow events (logged) | 0 | ≥ 1 |
| Gateway process alive | yes | crashed |
| No unhandled exception in logs | yes | any traceback |

---

## 5. Network fault injection

### 5.1 Broker disconnect

| ID | Scenario | Precondition | Inject | Expected |
|----|----------|-------------|--------|----------|
| FI-01 | Clean disconnect | Gateway connected, steady telemetry | `pkill mosquitto` or mock `disconnect()` | Gateway detects disconnect within 30 s; no unsafe queued execution; WS clients receive stale indicator |
| FI-02 | Broker unreachable at startup | Gateway starts, broker down | Block port 1883 via firewall rule | Gateway retries with backoff; emits warning; does not crash |
| FI-03 | Reconnect after clean disconnect | FI-01 state | Restart broker | Gateway re-subscribes; snapshot resync from store; no duplicate events injected |
| FI-04 | Reconnect with missed messages | Broker down 60 s, events queued | Broker up | Gateway re-subscribes; events published after disconnect are **not** recovered (at-most-once MQTT); store reflects gap |

### 5.2 Message loss

| ID | Scenario | Precondition | Inject | Expected |
|----|----------|-------------|--------|----------|
| FI-05 | Random MQTT QoS 0 drop | Steady stream | Mock broker drops 5 % of messages | Store receives ≤ 95 % of sent; no crash; no false "complete" state inferred |
| FI-06 | Sustained 30 s loss | Steady stream | Block inbound port for 30 s | Gateway continues running; events in the gap are absent from store; no fabricated data |

### 5.3 Message reorder

| ID | Scenario | Precondition | Inject | Expected |
|----|----------|-------------|--------|----------|
| FI-07 | Out-of-order delivery | Two events A then B sent | Deliver B then A | Store sequence numbers preserve ingestion order; `mqtt_timestamp_ms` reflects send time; query by `sequence` returns consistent ordering |
| FI-08 | Twin state monotonicity (E07) | Out-of-order events | Delayed B arrives after A | Twin state does **not** roll backward; the higher `mqtt_timestamp_ms` wins for display |

### 5.4 Pass/fail criteria (all FI-*)

| Criterion | Pass | Fail |
|-----------|------|------|
| Gateway stays alive | yes | crash / unhandled exception |
| No unsafe command execution | none observed | any command executed after disconnect |
| Events not fabricated to fill gaps | no | any missing range filled |
| Store query ordering consistent | ascending sequence | gaps / non-deterministic order |
| WS clients receive valid events only | yes | malformed / duplicate events leaked |

---

## 6. Latency measurement

### 6.1 Definitions

```
device_timestamp  = timestamp embedded in MQTT payload (ms since epoch, from ESP32 RTC)
mqtt_publish_time = time broker received message (from broker metadata or injected metadata)
ingested_at       = gateway ingestion time (ISO 8601 UTC, derived from time.time())
```

```
observed_latency_ms = ingested_at_ms - device_timestamp
                      (may be negative if device clock is ahead — record raw value, do not clamp)
```

### 6.2 Metrics to capture and publish

Per run manifest (see §9):

| Metric | Description |
|--------|-------------|
| `latency_p50_ms` | Median end-to-end observed latency |
| `latency_p95_ms` | 95th percentile |
| `latency_p99_ms` | 99th percentile |
| `latency_max_ms` | Maximum observed |
| `loss_rate` | Fraction of events missing from store vs sent |
| `duplicate_rate` | Fraction of events with duplicate `event_id` |
| `reconnect_time_ms` | Time from broker disconnect to first event after reconnect |
| `run_duration_s` | Wall-clock test duration |
| `msg_count_sent` | Events published to broker |
| `msg_count_stored` | Events persisted in SQLite |
| `simulator_vs_hardware` | L2 / L3 / L4 level indicator |

**Do not invent thresholds.** Report raw distributions. Accept/reject criteria are stated explicitly per run in §6.3.

### 6.3 Per-run reporting template

```yaml
run_id: "<uuid>"
commit: "<git SHA>"
firmware_version: "<ESP32 firmware tag or commit>"
start_iso: "<ISO 8601>"
end_iso: "<ISO 8601>"
level: "L2"  # or L3 / L4
broker: "<broker type + version>"
gateway: "<Python version + commit>"
results:
  latency_p50_ms: <float>
  latency_p95_ms: <float>
  latency_p99_ms: <float>
  latency_max_ms: <float>
  loss_rate: <float 0-1>
  duplicate_rate: <float 0-1>
  reconnect_time_ms: <float or null>
  msg_sent: <int>
  msg_stored: <int>
criteria_pass: true  # set by reviewer
notes: "<reviewer notes>"
```

### 6.4 Pass/fail criteria

Criteria are set **per run** by the reviewer after observing raw numbers. The plan mandates that raw numbers are published; it does not pre-define pass thresholds.

---

## 7. Simulator vs hardware execution matrix

| Test | L2 (simulated MQTT) | L3 (ESP32 on bench) | L4 (full subsystem) |
|------|---------------------|---------------------|---------------------|
| Soak (ST-01 – ST-04) | ✅ Required | ⚠️ Desired | ⚠️ Desired |
| Broker disconnect (FI-01 – FI-04) | ✅ Required | ✅ Required | ⚠️ Desired |
| Message loss (FI-05 – FI-06) | ✅ Required | ✅ Required | ⚠️ Desired |
| Message reorder (FI-07 – FI-08) | ✅ Required | ⚠️ Desired | ⚠️ Desired |
| Latency (L2 only) | ✅ Required | ⚠️ Desired | ⚠️ Desired |
| Safety: E-stop during disconnect | N/A | ⚠️ Desired | ⚠️ **BLOCKED** |
| Safety: Jam detection during fault | N/A | ⚠️ Desired | ⚠️ **BLOCKED** |

Legend: ✅ Required = must run in CI or manually before merge; ⚠️ Desired = should run when hardware available; **BLOCKED** = blocked by hardware availability.

---

## 8. Test execution commands

### L2 (simulated — local)

```bash
# Broker mock via testcontainers or localhost mosquitto
# Gateway
cd iot-gateway
python -m pytest tests/test_gateway.py -v --tb=short

# Bridge AMLP codec parity
cd esp32-ukit-bridge
python -m pytest tests/python/test_protocol.py tests/parity/test_parity.py -v

# Integration (requires running broker)
python -m pytest tests/integration/ -v
```

### L3 (ESP32 on bench)

```bash
# Flash firmware
cd esp32-ukit-bridge
pio run -e esp32-s3-bridge -t upload
# Monitor serial
pio device monitor --port /dev/ttyUSB0 --baud 115200

# Gateway + broker (local)
cd iot-gateway
python -m uvicorn iot_gateway.main:app --host 0.0.0.0

# Latency capture
python scripts/capture_latency.py --run-id <uuid> --duration 300 --level L3
```

---

## 9. Evidence requirements

For every test run the following must be attached to the PR or linked issue:

1. Run manifest YAML (per §6.3) — required for all levels
2. Gateway log excerpt (startup to shutdown) — required for all levels
3. SQLite dump of stored events — required for all levels
4. Broker QoS log / Wireshark capture — required for L3/L4
5. Hardware pre-check sign-off (voltage, grounding, E-stop, operator) — required for L3/L4

**Do not claim a run as PASS without evidence attached.**

---

## 10. Compatibility notes

- Gateway is read-only; it never publishes commands. Fault injection tests must not assume gateway can send commands.
- ESP32 bridge publishes MQTT telemetry only after confirmed UART AMLP exchange; there is no simulated standalone telemetry without a physical or simulator-connected UKIT reference.
- AMLP wire format: `@TYPE,fields*C4E5\r\n`; gateway normaliser reads the JSON envelope, not the AMLP frame directly.
- Store bounded retention: at most `max_events` (default 100) events are retained. Soak tests should account for this when measuring long-run counts.
- Gateway write queue capacity: 500 events. Events arriving when queue is full are dropped (QoS 0 semantics at application layer).

---

## 11. Relationship to acceptance scenarios

| Acceptance scenario | Integration test |
|---------------------|-----------------|
| E01 Normal production | ST-01, ST-03 |
| E02 Invalid command payload | FI-*: handled by normaliser quarantine |
| E03 Duplicate correlation ID | Duplicate rate metric (ST-02, ST-04) |
| E04 Bad CRC / oversize AMLP | L1 unit tests (`test_protocol.py`, `test_security_contract.py`) |
| E05 Jam / sensor timeout | **BLOCKED** (hardware) |
| E06 Broker disconnect | FI-01, FI-02 |
| E07 Out-of-order event | FI-07, FI-08 |
| E08 Reconnect | FI-03, FI-04 |
| E09 MiniAlpha offline | Out of scope for this plan |
| E10 AI unsafe action | Out of scope for this plan |
| E11 Emergency stop | **BLOCKED** (hardware L4) |
| E12 Event replay | Store query ordering tests |

---

## 12. Open issues and risks

| ID | Description | Impact | Mitigation |
|----|-------------|--------|------------|
| RISK-01 | TLS not wired in ESP32 firmware; port 8883 uses plain TCP | Security | Documented in `test_security_contract.py`; not a blocker for this plan |
| RISK-02 | ESP32 telemetry-to-MQTT not confirmed end-to-end | Coverage gap | Track in Issue #66 |
| RISK-03 | Soak test requires persistent environment (CI vs long-running local) | Execution | Run as separate job; results uploaded as artifacts |
| RISK-04 | L4 hardware tests blocked until physical subsystem available | Scope | Marked BLOCKED; no false PASS claims |
