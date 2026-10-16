# Issue #30 — Command Authorization, Lease and Acknowledgement Lifecycle

**Status:** Proposed
**Author:** Issue #30
**Related ADR:** [ADR-0006 Local Physical Command Safety](./adr/adr-0006-local-physical-safety.md)
**Related Issues:** #5, #9, #10, #13

---

## Table of Contents

1. [Scope](#1-scope)
2. [Current State](#2-current-state)
3. [Proposed Lifecycle](#3-proposed-lifecycle)
4. [Lease and Expiry Behavior](#4-lease-and-expiry-behavior)
5. [Idempotency](#5-idempotency)
6. [Not Yet Implemented](#6-not-yet-implemented)
7. [Relationship to ADR-0006](#7-relationship-to-adr-0006)
8. [Evidence](#8-evidence)

---

## 1. Scope

This document specifies the **command authorization, lease, and acknowledgement lifecycle** for the Smart Factory system. It covers the end-to-end path from an external MQTT client (dashboard, AI agent, operator) through the ESP32 bridge to the MEGA-uKit endpoint and back.

The system has three participants:

| Participant | Role |
|---|---|
| **Command issuer** | External MQTT client (dashboard, AI agent, operator) — publishes to `smart-factory/{deviceId}/command/down` |
| **ESP32 bridge** | Protocol translator: MQTT → AMLP/UART; enforces Layer 1–2 safety per ADR-0006 |
| **MEGA-uKit endpoint** | Physical actuator controller; enforces Layer 3 safety per ADR-0006 |

---

## 2. Current State

### 2.1 What exists in the bridge

The ESP32 bridge (`esp32-ukit-bridge/esp32/lib/bridge-core/src/bridge_core.h`) implements a finite-state machine with three internal states and two external acknowledgement types:

**Internal command states (bridge-internal only, not exposed in MQTT ACKs):**

| Internal state | Meaning | Transition |
|---|---|---|
| `enqueued` | Command stored in `queue_[8]` ring buffer, waiting to be dispatched | → `pending` when popped from queue and sent over UART |
| `pending` | Command transmitted over UART; waiting for MEGA ACK | → completion on MEGA ACK or timeout |
| *(none)* | No explicit `dispatched` or `acked` state is modelled in `BridgeCore` | — |

**External acknowledgement types (published to MQTT `command/ack`):**

| ACK type | When published | `status` field |
|---|---|---|
| **Immediate NACK** | JSON structurally valid but command name unknown, AMLP frame invalid, or queue full | `unknown_command`, `invalid_argument`, `queue_full`, `internal_error` |
| **Completion ACK** | MEGA responds over UART, or all retries exhausted | `ok`, `unknown_command`, `invalid_argument`, `internal_error`, `timeout` |

**Current command lifecycle (de facto, no explicit state machine):**

```
Command received on MQTT
  → JSON parsed
  → requestId / command_id extracted
  → deduplication check against recent_[16] cache
  → sequence number allocated
  → command name allowlisted (CommandMapper)
  → arguments validated (channel range 0–255, speed 1–100)
  → AMLP CMD frame built and enqueued (queue capacity 8)
  → [no immediate ACK on success]
  → [pending state while waiting for UART response]
  → MEGA ACK received over UART
  → Completion ACK published to MQTT
  → Command removed from pending slot
```

The bridge publishes **no state transitions** to MQTT. An external client receives only:
- An immediate NACK (on error *before* enqueue), OR
- A single completion ACK (after UART round-trip succeeds or times out).

There is no MQTT-visible `queued` → `dispatched` → `ack_received` progression.

### 2.2 What exists in the gateway

The iot-gateway (`iot-gateway/src/iot_gateway/models.py`) models `CanonicalEvent` with `EventType.COMMAND_ACK` and stores MQTT ACK payloads as event records. There is no gateway-side command state machine, no lease tracking, and no role-based authorization.

The gateway is a **passive consumer**: it receives MQTT ACK messages, wraps them in `CanonicalEvent`, persists them, and broadcasts them over WebSocket. It does not issue commands.

### 2.3 AMLP framing

AMLP v1 (`esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md`) provides only three frame types: `CMD`, `ACK`, `TEL`. The `ACK` frame carries a status token (`OK`, `UNKNOWN_COMMAND`, `INVALID_ARGUMENT`, `INTERNAL_ERROR`). No lease field, no sequence window, and no timestamp is defined in the protocol itself — these are application-profile concerns.

---

## 3. Proposed Lifecycle

The following lifecycle extends the existing bridge behavior to add observable state transitions, lease tracking, and explicit acknowledgement verification. It is expressed as a sequence of **MQTT-visible states** that an external client (dashboard, AI agent) can observe.

```
requested → authorized → queued → dispatched → ack_received → verified_success
                                                        └→ failed
                                                        └→ timed_out
                                                        └→ verified_failure
```

**Requested** *(client-side)* — the MQTT client publishes a command to `smart-factory/{deviceId}/command/down`.

### 3.1 authorized / rejected

**State: `authorized`** — the bridge has validated the command and accepted it for processing. This is the first MQTT-visible state transition. It replaces the current silent-accept behavior (where no ACK is sent on success).

**State: `rejected`** — the bridge rejects the command before any UART traffic. This replaces the current immediate NACK behavior (merged with completion ACKs in a single `command/ack` topic).

**Rejection reasons (current + proposed additions):**

| Reason | Code | Implemented | Notes |
|---|---|---|---|
| `unknown_command` | 1 | ✅ Yes | Command name not in allowlist |
| `invalid_argument` | 2 | ✅ Yes | Malformed JSON, bad AMLP frame, bad arguments |
| `queue_full` | 4 | ✅ Yes | Queue at capacity |
| `internal_error` | 3 | ✅ Yes | Sequence allocation failed |
| `unauthorized` | 5 | ❌ No | Role-based authorization not implemented |
| `rate_limited` | 6 | ❌ No | Per-issuer rate limiting not implemented |
| `device_offline` | 7 | ❌ No | Bridge not connected to MQTT broker |
| `command_disabled` | 8 | ❌ No | Command type globally disabled |

An `authorized` event does **not** mean the physical action succeeded — it means the command passed bridge-layer validation (ADR-0006 Layer 2) and has been queued for UART dispatch.

### 3.2 queued

**State: `queued`** — the command has been assigned a sequence number and placed in the bridge's command queue. The bridge publishes the sequence number to MQTT so clients can correlate the `authorized` event with subsequent `dispatched` / completion events.

```
{
  "event_type": "command_authorized",
  "request_id": "abc123",
  "sequence": 42,
  "command": "CONVEYOR_START",
  "arguments": ["60"],
  "queued_at_ms": 1234567890,
  "expires_at_ms": 1234568190
}
```

The `expires_at_ms` field carries the lease expiry (see Section 4).

### 3.3 dispatched

**State: `dispatched`** — the bridge has popped the command from the queue and transmitted the AMLP CMD frame over UART to the MEGA endpoint. The bridge sends a `command_dispatched` MQTT message on this transition.

```
{
  "event_type": "command_dispatched",
  "request_id": "abc123",
  "sequence": 42,
  "command": "CONVEYOR_START",
  "attempt": 1,
  "dispatched_at_ms": 1234567910
}
```

`attempt` reflects the current retry attempt (starts at 1). On retry, a new `dispatched` event is published with `attempt: 2`, etc.

### 3.4 ack_received

**State: `ack_received`** — the bridge received an AMLP ACK frame from the MEGA endpoint over UART. This is published to MQTT as a `command_ack_received` event.

```
{
  "event_type": "command_ack_received",
  "request_id": "abc123",
  "sequence": 42,
  "command": "CONVEYOR_START",
  "mega_status": "OK",
  "mega_status_code": 0,
  "attempts": 1,
  "ack_received_at_ms": 1234567950
}
```

`mega_status` is the raw MEGA status token. `ack_received_at_ms` is the bridge monotonic clock at the time the UART byte was received.

**Note:** `ack_received` is **not** `verified_success`. The MEGA ACK indicates the MEGA processed the command — it does not indicate the physical actuator completed the action or that the result is consistent with the requested outcome (see Section 6).

### 3.5 Terminal states

After `ack_received`, the bridge transitions to one of three terminal states:

| Terminal state | Trigger | MQTT `status` | MQTT `status_code` |
|---|---|---|---|
| `verified_success` | MEGA returned ACK with `OK` (status_code 0) | `ok` | 0 |
| `verified_failure` | MEGA returned non-OK status (UNKNOWN_COMMAND, INVALID_ARGUMENT, INTERNAL_ERROR) | canonical label | 1–3 |
| `timed_out` | All retry attempts exhausted with no MEGA ACK | `timeout` | — |

The terminal event schema:

```
{
  "event_type": "command_completed",
  "request_id": "abc123",
  "sequence": 42,
  "command": "CONVEYOR_START",
  "final_state": "verified_success",   // verified_success | verified_failure | timed_out
  "status": "ok",
  "status_code": 0,
  "attempts": 1,
  "completed_at_ms": 1234567950,
  "duration_ms": 160
}
```

`final_state` is the canonical terminal state name. `status` and `status_code` are the existing MQTT ACK fields, retained for backward compatibility.

---

## 4. Lease and Expiry Behavior

### 4.1 Command lease

A **command lease** is the time window during which the bridge guarantees a command will be executed, retried, and terminal state published. After the lease expires, the bridge MUST NOT dispatch the command and MUST publish `timed_out`.

**Proposed default lease duration:** 10 000 ms (10 s), configurable via `bridge_config.h` as `kCommandLeaseMs`.

**Lease expiry logic:**

- `expires_at_ms` is set at `authorized` time: `queued_at_ms + kCommandLeaseMs`.
- The bridge MUST track per-command lease timers in the pending slot.
- If `ack_received` does not occur before `expires_at_ms`, the bridge publishes `timed_out` and removes the command from all internal state.
- A lease applies per attempt: each retry resets the lease timer for that attempt.

### 4.2 Current retry behavior (no lease)

The current bridge implementation retries on a fixed **1000 ms interval** for up to **3 attempts** (`kRetryIntervalMs`, `kMaxAttempts` in `bridge_core.h`). Retries are not gated by a lease — they are unconditional and may continue indefinitely if the UART path is silent.

**Proposed retry behavior with lease:**
- Each retry attempt consumes one lease window.
- If all attempts within the lease window fail, the command transitions to `timed_out`.
- Retry interval is still configurable (`kRetryIntervalMs`) but total command lifetime is bounded by `kCommandLeaseMs`.

### 4.3 Queue TTL

Commands in the queue that are not dispatched within the lease window (i.e., the queue is stalled behind a command that has expired) MUST be rejected with `timed_out` rather than silently dropped.

**Not implemented.** Queue TTL with per-command lease timers requires changes to `BridgeCore::tick()`.

### 4.4 Device offline behavior

If the bridge is disconnected from the MQTT broker when a command arrives, the broker MUST reject the publish (no delivery to the bridge). The command lifecycle does not start — the issuer must retry.

If the bridge disconnects *after* accepting a command but *before* dispatching it, the command remains in the queue. On reconnect, the bridge resumes dispatching from the queue head. Commands whose lease expired during disconnection are marked `timed_out`.

---

## 5. Idempotency

### 5.1 Bridge deduplication (current)

The bridge maintains a 16-entry `RecentIdentity` cache (`recent_[16]`) keyed on `requestId` string. On a duplicate `requestId`:

- If the command is still in the queue: the duplicate is **silently ignored** (not re-enqueued).
- If the command is pending (UART sent, no ACK yet): the duplicate is **silently ignored**.
- If the command has completed: the bridge **re-publishes the last cached completion ACK** (completes from `completion_[8]` ring buffer).

This behavior is documented in `esp32-ukit-bridge/docs/mqtt-contract.md`.

### 5.2 Proposed idempotency contract

The proposed lifecycle extends idempotency as follows:

| Duplicate arrives during | Response | MQTT event published |
|---|---|---|
| `requested` | `unauthorized` — command not yet accepted | No |
| `authorized` / `queued` | Re-publish `command_authorized` with same `sequence` | Yes — `command_authorized` |
| `dispatched` | Re-publish `command_dispatched` with current `attempt` | Yes — `command_dispatched` |
| `ack_received` / `verified_*` | Re-publish terminal completion event | Yes — `command_completed` |
| `timed_out` | Re-publish `timed_out` | Yes — `command_completed` |

**Idempotency key:** The client MUST supply either `command_id` (uint32) or `request_id` (string ≤ 64 bytes). The bridge canonicalizes both to a string `requestId` for cache lookups. The two fields are mutually exclusive; `command_id` takes precedence if both are present.

### 5.3 Not implemented

- **Idempotency for `command_dispatched` re-publish** — the bridge currently does not track `dispatched` as a separate observable state and does not re-publish it on duplicate receipt.
- **Idempotency for `command_authorized` re-publish** — the bridge currently publishes no `authorized` event on success.

---

## 6. Not Yet Implemented

The following are identified gaps between the proposed lifecycle and current code. Each is tracked as a prerequisite for full lifecycle compliance.

### 6.1 Role-based authorization

**What:** The bridge currently accepts commands from any MQTT client authenticated to the broker (ADR-0006 Layer 1). There is no per-client command allowlisting, per-role command permission matrix, or issuer identity tracking in the bridge.

**Current:** `CommandMapper` only validates the command name against a static allowlist. All authenticated MQTT clients can issue any allowlisted command.

**Gap:** No `unauthorized` (code 5) or `rate_limited` (code 6) rejection reasons are implemented. The bridge does not read the MQTT username or client ID to enforce per-client permissions.

**Required changes:**
- Bridge receives MQTT client identity (username / client ID) from `PubSubClient::clientID()` or equivalent.
- A `CommandAuthorizationPolicy` (config file or compile-time table) maps `(client_role, command_name)` to `allow` / `deny`.
- On `deny`, the bridge publishes `unauthorized` (status_code 5) immediately without UART traffic.

**Relationship to ADR-0006 Layer 4:** ADR-0006 Layer 4 addresses AI/Twin fail-closed approval gates. Role-based authorization at the bridge is Layer 2 — it validates that an authenticated client is *permitted* to issue a given command class, independent of the AI approval workflow.

### 6.2 Command lease tracking

**What:** The bridge does not track per-command lease expiry timers. Commands remain in the pending slot indefinitely (bounded only by the hardcoded retry limit). There is no `kCommandLeaseMs` concept, no `expires_at_ms` in MQTT ACKs, and no TTL-based queue eviction.

**Current:** `BridgeCore::tick()` dispatches retries unconditionally every `kRetryIntervalMs` until `pendingAttempts_ >= kMaxAttempts`. Total command lifetime is unbounded — if the UART path is lossy but not fully dead, retries continue beyond any reasonable time budget.

**Gap:** No lease expiry, no `timed_out` triggered by wall-clock deadline (only by attempt exhaustion). No `expires_at_ms` in MQTT events.

**Required changes:**
- Add `kCommandLeaseMs` to `bridge_config.h`.
- Track `leaseExpiresAtMs` per pending command.
- On `tick()`, if `nowMs >= leaseExpiresAtMs` and no ACK received, publish `timed_out` and remove from pending.
- Add `expires_at_ms` and `final_state` fields to completion MQTT ACK schema.

### 6.3 Acknowledgement verification

**What:** The bridge treats any non-OK MEGA ACK as `verified_failure`. It does not cross-check the MEGA response against the original command, verify actuator state consistency, or detect logically inconsistent responses (e.g., MEGA reports `OK` for a `CONVEYOR_START` when the conveyor sensor shows no motion).

**Current:** `UartAdapter::handleFrame()` extracts `ACK,<sequence>,<status>` from the AMLP frame and calls `BridgeCore::acknowledge()`. The status code is forwarded verbatim to MQTT.

**Gap:** `ack_received` is conflated with `verified_success`. The bridge performs no semantic verification beyond the MEGA status token. Physical verification (e.g., sensor feedback confirming the actuator changed state) is out-of-scope for the bridge and belongs to a higher-layer system (Twin or operator dashboard).

**Proposed split:**
- `ack_received` — MEGA returned a status token; bridge records it.
- `verified_success` — terminal state set only after `ack_received` with `mega_status: OK`. Future extensions may add sensor-feedback verification in a higher layer.
- `verified_failure` — terminal state set after `ack_received` with non-OK status, or after lease expiry without ACK.

**Required changes:**
- Split `CompletionReason::Acknowledged` into `Acknowledged` (ACK received) and `LeaseExpired` (timeout).
- Add `mega_status` field to completion MQTT payload (currently only `status`/`status_code` are published).
- Add `command_dispatched` and `command_authorized` MQTT event types (separate topics or sub-payload discriminators).

---

## 7. Relationship to ADR-0006

ADR-0006 defines four layers of physical command safety. This document extends Layer 2 (bridge command validation) with observable state transitions and lease/expiry semantics, and identifies Layer 2 gaps.

| ADR-0006 Layer | Topic | Addressed by this spec |
|---|---|---|
| **Layer 1 — MQTT broker ACL** | Only authenticated clients may publish to `command/down` | Not addressed — broker ACL is a deployment concern |
| **Layer 2 — Bridge command validation** | Command name allowlist, argument range, deduplication | Extended here: `command_authorized` event, lease tracking, role-based auth (not yet implemented) |
| **Layer 3 — MEGA local safety** | Motion limits, speed bounds, E-stop | Not addressed — MEGA firmware is out of scope for this spec |
| **Layer 4 — AI/Twin fail-closed** | AI actions held in "proposed" state until operator approval | Not addressed — approval workflow is separate from the bridge lifecycle |

**Consistency requirements:**
- The `command_authorized` state (this spec) MUST only be entered after ADR-0006 Layer 2 validation passes. The bridge must not publish `command_authorized` for a command that would fail Layer 2 validation.
- The `verified_success` terminal state requires both a MEGA ACK with `OK` (Layer 3 confirmation) and no lease expiry. This aligns with ADR-0006's principle that physical safety is enforced at the local controller level.
- Role-based authorization (Section 6.1) complements but does not replace Layer 2 validation. Even an authorized issuer's commands must still pass Layer 2 argument and allowlist checks.

---

## 8. Evidence

| Source | What it shows |
|---|---|
| `esp32-ukit-bridge/docs/mqtt-contract.md` | MQTT command/ACK topic schema, immediate vs. completion ACK, retry/idempotency behavior |
| `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md` | AMLP frame grammar, ACK frame type, CRC, limits |
| `esp32-ukit-bridge/esp32/lib/bridge-core/src/bridge_core.h` | Internal queue (8), pending slot, completion ring (8), deduplication cache (16), `EnqueueResult`, `CompletionReason` |
| `esp32-ukit-bridge/esp32/lib/bridge-core/src/command_mapper.h` | Command name allowlist, argument validation |
| `esp32-ukit-bridge/esp32/src/mqtt_bridge.cpp` | `onMessage()` pipeline: parse → dedupe → allocate sequence → validate → enqueue → publishImmediateAck / publishCompletion |
| `esp32-ukit-bridge/esp32/src/uart_adapter.cpp` | AMLP frame consumption, MEGA ACK correlation, telemetry dispatch |
| `iot-gateway/src/iot_gateway/models.py` | `CanonicalEvent`, `EventType.COMMAND_ACK` — gateway event envelope |
| `docs/adr/adr-0006-local-physical-safety.md` | Safety layer definitions; Layer 2 = bridge validation, Layer 3 = MEGA enforcement |
| `docs/adr/README.md` Issue #30 row | Tracked as P1, Trigger 3, coupled to ADR-0006 Layer 2 |
| `docs/architecture/overview.md` | ADR-0006 reference in architecture overview |

---

*This document describes a proposed command lifecycle. Implementation is incomplete. See Section 6 for gaps.*
