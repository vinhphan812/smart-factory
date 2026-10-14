# ADR-0002: Bridge MQTT ↔ AMLP Contract

**Status:** Proposed
**Date:** 2026-10-14
**Deciders:** Issues #4, #5
**Related issues:** #4 #5 #29 #66

## Context

The ESP32-S3 bridge acts as a protocol translator between an MQTT broker (JSON payloads) and a UART serial link to a Mega microcontroller running UBTEDU firmware (AMLP v1 wire format). Both sides have different framing, encoding, and acknowledgment semantics.

MQTT is lossy, publish-only (QoS 0 by default), and does not provide native command correlation. AMLP uses CRC-16, sequence numbers, and explicit ACK frames. The bridge must bridge these semantics faithfully.

## Decision

The bridge translates **bidirectionally**:

**Downlink (MQTT → AMLP/UART):**
- Subscribes to `smart-factory/{deviceId}/command/down`
- JSON envelope: `{"command_id": uint32, "command_name": "SET_OUTPUT"|"CONVEYOR_START"|"CONVEYOR_STOP"|"PING"|"RESET", "arguments": [...]}`
- Dedupes by `command_id` before encoding
- Encodes as AMLP command frame, sends over UART
- Replies on `smart-factory/{deviceId}/command/ack` (immediate NAK on parse error, ACK on enqueue)
- Completes on Mega ACK: publishes `{"status": "ok"|"unknown_command"|"invalid_argument"|"internal_error"|"timeout"}`

**Uplink (AMLP/UART → MQTT):**
- Parses AMLP frames from UART
- Dispatches AMLP ACK frames to correlate with pending commands
- Publishes AMLP TEL frames as JSON telemetry to `smart-factory/{deviceId}/telemetry`

**Topics:**
- `smart-factory/{deviceId}/command/down` — command ingress
- `smart-factory/{deviceId}/command/ack` — immediate/local acknowledgment
- `smart-factory/{deviceId}/status` — retained online/offline with Last Will
- `smart-factory/{deviceId}/telemetry` — telemetry events
- `smart-factory/{deviceId}/heartbeat` — periodic health metrics (Issue #29)

## Consequences

**Easier:**
- Dashboard/twin subscribe to MQTT only — no UART exposure
- Command deduplication prevents duplicate execution
- Mega firmware is unaware of MQTT — UART contract is stable

**Harder:**
- Command latency = UART round-trip + MQTT publish
- No QoS 1/2 on downlink (AMLP has its own retry logic)
- `telemetry.schema.json` (contracts/) uses `timestamp`/`state` but bridge sends `received_at_ms`/`values`/`pairs` — schema mismatch documented in ADR-0009

## Alternatives considered

**Option A: Bridge translates MQTT QoS into AMLP retry semantics**
- MQTT QoS 1 with MID correlation could replace AMLP sequence numbers
- Rejected: AMLP sequence numbers are already in use on the UART side; dual correlation would double complexity

**Option B: Bridge as MQTT-to-MQTT proxy with AMLP as a transport**
- Put AMLP inside MQTT payloads and eliminate UART
- Rejected: Mega runs UBTEDU firmware with UART-only interface; cannot be changed without hardware replacement

**Option C: Binary MQTT payloads (AVRO/MessagePack)**
- Replace JSON on MQTT with binary encoding for efficiency
- Rejected: JSON is human-readable, debuggable, and compatible with existing dashboards (Issue #5)

## Evidence

- `esp32-ukit-bridge/docs/mqtt-contract.md` — current wire format
- `esp32-ukit-bridge/contracts/v1/` — JSON schema (partial; compatibility pending ADR-0009)
- `contracts/v1/schemas/command.schema.json` — command envelope schema
- `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md` — AMLP wire protocol spec
- Issue #5: "Harden bridge command authorization and device fail-safe policy"
- Issue #66: "Bridge MQTT telemetry pipeline" — telemetry uplift
