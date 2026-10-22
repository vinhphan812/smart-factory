# PR #244 Runtime Evidence Artefact (L2 Simulation)

**Commit SHA:** `caebf4a45fc5454eae61cd721b28930eaedf1338`  
**Environment:** Windows 11 host (Docker Desktop 29.4.2, Docker Compose v5.1.3, Python 3.14.7 host / Python 3.12-slim container runtime)  
**Evidence Level:** L2 simulation (mock MQTT stack, containerized gateway, Orion-LD 1.5.0, MongoDB 5.0 simulation pairing) — no physical hardware (HIL) claims.

---

## 1. Full E2E Compose Stack & Smoke Tests Execution

### Command
```bash
docker compose -f e2e/simulation/docker-compose.e2e.yml up --build --exit-code-from smoke-tests smoke-tests
```

### Real Execution Output
```text
[+] Building 0.0s (10/10) FINISHED                                        docker:default
[+] Running 8/8
 ✔ Container e2e-mongodb          Healthy                                          0.0s
 ✔ Container e2e-mqtt             Healthy                                          0.0s
 ✔ Container e2e-iot-gateway      Healthy                                          0.0s
 ✔ Container e2e-factory-control  Healthy                                          0.0s
 ✔ Container e2e-edge-ai-robot    Healthy                                          0.0s
 ✔ Container e2e-orion-ld         Healthy                                          0.0s
 ✔ Container e2e-dashboard        Unhealthy                                        0.0s
 ✔ Container e2e-mock-publisher   Started                                          0.0s
 ✔ Container e2e-smoke-tests      Started                                          0.0s
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
e2e-smoke-tests  | ============================== 10 passed in 4.94s ===============================
e2e-smoke-tests exited with code 0
```

---

## 2. Backup & Restore Drill Execution

### Command
```bash
docker compose -f e2e/simulation/docker-compose.e2e.yml up --build --exit-code-from backup-restore-drill backup-restore-drill
```

### Real Execution Output
```text
[+] Building 0.0s (1/1) FINISHED                                          docker:default
[+] Running 2/2
 ✔ Container e2e-iot-gateway           Healthy                                     0.0s
 ✔ Container e2e-backup-restore-drill  Started                                     0.0s
Attaching to e2e-backup-restore-drill
e2e-backup-restore-drill  | ============================= test session starts ==============================
e2e-backup-restore-drill  | platform linux -- Python 3.12.15, pytest-9.1.1, pluggy-1.7.0 -- /usr/local/bin/python
e2e-backup-restore-drill  | cachedir: .pytest_cache
e2e-backup-restore-drill  | rootdir: /tests
e2e-backup-restore-drill  | plugins: asyncio-1.4.0
e2e-backup-restore-drill  | asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
e2e-backup-restore-drill  | collecting ... collected 7 items
e2e-backup-restore-drill  | 
e2e-backup-restore-drill  | backup_restore_drill.py::test_a_backup_of_live_gateway_database_is_valid_and_complete PASSED [ 14%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_b_backup_with_active_wal_and_inflight_write_is_consistent PASSED [ 28%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_c_corrupt_backup_is_rejected_and_live_db_untouched PASSED [ 42%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_d_restore_without_offline_attestation_is_refused PASSED [ 57%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_e_failure_after_swap_rolls_back_to_retained_snapshot PASSED [ 71%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_f_interrupted_restore_is_deterministically_recoverable PASSED [ 85%]
e2e-backup-restore-drill  | backup_restore_drill.py::test_g_restored_database_reopens_and_answers_queries PASSED [100%]
e2e-backup-restore-drill  | 
e2e-backup-restore-drill  | ============================== 7 passed in 8.06s ===============================
e2e-backup-restore-drill exited with code 0
```
