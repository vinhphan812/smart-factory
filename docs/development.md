# Development and Testing

## Requirements

- Python 3.11 or newer.
- `pytest` 8.x for Python tests.
- PlatformIO Core for C99 and ESP32 firmware build/test.
- A native C/C++ compiler compatible with PlatformIO.

## Python AMLP tools

A virtual environment is recommended to avoid polluting the system Python:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

python -m pip install -e ".[test]"
pytest tests/python
```

Pytest is configured with `tools` in `pythonpath`, so when pytest is available the tests can also be run directly:

```bash
pytest tests/python
```

CLI commands:

```bash
amlp crc "CMD,102,CONVEYOR_START,60"
amlp command --id 102 --name CONVEYOR_START --arg 60
amlp command --id 43 --name CONVEYOR_STOP
amlp encode --type TEL --field CONVEYOR --field RUNNING --field 60 --field SENSOR1=1
amlp decode "@ACK,102,OK*22A0"
amlp simulate --host 127.0.0.1 --port 8765
```

The simulator uses a TCP byte stream to replace UART during development. Valid commands receive ACK; STATE telemetry is emitted periodically. Dedupe cache holds 8 correlation ids, matching the C99 endpoint.

## C99 reference endpoint

```bash
pio test -d ukit -e native
pio run -d ukit -e native
```

The `ukit/lib/amlp` library depends only on the C99 standard library. `ukit/examples/basic/main.c` demonstrates:

1. Callback to send bytes over UART.
2. Callback to handle commands/GPIO.
3. Feeding RX bytes and millisecond timestamps into the parser.
4. Calling timeout when UART is idle and emitting periodic telemetry.

This is a reference, not complete uKit firmware. When the real SDK is available:

- Replace UART/clock callbacks with SDK APIs.
- Confirm RX0/TX0 pin assignments, logic level, buffer sizes, IRQ/DMA and thread-safety.
- Do not call long-blocking handlers from an ISR.
- Add watchdog and error handling appropriate to the platform.

## AMLP synchronisation

The canonical sources are:

- `shared/protocol-spec/AMLP-v1.md`.
- `shared/protocol-spec/test-vectors.json`.

When changing the protocol, update Python, ESP32, C99, tests and docs simultaneously. Keep these golden vectors:

```
@CMD,102,CONVEYOR_START,60*C942\r\n
@ACK,102,OK*22A0\r\n
@TEL,CONVEYOR,RUNNING,60,SENSOR1=1*0942\r\n
```

and CRC `123456789 -> 0x29B1`. Incompatible changes must include a versioning strategy as described in the spec.

## CI

`.github/workflows/ci.yml` runs:

1. Python 3.11/3.12: install package/test dependencies and run `pytest tests/python`.
2. PlatformIO native uKit: test and build the C99 reference.
3. PlatformIO native ESP32 tests: run if the `native` environment is present.
4. Build ESP32 firmware for the default environment.

## Pre-merge checklist

- `pytest tests/python` passes.
- `pio test -d ukit -e native` and `pio run -d ukit -e native` pass.
- `pio test -d esp32 -e native` and `pio run -d esp32` pass.
- No secret, `.pio`, `.venv`, cache or log files committed.
- Wiring/MQTT docs updated if behaviour changed.
