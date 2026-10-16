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
