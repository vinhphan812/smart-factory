# MQTT Contract and AMLP Mapping

This document describes the contract implemented by the current ESP32 firmware and the uKit reference profile.

## Topics

| Topic                                        | Direction from ESP32 |         QoS | Retain |
| -------------------------------------------- | -------------------- | ----------: | -----: |
| `smart-factory/{deviceId}/command/down`      | Subscribe            |           1 |     No |
| `smart-factory/{deviceId}/command/ack`       | Publish              | best effort |     No |
| `smart-factory/{deviceId}/telemetry`         | Publish              | best effort |     No |
| `smart-factory/{deviceId}/status`            | Publish              | best effort |    Yes |

`{deviceId}` is provisioned from ESP32 chip MAC in `main.cpp` (e.g. `ukit-00000000`). All topics are per-device; the bridge subscribes only to its own command topic.

## MQTT Command

```json
{
    "command_id": 102,
    "command_name": "CONVEYOR_START",
    "arguments": ["60"]
}
```

- `command_id`: non-zero integer uint32; preferred correlation ID. Converted to a string for deduplication and ACK correlation. Mutually exclusive with `request_id`; if both are present, `command_id` takes precedence.
- `request_id`: string correlation ID (max 64 bytes); accepted for UUID-based or legacy callers.
- `command_name`: one of the five allowlisted tokens.
- `arguments`: positional arguments; `maxItems: 2` per schema. Only the first 2 are processed (channel + value for `SET_OUTPUT`; speed for `CONVEYOR_START`).
- Each element must be a valid AMLP string: printable ASCII 0x21..0x7E, 1..64 bytes, no `,`, `*`, `@`, CR/LF.
- AMLP payload fields max 11. `command_id`/`request_id` occupies one field, leaving 10 for the command name and arguments — but only the first 2 arguments are processed by the firmware.
- Complete AMLP frame must not exceed 256 bytes.

Mapping:

```
{"command_id":102,"command_name":"CONVEYOR_START","arguments":["60"]}
    -> @CMD,102,CONVEYOR_START,60*C942\r\n

{"request_id":"abc123","command_name":"CONVEYOR_STOP","arguments":[]}
    -> @CMD,abc123,CONVEYOR_STOP*XXXX\r\n
```

Command profile:

| Command          | Arguments         |
| ---------------- | ----------------- |
| `CONVEYOR_START` | speed (e.g. `60`) |
| `CONVEYOR_STOP`  | none              |

## MQTT Result

The bridge publishes to `smart-factory/{deviceId}/command/ack`.

**Immediate ACKs** are published synchronously during `onMessage()` for errors detected before or during enqueue. There is no immediate ACK on success — the completion ACK follows asynchronously after the UART round-trip.

| `status`             | When published                                       | `status_code` |
|---------------------|-----------------------------------------------------|---------------|
| `invalid_argument`   | JSON structurally valid but AMLP frame cannot be built | 2           |
| `unknown_command`    | `command_name` not in allowlist                     | 1             |
| `queue_full`         | Command queue at capacity (8 entries)                | 4             |
| `internal_error`     | Sequence allocation failed or queue operation failed | 3             |

On success (`kOk`), no immediate ACK is sent. The bridge waits for the completion ACK from the MEGA endpoint.

**Completion ACKs** are published asynchronously after the MEGA endpoint responds:

```json
// Success — MEGA returned ACK,OK
{ "request_id": "abc123", "sequence": 42, "command": "CONVEYOR_START",
  "status": "ok", "status_code": 0, "attempts": 1 }

// Failure — MEGA returned non-OK status
{ "request_id": "abc123", "sequence": 42, "command": "CONVEYOR_START",
  "status": "unknown_command", "status_code": 1 }

// Timeout — no MEGA ACK after all retries
{ "request_id": "abc123", "sequence": 42, "command": "CONVEYOR_START",
  "status": "timeout" }
```

Note: `status: "ok"` means the MEGA endpoint returned ACK with OK status (not a generic success). `status: "timeout"` means the bridge exhausted all retry attempts without receiving any MEGA ACK.

## UART ACK

uKit reference returns:

```
ACK,<id>,<status>
```

Example `@ACK,102,OK*22A0\r\n`. Profile status values are `OK`, `UNKNOWN_COMMAND`, `INVALID_ARGUMENT`, `INTERNAL_ERROR`. The ESP32 firmware reads the `<id>` field to stop retrying and forwards the status as `status_code` in the completion ACK JSON.

## UART Telemetry

uKit reference emits:

```
TEL,<metric>,<value>[,<value>...]
```

Example BODY:

```
TEL,CONVEYOR,RUNNING,60,SENSOR1=1
TEL,TEMP,2534,HUMIDITY=6550,SENSOR2=0
```

Fields after the `TEL` type token are parsed as follows:
- **key=value pair** — any field containing `=` is split at the first `=`. Both sides are stored as raw strings. Up to 4 pairs per frame are stored; excess pairs are silently dropped.
- **plain value** — any field without `=` is stored as a raw string. Up to 6 plain values per frame are stored; excess fields are silently dropped.

All fields must be valid AMLP: printable ASCII 0x21..0x7E, 1..64 bytes, no `,`, `*`, `@`, CR/LF. Empty fields are skipped.

## MQTT Telemetry

The bridge publishes parsed telemetry to `smart-factory/{deviceId}/telemetry` (QoS 0, not retained):

```json
{
  "device_id": "ukit-00000000",
  "received_at_ms": 123456,
  "values": ["CONVEYOR", "RUNNING", "60"],
  "pairs": { "SENSOR1": "1" }
}
```

- `device_id`: bridge device identifier.
- `received_at_ms`: monotonic millisecond timestamp at the moment the AMLP frame was recognised as complete.
- `values`: array of raw string values from plain fields (excluded key=value pairs). Omitted when empty.
- `pairs`: object mapping key strings to value strings from key=value fields. Omitted when empty.

**Backpressure policy:** If the MQTT write buffer is full (QoS 0), the frame is dropped and a counter is incremented. The UART poll loop is never blocked. Telemetry frames are not retransmitted.

**Duplicate/out-of-order TEL:** Unity should mark telemetry stale when no new frame arrives within `kTelemetryTimeoutMs` (60 s, configurable in `bridge_config.h`). Frames may arrive out of order; use `received_at_ms` for ordering.

## MQTT Status

Firmware publishes a retained JSON:

```json
{ "status": "online" }
```

Possible values include `online`, `subscribe_failed`, `invalid_json` and other states emitted by the bridge. Current firmware does not configure a Last Will.

## Retry and idempotency

- ESP32 retries every 1000 ms, up to 3 times by default configuration.
- Each retry sends the same wire frame, therefore the same `id` and CRC.
- uKit reference stores results for the last 8 ids, returns a cached ACK but does not call the handler a second time.
- ESP32 stores results for the last 16 completed ids and rejects duplicates in queue/pending/cache.
- MQTT publishers must not reuse an `id` for a different command while it could still be in any of these caches.

Do not include Wi-Fi passwords, MQTT tokens or any secret data in payloads, status or logs.
