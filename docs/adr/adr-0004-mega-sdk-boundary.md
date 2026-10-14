# ADR-0004: Mega SDK Boundary: Portable C99 vs UBTEDU Vendor SDK

**Status:** Proposed
**Date:** 2026-10-14
**Deciders:** Issue #57
**Related issues:** #56 #57 #58 #59 #60

## Context

The Arduino Mega runs the physical factory's UBTEDU firmware which communicates over UART using the AMLP v1 protocol. Two integration paths exist:

1. **UBTEDU Vendor SDK** — official library from the uKit Explore vendor; provides motor control, sensor reads, and UART framing
2. **Portable C99 AMLP endpoint** — a custom AMLP implementation (`ukit/`) that runs on any microcontroller with a UART port

The bridge ESP32 must send commands to and receive telemetry from the Mega. The ESP32's UART TX/RX pins are wired to the Mega.

## Decision

The integration uses a **dual-layer approach**:

1. **ESP32 → Mega: AMLP command frames over UART**
   - The ESP32 sends AMLP-encoded command frames (sequence, command name, arguments) via UART
   - The Mega must interpret these frames — either via UBTEDU SDK or a custom AMLP handler

2. **Mega → ESP32: AMLP telemetry/ACK frames over UART**
   - The Mega sends AMLP response frames back via UART
   - The ESP32 parses and publishes telemetry over MQTT

3. **Portable reference (`ukit/`)** — a C99 AMLP endpoint that provides the full encode/decode logic, independent of the UBTEDU SDK. This serves as:
   - A hardware-free development/test environment
   - A documented reference for the UART wire format
   - A fallback if UBTEDU SDK is unavailable or incompatible

4. **UBTEDU SDK** — used for actual motor/sensor hardware control, wired separately. The SDK must produce AMLP-compliant UART output or be wrapped by a translator.

The `ukit/` portable endpoint is **not** the vendor SDK. It is a clean-room implementation of the AMLP protocol.

## Consequences

**Easier:**
- Bridge development can proceed without real hardware (using `amlp-sim` TCP simulator)
- UART wire format is documented and stable via `ukit/`
- Tests run in CI without Arduino hardware

**Harder:**
- UBTEDU SDK and AMLP protocol must be aligned — if the SDK does not emit AMLP frames natively, a translation layer is needed
- Real hardware validation requires physical wiring and flashed Mega firmware
- SDK version changes may break the AMLP alignment

## Alternatives considered

**Option A: Use only UBTEDU SDK, no custom AMLP endpoint**
- The ESP32 sends SDK-compatible serial commands
- Rejected: SDK serial protocol is vendor-internal and undocumented; AMLP v1 provides a stable, documented wire format

**Option B: Replace Mega firmware entirely with custom AMLP endpoint**
- Mega runs only the portable C99 AMLP endpoint
- Rejected: UBTEDU SDK provides motor/sensor abstractions that are necessary for physical control; replacing it entirely is out of scope

**Option C: Bridge on ESP32 interprets UBTEDU SDK protocol directly**
- Rejected: SDK protocol is vendor-internal; AMLP provides a documented, cross-vendor stable contract

## Evidence

- `ukit/` — portable C99 AMLP endpoint (`ukit/lib/amlp/`, `ukit/test/test_ukit/`)
- `ukit/README.md` — confirms clean-room implementation
- `esp32-ukit-bridge/docs/architecture/ukit-explore-sdk-audit.md` — SDK audit (Issue #56)
- `docs/architecture/ukit-mega-sdk-integration.md` — integration design
- `docs/architecture/repository-layout.md` — boundary rule: "local controllers own motion limits"
- Issue #56: "Audit uKit Explore v1/v2 SDK, Mega pinout, dependencies and licensing"
- Issue #57: "Create Arduino Mega firmware target and integrate official UBTEDU library"
- Issue #58: "Port AMLP v1 endpoint to Arduino Mega HardwareSerial"
