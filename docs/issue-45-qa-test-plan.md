# Issue #45 — QA Test Plan

**Author:** agent  
**Reviewer:** vinhphan812  
**Status:** draft  
**Evidence level:** L0–L3  
**Branch:** `feat/issues-44-45-test-plans`

---

## 1. Purpose and scope

This plan defines the QA test suite for the Smart Factory system: **ESP32 UKIT bridge firmware, AMLP protocol codec, and IoT gateway**.

It covers:
- Current test coverage per module (what exists today)
- Negative-case matrix: malformed inputs, missing fields, over-range values, unknown devices, duplicate commands, late ACKs, CRC errors, unsynced timestamps
- PR quality gate criteria: what must pass before a PR can be merged
- Coverage targets: minimum line/branch and scenario coverage required per module

It does **not** cover:
- Physical hardware safety tests (L4) — those require a controlled lab environment and operator pre-check
- Unity Digital Twin and MiniAlpha integration — tracked separately

---

## 2. Evidence level definitions (from `docs/testing-and-acceptance.md`)

| Level | Environment |
|-------|-------------|
| L0 | static / schema review |
| L1 | Python / C99 host unit |
| L2 | simulated UART/MQTT, mock device |
| L3 | ESP32 + real controller on bench |

---

## 3. Current test coverage per module

### 3.1 `iot-gateway/` — Python gateway service

| File | Tests | Coverage focus |
|------|-------|----------------|
| `tests/conftest.py` | fixtures only | store, ws_server, database_url |
| `tests/test_gateway.py` | 7 test classes, ~14 cases | MQTT pipeline, quarantine, deduplication, ordering, bounded queue, read-only, shutdown |
| `tests/test_models.py` | 4 cases | CanonicalEvent, EventType enum, serialisation |
| `tests/test_normalizer.py` | 12 cases | all event types, invalid JSON, unknown topics, sequence, UUID uniqueness, ISO timestamp, UTF-8 |
| `tests/test_store.py` | 8 cases | insert, query, count, retention, ordering |
| `tests/test_alerts.py` | 6 test classes | AlertEvent, AlertService, handlers, severity, ACK/RESOLVE |
| `tests/test_api.py` | 9 cases | REST endpoints, WS broadcast fan-out, disconnect |
| `tests/test_dashboard_safety.py` | 11 test classes | WS config, mode separation, local ack restriction, telemetry forwarding, XSS safety, canonical acceptance |
| `tests/test_ssrf.py` | 8 cases | SSRF allowlist, fail-closed, redirects, credentials masking |

**Summary:** 9 test files, ~80 test cases. All at L1/L2.

**Gaps identified:**
- No MQTT broker integration test (mock only, no live broker)
- No latency measurement tests
- No network fault injection tests (broker disconnect, reorder)
- No soak / sustained-load test
- Alert webhook handler: no live HTTP mock tests (aiohttp mock only)
- REST API: no 4xx/5xx error path tests beyond 404

### 3.2 `esp32-ukit-bridge/` — ESP32 firmware + Python AMLP codec + simulator

| File | Tests | Coverage focus |
|------|-------|----------------|
| `tests/python/test_protocol.py` | 7 cases | CRC reference vector, encode/decode round-trip, stream parser noise/chunks, timeout, bad CRC, field validation |
| `tests/python/test_simulator.py` | 4 cases | conveyor start/ack, duplicate ID suppression, unknown command, non-command ignore |
| `tests/python/test_cli.py` | 5 cases | CRC, encode/decode, invalid frame |
| `tests/parity/test_parity.py` | 4 classes, ~30 parametrised cases | CRC golden vectors (5 vectors), CRLF/LF decode, wrong CRC, canonical envelope, JSON→AMLP wire, malformed JSON rejection, duplicate suppression |
| `tests/integration/test_security_contract.py` | 5 classes, ~25 cases | anonymous connection prevention, command allowlist, argument validation, input validation, SSRF/TLS not wired |

**Summary:** 5 test files, ~65 test cases. All at L1.

**Gaps identified:**
- No L2 MQTT integration tests (live broker + ESP32)
- No firmware-level C++ unit tests (CommandMapper, MqttBridge) — these are documented as "not yet wired" in parity test comments
- No latency measurement
- No fault injection (network loss, reorder, reconnect)
- TLS not tested (`TestTlsNotWired` is entirely `@pytest.skip`)
- Stream parser: timeout boundary at exactly 350 ms only; no mid-frame injection of noise bytes at every byte position

