# Threat Model and Safety Policy

> ⚠️ **PRODUCTION BLOCKED**: The current firmware uses plain MQTT (`WiFiClient`) on port 1883 with no TLS. All credentials and payload data are transmitted in the clear. Do not deploy outside an isolated lab until TLS is wired. See `mqtt-security.md` Section 2.

This document defines the threat model, command authorization rules, AI command safety constraints, fail-safe behaviour, and watchdog policy for the ESP32-MEGA MQTT bridge. It is the authoritative safety reference for issue #5.

It supplements:
- [MQTT contract](./mqtt-contract.md) -- topics, QoS, framing
- [Command lifecycle & authorization](./contracts/v1/command-lifecycle.md) -- state machine, TTL, dedupe, error codes
- [Command schema](./contracts/v1/schemas/command.schema.json) -- JSON field constraints

---

## Implementation Status

| Control | Status | Evidence |
|---|---|---|
| CRC-16/CCITT-FALSE accidental-corruption detection | ✅ Implemented | `amlp::encode()` / `crc16_ccitt_false()` |
| Replay deduplication (16-entry FIFO) | ✅ Implemented | `BridgeCore` `recent_[]` cache; `kDedupeCapacity = 16` |
| Command queue capacity (8) | ✅ Implemented | `kCommandQueueCapacity = 8` |
| Command allowlist: all 5 commands | ✅ Implemented | `CommandMapper::build()` in `command_mapper.cpp` |
| CONVEYOR_START speed validation 1..100 | ✅ Implemented | `CommandMapper::validSpeed()` |
| SET_OUTPUT channel validation 0..255 | ✅ Implemented | `CommandMapper::validChannel()` |
| Fail-closed auth (no empty credentials) | ✅ Implemented | `connectOnce()` guard in `mqtt_bridge.cpp` |
| Anonymous connection prevention | ✅ Implemented | `connectOnce()` refuses if `username_` empty |
| CRC-16 as cryptographic integrity | ❌ Not applicable | CRC-16 detects accidents only; not a security primitive |
| TLS transport | 🔒 Planned | `WiFiClient` used; `WiFiClientSecure` not wired |
| Runtime allowlist (configurable) | 🔒 Planned | Hard-coded in `CommandMapper` |
| Actuator hard limits at ESP32 level | 🔒 Planned | MEGA enforces; ESP32-level clamp planned |
| E-stop priority queue bypass | 🔒 Planned | `estop_active_` not implemented; `CONVEYOR_STOP` not yet special-cased |
| SPIFFS device registry | 🔒 Planned | Hard-coded topic names |
| Exponential backoff for MQTT reconnect | 🔒 Planned | Fixed `kMqttRetryMs` used |

---

## 1. Threat Model

### 1.1 Asset Inventory

| Asset | Description | Confidentiality Requirement |
|---|---|---|
| Bridge firmware | ESP32 binary (`esp32/src/`) | Integrity only |
| MEGA actuator firmware | uKit firmware on MEGA microcontroller | Integrity only |
| MQTT broker credentials | Username/password transmitted in plaintext (no TLS) | **Confidential** |
| `deviceId` in MQTT topics | Device identifier exposed in topic names | Confidentiality not required (topic name is not secret) |
| Wi-Fi network | Bridge transport layer | WPA2-PSK or WPA3 minimum |
| Command/telemetry data | JSON payloads on the wire | Integrity only; confidentiality not required for command data |
| AMLP frame stream | UART framing between ESP32 and MEGA | Integrity via CRC-16/CCITT-FALSE |

> **Note on MQTT confidentiality:** The current firmware uses plain MQTT (`WiFiClient`) with no TLS. All credentials and command/telemetry payloads are transmitted in the clear on the local network. This is the primary reason for the production-blocked banner at the top of this document. Deploy only behind a trusted network segment or after TLS is wired.

### 1.2 Threat Actors

