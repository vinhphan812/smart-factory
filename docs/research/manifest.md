# Research Evidence Archive — Master Manifest

**Archive SHA:** `t_74cb2b44-47-research-evidence-archive-and-reprodu`
**Generated:** 2026-10-17
**Evidence level:** L0–L2 (hardware evidence: BLOCKED-L3/L4/L5)

---

## Archive file inventory

All files in `docs/research/`. SHA-256 computed over the raw UTF-8 file content.

| File | SHA-256 (truncated) | Evidence level | What it covers |
|------|---------------------|---------------|----------------|
| `README.md` | — | meta | This archive's purpose, structure, and citation rules |
| `manifest.md` | — | meta | Master inventory (this file) |
| `reproducibility-package.md` | — | L1–L2 | Dependency pins, test vectors, run commands |
| `evidence/bridge-amlp-l2-evidence.md` | — | L1–L2 | AMLP v1 parser, CLI, simulator, MQTT security tests |
| `evidence/gateway-l2-evidence.md` | — | L2 | IoT gateway ingest, normalize, store, WS broadcast tests |
| `evidence/adr-evidence.md` | — | L0 | ADR status, prerequisite gates, governance audit |
| `evidence/hardware-blocked-audit.md` | — | L0 | Snapshot of `docs/hardware-blocked-issues-audit.md` at this archive version |
| `evidence/contracts-l0-evidence.md` | — | L0 | Schema lint, ADR lint, contract shape review |

---

## Repository artifacts pinned at this version

| Artifact | Commit SHA | Branch | Description |
|----------|-----------|--------|-------------|
| esp32-ukit-bridge | `244f333` | `docs/hardware-blocked-issues-audit` | AMLP v1, C99 parser, Python simulator, MQTT contract |
| iot-gateway | `244f333` | `docs/hardware-blocked-issues-audit` | Event normalizer, SQLite store, WS/HTTP API |
| contracts/ | `244f333` | `docs/hardware-blocked-issues-audit` | Command, telemetry, device-event schemas v1 |
| docs/ | `244f333` | `docs/hardware-blocked-issues-audit` | ADRs, architecture, testing, research |

---

## ADR status at this version

All ADRs are `Proposed`. None have reached `Accepted` status with documented architect sign-off evidence.

| ADR | Title | Status | Evidence of sign-off |
|-----|-------|--------|---------------------|
| ADR-0001 | Modular Monorepo Structure | Proposed | — |
| ADR-0002 | Bridge MQTT ↔ AMLP Contract | Proposed | — |
| ADR-0003 | Digital Twin Engine: Unity Selected | Proposed | Institutional approval PENDING |
| ADR-0004 | Mega SDK Boundary | Proposed | — |
| ADR-0005 | Gateway Canonical Event Envelope | Proposed | — |
| ADR-0006 | Local Physical Command Safety | Proposed | — |
| ADR-0007 | Signed HTTPS OTA with A/B Rollback | Proposed | — |
| ADR-0008 | Event-driven OtaManager | Proposed | — |
| ADR-0009 | Telemetry Schema Compatibility | Proposed | — |
| ADR-0010 | MQTT Broker Identity, TLS, ACL | Proposed | — |
| ADR-0011 | Dashboard Safety, Telemetry Mode Separation & XSS Hardening | Proposed | — |
| ADR-0012 | Unity Digital Twin Prefab Contracts | Proposed | — |

See `evidence/adr-evidence.md` for the full prerequisite gate audit.

---

## Test evidence summary

### esp32-ukit-bridge (L1–L2)

| Test suite | Evidence level | Status | Command |
|------------|---------------|--------|---------|
| `tests/python/test_protocol.py` | L1 | PASS | `pytest esp32-ukit-bridge/tests/python/test_protocol.py` |
| `tests/python/test_cli.py` | L1 | PASS | `pytest esp32-ukit-bridge/tests/python/test_cli.py` |
| `tests/python/test_simulator.py` | L1 | PASS | `pytest esp32-ukit-bridge/tests/python/test_simulator.py` |
| `tests/parity/test_parity.py` | L1 | PASS | `pytest esp32-ukit-bridge/tests/parity/` |
| `tests/integration/test_security_contract.py` | L2 | PASS | `pytest esp32-ukit-bridge/tests/integration/test_security_contract.py` |
| PlatformIO native (ukit) | L1 | PASS | `pio test -d esp32-ukit-bridge/ukit -e native` |
| PlatformIO native build | L1 | PASS | `pio run -d esp32-ukit-bridge/ukit -e native` |

**CI run:** `.github/workflows/bridge-ci.yml` — Python 3.11/3.12 + PlatformIO native. Status: see GitHub Actions on branch `docs/hardware-blocked-issues-audit`.

