"""MiniAlpha robot adapter with typed mock implementation.

This adapter provides:
- Mock MiniAlpha connection for L2 simulation (no physical hardware required)
- Typed command interface with validation
- Unsupported skill rejection (fail-closed)
- Bounded command execution

For physical HIL testing, replace MockMiniAlphaAdapter with real MiniAlphaClient.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import asyncio
import uuid

import structlog

from edge_ai_robot.skills import (
    SkillDefinition,
    SkillStatus,
    get_skill_definition,
    BOUNDED_SKILLS,
)

logger = structlog.get_logger(__name__)


class ConnectionState(str, Enum):
    """MiniAlpha connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class RobotStatus:
    """Current robot status."""
    robot_id: str
    connection_state: ConnectionState
    battery_level: float = 100.0
    position: dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    is_emergency_stopped: bool = False
    last_heartbeat: datetime = field(default_factory=datetime.now)
    available_skills: list[str] = field(default_factory=list)


@dataclass
class SkillInvocation:
    """Record of a skill invocation."""
    invocation_id: str
    skill_id: str
    parameters: dict[str, Any]
    requested_by: str  # "ai" or "operator"
    status: SkillStatus
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class MiniAlphaAdapterBase(ABC):
    """Abstract base class for MiniAlpha adapters."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to MiniAlpha."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to MiniAlpha."""
        pass

    @abstractmethod
    async def get_status(self) -> RobotStatus:
        """Get current robot status."""
        pass

    @abstractmethod
    async def invoke_skill(
        self,
        skill_id: str,
        parameters: dict[str, Any],
        requested_by: str = "ai",
    ) -> SkillInvocation:
        """Invoke a bounded skill on the robot."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Perform health check."""
        pass


