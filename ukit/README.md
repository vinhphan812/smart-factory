# uKit C99 Reference Endpoint

This directory is a **portable C99 reference implementation**, not official firmware for uKit. The real SDK, toolchain and hardware documentation have not been provided, so UART/GPIO integration points in `examples/basic/main.c` are `TODO` placeholders that must be replaced with the official API before running on hardware.

Components:

- `lib/amlp/src/amlp.c`: CRC-16/CCITT-FALSE, ASCII encode/decode and streaming/timeout parser.
- `lib/amlp/src/ukit_endpoint.c`: `CMD/ACK/TEL` profile, ACK, telemetry and 8-correlation-id dedupe.
- `examples/basic/main.c`: integration template with stub UART/clock layers.
- `test/test_native/test_main.c`: native tests via PlatformIO/Unity, using vectors from `../shared/protocol-spec/`.

Run:

```bash
pio test -d ukit -e native
pio run -d ukit -e native
```

The canonical wire form is `@BODY*CRC4\r\n`; see `../shared/protocol-spec/AMLP-v1.md`. Before running on hardware, UART logic level, pinout, baud rate and the actual uKit SDK API must be confirmed.
