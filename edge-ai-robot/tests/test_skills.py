"""Tests for bounded skill registry."""

import pytest

from edge_ai_robot.skills import (
    BOUNDED_SKILLS,
    SkillCategory,
    SkillStatus,
    get_allowed_skills_for_ai,
    get_skill_definition,
    get_skills_by_category,
)


class TestSkillRegistry:
    """Test skill registry functionality."""

    def test_bounded_skills_not_empty(self):
        """Registry should contain skills."""
        assert len(BOUNDED_SKILLS) > 0

    def test_all_skills_have_valid_category(self):
        """All skills should have a valid category."""
        for skill_id, skill in BOUNDED_SKILLS.items():
            assert skill.skill_id == skill_id
            assert skill.category in list(SkillCategory)

    def test_all_skills_have_parameters_list(self):
        """All skills should have a parameters list."""
        for skill in BOUNDED_SKILLS.values():
            assert skill.parameters is not None
            assert isinstance(skill.parameters, list)

    def test_get_skill_definition_found(self):
        """get_skill_definition returns skill when found."""
        skill = get_skill_definition("notify_operator")
        assert skill is not None
        assert skill.skill_id == "notify_operator"

    def test_get_skill_definition_not_found(self):
        """get_skill_definition returns None when not found."""
        skill = get_skill_definition("nonexistent_skill")
        assert skill is None

    def test_get_allowed_skills_for_ai(self):
        """Get skills allowed for AI invocation."""
        ai_skills = get_allowed_skills_for_ai()
        assert len(ai_skills) > 0

        # All returned skills should have allowed_from_ai = True
        for skill in ai_skills:
            assert skill.allowed_from_ai is True

        # Physical action skills should NOT be in the list
        physical_skills = get_skills_by_category(SkillCategory.BLOCKED)
        for skill in physical_skills:
            assert skill.skill_id not in [s.skill_id for s in ai_skills]

    def test_get_skills_by_category(self):
        """Get skills filtered by category."""
        notification_skills = get_skills_by_category(SkillCategory.NOTIFICATION)
        assert len(notification_skills) > 0

        for skill in notification_skills:
            assert skill.category == SkillCategory.NOTIFICATION

    def test_blocked_skills_not_allowed_from_ai(self):
        """Blocked category skills should not be allowed from AI."""
        blocked_skills = get_skills_by_category(SkillCategory.BLOCKED)
        assert len(blocked_skills) > 0

        for skill in blocked_skills:
            assert skill.allowed_from_ai is False

    def test_emergency_stop_not_allowed_from_ai(self):
        """Emergency stop should never be allowed from AI."""
        estop_skill = get_skill_definition("emergency_stop")
        assert estop_skill is not None
        assert estop_skill.allowed_from_ai is False
        assert estop_skill.category == SkillCategory.BLOCKED


class TestSkillDefinitions:
    """Test individual skill definitions."""

    def test_notify_operator_skill(self):
        """Test notify_operator skill definition."""
        skill = get_skill_definition("notify_operator")
        assert skill is not None
        assert skill.category == SkillCategory.NOTIFICATION
        assert skill.allowed_from_ai is True
        assert skill.requires_human_approval is False

    def test_query_robot_status_skill(self):
        """Test query_robot_status skill definition."""
        skill = get_skill_definition("query_robot_status")
        assert skill is not None
        assert skill.category == SkillCategory.STATUS_QUERY
        assert skill.allowed_from_ai is True

    def test_acknowledge_alarm_skill(self):
        """Test acknowledge_alarm skill definition."""
        skill = get_skill_definition("acknowledge_alarm")
        assert skill is not None
        assert skill.category == SkillCategory.ACKNOWLEDGE
        assert skill.allowed_from_ai is True
        assert skill.requires_human_approval is True

    def test_move_robot_blocked_for_ai(self):
        """Test move_robot is blocked for AI."""
        skill = get_skill_definition("move_robot")
        assert skill is not None
        assert skill.category == SkillCategory.BLOCKED
        assert skill.allowed_from_ai is False

    def test_skill_parameter_constraints(self):
        """Test skill parameter validation."""
        skill = get_skill_definition("notify_operator")
        assert skill is not None

        # Find priority parameter
        priority_param = next(p for p in skill.parameters if p.name == "priority")
        assert "allowed_values" in priority_param.constraints
        assert priority_param.constraints["allowed_values"] == ["info", "warning", "critical"]
