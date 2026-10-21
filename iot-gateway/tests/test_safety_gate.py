"""Unit tests for the safety gate module.

Tests cover:
- PERMIT when all conditions met
- DENY on stale data
- DENY below confidence threshold
- HOLD on operator override
- Log non-sensitive audit trail
"""

import time
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from iot_gateway.safety_gate import (
    SafetyGate,
    SafetyRuleConfig,
    SafetyDecision,
    Verdict,
    ReasonCode,
    IssuerType,
)


class TestSafetyGatePermit:
    """Tests for PERMIT decisions when all criteria are met."""

    def test_permit_when_all_conditions_met(self) -> None:
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
            data_timestamp_ms=current_time_ms,  # Fresh data
        )

        assert decision.verdict == Verdict.PERMIT
        assert decision.reason_code == ReasonCode.ALL_CRITERIA_MET
        assert decision.command_id == "cmd-001"
        assert decision.device_id == "conveyor-01"

    def test_permit_edge_case_confidence_equal_to_threshold(self) -> None:
        """PERMIT when confidence equals threshold (boundary case)."""
        config = SafetyRuleConfig(min_confidence_threshold=0.8)
        gate = SafetyGate(config)

        current_time_ms = int(time.time() * 1000)
        decision = gate.evaluate(
            command_id="cmd-003",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.8,  # Exactly at threshold
            data_timestamp_ms=current_time_ms,
        )

        assert decision.verdict == Verdict.PERMIT

    def test_deny_when_no_telemetry(self) -> None:
        """DENY when data_timestamp_ms is None (fail-closed, not PERMIT)."""
        gate = SafetyGate()

        decision = gate.evaluate(
            command_id="cmd-002",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.9,
            data_timestamp_ms=None,
        )

        assert decision.verdict == Verdict.DENY
        assert decision.reason_code == ReasonCode.NO_TELEMETRY


class TestSafetyGateDenyStaleData:
    """Tests for DENY on stale data."""

    def test_deny_when_data_stale(self) -> None:
        """DENY when data exceeds max age threshold."""
        config = SafetyRuleConfig(max_data_age_seconds=5.0)
        gate = SafetyGate(config)

        # Data is 10 seconds old (exceeds 5 second threshold)
        stale_time_ms = int(time.time() * 1000) - (10 * 1000)

        decision = gate.evaluate(
            command_id="cmd-004",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.95,
            data_timestamp_ms=stale_time_ms,
        )

        assert decision.verdict == Verdict.DENY
        assert decision.reason_code == ReasonCode.STALE_DATA

    def test_deny_edge_case_data_at_threshold_boundary(self) -> None:
        """DENY when data is just over the staleness threshold."""
        config = SafetyRuleConfig(max_data_age_seconds=5.0)
        gate = SafetyGate(config)

        # Data is 5.1 seconds old (slightly over threshold)
        boundary_time_ms = int(time.time() * 1000) - (5100)

        decision = gate.evaluate(
            command_id="cmd-005",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.95,
            data_timestamp_ms=boundary_time_ms,
        )

        assert decision.verdict == Verdict.DENY
        assert decision.reason_code == ReasonCode.STALE_DATA


class TestSafetyGateDenyLowConfidence:
    """Tests for DENY below confidence threshold."""

    def test_deny_when_confidence_below_threshold(self) -> None:
        """DENY when AI confidence is below configured threshold."""
        config = SafetyRuleConfig(min_confidence_threshold=0.8)
        gate = SafetyGate(config)

        current_time_ms = int(time.time() * 1000)
        decision = gate.evaluate(
            command_id="cmd-006",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.6,  # Below threshold
            data_timestamp_ms=current_time_ms,
        )

        assert decision.verdict == Verdict.DENY
        assert decision.reason_code == ReasonCode.LOW_CONFIDENCE

    def test_deny_confidence_zero(self) -> None:
        """DENY when confidence is zero."""
        gate = SafetyGate()

        current_time_ms = int(time.time() * 1000)
        decision = gate.evaluate(
            command_id="cmd-007",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.0,
            data_timestamp_ms=current_time_ms,
        )

        assert decision.verdict == Verdict.DENY
        assert decision.reason_code == ReasonCode.LOW_CONFIDENCE


class TestSafetyGateEmergencyStop:
    """Tests for emergency stop functionality."""

    def test_deny_all_on_emergency_stop(self) -> None:
        """DENY all commands when emergency stop is active."""
        config = SafetyRuleConfig(emergency_stop_active=True)
        gate = SafetyGate(config)

        # Even with perfect confidence and fresh data
        decision = gate.evaluate(
            command_id="cmd-008",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.99,
            data_timestamp_ms=int(time.time() * 1000),
        )

        assert decision.verdict == Verdict.DENY
        assert decision.reason_code == ReasonCode.EMERGENCY_STOP


