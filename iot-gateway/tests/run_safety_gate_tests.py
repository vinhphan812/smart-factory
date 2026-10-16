"""Minimal test runner for safety_gate tests.

This script runs the safety_gate tests without needing the full pytest infrastructure.
"""

import sys
import time
sys.path.insert(0, 'src')

# Import the safety_gate module
from iot_gateway.safety_gate import (
    SafetyGate,
    SafetyRuleConfig,
    SafetyDecision,
    Verdict,
    ReasonCode,
    IssuerType,
)

def test_permit_when_all_conditions_met():
    """PERMIT when data is fresh, confidence is high, no emergency/interlock."""
    config = SafetyRuleConfig(
        max_data_age_seconds=5.0,
        min_confidence_threshold=0.8,
        emergency_stop_active=False,
        interlocks={},
    )
    gate = SafetyGate(config)

    current_time_ms = int(time.time() * 1000)

    decision = gate.evaluate(
        command_id="cmd-001",
        device_id="conveyor-01",
        command_name="CONVEYOR_START",
        confidence=0.95,
        data_timestamp_ms=current_time_ms,
    )

    assert decision.verdict == Verdict.PERMIT, f"Expected PERMIT, got {decision.verdict}"
    assert decision.reason_code == ReasonCode.ALL_CRITERIA_MET
    print("PASS: test_permit_when_all_conditions_met")

def test_deny_when_data_stale():
    """DENY when data exceeds max age threshold."""
    config = SafetyRuleConfig(max_data_age_seconds=5.0)
    gate = SafetyGate(config)

    stale_time_ms = int(time.time() * 1000) - (10 * 1000)

    decision = gate.evaluate(
        command_id="cmd-004",
        device_id="conveyor-01",
        command_name="CONVEYOR_START",
        confidence=0.95,
        data_timestamp_ms=stale_time_ms,
    )

    assert decision.verdict == Verdict.DENY, f"Expected DENY, got {decision.verdict}"
    assert decision.reason_code == ReasonCode.STALE_DATA
    print("PASS: test_deny_when_data_stale")

def test_deny_when_confidence_below_threshold():
    """DENY when AI confidence is below configured threshold."""
    config = SafetyRuleConfig(min_confidence_threshold=0.8)
    gate = SafetyGate(config)

    decision = gate.evaluate(
        command_id="cmd-006",
        device_id="conveyor-01",
        command_name="CONVEYOR_START",
        confidence=0.6,
        data_timestamp_ms=None,
    )

    assert decision.verdict == Verdict.DENY, f"Expected DENY, got {decision.verdict}"
    assert decision.reason_code == ReasonCode.LOW_CONFIDENCE
    print("PASS: test_deny_when_confidence_below_threshold")

def test_deny_all_on_emergency_stop():
    """DENY all commands when emergency stop is active."""
    config = SafetyRuleConfig(emergency_stop_active=True)
    gate = SafetyGate(config)

    decision = gate.evaluate(
        command_id="cmd-008",
        device_id="conveyor-01",
        command_name="CONVEYOR_START",
        confidence=0.99,
        data_timestamp_ms=int(time.time() * 1000),
    )

    assert decision.verdict == Verdict.DENY, f"Expected DENY, got {decision.verdict}"
    assert decision.reason_code == ReasonCode.EMERGENCY_STOP
    print("PASS: test_deny_all_on_emergency_stop")

def test_deny_on_interlock_active():
    """DENY when device has active interlock."""
    config = SafetyRuleConfig(interlocks={"conveyor-01": True})
    gate = SafetyGate(config)

    decision = gate.evaluate(
        command_id="cmd-009",
        device_id="conveyor-01",
        command_name="CONVEYOR_START",
        confidence=0.95,
        data_timestamp_ms=None,
    )

    assert decision.verdict == Verdict.DENY, f"Expected DENY, got {decision.verdict}"
    assert decision.reason_code == ReasonCode.INTERLOCK_VIOLATION
    print("PASS: test_deny_on_interlock_active")

