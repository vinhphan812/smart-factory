"""Yanshee response policy over the FIWARE context layer (Issue #204).

This module decides whether a **notification** to the UBTECH Yanshee robot
may be proposed, based on read-only FIWARE context.

Hard boundaries (ADR-0006, ADR-0014 invariant 6, Issue #204 SPEC-3/SPEC-6):

- Context is *evidence*, never authority. A context change alone can never
  dispatch a skill. A Gateway-approved incident outbox record is required.
- The policy can only propose **notification-class** skills. Physical
  motion, gripper and E-stop skills are permanently ``BLOCKED`` here; they
  are reachable only through the operator/command path.
- The policy never clears, bypasses or reasons about the E-stop interlock.
  The E-stop is owned by ``factory-control/``/the gateway safety gate and is
  independent of this code.
- Stale or invalid context is refused (``DENIED``) instead of being treated
  as "probably still fine".

Module boundary: this module must not import ``iot_gateway``. It consumes a
structural :class:`ContextReader` protocol so that the Gateway can supply the
read-only facade without creating a cross-module import.

Evidence level: L1 (unit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from ..skills import BOUNDED_SKILLS, SkillCategory

#: Maximum age of context that may still be used to propose a notification.
DEFAULT_MAX_CONTEXT_AGE_SECONDS = 120.0

#: Mapping of the Gateway Yanshee skill topics (``iot_gateway.alert_outbox``)
#: onto the bounded skill registry of this module. Only notification-class
#: skills are reachable; movement/grabbing/navigation have no entry and are
#: therefore permanently blocked from the context path.
YANSHEE_SKILL_MAP: dict[str, str] = {
    "yanshee/speech": "notify_operator",
    "yanshee/emotion": "broadcast_alert",
}

#: Gateway Yanshee topics that denote physical robot actions. They are
#: permanently blocked from the context path and are rejected as
#: ``PHYSICAL_SKILL_BLOCKED`` rather than as an unknown skill, so the reason
#: code states the real cause.
YANSHEE_BLOCKED_TOPICS: frozenset[str] = frozenset(
    {
        "yanshee/movement",
        "yanshee/grabbing",
        "yanshee/navigation",
    }
)


def normalize_skill(skill: str) -> str:
    """Map a Gateway Yanshee skill topic onto a bounded skill id.

    Unknown skills are returned unchanged so that they are rejected with an
    explicit ``UNKNOWN_SKILL`` denial instead of being silently mapped.
    """
    return YANSHEE_SKILL_MAP.get(skill, skill)


class SkillDecision(str, Enum):
    """Outcome of a response-policy evaluation."""

    APPROVED = "APPROVED"
    DENIED = "DENIED"
    BLOCKED = "BLOCKED"


class DecisionReason(str, Enum):
    """Machine-readable reason codes for a response decision."""

    OK = "OK"
    NO_GATEWAY_APPROVAL = "NO_GATEWAY_APPROVAL"
    CONTEXT_STALE = "CONTEXT_STALE"
    CONTEXT_INVALID = "CONTEXT_INVALID"
    UNSUPPORTED_SKILL = "UNSUPPORTED_SKILL"
    ROBOT_CAPABILITY_UNVERIFIED = "ROBOT_CAPABILITY_UNVERIFIED"
    ALERT_NOT_ACTIONABLE = "ALERT_NOT_ACTIONABLE"
    PHYSICAL_SKILL_BLOCKED = "PHYSICAL_SKILL_BLOCKED"
    EMERGENCY_STOP_ACTIVE = "EMERGENCY_STOP_ACTIVE"
    UNKNOWN_SKILL = "UNKNOWN_SKILL"


@runtime_checkable
class ContextReader(Protocol):
    """Read-only FIWARE context access used by the policy.

    Implemented structurally by ``iot_gateway.context_query.ContextQueryFacade``.
    """

    async def get_alert(self, incident_id: str) -> Any | None:
        """Return the projected alert entity for an incident id."""
        ...

    async def get_robot(self, robot_id: str) -> Any | None:
        """Return the robot capability entity for a robot id."""
        ...


@dataclass(frozen=True)
class GatewayApproval:
    """Proof that the Gateway approved this notification.

    Produced by the Gateway incident outbox (``iot_gateway.alert_outbox``).
    Its presence is what distinguishes "the robot noticed something" from
    "the factory system decided to tell the robot about it".

    Attributes:
        outbox_entry_id: Id of the approved outbox entry.
        incident_id: Incident the approval refers to.
        skill: Skill the Gateway approved.
        approved_at: ISO-8601 approval timestamp.
    """

    outbox_entry_id: str
    incident_id: str
    skill: str
    approved_at: str


@dataclass
class ResponseDecision:
    """Result of evaluating the response policy.

    Attributes:
        decision: ``APPROVED``, ``DENIED`` or ``BLOCKED``.
        reason: Machine-readable reason code.
        message: Human-readable explanation.
        skill: Skill the decision applies to.
        incident_id: Incident the decision applies to.
        context_observed_at: Observation timestamp of the context used.
    """

    decision: SkillDecision
    reason: DecisionReason
    message: str
    skill: str
    incident_id: str
    context_observed_at: str | None = None

    @property
    def approved(self) -> bool:
        """True only when a notification may be proposed."""
        return self.decision is SkillDecision.APPROVED

    def to_dict(self) -> dict[str, Any]:
        """Serialise the decision for logs and reports."""
        return {
            "decision": self.decision.value,
            "reason": self.reason.value,
            "message": self.message,
            "skill": self.skill,
            "incident_id": self.incident_id,
            "context_observed_at": self.context_observed_at,
        }


@dataclass
class YansheeResponsePolicy:
    """Policy deciding whether a Yanshee notification may be proposed.

    Args:
        context_reader: Read-only FIWARE context access.
        robot_id: Robot the policy acts for.
        max_context_age_seconds: Maximum age of context that is still usable.
        allowed_skill_categories: Skill categories this policy may propose.
            Defaults to notification-only; acknowledge/status-query skills are
            deliberately excluded because they change robot-side state.
    """

    context_reader: ContextReader
    robot_id: str = "yanshee-01"
    max_context_age_seconds: float = DEFAULT_MAX_CONTEXT_AGE_SECONDS
    allowed_skill_categories: tuple[SkillCategory, ...] = (
        SkillCategory.NOTIFICATION,
    )
    now_provider: Any = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        incident_id: str,
        skill: str,
        approval: GatewayApproval | None = None,
    ) -> ResponseDecision:
        """Evaluate whether a notification may be proposed.

        Args:
            incident_id: Gateway incident the notification refers to.
            skill: Skill the caller wants to propose.
            approval: Gateway outbox approval, if any.

        Returns:
            The decision. Only ``APPROVED`` permits a notification.
        """
        normalized_skill = normalize_skill(skill)
        skill_def = BOUNDED_SKILLS.get(normalized_skill)

        # 1. Unknown skill -> explicit denial, never a silent success.
        if skill_def is None:
            if skill in YANSHEE_BLOCKED_TOPICS:
                return ResponseDecision(
                    decision=SkillDecision.BLOCKED,
                    reason=DecisionReason.PHYSICAL_SKILL_BLOCKED,
                    message=(
                        f"Skill topic '{skill}' denotes a physical robot "
                        "action and is permanently blocked from the FIWARE "
                        "context path."
                    ),
                    skill=skill,
                    incident_id=incident_id,
                )
            return ResponseDecision(
                decision=SkillDecision.DENIED,
                reason=DecisionReason.UNKNOWN_SKILL,
                message=(
                    f"Skill '{skill}' is not in the bounded skill registry. "
                    "No skill proposed."
                ),
                skill=skill,
                incident_id=incident_id,
            )

        # 2. Physical-action skills are never proposable from context.
        if skill_def.category not in self.allowed_skill_categories:
            blocked = skill_def.category is SkillCategory.BLOCKED
            return ResponseDecision(
                decision=SkillDecision.BLOCKED,
                reason=(
                    DecisionReason.PHYSICAL_SKILL_BLOCKED
                    if blocked
                    else DecisionReason.UNSUPPORTED_SKILL
                ),
                message=(
                    f"Skill '{skill}' is category '{skill_def.category.value}' "
                    "and is not proposable from FIWARE context. Physical "
                    "actions require the authorised operator/command path."
                ),
                skill=skill,
                incident_id=incident_id,
            )

        # 3. A context change alone is never sufficient.
        if approval is None:
            return ResponseDecision(
                decision=SkillDecision.DENIED,
                reason=DecisionReason.NO_GATEWAY_APPROVAL,
                message=(
                    "No Gateway-approved incident outbox record. Context "
                    "changes alone never dispatch a robot skill."
                ),
                skill=skill,
                incident_id=incident_id,
            )

        if approval.incident_id != incident_id:
            return ResponseDecision(
                decision=SkillDecision.DENIED,
                reason=DecisionReason.NO_GATEWAY_APPROVAL,
                message=(
                    "Gateway approval refers to a different incident "
                    f"({approval.incident_id})."
                ),
                skill=skill,
                incident_id=incident_id,
            )

        if approval.skill != skill:
            return ResponseDecision(
                decision=SkillDecision.DENIED,
                reason=DecisionReason.UNSUPPORTED_SKILL,
                message=(
                    f"Gateway approved skill '{approval.skill}', not "
                    f"'{skill}'."
                ),
                skill=skill,
                incident_id=incident_id,
            )

        # 4. Read the context (read-only).
        alert = await self.context_reader.get_alert(incident_id)
        if alert is None:
            return ResponseDecision(
                decision=SkillDecision.DENIED,
                reason=DecisionReason.CONTEXT_INVALID,
                message=(
                    "No alert entity present in FIWARE context for incident "
                    f"{incident_id}."
                ),
                skill=skill,
                incident_id=incident_id,
            )

        observed_at = getattr(alert, "observed_at", None)
        if not self._is_fresh(observed_at):
            return ResponseDecision(
                decision=SkillDecision.DENIED,
                reason=DecisionReason.CONTEXT_STALE,
                message=(
                    "FIWARE context is missing a timestamp or is stale; "
                    "stale context cannot authorise a robot response."
                ),
                skill=skill,
                incident_id=incident_id,
                context_observed_at=observed_at,
            )

        status = self._property(alert, "status")
        if status not in ("active", "acknowledged"):
            return ResponseDecision(
                decision=SkillDecision.DENIED,
                reason=DecisionReason.ALERT_NOT_ACTIONABLE,
                message=(
                    f"Alert status '{status}' is not actionable for a robot "
                    "notification."
                ),
                skill=skill,
                incident_id=incident_id,
                context_observed_at=observed_at,
            )

        # 5. The robot must have a verified capability for this skill.
        robot = await self.context_reader.get_robot(self.robot_id)
        if robot is None:
            return ResponseDecision(
                decision=SkillDecision.DENIED,
                reason=DecisionReason.ROBOT_CAPABILITY_UNVERIFIED,
                message=(
                    "No robot capability entity in FIWARE context; cannot "
                    "confirm the skill is supported."
                ),
                skill=skill,
                incident_id=incident_id,
                context_observed_at=observed_at,
            )

        verification = self._property(robot, "verificationStatus")
        if verification != "VERIFIED":
            return ResponseDecision(
                decision=SkillDecision.DENIED,
                reason=DecisionReason.ROBOT_CAPABILITY_UNVERIFIED,
                message=(
                    "Robot capability is not verified "
                    f"(verificationStatus={verification!r}); the skill may "
                    "not be proposed. See Issue #160 for the SDK audit."
                ),
                skill=skill,
                incident_id=incident_id,
                context_observed_at=observed_at,
            )

        supported = self._property(robot, "supportedActions") or []
        # The robot reports bounded skill ids; the caller may have used the
        # Gateway topic form. Accept either representation.
        supported_names = {str(item) for item in supported}
        if normalized_skill not in supported_names and skill not in supported_names:
            return ResponseDecision(
                decision=SkillDecision.DENIED,
                reason=DecisionReason.UNSUPPORTED_SKILL,
                message=(
                    f"Robot does not report '{skill}' as a supported action "
                    f"(supportedActions={sorted(supported_names)!r})."
                ),
                skill=skill,
                incident_id=incident_id,
                context_observed_at=observed_at,
            )

        # 6. The E-stop interlock is independent and always wins.
        if self._emergency_stop_active(robot):
            return ResponseDecision(
                decision=SkillDecision.BLOCKED,
                reason=DecisionReason.EMERGENCY_STOP_ACTIVE,
                message=(
                    "Emergency stop is active. The interlock is independent "
                    "of FIWARE context and cannot be overridden by it."
                ),
                skill=skill,
                incident_id=incident_id,
                context_observed_at=observed_at,
            )

        return ResponseDecision(
            decision=SkillDecision.APPROVED,
            reason=DecisionReason.OK,
            message=(
                "Gateway-approved notification; context is fresh and the "
                "skill is verified as supported."
            ),
            skill=skill,
            incident_id=incident_id,
            context_observed_at=observed_at,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _now(self) -> datetime:
        """Return the current time (overridable for deterministic tests)."""
        if self.now_provider is not None:
            return self.now_provider
        return datetime.now(timezone.utc)

    def _is_fresh(self, observed_at: str | None) -> bool:
        """Return True when the context observation is recent enough."""
        if not observed_at:
            return False
        try:
            observed = datetime.fromisoformat(observed_at)
        except (TypeError, ValueError):
            return False
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age = (self._now() - observed).total_seconds()
        return 0 <= age <= self.max_context_age_seconds

    @staticmethod
    def _property(entity: Any, name: str) -> Any:
        """Read a Property value from a context entity."""
        getter = getattr(entity, "property", None)
        if callable(getter):
            return getter(name)
        if isinstance(entity, dict):
            attr = entity.get(name)
            if isinstance(attr, dict):
                return attr.get("value")
            return attr
        return None

    @staticmethod
    def _emergency_stop_active(robot: Any) -> bool:
        """Read the emergency-stop state carried by the robot entity.

        The policy never clears this flag; it only refuses to propose a
        notification while it is set.
        """
        getter = getattr(robot, "property", None)
        if callable(getter):
            value = getter("emergencyStop")
        elif isinstance(robot, dict):
            attr = robot.get("emergencyStop")
            value = attr.get("value") if isinstance(attr, dict) else attr
        else:
            value = None
        return bool(value)
