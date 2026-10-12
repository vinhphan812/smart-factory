# MQTT Contract and AMLP Mapping

This document describes the contract implemented by the current ESP32 firmware and the uKit reference profile.

## Topics

| Topic                          | Direction from ESP32 |         QoS | Retain |
| ------------------------------ | -------------------- | ----------: | -----: |
| `smart-factory/bridge/command` | Subscribe            |           1 |     No |
| `smart-factory/bridge/result`  | Publish              | best effort |     No |
| `smart-factory/bridge/status`  | Publish              | best effort |    Yes |

Topics are currently compile-time constants in `esp32/include/bridge_config.h`. To support multiple devices, a per-device topic/client id must be provisioned when extending the firmware; do not assume that a `{device_id}` placeholder is already supported.

## MQTT Command

```json
{
    "id": 102,
    "fields": ["CONVEYOR_START", "60"]
}
```

- `id`: non-zero integer, max uint32; used for correlation, queue/retry and deduplication.
- `fields`: optional but the command name must be the first element for the endpoint to execute it.
- Each element must be a valid AMLP string: printable ASCII, 1..64 bytes, no `,`, `*`, `@`, CR/LF.
- AMLP payload fields max 11. Since `id` occupies one field, `fields` max 10 elements.
- Complete AMLP frame must not exceed 256 bytes.

Mapping:

```
{"id":102,"fields":["CONVEYOR_START","60"]}
    -> @CMD,102,CONVEYOR_START,60*C942\r\n

{"id":43,"fields":["CONVEYOR_STOP"]}
    -> CMD,43,CONVEYOR_STOP (CRC computed at encode time)
```

Command profile:

| Command          | Arguments         |
| ---------------- | ----------------- |
| `CONVEYOR_START` | speed (e.g. `60`) |
| `CONVEYOR_STOP`  | none              |

## MQTT Result

Immediate on enqueue:

```json
{ "id": 102, "status": "queued" }
```

Enqueue status can be:

- `queued`: entered the queue.
- `duplicate`: id is already pending/queued or still in ESP32 cache.
- `queue_full`: queue is full.
- `invalid`: JSON/profile cannot produce a valid AMLP frame.

When a command completes:

```json
{ "id": 102, "status": "acknowledged", "attempts": 1 }
```

or:

```json
{ "id": 102, "status": "failed", "attempts": 3 }
```

`failed` currently means attempts were exhausted, not an application-level status from uKit.

## UART ACK

uKit reference returns:

```
ACK,<id>,<status>
```

Example `@ACK,102,OK*22A0\r\n`. Profile status values are `OK`, `UNKNOWN_COMMAND`, `INVALID_ARGUMENT`, `INTERNAL_ERROR`. Current ESP32 firmware reads the `<id>` field to stop retrying; the status is not yet forwarded in the result JSON.

## UART Telemetry

uKit reference emits:

```
TEL,STATE,<uptime_ms>,<temperature_centi_c>,<humidity_centi_percent>,<digital_inputs>
```

Example BODY:

```
TEL,STATE,123456,2534,6550,5
```

- `temperature_c = temperature_centi_c / 100`.
- `humidity_percent = humidity_centi_percent / 100`.
- `digital_inputs` is a decimal 16-bit bitmask.

Current ESP32 firmware does not yet publish TEL to MQTT. The MQTT telemetry contract should only be finalized after this handler is implemented; do not claim a topic/payload that is not in the code.

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
