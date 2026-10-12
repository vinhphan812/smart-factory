# Command Lifecycle, Authorization and Error Contract

This document defines the complete lifecycle of a command from the MQTT application layer down to the uKit (MEGA) endpoint, covering state transitions, lease semantics, deduplication, authorization, emergency handling, error codes, recovery behaviour, and the field mapping between the MQTT JSON envelope and the AMLP CMD wire frame.

It supplements the [MQTT contract](./mqtt-contract.md) and assumes familiarity with the topics, QoS levels and basic framing described there.

---

## 1. Command Lifecycle States

A command moves through the following logical states. Not every command visits every state.

```
PENDING → SENT → ACKNOWLEDGED
              → FAILED
              → EXPIRED
```

| State        | When it is entered                                                          |
|--------------|-----------------------------------------------------------------------------|
| **PENDING**  | The MQTT broker has delivered the JSON to the bridge; the bridge has either enqueued it successfully or published an immediate negative ACK. |
| **SENT**     | The bridge has popped the command from the queue and transmitted the AMLP frame over UART to the MEGA endpoint. First transmission is immediate; subsequent transmissions are retries. |
| **ACKNOWLEDGED** | The MEGA endpoint returned `ACK,<id>,OK`. The bridge publishes `status: "acknowledged"` on the ACK topic. |
| **FAILED**   | The MEGA endpoint returned a non-OK ACK (`UNKNOWN_COMMAND`, `INVALID_ARGUMENT`, `INTERNAL_ERROR`). The bridge maps the AMLP status to an MQTT status string and publishes `status: "failed"` or the named error on the ACK topic. |
| **EXPIRED**  | After `maxAttempts` retries (default 3) without receiving any ACK, the bridge abandons the command. It publishes `status: "timeout"` on the ACK topic. |

### 1.1 MQTT ACK Payload by State

```json
// SENT / ACKNOWLEDGED completion
{ "request_id": "abc123", "sequence": 42, "command": "CONVEYOR_START",
  "status": "acknowledged", "status_code": 0, "attempts": 1 }

// FAILED — application error from MEGA
{ "request_id": "abc123", "sequence": 42, "command": "CONVEYOR_START",
  "status": "unknown_command", "status_code": 1 }

// EXPIRED — no ACK after all retries
{ "request_id": "abc123", "sequence": 42, "command": "CONVEYOR_START",
  "status": "timeout" }
```

Immediate ACKs are published synchronously during `onMessage()` for errors detected before enqueue:

| MQTT ACK `status`          | When published                                          | `status_code` |
|----------------------------|---------------------------------------------------------|---------------|
| `queued`                   | Command successfully enqueued (future completion follows) | 0             |
| `duplicate`                | `request_id` already in pending / queue / recent cache | — (omitted)   |
| `queue_full`               | Command queue at capacity (8)                           | — (omitted)   |
| `invalid_argument`         | JSON structurally valid but AMLP frame cannot be built  | 2             |
| `internal_error`           | Sequence allocation failed or queue operation failed    | 3             |

---

## 2. Lease and TTL

### 2.1 Schema `ttl_seconds`

The command JSON schema (see `schemas/command.schema.json`) defines the field:

```json
"ttl_seconds": {
  "type": "integer",
  "minimum": 1,
  "maximum": 300,
  "default": 10,
  "description": "Time-to-live in seconds before the command is considered stale by the bridge."
}
```

- **Minimum**: 1 second. Commands with `ttl_seconds < 1` are rejected as `invalid_argument`.
- **Maximum**: 300 seconds. Commands exceeding this are rejected as `invalid_argument`.
- **Default**: 10 seconds, used when the field is absent.

### 2.2 Mapping to Retry Parameters

The bridge exposes two configurable retry parameters in `BridgeOptions` (defined in `bridge_core.h`):

| Parameter           | Default | Description                                         |
|--------------------|---------|-----------------------------------------------------|
| `retryIntervalMs`   | 1000    | Milliseconds between retry attempts                 |
| `maxAttempts`       | 3       | Total number of transmission attempts (initial + retries) |

The effective TTL for a given command is:

```
effective_ttl_ms = min(ttl_seconds * 1000, maxAttempts * retryIntervalMs)
```