| Actor | Capability | Bounded by |
|---|---|---|
| **Unauthorized network actor** | Publishes to the broker command topic from inside the Wi-Fi LAN | MQTT broker ACL |
| **Rogue MQTT client** | Authenticates to the broker but has no command-topic grant | MQTT broker ACL |
| **Physical tampering** | Attaches to UART TX/RX between ESP32 and MEGA, or accesses ESP32 programming interface | Physical perimeter; JTAG disable fuse + case |
| **Software supply chain** | Substitutes a malicious library or build artefact | Reproducible build; SHA-256 binary hash on flash |
| **MEGA firmware compromise** | Replaces uKit firmware on MEGA | MEGA write-protect; signed firmware (future) |
| **AI agent (authorised)** | Generates commands programmatically | Same validation and ACL as any client |

### 1.3 Attack Surfaces

| Surface | Vector | Mitigations |
|---|---|---|
| MQTT ingress | Malformed JSON, out-of-allowlist command name, out-of-range arguments | Broker ACL + ESP32 input validation (field count, length, range, allowlist) |
| UART egress | Truncated frame, wrong CRC, wrong sequence number | AMLP CRC check, inter-byte timeout (250 ms), field count limit |
| Wi-Fi | Evil-twin, deauth, credential theft | WPA2/WPA3; no PSK in firmware binary (use secure boot or NVS with protection) |
| Debug/programming interface | JTAG/SWD read of firmware or NVS | Disable fuses in production build; cover physical debug header |
| MEGA UART response | Fake ACK frame | CRC validation in AMLP parser; sequence correlation in ESP32 |

---

## 2. Command Authorization

### 2.1 MQTT ACL Enforcement (Broker-Side)

The MQTT broker **must** enforce an access control list. This is the primary gate before any command reaches the ESP32.

| Topic | Permission | Who |
|---|---|---|
| `smart-factory/{device_id}/command/down` | Subscribe (ESP32 bridge) | ESP32 client ID only |
| `smart-factory/{device_id}/command/down` | Publish | Authorised SCADA/AI clients only |
| `smart-factory/{device_id}/command/ack` | Publish (broker ACL) | ESP32 client ID only |
| `smart-factory/{device_id}/telemetry` | Publish | ESP32 client ID only |
| `smart-factory/{device_id}/status` | Publish | ESP32 client ID only |

- The ESP32 subscribes to `smart-factory/{device_id}/command/down` with QoS 1.
- No client other than the bridge may publish to the `ack`, `telemetry`, or `status` topics.
- Shared subscriptions (`$share/`) are **not** used for the command topic; commands are device-specific.

### 2.2 ESP32 Input Validation

All MQTT JSON is validated in `MqttBridge::onMessage()` and `CommandMapper::build()` before a UART frame is transmitted.

| Check | Source field | Rule | On failure |
|---|---|---|---|
| JSON structure | top-level | Must be a JSON object; `deserializeJson` must succeed | `invalid_argument` |
| Required fields | `command_id` (integer) or `request_id` (string), `command_name` | Correlation ID must be present; `command_name` must be non-null | `invalid_argument` |
| Field count | `arguments` array | Max 2 items (`maxItems: 2` in schema) | `invalid_argument` |
| String length | `request_id`, `command_name`, each `arguments` item | Max 64 bytes each (AMLP field limit) | `invalid_argument` |
| Allowed characters | `arguments` items | Printable ASCII 0x21..0x7E; prohibited: `,` `*` `@` CR LF | `invalid_argument` |
| `command_name` allowlist | `command_name` field | Must be one of the five tokens below | `unknown_command` |
| Argument range -- CONVEYOR_START | `arguments[0]` | Integer string 1..100 | `invalid_argument` |
| Argument range -- SET_OUTPUT | `arguments[0]` | Integer string 0..255; `arguments[1]` must be `"0"` or `"1"` | `invalid_argument` |
| Payload size | AMLP-encoded frame | Must be <= 256 bytes | `invalid_argument` |
| `command_id` / `request_id` uniqueness | pending / queue / recent cache | Rejected; silently dropped (no ACK published) |

All rejected commands (except duplicates) result in an **immediate** MQTT ACK (`status: "invalid_argument"`, `"unknown_command"`, `"queue_full"`, `"internal_error"`). **Duplicates are silently dropped** — no ACK is published and the command is not re-enqueued. Commands are never forwarded with invalid data.

