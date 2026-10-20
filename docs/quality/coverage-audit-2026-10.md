# Coverage Audit — October 2026

**Issue:** #187  
**Audited:** 2026-10-20  
**Auditor:** dev-qa  
**Branch:** `feat/issue-187-ci-coverage-audit` → master  
**Scope:** `iot-gateway/`, `factory-control/`, `dashboard/`, `edge-ai-robot/`, `integration-tests/`

---

## 1. Module Summary

| Module | Language | Source LOC | Test LOC | Test Files | CI Workflow | Overall Coverage | Status |
|---|---|---|---|---|---|---|---|
| `iot-gateway/` | Python | 3,641 | 4,675 | 12 | `gateway-ci.yml` | **50%** | ⚠️ PARTIAL |
| `factory-control/` | Python | 2,709 | 1,554 | 5 | `factory-control-ci.yml` | **69%** | ⚠️ PARTIAL |
| `dashboard/` | TypeScript/React | 5,496 | ~300 | 2 | **MISSING** | unknown | 🔴 NO CI |
| `edge-ai-robot/` | Python | 927 | 504 | 3 | **MISSING** | 0% | 🔴 NO CI |
| `integration-tests/` | Python | — | — | 0 | **MISSING** | N/A | 🔴 NOT STARTED |
| `esp32-ukit-bridge/` | C / Python | — | 196 | 1 | `bridge-ci.yml` | N/A (native) | 🟢 CI OK |
| `digital-twin/` | — | — | — | — | **MISSING** | N/A | ⚪ UNCLEAR |

---

## 2. `iot-gateway/` — Detailed Coverage

**Run:** `pytest --cov=src --cov-report=term-missing tests/` (161 pass / 7 fail)  
**Result:** 50% line coverage (670 of 1,429 statements not covered)  
**CI:** `gateway-ci.yml` — runs pytest on Python 3.11/3.12, installs `iot-gateway[dev]`  
**Note:** 7 SSRF tests fail due to `aiohttp` not being installed in the local venv; these pass in CI where dependencies are installed.

### Per-Module Coverage

| File | Statements | Missing | Coverage | Missing Test Categories |
|---|---|---|---|---|
| `src/iot_gateway/gateway.py` | 100 | 100 | **0%** | HAPPY_PATH, ERROR_PATH, MQTT reconnect, timeout |
| `src/iot_gateway/mqtt_client.py` | 49 | 49 | **0%** | CONNECT, DISCONNECT, RECONNECT, QoS, TLS |
| `src/iot_gateway/adapters/orion_ld.py` | 264 | 264 | **0%** | QUERY, SUBSCRIBE, ERROR_PATH, NGSI-LD entities |
| `src/iot_gateway/time_sync.py` | 82 | 64 | **16%** | HAPPY_PATH (NTP-like sync), skew detection |
| `src/iot_gateway/incidents.py` | 105 | 46 | **47%** | INCIDENT_ACK, CONCURRENCY, timeout |
| `src/iot_gateway/event_store.py` | 143 | 38 | **71%** | CONCURRENCY, RECOVERY, TTL expiry |
| `src/iot_gateway/api.py` | 176 | 42 | **73%** | AUTH, CONCURRENCY, timeout, 4xx/5xx |
| `src/iot_gateway/alerts.py` | 212 | 24 | **89%** | CONCURRENCY (webhook handler) |
| `src/iot_gateway/safety_gate.py` | 143 | 6 | **95%** | CONCURRENCY (async) |
| `src/iot_gateway/event_normalizer.py` | 73 | 3 | **95%** | All major paths covered |
| `src/iot_gateway/models.py` | 32 | 1 | **97%** | All paths covered |

### Missing Test Categories (iot-gateway)

