# Edge Anomaly Detection, Alert Triage, and Human-Safe Response Pipeline

**Issue:** #14  
**Status:** Design spec (L2-implementable)  
**Author:** dev-backend  
**Reviewer:** vinhphan812  
**Branch:** smart-factory/t_d8b0d15a-14-edge-anomaly-detection-alert-triage-a

---

## 1. Overview

This document specifies the edge anomaly detection pipeline, alert triage system, and human-safe response workflow for the Smart Factory. The system monitors the event store for anomalous conditions, triages alerts by severity and source, and provides bounded, human-approved responses via MiniAlpha.

**Design constraints:**
- **BLOCKED-simulator:** Rule-based detection trainable on scripted fixtures without physical factory
- **Fail-closed:** AI never overrides physical safety interlocks or initiates unapproved rescue actions
- **Human-in-the-loop:** All AI-suggested responses require operator approval before execution

---

## 2. Architecture

### 2.1 High-Level Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Event Store    │────▶│ Anomaly Detector │────▶│ Alert Triage    │
│  (SQLite)       │     │  (rule-based)    │     │  (severity)     │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  MiniAlpha      │◀────│ Response Guard  │◀────│ Operator        │
│  (bounded)      │     │  (safety check)  │     │  (approval)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **EventPoller** | Subscribes to event store changes; triggers detection on new telemetry/heartbeat events |
| **AnomalyDetector** | Applies rule-based detection logic; outputs anomaly scores |
| **AlertTriage** | Assigns severity, source, and recommended actions based on detected anomalies |
| **ResponseGuard** | Validates proposed responses against safety constraints; blocks unsafe actions |
| **OperatorNotifier** | Sends notifications to operators (webhook, dashboard) with approval buttons |
| **ResponseExecutor** | Executes approved bounded commands via gateway MQTT |

---

## 3. Anomaly Detection Rules

### 3.1 Rule Taxonomy

Rules are deterministic and trainable on scripted fixtures. Each rule maps to specific sensor patterns.

| Rule ID | Name | Condition | Severity | Source |
|---------|------|-----------|----------|--------|
| R001 | Conveyor Jam | `speed < 5` for > 30s | CRITICAL | conveyor |
| R002 | Conveyor Stopped | `status == STOPPED` unexpectedly | WARNING | conveyor |
| R003 | High Temperature | `temp > 8000` (>80°C) | CRITICAL | temperature |
| R004 | Elevated Temperature | `temp > 6000` (>60°C) | WARNING | temperature |
| R005 | Humidity Out of Range | `humidity < 2000` or `> 8000` | WARNING | humidity |
| R006 | Device Offline | `status_offline` received | INFO | system |
| R007 | Stale Telemetry | No telemetry for > 60s | WARNING | sensor |
| R008 | Heartbeat Missing | No heartbeat for > 120s | CRITICAL | system |
| R009 | Command Timeout | Command pending for > 30s | WARNING | system |
| R010 | Command Failed | Command status == FAILED | WARNING | system |

### 3.2 Rule Engine Interface

```python
@dataclass
class DetectionRule:
    rule_id: str
    name: str
    condition: Callable[[CanonicalEvent], bool]
    severity: AlertSeverity
    source: AlertSource
    recommended_action: str

class AnomalyDetector:
    def __init__(self, rules: list[DetectionRule]) -> None:
        self._rules = {r.rule_id: r for r in rules}

    async def detect(self, event: CanonicalEvent) -> list[AlertEvent]:
        """Apply all rules to event, return matching alerts."""
        alerts = []
        for rule in self._rules.values():
            if rule.condition(event):
                alerts.append(AlertEvent(
                    severity=rule.severity,
                    source=rule.source,
                    message=f"{rule.name}: {self._format_event(event)}",
                    recommended_action=rule.recommended_action,
                    metadata={"rule_id": rule.rule_id, "event": event.to_dict()},
                ))
        return alerts
```