- If `ttl_seconds * 1000` is smaller than the fixed retry budget, the bridge SHOULD stop retransmitting once the wall-clock deadline is reached rather than waiting for all `maxAttempts`.
- If `ttl_seconds * 1000` is larger, the fixed `maxAttempts` limit takes precedence.
- **Current firmware behaviour**: The ESP32 bridge uses the fixed `maxAttempts` (3) and `retryIntervalMs` (1000 ms) values. The `ttl_seconds` field from the JSON is parsed but not yet wired into the retry budget. Implementations SHOULD interpret `ttl_seconds` as the wall-clock deadline for the command; firmware should be updated to enforce it.

### 2.3 What Happens on TTL Expiry

1. The bridge stops retransmitting the AMLP frame.
2. The pending command is evicted from the active slot.
3. A completion record with `reason = AttemptsExhausted` is pushed to the completion queue.
4. The bridge publishes `status: "timeout"` on the ACK topic.
5. The `request_id` is recorded in the deduplication cache (see Section 3) so that a retransmission with the same ID is correctly identified as a duplicate.

---

## 3. Anti-Replay / Deduplication

### 3.1 Correlation ID

The MQTT JSON envelope carries `command_id` (integer, 1..4294967295) as the primary correlation field. The `correlation_id` string field (optional) may be used for end-to-end tracing between the SCADA layer and the bridge log.

```json
{
  "command_id": 102,
  "correlation_id": "msg-uuid-abc123",
  "device_id": "bridge-001",
  "command_name": "CONVEYOR_START",
  "arguments": ["60"],
  "timestamp": "2026-10-12T10:00:00Z",
  "ttl_seconds": 15
}
```

### 3.2 Deduplication Window

The bridge maintains a **rolling 16-entry cache** (`recent_[]` in `bridge_core.h`, `kDedupeCapacity = 16`) of recently completed command identities (both `request_id` and `sequence`).

The MEGA uKit endpoint maintains an **independent 8-entry cache** of acknowledged command IDs.

| Component  | Cache size | What's stored              | Used for                          |
|------------|------------|----------------------------|-----------------------------------|
| ESP32 bridge | 16 ids    | `request_id` + `sequence`  | Reject MQTT re-delivery of same command |
| MEGA uKit  | 8 ids      | Command `id` (AMLP field 1) | Return cached ACK without re-executing |

### 3.3 Deduplication Rules

- A new MQTT message whose `command_id` is found in the bridge's pending, queue, or recent cache is acknowledged with `status: "duplicate"` and is **not re-enqueued or re-sent**.
- After a command is completed (acknowledged or timed out) its ID remains in the bridge's recent cache until it is evicted by newer entries.
- MQTT publishers **must not reuse a `command_id`** for a different command while it could still be in either cache:
  - Safe reuse window after completion: at least `max(kDedupeCapacity, MEGA_cache) * retryIntervalMs` = **16 seconds** after the last publish of that ID.
  - Publishers SHOULD use a UUID or monotonic counter for `command_id` to avoid accidental reuse.

### 3.4 Sequence Number

The bridge assigns a 16-bit `sequence` number (field `sequence` in MQTT ACK JSON) to each command at enqueue time. The sequence is used internally to correlate UART ACKs with the correct pending command. The MQTT caller does not need to supply a sequence; it uses `command_id` / `request_id` for correlation.

---

## 4. Authorization Model

### 4.1 MQTT Transport Authorization

Commands are published to the topic:

```
smart-factory/{device_id}/command/down
```

**Who may publish:**
- Any authenticated MQTT client (username + password, or TLS client certificate) that has **write access** to the device's command topic.
- The ESP32 bridge subscribes to this topic with QoS 1, so the broker guarantees delivery.
- The broker's access control list (ACL) MUST restrict `smart-factory/{device_id}/command/down` to authorised clients only.

### 4.2 Command Allowlist

The bridge firmware accepts the following `command_name` values (case-sensitive):

| `command_name`  | Required arguments                              | Description                        |
|-----------------|------------------------------------------------|------------------------------------|
| `CONVEYOR_START` | One: speed as string, integer 1..100          | Start the conveyor at given speed  |
| `CONVEYOR_STOP` | None                                           | Stop the conveyor                  |
| `RESET`         | None                                           | Reset the uKit endpoint            |
| `PING`          | None                                           | uKit health check (no side-effect) |
| `SET_OUTPUT`    | Two: channel (uint 0..255), value (`"0"` / `"1"`) | Set digital output channel       |

