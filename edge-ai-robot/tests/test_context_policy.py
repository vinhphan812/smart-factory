"""Unit tests for the Yanshee response policy over FIWARE context (#204).

These are the safety-critical tests for Issue #204:

- SPEC-6 / TC-3: outdated context never dispatches a robot action.
- TC-2: the robot mock receives only an approved skill, never because an
  arbitrary entity changed.
- TC-4: an unsupported skill yields an explicit DENIED/BLOCKED, not success.
- Context can never authorise physical movement or override the E-stop.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from edge_ai_robot.context import (
    DecisionReason,
    GatewayApproval,
    SkillDecision,
    YansheeResponsePolicy,
    normalize_skill,
)

NOW = datetime(2026, 10, 23, 8, 0, 30, tzinfo=timezone.utc)


class FakeContextEntity:
    """Minimal stand-in for ``iot_gateway.context_query.ContextEntity``."""

    def __init__(self, attributes: dict[str, Any], observed_at: str | None = None):
        self.attributes = attributes
        self.observed_at = observed_at

    def property(self, name: str) -> Any:
        attr = self.attributes.get(name)
        if isinstance(attr, dict):
            return attr.get("value")
        return attr

    def relationship(self, name: str) -> str | None:
        attr = self.attributes.get(name)
        if isinstance(attr, dict):
            obj = attr.get("object")
            return str(obj) if obj is not None else None
        return None


class FakeContextReader:
    """Read-only context stub for the policy."""

    def __init__(
        self,
        alert: FakeContextEntity | None = None,
        robot: FakeContextEntity | None = None,
    ) -> None:
        self.alert = alert
        self.robot = robot
        self.alert_reads = 0
        self.robot_reads = 0

    async def get_alert(self, incident_id: str) -> Any | None:
        self.alert_reads += 1
        return self.alert

    async def get_robot(self, robot_id: str) -> Any | None:
        self.robot_reads += 1
        return self.robot


def _alert(
    status: str = "active",
    observed_at: str = "2026-10-23T08:00:00+00:00",
) -> FakeContextEntity:
    return FakeContextEntity(
        {
            "status": {"type": "Text", "value": status},
            "severity": {"type": "Text", "value": "critical"},
            "traceId": {"type": "Text", "value": "trace-abc"},
        },
        observed_at=observed_at,
    )


def _robot(
    verification: str = "VERIFIED",
    supported: list[str] | None = None,
    emergency_stop: bool = False,
) -> FakeContextEntity:
    return FakeContextEntity(
        {
            "verificationStatus": {"type": "Text", "value": verification},
            "supportedActions": {
                "type": "Array",
                "value": supported
                if supported is not None
                else ["notify_operator"],
            },
            "emergencyStop": {"type": "Boolean", "value": emergency_stop},
        },
        observed_at="2026-10-23T08:00:00+00:00",
    )


def _policy(reader: FakeContextReader) -> YansheeResponsePolicy:
    return YansheeResponsePolicy(context_reader=reader, now_provider=NOW)


def _approval(
    incident_id: str = "INC-001",
    skill: str = "notify_operator",
) -> GatewayApproval:
    return GatewayApproval(
        outbox_entry_id="entry-1",
        incident_id=incident_id,
        skill=skill,
        approved_at="2026-10-23T08:00:10+00:00",
    )


class TestApprovedPath:
    """The only path that yields APPROVED."""

    @pytest.mark.asyncio
    async def test_approved_notification_is_approved(self) -> None:
        reader = FakeContextReader(_alert(), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )

        assert decision.decision is SkillDecision.APPROVED
        assert decision.reason is DecisionReason.OK
        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_yanshee_topic_maps_to_bounded_skill(self) -> None:
        reader = FakeContextReader(_alert(), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001",
            "yanshee/speech",
            _approval(skill="yanshee/speech"),
        )

        assert decision.decision is SkillDecision.APPROVED

    @pytest.mark.asyncio
    async def test_acknowledged_alert_is_still_actionable(self) -> None:
        reader = FakeContextReader(_alert(status="acknowledged"), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )

        assert decision.decision is SkillDecision.APPROVED


class TestContextCannotDispatchOnItsOwn:
    """TC-2: a context change alone never launches a skill."""

    @pytest.mark.asyncio
    async def test_missing_approval_is_denied(self) -> None:
        reader = FakeContextReader(_alert(), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate("INC-001", "notify_operator")

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.NO_GATEWAY_APPROVAL

    @pytest.mark.asyncio
    async def test_approval_for_other_incident_is_denied(self) -> None:
        reader = FakeContextReader(_alert(), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval(incident_id="INC-999")
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.NO_GATEWAY_APPROVAL

    @pytest.mark.asyncio
    async def test_approval_for_other_skill_is_denied(self) -> None:
        reader = FakeContextReader(_alert(), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval(skill="broadcast_alert")
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.UNSUPPORTED_SKILL


class TestStaleContext:
    """TC-3 / SPEC-6: outdated context never dispatches a robot action."""

    @pytest.mark.asyncio
    async def test_stale_context_is_denied(self) -> None:
        stale = (NOW - timedelta(hours=2)).isoformat()
        reader = FakeContextReader(_alert(observed_at=stale), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.CONTEXT_STALE

    @pytest.mark.asyncio
    async def test_context_without_timestamp_is_denied(self) -> None:
        reader = FakeContextReader(_alert(observed_at=None), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.CONTEXT_STALE

    @pytest.mark.asyncio
    async def test_missing_alert_is_denied(self) -> None:
        reader = FakeContextReader(None, _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.CONTEXT_INVALID


class TestUnsupportedSkill:
    """TC-4: unsupported skills are explicitly denied or blocked."""

    @pytest.mark.asyncio
    async def test_unknown_skill_is_denied(self) -> None:
        reader = FakeContextReader(_alert(), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "self_destruct", _approval(skill="self_destruct")
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.UNKNOWN_SKILL

    @pytest.mark.asyncio
    async def test_skill_not_supported_by_robot_is_denied(self) -> None:
        reader = FakeContextReader(
            _alert(), _robot(supported=["broadcast_alert"])
        )
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.UNSUPPORTED_SKILL

    @pytest.mark.asyncio
    async def test_resolved_alert_is_not_actionable(self) -> None:
        reader = FakeContextReader(_alert(status="resolved"), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.ALERT_NOT_ACTIONABLE


class TestPhysicalSkillsAreBlocked:
    """SPEC-6: context cannot authorise physical movement."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "skill",
        ["move_robot", "activate_gripper", "emergency_stop"],
    )
    async def test_physical_skills_are_blocked(self, skill: str) -> None:
        reader = FakeContextReader(_alert(), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", skill, _approval(skill=skill)
        )

        assert decision.decision is SkillDecision.BLOCKED
        assert decision.reason is DecisionReason.PHYSICAL_SKILL_BLOCKED
        assert decision.approved is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "skill",
        ["yanshee/movement", "yanshee/grabbing", "yanshee/navigation"],
    )
    async def test_yanshee_physical_topics_are_blocked(self, skill: str) -> None:
        reader = FakeContextReader(_alert(), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", skill, _approval(skill=skill)
        )

        assert decision.decision is SkillDecision.BLOCKED
        assert decision.reason is DecisionReason.PHYSICAL_SKILL_BLOCKED
        assert decision.approved is False

    @pytest.mark.asyncio
    async def test_status_query_skill_is_not_proposable(self) -> None:
        reader = FakeContextReader(_alert(), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "query_robot_status", _approval(skill="query_robot_status")
        )

        assert decision.approved is False


