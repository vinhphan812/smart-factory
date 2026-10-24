"""Edge AI Robot package."""

__version__ = "0.1.0"

from edge_ai_robot.adapter import (
    ConnectionState,
    MiniAlphaAdapterBase,
    MockMiniAlphaAdapter,
    RobotStatus,
    SkillInvocation,
)
from edge_ai_robot.detection import (
    Alarm,
    AlarmCategory,
    AlarmSeverity,
    AnomalyDetector,
)
from edge_ai_robot.skills import (
    BOUNDED_SKILLS,
    SkillCategory,
    SkillDefinition,
    SkillParameter,
    SkillStatus,
    get_allowed_skills_for_ai,
    get_skill_definition,
    get_skills_by_category,
)

__all__ = [
    # Adapter
    "ConnectionState",
    "MiniAlphaAdapterBase",
    "MockMiniAlphaAdapter",
    "RobotStatus",
    "SkillInvocation",
    # Detection
    "Alarm",
    "AlarmCategory",
    "AlarmSeverity",
    "AnomalyDetector",
    # Skills
    "BOUNDED_SKILLS",
    "SkillCategory",
    "SkillDefinition",
    "SkillParameter",
    "SkillStatus",
    "get_allowed_skills_for_ai",
    "get_skill_definition",
    "get_skills_by_category",
]