Any `command_name` not in this list causes the bridge to publish an immediate `status: "unknown_command"` ACK and the command is **not forwarded** to MEGA.

### 4.3 Argument Validation

| Command        | Validation rule                                                | On failure                        |
|----------------|----------------------------------------------------------------|-----------------------------------|
| `CONVEYOR_START` | `arguments[0]` must be a string containing an integer 1..100   | `invalid_argument`, not forwarded |
| `CONVEYOR_STOP`  | `arguments` must be absent or an empty array                   | `invalid_argument`, not forwarded |
| `SET_OUTPUT`     | `arguments[0]` must be uint 0..255; `arguments[1]` must be `"0"` or `"1"` | `invalid_argument`, not forwarded |

Argument validation is performed by `buildAmlpCommand()` in `mqtt_bridge.cpp` before the AMLP frame is constructed.

### 4.4 Rate Limiting

There is currently **no firmware-level rate limiter** implemented in the ESP32 bridge. Rate limiting SHOULD be enforced at the MQTT broker or SCADA application layer. Recommended broker-side limits:

| Limit                    | Value  | Rationale                                    |
|--------------------------|--------|----------------------------------------------|
| Commands per client / s  | 10     | Well above normal operation, below abuse risk |
| Burst allowance          | 20     | Allows a quick double-press of E-stop        |
| Queue depth per device   | 8      | Matches `kCommandQueueCapacity` in firmware   |

If the queue is full the bridge immediately publishes `status: "queue_full"` on the ACK topic; the MQTT broker should return QoS-1 acknowledgement to the publisher.

---

## 5. Emergency Stop (E-Stop)

### 5.1 Precedence

E-stop is a **physical or high-priority logical signal** that overrides all queued and in-progress commands. The precedence hierarchy is:

```
E-STOP signal  >  any in-flight AMLP CMD  >  queued commands
```

When an E-stop is asserted:

1. The bridge immediately stops transmitting any further retry attempts.
2. Any pending AMLP CMD is abandoned (no completion record with ACK is published for it).
3. A `CONVEYOR_STOP` equivalent command is sent to MEGA with the highest priority (bypassing the queue).
4. All other queued commands are **suspended** (not dropped) until E-stop is cleared.

### 5.2 Queue Behaviour During E-Stop

| Command state     | Behaviour on E-stop                              |
|-------------------|--------------------------------------------------|
| In UART transmit  | Abandoned; no ACK published for that command      |
| In command queue  | Suspended; remains in queue; not dropped         |
| Not yet published | Client should hold further publishes             |

### 5.3 Clearing E-Stop

When E-stop clears:

1. Queued commands resume in FIFO order.
2. Any command whose `ttl_seconds` deadline has already passed is evicted as expired.
3. Commands that were "in UART transmit" when E-stop fired are **not** automatically retried; the caller must re-issue them.

### 5.4 Current Firmware Status

The ESP32 bridge does **not yet implement** E-stop detection or priority queue bypass. This section defines the target behaviour; the firmware must be updated to add a `estop_active_` flag and a hardware or MQTT-signal E-stop input.

---

## 6. Command Error States

The MEGA endpoint returns one of four ACK statuses over UART. The bridge maps these to named strings and integer codes in the MQTT ACK payload.

### 6.1 Status Mapping Table

| MEGA ACK status       | MQTT `status`        | `status_code` | Meaning for the caller                           |
|-----------------------|----------------------|---------------|--------------------------------------------------|
| `OK`                  | `acknowledged`       | 0             | Command was executed successfully                |
| `UNKNOWN_COMMAND`     | `unknown_command`    | 1             | MEGA does not recognise the command name         |
| `INVALID_ARGUMENT`    | `invalid_argument`   | 2             | Arguments failed MEGA-level validation           |
| `INTERNAL_ERROR`      | `internal_error`     | 3             | MEGA had an internal fault processing the command |

### 6.2 Caller Guidance by Error State