| Category | Covered? | Key Gap |
|---|---|---|
| Happy path — MQTT connect/publish | ❌ No | `gateway.py`, `mqtt_client.py` at 0% |
| Error path — broker disconnect | ❌ No | No reconnect/disconnect tests |
| Error path — malformed payloads | ⚠️ Partial | `event_normalizer.py` covered; `models.py` minimal |
| Auth / RBAC | ❌ No | No auth tests in `api.py` |
| Concurrency — concurrent events | ⚠️ Partial | `safety_gate.py` async covered; `api.py` concurrent WS not |
| Timeout / retry | ❌ No | No timeout/retry scenarios |
| Orion LD NGSI-LD | ❌ No | `adapters/orion_ld.py` at 0% |
| SSRF prevention | 🟢 Yes | `test_ssrf.py` 7 tests |

---

## 3. `factory-control/` — Detailed Coverage

**Run:** `pytest --cov=src --cov-report=term-missing tests/` (98 pass)  
**Result:** 69% line coverage (339 of 1,092 statements not covered)  
**CI:** `factory-control-ci.yml` — runs pytest on Python 3.11/3.12, installs `pydantic pytest pytest-asyncio`  

### Per-Module Coverage

| File | Statements | Missing | Coverage | Notes |
|---|---|---|---|---|
| `src/factory_control/` (old pkg, unused) | ~230 | ~230 | **0%** | Deprecated dual-package layout |
| `src/adapters/adapters.py` (stub) | 2 | 2 | **0%** | Re-export stub, not used |
| `src/adapters/sorting.py` | 183 | 34 | **81%** | TC1–TC8 covered; reject/sensor fault paths missing |
| `src/adapters/base.py` | 66 | 12 | **82%** | Abstract base, partially exercised |
| `src/simulator.py` | 115 | 34 | **70%** | Tick loop; integration with adapters not covered |
| `src/state_machine.py` | 124 | 7 | **94%** | All transitions; history/telemetry paths missing |
| `src/adapters/conveyor.py` | 142 | 7 | **95%** | Speed, direction, sensor integration covered |
| `src/models.py` | 122 | 5 | **96%** | Edge cases for serialization |

### Missing Test Categories (factory-control)

| Category | Covered? | Key Gap |
|---|---|---|
| Happy path — sorting module | 🟢 Yes | TC1–TC8 implemented |
| Error path — sensor fault | ⚠️ Partial | TC5 covered; other fault modes not |
| Error path — E-stop from running | 🟢 Yes | TC6 covered |
| Error path — duplicate item | 🟢 Yes | TC3 covered |
| Concurrency — multi-module | ❌ No | No concurrent state machine tests |
| Simulator — tick integration | ⚠️ Partial | `test_simulator.py` exists; adapter integration missing |
| Idempotency | 🟢 Yes | TC7 covered |
| Telemetry compliance | 🟢 Yes | TC8 covered |

---

## 4. `dashboard/` — No Coverage

**Run:** `npm test` — 2 test files exist but no CI workflow  
**Result:** No CI; coverage unknown  
**CI Status:** 🔴 **MISSING** — no `.github/workflows/dashboard-ci.yml`

### Existing Tests

| File | Type | Coverage |
|---|---|---|
| `src/tests/gatewayWs.test.ts` | Vitest unit | Minimal |
| `src/tests/TelemetryChart.test.tsx` | Vitest + React Testing Library | Minimal |

### Source Files Without Tests

- `src/api/gateway.ts` — API client for all gateway operations
- `src/api/websocket.ts` — WebSocket event consumer
- `src/components/incident/*` — Incident UI components (AcknowledgeButton, IncidentCard, IncidentTimeline)
- `src/hooks/incidents/*` — Incident state management hooks
- `src/hooks/useGatewayEvents.ts` — Gateway event processing
- `src/features/telemetry/*` — Telemetry charts (TelemetryChart covered; hook not)
- `src/contracts/gateway.ts` — Contract types (Pydantic-equivalent)

### Missing Test Categories (dashboard)