### 3.3 Scripted Test Fixtures

Rules are validated against scripted fixtures in `edge-ai-robot/tests/fixtures/`:

```
fixtures/
├── conveyor_jam.json      # speed < 5 for 30s sequence
├── conveyor_stopped.json   # unexpected STOPPED status
├── high_temperature.json   # temp > 8000
├── elevated_temp.json      # temp > 6000
├── humidity_out_of_range.json
├── device_offline.json
├── stale_telemetry.json    # gap > 60s
├── heartbeat_missing.json  # gap > 120s
├── command_timeout.json
└── command_failed.json
```

Each fixture contains a sequence of canonical events that trigger the corresponding rule.

---

## 4. Alert Triage

### 4.1 Triage Logic

Alert triage enriches raw anomaly detections with contextual metadata:

```python
class AlertTriage:
    def __init__(self, detector: AnomalyDetector) -> None:
        self._detector = detector

    async def triage(self, event: CanonicalEvent) -> list[AlertEvent]:
        """Enrich alerts with device context and dedupe."""
        raw_alerts = await self._detector.detect(event)

        # Deduplicate: collapse repeated alerts for same device/rule within 60s
        enriched = []
        for alert in raw_alerts:
            alert.metadata["device_context"] = self._get_device_context(alert.device_id)
            alert.metadata["event_timestamp"] = event.timestamp
            enriched.append(alert)

        return enriched

    def _get_device_context(self, device_id: str | None) -> dict:
        """Fetch latest known state for device from event store."""
        # Query event store for latest STATUS_ONLINE event
        ...
```

### 4.2 Severity Escalation Rules

| Condition | Escalation |
|-----------|------------|
| 3+ CRITICAL alerts within 60s | Escalate to emergency broadcast |
| Same rule triggers 5+ times in 5min | Escalate severity by one level |
| Device offline + command pending | Escalate to WARNING |

---

## 5. Human-Safe Response Pipeline

### 5.1 Safety Principles

1. **Fail-closed:** AI never issues commands that bypass safety interlocks
2. **Human approval:** All response actions require operator approval
3. **Bounded actions:** AI can only suggest pre-approved bounded skills
4. **Audit trail:** All decisions logged with trace IDs

### 5.2 Response Categories

| Category | Description | Example | Requires Approval |
|----------|-------------|---------|-------------------|
| **INFORM** | Notify operator, no action | "Conveyor speed low" | No |
| **INVESTIGATE** | Request operator inspection | "Check conveyor belt" | No |
| **CONFIRM** | Request confirmation before proceeding | "Restart conveyor?" | Yes |
| **EMERGENCY** | Trigger E-stop via safety gate | "Emergency stop" | Yes (explicit) |

### 5.3 Response Guard

```python
class ResponseGuard:
    """Validates proposed responses against safety constraints."""

    # Skills that AI may suggest (bounded, pre-approved)
    ALLOWED_SKILLS = {
        "conveyor_restart": {"max_attempts": 1, "requires_confirmation": True},
        "conveyor_stop": {"max_attempts": 1, "requires_confirmation": False},
        "report_incident": {"max_attempts": 0, "requires_confirmation": False},
        "request_inspection": {"max_attempts": 0, "requires_confirmation": False},
    }

    # Skills that AI may NEVER suggest
    BLOCKED_SKILLS = {"motor_override", "estop_override", "unlimited_motion"}

    def validate(self, proposed_skill: str, context: dict) -> ValidationResult:
        """Validate if proposed skill is allowed given context."""
        if proposed_skill in self.BLOCKED_SKILLS:
            return ValidationResult(allowed=False, reason="Blocked by safety policy")

        if proposed_skill not in self.ALLOWED_SKILLS:
            return ValidationResult(allowed=False, reason="Unknown skill")

        skill_config = self.ALLOWED_SKILLS[proposed_skill]
        if skill_config["requires_confirmation"] and not context.get("operator_approved"):
            return ValidationResult(allowed=False, reason="Requires operator approval")

        return ValidationResult(allowed=True)
```

