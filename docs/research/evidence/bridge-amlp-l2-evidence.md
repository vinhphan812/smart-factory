# L1–L2 Evidence — ESP32-uKit Bridge (AMLP v1)

**Evidence level:** L1–L2
**Module:** `esp32-ukit-bridge/`
**Archive version:** smart-factory/t_74cb2b44-47-research-evidence-archive-and-reprodu
**Pinned commit:** `244f333`
**Date:** 2026-10-17

---

## What this evidence covers

The esp32-ukit-bridge module implements the ESP32 ↔ uKit UART bridge firmware, an AMLP v1 protocol codec in Python and C99, and a Python AMLP simulator. This file records the evidence for L1 and L2 claims about the protocol.

**Evidence level definitions:**
- **L1** = Python/C99 host unit tests — verifies parser, state machine, CRC algorithm locally
- **L2** = simulated UART/MQTT, mock device — verifies MQTT contract, CLI end-to-end, simulator

---

## AMLP v1 Protocol — L1 evidence

### CRC-16/CCITT-FALSE

**Claim:** The CRC implementation matches the canonical AMLP v1 specification.

**Specification:**
- Polynomial: `0x1021`
- Init: `0xFFFF`
- No reflection on input or output
- XOR out: `0x0000`
- Check vector: body `123456789` → `0x29B1`

**Evidence:**
- `tests/python/test_protocol.py::test_crc_golden_vector` — PASS
- `tests/parity/test_parity.py` — Python ↔ C99 CRC output matches on all test vectors

**Reproduce:**
```bash
pytest esp32-ukit-bridge/tests/python/test_protocol.py -v -k crc
```

### Parser — valid frames

**Claim:** Parser correctly decodes valid CMD, ACK, and TEL frames.

**Evidence:**
- `tests/python/test_protocol.py::test_decode_cmd_frame` — PASS
- `tests/python/test_protocol.py::test_decode_ack_frame` — PASS
- `tests/python/test_protocol.py::test_decode_tel_frame` — PASS

**Reproduce:**
```bash
pytest esp32-ukit-bridge/tests/python/test_protocol.py -v -k decode
```

### Parser — malformed frames

**Claim:** Parser rejects malformed frames with a diagnostic error and does not crash.

**Evidence:**
- `tests/python/test_protocol.py::test_reject_no_prefix` — PASS
- `tests/python/test_protocol.py::test_reject_bad_crc` — PASS
- `tests/python/test_protocol.py::test_reject_oversize` — PASS
- `tests/python/test_protocol.py::test_reject_truncated` — PASS

**Reproduce:**
```bash
pytest esp32-ukit-bridge/tests/python/test_protocol.py -v -k reject
```

### Parser — deduplication

**Claim:** Parser detects and rejects duplicate command IDs within the deduplication window.

**Evidence:**
- `tests/python/test_protocol.py::test_dedupe_within_window` — PASS
- `tests/python/test_protocol.py::test_dedupe_outside_window` — PASS (rejected, ID expired)

**Reproduce:**
```bash
pytest esp32-ukit-bridge/tests/python/test_protocol.py -v -k dedupe
```

---

## CLI — L1 evidence

**Claim:** `amlp` CLI encodes, decodes, and validates AMLP frames correctly.

**Evidence:**
- `tests/python/test_cli.py::test_cli_encode_command` — PASS
- `tests/python/test_cli.py::test_cli_decode_frame` — PASS
- `tests/python/test_cli.py::test_cli_crc` — PASS
- `tests/python/test_cli.py::test_cli_simulate` — PASS (TCP simulator starts and emits telemetry)

**Reproduce:**
```bash
pytest esp32-ukit-bridge/tests/python/test_cli.py -v
```

### CLI usage examples (verified)

```bash
# Encode a command
python -m amlp command --id 102 --name CONVEYOR_START --arg 60
# Output: @CMD,102,CONVEYOR_START,60*C942\r\n

# Decode a frame
python -m amlp decode "@ACK,102,OK*22A0"
# Output: {"type": "ACK", "id": 102, "status": "OK", "crc": "22A0"}

# CRC of golden vector
python -m amlp crc "CMD,102,CONVEYOR_START,60"
# Output: C942

# TCP simulator (starts at 127.0.0.1:8765)
python -m amlp simulate --telemetry-interval 1
```

---

## Simulator — L1–L2 evidence

**Claim:** AMLP TCP simulator produces valid AMLP telemetry frames on a TCP socket and accepts command injection.