### 2.3 Command Allowlist

The bridge firmware accepts **only** the following `command_name` values (case-sensitive ASCII). Any other value returns `unknown_command`.

| `command_name` | Required `arguments` | AMLP frame example |
|---|---|---|
| `CONVEYOR_START` | One: speed as decimal string integer 1..100 | `@CMD,1,CONVEYOR_START,60*XXXX\r\n` |
| `CONVEYOR_STOP` | None | `@CMD,2,CONVEYOR_STOP*XXXX\r\n` |
| `RESET` | None | `@CMD,3,RESET*XXXX\r\n` |
| `PING` | None | `@CMD,4,PING*XXXX\r\n` |
| `SET_OUTPUT` | Two: channel 0..255, value `"0"` or `"1"` | `@CMD,5,SET_OUTPUT,5,1*XXXX\r\n` |

The JSON schema (`command.schema.json`) encodes this as `enum: ["CONVEYOR_START","CONVEYOR_STOP","RESET","PING","SET_OUTPUT"]`.

### 2.4 Anti-Replay: Correlation ID Deduplication

| Component | Cache size | What's stored | TTL |
|---|---|---|---|
| ESP32 bridge | 16 (`kDedupeCapacity`) | `request_id` + `sequence` | Until evicted by newer entries |
| MEGA uKit | 8 | Command `id` (AMLP field 0) | Until evicted by newer entries |

- **Dedup window**: The bridge maintains a 16-entry FIFO cache (`kDedupeCapacity`) and the MEGA uKit maintains an 8-entry cache. A `command_id` evicted from either cache is treated as new. The window is throughput-dependent — at ≤1 command/s the ESP32 cache holds 16 seconds of history, but at higher rates it shrinks. Publishers must not assume any minimum reuse window; use UUIDs or monotonic counters.
- **TTL enforcement**: `ttl_seconds` (schema default 10 s, range 1..300 s) is the wall-clock deadline for the command. The ESP32 should stop retransmitting once the deadline is reached rather than waiting for all `maxAttempts`. (Currently `ttl_seconds` is parsed but not wired into the retry budget; firmware update required.)
- A command whose `request_id` (or `command_id` as string) is found in the cache is **silently dropped** — no ACK is published and the command is not re-enqueued or re-sent. Callers should not rely on an ACK to detect duplicates; use monotonic IDs or UUIDs instead.

### 2.5 Rate Limiting

There is **no firmware-level rate limiter** implemented in the ESP32 bridge. Rate limiting must be enforced at the MQTT broker or SCADA layer.

| Limit | Recommended value | Rationale |
|---|---|---|
| Commands per client per second | 10 | Well above normal operation; below abuse risk |
| Burst allowance | 20 | Allows a quick double-press of E-stop |
| Queue depth per device | 8 | Matches `kCommandQueueCapacity` |

When the queue is full the bridge immediately publishes `status: "queue_full"` on the ACK topic.

---

## 3. AI Command Safety

### 3.1 AI Commands Are Not Privileged

AI-generated commands are MQTT clients like any other. They must:
- Authenticate to the MQTT broker with valid credentials.
- Publish to `smart-factory/{device_id}/command/down` -- subject to the same broker ACL as human-issued commands.
- Include `command_name` from the allowlist only (Section 2.3).
- Include valid arguments within the defined ranges.
- Carry a unique `command_id` (not reused within the dedup window).

AI commands that fail validation are rejected with the same status codes as human commands. There is no "AI bypass" path.

### 3.2 No Direct AI-to-Actuator Path

```
Human / AI Client  →  MQTT Broker ACL  →  ESP32 Bridge  →  UART  →  MEGA  →  Actuator
```

The only path from any client (human or AI) to an actuator is through the broker ACL, the ESP32 input validation, the AMLP CRC, and the MEGA command handler. AI cannot emit AMLP frames directly.

### 3.3 Fail-Closed Policy