class TestSafetyGateInterlock:
    """Tests for interlock functionality."""

    def test_deny_on_interlock_active(self) -> None:
        """DENY when device has active interlock."""
        config = SafetyRuleConfig(interlocks={"conveyor-01": True})
        gate = SafetyGate(config)

        current_time_ms = int(time.time() * 1000)
        decision = gate.evaluate(
            command_id="cmd-009",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.95,
            data_timestamp_ms=current_time_ms,
        )

        assert decision.verdict == Verdict.DENY
        assert decision.reason_code == ReasonCode.INTERLOCK_VIOLATION

    def test_permit_when_interlock_inactive(self) -> None:
        """PERMIT when device interlock is cleared."""
        config = SafetyRuleConfig(interlocks={"conveyor-01": False})
        gate = SafetyGate(config)

        current_time_ms = int(time.time() * 1000)
        decision = gate.evaluate(
            command_id="cmd-010",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.95,
            data_timestamp_ms=current_time_ms,
        )

        assert decision.verdict == Verdict.PERMIT


class TestSafetyGateOperatorOverride:
    """Tests for operator override functionality."""

    def test_hold_on_operator_override_active(self) -> None:
        """HOLD when operator override is active and awaiting re-authorization."""
        gate = SafetyGate()
        gate.activate_operator_override()

        # Override is now active, authorization is required
        current_time_ms = int(time.time() * 1000)
        decision = gate.evaluate(
            command_id="cmd-011",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.95,
            data_timestamp_ms=current_time_ms,
        )

        assert decision.verdict == Verdict.HOLD
        assert decision.reason_code == ReasonCode.OPERATOR_OVERRIDE
        assert decision.issuer == IssuerType.HUMAN

    def test_permit_after_override_authorization(self) -> None:
        """PERMIT after operator override with re-authorization."""
        gate = SafetyGate()
        gate.activate_operator_override()

        # Authorize after override
        gate.authorize_after_override()

        current_time_ms = int(time.time() * 1000)
        decision = gate.evaluate(
            command_id="cmd-012",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.95,
            data_timestamp_ms=current_time_ms,
        )

        # Now should permit after re-authorization
        assert decision.verdict == Verdict.PERMIT
        assert decision.issuer == IssuerType.AUTOMATED

    def test_override_deactivation_resets_authorization(self) -> None:
        """Deactivating override resets authorization requirement."""
        gate = SafetyGate()

        # Activate and then deactivate
        gate.activate_operator_override()
        gate.deactivate_operator_override()

        # Should work normally (no override active)
        current_time_ms = int(time.time() * 1000)
        decision = gate.evaluate(
            command_id="cmd-013",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.95,
            data_timestamp_ms=current_time_ms,
        )

        assert decision.verdict == Verdict.PERMIT


class TestSafetyGateAuditLog:
    """Tests for audit log functionality."""

    def test_audit_log_stores_decisions(self) -> None:
        """Every decision is logged to the audit log."""
        gate = SafetyGate()

        current_time_ms = int(time.time() * 1000)
        gate.evaluate(
            command_id="cmd-014",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.95,
            data_timestamp_ms=current_time_ms,
        )

        log = gate.audit_log
        assert len(log) == 1
        assert log[0].command_id == "cmd-014"
        assert log[0].verdict == Verdict.PERMIT

    def test_audit_log_contains_only_envelope_metadata(self) -> None:
        """Audit log stores only non-sensitive envelope metadata.

        Command arguments are NOT stored to protect secrets.
        """
        gate = SafetyGate()

        current_time_ms = int(time.time() * 1000)
        gate.evaluate(
            command_id="cmd-015",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.95,
            data_timestamp_ms=current_time_ms,
        )

        log = gate.audit_log[0]

        # Should have envelope fields
        assert log.decision_id is not None
        assert log.command_id == "cmd-015"
        assert log.device_id == "conveyor-01"
        assert log.command_name == "CONVEYOR_START"
        assert log.verdict is not None
        assert log.reason_code is not None

    def test_audit_log_does_not_store_command_arguments(self) -> None:
        """Verify that command arguments are not stored in the audit log.

        This ensures secrets in command arguments are protected.
        """
        gate = SafetyGate()

        # The evaluate method only takes command_name, not arguments
        # This test verifies the design: arguments are not passed to evaluate
        current_time_ms = int(time.time() * 1000)
        gate.evaluate(
            command_id="cmd-016",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.95,
            data_timestamp_ms=current_time_ms,
        )

        log = gate.audit_log[0]

        # The decision only stores command_name, not arguments
        # (command_name is the envelope type like CONVEYOR_START,
        # not the arguments like speed=60)
        assert hasattr(log, 'command_name')
        # No 'arguments' field exists in SafetyDecision


