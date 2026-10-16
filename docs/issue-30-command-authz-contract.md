# Issue #30 — Command Authorization Lifecycle Specification

**Status:** Proposed (not yet implemented)
**Author:** Subagent
**Related:** ADR-0006 (Local Physical Command Safety), ADR-0002 (Bridge-MQTT-AMLP Contract)

---

## 1. Current Command Lifecycle (as-implemented)

The bridge and gateway today implement a partial, implicit lifecycle centered on error-reporting rather than authorization state.

### Bridge side

The ESP32 bridge processes inbound MQTT commands on `smart-factory/{deviceId}/command/down` via `onMessage()`. It performs the following checks **synchronously**, before enqueuing:

1. JSON parse — if invalid, publish immediate NAK with `status: invalid_json` to `smart-factory/{deviceId}/command/ack` and stop.
2. Command name allowlist lookup — if unknown, publish `status: unknown_command`, stop.
3. Queue capacity check — if full (max 8 entries), publish `status: queue_full`, stop.
4. Sequence / command-id deduplication — if already in pending cache (last 16 entries), silently dedup, stop.
5. On success, the command is enqueued internally; no immediate ACK is sent.

After enqueue, the bridge sends the frame over UART to the MEGA endpoint and retries up to 3 times at 1000 ms intervals. When the MEGA responds with an `ACK,<id>,<status>` over UART, the bridge publishes a **completion ACK** to MQTT:

| status in completion ACK | meaning |
|---|---|
| `ok` | MEGA returned ACK,OK |
| `unknown_command` | MEGA rejected command |
| `timeout` | All retries exhausted, no MEGA ACK received |

The gateway models this with `EventType.COMMAND_ACK` in `CanonicalEvent` (`iot-gateway/src/iot_gateway/models.py`), wrapping the MQTT payload in a timed envelope with `received_at_ms`, `latency_ms`, and staleness flags.

### Gateway side

The gateway consumes `smart-factory/{deviceId}/command/ack` and normalizes every event into a `CanonicalEvent`. The `payload` field contains the raw MQTT JSON. The gateway does **not** currently:

- Track per-command state beyond a single `command_ack` event.
- Maintain a command queue, command registry, or state machine.
- Perform authorization checks of its own.
- Correlate a command's dispatch to its completion beyond the correlation ID (`command_id`/`request_id`).

### Gap summary (current)

| Capability | Status |
|---|---|
| JSON / allowlist validation | Implemented (bridge) |
| Queue capacity enforcement | Implemented (bridge, 8 slots) |
| Deduplication (16-entry cache) | Implemented (bridge) |
| Retry with exponential backoff | Implemented (bridge, 3×1000 ms) |
| Immediate NAK on validation failure | Implemented (bridge) |
| Completion ACK from MEGA | Implemented (bridge → MQTT) |
| **Gateway command registry** | **Not implemented** |
| **Gateway per-command state tracking** | **Not implemented** |
| **Authorization gate before dispatch** | **Not implemented** |
| **Timeout tracking beyond bridge retry** | **Not implemented** |
| **Verified-success / failed / timed_out terminal states** | **Not implemented** |

---

## 2. Proposed Command Authorization Lifecycle

The full lifecycle is a state machine on the **gateway side**, tracking each command from the moment it is received at the gateway to the moment its physical outcome is confirmed or declared dead.

```
requested → authorized → rejected → queued → dispatched → ack_received → verified_success
                                                            ↓              ↓
                                                          failed      timed_out
```

### State definitions

**requested**
The gateway has received a command on a command-ingest endpoint (MQTT `command/down`, REST API, or AI action proposal). The command carries a `command_id` (uint32) or `request_id` (string, max 64 bytes) for correlation. The gateway assigns a canonical `event_id` (UUID) if none is supplied.

**authorized / rejected**
The gateway applies the authorization policy defined in §3. If the command passes all checks, it transitions to `authorized` and is eligible for dispatch. If any check fails, it transitions to `rejected` with a reason code and the command lifecycle terminates. The rejection is reported back to the caller and logged.

Authorization checks include but are not limited to:

- Caller identity verification (MQTT client certificate, API token, operator session).
- Command name is in the allowlist for the target device.
- Arguments are within the physical limits defined in ADR-0006 Layer 3 (Mega safety limits) — not enforced by the gateway alone, but the gateway records the limit profile used for this decision.
- No conflicting command is currently in `dispatched` or `ack_received` state for the same actuator on the same device (anti-conflict check).

> **Note:** The Mega controller remains the authoritative enforcement point for physical safety (ADR-0006 Layer 3). The gateway authorization gate does not replace Mega enforcement; it screens commands before they enter the dispatch queue.

