# ADR-0013: Edge AI Safety Gate

**Status:** Proposed
**Date:** 2026-10-16
**Deciders:** Issue #37
**Related issues:** #37

## Context

The Smart Factory system uses AI inference to generate proposed actions for physical actuators (conveyor belts, motors, etc.). Issue #37 requires implementing a fail-closed safety decision gate between AI inference and physical robot actions.

The gate must ensure:
- Default: DENY unless all PERMIT criteria are explicitly met
- AI cannot bypass the gate
- Only operator/manual override can temporarily HOLD (not PERMIT) commands
- Mandatory re-authorization after any operator override

## Decision

We implement a `SafetyGate` class in `iot-gateway/src/iot_gateway/safety_gate.py` that evaluates proposed commands against configurable safety rules.

### Safety Gate Interface

**Inputs:**
- `command_id`: Unique command identifier (envelope)
- `device_id`: Target device identifier
- `command_name`: Command type (e.g., CONVEYOR_START)
- `confidence`: AI confidence score (0.0 to 1.0)
- `data_timestamp_ms`: Timestamp of AI inference (for staleness check)

**Outputs:**
- `SafetyDecision` with verdict (PERMIT/DENY/HOLD), reason_code, and metadata

**Safety Conditions:**
1. **Staleness**: Data must be within `max_data_age_seconds` (default: 5.0s)
2. **Confidence threshold**: AI confidence must exceed `min_confidence_threshold` (default: 0.8)
3. **Emergency stop**: If active, all commands are DENIED
4. **Interlock**: Device-specific interlocks block commands when active
5. **Operator override**: Temporarily HOLDS commands, requires re-authorization

### Default-Deny Rule

The safety gate operates on a **default-deny** policy:
- Unless ALL PERMIT criteria are met, the command is DENIED
- This is the inverse of typical "allow by default" systems
- Ensures no unsafe command proceeds accidentally

### Operator Override Protocol

1. Operator activates override via API: `POST /safety-gate/operator-override`
2. Gate enters HOLD state: commands are HELD, not PERMITed
3. After investigation, operator explicitly re-authorizes: `POST /safety-gate/authorize`
4. Gate returns to normal operation

**Critical**: Operator override can only HOLD, never PERMIT. Re-authorization is mandatory before any command can proceed.

### SafetyDecision Envelope

```python
@dataclass
class SafetyDecision:
    decision_id: str          # Unique decision ID
    command_id: str           # Envelope command_id (not content)
    device_id: str            # Target device
    command_name: str         # Command name only
    verdict: Verdict         # PERMIT/DENY/HOLD
    reason_code: ReasonCode   # Detailed reason
    confidence: float         # AI confidence
    timestamp: str            # ISO 8601 timestamp
    issuer: IssuerType        # AUTOMATED or HUMAN
```

### Audit Trail

Every decision is logged with non-sensitive envelope metadata only:
- decision_id, command_id (envelope), verdict, reason_code
- confidence, timestamp, issuer