- **Unknown commands**: rejected as `unknown_command`, not silently ignored.
- **Out-of-range arguments**: rejected as `invalid_argument`, not silently clamped.
- **Malformed JSON**: rejected as `invalid_argument`, not partially processed.
- **Broker ACL denial**: the broker does not deliver the message to the ESP32 at all.

All rejections are logged with `request_id`, `command_name`, source client ID (if available from broker logs), and timestamp.

### 3.4 Audit Logging

Every command received by the ESP32 (including rejected ones) generates an MQTT ACK. The broker should log every publish to the command topic with:

- `command_id` / `request_id`
- `command_name`
- Source client ID and IP
- Timestamp (UTC)
- Resulting `status` (ok, invalid_argument, unknown_command, queue_full, internal_error, timeout)

---

## 4. Fail-Safe Policy

### 4.1 Offline Behaviour

| Condition | Bridge behaviour | MEGA behaviour | Actuator behaviour |
|---|---|---|---|
| Wi-Fi loss | Stops MQTT operations; holds RAM state (queue, pending, cache) | Holds last state | Holds last state; **does NOT emergency stop** |
| MQTT disconnect | Publishes `{ "online": false }` via LWT (retained); retries every `kMqttRetryMs` (5000 ms) | Unaffected | Unaffected |
| ESP32 power loss | All RAM state lost; queue/pending cleared | Holds last state | Holds last state |
| MEGA UART loss | Marks telemetry stale; publishes `{ "status": "mega_offline" }` event; retries command | Not responding | Holds last state |

The bridge **never reverts to a default state** on loss of connectivity. It holds the last known command state in RAM and resumes from where it left off on reconnect.

### 4.2 Wi-Fi / MQTT Loss Recovery

1. `MqttBridge::tick()` detects `!client_.connected()`.
2. Publishes LWT `{ "online": false }` (retained).
3. Pending command retry timer pauses; `lastAttemptMs_` is frozen.
4. Command queue remains intact in RAM.
5. On reconnect (`connectOnce()`): re-subscribes to `command/down`, publishes `{ "online": true }`, and resumes retry timer and queue processing.
6. A command that was transmitted but lost its ACK before disconnect: retry timer resumes on reconnect; MEGA may return a cached ACK (idempotent).

### 4.3 MEGA UART Loss

| Step | Behaviour |
|---|---|
| Detection | No UART byte received within expected window; `uart_adapter.cpp` marks telemetry stale |
| Event | Bridge publishes `{ "status": "mega_offline", "last_seen": <timestamp> }` on status topic |
| Command retry | Commands awaiting ACK timeout normally (3 retries x 1 s); `status: "timeout"` published |
| Recovery | UART bytes resume -> telemetry parser recovers; bridge resumes normal operation |

MEGA UART loss does **not** trigger an E-stop. The actuator holds its last commanded state.

### 4.4 Emergency Stop (E-Stop)

E-stop is **defined as a `CONVEYOR_STOP` command**, not a special AMLP frame or hardware signal.

E-stop precedence hierarchy:

```
E-STOP (CONVEYOR_STOP)  >  any in-flight AMLP CMD  >  queued commands
```

When E-stop fires:
1. Bridge immediately stops retrying any in-progress command.
2. Bridge transmits `CONVEYOR_STOP` bypassing the queue.
3. All other queued commands are **suspended** (not dropped).
4. On clear: queued commands resume in FIFO order; any command whose `ttl_seconds` deadline has passed is evicted as expired.

Current firmware status: E-stop detection and priority queue bypass are **not yet implemented** in ESP32 (`estop_active_` flag and MQTT-signal input are required).

### 4.5 Recovery Procedures

| Failure mode | Recovery procedure |
|---|---|
| Wi-Fi reconnect | ESP32 auto-reconnects; queue resumes automatically; no manual step required |
| MQTT broker unavailable | ESP32 retries every 5 s; commands remain queued; publish resumes when broker is reachable |
| MEGA offline | Investigate UART wiring and MEGA power; bridge publishes `mega_offline` event; retry commands after MEGA recovers |
| Command timeout | Check MEGA UART wiring and power; verify MEGA firmware is running; re-issue command if needed |
| Bridge power loss | Re-flash if needed; MEGA holds last state; re-issue any lost commands |
| Stale telemetry | Check UART wiring; MEGA must be emitting `TEL,STATE,...`; if MEGA is offline, see MEGA offline procedure |