**queued**
An authorized command is placed in the gateway's dispatch queue. The queue is ordered and supports priority fields (reserved for future use). Commands in this state may be cancelled by an operator before they reach `dispatched`.

**dispatched**
The command has been published to `smart-factory/{deviceId}/command/down` on the MQTT broker. The `command_id`/`request_id` and a new gateway-assigned dispatch sequence number are recorded. A timeout counter starts.

**ack_received**
The bridge has published a completion ACK on `smart-factory/{deviceId}/command/ack` for this `command_id`/`request_id`. The gateway ingests this as a `CanonicalEvent` and correlates it to the dispatched command.

**verified_success**
The `ack_received` status was `ok` (bridge reported MEGA returned ACK,OK). The command lifecycle terminates successfully.

**failed**
The `ack_received` status was a non-ok MEGA status code (e.g., `unknown_command`, `invalid_argument`, `internal_error`). The command lifecycle terminates with failure.

**timed_out**
The gateway's dispatch timeout expired before any ACK arrived. The command is marked dead. The gateway may optionally publish a CANCEL or ABORT to the bridge (future work).

### State transitions summary

| From | To | Trigger |
|---|---|---|
| `requested` | `authorized` | All authorization checks pass |
| `requested` | `rejected` | Any authorization check fails |
| `authorized` | `queued` | Command accepted into dispatch queue |
| `queued` | `dispatched` | MQTT publish confirmed |
| `queued` | `rejected` | Operator cancellation (future) |
| `dispatched` | `ack_received` | `command_ack` CanonicalEvent with matching correlation ID |
| `dispatched` | `timed_out` | Dispatch timeout expires |
| `ack_received` | `verified_success` | ACK `status: ok` |
| `ack_received` | `failed` | ACK `status` != ok |

---

## 3. What Is Not Yet Implemented

The following components of the proposed lifecycle are **not implemented** as of this writing:

| Component | Owner | Blocker |
|---|---|---|
| Gateway command registry (state store per command) | iot-gateway | Requires ADR-0006 Layer 4 policy definition |
| Authorization gate (caller identity + allowlist check) | iot-gateway | Requires MQTT ACL integration (Issue #41) |
| Anti-conflict check (same actuator, concurrent commands) | iot-gateway | Requires actuator lock model |
| Dispatch queue with persistence | iot-gateway | Requires queue backend (Redis / in-memory) |
| Gateway-side dispatch timeout (beyond bridge 3×1 s retry) | iot-gateway | Requires command registry |
| `timed_out` terminal state and caller notification | iot-gateway | Blocked on dispatch timeout |
| Operator cancellation of queued commands | iot-gateway | Requires operator session model |
| Dispatch sequence number (separate from `command_id`) | iot-gateway | Requires registry schema |
| AI action proposal → operator approval flow (ADR-0006 Layer 4) | dashboard / AI service | Requires approval-gate API design |

The current bridge-side lifecycle (validation, queue, retry, completion ACK) is fully implemented and is **not changed** by this proposal. The gateway-side additions build on top of the existing MQTT contract without modifying the bridge firmware.

---

## 4. Relationship to ADR-0006

ADR-0006 (Local Physical Command Safety) defines four defense layers. This spec maps to those layers as follows:

**Layer 1 — MQTT broker ACL** (Issue #41)
Authorization gate in this spec depends on MQTT client identity. The authorization check in the `requested → authorized` transition requires the caller's MQTT certificate or token to be verified at the broker.

**Layer 2 — ESP32 bridge command validation**
Already implemented. The bridge validates command name, channel, value range, and performs deduplication. This remains the first line of defense. The gateway's authorization gate is additive, not a replacement.

**Layer 3 — Mega local safety**
The Mega controller is the authoritative enforcement point for physical limits. The gateway records which limit profile applies to a command, but does not duplicate Mega enforcement logic. Commands that pass the gateway gate may still be rejected by Mega; the gateway handles Mega's rejection via the existing `failed` terminal state.

**Layer 4 — AI/Twin fail-closed**
AI-generated commands enter the lifecycle in the `requested` state. The authorization gate applies equally to all callers. For AI proposals, ADR-0006 requires an explicit operator approval step before the command transitions to `authorized`. This approval step is modeled as a separate authorization sub-check, not a separate lifecycle state, pending the approval-gate API design.

---

## 5. Open Questions

1. Should the gateway maintain an in-process command registry, or delegate to an external store (Redis)?
2. What is the dispatch timeout value? The bridge retries for 3 × 1 s = 3 s. Should the gateway timeout be longer to account for MQTT delivery latency?
3. Does the `timed_out` state require a compensating action (e.g., bridge-side abort)?
4. How does the operator cancellation flow interact with a command that has already been dispatched to the bridge?