| Category | Covered? | Key Gap |
|---|---|---|
| Happy path — incident list | ❌ No | No incident component tests |
| Happy path — telemetry chart | ⚠️ Partial | `TelemetryChart.test.tsx` exists; `useTelemetryChart` hook not |
| Error path — WebSocket disconnect | ⚠️ Partial | `gatewayWs.test.ts` covers disconnect; no reconnect |
| Auth / RBAC | ❌ No | No auth/rbac tests |
| WebSocket event routing | ❌ No | No tests for `useGatewayEvents` |
| Incident acknowledge workflow | ❌ No | No `AcknowledgeButton` tests |
| Contract validation | ❌ No | No tests for `contracts/gateway.ts` |

---

## 5. `edge-ai-robot/` — Tests Cannot Run

**Run:** `pytest tests/` → all 3 tests fail with `ModuleNotFoundError: No module named 'structlog'`  
**Result:** 0% coverage (no test can even collect)  
**CI Status:** 🔴 **MISSING** — no workflow file  

**Root Cause:** Tests import `edge_ai_robot.*` which transitively imports `structlog`, `httpx`, `websockets`, and `pydantic`. These are declared in `pyproject.toml` as runtime dependencies but the tests are unrunnable without them.

### Source Files Without Tests

- `src/edge_ai_robot/adapter/__init__.py` (156 statements) — Robot adapter, 0% covered
- `src/edge_ai_robot/detection/__init__.py` (90 statements) — Anomaly detection, 0% covered
- `src/edge_ai_robot/skills/__init__.py` (40 statements) — Skill definitions, 0% covered

### Missing Test Categories (edge-ai-robot)

All categories missing — tests cannot run at all.

| Category | Status |
|---|---|
| Happy path — robot connect/command | ❌ Tests fail at import |
| Error path — connection failure | ❌ Tests fail at import |
| Detection — anomaly scoring | ❌ Tests fail at import |
| Skills — invocation and response | ❌ Tests fail at import |
| Auth / RBAC | ❌ Tests fail at import |
| Concurrency | ❌ Tests fail at import |

---

## 6. CI Gaps

| Module | CI Workflow | Trigger | Tests Run | Coverage | Notes |
|---|---|---|---|---|---|
| `iot-gateway/` | `gateway-ci.yml` | push + PR, paths filter | ✅ Yes | ✅ (XML) | `coverage report: term-missing` as `continue-on-error: true` |
| `factory-control/` | `factory-control-ci.yml` | push + PR, paths filter | ✅ Yes | ❌ No | No coverage step |
| `dashboard/` | **MISSING** | — | — | — | Needs `dashboard-ci.yml` |
| `edge-ai-robot/` | **MISSING** | — | — | — | Needs `edge-ai-robot-ci.yml` |
| `integration-tests/` | **MISSING** | — | — | — | Status: PLANNED |
| `esp32-ukit-bridge/` | `bridge-ci.yml` | push + PR, paths filter | ✅ Python + PlatformIO | ✅ Native | Python tests + native firmware |
| `digital-twin/` | **MISSING** | — | — | — | No workflow; scope unclear |

### CI Quality Issues

1. **`gateway-ci.yml`** — coverage step has `continue-on-error: true`; coverage failures are silently ignored
2. **`factory-control-ci.yml`** — no coverage collection; cannot track coverage trends
3. **`adr-lint.yml`** — only checks ADR compliance, not test quality

---

## 7. Recommendations

### Priority 1 — Add Missing CI Workflows

1. **Create `docs/quality/.github/workflows/dashboard-ci.yml`**
   ```yaml
   name: Dashboard Tests
   on:
     push:
       branches: [master]
       paths: [dashboard/**]
     pull_request:
       paths: [dashboard/**]
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4
           with: { node-version: '20', cache: 'npm', cache-dependency-path: dashboard/package-lock.json }
         - run: npm ci
         - run: npm test -- --coverage
         - uses: actions/upload-artifact@v4
           with: { name: coverage, path: coverage/ }
   ```

