# Smart Factory Contracts v1

Canonical JSON contracts for the Smart Factory ESP32 bridge system. These schemas
describe the high-level application-layer contracts; the wire format uses AMLP v1
(`@BODY*CRC4\r\n`).

## Versioning

Contract versions are pinned under `v1/`. A new major version is introduced only
when a change is non-additive or removes backward compatibility. Minor additions
(e.g. new optional fields) are added to the existing version.

## Schema Index

| File | Description |
|------|-------------|
| `schemas/device-event.schema.json` | Generic device event envelope (acknowledgements, errors, status changes) |
| `schemas/command.schema.json` | Command envelope issued by SCADA/application to a bridge |
| `schemas/telemetry.schema.json` | Telemetry payload forwarded by the ESP32 bridge |
| `schemas/device-registry.schema.json` | Device registry and configuration ownership schema |

## Examples

| File | Description |
|------|-------------|
| `examples/command-example.json` | `CONVEYOR_START` command with speed argument |
| `examples/telemetry-example.json` | Periodic telemetry from uKit |
| `examples/device-registry.json` | Smart Factory device registry example mapping nine production modules |

## Field Naming Conventions

All field names use `snake_case`. Timestamps are ISO 8601 UTC (`date-time`).

## Compatibility Matrix

| Client | Schema v1 | Notes |
|--------|:---------:|-------|
| ESP32 bridge firmware (current) | Partial | Uses flat `{id, fields}` JSON on MQTT; internal AMLP encoding is opaque |
| SCADA / application layer | Planned | Consumes `device-event` and emits `command` |
| Python tools (`simulator.py`) | Partial | TCP endpoint mirrors raw AMLP bytes; no JSON schema applied |

> **Status**: Active development. The ESP32 telemetry-to-MQTT path is not yet
> implemented. Do not claim a telemetry topic/payload that is not present in the
> code.

## AMLP v1 Wire Format Reference

```
@BODY*CRC4\r\n
```

- `BODY = TYPE[,field...]` — `TYPE` is `CMD`, `ACK` or `TEL`
- CRC4: uppercase hex of CRC-16/CCITT-FALSE over BODY only
- Max frame: 256 bytes; max 12 fields; each field max 64 bytes
- Receivers must accept both CRLF and LF-only line endings

### Command

```
CMD,<correlation_id>,<command>[,<argument>...]
```

### ACK

```
ACK,<correlation_id>,<status>
```

Status values: `OK`, `UNKNOWN_COMMAND`, `INVALID_ARGUMENT`, `INTERNAL_ERROR`.

### Telemetry

```
TEL,STATE,<uptime_ms>,<temperature_centi_c>,<humidity_centi_percent>,<digital_inputs>
```

All values are ASCII decimal strings.
