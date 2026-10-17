"""Fail-closed safety decision gate between AI inference and physical robot actions.

This module implements a safety gate that evaluates proposed commands against
configurable safety rules. The gate operates on a default-deny policy: commands
are blocked unless all PERMIT criteria are explicitly met.

Safety Gate Philosophy:
- Default: DENY (fail-closed)
- AI cannot bypass the gate
- Only operator/manual override can temporarily HOLD (not PERMIT)
- Operator override requires mandatory re-authorization
- Every decision is logged for audit (command envelope only, not content)

Integration Note:
    The SafetyGate evaluates command SAFETY in isolation. It does NOT
    intercept the MQTT publish path. Callers MUST check the SafetyDecision
    verdict BEFORE dispatching a command to the broker. The gateway's
    MqttSubscriber (mqtt_client.py) is read-only; it has no publish method.
    Consumers that DO publish (e.g. command issuers, AI agents) are
    responsible for enforcing verdicts locally.
    See ADR-0013 §Integration Gap for full documentation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class Verdict(str, Enum):
    """Safety gate decision outcomes."""
    PERMIT = "PERMIT"  # Command allowed to proceed
    DENY = "DENY"      # Command blocked
    HOLD = "HOLD"      # Temporarily paused, awaiting re-authorization


class ReasonCode(str, Enum):
    """Reason codes for safety gate decisions."""
    # DENY reasons
    STALE_DATA = "STALE_DATA"              # Data exceeded staleness threshold
    LOW_CONFIDENCE = "LOW_CONFIDENCE"       # AI confidence below threshold
    EMERGENCY_STOP = "EMERGENCY_STOP"       # Emergency stop is active
    INTERLOCK_VIOLATION = "INTERLOCK_VIOLATION"  # Safety interlock violated
    NO_PERMIT_CRITERIA_MET = "NO_PERMIT_CRITERIA_MET"  # No criteria met
    UNKNOWN_DEVICE = "UNKNOWN_DEVICE"       # Device not recognized
    NO_TELEMETRY = "NO_TELEMETRY"           # Telemetry absent — fail-closed

    # HOLD reasons
    OPERATOR_OVERRIDE = "OPERATOR_OVERRIDE"  # Operator manually paused

    # PERMIT reasons
    ALL_CRITERIA_MET = "ALL_CRITERIA_MET"  # All safety criteria satisfied


class IssuerType(str, Enum):
    """Who or what issued the command."""
    AUTOMATED = "automated"  # AI/Twin/dashboard automated system
    HUMAN = "human"          # Human operator


@dataclass
class SafetyDecision:
    """Safety gate decision envelope.

    Every decision is logged for audit. Only non-sensitive metadata is stored:
    decision_id, command_id (envelope), verdict, reason_code, confidence,
    timestamp, issuer. Command arguments are NOT stored to protect secrets.
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command_id: str = ""  # Envelope command_id, not content
    device_id: str = ""
    command_name: str = ""  # Command name only (CONVEYOR_START, etc.)
    verdict: Verdict = Verdict.DENY
    reason_code: ReasonCode = ReasonCode.NO_PERMIT_CRITERIA_MET
    confidence: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    issuer: IssuerType = IssuerType.AUTOMATED

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "command_id": self.command_id,
            "device_id": self.device_id,
            "command_name": self.command_name,
            "verdict": self.verdict.value,
            "reason_code": self.reason_code.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "issuer": self.issuer.value,
        }


@dataclass
class SafetyRuleConfig:
    """Configurable safety rules for the gate.

    Hardware interlocks are authoritative: the software gate evaluates but
    cannot remotely clear a hardware E-stop or hardware interlock. A device
    listed in hardware_interlocks is always treated as blocked regardless of
    software state.
    """
    # Data freshness: max age in seconds for AI inference data
    max_data_age_seconds: float = 5.0

    # Minimum AI confidence threshold (0.0 to 1.0)
    min_confidence_threshold: float = 0.8

    # Emergency stop flag (software-controlled)
    emergency_stop_active: bool = False

    # Interlock states: device_id -> blocked (True = blocked) (software)
    interlocks: dict[str, bool] = field(default_factory=dict)

    # Hardware interlocks: device_id -> True. These are authoritative and
    # cannot be cleared by software. Any device present in this dict is
    # always considered blocked regardless of software interlock state.
    hardware_interlocks: dict[str, bool] = field(default_factory=dict)