def test_hold_on_operator_override_active():
    """HOLD when operator override is active and awaiting re-authorization."""
    gate = SafetyGate()
    gate.activate_operator_override()

    decision = gate.evaluate(
        command_id="cmd-011",
        device_id="conveyor-01",
        command_name="CONVEYOR_START",
        confidence=0.95,
        data_timestamp_ms=None,
    )

    assert decision.verdict == Verdict.HOLD, f"Expected HOLD, got {decision.verdict}"
    assert decision.reason_code == ReasonCode.OPERATOR_OVERRIDE
    assert decision.issuer == IssuerType.HUMAN
    print("PASS: test_hold_on_operator_override_active")

def test_permit_after_override_authorization():
    """PERMIT after operator override with re-authorization."""
    gate = SafetyGate()
    gate.activate_operator_override()
    gate.authorize_after_override()

    decision = gate.evaluate(
        command_id="cmd-012",
        device_id="conveyor-01",
        command_name="CONVEYOR_START",
        confidence=0.95,
        data_timestamp_ms=None,
    )

    assert decision.verdict == Verdict.PERMIT, f"Expected PERMIT, got {decision.verdict}"
    print("PASS: test_permit_after_override_authorization")

def test_audit_log_stores_decisions():
    """Every decision is logged to the audit log."""
    gate = SafetyGate()

    gate.evaluate(
        command_id="cmd-014",
        device_id="conveyor-01",
        command_name="CONVEYOR_START",
        confidence=0.95,
        data_timestamp_ms=None,
    )

    log = gate.audit_log
    assert len(log) == 1, f"Expected 1 log entry, got {len(log)}"
    assert log[0].command_id == "cmd-014"
    print("PASS: test_audit_log_stores_decisions")

def test_audit_log_contains_only_envelope_metadata():
    """Audit log stores only non-sensitive envelope metadata."""
    gate = SafetyGate()

    gate.evaluate(
        command_id="cmd-015",
        device_id="conveyor-01",
        command_name="CONVEYOR_START",
        confidence=0.95,
        data_timestamp_ms=None,
    )

    log = gate.audit_log[0]

    # Should have envelope fields
    assert log.decision_id is not None
    assert log.command_id == "cmd-015"
    assert log.device_id == "conveyor-01"
    print("PASS: test_audit_log_contains_only_envelope_metadata")

def test_status_returns_non_sensitive_info():
    """Status endpoint returns only non-sensitive configuration."""
    config = SafetyRuleConfig(
        max_data_age_seconds=5.0,
        min_confidence_threshold=0.8,
        emergency_stop_active=False,
        interlocks={"conveyor-01": True},
    )
    gate = SafetyGate(config)
    gate.activate_operator_override()

    status = gate.get_status()

    assert "emergency_stop_active" in status
    assert "operator_override_active" in status
    assert "config" in status
    assert status["config"]["max_data_age_seconds"] == 5.0
    print("PASS: test_status_returns_non_sensitive_info")

def test_safety_decision_to_dict():
    """SafetyDecision serializes correctly to dict."""
    decision = SafetyDecision(
        decision_id="dec-001",
        command_id="cmd-001",
        device_id="conveyor-01",
        command_name="CONVEYOR_START",
        verdict=Verdict.PERMIT,
        reason_code=ReasonCode.ALL_CRITERIA_MET,
        confidence=0.95,
        issuer=IssuerType.AUTOMATED,
    )

    d = decision.to_dict()

    assert d["decision_id"] == "dec-001"
    assert d["command_id"] == "cmd-001"
    assert d["verdict"] == "PERMIT"
    assert d["reason_code"] == "ALL_CRITERIA_MET"
    assert d["confidence"] == 0.95
    print("PASS: test_safety_decision_to_dict")

if __name__ == "__main__":
    print("Running safety_gate tests...")
    print()
    
    tests = [
        test_permit_when_all_conditions_met,
        test_deny_when_data_stale,
        test_deny_when_confidence_below_threshold,
        test_deny_all_on_emergency_stop,
        test_deny_on_interlock_active,
        test_hold_on_operator_override_active,
        test_permit_after_override_authorization,
        test_audit_log_stores_decisions,
        test_audit_log_contains_only_envelope_metadata,
        test_status_returns_non_sensitive_info,
        test_safety_decision_to_dict,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {e}")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    
    sys.exit(0 if failed == 0 else 1)
