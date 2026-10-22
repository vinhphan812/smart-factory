# Coverage Audit — October 2026 (Reproducible Bounded Snapshot)

> **⚠️ DATED AUDIT — NOT A CI COMPLIANCE CERTIFICATION**  
> This is a point-in-time L1 local result, not a current-master quality gate, hardware evidence,
> or a claim that all environments pass. Results below apply only to the named revision, command,
> and tool versions. Re-run the documented commands after source, dependency, or CI changes.

**Issue:** #187  
**Audit evidence captured:** 2026-10-22  
**Auditor:** dev-qa  
**PR:** #234, `feat/issue-187-ci-coverage-audit` → `master`  
**Historical source revision:** `87e2e383a4beb7819624a269180001b27adeae7f`  
**Evidence artifacts:**
- [`coverage-audit-2026-10-87e2e38-iot-gateway.txt`](evidence/coverage-audit-2026-10-87e2e38-iot-gateway.txt)
- [`coverage-audit-2026-10-87e2e38-factory-control.txt`](evidence/coverage-audit-2026-10-87e2e38-factory-control.txt)

## 1. Evidence rules and provenance

A coverage number is retained only where a local run completed and the full terminal capture is
versioned above. Counts such as source LOC and test LOC from the prior draft are intentionally
not retained: they were not captured by a reproducible command.

| Tag | Meaning |
|---|---|
| **[measured]** | The exact coverage command completed; its SHA, environment, and capture are linked. |
| **[uncollectable]** | Test collection was attempted and failed before tests ran; it is **not** coverage. |
| **[not measured]** | Files/workflows were inspected but no coverage command was run. |
| **[not audited]** | Outside this bounded local audit. |

A percentage without a tag is a target, not a result. `0% [uncollectable]` is never a measured
coverage value.

The versioned captures in `docs/quality/evidence/` are raw terminal output with absolute local
paths replaced by `<PYTHON_SITE_PACKAGES>`, `<PYTHON_STDLIB>` and `<REPO_ROOT>` placeholders. No
other content was altered; each capture states the redaction and the captured UTC timestamp.

---

## 2. Bounded module summary

All observed figures in this table are at `87e2e38`; the command and environment are detailed in
sections 3–6. They do not describe later commits or open PR heads.

| Module | Test/coverage observation | CI workflow at `87e2e38` | Status |
|---|---|---|---|
| `iot-gateway/` | **246 passed; 79% [measured]** | `gateway-ci.yml` | L1 local evidence; CI coverage is non-blocking |
| `factory-control/` | **98 passed; 69% [measured]** | `factory-control-ci.yml` | L1 local evidence; workflow has no coverage step |
| `dashboard/` | 2 test files; **coverage unknown [not measured]** | no dashboard workflow found | Not a coverage result |
| `edge-ai-robot/` | 3 collection errors; **coverage unknown [uncollectable]** | no edge/robot workflow found | Import path/dependency setup must be verified |
| `integration-tests/` | `README.md` only; **not measured** | no workflow found | Harness not audited as executable |
| `esp32-ukit-bridge/` | **not audited** | `bridge-ci.yml` found | Outside scope of local coverage runs |
| `digital-twin/` | **not audited** | no workflow found | Outside scope of local coverage runs |

---

## 3. `iot-gateway/` — reproducible coverage evidence

### Run identity

- **SHA:** `87e2e383a4beb7819624a269180001b27adeae7f`
- **Working directory:** `iot-gateway/` in a detached worktree at that SHA
- **Command:** `python -m pytest --cov=src --cov-report=term-missing tests/`
- **OS/interpreter:** Windows 11; Python 3.14.7
- **Test tooling:** pytest 8.4.2; pytest-cov 7.1.0; coverage 7.16.2
- **Relevant installed dependency:** aiohttp 3.14.3
- **Result:** **246 passed, 632 warnings; total line coverage 79%**
- **Full output:** [`coverage-audit-2026-10-87e2e38-iot-gateway.txt`](evidence/coverage-audit-2026-10-87e2e38-iot-gateway.txt)

The prior `161 pass / 7 fail / 50%` assertion is **unverified and withdrawn**. It is not used as a
baseline, does not establish a historical regression, and must not be attributed to `87e2e38`.
Likewise, this revision already contains `tests/test_gateway.py` and `tests/test_orion_ld.py`;
recommendations below therefore expand these files rather than claiming they need creation.

