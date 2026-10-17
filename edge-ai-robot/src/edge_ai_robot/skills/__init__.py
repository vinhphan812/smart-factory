"""Bounded robot skill definitions.

Safety constraints:
- All AI-initiated actions are bounded and fail-closed
- E-stop and motion limits are enforced by factory-control/, not by AI
- AI does not initiate unapproved physical rescue or override operator commands
- Anomaly detection output is advisory; human operators approve or reject responses
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SkillCategory(str, Enum):
    """Categories of bounded robot skills."""
    NOTIFICATION = "notification"  # Notify operator, no physical action
    STATUS_QUERY = "status_query"  # Query robot/device status
    ACKNOWLEDGE = "acknowledge"   # Acknowledge alarm, no motion
    BLOCKED = "blocked"            # Skill not permitted for AI invocation


class SkillStatus(str, Enum):
    """Execution status of a skill."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"  # Skill not in allowed list


@dataclass
class SkillParameter:
    """Definition of a skill parameter."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillDefinition:
    """Definition of a bounded robot skill."""
    skill_id: str
    name: str
    description: str
    category: SkillCategory
    parameters: list[SkillParameter] = field(default_factory=list)
    max_duration_seconds: int = 30
    requires_human_approval: bool = True
    allowed_from_ai: bool = True  # False = operator only


# =============================================================================
# BOUNDED SKILL REGISTRY
# =============================================================================

# All skills must be explicitly defined here. Skills not in this registry
# are automatically REJECTED when invoked by AI (fail-closed).

BOUNDED_SKILLS: dict[str, SkillDefinition] = {
    # -------------------------------------------------------------------------
    # NOTIFICATION SKILLS — No physical action, pure notification
    # -------------------------------------------------------------------------
    "notify_operator": SkillDefinition(
        skill_id="notify_operator",
        name="Notify Operator",
        description="Send notification to operator about factory status or alerts",
        category=SkillCategory.NOTIFICATION,
        parameters=[
            SkillParameter(
                name="message",
                type="string",
                description="Notification message to display",
                required=True,
            ),
            SkillParameter(
                name="priority",
                type="string",
                description="Priority level: info, warning, critical",
                required=False,
                default="info",
                constraints={"allowed_values": ["info", "warning", "critical"]},
            ),
        ],
        max_duration_seconds=5,
        requires_human_approval=False,  # Can auto-notify
        allowed_from_ai=True,
    ),
    "broadcast_alert": SkillDefinition(
        skill_id="broadcast_alert",
        name="Broadcast Alert",
        description="Broadcast factory-wide alert (non-critical)",
        category=SkillCategory.NOTIFICATION,
        parameters=[
            SkillParameter(
                name="alert_type",
                type="string",
                description="Type of alert",
                required=True,
                constraints={"allowed_values": ["maintenance", "shift_change", "general"]},
            ),
            SkillParameter(
                name="message",
                type="string",
                description="Alert message",
                required=True,
            ),
        ],
        max_duration_seconds=10,
        requires_human_approval=True,
        allowed_from_ai=True,
    ),
    # -------------------------------------------------------------------------
    # STATUS QUERY SKILLS — Read-only, no action
    # -------------------------------------------------------------------------
    "query_robot_status": SkillDefinition(
        skill_id="query_robot_status",
        name="Query Robot Status",
        description="Get current robot operational status",
        category=SkillCategory.STATUS_QUERY,
        parameters=[
            SkillParameter(
                name="include_battery",
                type="boolean",
                description="Include battery level in response",
                required=False,
                default=True,
            ),
            SkillParameter(
                name="include_position",
                type="boolean",
                description="Include current position in response",
                required=False,
                default=False,
            ),
        ],
        max_duration_seconds=3,
        requires_human_approval=False,
        allowed_from_ai=True,
    ),
    "query_device_status": SkillDefinition(
        skill_id="query_device_status",
        name="Query Device Status",
        description="Query status of factory devices via gateway",
        category=SkillCategory.STATUS_QUERY,
        parameters=[
            SkillParameter(
                name="device_id",
                type="string",
                description="Device ID to query",
                required=True,
            ),
        ],
        max_duration_seconds=5,
        requires_human_approval=False,
        allowed_from_ai=True,
    ),
    "query_event_history": SkillDefinition(
        skill_id="query_event_history",
        name="Query Event History",
        description="Query recent events from event store",
        category=SkillCategory.STATUS_QUERY,
        parameters=[
            SkillParameter(
                name="device_id",
                type="string",
                description="Filter by device ID (optional)",
                required=False,
            ),
            SkillParameter(
                name="limit",
                type="integer",
                description="Maximum number of events to return",
                required=False,
                default=10,
                constraints={"min": 1, "max": 100},
            ),
        ],
        max_duration_seconds=10,
        requires_human_approval=False,
        allowed_from_ai=True,
    ),
    # -------------------------------------------------------------------------
    # ACKNOWLEDGE SKILLS — No motion, clear alarm state
    # -------------------------------------------------------------------------
    "acknowledge_alarm": SkillDefinition(
        skill_id="acknowledge_alarm",
        name="Acknowledge Alarm",
        description="Acknowledge a factory alarm (clears pending alert, no motion)",
        category=SkillCategory.ACKNOWLEDGE,
        parameters=[
            SkillParameter(
                name="alarm_id",
                type="string",
                description="ID of alarm to acknowledge",
                required=True,
            ),
            SkillParameter(
                name="reason",
                type="string",
                description="Reason for acknowledgment",
                required=False,
            ),
        ],
        max_duration_seconds=5,
        requires_human_approval=True,
        allowed_from_ai=True,
    ),
    "clear_alarm": SkillDefinition(
        skill_id="clear_alarm",
        name="Clear Alarm",
        description="Clear a resolved alarm from active state",
        category=SkillCategory.ACKNOWLEDGE,
        parameters=[
            SkillParameter(
                name="alarm_id",
                type="string",
                description="ID of alarm to clear",
                required=True,
            ),
        ],
        max_duration_seconds=5,
        requires_human_approval=True,
        allowed_from_ai=True,
    ),
    # -------------------------------------------------------------------------
    # PHYSICAL ACTION SKILLS — BLOCKED for AI (operator only)
    # -------------------------------------------------------------------------
    "move_robot": SkillDefinition(
        skill_id="move_robot",
        name="Move Robot",
        description="Move robot to specified position",
        category=SkillCategory.BLOCKED,
        parameters=[
            SkillParameter(
                name="x",
                type="float",
                description="Target X coordinate",
                required=True,
            ),
            SkillParameter(
                name="y",
                type="float",
                description="Target Y coordinate",
                required=True,
            ),
        ],
        max_duration_seconds=60,
        requires_human_approval=True,
        allowed_from_ai=False,  # BLOCKED: physical motion
    ),
    "activate_gripper": SkillDefinition(
        skill_id="activate_gripper",
        name="Activate Gripper",
        description="Open or close robot gripper",
        category=SkillCategory.BLOCKED,
        parameters=[
            SkillParameter(
                name="action",
                type="string",
                description="Gripper action",
                required=True,
                constraints={"allowed_values": ["open", "close"]},
            ),
        ],
        max_duration_seconds=10,
        requires_human_approval=True,
        allowed_from_ai=False,  # BLOCKED: physical action
    ),
    "emergency_stop": SkillDefinition(
        skill_id="emergency_stop",
        name="Emergency Stop",
        description="Trigger robot E-stop (safety-critical)",
        category=SkillCategory.BLOCKED,
        parameters=[
            SkillParameter(
                name="reason",
                type="string",
                description="Reason for E-stop",
                required=True,
            ),
        ],
        max_duration_seconds=1,
        requires_human_approval=False,  # E-stop always allowed
        allowed_from_ai=False,  # BLOCKED: safety-critical, operator only
    ),
}


def get_skill_definition(skill_id: str) -> SkillDefinition | None:
    """Get skill definition by ID."""
    return BOUNDED_SKILLS.get(skill_id)


def get_allowed_skills_for_ai() -> list[SkillDefinition]:
    """Get list of skills allowed for AI invocation."""
    return [s for s in BOUNDED_SKILLS.values() if s.allowed_from_ai]


def get_skills_by_category(category: SkillCategory) -> list[SkillDefinition]:
    """Get all skills in a specific category."""
    return [s for s in BOUNDED_SKILLS.values() if s.category == category]