**Evidence:**
- `tests/python/test_simulator.py::test_simulator_starts` — PASS
- `tests/python/test_simulator.py::test_simulator_telemetry_output` — PASS
- `tests/python/test_simulator.py::test_simulator_command_injection` — PASS
- `tests/python/test_simulator.py::test_simulator_reconnect` — PASS

**Reproduce:**
```bash
pytest esp32-ukit-bridge/tests/python/test_simulator.py -v
```

---

## MQTT security contract — L2 evidence

**Claim:** The ESP32 bridge MQTT adapter correctly enforces the security contract: topic structure, payload schema, and rejection of malformed or unauthorized payloads.

**Evidence:**
- `tests/integration/test_security_contract.py` — all tests PASS

**Key test cases:**
- `test_mqtt_topic_structure` — verifies topic pattern `smart-factory/{device_id}/command/ack`
- `test_mqtt_payload_schema` — verifies JSON schema for command acknowledgement
- `test_mqtt_malformed_payload_rejection` — verifies bridge rejects malformed JSON without crashing
- `test_mqtt_unauthorized_topic_rejection` — verifies bridge ignores messages on unauthorized topics

**Reproduce:**
```bash
pytest esp32-ukit-bridge/tests/integration/test_security_contract.py -v
```

**Note:** These are L2 tests — they use a mock MQTT broker and do not require real hardware. They verify the bridge's MQTT contract behavior, not physical electrical interoperability.

---

## C99 reference — L1 evidence

**Claim:** The portable C99 AMLP reference implementation compiles and runs on a native host, and its output matches the Python implementation on all test vectors.

**Evidence:**
- `pio test -d esp32-ukit-bridge/ukit -e native` — all native tests PASS
- `pio run -d esp32-ukit-bridge/ukit -e native` — build exits 0
- `tests/parity/test_parity.py` — Python ↔ C99 output matches for all AMLP frames

**Reproduce:**
```bash
pio test -d esp32-ukit-bridge/ukit -e native
pio run -d esp32-ukit-bridge/ukit -e native
pytest esp32-ukit-bridge/tests/parity/ -v
```

**Important caveat:** Native build verifies the C99 reference compiles on a host machine. It does **not** prove compatibility with real uKit hardware. ESP32 firmware flashing and GPIO/UART wiring require L3 bench evidence.

---

## Cross-language parity — L1 evidence

**Claim:** Python and C99 implementations produce identical output for all defined test vectors.

**Evidence:**
- `tests/parity/test_parity.py` — all parity tests PASS

**Reproduce:**
```bash
pytest esp32-ukit-bridge/tests/parity/ -v
```

---

## CI evidence

| Job | Evidence level | Status | Notes |
|-----|---------------|--------|-------|
| Python 3.11 + 3.12 unit tests | L1 | CI green on `244f333` | `.github/workflows/bridge-ci.yml` |
| PlatformIO native (ukit) | L1 | CI green on `244f333` | C99 reference only, no hardware |
| PlatformIO ESP32 build (when present) | L1 | CI green | Firmware compile check only; no flashing |

**Important:** ESP32 firmware build (PlatformIO `esp32` env) is a compile-time check. It does not verify UART wiring, electrical levels, or runtime behavior on real hardware. That is L3 evidence.

---

## Hardware-blocked claims from this module

| Claim | Blocking level | Blocker | Evidence gate |
|-------|---------------|---------|--------------|
| ESP32 UART TX → broker MQTT telemetry | BLOCKED-L3 | Bridge firmware TEL→MQTT not yet implemented | See `docs/architecture/overview.md` |
| ESP32↔uKit electrical interoperability | BLOCKED-L3 | No Mega board + license (#98) | Voltage verification required |
| Real GPIO/UART wiring | BLOCKED-L3 | No level verification | Multimter + logic analyzer required |
| ESP32 firmware flashing | BLOCKED-L3 | No ESP32-S3 boards (#74) | Physical board required |
| Physical OTA with real ESP32-S3 | BLOCKED-L3 | No ESP32-S3 boards (#74) | Bench board matrix required |

---

## Related documents

- Protocol spec: `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md`
- Test vectors: `esp32-ukit-bridge/shared/protocol-spec/test-vectors.json`
- MQTT contract: `esp32-ukit-bridge/docs/mqtt-contract.md`
- Safety model: `esp32-ukit-bridge/docs/threat-safety-model.md`