`iot-gateway/pyproject.toml` at this SHA requires `aiohttp>=3.9.0`. The reproducible environment
had aiohttp installed. No claim is retained that the same environment both listed aiohttp and
failed because it was absent.

### Per-module coverage from the captured output

| File | Statements | Missing | Coverage | Evidence-based gap note |
|---|---:|---:|---:|---|
| `src/iot_gateway/adapters/orion_ld.py` | 261 | 51 | **78% [measured]** | Error and branch paths remain in capture |
| `src/iot_gateway/alerts.py` | 212 | 14 | **94% [measured]** | Capture identifies remaining lines |
| `src/iot_gateway/api.py` | 176 | 25 | **83% [measured]** | Capture identifies remaining lines/branches |
| `src/iot_gateway/cli.py` | 29 | 29 | **0% [measured]** | CLI path was not executed |
| `src/iot_gateway/config.py` | 9 | 2 | **78% [measured]** | Two lines not executed |
| `src/iot_gateway/event_normalizer.py` | 73 | 2 | **97% [measured]** | Narrow residual gap |
| `src/iot_gateway/event_store.py` | 143 | 15 | **88% [measured]** | Recovery/branch lines remain |
| `src/iot_gateway/gateway.py` | 100 | 33 | **65% [measured]** | Remaining gateway paths listed in capture |
| `src/iot_gateway/incidents.py` | 105 | 46 | **47% [measured]** | Lowest non-CLI measured module |
| `src/iot_gateway/models.py` | 32 | 0 | **100% [measured]** | All listed statements executed |
| `src/iot_gateway/mqtt_client.py` | 49 | 37 | **20% [measured]** | Connection/retry paths are a priority |
| `src/iot_gateway/safety_gate.py` | 143 | 6 | **95% [measured]** | Small residual gap |
| `src/iot_gateway/time_sync.py` | 82 | 12 | **85% [measured]** | Snapshot/synchronization paths remain |
| **TOTAL** | **1,417** | **272** | **79% [measured]** | 314 branches, 29 partial branches |

The capture also reports package initializers at 100%; they are omitted above because they are not
separate remediation priorities. Percentages include branch-aware coverage output but the reported
`Cover` column is the tool's aggregate percentage.

### Test-to-module mapping at `87e2e38`

The runner collected these executable test modules: `test_alerts.py`, `test_api.py`,
`test_dashboard_safety.py`, `test_gateway.py`, `test_models.py`, `test_normalizer.py`,
`test_orion_ld.py`, `test_safety_gate.py`, `test_ssrf.py`, `test_store.py`, and
`test_time_sync.py`. `conftest.py`, `run_safety_gate_tests.py`, and
`test_safety_gate_conftest.py` also exist in the test tree but are not listed as collected test
modules by the run output. The mapping below is based on names and observed collection only; it is
not a proof of one-to-one coverage ownership.

| Source area | Relevant existing test module(s) | Follow-up owner | Gate |
|---|---|---|---|
| Gateway orchestration | `test_gateway.py` | backend-a | Raise `gateway.py` from 65% with targeted failure/retry tests |
| MQTT client | no dedicated `test_mqtt_client.py` | backend-a | Exercise connect, disconnect, retry, QoS and TLS failure paths |
| Orion-LD adapter | `test_orion_ld.py` | backend-a | Add error/redirect/subscription negative paths; retain ≥78% |
| Incidents | no dedicated `test_incidents.py` | backend-a | Exercise acknowledgement, timeout, and concurrent updates |
| Event store | `test_store.py` | backend-a | Add recovery/concurrent-write scenarios |
| Time synchronization | `test_time_sync.py` | backend-a | Add snapshot ordering/skew/recovery cases |
| API and dashboard safety | `test_api.py`, `test_dashboard_safety.py` | backend-a | Add auth/error/concurrent WebSocket cases where contract requires them |
| SSRF protections | `test_ssrf.py` | security | Preserve passing negative/security paths |

### Bounded finding

This run is evidence of L1 behavior only. It does not verify live MQTT, broker reconnect behavior,
TLS credentials, physical interlocks, or HIL safety. Those need suitable L2–L4 environments under
`docs/testing-and-acceptance.md`.

---

## 4. `factory-control/` — reproducible coverage evidence

### Run identity