### 5.4 Approval Workflow

```
Alert → Triage → Guard Check → Operator Notification → Approval → Execute
                            ↓
                      Blocked → Log & Notify Security
```

1. **Alert detected** → Triage enriches with context
2. **Guard validates** → Checks skill allowlist, confirmation requirements
3. **Notification sent** → Webhook to dashboard with approval token
4. **Operator approves** → POST /alerts/{id}/approve with token
5. **Executor runs** → Sends bounded command via gateway MQTT

---

## 6. API Contracts

### 6.1 Event Polling Endpoint

```
WS /ws/events
```

WebSocket stream of canonical events from event store (polling new inserts).

### 6.2 Alert API

| Method | Path | Description |
|--------|------|-------------|
| GET | /alerts | List active alerts |
| GET | /alerts/{alert_id} | Get alert details |
| POST | /alerts/{alert_id}/acknowledge | Acknowledge alert |
| POST | /alerts/{alert_id}/resolve | Resolve alert (after action taken) |
| POST | /alerts/{alert_id}/approve | Approve AI-suggested response |
| POST | /alerts/{alert_id}/reject | Reject AI-suggested response |

### 6.3 Response Execution

```
POST /commands
{
  "device_id": "ukit-00000000",
  "command": "CONVEYOR_START",
  "args": ["60"],
  "approved_by": "operator-123",
  "alert_id": "alert-uuid"
}
```

---

## 7. Implementation Plan

### Phase 1: Detection Rules (L2)
- [ ] Implement `DetectionRule` dataclass and `AnomalyDetector`
- [ ] Add rules R001-R010 with scripted test fixtures
- [ ] Unit tests for each rule with fixture validation

### Phase 2: Alert Triage (L2)
- [ ] Implement `AlertTriage` with deduplication
- [ ] Severity escalation logic
- [ ] Integration with existing `AlertService`

### Phase 3: Response Guard (L2)
- [ ] Implement `ResponseGuard` with skill allowlist
- [ ] Blocked skills enforcement
- [ ] Approval token generation and validation

### Phase 4: Operator Integration (L2)
- [ ] Dashboard webhook handler for alert notifications
- [ ] Approval/rejection endpoints
- [ ] Audit logging for all decisions

### Phase 5: Physical HIL (L5 - blocked)
- [ ] Validate rules on physical hardware
- [ ] Tune thresholds based on real sensor data
- [ ] Safety gate integration

---

## 8. Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Event store (issue #31) | Implemented | SQLite event store exists |
| Alert service (issue #33) | Implemented | AlertService with handlers |
| MiniAlpha adapter (issue #13) | BLOCKED-simulator | Mock adapter implementable now |
| Gateway MQTT | Implemented | Command publishing works |

---

## 9. Security Considerations

1. **SSRF Protection:** Webhook notifications enforce host allowlist (per existing `WebhookNotification`)
2. **No PII in Logs:** Alert metadata sanitized before logging
3. **Approval Tokens:** Signed JWT tokens with expiry for response approval
4. **Rate Limiting:** Alert deduplication prevents notification flood
5. **Audit Trail:** All AI decisions logged with trace IDs for forensics

---

## 10. Not In Scope

- **ML-based anomaly detection:** Rule-based only for L2; ML evaluation blocked by #38
- **Physical robot HIL:** MiniAlpha physical unit confirmation pending (#13)
- **Auto-remediation without approval:** All actions require human approval
- **Email/SMS notifications:** Dashboard webhook only

---

## 11. References

- [Alert Notification Contract](../alerts/notification-contract.md)
- [Event Store Contract](../../docs/issue-31-event-store-contract.md)
- [Edge AI Robot README](../../edge-ai-robot/README.md)
- [Architecture Overview](../../docs/architecture/overview.md)
- [Safety Gate ADR](../../docs/adr/adr-0006-local-physical-safety.md)