---

## 4. Negative-case matrix

Each cell documents: module, test level, current coverage status, what must be added.

| Case | Module | Level | Currently tested? | Required addition |
|------|--------|-------|-------------------|-------------------|
| **Malformed JSON** — invalid UTF-8 | gateway / normaliser | L1 | ✅ `test_normalizer.py::test_invalid_json_returns_none` | Add: mixed-encoding payload (UTF-16 LE/BE, BOM prefix), string truncation mid-character |
| **Malformed JSON** — not JSON at all | gateway / normaliser | L1 | ✅ `test_normalizer.py::test_invalid_json_returns_none` | Add: empty bytes, binary payload (image data), extremely long string (>1 MB) |
| **Malformed JSON** — wrong type (array instead of dict) | gateway / normaliser | L1 | ❌ Missing | Add: `payload = json.dumps([1,2,3]).encode()` → normaliser must return None |
| **Missing required field** — `device_id` via topic | gateway / normaliser | L1 | ⚠️ Partial | Add: malformed topic with empty segment `smart-factory//command/ack` |
| **Missing required field** — `status` in command_ack | gateway / normaliser | L1 | ❌ Missing | Add: `{"command_id":1,"request_id":"x"}` (no `status`) → event created but `status` absent from payload |
| **Missing required field** — `command_name` | gateway / normaliser | L1 | ❌ Missing | Add: `{"command_id":1}` → normaliser returns `command_ack` type but payload lacks command_name |
| **Over-range integer** — command_id > 65535 | gateway / normaliser | L1 | ❌ Missing | Add: `{"command_id":70000}` → event created; store must not reject (schema allows integer) |
| **Over-range** — speed argument > 100 | firmware / CommandMapper | L1 | ⚠️ Documented only | Codec accepts; firmware rejects — no automated firmware test yet; document in test_parity.py |
| **Over-range** — channel > 255 | firmware / CommandMapper | L1 | ⚠️ Documented only | Same as above |
| **Unknown device** — unregistered device_id | gateway / quarantine | L1 | ✅ `test_gateway.py::test_unknown_topic_not_stored` | Note: "unknown device" vs "unknown topic" — device_id `xyz-999` passes topic pattern but is unrecognised; add test |
| **Unknown command name** | firmware / codec | L1 | ✅ `test_simulator.py::test_unknown_command_is_rejected` + `test_security_contract.py` | Add: case variants (`Conveyor_Start`), injection (`CONVEYOR_START\nRISET`), mixed-case |
| **Duplicate command** — same correlation ID | firmware / simulator | L1 | ✅ `test_simulator.py::test_duplicate_id_is_acknowledged_without_reexecution` | Add: duplicate at boundary of 16-entry LRU cache (17th entry evicts first) |
| **Duplicate command** — gateway read-only (no dedup at application level) | gateway | L1 | ✅ `test_gateway.py::TestGatewayDeduplication` | No application-layer dedup; downstream consumers deduplicate by `event_id` |
| **Late ACK** — ACK arrives after command expiry window | gateway | L1 | ❌ Missing | Add: simulated 30 s delay between command publish and ACK arrival; sequence must reflect late arrival |
| **Late ACK** — ACK for already-replaced duplicate | firmware / simulator | L1 | ✅ Simulator handles; no explicit timing test | Add: LRU cache replacement test with explicit timing |
| **CRC error** — bad checksum | firmware / codec | L1 | ✅ `test_protocol.py::test_bad_crc_and_lowercase_crc_are_rejected` | Add: single-bit flip in body bytes (not just CRC); CRC of zero |
| **CRC error** — lowercase CRC hex | firmware / codec | L1 | ✅ `test_protocol.py::test_bad_crc_and_lowercase_crc_are_rejected` | Covered |
| **Unsync timestamp** — device clock drift | gateway | L1 | ❌ Missing | Add: payload timestamp in future (device clock ahead of gateway) and far past (negative latency); normaliser stores raw value, does not reject |
| **Unsync timestamp** — zero timestamp | gateway / normaliser | L1 | ✅ `test_normalizer.py::test_timestamp_ms_missing` | Covered |
| **Unsync timestamp** — non-integer timestamp | gateway / normaliser | L1 | ❌ Missing | Add: `"timestamp": "not-a-number"` → mqtt_timestamp_ms = 0, no exception |
| **Malformed AMLP frame** — missing @ prefix | firmware / codec | L1 | ✅ Stream parser noise test | Covered implicitly |
| **Malformed AMLP frame** — reserved character in field | firmware / codec | L1 | ✅ `test_security_contract.py::test_amlp_reserved_characters_rejected` | Covered |
| **Malformed AMLP frame** — empty field | firmware / codec | L1 | ✅ `test_security_contract.py::test_empty_field_rejected` | Covered |
| **Malformed AMLP frame** — frame too long | firmware / codec | L1 | ❌ Missing | Add: body > 255 bytes; codec should reject before UART dispatch |
| **Oversized JSON** — > broker max payload | gateway / normaliser | L1 | ❌ Missing | Add: payload > broker limit (e.g. 1 MB JSON); normaliser must not OOM |
| **SSRF via webhook URL** — file:// scheme | gateway / alerts | L1 | ✅ `test_alerts.py::test_rejects_file_scheme` | Covered |
| **SSRF via webhook URL** — gopher:// scheme | gateway / alerts | L1 | ✅ `test_alerts.py::test_rejects_gopher_scheme` | Covered |
| **SSRF via webhook URL** — off-allowlist host | gateway / alerts | L1 | ✅ `test_ssrf.py::test_reject_off_allowlist_host` | Covered |
| **SSRF via webhook URL** — subdomain bypass | gateway / alerts | L1 | ✅ `test_ssrf.py::test_subdomain_not_accepted` | Covered |
| **WS client full queue** | gateway / api | L2 | ✅ `test_api.py::test_broadcast_disconnects_lagging_clients` | Covered |