class TestUnverifiedRobotCapability:
    """SPEC-1: unverified robot capability cannot enable a skill."""

    @pytest.mark.asyncio
    async def test_unverified_robot_is_denied(self) -> None:
        reader = FakeContextReader(
            _alert(), _robot(verification="UNVERIFIED")
        )
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.ROBOT_CAPABILITY_UNVERIFIED

    @pytest.mark.asyncio
    async def test_missing_robot_entity_is_denied(self) -> None:
        reader = FakeContextReader(_alert(), None)
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.ROBOT_CAPABILITY_UNVERIFIED


class TestEmergencyStopIndependence:
    """SPEC-6: the E-stop interlock is independent of FIWARE context."""

    @pytest.mark.asyncio
    async def test_active_estop_blocks_notification(self) -> None:
        reader = FakeContextReader(_alert(), _robot(emergency_stop=True))
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )

        assert decision.decision is SkillDecision.BLOCKED
        assert decision.reason is DecisionReason.EMERGENCY_STOP_ACTIVE

    @pytest.mark.asyncio
    async def test_estop_cannot_be_cleared_through_context(self) -> None:
        reader = FakeContextReader(_alert(), _robot(emergency_stop=True))
        policy = _policy(reader)

        # The policy evaluates; it must not mutate the robot entity.
        robot_before = dict(reader.robot.attributes)
        await policy.evaluate("INC-001", "notify_operator", _approval())

        assert reader.robot.attributes == robot_before
        assert (
            reader.robot.property("emergencyStop") is True
        )


class TestDecisionSerialisation:
    """Decision output shape for logs and reports."""

    @pytest.mark.asyncio
    async def test_to_dict_is_serialisable(self) -> None:
        reader = FakeContextReader(_alert(), _robot())
        policy = _policy(reader)

        decision = await policy.evaluate(
            "INC-001", "notify_operator", _approval()
        )
        payload = decision.to_dict()

        assert payload["decision"] == "APPROVED"
        assert payload["reason"] == "OK"
        assert payload["incident_id"] == "INC-001"
        assert payload["skill"] == "notify_operator"


class TestSkillNormalisation:
    """Gateway Yanshee topic -> bounded skill id mapping."""

    def test_speech_maps_to_notify_operator(self) -> None:
        assert normalize_skill("yanshee/speech") == "notify_operator"

    def test_emotion_maps_to_broadcast_alert(self) -> None:
        assert normalize_skill("yanshee/emotion") == "broadcast_alert"

    def test_unknown_topic_is_unchanged(self) -> None:
        assert normalize_skill("yanshee/movement") == "yanshee/movement"
