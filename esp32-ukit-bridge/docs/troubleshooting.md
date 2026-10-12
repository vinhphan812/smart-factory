# Troubleshooting

## No UART bytes received

1. Check crossover: ESP32 GPIO17 must connect to uKit RX0; GPIO18 receives from TX0.
2. Verify common GND.
3. Confirm both sides use `115200 8N1` (or whatever configuration was chosen).
4. Confirm the firmware uses the correct UART and pins; ensure no serial console is occupying them.
5. Use a logic analyzer to check for signal transitions on TX.
6. Stop immediately if uKit TX shows a voltage level above ESP32's maximum.

## Bytes arrive but parser produces no frame

- A frame must start with `@` and end with LF; standard senders emit CRLF.
- BODY type must be `CMD`, `ACK` or `TEL`.
- CRC must be exactly 4 uppercase hex characters after `*`.
- No field may be empty or contain `,`, `*`, `@`, CR/LF.
- Frame max 256 bytes, 12 fields including type, each field max 64 bytes.
- Partial frame idle for 250 ms is discarded; a new `@` restarts the parser.
- AMLP is ASCII; do not add log prefixes or alter newlines arbitrarily.

Use `amlp decode` with a complete frame to check independently.

## CRC mismatch

Both sides must use CRC-16/CCITT-FALSE:

```
poly=0x1021 init=0xFFFF refin=false refout=false xorout=0x0000
check("123456789")=0x29B1
```

CRC is computed over the exact ASCII bytes of BODY only; `@`, `*`, CRC text and CRLF are not included. CRC is rendered as 4 uppercase hex characters.

```bash
python -m amlp crc "CMD,102,CONVEYOR_START,60"
# C942
```

Golden wire frame:

```
@CMD,102,CONVEYOR_START,60*C942\r\n
```

## Command executed twice

- Retries must send the exact same frame with the same correlation id.
- MQTT QoS 1 publishers may redeliver JSON; use the same `id` for the same logical request.
- uKit reference dedupe window holds 8 ids; ESP32 holds queue/pending plus 16 recent ids.
- A retry arriving too late, after its cache entry was evicted, may be treated as a new command.

## ACK received but MQTT still reports failed

- ACK must be `ACK,<id>,<status>` with a valid CRC.
- `<id>` must be a non-zero uint32 decimal matching the pending command.
- Current ESP32 uses the first ACK field to correlate; it does not use status as the id.
- Verify ACK arrives before the 3rd attempt timeout (default 1000 ms per attempt).

## Telemetry values off by a factor of 100

The `TEL,STATE` profile uses:

- `temperature_c = temperature_centi_c / 100`.
- `humidity_percent = humidity_centi_percent / 100`.
- `digital_inputs` is a decimal 16-bit bitmask.

All wire fields are ASCII decimal strings, not binary integers.

## Simulator cannot connect

```bash
python -m amlp simulate --host 127.0.0.1 --port 8765
```

- Clients must connect over TCP, not UDP or serial.
- Check the port is not already in use and that the local firewall permits the connection.
- Inside a container/VM, `127.0.0.1` refers to that environment, not the host.
- Do not bind `0.0.0.0` on untrusted networks; the simulator has no authentication or encryption.

## PlatformIO native fails

- Confirm `pio --version` works.
- Delete `.pio/` and retry if artifacts are corrupted.
- Verify the host has a compatible native compiler.
- Run `pio test -d ukit -e native` separately to isolate C99 issues from ESP32.

## Cannot flash uKit hardware

This is an expected limitation: `ukit/` is a portable reference because the official uKit SDK/toolchain is not yet available. SDK, pinout, linker/startup, UART driver and official flashing procedure are required before producing firmware that runs on the device.
