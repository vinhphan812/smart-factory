# PR #244 Runtime Evidence Artefact (L2 Simulation)

**Commit SHA:** `e46cee82a084c4a0775b60e871b29060f7abaed3`  
**Environment:** Windows 11 host (Docker Desktop 29.4.2, Docker Compose v5.1.3, Python 3.14.7 host / Python 3.12-slim container runtime)  
**Evidence Level:** L2 simulation (mock MQTT stack, containerized gateway, Orion-LD 1.5.0, MongoDB 5.0 simulation pairing) — no physical hardware (HIL) claims.

## Evidence provenance and scope — historical JSON report

`e2e/simulation/e2e-report.json` is **historical evidence only**. It is not
current-HEAD proof for this PR and must not be used to certify the current
branch tip.

| Field | Recorded, verifiable value |
|---|---|
| JSON `target_sha` | `caebf4a45fc5454eae61cd721b28930eaedf1338` |
| JSON `generated_at` | `2026-10-22T03:32:58Z` |
| Historical CI run that archived the checked-in JSON | [E2E Simulation & Backup-Restore Drill run `39717484035`](https://github.com/vinhphan812/smart-factory/actions/runs/39717484035), artefact `e2e-simulation-report` (`12399980400`, SHA-256 archive digest `f11e5566bd9a64c821362687e5294b06e1353ad8ceae0ec4bde0cecd203528be`) |
| Report-generation source | `e2e/simulation/scenarios/conftest.py` pytest session hook (`pytest_sessionfinish`): it serialises scenario call results, records UTC `generated_at`, and resolves `target_sha` from `TARGET_SHA` or `git rev-parse HEAD`. |

The historical workflow run failed and skipped its backup-restore step; the
JSON's eight passing scenario results therefore do **not** establish an
all-green E2E workflow for `caebf4a...` or any later commit. The source
available in this repository does not provide a separate immutable execution
record for the report's pre-workflow timestamp beyond the report itself and
its subsequent CI artefact upload. That limitation is recorded rather than
backfilled with an inferred run identifier or SHA.

For the exact reviewed head
`8a162fb05e6a5db187876af9eff52087ea23a453`, the authoritative CI evidence is
[E2E Simulation & Backup-Restore Drill run `39789237752`](https://github.com/vinhphan812/smart-factory/actions/runs/39789237752), which completed
SUCCESS on `2026-10-22T13:44:31Z`; its L2 job ran both the Compose smoke-test
and backup-restore-drill steps successfully. That run also uploaded an
`e2e-simulation-report` artefact (`12430756606`, SHA-256 archive digest
`3d25c3b27cc09a3abc736d2ca77fbefc00396a52c4d4cf0fd9de26eb77ec1bcc`), but it
contains the same historical checked-in JSON. It is retained as a workflow
artefact, not relabelled as a regenerated current-HEAD report. CI evidence
here does not demonstrate deployment, production recovery, physical hardware,
or HIL acceptance.

Findings 4 (deployment/supply-chain constraints) and 5 (recovery/hardware
boundaries) remain open and are outside this provenance clarification.

---

## 0. CI Failure Analysis and Root Cause (run `39738892208`, head `b70eb4a`)

The `E2E Simulation & Backup-Restore Drill (L2)` job failed on a clean GitHub
runner. Three distinct defects were identified, each confirmed with direct
evidence rather than inferred from the symptom.

### Root cause 1 — the MQTT publisher was outside the dependency closure

`docker compose up --exit-code-from smoke-tests smoke-tests` starts only the
named target **and its dependency closure**. `smoke-tests` had no edge to
`mock-mqtt-publisher`, so on a clean runner the publisher container was never
created. No publisher means no MQTT traffic, so every gateway ingestion and
WebSocket assertion waited for data that could never arrive.

Evidence:

```text
# CI log of the failed run — no publisher container was ever created
$ gh run view 39738892208 --log-failed | grep -E 'mock-publisher|mock_mqtt'
(no matches)

# Compose dependency graph of the failing target — publisher absent
$ docker compose -f e2e/simulation/docker-compose.e2e.yml \
    --dry-run up --exit-code-from smoke-tests smoke-tests
 Container e2e-mongodb Running
 Container e2e-orion-ld Running
 Container e2e-mqtt Recreate
 Container e2e-iot-gateway Recreate
 Container e2e-factory-control Recreate
 Container e2e-smoke-tests Recreate
```

The earlier local evidence in this document recorded
`Container e2e-mock-publisher Started`; that run had **reused** an already
running stack, so it never exercised the clean-runner dependency closure.

**Fix:** `smoke-tests` and `backup-restore-drill` now depend on
`mock-mqtt-publisher`, and the publisher waits for a healthy gateway before
it starts emitting, so the first event cannot precede the gateway's
subscription.

### Root cause 2 — the drill copied a WAL database with a plain file copy

The gateway stores events in SQLite **WAL** mode. The drill took its working
copy with `shutil.copyfile(LIVE_DB, live_copy)`, which copies only the main
database file. While the gateway is running and has not checkpointed, the
schema and the committed rows live in the `-wal` sidecar, so the copy has no
`events` table at all.

This was reproduced in isolation, reproducing the CI error verbatim:

```text
main file size: 4096
wal exists: True 28872
OLD copyfile -> FAILED: no such table: events
NEW online-backup -> events count: 2
```

Locally the drill passed only because the gateway had previously been
restarted, and a clean close checkpoints the WAL into the main file. A
freshly started gateway — as on a CI runner — does not.

**Fix:** the drill now takes a consistent snapshot through the SQLite online
backup API (`backup_database`), which reads the database and its WAL
atomically and yields a single self-contained file. Regression test
`test_h_snapshot_of_live_database_is_wal_safe` pins this behaviour.

### Root cause 3 — stale scratch artefacts leaked between drill runs

The drill container's writable layer survives between runs, so a
`source-e.bak` from an earlier run already contained an `events` table and
the next run failed with `sqlite3.OperationalError: table events already
exists`.

**Fix:** an autouse fixture clears the scratch directory before every test,
so each test starts from a known state.

---

## 1. Full E2E Compose Stack & Smoke Tests Execution

### Command
```bash
docker compose -f e2e/simulation/docker-compose.e2e.yml up --build --exit-code-from smoke-tests smoke-tests
```

### Real Execution Output
```text
 Container e2e-mongodb Running
 Container e2e-mqtt Running
 Container e2e-orion-ld Running
 Container e2e-iot-gateway Running
 Container e2e-factory-control Running
 Container e2e-mock-publisher Recreate
 Container e2e-mock-publisher Recreated
 Container e2e-mongodb Healthy
 Container e2e-mqtt Healthy
 Container e2e-iot-gateway Healthy
 Container e2e-mock-publisher Starting
 Container e2e-mock-publisher Started
 Container e2e-orion-ld Healthy
 Container e2e-factory-control Healthy
 Container e2e-smoke-tests Starting
 Container e2e-smoke-tests Started
Attaching to e2e-smoke-tests
e2e-smoke-tests  | ============================= test session starts ==============================
e2e-smoke-tests  | platform linux -- Python 3.12.15, pytest-9.1.1, pluggy-1.7.0 -- /usr/local/bin/python
e2e-smoke-tests  | cachedir: .pytest_cache
e2e-smoke-tests  | rootdir: /tests
e2e-smoke-tests  | plugins: anyio-4.15.1, asyncio-1.4.0
e2e-smoke-tests  | asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
e2e-smoke-tests  | collecting ... collected 10 items
e2e-smoke-tests  | 
e2e-smoke-tests  | smoke_tests.py::test_compose_services_started PASSED                     [ 10%]
e2e-smoke-tests  | smoke_tests.py::test_gateway_health PASSED                               [ 20%]
e2e-smoke-tests  | smoke_tests.py::test_orion_ld_version PASSED                             [ 30%]
e2e-smoke-tests  | smoke_tests.py::test_factory_control_health PASSED                       [ 40%]
e2e-smoke-tests  | smoke_tests.py::test_gateway_ingests_events PASSED                       [ 50%]
e2e-smoke-tests  | smoke_tests.py::test_gateway_event_fields PASSED                         [ 60%]
e2e-smoke-tests  | smoke_tests.py::test_websocket_receives_events PASSED                    [ 70%]
e2e-smoke-tests  | smoke_tests.py::test_scenario_manifest_loaded PASSED                     [ 80%]
e2e-smoke-tests  | smoke_tests.py::test_malformed_json_handling PASSED                      [ 90%]
e2e-smoke-tests  | smoke_tests.py::test_snapshot_resync_endpoint PASSED                     [100%]
e2e-smoke-tests  | 
e2e-smoke-tests  | ============================== 10 passed in 2.49s ==============================
e2e-smoke-tests exited with code 0
```

---

## 2. Backup & Restore Drill Execution

### Command
```bash
docker compose -f e2e/simulation/docker-compose.e2e.yml up --build --exit-code-from backup-restore-drill backup-restore-drill
```

### Live database state during the run

The gateway was running with a hot WAL at the time of the drill, matching the
CI condition that previously broke the raw file copy:

```text
$ docker exec e2e-iot-gateway ls -la /app/data
-rw-r--r-- 1 root root   4718592 Oct 22 11:51 gateway.db
-rw-r--r-- 1 root root     32768 Oct 22 11:51 gateway.db-shm
-rw-r--r-- 1 root root  12450672 Oct 22 11:51 gateway.db-wal
```

### Real Execution Output
```text
 Container e2e-mqtt Running
 Container e2e-iot-gateway Running
 Container e2e-mock-publisher Recreate
 Container e2e-mock-publisher Recreated
 Container e2e-mqtt Healthy
 Container e2e-iot-gateway Healthy
 Container e2e-mock-publisher Starting
 Container e2e-mock-publisher Started
 Container e2e-backup-restore-drill Starting
 Container e2e-backup-restore-drill Started
Attaching to e2e-backup-restore-drill
e2e-backup-restore-drill  | ============================= test session starts ==============================
e2e-backup-restore-drill  | platform linux -- Python 3.12.15, pytest-9.1.1, pluggy-1.7.0 -- /usr/local/bin/python
e2e-backup-restore-drill  | cachedir: .pytest_cache
e2e-backup-restore-drill  | rootdir: /tests
e2e-backup-restore-drill  | plugins: asyncio-1.4.0
e2e-backup-restore-drill  | asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
e2e-backup-restore-drill  | collecting ... collected 8 items
e2e-backup-restore-drill  | 
e2e-backup-restore-drill  | backup_restore_drill.py::test_a_backup_of_live_gateway_database_is_valid_and_complete PASSED [ 12%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_b_backup_with_active_wal_and_inflight_write_is_consistent PASSED [ 25%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_c_corrupt_backup_is_rejected_and_live_db_untouched PASSED [ 37%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_d_restore_without_offline_attestation_is_refused PASSED [ 50%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_e_failure_after_swap_rolls_back_to_retained_snapshot PASSED [ 62%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_f_interrupted_restore_is_deterministically_recoverable PASSED [ 75%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_h_snapshot_of_live_database_is_wal_safe PASSED [ 87%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_g_restored_database_reopens_and_answers_queries PASSED [100%]
e2e-backup-restore-drill  | 
e2e-backup-restore-drill  | ============================== 8 passed in 11.20s ===============================
e2e-backup-restore-drill exited with code 0
```

---

## 3. Files Changed by the Fix

| File | Change |
|------|--------|
| `e2e/simulation/docker-compose.e2e.yml` | `smoke-tests` and `backup-restore-drill` now depend on `mock-mqtt-publisher`; the publisher waits for a healthy gateway. |
| `e2e/simulation/backup_restore_drill.py` | Live-database copies use the SQLite online backup API; per-test scratch isolation; new WAL-safety regression test. |

No protocol, contract or public API changed. The gateway, MQTT topics and
AMLP compatibility are untouched.
