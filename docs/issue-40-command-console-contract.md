# Issue #40 — Role-Based Command Request Console Contract

**Status:** Proposed  
**Author:** Subagent  
**Reviewer:** vinhphan812  
**Related:** ADR-0006 (Local Physical Safety), #30 (Command Lifecycle), #5 (Bridge Authorization), #41 (MQTT ACL)

---

## 1. Current Command Endpoints and Capabilities

### 1.1 What exists today

The `iot-gateway/src/iot_gateway/api.py` exposes **read-only endpoints only**:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Event count, high watermark, queue-dropped counter |
| GET | `/events` | Query events by `device_id`, `event_type`, `limit` |
| GET | `/events/{event_id}` | Single event by ID |
| GET | `/snapshot` | Full/incremental scene snapshot + per-device latest state |
| GET | `/metrics` | Latency, jitter, stale-event rate, overflow counter |
| WS | `ws://host:port/` | Broadcast fan-out to all connected clients |

**No command ingestion endpoint exists.** The gateway has never accepted a command request via REST or WebSocket.

### 1.2 How commands reach devices today

The only command path is MQTT direct publish → ESP32 bridge → UART → MEGA:

```
[MQTT client] → smart-factory/{deviceId}/command/down
                    [ESP32 bridge subscribes]
                         → UART → MEGA → actuator
                                    ← UART ACK ← MEGA
                    ← smart-factory/{deviceId}/command/ack [bridge publishes]
```

The gateway consumes `command/ack` as a `CanonicalEvent` (read-only telemetry ingestion). It does **not** correlate or track commands.

### 1.3 Bridge command validation (current, unchanged)

Per `esp32-ukit-bridge/docs/mqtt-contract.md` and Issue #30 §1:

- JSON parse → `invalid_json` NAK
- Allowlist lookup → `unknown_command` NAK
- Queue capacity check → `queue_full` NAK (max 8 entries)
- 16-entry deduplication cache
- 3 × 1000 ms UART retry
- MEGA `ACK,OK` → `status: ok`; non-OK → `status: unknown_command` / `timeout`

Five commands are allowlisted: `CONVEYOR_START`, `CONVEYOR_STOP`, `SET_OUTPUT`, `MOTOR_MOVE`, `E_STOP`.

---

## 2. Proposed Command Request Console

### 2.1 Architecture

The browser (or any HTTP client) **never publishes to MQTT directly**. Instead:

```
[Browser / Operator UI]
        |  POST /commands/request   (with session token)
        ↓
[iot-gateway REST API]   ← new endpoint
        |  authorizes → if operator, publishes to MQTT
        ↓
[MQTT broker]
        |  smart-factory/{deviceId}/command/down
        ↓
[ESP32 bridge] → UART → MEGA → actuator
        |  smart-factory/{deviceId}/command/ack
        ↓
[MQTT broker] → [gateway event consumer]
        |  gateway matches ACK to command registry entry
        ↓
[Browser / Operator UI]
        |  GET /commands/{command_id}  or  WebSocket push
        ↓
[Operator sees: pending → ACK → verified / failed / timed_out]
```

### 2.2 New REST Endpoints

#### `POST /commands/request`

**Access:** Operator role only. Read-only role returns `403 Forbidden`.