- **SHA:** `87e2e383a4beb7819624a269180001b27adeae7f`
- **Working directory:** `factory-control/` in a detached worktree at that SHA
- **Command:** `python -m pytest --cov=src --cov-report=term-missing tests/`
- **OS/interpreter:** Windows 11; Python 3.14.7
- **Test tooling:** pytest 8.4.2; pytest-cov 7.1.0; coverage 7.16.2
- **Result:** **98 passed, 1 warning; total line coverage 69%**
- **Full output:** [`coverage-audit-2026-10-87e2e38-factory-control.txt`](evidence/coverage-audit-2026-10-87e2e38-factory-control.txt)

### Per-module coverage from the captured output

| File | Statements | Missing | Coverage |
|---|---:|---:|---:|
| `src/__init__.py` | 1 | 1 | **0% [measured]** |
| `src/adapters/__init__.py` | 103 | 4 | **96% [measured]** |
| `src/adapters/adapters.py` | 2 | 2 | **0% [measured]** |
| `src/adapters/base.py` | 66 | 12 | **82% [measured]** |
| `src/adapters/conveyor.py` | 142 | 7 | **95% [measured]** |
| `src/adapters/sorting.py` | 183 | 34 | **81% [measured]** |
| `src/factory_control/__init__.py` | 3 | 3 | **0% [measured]** |
| `src/factory_control/adapters/__init__.py` | 3 | 3 | **0% [measured]** |
| `src/factory_control/adapters/base.py` | 57 | 57 | **0% [measured]** |
| `src/factory_control/adapters/conveyor.py` | 119 | 119 | **0% [measured]** |
| `src/factory_control/models.py` | 45 | 45 | **0% [measured]** |
| `src/models.py` | 116 | 5 | **96% [measured]** |
| `src/simulator.py` | 115 | 34 | **70% [measured]** |
| `src/state_machine.py` | 120 | 7 | **94% [measured]** |
| **TOTAL** | **1,075** | **333** | **69% [measured]** |

### Follow-up priorities

| Priority | Action | Owner | Gate |
|---:|---|---|---|
| 1 | Add simulator/adaptor integration tests | factory-a | `simulator.py` coverage exceeds the current 70% measurement |
| 2 | Cover sorting fault and rejection paths | factory-a | `sorting.py` coverage exceeds the current 81% measurement |
| 3 | Resolve or document the parallel `src/factory_control/` package | factory-a | Explicit ownership/exclusion decision with test evidence |
| 4 | Add CI coverage collection | factory-a | Artifact or terminal report produced by CI (not merely a test pass) |

---

## 5. Bounded file and workflow inspection (not coverage)

The following outputs were inspected at `87e2e38` and are deliberately not represented as
percentages:

| Scope | Command | Environment | Result | Interpretation |
|---|---|---|---|---|
| Dashboard test files | `find dashboard -name '*.test.*' -printf '%P\n' \| sort` | Node 26.7.0; npm 12.0.2; Windows 11 | `src/tests/gatewayWs.test.ts`; `src/tests/TelemetryChart.test.tsx` | Two files exist; no coverage was run |
| Edge robot collection | `cd edge-ai-robot && python -m pytest tests/ --collect-only -q` | Python 3.14.7; pytest 8.4.2; Windows 11 | no tests collected; 3 `ModuleNotFoundError: edge_ai_robot` errors | **[uncollectable]**, not 0% coverage |
| Workflows | `find .github/workflows -maxdepth 1 -type f -name '*.yml' -printf '%f\n' \| sort` | Windows 11; SHA `87e2e38` | `adr-lint.yml`, `bridge-ci.yml`, `factory-control-ci.yml`, `gateway-ci.yml` | No dashboard, edge-robot, or integration workflow found |
| Integration harness | `find integration-tests -maxdepth 2 -type f -printf '%P\n' \| sort` | Windows 11; SHA `87e2e38` | `README.md` | No executable test claim is made |

### CI configuration observations at `87e2e38`

- `gateway-ci.yml` installs `iot-gateway[dev]`, tests Python 3.11/3.12, and invokes a coverage
  command, but its coverage step has `continue-on-error: true`; a successful test job is not
  evidence that the coverage command passed.
- `factory-control-ci.yml` tests Python 3.11/3.12 but has no coverage command.
- The absence of the named workflow files is a file-inspection result, not evidence that a module
  has zero tests or zero coverage.

---

## 6. Remediation matrix