**NOT logged**: Command arguments (to protect potential secrets)

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/safety-gate/status` | GET | Current gate status (non-sensitive) |
| `/safety-gate/audit-log` | GET | Decision audit trail |
| `/safety-gate/emergency-stop` | POST | Activate/deactivate emergency stop |
| `/safety-gate/interlock/{device_id}` | POST | Set device interlock |
| `/safety-gate/operator-override` | POST | Activate operator hold |
| `/safety-gate/authorize` | POST | Re-authorize after override |

## Consequences

**Positive:**
- Explicit, auditable safety decisions
- Default-deny ensures no accidental command execution
- Non-bypassable by AI systems
- Operator override with mandatory re-authorization
- Complete audit trail for compliance

**Negative:**
- Additional latency for safety evaluation
- Requires proper configuration tuning (thresholds)
- Must be integrated into command pipeline

## Alternatives Considered

**Option A: ML-based safety classifier**
- Rejected: Cannot be validated as safety-critical without extensive HIL testing

**Option B: Simple rule-based in ESP32 bridge**
- Rejected: Bridge doesn't have access to AI confidence scores

**Option C: Cloud-based safety service**
- Rejected: Latency and availability concerns for safety-critical path

## Evidence

- Implementation: `iot-gateway/src/iot_gateway/safety_gate.py`
- Tests: `iot-gateway/tests/test_safety_gate.py` (48 unit tests)
- API integration: `iot-gateway/src/iot_gateway/api.py`
- ADR proposed: this record

## Implementation

- Module: `iot-gateway/src/iot_gateway/safety_gate.py`
- Tests: `iot-gateway/tests/test_safety_gate.py`
- Integrated into: `iot-gateway/src/iot_gateway/api.py`

## Integration Gap (L0 — Static Analysis)

> **Reviewer finding (PR #110):** Unit tests verify gate evaluation in isolation, but do not demonstrate gate execution on the actual physical command path.

### (1) Gateway does NOT currently intercept MQTT dispatch

The gateway (`gateway.py`) is a **read-only MQTT subscriber**. Its data flow is:

```
MQTT broker → MqttSubscriber → EventNormalizer → write queue → EventStore → WebSocket broadcast
```

`gateway.py` has no publish capability (`_mqtt_publisher` absent, no `publish()` method). The `SafetyGate` class is integrated into the HTTP API layer (`api.py`) as an **evaluation service**, not as an **MQTT dispatch interceptor**. There is no gate-wrapped MQTT publish path in the gateway today.

**What this means:** Calling `SafetyGate.evaluate()` returns a verdict; nothing in the gateway blocks or rewrites MQTT messages based on that verdict. A consumer that ignores the verdict can still publish commands directly to the broker.

### (2) Consumers must enforce verdicts

Any system that **publishes** commands to the broker is responsible for:

1. Calling `SafetyGate.evaluate()` with the command's envelope before dispatch.
2. Checking `decision.verdict` — if not `PERMIT`, the command MUST NOT be dispatched.
3. Logging or alerting on non-PERMIT verdicts for audit.

The gate is **advisory at the API boundary**; it is **enforced by contract** at each consumer. Consumers include (but are not limited to):
- AI inference pipelines that generate actuator commands
- Operator dashboards that issue manual commands
- Any service that bridges between AI/Twin and the MQTT command topic

### (3) Hardware E-stop is last line of defense

The software `SafetyGate` — even if correctly enforced by all consumers — cannot override physical safety hardware:

- **Hardware E-stop buttons** are hardwired to motor drivers and cut power independently of any software path.
- **Hardware interlocks** (e.g., door sensors, light curtains) are wired to the ESP32-uKit bridge via digital inputs; the bridge treats `HW_INTERLOCK` as an immutable `DENY` regardless of software state.
- Software can set `emergency_stop_active` in `SafetyRuleConfig`, but this only affects the gate's logical verdict — it does not physically cut power. The bridge must map this to an actual relay/open collector output.

The hardware E-stop is the **authoritative last line of defense** when all software safety measures fail.

### (4) Test evidence: unit tests pass, no E2E physical path test exists

| Level | What is tested | What is NOT tested |
|-------|---------------|-------------------|
| L1 unit | `SafetyGate.evaluate()` returns correct verdicts for each condition (stale, low confidence, interlock, emergency stop, operator override, hardware interlock). `SafetyDecision` serialization. Audit log envelope-only storage. | — |
| L2 simulation | — | Command pipeline: AI → evaluate → MQTT publish → bridge receives command |
| L3 bench | — | Physical actuator response to PERMIT vs DENY verdicts |
| L4 HIL | — | ESP32 bridge receives MQTT command, gate verdict honored, motor starts/stops accordingly |
| L5 integrated | — | Full chain: AI inference → safety gate → MQTT publish → ESP32 bridge → motor control → position sensor feedback |

**Unit tests pass:** `test_safety_gate.py` runs 48 assertions against `SafetyGate.evaluate()` in isolation with mocked time. All pass.

**No E2E physical path test exists:** There is no integration test that sends a command through the actual MQTT publish path and verifies the bridge enforces the gate verdict. This is a **documented gap** pending HIL testing infrastructure (Issue #37 sub-task).

**Required for L4/L5:** A test that:
1. Spins up a real (or mock) MQTT broker.
2. Calls `SafetyGate.evaluate()` → gets `PERMIT`.
3. Publishes the command to `smart-factory/{device_id}/command`.
4. Verifies the ESP32 bridge receives and executes the command.
5. Then re-evaluates with stale data → gets `DENY`.
6. Publishes the same command.
7. Verifies the bridge **does not execute** the command.

This test is blocked on HIL test infrastructure and is tracked separately from the safety gate implementation.
