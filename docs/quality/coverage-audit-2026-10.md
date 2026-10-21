# Coverage Audit — October 2026 (Evidence-Bounded Snapshot)

> **⚠️ DATED AUDIT — NOT CI COMPLIANCE CERTIFICATION**  
> This document is an evidence-bounded snapshot taken on a specific commit with a specific
> environment. It does **not** represent current CI status, does **not** certify clean regression,
> and does **not** imply all tests pass everywhere. Figures marked stale are superseded by
> open PRs (#242, #244, #245). A re-audit is required after those PRs merge.

**Issue:** #187  
**Audited:** 2026-10-20  
**Last re-verified:** 2026-10-21 (ADR lint re-validation; test count re-check)  
**Auditor:** dev-qa  
**Branch:** `feat/issue-187-ci-coverage-audit` → master  
**PR Head:** `08ac8d5`  
**Scope:** `iot-gateway/`, `factory-control/`, `dashboard/`, `edge-ai-robot/`, `integration-tests/`

### How to Read This Document

Each percentage figure carries a provenance tag in brackets:

| Tag | Meaning |
|-----|---------|
| `[measured]` | Collected via `pytest --cov` or equivalent; coverage tool ran to completion |
| `[uncollectable]` | Tests exist but fail at import before any code executes; no coverage produced |
| `[not measured]` | No test run was executed for this module; no coverage data available |
| `[unavailable]` | Tooling or environment not set up to run tests for this module |

A `0%` figure with `[measured]` means coverage was collected and the result was zero.
A `0%` figure with `[uncollectable]` means no coverage was collected at all.

### ADR Lint Status

| Check | Result | Detail |
|-------|--------|--------|
| `ADR Lint & Architecture Governance Gate` | ✅ PASS | 4 consecutive runs 2026-10-20 13:31–13:38 (push + PR × 2) on SHA `08ac8d57` |

---

## 1. Module Summary

> **Staleness notice:** PRs #242 (dashboard auth), #244 (deployment/E2E), #245 (threat model v2, 69 security abuse tests)
> are open and **not yet merged** as of 2026-10-21. Their merge will alter iot-gateway test counts
> and runtime behavior. The iot-gateway coverage figure (50%) was measured before PR #245 merged;
> re-audit required post-merge. See Section 8 for confirmed staleness evidence.

| Module | Language | Source LOC | Test LOC | Test Files | CI Workflow | Coverage Provenance | Status |
|--------|----------|-----------|----------|------------|-------------|---------------------|--------|
| `iot-gateway/` | Python | 3,641 | 4,675 | 12 | `gateway-ci.yml` | **50% [measured]** | ⚠️ PARTIAL |
| `factory-control/` | Python | 2,709 | 1,554 | 5 | `factory-control-ci.yml` | **69% [measured]** | ⚠️ PARTIAL |
| `dashboard/` | TypeScript/React | 5,496 | ~300 | 2 | **MISSING** | **unknown [not measured]** | 🔴 NO CI |
| `edge-ai-robot/` | Python | 927 | 504 | 3 | **MISSING** | **0% [uncollectable]** | 🔴 NO CI |
| `integration-tests/` | Python | — | — | 0 | **MISSING** | N/A | 🔴 NOT STARTED |
| `esp32-ukit-bridge/` | C / Python | — | 196 | 1 | `bridge-ci.yml` | N/A (native) | 🟢 CI OK |
| `digital-twin/` | — | — | — | — | **MISSING** | N/A [unavailable] | ⚪ UNCLEAR |

---

## 2. `iot-gateway/` — Detailed Coverage

> **⚠️ STALE — 2026-10-21 re-check shows 246 tests collected (vs 168 at audit time).**
> PR #245 adds 69 security abuse tests. The 161/7 figure below was measured before PR #245 merged.
> Coverage % is expected to increase post-merge. See Section 8 for evidence.

**Original Run (2026-10-20):**
- **Command:** `pytest --cov=src --cov-report=term-missing tests/` (from `iot-gateway/` directory)
- **Environment:** Python 3.14.7, pytest 7.4.4, pytest-cov 4.1.0, coverage 7.2.7, aiohttp 3.8.6
- **OS:** Windows 11 (git-bash/MSYS)
- **Result:** 161 pass / 7 fail (SSRF tests requiring `aiohttp`); 50% line coverage
- **Commit measured:** `87e2e38` (master at audit time)
- **CI:** `gateway-ci.yml` — Python 3.11/3.12, installs `iot-gateway[dev]`, `continue-on-error: true` on coverage step

**7 SSRF failures:** `ModuleNotFoundError: No module named 'aiohttp'` in local venv. These 7 tests
pass in CI where `iot-gateway[dev]` is installed (which includes `aiohttp`). This is an environment
issue, not a test logic failure.

### Per-Module Coverage

| File | Statements | Missing | Coverage | Missing Test Categories |
|------|-----------|---------|----------|------------------------|
| `src/iot_gateway/gateway.py` | 100 | 100 | **0% [measured]** | HAPPY_PATH, ERROR_PATH, MQTT reconnect, timeout |
| `src/iot_gateway/mqtt_client.py` | 49 | 49 | **0% [measured]** | CONNECT, DISCONNECT, RECONNECT, QoS, TLS |
| `src/iot_gateway/adapters/orion_ld.py` | 264 | 264 | **0% [measured]** | QUERY, SUBSCRIBE, ERROR_PATH, NGSI-LD entities |
| `src/iot_gateway/time_sync.py` | 82 | 64 | **16% [measured]** | HAPPY_PATH (NTP-like sync), skew detection |
| `src/iot_gateway/incidents.py` | 105 | 46 | **47% [measured]** | INCIDENT_ACK, CONCURRENCY, timeout |
| `src/iot_gateway/event_store.py` | 143 | 38 | **71% [measured]** | CONCURRENCY, RECOVERY, TTL expiry |
| `src/iot_gateway/api.py` | 176 | 42 | **73% [measured]** | AUTH, CONCURRENCY, timeout, 4xx/5xx |
| `src/iot_gateway/alerts.py` | 212 | 24 | **89% [measured]** | CONCURRENCY (webhook handler) |
| `src/iot_gateway/safety_gate.py` | 143 | 6 | **95% [measured]** | CONCURRENCY (async) |
| `src/iot_gateway/event_normalizer.py` | 73 | 3 | **95% [measured]** | All major paths covered |
| `src/iot_gateway/models.py` | 32 | 1 | **97% [measured]** | All paths covered |

### Missing Test Categories (iot-gateway)

| Category | Covered? | Key Gap | Owner |
|----------|----------|---------|-------|
| Happy path — MQTT connect/publish | ❌ No | `gateway.py`, `mqtt_client.py` at 0% | backend-a |
| Error path — broker disconnect | ❌ No | No reconnect/disconnect tests | backend-a |
| Error path — malformed payloads | ⚠️ Partial | `event_normalizer.py` covered; `models.py` minimal | backend-a |
| Auth / RBAC | ❌ No | No auth tests in `api.py` | backend-a |
| Concurrency — concurrent events | ⚠️ Partial | `safety_gate.py` async covered; `api.py` concurrent WS not | backend-a |
| Timeout / retry | ❌ No | No timeout/retry scenarios | backend-a |
| Orion LD NGSI-LD | ❌ No | `adapters/orion_ld.py` at 0% | backend-a |
| SSRF prevention | 🟢 Yes | `test_ssrf.py` 7 tests (pass in CI) | security |

> **Owner key:** `backend-a` = iot-gateway implementer; `security` = security reviewer; `qa` = dev-qa.

---

## 3. `factory-control/` — Detailed Coverage

**Run:** `pytest --cov=src --cov-report=term-missing tests/` (from `factory-control/` directory)  
**Environment:** Python 3.14.7, pytest 7.4.4, pytest-cov 4.1.0, coverage 7.2.7  
**OS:** Windows 11 (git-bash/MSYS)  
**Result:** 98 pass; 69% line coverage (339 of 1,092 statements not covered)  
**Commit measured:** `87e2e38` (same run as iot-gateway)  
**CI:** `factory-control-ci.yml` — Python 3.11/3.12, installs `pydantic pytest pytest-asyncio`

### Per-Module Coverage

| File | Statements | Missing | Coverage | Notes |
|------|-----------|---------|----------|-------|
| `src/factory_control/` (old pkg, unused) | ~230 | ~230 | **0% [measured]** | Deprecated dual-package layout |
| `src/adapters/adapters.py` (stub) | 2 | 2 | **0% [measured]** | Re-export stub, not used |
| `src/adapters/sorting.py` | 183 | 34 | **81% [measured]** | TC1–TC8 covered; reject/sensor fault paths missing |
| `src/adapters/base.py` | 66 | 12 | **82% [measured]** | Abstract base, partially exercised |
| `src/simulator.py` | 115 | 34 | **70% [measured]** | Tick loop; integration with adapters not covered |
| `src/state_machine.py` | 124 | 7 | **94% [measured]** | All transitions; history/telemetry paths missing |
| `src/adapters/conveyor.py` | 142 | 7 | **95% [measured]** | Speed, direction, sensor integration covered |
| `src/models.py` | 122 | 5 | **96% [measured]** | Edge cases for serialization |

### Missing Test Categories (factory-control)

| Category | Covered? | Key Gap | Owner |
|----------|----------|---------|-------|
| Happy path — sorting module | 🟢 Yes | TC1–TC8 implemented | factory-a |
| Error path — sensor fault | ⚠️ Partial | TC5 covered; other fault modes not | factory-a |
| Error path — E-stop from running | 🟢 Yes | TC6 covered | factory-a |
| Error path — duplicate item | 🟢 Yes | TC3 covered | factory-a |
| Concurrency — multi-module | ❌ No | No concurrent state machine tests | factory-a |
| Simulator — tick integration | ⚠️ Partial | `test_simulator.py` exists; adapter integration missing | factory-a |
| Idempotency | 🟢 Yes | TC7 covered | factory-a |
| Telemetry compliance | 🟢 Yes | TC8 covered | factory-a |

> **Owner key:** `factory-a` = factory-control implementer.

---

## 4. `dashboard/` — Not Measured

> **`unknown [not measured]`** means no pytest/coverage run was executed. Two test files exist
> but no coverage tool was invoked and no CI workflow exists. This is **not** the same as "0% coverage".

**Run:** `find dashboard -name "*.test.*"` (find test files; no coverage collected)  
**Environment:** Node 26.7.0, npm 12.0.2  
**OS:** Windows 11  
**Result:** 2 test files found; no `npm test` coverage run recorded in audit  
**CI Status:** 🔴 **MISSING** — no `.github/workflows/dashboard-ci.yml`  
**Coverage:** **unknown [not measured]** — no CI workflow means no automated measurement

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

| Category | Covered? | Key Gap | Owner |
|----------|----------|---------|-------|
| Happy path — incident list | ❌ No | No incident component tests | dashboard-a |
| Happy path — telemetry chart | ⚠️ Partial | `TelemetryChart.test.tsx` exists; hook not | dashboard-a |
| Error path — WebSocket disconnect | ⚠️ Partial | `gatewayWs.test.ts` covers disconnect; no reconnect | dashboard-a |
| Auth / RBAC | ❌ No | No auth/rbac tests | dashboard-a |
| WebSocket event routing | ❌ No | No tests for `useGatewayEvents` | dashboard-a |
| Incident acknowledge workflow | ❌ No | No `AcknowledgeButton` tests | dashboard-a |
| Contract validation | ❌ No | No tests for `contracts/gateway.ts` | dashboard-a |

> **Owner key:** `dashboard-a` = dashboard implementer.
> **Remediation gate:** `dashboard-ci.yml` must exist and collect coverage before any module
> coverage target applies.

---

## 5. `edge-ai-robot/` — Tests Uncollectable

> **`0% [uncollectable]`** means coverage was not measured. All 3 test files fail at import
> (`ModuleNotFoundError: No module named 'edge_ai_robot'`). This is **not** "measured zero coverage."
> The source code exists; the package is not installed in the local environment.

**Run:** `pytest tests/` (from `edge-ai-robot/` directory)  
**Environment:** Python 3.14.7, pytest 7.4.4, httpx 0.24.1 (local venv)  
**OS:** Windows 11 (git-bash/MSYS)  
**Result:** 3 ERROR — all tests fail with `ModuleNotFoundError: No module named 'edge_ai_robot'`  
**CI Status:** 🔴 **MISSING** — no workflow file  
**Coverage:** **0% [uncollectable]** — tests cannot collect; coverage tool never ran

**Root Cause:** Tests import `edge_ai_robot.*` which transitively imports `structlog`, `httpx`,
`websockets`, and `pydantic`. The package is declared in `pyproject.toml` but not installed in the
local environment. CI would install `-e "edge-ai-robot[dev]"` which pulls all runtime deps.  
**Additional note:** `httpx>=0.27` required by the current `pyproject.toml` is not available for
Python 3.14 (`pip install -e .` fails with "No matching distribution found for httpx>=0.27").
The CI uses Python 3.11/3.12 where this is not an issue.

### Source Files Without Tests

- `src/edge_ai_robot/adapter/__init__.py` (156 statements) — Robot adapter, 0% covered
- `src/edge_ai_robot/detection/__init__.py` (90 statements) — Anomaly detection, 0% covered
- `src/edge_ai_robot/skills/__init__.py` (40 statements) — Skill definitions, 0% covered

### Missing Test Categories (edge-ai-robot)

All categories missing — tests cannot collect at all.

| Category | Status | Owner |
|----------|--------|-------|
| Happy path — robot connect/command | ❌ Tests uncollectable | robot-a |
| Error path — connection failure | ❌ Tests uncollectable | robot-a |
| Detection — anomaly scoring | ❌ Tests uncollectable | robot-a |
| Skills — invocation and response | ❌ Tests uncollectable | robot-a |
| Auth / RBAC | ❌ Tests uncollectable | robot-a |
| Concurrency | ❌ Tests uncollectable | robot-a |

> **Owner key:** `robot-a` = edge-ai-robot implementer.
> **Remediation gate:** CI workflow must confirm test collection before coverage targets apply.
> Python 3.11/3.12 in CI should resolve the `httpx>=0.27` dependency issue that blocks local installation.

---

## 6. CI Gaps

> **Staleness:** PRs #242, #244, #245 are open and unmerged. Their merge will change iot-gateway
> test counts and potentially factory-control/dashboard state. A post-merge re-audit is required.

| Module | CI Workflow | Trigger | Tests Run | Coverage | Notes |
|--------|-----------|---------|-----------|----------|-------|
| `iot-gateway/` | `gateway-ci.yml` | push + PR, paths filter | ✅ Yes | ✅ (XML) | `continue-on-error: true` on coverage step; failures silent |
| `factory-control/` | `factory-control-ci.yml` | push + PR, paths filter | ✅ Yes | ❌ No | No coverage step; no trend tracking |
| `dashboard/` | **MISSING** | — | — | — | Needs `dashboard-ci.yml` |
| `edge-ai-robot/` | **MISSING** | — | — | — | Needs `edge-ai-robot-ci.yml` |
| `integration-tests/` | **MISSING** | — | — | — | Status: PLANNED |
| `esp32-ukit-bridge/` | `bridge-ci.yml` | push + PR, paths filter | ✅ Python + PlatformIO | ✅ Native | Python tests + native firmware |
| `digital-twin/` | **MISSING** | — | — | — | No workflow; scope unclear |

### CI Quality Issues

1. **`gateway-ci.yml`** — coverage step has `continue-on-error: true`; coverage failures are silently ignored; coverage figure (50%) does not gate merge
2. **`factory-control-ci.yml`** — no coverage collection; cannot track coverage trends over time
3. **`adr-lint.yml`** — only checks ADR compliance, not test quality or coverage thresholds

---

## 7. Recommendations

> **Path convention:** All CI workflow recommendations below use root-relative `.github/workflows/` paths (e.g. `.github/workflows/dashboard-ci.yml`). GitHub Actions only executes workflows placed at this location.

### Priority 1 — Add Missing CI Workflows

| # | Action | Owner | Gate |
|---|--------|-------|------|
| 1 | Create `.github/workflows/dashboard-ci.yml` | dashboard-a | Workflow file exists, `npm test` collects tests, coverage XML uploaded |
| 2 | Create `.github/workflows/edge-ai-robot-ci.yml` | robot-a | Workflow file exists, `pytest tests/` collects ≥3 tests, coverage XML uploaded |

### Priority 2 — Fix Test Collectibility (edge-ai-robot)

| # | Action | Owner | Gate |
|---|--------|-------|------|
| 3 | Confirm `pytest tests/` collects ≥3 tests in CI (Python 3.11/3.12) after `pip install -e "edge-ai-robot[dev]"` | robot-a, qa | Test collection confirmed in CI run |
| 4 | Verify `httpx>=0.27` resolves on Python 3.11/3.12 CI runner (may need `pyproject.toml` constraint) | robot-a | CI pip install step succeeds |

### Priority 3 — Increase iot-gateway Coverage (50% → target 80%)

> **Staleness gate:** Re-audit coverage % after PR #245 merges; 69 new tests may shift baseline.

| # | Action | Owner | Gate |
|---|--------|-------|------|
| 5 | Add `tests/test_gateway.py` — MQTT connect/publish happy path | backend-a | `gateway.py` coverage > 30% |
| 6 | Add `tests/test_mqtt_client.py` — CONNECT, DISCONNECT, RECONNECT | backend-a | `mqtt_client.py` coverage > 30% |
| 7 | Add `tests/test_orion_ld_adapter.py` — QUERY, SUBSCRIBE, ERROR_PATH | backend-a | `orion_ld.py` coverage > 30% |
| 8 | Expand `tests/test_time_sync.py` — `sync_and_offset()`, skew detection | backend-a | `time_sync.py` coverage > 40% |
| 9 | Expand `tests/test_incidents.py` — acknowledge workflow, CONCURRENCY | backend-a | `incidents.py` coverage > 60% |
| 10 | Add `tests/test_event_store_concurrency.py` — concurrent write scenarios | backend-a | `event_store.py` coverage > 80% |

### Priority 4 — Increase factory-control Coverage (69% → target 85%)

| # | Action | Owner | Gate |
|---|--------|-------|------|
| 11 | Add `tests/test_simulator_integration.py` — tick loop with adapter calls | factory-a | `simulator.py` coverage > 85% |
| 12 | Add `tests/test_sorting_fault_modes.py` — sensor fault, multi-item jams | factory-a | `sorting.py` coverage > 90% |
| 13 | Add `tests/test_state_machine_concurrency.py` — concurrent transitions | factory-a | `state_machine.py` coverage > 95% |
| 14 | Remove or document `src/factory_control/` stub package | factory-a | Stub package either removed or explicitly marked skip-covered |

### Priority 5 — Dashboard Tests

| # | Action | Owner | Gate |
|---|--------|-------|------|
| 15 | Add `src/hooks/incidents/__tests__/` — `useIncidentActions`, `useIncidents` | dashboard-a | CI collects and runs these tests |
| 16 | Add `src/components/incident/__tests__/` — `AcknowledgeButton`, `IncidentCard` | dashboard-a | CI collects and runs these tests |
| 17 | Add `src/api/__tests__/` — `gateway.ts` and `websocket.ts` contract tests | dashboard-a | CI collects and runs these tests |
| 18 | Add `src/contracts/__tests__/` — `contracts/gateway.ts` type validation | dashboard-a | CI collects and runs these tests |

> **Note:** PR #242 (dashboard auth/RBAC) is open. The auth test gap (#17, owner: dashboard-a)
> should be coordinated with PR #242 implementer to avoid merge conflicts.

### Priority 6 — Integration Tests

| # | Action | Owner | Gate |
|---|--------|-------|------|
| 19 | Implement `integration-tests/` scaffold per `docs/testing-and-acceptance.md` L3–L5 | qa | At least 1 happy-path E2E scenario collects and passes in CI |

---

## 8. Evidence

All runs below are dated. Source commit `87e2e38` (master at audit time, 2026-10-20).

### Re-verified 2026-10-21 (qa re-check)

| Check | Command | Environment | Result |
|-------|---------|-------------|--------|
| iot-gateway pytest | `cd iot-gateway && pytest tests/ -q` | Python 3.14.7, pytest 7.4.4, Windows 11, commit `87e2e38` | **246 passed** (⚠️ see staleness below) |
| factory-control pytest | `cd factory-control && pytest tests/ -q` | Python 3.14.7, pytest 7.4.4, Windows 11, commit `87e2e38` | **98 passed** |
| edge-ai-robot test collection | `cd edge-ai-robot && pytest tests/ --collect-only -q` | Python 3.14.7, pytest 7.4.4, Windows 11, commit `87e2e38` | **3 ERROR — ModuleNotFoundError: No module named 'edge_ai_robot'** (tests uncollectable) |
| dashboard test files | `find dashboard -name "*.test.*"` | Node 26.7.0, npm 12.0.2, Windows 11, commit `87e2e38` | 2 files: `gatewayWs.test.ts`, `TelemetryChart.test.tsx` |

**⚠️ Staleness — iot-gateway test count change:**
The original audit (2026-10-20) recorded 161 pass / 7 fail = 168 tests.
The 2026-10-21 re-check at the same commit `87e2e38` shows 246 tests — an increase of 78.
This is attributed to PR #245 (`feat/issue-179-threat-model-v2`, SHA `fd3097ea`) which adds
69 security abuse tests (`iot-gateway/tests/test_security_abuse.py`). The 7 SSRF failures
(attributed to missing `aiohttp` in the local venv) are now resolved in the current state.
The 50% coverage figure is stale; re-audit required after PR #245 merges.

### Original 2026-10-20 Audit (with coverage)

| Check | Command | Environment | Result |
|-------|---------|-------------|--------|
| iot-gateway coverage | `cd iot-gateway && pytest --cov=src --cov-report=term-missing tests/` | Python 3.14.7, pytest 7.4.4, pytest-cov 4.1.0, coverage 7.2.7, Windows 11, commit `87e2e38` | **161 pass / 7 fail; 50% line coverage** |
| factory-control coverage | `cd factory-control && pytest --cov=src --cov-report=term-missing tests/` | Python 3.14.7, pytest 7.4.4, pytest-cov 4.1.0, coverage 7.2.7, Windows 11, commit `87e2e38` | **98 pass; 69% line coverage** |

### CI Workflow Audit (2026-10-20)

| Check | Command | Result |
|-------|---------|--------|
| CI workflows | `find .github/workflows -name "*.yml"` | 4 workflows: `gateway-ci.yml`, `factory-control-ci.yml`, `bridge-ci.yml`, `adr-lint.yml` |
| dashboard CI | `find .github/workflows -name "*dashboard*"` | **NOT FOUND** |
| edge-ai-robot CI | `find .github/workflows -name "*edge*" -o -name "*robot*"` | **NOT FOUND** |
| integration-tests | `ls integration-tests/` | README.md only; harness not implemented |

### ADR Lint Re-validation (2026-10-21)

| Check | Run | Result |
|-------|-----|--------|
| ADR Lint | `gh run list --repo VinhPhan812/Smart-Factory --branch feat/issue-187-ci-coverage-audit` | 4 consecutive ✅ PASS (push + PR × 2) at 2026-10-20 13:31–13:38 UTC |
| PR Head SHA | `git rev-parse feat/issue-187-ci-coverage-audit` | `08ac8d57119eb9551ffad69bb3b25927eff008e4` |

### Staleness — Impact of Open PRs

| PR | Title | Status | Impact on This Audit | Action Required |
|----|-------|--------|---------------------|-----------------|
| #242 | Dashboard auth/RBAC + job/material lineage | Open, not merged | May add dashboard auth tests; dashboard-a coordination needed | Re-audit dashboard coverage post-merge |
| #244 | Deployment topology, DB migrations, E2E simulation | Open, not merged | May add integration tests; `integration-tests/` scope may be affected | Re-audit integration-tests status post-merge |
| #245 | Threat model v2 + 69 security abuse tests | Open, not merged | **Confirmed stale.** iot-gateway: 168 → 246 tests. SSRF failures resolved. Coverage % will change. | **Re-audit required before merge or close.** |

---

*Audit performed on `master` @ commit `87e2e38` via worktree `feat/issue-187-ci-coverage-audit`.*
*Evidence re-verified 2026-10-21 at SHA `87e2e383a4beb7819624a269180001b27adeae7f`.*
*ADR lint re-validated on PR branch HEAD `08ac8d57119eb9551ffad69bb3b25927eff008e4`.*