| Priority | Action | Owner | Verifiable gate |
|---:|---|---|---|
| 1 | Add a dedicated MQTT-client test module | backend-a | New run raises `mqtt_client.py` above 20% and includes negative reconnect/timeout cases |
| 2 | Expand existing `tests/test_gateway.py` | backend-a | New run raises `gateway.py` above 65% with failure/retry tests |
| 3 | Expand existing `tests/test_orion_ld.py` | backend-a | New run covers error/subscription paths and retains/improves 78% |
| 4 | Add incident lifecycle tests | backend-a | New run raises `incidents.py` above 47%; includes concurrent/timeout case |
| 5 | Remove or cover CLI blind spot | backend-a | New run raises `cli.py` above 0%, or a reviewed explicit exclusion exists |
| 6 | Add dashboard CI and coverage capture | dashboard-a | CI uploads/reports coverage and has a passing/error/loading test set |
| 7 | Make edge robot collection reproducible | robot-a | CI installation and `--collect-only` output demonstrate collection before setting any target |
| 8 | Add an integration harness only at an appropriate declared level | qa | At least one L2+ scenario has a command, declared simulator/hardware mix, and CI evidence |

The numeric thresholds in the gates are intentionally comparisons to this snapshot, not release
thresholds. They must be revisited when dependencies or source change.

---

## 7. Reproduction procedure

Use a clean detached worktree at the source SHA and the same interpreter/dependency environment
when comparing to the evidence artifacts:

```bash
git worktree add --detach <clean-worktree> 87e2e383a4beb7819624a269180001b27adeae7f
cd <clean-worktree>
git rev-parse HEAD
python --version
python -m pytest --version
python -m pip show pytest pytest-cov coverage aiohttp
cd iot-gateway && python -m pytest --cov=src --cov-report=term-missing tests/
cd ../factory-control && python -m pytest --cov=src --cov-report=term-missing tests/
```

Expected under the captured environment: iot-gateway **246 passed / 79%** and factory-control
**98 passed / 69%**. Different dependency versions, Python versions, platforms, or working-tree
content can produce different results and must be recorded rather than treated as failures of this
dated evidence.

---

## 8. PR-head verification record

The documented commands were re-run on the PR branch after this report was corrected. The PR-head
runtime tree is unchanged since the audited revision, which is verified, not assumed:

```bash
git diff 87e2e383a4beb7819624a269180001b27adeae7f 7072fb328a2223238dd6e85273dd13192fde8aa7 -- iot-gateway factory-control
# (no output: iot-gateway/ and factory-control/ are byte-identical to 87e2e38)
```

That empty diff is why the `87e2e38` figures in sections 3 and 4 are also the current PR-head
figures for those two modules. The commits after `87e2e38` in this branch touch only
`docs/quality/` and `.gitignore`.

### Verified run on PR head `7072fb328a2223238dd6e85273dd13192fde8aa7`

- **Environment:** Windows 11; Python 3.14.7; pytest 8.4.2; pytest-cov 7.1.0; coverage 7.16.2;
  aiohttp 3.14.3
- **Captured:** 2026-10-22T01:23Z

| Command | Result | Capture |
|---|---|---|
| `cd iot-gateway && python -m pytest --cov=src --cov-report=term-missing tests/` | **246 passed; 79% total coverage** | [`coverage-audit-2026-10-prhead-iot-gateway.txt`](evidence/coverage-audit-2026-10-prhead-iot-gateway.txt) |
| `cd factory-control && python -m pytest --cov=src --cov-report=term-missing tests/` | **98 passed; 69% total coverage** | [`coverage-audit-2026-10-prhead-factory-control.txt`](evidence/coverage-audit-2026-10-prhead-factory-control.txt) |
| `cd edge-ai-robot && python -m pytest tests/ --collect-only -q` | **no tests collected; 3 `ModuleNotFoundError: edge_ai_robot` errors [uncollectable]** | [`coverage-audit-2026-10-prhead-edge-ai-robot-collect.txt`](evidence/coverage-audit-2026-10-prhead-edge-ai-robot-collect.txt) |

The commit that follows this one only appends this section; it does not change any measured code
path, so the recorded results remain valid for the PR head. Any later code, dependency, or CI
change invalidates them and requires a rerun.

### CI evidence

The PR's only required check is `ADR Lint & Architecture Governance Gate`. Its run URLs and
outcomes for each pushed head are quoted in the PR conversation. ADR-lint success is an ADR
compliance signal only; it is **not** a test, coverage, or regression signal, and is not used as
evidence anywhere in this report.