class SafetyGate:
    """Fail-closed safety decision gate.

    Evaluates proposed commands against configurable safety rules.
    Default policy: DENY unless all PERMIT criteria are met.

    The gate cannot be bypassed by AI or any automated system.
    Only operator/manual override can temporarily HOLD (not PERMIT) commands,
    requiring mandatory re-authorization for any subsequent actions.

    Integration Note:
        This class evaluates decision safety in isolation. It does NOT
        intercept the MQTT publish path. Consumers MUST check the returned
        SafetyDecision.verdict BEFORE dispatching commands to the broker.
        The gateway's MqttSubscriber is read-only (no publish capability).
        See ADR-0013 §Integration Gap.
    """

    def __init__(self, config: SafetyRuleConfig | None = None) -> None:
        self._config = config or SafetyRuleConfig()
        self._audit_log: list[SafetyDecision] = []
        self._operator_override_active: bool = False
        self._override_authorization_required: bool = False

    @property
    def config(self) -> SafetyRuleConfig:
        return self._config

    @property
    def audit_log(self) -> list[SafetyDecision]:
        """Return immutable copy of audit log."""
        return list(self._audit_log)

    @property
    def operator_override_active(self) -> bool:
        """Check if operator override is currently active."""
        return self._operator_override_active

    def set_emergency_stop(self, active: bool) -> None:
        """Set emergency stop state (True = stop all commands)."""
        self._config.emergency_stop_active = active

    def set_interlock(self, device_id: str, blocked: bool) -> None:
        """Set interlock state for a device."""
        self._config.interlocks[device_id] = blocked

    def clear_interlock(self, device_id: str) -> None:
        """Clear interlock for a device."""
        self._config.interlocks.pop(device_id, None)

    def activate_operator_override(self) -> bool:
        """Activate operator override mode.

        Operator override can only HOLD (not PERMIT) commands.
        Returns True if override was activated.

        Note: Override requires re-authorization for any PERMIT decision.
        """
        if self._operator_override_active:
            # Already active, no change needed
            return True

        self._operator_override_active = True
        self._override_authorization_required = True
        return True

    def deactivate_operator_override(self) -> None:
        """Deactivate operator override mode.

        This clears the override and resets authorization requirement.
        """
        self._operator_override_active = False
        self._override_authorization_required = False

    def authorize_after_override(self) -> bool:
        """Grant authorization after operator override.

        Must be called after operator override to allow PERMIT decisions.
        Returns True if authorization was granted.

        This implements the mandatory re-authorization requirement:
        after any operator override, explicit re-authorization is needed
        before any command can proceed.
        """
        if not self._operator_override_active:
            # No override active, no authorization needed
            return True

        if not self._override_authorization_required:
            # Already authorized
            return True

        self._override_authorization_required = False
        return True

    def evaluate(
        self,
        command_id: str,
        device_id: str,
        command_name: str,
        confidence: float,
        data_timestamp_ms: int | None = None,
    ) -> SafetyDecision:
        """Evaluate a proposed command against safety rules.

        Args:
            command_id: Unique identifier for the command (envelope)
            device_id: Target device identifier
            command_name: Command name (e.g., CONVEYOR_START)
            confidence: AI confidence score (0.0 to 1.0)
            data_timestamp_ms: Timestamp of the AI inference in milliseconds
                               (Unix epoch). If None, data is considered fresh.

        Returns:
            SafetyDecision with verdict, reason_code, and metadata.
            Default: DENY unless all PERMIT criteria are met.

        Integration:
            Callers MUST check decision.verdict BEFORE dispatching commands.
            This method evaluates safety only; it does not block or dispatch.
        """
        import time

        # Default deny verdict
        verdict = Verdict.DENY
        reason_code = ReasonCode.NO_PERMIT_CRITERIA_MET

        # Check emergency stop first (highest priority)
        if self._config.emergency_stop_active:
            verdict = Verdict.DENY
            reason_code = ReasonCode.EMERGENCY_STOP
            decision = self._create_decision(
                command_id=command_id,
                device_id=device_id,
                command_name=command_name,
                verdict=verdict,
                reason_code=reason_code,
                confidence=confidence,
            )
            self._log_decision(decision)
            return decision

        # Check data staleness — fail-closed: DENY if telemetry is absent
        if data_timestamp_ms is None:
            verdict = Verdict.DENY
            reason_code = ReasonCode.NO_TELEMETRY
            decision = self._create_decision(
                command_id=command_id,
                device_id=device_id,
                command_name=command_name,
                verdict=verdict,
                reason_code=reason_code,
                confidence=confidence,
            )
            self._log_decision(decision)
            return decision

        current_time_ms = int(time.time() * 1000)
        age_seconds = (current_time_ms - data_timestamp_ms) / 1000.0
        if age_seconds > self._config.max_data_age_seconds:
            verdict = Verdict.DENY
            reason_code = ReasonCode.STALE_DATA
            decision = self._create_decision(
                command_id=command_id,
                device_id=device_id,
                command_name=command_name,
                verdict=verdict,
                reason_code=reason_code,
                confidence=confidence,
            )
            self._log_decision(decision)
            return decision

        # Check confidence threshold
        if confidence < self._config.min_confidence_threshold:
            verdict = Verdict.DENY
            reason_code = ReasonCode.LOW_CONFIDENCE
            decision = self._create_decision(
                command_id=command_id,
                device_id=device_id,
                command_name=command_name,
                verdict=verdict,
                reason_code=reason_code,
                confidence=confidence,
            )
            self._log_decision(decision)
            return decision

        # Check interlock (software + hardware — hardware is authoritative)
        # Hardware interlocks cannot be cleared by software.
        if self._config.hardware_interlocks.get(device_id, False):
            verdict = Verdict.DENY
            reason_code = ReasonCode.INTERLOCK_VIOLATION
            decision = self._create_decision(
                command_id=command_id,
                device_id=device_id,
                command_name=command_name,
                verdict=verdict,
                reason_code=reason_code,
                confidence=confidence,
            )
            self._log_decision(decision)
            return decision

        if self._config.interlocks.get(device_id, False):
            verdict = Verdict.DENY
            reason_code = ReasonCode.INTERLOCK_VIOLATION
            decision = self._create_decision(
                command_id=command_id,
                device_id=device_id,
                command_name=command_name,
                verdict=verdict,
                reason_code=reason_code,
                confidence=confidence,
            )
            self._log_decision(decision)
            return decision

        # Check operator override
        if self._operator_override_active:
            # Operator override can only HOLD, not PERMIT
            # This requires re-authorization before any PERMIT
            if self._override_authorization_required:
                # Still awaiting re-authorization after override
                verdict = Verdict.HOLD
                reason_code = ReasonCode.OPERATOR_OVERRIDE
                decision = self._create_decision(
                    command_id=command_id,
                    device_id=device_id,
                    command_name=command_name,
                    verdict=verdict,
                    reason_code=reason_code,
                    confidence=confidence,
                    issuer=IssuerType.HUMAN,
                )
                self._log_decision(decision)
                return decision
            else:
                # Re-authorized after override - allow PERMIT
                pass
        # If we reach here, all criteria are met - PERMIT
        verdict = Verdict.PERMIT
        reason_code = ReasonCode.ALL_CRITERIA_MET

        decision = self._create_decision(
            command_id=command_id,
            device_id=device_id,
            command_name=command_name,
            verdict=verdict,
            reason_code=reason_code,
            confidence=confidence,
        )
        self._log_decision(decision)
        return decision

    def _create_decision(
        self,
        command_id: str,
        device_id: str,
        command_name: str,
        verdict: Verdict,
        reason_code: ReasonCode,
        confidence: float,
        issuer: IssuerType = IssuerType.AUTOMATED,
    ) -> SafetyDecision:
        """Create a SafetyDecision with the given parameters."""
        return SafetyDecision(
            command_id=command_id,
            device_id=device_id,
            command_name=command_name,
            verdict=verdict,
            reason_code=reason_code,
            confidence=confidence,
            issuer=issuer,
        )

    def _log_decision(self, decision: SafetyDecision) -> None:
        """Log a safety decision to the audit log.

        Only non-sensitive metadata is stored:
        - decision_id, command_id (envelope), verdict, reason_code
        - confidence, timestamp, issuer
        Command arguments are NOT logged.
        """
        # Store only the envelope, not command content
        self._audit_log.append(decision)

        # Keep audit log bounded to prevent memory exhaustion
        max_log_size = 10000
        if len(self._audit_log) > max_log_size:
            # Keep the most recent entries
            self._audit_log = self._audit_log[-max_log_size:]

    def get_status(self) -> dict[str, Any]:
        """Get current safety gate status (non-sensitive).

        Note: hardware_interlocks are reported as read-only authoritative state.
        Software cannot clear hardware interlocks; they must be cleared physically.
        """
        return {
            "emergency_stop_active": self._config.emergency_stop_active,
            "operator_override_active": self._operator_override_active,
            "authorization_required": self._override_authorization_required,
            "interlocks": list(self._config.interlocks.keys()),
            "hardware_interlocks": list(self._config.hardware_interlocks.keys()),
            "config": {
                "max_data_age_seconds": self._config.max_data_age_seconds,
                "min_confidence_threshold": self._config.min_confidence_threshold,
            },
        }
