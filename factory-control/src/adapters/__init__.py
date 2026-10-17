"""Base device adapter for factory modules.

Provides a common interface for all module adapters (conveyor, robot, crane, etc.).
Each adapter implements the device-specific behavior while conforming to the
canonical command and event contracts.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
import uuid

from state_machine import (
    ProductionState,
    CommandName,
    CommandStatus,
    ProductionStateMachine,
    ModuleState,
)


@dataclass
class Command:
    """Canonical command envelope for factory modules.
    
    Matches the MQTT command contract (command.schema.json).
    """

    command_id: Optional[int] = None
    request_id: Optional[str] = None
    device_id: str = ""
    command_name: CommandName = CommandName.PING
    arguments: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ttl_seconds: int = 10

    @property
    def correlation_id(self) -> str:
        """Get correlation ID (command_id or request_id)."""
        if self.command_id is not None:
            return str(self.command_id)
        return self.request_id or str(uuid.uuid4())


@dataclass
class CommandResult:
    """Result of command execution.
    
    Matches the MQTT ACK payload contract.
    """

    request_id: str
    sequence: int = 0
    command: str = ""
    status: CommandStatus = CommandStatus.PENDING
    status_code: int = 0  # 0 = OK, non-zero = error
    attempts: int = 1
    error_message: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DeviceAdapter(ABC):
    """Abstract base class for factory module adapters.
    
    Each device type (conveyor, robot, crane, etc.) implements this interface.
    The adapter handles device-specific command translation and event generation.
    """

    def __init__(self, device_id: str, device_type: str):
        self.device_id = device_id
        self.device_type = device_type
        self._state_machine = ProductionStateMachine(device_id, device_type)
        self._pending_commands: dict[str, Command] = {}

    @property
    def state(self) -> ProductionState:
        """Current device state."""
        return self._state_machine.state

    @property
    def module_id(self) -> str:
        """Device identifier."""
        return self.device_id

    def get_module_state(self) -> ModuleState:
        """Get the module state."""
        return self._state_machine.module

    def get_state_dict(self) -> dict:
        """Get current state as dictionary."""
        return self._state_machine.get_state()

    def can_execute(self, command: Command) -> tuple[bool, Optional[str]]:
        """Check if command can be executed.
        
        Returns:
            (can_execute, error_message)
        """
        # Check TTL
        if command.ttl_seconds < 1 or command.ttl_seconds > 300:
            return False, "ttl_seconds must be between 1 and 300"

        # Check correlation ID
        if command.command_id is None and command.request_id is None:
            return False, "command requires command_id or request_id"

        # Check state machine
        can_exec = self._state_machine.can_transition(command.command_name)
        if can_exec:
            return True, None
        else:
            return False, f"Command {command.command_name.value} not valid in state {self._state_machine.state.value}"

    def execute(self, command: Command) -> CommandResult:
        """Execute a command on the device.
        
        Returns a CommandResult with the execution status.
        """
        # Validate command
        can_exec, error_msg = self.can_execute(command)
        if not can_exec:
            return CommandResult(
                request_id=command.correlation_id,
                sequence=self._state_machine.module.sequence,
                command=command.command_name.value,
                status=CommandStatus.FAILED,
                status_code=2,  # invalid_argument
                attempts=1,
                error_message=error_msg,
            )

        # Track pending command
        self._pending_commands[command.correlation_id] = command

        # Execute on state machine
        success, error_msg = self._state_machine.execute_command(
            command.command_name, command.arguments
        )

        if not success:
            return CommandResult(
                request_id=command.correlation_id,
                sequence=self._state_machine.module.sequence,
                command=command.command_name.value,
                status=CommandStatus.FAILED,
                status_code=1,  # unknown_command or similar
                attempts=1,
                error_message=error_msg,
            )

        # Return success result
        return CommandResult(
            request_id=command.correlation_id,
            sequence=self._state_machine.module.sequence,
            command=command.command_name.value,
            status=CommandStatus.ACKNOWLEDGED,
            status_code=0,
            attempts=1,
        )

    def tick(self) -> None:
        """Advance the device simulation by one tick."""
        self._state_machine.tick()

    def generate_event(self, event_type: str, payload: dict) -> dict:
        """Generate a device event.
        
        Returns an event dictionary matching the device-event.schema.json.
        """
        return {
            "event_id": str(uuid.uuid4()),
            "device_id": self.device_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "id": self._state_machine.module.sequence,
                "status": self.state.value,
            },
            "sequence": self._state_machine.module.sequence,
        }

    def get_telemetry(self) -> dict:
        """Get current telemetry from the device.
        
        Returns a telemetry dictionary matching the telemetry.schema.json.
        """
        return {
            "device_id": self.device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": self.state.value,
            "speed": self._state_machine.module.speed,
            "sensors": {
                "temperature_centi_c": 2500,  # 25°C
                "humidity_centi_percent": 5000,  # 50%
                "digital_inputs": 0,
            },
            "uptime": self._state_machine.module.simulated_ticks * 100,  # ms
        }

    def reset(self) -> None:
        """Reset the device to initial state."""
        self._state_machine.reset()
        self._pending_commands.clear()


class ConveyorAdapter(DeviceAdapter):
    """Device adapter for conveyor modules.
    
    Implements conveyor-specific behavior:
    - Speed control (0-100)
    - Direction control
    - Position tracking
    """

    def __init__(self, device_id: str):
        super().__init__(device_id, "conveyor")
        self._direction = 1  # 1 = forward, -1 = reverse

    def get_telemetry(self) -> dict:
        """Get conveyor-specific telemetry."""
        telemetry = super().get_telemetry()
        telemetry["position"] = self._state_machine.module.position
        telemetry["direction"] = self._direction
        return telemetry


class RobotAdapter(DeviceAdapter):
    """Device adapter for robotic arms (MiniAlpha).
    
    Implements robot-specific behavior:
    - Joint position control
    - Gripper control
    - Predefined motion sequences
    """

    def __init__(self, device_id: str):
        super().__init__(device_id, "robot")
        self._gripper_state = "open"
        self._joint_positions = [0.0, 0.0, 0.0, 0.0]  # 4 joints

    def get_telemetry(self) -> dict:
        """Get robot-specific telemetry."""
        telemetry = super().get_telemetry()
        telemetry["gripper_state"] = self._gripper_state
        telemetry["joint_positions"] = self._joint_positions
        return telemetry


class CraneAdapter(DeviceAdapter):
    """Device adapter for tower crane modules.
    
    Implements crane-specific behavior:
    - Hoist position (vertical)
    - Trolley position (horizontal along boom)
    - Boom rotation
    """

    def __init__(self, device_id: str):
        super().__init__(device_id, "crane")
        self._hoist_position = 0  # 0-100%
        self._trolley_position = 0  # 0-100%
        self._rotation = 0  # 0-360 degrees

    def get_telemetry(self) -> dict:
        """Get crane-specific telemetry."""
        telemetry = super().get_telemetry()
        telemetry["hoist_position"] = self._hoist_position
        telemetry["trolley_position"] = self._trolley_position
        telemetry["rotation"] = self._rotation
        return telemetry