---

## 5. PR quality gate criteria

A PR **must** satisfy all of the following before it can be merged. The reviewer (vinhphan812) enforces these gates.

### 5.1 Required: all existing tests pass

```bash
cd iot-gateway && python -m pytest tests/ -q --tb=short
cd esp32-ukit-bridge && python -m pytest tests/ -q --tb=short
```

Exit code must be 0. No skipped tests may be converted to passing without corresponding code changes.

### 5.2 Required: no new linting errors

```bash
pylint --disable=all --enable=doc-string-type,docstring-min-length,missing-function-docstring,missing-module-docstring,missing-class-docstring iot-gateway/
pylint --disable=all --enable=doc-string-type,docstring-min-length,missing-function-docstring,missing-module-docstring,missing-class-docstring esp32-ukit-bridge/
```

New warnings introduced by the PR are treated as failures. Pre-existing warnings are out of scope.

### 5.3 Required: new code has tests

| Change type | Minimum coverage |
|-------------|-----------------|
| New gateway module | New module covered by L1 tests |
| New normaliser event type | Test for that type + missing/invalid payload |
| New AMLP message type | Encode/decode round-trip + invalid body test |
| New API endpoint | `GET` → at least one 200 + one 404 test |
| New alert handler | Unit test for accept path + all rejection paths |

### 5.4 Required: negative cases covered for user input paths

Any function that parses external input (JSON, MQTT payload, URL, user-provided config) must have at least one test for:
- Valid input (happy path)
- Invalid/malformed input
- Empty input (if applicable)

### 5.5 Required: no secrets in diff

```bash
git diff origin/master -- "*.py" "*.json" "*.yaml" | grep -iE "(password|token|secret|api_key|private_key)" || echo "OK"
```

Any hard-coded secret introduced by the PR is a blocking finding.

### 5.6 Required: schema changes reviewed

If `contracts/v1/schemas/` is modified, the PR must include:
- Updated schema file
- Test case(s) that use the new schema via `jsonschema.validate()`
- Note in PR description: "Schema change: backward-compatible / breaking" (choose one)

### 5.7 Required: ADR for architecture changes

Any change that alters the contract between modules (AMLP wire format, MQTT topic pattern, canonical event envelope, API response shape) requires an ADR or a reference to an existing ADR. ADR must be in `docs/architecture/adr-*.md`.