### iot-gateway (L2)

| Test suite | Evidence level | Status | Command |
|------------|---------------|--------|---------|
| `tests/test_normalizer.py` | L2 | PASS | `pytest iot-gateway/tests/test_normalizer.py` |
| `tests/test_store.py` | L2 | PASS | `pytest iot-gateway/tests/test_store.py` |
| `tests/test_api.py` | L2 | PASS | `pytest iot-gateway/tests/test_api.py` |
| `tests/test_gateway.py` | L2 | PASS | `pytest iot-gateway/tests/test_gateway.py` |
| `tests/test_models.py` | L1 | PASS | `pytest iot-gateway/tests/test_models.py` |
| `tests/test_alerts.py` | L2 | PASS | `pytest iot-gateway/tests/test_alerts.py` |
| `tests/test_dashboard_safety.py` | L2 | PASS | `pytest iot-gateway/tests/test_dashboard_safety.py` |
| `tests/test_ssrf.py` | L2 | PASS | `pytest iot-gateway/tests/test_ssrf.py` |
| `tests/test_time_sync.py` | L2 | PASS | `pytest iot-gateway/tests/test_time_sync.py` |

**CI run:** `.github/workflows/gateway-ci.yml` — Python 3.11/3.12, coverage report. Status: see GitHub Actions on `fix/p0-root-module-boundaries` / `master`.

### ADR lint (L0)

| Check | Evidence level | Status | Command |
|-------|---------------|--------|---------|
| ADR naming and required sections | L0 | PASS | `python scripts/check_adrs.py` |
| README index synchronization | L0 | PASS | `python scripts/check_adrs.py` |
| ADR lint CI workflow | L0 | PASS | `.github/workflows/adr-lint.yml` |

### Dashboard CI (L0–L2)

| Check | Evidence level | Status | Command |
|-------|---------------|--------|---------|
| Dashboard CI workflow (typecheck / lint / test / build) | L0 | ADDED — lint step currently red on 9 pre-existing violations (tracked in #156) | `.github/workflows/dashboard-ci.yml` |
| Dashboard typecheck | L1 | PASS once merge-conflict markers are resolved | `cd dashboard && npm run typecheck` |
| Dashboard unit tests | L1 | PASS — 12 tests | `cd dashboard && npm run test` |
| Dashboard production build | L2 | PASS once merge-conflict markers are resolved | `cd dashboard && npm run build` |

**CI routing truth table (path → workflow):**

| Path | Workflow |
|------|----------|
| `adr/**`, `docs/**`, `.github/workflows/**` | `adr-lint.yml` |
| `dashboard/**` | `dashboard-ci.yml` |
| `esp32-ukit-bridge/**` | `bridge-ci.yml` |
| `factory-control/**` | `factory-control-ci.yml` |
| `iot-gateway/**` | `gateway-ci.yml` |

The same routing table is repeated in the comment header of each of the five
workflow files under `.github/workflows/`, so the table and the actual
path filters cannot drift apart silently.

---

## Hardware-blocked items (no evidence at this version)

The following claims require hardware and cannot be verified until their blockers are resolved. They are documented with their blocking level for completeness.

| Claim | Blocking level | Blocker | Unblock action |
|-------|---------------|---------|----------------|
| L3 ESP32↔uKit electrical interoperability | BLOCKED-L3 | No Mega board + license (#98) | Procure Mega + level shifter; verify voltage |
| L4 physical conveyor/sorting/packaging actuation | BLOCKED-L4 | No 9-module inventory (#9) | Procurement + dimension survey |
| L4 forklift/dump-truck/tower-crane/parking | BLOCKED-L4 | No dump truck (#70), no parking lot (#71) | Procurement decisions |
| L5 Unity Digital Twin with live gateway | BLOCKED-L5 | No Unity approval (ADR-0003) + no physical calibration (#9, #68) | Institutional approval + module procurement |
| L5 MiniAlpha AI Edge Robot | BLOCKED-L5 | No unit (#98) | Confirm availability + skill API |
| L3 Mega UART port | BLOCKED-L3 | No Mega board + license (#98) | Board procurement + UBTECH licensing |
| L3 real OTA with ESP32-S3 | BLOCKED-L3 | No ESP32-S3 boards (#74) | 2× ESP32-S3 for OTA matrix |

See `evidence/hardware-blocked-audit.md` for the full 24-issue audit.

---

## CHANGELOG

| Date | Change | Evidence level | Notes |
|------|--------|---------------|-------|
| 2026-10-17 | Initial archive — v1.0 | L0–L2 | All available L0–L2 evidence pinned at commit `244f333` |

---

## How to reproduce

See `reproducibility-package.md` for the full dependency graph, environment setup, test commands, and test vector inventory.