| Status              | What the caller should do                                                      |
|---------------------|--------------------------------------------------------------------------------|
| `acknowledged`      | Success; command completed. Update application state.                          |
| `unknown_command`   | The SCADA firmware or MEGA firmware version is outdated; upgrade required.      |
| `invalid_argument`  | Re-check argument values before retrying; command was structurally valid but semantically rejected. |
| `internal_error`    | Transient MEGA fault; retry after a short delay (1-2 seconds). If persistent, inspect MEGA hardware. |
| `timeout`           | MEGA unreachable or not responding; check UART wiring, power, and MEGA firmware. |

---

## 7. Recovery After MQTT Disconnect

### 7.1 What Survives a Disconnect

The ESP32 bridge is an embedded firmware process. All command state is held in RAM:

| State component           | Survives disconnect? | Notes                                              |
|---------------------------|---------------------|----------------------------------------------------|
| Command queue             | Yes (RAM)           | Survives a Wi-Fi dropout if MQTT reconnects quickly |
| Pending (in-flight) command | Yes (RAM)           | Continues retry timer on reconnect                 |
| Recent deduplication cache | Yes (RAM)           | Prevents duplicate detection across reconnects     |
| Completion queue          | Yes (RAM)           | Pending completion publishes resume on reconnect   |

### 7.2 MQTT Disconnect Sequence

1. `MqttBridge::tick()` detects `!client_.connected()`.
2. `publishOnlineStatus()` publishes the LWT `{ "online": false }` (retained).
3. Pending command retries pause; the `lastAttemptMs_` timer is frozen.
4. On reconnect (`connectOnce()`), the bridge re-subscribes to `command/down` and re-publishes `{ "online": true }`.

### 7.3 Commands That Never Received an ACK

A command that was transmitted to MEGA but never got an ACK before the MQTT connection was lost:

- **Stays pending** in RAM with its current retry count frozen.
- **On reconnect**: the bridge resumes retrying it from where it left off. The retry interval timer continues from `lastAttemptMs_` (which is not updated during disconnect, so the first reconnect tick will likely immediately trigger the next attempt if `elapsed()` returns true).
- **If `maxAttempts` is exhausted** during or after reconnect, the command is completed with `status: "timeout"`.
- **MEGA deduplication**: if the MEGA endpoint already executed the command and returned the ACK (which was lost in transit), the retry will be a duplicate on MEGA's side. MEGA will return a cached `ACK,<id>,OK` and the bridge will publish a second `acknowledged` completion. Callers must handle this idempotently.

### 7.4 Commands Queued But Not Yet Sent

These survive the disconnect. On reconnect the bridge's `tick()` resumes and pops them in FIFO order.

### 7.5 Commands Published While Disconnected

MQTT QoS 1 guarantees that the broker holds messages for the duration of the disconnection. When the bridge reconnects and re-subscribes, the broker delivers any queued messages. The bridge processes them normally; `findRequest()` checks the deduplication cache so duplicates (from both the cache and the broker replay) are handled correctly.

---

## 8. Compatibility: MQTT JSON ↔ AMLP CMD Frame

This section documents the exact field mapping between the MQTT command JSON and the AMLP UART wire frame.

### 8.1 MQTT JSON Envelope

```json
{
  "command_id": 102,
  "correlation_id": "uuid-xyz",
  "device_id": "bridge-001",
  "command_name": "CONVEYOR_START",
  "arguments": ["60"],
  "timestamp": "2026-10-12T10:00:00Z",
  "ttl_seconds": 15
}
```

### 8.2 AMLP CMD Frame Wire Format

AMLP frames are colon-delimited (`@TYPE,field0,field1,...*CRC\r\n`) with a CRC-16-CCITT-FALSE checksum.

| AMLP field index | Value (example)       | Source from MQTT JSON                                 |
|------------------|----------------------|-------------------------------------------------------|
| 0                | Sequence number (uint16 as decimal string) | `sequence` — bridge-assigned, not in MQTT JSON |
| 1                | Command name         | `command_name` mapped to AMLP token (see 8.3)         |
| 2..N             | Arguments            | `arguments[0]`, `arguments[1]`, ...                  |

### 8.3 Command Name Mapping

The `command_name` string in JSON is mapped to an AMLP token for field 1:

| JSON `command_name` | AMLP field 1 token  | Notes                                            |
|---------------------|---------------------|--------------------------------------------------|
| `CONVEYOR_START`    | `CONVEYOR_START`    | Argument: speed as decimal string                |
| `CONVEYOR_STOP`     | `CONVEYOR_STOP`     | No arguments                                     |
| `RESET`             | `RESET`             | No arguments                                     |
| `PING`              | `PING`              | No arguments; MEGA health check only            |
| `SET_OUTPUT`        | `SET_OUTPUT`        | Arguments: channel (0..255), value (`"0"`/`"1"`) |

Note: the current `mqtt_bridge.cpp` (`buildAmlpCommand()`) uses the tokens `PING`, `RESET`, `SET_OUTPUT` directly. `CONVEYOR_START` and `CONVEYOR_STOP` are documented in `mqtt-contract.md` but not yet implemented in the C++ firmware — they are listed in the JSON schema and documented here as the target behaviour.

### 8.4 Complete Encode Examples

```
// CONVEYOR_START 60
MQTT JSON: {"command_id":102,"command_name":"CONVEYOR_START","arguments":["60"]}
AMLP wire:  @CMD,1,CONVEYOR_START,60*XXXX\r\n

// CONVEYOR_STOP
MQTT JSON: {"command_id":43,"command_name":"CONVEYOR_STOP"}
AMLP wire:  @CMD,2,CONVEYOR_STOP*XXXX\r\n

// RESET
MQTT JSON: {"command_id":7,"command_name":"RESET"}
AMLP wire:  @CMD,3,RESET*XXXX\r\n

// SET_OUTPUT channel 5, value 1
MQTT JSON: {"command_id":9,"command_name":"SET_OUTPUT","arguments":["5","1"]}
AMLP wire:  @CMD,4,SET_OUTPUT,5,1*XXXX\r\n
```

`*XXXX` is the CRC-16-CCITT-FALSE of the bytes before the asterisk, computed by `amlp_encode()`.

### 8.5 Field Constraints

| Constraint                          | Value                          |
|-------------------------------------|--------------------------------|
| AMLP frame type                     | `CMD` (0)                      |
| AMLP max frame length               | 256 bytes (including header + CRC) |
| AMLP max fields                     | 12 (header + 11 payload fields) |
| AMLP max field length               | 64 bytes per field             |
| Field character set                 | Printable ASCII 0x21..0x7E; prohibited: `,` `*` `@` CR LF |
| MQTT `command_id` range             | 1 .. 4,294,967,295 (uint32)    |
| MQTT `command_id` uniqueness window | See Section 3.3                |
| MQTT `ttl_seconds` range            | 1 .. 300 seconds               |

### 8.6 Schema Field Name Note

The canonical JSON schema (`schemas/command.schema.json`) uses `command_id` as the primary correlation field. The current ESP32 firmware reads this field as `request_id` in `mqtt_bridge.cpp` (`document["request_id"]`). Implementations MUST treat `command_id` and `request_id` as equivalent — firmware should be updated to read `command_id` from the JSON and use it as the `requestId` in `BridgeCore`. The ACK response always uses `request_id` to match the firmware's internal naming.

---

## 9. Summary of Constants

| Constant                         | Value   | Defined in                        |
|----------------------------------|---------|-----------------------------------|
| `kCommandQueueCapacity`          | 8       | `bridge_core.h`                   |
| `kCompletionQueueCapacity`       | 8       | `bridge_core.h`                   |
| `kDedupeCapacity` (bridge)       | 16      | `bridge_core.h`                   |
| MEGA dedupe cache                | 8       | `mqtt-contract.md`                |
| `kMaxPayloadSize`                | 256 B   | `bridge_core.h`                   |
| `kMaxRequestIdLength`            | 64      | `bridge_core.h`                   |
| Default `retryIntervalMs`        | 1000    | `bridge_core.cpp`                 |
| Default `maxAttempts`            | 3       | `bridge_core.cpp`                 |
| `kMqttRetryMs`                   | 5000    | `bridge_config.h`                 |
| MQTT keep-alive                  | 30 s    | `mqtt_bridge.cpp`                 |
| MQTT buffer size                 | 768 B   | `mqtt_bridge.cpp`                 |
| Default `ttl_seconds` (schema)    | 10 s    | `command.schema.json`             |