Request:
```json
{
  "device_id": "ukit-00000000",
  "command_name": "CONVEYOR_START",
  "arguments": ["60"],
  "command_id": 102,
  "reason": "Shift supervisor requested start for loading bay conveyor"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `device_id` | Yes | Must match a known device from the device registry |
| `command_name` | Yes | Must be in the bridge allowlist |
| `arguments` | No | Positional args; max 2; max 64 bytes each, printable ASCII |
| `command_id` | No | uint32; auto-generated as incrementing counter if omitted |
| `reason` | No | Human-readable justification; stored in registry |

Response `202 Accepted`:
```json
{
  "command_id": 102,
  "event_id": "cmd-uuid-001",
  "device_id": "ukit-00000000",
  "state": "requested",
  "created_at": "2026-10-17T10:00:00Z"
}
```

Error responses:
- `400 Bad Request` — malformed JSON, missing required fields, invalid `command_id`
- `403 Forbidden` — caller is read-only role
- `404 Not Found` — `device_id` not in registry
- `409 Conflict` — a command for the same actuator is already in `dispatched` or `ack_received` state
- `503 Service Unavailable` — MQTT broker unreachable

#### `GET /commands/{command_id}`

**Access:** Operator + read-only roles.

Response:
```json
{
  "command_id": 102,
  "event_id": "cmd-uuid-001",
  "device_id": "ukit-00000000",
  "command_name": "CONVEYOR_START",
  "arguments": ["60"],
  "state": "verified_success",
  "reason": "Shift supervisor requested start for loading bay conveyor",
  "pre_authorization": {
    "caller_role": "operator",
    "preconditions_checked": [
      "identity_verified",
      "command_name_in_allowlist",
      "arguments_within_limits",
      "no_conflicting_actuator_state"
    ]
  },
  "dispatch_at": "2026-10-17T10:00:00.150Z",
  "ack_received_at": "2026-10-17T10:00:00.280Z",
  "completed_at": "2026-10-17T10:00:00.280Z",
  "mqtt_ack": {
    "status": "ok",
    "status_code": 0,
    "attempts": 1,
    "sequence": 42
  }
}
```

#### `GET /commands`

**Access:** Operator + read-only roles. Returns the command registry.

Query params: `?device_id=&state=&limit=100`

### 2.3 Pre-Authorization Preconditions

Before transitioning a command from `requested` to `authorized`, the gateway performs explainable checks. Each check produces a named result stored in the registry under `pre_authorization.preconditions_checked`:

| Check | Failure result |
|-------|---------------|
| `identity_verified` | Caller token/session is valid and not expired |
| `command_name_in_allowlist` | `command_name` is one of the 5 allowlisted commands |
| `arguments_within_limits` | Each argument is within the physical limit profile defined in ADR-0006 Layer 3 |
| `no_conflicting_actuator_state` | No other command for the same actuator is currently in `dispatched` or `ack_received` state |
| `device_online` | Target device's retained `status` topic is `online` (optional, configurable) |

If any check fails → `rejected` state with a human-readable `rejection_reason`.

### 2.4 Confirmation Dialog

Some commands require a two-step operator confirmation:

1. **Step 1 — Dry run / preview:** `POST /commands/request` with `dry_run: true` returns pre-authorization results without entering the dispatch queue.
2. **Step 2 — Confirm:** `POST /commands/request` (without `dry_run`) dispatches immediately after authorization.

A confirmation dialog in the browser UI shows:
- What command will be sent (`command_name`, `arguments`)
- Which preconditions passed/failed with explanations
- The `reason` field entered by the operator
- A "Confirm" button that submits the actual request

Confirmation is required for:
- Any command where `arguments_within_limits` check is close to a boundary (threshold TBD per ADR-0006 Layer 3 policy)
- Any `E_STOP` command
- Commands from an AI-proposed origin (ADR-0006 Layer 4)

### 2.5 Command State Tracking

The gateway maintains a **command registry** (in-process or Redis-backed, TBD — see Issue #30 §5 Q1). State machine mirrors Issue #30 §2:

```
requested → authorized → queued → dispatched → ack_received → verified_success
                         ↓            ↓              ↓               ↓
                       rejected    cancelled     failed         timed_out
