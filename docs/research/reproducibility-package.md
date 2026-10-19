# Reproducibility Package

**Owner:** Issue #47
**Archive version:** smart-factory/t_74cb2b44-47-research-evidence-archive-and-reprodu
**Evidence levels:** L0–L2
**Date:** 2026-10-17

This package documents exactly how to reproduce every L0–L2 claim in the archive without hardware. Hardware-blocked claims (L3/L4/L5) are excluded — see `manifest.md` and `evidence/hardware-blocked-audit.md`.

---

## Repository pinning

Every claim is tied to a specific commit. Do NOT use `latest` or a moving branch reference when reproducing evidence.

```bash
# Clone and check out the pinned version
git clone https://github.com/vinhphan812/smart-factory.git
cd smart-factory
git checkout 244f333   # pinned archive commit
git checkout -b my-reproduction-run
```

---

## Environment setup

### Python (esp32-ukit-bridge + iot-gateway)

```bash
# Python 3.11 or 3.12 required
python3 --version   # must be 3.11 or 3.12

# Install esp32-ukit-bridge with test dependencies
pip install -e "esp32-ukit-bridge[test]"

# Install iot-gateway with dev dependencies
pip install -e "iot-gateway[dev]"

# Install ADR lint tool (if checking L0 governance)
pip install -r scripts/requirements-lint.txt 2>/dev/null || true
```

### PlatformIO (C99 reference only — native build, no hardware)

```bash
# PlatformIO Core (Python-based, no hardware required for native target)
pip install --upgrade platformio intelhex

# Verify ukit C99 reference compiles natively (no hardware)
pio test -d esp32-ukit-bridge/ukit -e native
pio run -d esp32-ukit-bridge/ukit -e native
```

Note: The native PlatformIO build verifies the C99 reference code compiles on a host machine. It does **not** prove compatibility with real uKit hardware. This is L1 evidence only.

---

## Test commands and expected results

Run each command from the repository root (`D:\esp32\Smart Factory`).

### L1 — esp32-ukit-bridge unit tests

```bash
# AMLP v1 parser and frame handling
pytest esp32-ukit-bridge/tests/python/test_protocol.py -v

# CLI: encode, decode, command, crc
pytest esp32-ukit-bridge/tests/python/test_cli.py -v

# TCP simulator and telemetry injection
pytest esp32-ukit-bridge/tests/python/test_simulator.py -v

# Cross-language parity (Python ↔ C99 AMLP output)
pytest esp32-ukit-bridge/tests/parity/ -v
```

**Expected:** All pass with exit code 0.

### L2 — esp32-ukit-bridge integration tests

```bash
# MQTT security contract: malformed frames, auth rejection, topic enforcement
pytest esp32-ukit-bridge/tests/integration/test_security_contract.py -v
```

**Expected:** All pass with exit code 0.

### L1 — PlatformIO native (C99 reference, no hardware)

```bash
# C99 unit tests (native target only)
pio test -d esp32-ukit-bridge/ukit -e native

# C99 build (compile check only)
pio run -d esp32-ukit-bridge/ukit -e native
```

**Expected:** Test results show all tests passed; build exits 0.

### L2 — iot-gateway integration tests

```bash
# Core ingest, normalize, store, broadcast
pytest iot-gateway/tests/test_normalizer.py -v
pytest iot-gateway/tests/test_store.py -v
pytest iot-gateway/tests/test_gateway.py -v
pytest iot-gateway/tests/test_api.py -v

# Schema and models
pytest iot-gateway/tests/test_models.py -v

# Alerts and safety
pytest iot-gateway/tests/test_alerts.py -v
pytest iot-gateway/tests/test_dashboard_safety.py -v

# Security
pytest iot-gateway/tests/test_ssrf.py -v
pytest iot-gateway/tests/test_time_sync.py -v
```

**Expected:** All pass with exit code 0.

### L0 — ADR lint (no code execution)

```bash
# Check ADR naming, required sections, README index sync
python scripts/check_adrs.py

# CI workflow equivalent
# See: .github/workflows/adr-lint.yml
```

**Expected:** Linter reports pass (no errors or warnings for ADRs in Proposed/Accepted state).

---

## Test vector inventory

All test vectors are in `esp32-ukit-bridge/shared/protocol-spec/test-vectors.json`.

| Vector ID | Frame | Purpose | Expected output |
|-----------|-------|---------|-----------------|
| VT-001 | `@CMD,102,CONVEYOR_START,60*C942\r\n` | Valid command | parsed: type=CMD, id=102, name=CONVEYOR_START, arg=60, crc=0xC942 |
| VT-002 | `@ACK,102,OK*22A0\r\n` | Valid acknowledgement | parsed: type=ACK, id=102, status=OK, crc=0x22A0 |
| VT-003 | `@TEL,CONVEYOR,RUNNING,60,SENSOR1=1*0942\r\n` | Telemetry event | parsed: type=TEL, device=CONVEYOR, state=RUNNING, rpm=60, sensors |
| VT-004 | `@CMD,99,BAD_CRC,0*0000\r\n` | Bad CRC | rejection: CRC mismatch |
| VT-005 | Invalid frame (no `@` prefix) | Malformed frame | rejection: frame format error |
| VT-006 | Oversize frame (>256 bytes) | Boundary test | rejection: frame size exceeded |
| VT-007 | CRC golden vector body `123456789` | CRC-16/CCITT reference | expected: 0x29B1 |

CRC spec: CRC-16/CCITT-FALSE, poly=0x1021, init=0xFFFF, refin=false, refout=false, xorout=0x0000.

---

## Dependency graph

```
esp32-ukit-bridge/
  Python 3.11 | 3.12
  pytest 8.x
  amlp (local, editable install)
  intelhex  (for hex parsing in tests)
  platformio-core  (native build only)
    └── C++ toolchain (host gcc/clang via PlatformIO toolchain)

iot-gateway/
  Python 3.11 | 3.12
  pytest 8.x
  pytest-asyncio
  aiosqlite
  websockets
  paho-mqtt
  httpx  (for SSRF test)
  pytest-cov  (optional)

scripts/
  check_adrs.py
    Python 3.11+
    standard library only (no external deps)
```

---

## Reproducing a specific claim

To reproduce a specific claim from the archive:

1. Check the manifest for the file and SHA.
2. Identify the test command from the table above.
3. Run in a clean environment.
4. Record:
   - `git describe --tags --exact-match 2>/dev/null || git rev-parse HEAD`
   - Test command and exit code
   - Python version: `python3 --version`
   - PlatformIO version: `pio --version`
5. If the run produces output files (coverage, logs), store them alongside the evidence.

---

## Versioning policy

- Archive versions are tied to git branch names on `smart-factory/t_74cb2b44-47-research-evidence-archive-and-reprodu`.
- Each archive version pins a specific commit SHA in `manifest.md`.
- Evidence files in `evidence/` are immutable once published.
- New evidence files get versioned names (e.g. `gateway-l2-evidence-v2.md`).
- The manifest's `CHANGELOG` records each update.

---

## Limitations

- L2 tests use mock devices and simulated MQTT — they verify software behavior, not physical actuation.
- L2 tests cannot substitute for L3/L4/L5 hardware evidence.
- ADR `Accepted` status requires architect sign-off that is not captured in this reproducibility package.
- Python 3.10 or earlier is not tested; Python 3.13 is not tested.
- PlatformIO ESP32 target requires ESP32-S3 hardware and is not covered here (L3 evidence).
