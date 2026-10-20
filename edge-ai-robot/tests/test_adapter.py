"""Tests for MiniAlpha adapter."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from edge_ai_robot.adapter import (
    ConnectionState,
    MockMiniAlphaAdapter,
    RobotStatus,
    SkillInvocation,
)
from edge_ai_robot.skills import SkillStatus


class TestMockMiniAlphaAdapter:
    """Test MockMiniAlphaAdapter functionality."""

    @pytest.fixture
    def adapter(self):
        """Create adapter instance."""
        return MockMiniAlphaAdapter(robot_id="test-robot-001")

    @pytest.mark.asyncio
    async def test_initial_state(self, adapter):
        """Test adapter starts in disconnected state."""
        assert adapter.connection_state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_connect(self, adapter):
        """Test connection establishes successfully."""
        await adapter.connect()
        assert adapter.connection_state == ConnectionState.CONNECTED

        status = await adapter.get_status()
        assert status.robot_id == "test-robot-001"
        assert status.connection_state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter):
        """Test disconnection."""
        await adapter.connect()
        await adapter.disconnect()
        assert adapter.connection_state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_health_check_when_connected(self, adapter):
        """Health check returns True when connected."""
        await adapter.connect()
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_when_disconnected(self, adapter):
        """Health check returns False when disconnected."""
        assert await adapter.health_check() is False

    @pytest.mark.asyncio
    async def test_invoke_skill_not_connected(self, adapter):
        """Skill invocation rejected when not connected."""
        result = await adapter.invoke_skill(
            skill_id="notify_operator",
            parameters={"message": "test"},
        )
        assert result.status == SkillStatus.REJECTED
        assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invoke_unknown_skill(self, adapter):
        """Unknown skill is rejected (fail-closed)."""
        await adapter.connect()
        result = await adapter.invoke_skill(
            skill_id="nonexistent_skill",
            parameters={},
        )
        assert result.status == SkillStatus.REJECTED
        assert "unknown" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invoke_blocked_skill_from_ai(self, adapter):
        """Physical action skill is rejected for AI (fail-closed)."""
        await adapter.connect()
        result = await adapter.invoke_skill(
            skill_id="move_robot",
            parameters={"x": 10.0, "y": 20.0},
            requested_by="ai",
        )
        assert result.status == SkillStatus.REJECTED
        assert "not allowed" in result.error.lower()
        assert "physical" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invoke_blocked_skill_from_operator(self, adapter):
        """Physical action skill allowed for operator."""
        await adapter.connect()
        result = await adapter.invoke_skill(
            skill_id="move_robot",
            parameters={"x": 10.0, "y": 20.0},
            requested_by="operator",
        )
        # Operator should be able to invoke (category is BLOCKED but we check allowed_from_ai)
        # Actually, operator can invoke blocked skills too - the check is only for "ai"
        assert result.status in [SkillStatus.RUNNING, SkillStatus.COMPLETED]

    @pytest.mark.asyncio
    async def test_invoke_notification_skill(self, adapter):
        """Notification skill executes successfully."""
        await adapter.connect()
        result = await adapter.invoke_skill(
            skill_id="notify_operator",
            parameters={"message": "Test notification", "priority": "warning"},
            requested_by="ai",
        )
        assert result.status == SkillStatus.COMPLETED
        assert result.result is not None
        assert result.result["notification_sent"] is True

    @pytest.mark.asyncio
    async def test_invoke_status_query_skill(self, adapter):
        """Status query skill executes successfully."""
        await adapter.connect()
        result = await adapter.invoke_skill(
            skill_id="query_robot_status",
            parameters={"include_battery": True, "include_position": True},
            requested_by="ai",
        )
        assert result.status == SkillStatus.COMPLETED
        assert result.result is not None
        assert "battery_level" in result.result

    @pytest.mark.asyncio
    async def test_invoke_skill_missing_required_param(self, adapter):
        """Skill rejected when required parameter missing."""
        await adapter.connect()
        result = await adapter.invoke_skill(
            skill_id="notify_operator",
            parameters={},  # Missing "message"
        )
        assert result.status == SkillStatus.REJECTED
        assert "missing" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invoke_skill_invalid_param_value(self, adapter):
        """Skill rejected when parameter value invalid."""
        await adapter.connect()
        result = await adapter.invoke_skill(
            skill_id="notify_operator",
            parameters={"message": "test", "priority": "invalid_priority"},
        )
        assert result.status == SkillStatus.REJECTED
        assert "invalid" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invoke_estop_from_ai_rejected(self, adapter):
        """E-stop rejected for AI (operator only)."""
        await adapter.connect()
        result = await adapter.invoke_skill(
            skill_id="emergency_stop",
            parameters={"reason": "test"},
            requested_by="ai",
        )
        assert result.status == SkillStatus.REJECTED

    @pytest.mark.asyncio
    async def test_invocation_history_tracked(self, adapter):
        """Skill invocations are tracked in history."""
        await adapter.connect()
        await adapter.invoke_skill(
            skill_id="query_robot_status",
            parameters={},
        )
        history = adapter.get_invocation_history()
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_get_status_returns_battery(self, adapter):
        """Status includes battery level."""
        await adapter.connect()
        status = await adapter.get_status()
        assert hasattr(status, "battery_level")
        assert status.battery_level >= 0

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, adapter):
        """Reset clears adapter state."""
        await adapter.connect()
        await adapter.invoke_skill("query_robot_status", {})
        await adapter.reset()

        assert adapter.connection_state == ConnectionState.DISCONNECTED
        assert len(adapter.get_invocation_history()) == 0