class MockMiniAlphaAdapter(MiniAlphaAdapterBase):
    """Mock MiniAlpha adapter for L2 simulation.

    This adapter:
    - Simulates connection without physical hardware
    - Validates all skills against bounded skill registry
    - Rejects skills not in the allowed list (fail-closed)
    - Returns deterministic mock responses
    """

    def __init__(self, robot_id: str = "minialpha-001"):
        self.robot_id = robot_id
        self._connection_state = ConnectionState.DISCONNECTED
        self._status = RobotStatus(
            robot_id=robot_id,
            connection_state=ConnectionState.DISCONNECTED,
            battery_level=85.5,
            position={"x": 10.0, "y": 20.0},
            is_emergency_stopped=False,
            available_skills=list(BOUNDED_SKILLS.keys()),
        )
        self._invocation_history: list[SkillInvocation] = []
        self._lock = asyncio.Lock()

    @property
    def connection_state(self) -> ConnectionState:
        return self._connection_state

    async def connect(self) -> None:
        """Simulate connection to MiniAlpha."""
        async with self._lock:
            if self._connection_state == ConnectionState.CONNECTED:
                logger.info("already_connected", robot_id=self.robot_id)
                return

            self._connection_state = ConnectionState.CONNECTING
            logger.info("connecting", robot_id=self.robot_id)

            # Simulate connection delay
            await asyncio.sleep(0.1)

            self._connection_state = ConnectionState.CONNECTED
            self._status.connection_state = ConnectionState.CONNECTED
            self._status.last_heartbeat = datetime.now()

            logger.info("connected", robot_id=self.robot_id)

    async def disconnect(self) -> None:
        """Simulate disconnection from MiniAlpha."""
        async with self._lock:
            self._connection_state = ConnectionState.DISCONNECTED
            self._status.connection_state = ConnectionState.DISCONNECTED
            logger.info("disconnected", robot_id=self.robot_id)

    async def get_status(self) -> RobotStatus:
        """Get current robot status (mock)."""
        async with self._lock:
            # Simulate slight battery drain
            self._status.battery_level = max(0.0, self._status.battery_level - 0.01)
            self._status.last_heartbeat = datetime.now()
            return self._status

    async def invoke_skill(
        self,
        skill_id: str,
        parameters: dict[str, Any],
        requested_by: str = "ai",
    ) -> SkillInvocation:
        """Invoke a bounded skill with validation.

        This implements fail-closed behavior:
        - Skills not in registry are REJECTED
        - Physical action skills (BLOCKED category) are REJECTED for AI
        - Valid skills are executed with mock responses
        """
        invocation = SkillInvocation(
            invocation_id=str(uuid.uuid4()),
            skill_id=skill_id,
            parameters=parameters,
            requested_by=requested_by,
            status=SkillStatus.PENDING,
        )

        async with self._lock:
            self._invocation_history.append(invocation)

        # Check connection
        if self._connection_state != ConnectionState.CONNECTED:
            invocation.status = SkillStatus.REJECTED
            invocation.error = "Robot not connected"
            logger.warning("skill_rejected_not_connected", invocation_id=invocation.invocation_id)
            return invocation

        # Check E-stop
        if self._status.is_emergency_stopped:
            invocation.status = SkillStatus.REJECTED
            invocation.error = "Robot is in emergency stop state"
            logger.warning("skill_rejected_estop", invocation_id=invocation.invocation_id)
            return invocation

        # Lookup skill definition
        skill_def = get_skill_definition(skill_id)
        if skill_def is None:
            invocation.status = SkillStatus.REJECTED
            invocation.error = f"Unknown skill: {skill_id}. No skill executed."
            logger.warning(
                "skill_rejected_unknown",
                invocation_id=invocation.invocation_id,
                skill_id=skill_id,
            )
            return invocation

        # Fail-closed: AI cannot invoke BLOCKED category skills
        if requested_by == "ai" and not skill_def.allowed_from_ai:
            invocation.status = SkillStatus.REJECTED
            invocation.error = (
                f"Skill '{skill_id}' is not allowed for AI invocation. "
                f"Category: {skill_def.category.value}. "
                "Physical actions require human operator approval."
            )
            logger.warning(
                "skill_rejected_blocked_for_ai",
                invocation_id=invocation.invocation_id,
                skill_id=skill_id,
                category=skill_def.category.value,
            )
            return invocation

        # Validate required parameters
        for param in skill_def.parameters:
            if param.required and param.name not in parameters:
                invocation.status = SkillStatus.REJECTED
                invocation.error = f"Missing required parameter: {param.name}"
                logger.warning(
                    "skill_rejected_missing_param",
                    invocation_id=invocation.invocation_id,
                    skill_id=skill_id,
                    param=param.name,
                )
                return invocation

        # Validate parameter constraints
        for param_name, value in parameters.items():
            param_def = next(
                (p for p in skill_def.parameters if p.name == param_name), None
            )
            if param_def and "allowed_values" in param_def.constraints:
                allowed = param_def.constraints["allowed_values"]
                if value not in allowed:
                    invocation.status = SkillStatus.REJECTED
                    invocation.error = (
                        f"Invalid value for '{param_name}': {value}. "
                        f"Allowed values: {allowed}"
                    )
                    return invocation

        # Execute skill (mock)
        invocation.status = SkillStatus.RUNNING
        logger.info(
            "skill_executing",
            invocation_id=invocation.invocation_id,
            skill_id=skill_id,
            requested_by=requested_by,
        )

        # Simulate execution time
        await asyncio.sleep(min(skill_def.max_duration_seconds, 0.1))

        # Generate mock result based on skill category
        result = await self._generate_mock_result(skill_def, parameters)

        invocation.status = SkillStatus.COMPLETED
        invocation.result = result
        invocation.completed_at = datetime.now()

        logger.info(
            "skill_completed",
            invocation_id=invocation.invocation_id,
            skill_id=skill_id,
        )

        return invocation

    async def _generate_mock_result(
        self,
        skill_def: SkillDefinition,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate deterministic mock result based on skill type."""
        base_result = {
            "skill_id": skill_def.skill_id,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
        }

        if skill_def.category.value == "notification":
            return {
                **base_result,
                "notification_sent": True,
                "message": parameters.get("message", ""),
            }

        if skill_def.category.value == "status_query":
            if skill_def.skill_id == "query_robot_status":
                status = await self.get_status()
                return {
                    **base_result,
                    "robot_id": status.robot_id,
                    "battery_level": status.battery_level,
                    "position": status.position if parameters.get("include_position") else None,
                    "connection_state": status.connection_state.value,
                }
            elif skill_def.skill_id == "query_device_status":
                return {
                    **base_result,
                    "device_id": parameters.get("device_id"),
                    "status": "online",
                    "last_seen": datetime.now().isoformat(),
                }
            elif skill_def.skill_id == "query_event_history":
                return {
                    **base_result,
                    "events": [],
                    "count": 0,
                }

        if skill_def.category.value == "acknowledge":
            return {
                **base_result,
                "alarm_id": parameters.get("alarm_id"),
                "acknowledged": True,
            }

        # Default fallback
        return base_result

    async def health_check(self) -> bool:
        """Perform health check (mock)."""
        return self._connection_state == ConnectionState.CONNECTED

    def get_invocation_history(self) -> list[SkillInvocation]:
        """Get skill invocation history."""
        return list(self._invocation_history)

    async def reset(self) -> None:
        """Reset adapter state (for testing)."""
        async with self._lock:
            self._connection_state = ConnectionState.DISCONNECTED
            self._status.connection_state = ConnectionState.DISCONNECTED
            self._status.is_emergency_stopped = False
            self._invocation_history.clear()