```

WebSocket clients receive push events on state transitions (same broadcast channel as telemetry). Clients can also poll `GET /commands/{command_id}`.

---

## 3. Role-Based Access

### 3.1 Roles

| Role | Command request | Command query | Event query | Metrics |
|------|----------------|---------------|-------------|---------|
| `operator` | ✅ POST /commands/request | ✅ All commands | ✅ | ✅ |
| `read_only` | ❌ 403 Forbidden | ✅ Own device only | ✅ | ✅ |
| `ai_service` | ✅ POST (AI proposals only; confirmation required per ADR-0006 L4) | ✅ | ✅ | ✅ |
| `anonymous` | ❌ 401 Unauthorized | ❌ | ❌ | ❌ |

### 3.2 Session Token

The gateway does **not** implement its own auth. It requires a **pre-shared secret** or **JWT** in the `Authorization: Bearer <token>` header on all `/commands/*` endpoints. The JWT must carry `role` and `sub` (caller identity) claims.

> **Open question (per Issue #30 §5 Q1):** How is the session token issued? Options: separate auth service, MQTT client certificate mapped to role, or static shared secret per operator. This spec assumes a token is available; token issuance is out of scope for Issue #40.

### 3.3 Read-Only Role

The `read_only` role is the browser/Unity default. It can:
- Subscribe to WebSocket for live telemetry
- Poll `/events`, `/snapshot`, `/metrics`
- Query `GET /commands/{command_id}` for events (not future dispatch intent)

It **cannot**:
- POST to any `/commands/*` endpoint
- Publish to MQTT directly (enforced by MQTT broker ACL — Layer 1 of ADR-0006)

---

## 4. Browser Never Directly Publishes to MQTT

This is a hard architectural constraint derived from ADR-0006 Layer 4 and Issue #30 §1.

| Actor | Can publish to `command/down`? | How |
|-------|-------------------------------|-----|
| ESP32 bridge | ✅ Yes | Subscribes to own `command/down` topic |
| AI service | ✅ Via gateway only | POST /commands/request with `ai_service` role |
| Operator browser | ❌ Never | REST API only; gateway does MQTT publish |
| Unity Twin | ❌ Never | Read-only WebSocket subscriber |
| Anonymous | ❌ Never | 401 before any action |

The gateway is the sole MQTT command publisher. The browser's only command path is the REST API → gateway → MQTT.

---

## 5. What Is NOT Yet Implemented

This spec is **design-only** for Issue #40. The following components are not implemented:

| Component | Owner | Blocker |
|-----------|-------|---------|
| `POST /commands/request` REST endpoint | iot-gateway | None — this spec defines it |
| `GET /commands/{command_id}` endpoint | iot-gateway | Requires command registry |
| `GET /commands` listing endpoint | iot-gateway | Requires command registry |
| Command registry (state store) | iot-gateway | Issue #30 open question Q1 |
| Authorization gate (caller identity + allowlist) | iot-gateway | Issue #41 MQTT ACL required first |
| Precondition checks | iot-gateway | Blocked on ADR-0006 Layer 3 limit profiles |
| Anti-conflict check (actuator locking) | iot-gateway | Requires actuator lock model |
| `dry_run` mode | iot-gateway | Straightforward once registry exists |
| Confirmation dialog (UI) | dashboard | None — spec defines contract only |
| WebSocket push on command state change | iot-gateway | Requires registry + WS integration |
| `timed_out` state | iot-gateway | Requires gateway-side dispatch timeout |
| `cancelled` state | iot-gateway | Requires operator cancellation API |
| AI-proposed → operator approval gate | dashboard / AI service | Requires ADR-0006 Layer 4 policy |
| Operator session / JWT token issuance | auth service | Out of scope for this spec |
| Per-device MQTT topic ACL enforcement | MQTT broker | Issue #41 |

**The current gateway** (`api.py`) is **unchanged** until implementation begins. The `/commands/*` endpoints are added by the implementation workstream.

---

## 6. Relationship to ADR-0006 and Issue #30

### 6.1 ADR-0006 (Local Physical Command Safety)

This spec implements **Layer 1** (MQTT broker ACL, via Issue #41) and **Layer 4** (operator approval gate) from the perspective of the gateway/dashboard. The bridge enforces Layers 2 and 3 unchanged.

| ADR-0006 Layer | How this spec addresses it |
|----------------|----------------------------|
| Layer 1 — MQTT broker ACL | MQTT broker rejects any client not in the `command-publisher` ACL group; enforced outside the gateway |
| Layer 2 — ESP32 bridge validation | Unchanged; `unknown_command`, `queue_full`, `invalid_json` ACKs remain the first line of defense |
| Layer 3 — Mega local safety | Gateway records the limit profile used during pre-authorization; does not duplicate Mega enforcement |
| Layer 4 — AI/Twin fail-closed | Browser (Twin) is `read_only` role; AI proposals require explicit operator confirmation step |

### 6.2 Issue #30 (Command Authorization Lifecycle)

Issue #30 §2 defines the **8-state state machine** that this spec adopts. Issue #30 §3 identifies the gap items this spec begins to fill.

This spec is the **API-facing complement** to Issue #30:
- Issue #30 specifies the internal state machine and authorization logic
- Issue #40 specifies the REST API contract, role model, and human-in-the-loop console contract

Both specs share:
- The same command registry schema (to be defined in Issue #30 implementation)
- The same MQTT command/ack topics from `mqtt-contract.md`
- The same ADR-0006 constraint model

---

## 7. Open Questions

1. **Command registry backend:** In-process dict (sufficient for single-instance gateway) or Redis (required for multi-instance HA)?
2. **Dispatch timeout:** Issue #30 §5 Q2 — what is the gateway timeout? Bridge retries 3 × 1 s = 3 s. Should gateway timeout = 10 s to account for MQTT delivery variance?
3. **AI approval gate:** Is the confirmation dialog in the browser sufficient, or does the AI service need its own proposal/approval API?
4. **Read-only device scope:** Can a `read_only` user query commands for any device, or only devices they are assigned to?
5. **E-Stop confirmation:** Should `E_STOP` require a second confirmation click ("Are you sure?") in the UI, separate from the normal confirmation flow?