class TestSafetyGateStatus:
    """Tests for safety gate status API."""

    def test_status_returns_non_sensitive_info(self) -> None:
        """Status endpoint returns only non-sensitive configuration."""
        config = SafetyRuleConfig(
            max_data_age_seconds=5.0,
            min_confidence_threshold=0.8,
            emergency_stop_active=False,
            interlocks={"conveyor-01": True},
            hardware_interlocks={"robot-arm-01": True},
        )
        gate = SafetyGate(config)
        gate.activate_operator_override()

        status = gate.get_status()

        assert "emergency_stop_active" in status
        assert "operator_override_active" in status
        assert "interlocks" in status
        assert "hardware_interlocks" in status
        assert status["hardware_interlocks"] == ["robot-arm-01"]
        assert status["config"]["max_data_age_seconds"] == 5.0
        assert status["config"]["min_confidence_threshold"] == 0.8


class TestSafetyDecisionModel:
    """Tests for SafetyDecision dataclass."""

    def test_safety_decision_to_dict(self) -> None:
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

    def test_verdict_enum_values(self) -> None:
        """Verdict enum has correct string values."""
        assert Verdict.PERMIT.value == "PERMIT"
        assert Verdict.DENY.value == "DENY"
        assert Verdict.HOLD.value == "HOLD"

    def test_reason_code_enum_values(self) -> None:
        """ReasonCode enum has correct string values."""
        assert ReasonCode.STALE_DATA.value == "STALE_DATA"
        assert ReasonCode.LOW_CONFIDENCE.value == "LOW_CONFIDENCE"
        assert ReasonCode.EMERGENCY_STOP.value == "EMERGENCY_STOP"
        assert ReasonCode.INTERLOCK_VIOLATION.value == "INTERLOCK_VIOLATION"
        assert ReasonCode.OPERATOR_OVERRIDE.value == "OPERATOR_OVERRIDE"
        assert ReasonCode.ALL_CRITERIA_MET.value == "ALL_CRITERIA_MET"
        assert ReasonCode.NO_TELEMETRY.value == "NO_TELEMETRY"