---

## 5. Safety Boundaries

### 5.1 Telemetry vs. Command Path Isolation

Telemetry flows **upstream only** (MEGA -> ESP32 -> MQTT) and has no effect on actuator state.

Commands flow **downstream only** (MQTT -> ESP32 -> MEGA -> Actuator).

The telemetry parser in `uart_adapter.cpp` does not write to the command queue or any command state. The command processor does not parse telemetry frames.

### 5.2 ESP32 Firmware: No Dynamic Allocation in ISR Context

All FreeRTOS tasks on the ESP32 use static memory or stack-allocated objects:

- **UART RX task**: reads bytes into a fixed-size ring buffer; no `malloc`/`new`.
- **MQTT task**: uses `ArduinoJson` with a fixed `StaticJsonDocument` or stack-allocated `JsonDocument`; no dynamic allocation at runtime.
- **Wi-Fi task**: managed by ESP-IDF; no custom ISR with dynamic allocation.

`BridgeCore` and `MqttBridge` are plain C++ objects with fixed-size member arrays (`kCommandQueueCapacity = 8`, `kCompletionQueueCapacity = 8`, `kDedupeCapacity = 16`).

### 5.3 MEGA Hard Limits

The MEGA uKit reference enforces:

| Limit | Value | Enforced by |
|---|---|---|
| Conveyor speed | 1..100 (CONVEYOR_START argument) | uKit command handler; `INVALID_ARGUMENT` on violation |
| Frame length | 256 bytes max | AMLP parser; frames exceeding 256 bytes are discarded |
| Inter-byte timeout | 250 ms | AMLP parser; partial frame discarded on timeout |
| Watchdog timer | Reset on stall | MEGA hardware watchdog |

MEGA hard limits **override** any ESP32 command. If ESP32 sends an out-of-range speed (e.g. `"200"`), MEGA returns `INVALID_ARGUMENT`. The actuator never receives an out-of-range command.

### 5.4 Actuator Safety Boundary

The actuator (conveyor motor) is driven only by MEGA. ESP32 commands pass through MEGA's validation before reaching the actuator. ESP32 cannot drive GPIO pins or affect actuator state except through the MEGA command protocol.

---

## 6. Watchdog and Timeout

### 6.1 ESP32 Task Watchdog

FreeRTOS task watchdog configuration (defined in `esp32/src/main.cpp` and platform IO configuration):

| Task | Watchdog timeout | Action on timeout |
|---|---|---|
| UART RX task | 5 s | ESP32 restarts UART peripheral; logs error; may indicate MEGA or UART hardware issue |
| MQTT task | 10 s | ESP32 disconnects and reconnects MQTT; logs error |
| Wi-Fi task | 30 s | ESP32 restarts Wi-Fi station; reconnects MQTT |

### 6.2 MEGA Watchdog

The MEGA microcontroller runs a hardware watchdog timer. If the MEGA stalls (e.g. infinite loop in command handler), it resets after the watchdog period. The watchdog is reset on:
- Successful command processing.
- Periodic `PING` command.
- Regular telemetry emission.

### 6.3 Command Timeout

| Parameter | Value |
|---|---|
| Retry interval | 1000 ms (`retryIntervalMs`) |
| Max attempts | 3 (`maxAttempts`) |
| Max wait for ACK | 3 s (3 x 1 s) |
| `ttl_seconds` default | 10 s |
| `ttl_seconds` range | 1..300 s |
| On timeout | Bridge publishes `status: "timeout"`; `request_id` recorded in dedup cache |

Commands that do not receive an ACK within `maxAttempts * retryIntervalMs` are completed with `status: "timeout"`. The `ttl_seconds` field from the JSON provides a wall-clock deadline; firmware should stop retransmitting once the deadline is reached even if attempts remain.

---

*Document version 1.0 -- aligned with contracts/v1/command-lifecycle.md and ESP32 firmware v0.1.0.*