Exception: trivial refactoring with no contract change may omit the ADR if the reviewer agrees.

### 5.8 Desired: coverage report attached

For PRs adding >50 lines of production code:

```bash
cd iot-gateway && python -m pytest tests/ --cov=iot_gateway --cov-report=term-missing
cd esp32-ukit-bridge && python -m pytest tests/ --cov=amlp --cov-report=term-missing
```

Coverage report must be attached as a PR comment or artifact. Coverage must not drop by more than 2 percentage points from the branch baseline.

---

## 6. Coverage targets

Targets are **minimum requirements**, not aspirational goals. Current coverage is stated as baseline.

### 6.1 `iot-gateway/` Python module

| Metric | Current baseline | Target |
|--------|----------------|--------|
| Line coverage | ~75 % (approximate, run `pytest --cov`) | ≥ 85 % |
| Branch coverage | ~60 % (approximate) | ≥ 75 % |
| Module coverage (all `.py` files importable) | 100 % | 100 % |
| Negative case scenarios covered | ~12 of 30 | ≥ 25 of 30 |

### 6.2 `esp32-ukit-bridge/` Python AMLP codec + simulator

| Metric | Current baseline | Target |
|--------|----------------|--------|
| Line coverage | ~90 % (codec well-tested) | ≥ 90 % |
| Branch coverage | ~80 % | ≥ 85 % |
| AMLP frame type coverage | 3/3 types | 3/3 types |
| AMLP error path coverage | partial | All FrameError paths covered |
| Negative case scenarios covered | ~18 of 25 | ≥ 22 of 25 |

### 6.3 Firmware C++ tests (ESP32, `test_bridge/`)

These tests are not yet wired in CI. They are tracked as **BLOCKED** pending PlatformIO test environment setup.

| Metric | Target |
|--------|--------|
| CommandMapper unit tests | Cover all 5 commands + all rejection cases |
| MqttBridge JSON adapter tests | Cover all JSON error paths |
| UART mock integration | Cover: valid frame, CRC error, timeout, LRU dedup |
| TLS not-wired | Documented skip; gate on ADR |

### 6.4 Coverage reporting cadence

Coverage is measured:
- Per PR (desired, see §5.8)
- On merge to `origin/master` (required, reported in PR)
- Monthly baseline comparison (tracked in issue)

---

## 7. Test execution summary

```bash
# Full QA suite (L1 + L2)
cd iot-gateway && python -m pytest tests/ -v --tb=short
cd esp32-ukit-bridge && python -m pytest tests/ -v --tb=short

# Coverage (desired)
cd iot-gateway && python -m pytest tests/ --cov=iot_gateway --cov-report=term-missing
cd esp32-ukit-bridge && python -m pytest tests/ --cov=amlp --cov-report=term-missing

# Lint gate
pylint --disable=all --enable=doc-string-type,docstring-min-length,missing-function-docstring iot_gateway/ esp32-ukit-bridge/amlp/
```

---

## 8. Open gaps and tracking

| Gap | Tracked in | Notes |
|-----|-----------|-------|
| L2 MQTT broker integration tests | Issue #44 (this plan) | soak + fault injection |
| L3 ESP32 bench tests | Issue #66 | pending hardware availability |
| C++ firmware unit tests | Issue #66 | pending PlatformIO test setup |
| TLS integration tests | Issue #66 + ADR | blocked by WiFiClientSecure wiring |
| Monthly coverage regression check | Issue #45 (this plan) | manual or CI job |

---

## 9. Relationship to acceptance scenarios

| Acceptance scenario | QA coverage |
|---------------------|-------------|
| E02 Invalid command payload | Negative case matrix rows: malformed JSON, missing fields |
| E03 Duplicate correlation ID | `test_simulator.py::test_duplicate_id_is_acknowledged_without_reexecution`; negative matrix entry |
| E04 Bad CRC / oversize AMLP | `test_protocol.py`, `test_security_contract.py`; negative matrix entry |
| E06 Broker disconnect | Covered by `test_gateway.py::TestGatewayMQTTPipeline` at L2 mock; live broker in Issue #44 |
| E07 Out-of-order event | Store ordering test (`test_store.py::test_sequence_ordering`); negative matrix entry |
| E11 Emergency stop | **BLOCKED** (hardware L4) |