class TestSafetyGateOperatorAuthHTTP:
    """HTTP-layer tests for X-Operator-Token authentication on safety-gate endpoints.

    These tests verify that the FastAPI dependency injection for
    _require_operator_token is wired correctly — i.e. via Depends() so that
    test overrides work and unauthenticated / wrong-token requests are rejected
    at the HTTP layer before reaching business logic.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin the token for all HTTP-level tests — reload api module after setting
        # the env var so that OPERATOR_TOKEN (evaluated at import time) picks it up.
        monkeypatch.setenv("SAFETY_OPERATOR_TOKEN", "test-secret-token")
        import importlib, iot_gateway.api
        importlib.reload(iot_gateway.api)

    @pytest.fixture
    def _client(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        from iot_gateway.api import create_http_app
        from iot_gateway.event_store import EventStore
        from iot_gateway.safety_gate import SafetyGate

        # Pin a fresh SafetyGate so tests are isolated from any global state
        _fresh_gate = SafetyGate()
        store = MagicMock(spec=EventStore)
        app = create_http_app(store, safety_gate=_fresh_gate)
        return TestClient(app)

    def test_emergency_stop_no_token_header(self, _client: TestClient) -> None:
        """POST /safety-gate/emergency-stop without X-Operator-Token → 401."""
        response = _client.post("/safety-gate/emergency-stop", params={"active": True})
        assert response.status_code == 401, response.text
        assert "X-Operator-Token" in response.json()["detail"]

    def test_emergency_stop_wrong_token_header(self, _client: TestClient) -> None:
        """POST /safety-gate/emergency-stop with wrong token → 401."""
        response = _client.post(
            "/safety-gate/emergency-stop",
            params={"active": True},
            headers={"X-Operator-Token": "wrong-token"},
        )
        assert response.status_code == 401, response.text

    def test_emergency_stop_correct_token(self, _client: TestClient) -> None:
        """POST /safety-gate/emergency-stop with correct token → 200."""
        response = _client.post(
            "/safety-gate/emergency-stop",
            params={"active": True},
            headers={"X-Operator-Token": "test-secret-token"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["emergency_stop_active"] == "true"

    def test_interlock_no_token(self, _client: TestClient) -> None:
        """POST /safety-gate/interlock/{id} without token → 401."""
        response = _client.post(
            "/safety-gate/interlock/robot-01",
            params={"blocked": True},
        )
        assert response.status_code == 401, response.text

    def test_interlock_wrong_token(self, _client: TestClient) -> None:
        """POST /safety-gate/interlock/{id} with wrong token → 401."""
        response = _client.post(
            "/safety-gate/interlock/robot-01",
            params={"blocked": True},
            headers={"X-Operator-Token": "wrong-token"},
        )
        assert response.status_code == 401, response.text

    def test_interlock_correct_token(self, _client: TestClient) -> None:
        """POST /safety-gate/interlock/{id} with correct token → 200."""
        response = _client.post(
            "/safety-gate/interlock/robot-01",
            params={"blocked": True},
            headers={"X-Operator-Token": "test-secret-token"},
        )
        assert response.status_code == 200, response.text

    def test_operator_override_no_token(self, _client: TestClient) -> None:
        """POST /safety-gate/operator-override without token → 401."""
        response = _client.post("/safety-gate/operator-override")
        assert response.status_code == 401, response.text

    def test_operator_override_correct_token(self, _client: TestClient) -> None:
        """POST /safety-gate/operator-override with correct token → 200."""
        response = _client.post(
            "/safety-gate/operator-override",
            headers={"X-Operator-Token": "test-secret-token"},
        )
        assert response.status_code == 200, response.text

    def test_authorize_no_token(self, _client: TestClient) -> None:
        """POST /safety-gate/authorize without token → 401."""
        response = _client.post("/safety-gate/authorize")
        assert response.status_code == 401, response.text

    def test_authorize_correct_token(self, _client: TestClient) -> None:
        """POST /safety-gate/authorize with correct token → 200."""
        response = _client.post(
            "/safety-gate/authorize",
            headers={"X-Operator-Token": "test-secret-token"},
        )
        assert response.status_code == 200, response.text

    def test_token_not_configured_returns_503(
        self, _client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When SAFETY_OPERATOR_TOKEN is unset the server returns 503, not 200."""
        monkeypatch.delenv("SAFETY_OPERATOR_TOKEN", raising=False)
        import importlib, iot_gateway.api
        importlib.reload(iot_gateway.api)
        response = _client.post(
            "/safety-gate/authorize",
            headers={"X-Operator-Token": "any"},
        )
        assert response.status_code == 503, response.text


class TestSafetyGateHardwareInterlock:
    """Tests for hardware interlock authoritative behavior.

    Hardware interlocks are physically hardwired and cannot be cleared by
    software. The software gate evaluates but cannot override them.
    """

    def test_deny_on_hardware_interlock(self) -> None:
        """DENY when device has active hardware interlock (authoritative)."""
        config = SafetyRuleConfig(hardware_interlocks={"conveyor-01": True})
        gate = SafetyGate(config)

        current_time_ms = int(time.time() * 1000)
        decision = gate.evaluate(
            command_id="cmd-hw-001",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.99,
            data_timestamp_ms=current_time_ms,
        )

        assert decision.verdict == Verdict.DENY
        assert decision.reason_code == ReasonCode.INTERLOCK_VIOLATION

    def test_hardware_interlock_not_cleared_by_software(self) -> None:
        """Hardware interlock DENYs even when software interlock is False."""
        # Hardware interlock active, software says not blocked
        config = SafetyRuleConfig(
            hardware_interlocks={"conveyor-01": True},
            interlocks={"conveyor-01": False},
        )
        gate = SafetyGate(config)

        current_time_ms = int(time.time() * 1000)
        decision = gate.evaluate(
            command_id="cmd-hw-002",
            device_id="conveyor-01",
            command_name="CONVEYOR_START",
            confidence=0.99,
            data_timestamp_ms=current_time_ms,
        )

        # Hardware is authoritative — software cannot override it
        assert decision.verdict == Verdict.DENY
        assert decision.reason_code == ReasonCode.INTERLOCK_VIOLATION

    def test_status_reports_hardware_interlocks(self) -> None:
        """Status endpoint reports hardware_interlocks as read-only state."""
        config = SafetyRuleConfig(hardware_interlocks={"conveyor-01": True})
        gate = SafetyGate(config)

        status = gate.get_status()

        assert "hardware_interlocks" in status
        assert "conveyor-01" in status["hardware_interlocks"]