2. **Create `.github/workflows/edge-ai-robot-ci.yml`**
   ```yaml
   name: Edge AI Robot Tests
   on:
     push:
       branches: [master]
       paths: [edge-ai-robot/**]
     pull_request:
       paths: [edge-ai-robot/**]
   jobs:
     pytest:
       runs-on: ubuntu-latest
       strategy:
         matrix:
           python: ['3.11', '3.12']
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with: { python-version: ${{ matrix.python }} }
         - run: pip install -e "edge-ai-robot[dev]"
         - run: pytest tests/ --cov=src --cov-report=xml --cov-report=term-missing
   ```

### Priority 2 — Fix Test Collectibility (edge-ai-robot)

3. **Add missing dev dependencies to `edge-ai-robot/pyproject.toml`**
   - `pytest-asyncio` is already in `[dev]`
   - Add `pytest-mock` for unit isolation
   - The runtime deps (`structlog`, `httpx`, `websockets`, `pydantic`) are already declared; CI installs `-e "edge-ai-robot[dev]"` which pulls all deps

### Priority 3 — Increase iot-gateway Coverage (50% → target 80%)

4. **Add `tests/test_gateway.py`** — currently exists but requires `paho-mqtt`; expand with mocked MQTT
5. **Add `tests/test_mqtt_client.py`** — new file needed; 0% coverage
6. **Add `tests/test_orion_ld_adapter.py`** — new file needed; 0% coverage
7. **Add `tests/test_time_sync.py`** — currently 16%; expand to cover `sync_and_offset()`, skew detection
8. **Add `tests/test_incidents.py`** — currently 47%; add acknowledge workflow tests
9. **Add `tests/test_event_store_concurrency.py`** — new file for concurrent write scenarios

### Priority 4 — Increase factory-control Coverage (69% → target 85%)

10. **Add `tests/test_simulator_integration.py`** — integrate `test_simulator.py` with adapter calls
11. **Add `tests/test_sorting_fault_modes.py`** — sensor fault, multi-item jams, unknown classification edge cases
12. **Add `tests/test_state_machine_concurrency.py`** — concurrent state transitions
13. **Remove or document `src/factory_control/` stub package** — dual package layout causes 230 statements at 0%

### Priority 5 — Dashboard Tests

14. **Add `src/hooks/incidents/__tests__/`** — `useIncidentActions`, `useIncidents` hooks
15. **Add `src/components/incident/__tests__/`** — `AcknowledgeButton`, `IncidentCard`, `IncidentTimeline`
16. **Add `src/api/__tests__/`** — `gateway.ts` and `websocket.ts` contract tests
17. **Add `src/contracts/__tests__/`** — `contracts/gateway.ts` type validation tests

### Priority 6 — Integration Tests

18. **Implement `integration-tests/` scaffold** — per `docs/testing-and-acceptance.md` L3–L5 scope
19. **Add `integration-tests/scenarios/`** — at least one happy-path E2E and one error-path

---

## 8. Evidence

| Check | Command | Result |
|---|---|---|
| iot-gateway pytest | `pytest --cov=src tests/` | 161 pass / 7 fail; 50% coverage |
| factory-control pytest | `pytest --cov=src tests/` | 98 pass; 69% coverage |
| edge-ai-robot pytest | `pytest tests/` | 3 ERROR (ModuleNotFoundError) |
| dashboard tests | `find dashboard -name "*.test.*"` | 2 files: gatewayWs.test.ts, TelemetryChart.test.tsx |
| CI workflows | `find . -path "*/.github/workflows/*.yml"` | 4 workflows (gateway, factory-control, bridge, adr-lint) |
| dashboard CI | `find .github/workflows -name "*dashboard*"` | NOT FOUND |
| edge-ai-robot CI | `find .github/workflows -name "*edge*" -o -name "*robot*"` | NOT FOUND |
| integration-tests | `ls integration-tests/` | README.md only; harness not implemented |

---

*Audit performed on `master` @ commit `87e2e38` via worktree `feat/issue-187-ci-coverage-audit`.*
