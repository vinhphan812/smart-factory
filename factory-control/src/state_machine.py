"""Deterministic production state machine.

Defines the canonical production states and transitions for the factory.
Each state transition is deterministic and traceable for testing.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


class ProductionState(str, Enum):
    """Canonical production states for factory modules.
    
    States follow a deterministic lifecycle:
    - IDLE: Module initialized, no production active
    - INITIALIZING: Module starting up, sensors calibrating
    - READY: Module ready to receive commands
    - RUNNING: Module actively processing/transporting
    - PAUSED: Production paused, state preserved
    - STOPPING: Graceful shutdown in progress
    - STOPPED: Module stopped, safe to reconfigure
    - ERROR: Fault condition, requires intervention
    - ESTOP: Emergency stop active, safety mode
    """

    IDLE = "idle"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    ESTOP = "estop"


class CommandName(str, Enum):
    """Supported commands for factory modules.
    
    Matches the MQTT command contract (command.schema.json).
    """

    CONVEYOR_START = "CONVEYOR_START"
    CONVEYOR_STOP = "CONVEYOR_STOP"
    RESET = "RESET"
    PING = "PING"
    SET_OUTPUT = "SET_OUTPUT"
    ESTOP = "ESTOP"  # Emergency stop
    PAUSE = "PAUSE"
    RESUME = "RESUME"


class CommandStatus(str, Enum):
    """Command execution status.
    
    Matches the command lifecycle contract.
    """

    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    EXPIRED = "expired"
    TIMEOUT = "timeout"


@dataclass
class StateTransition:
    """Records a state transition for traceability.
    
    Every transition is deterministic and logged with timestamps
    for debugging and replay.
    """

    from_state: ProductionState
    to_state: ProductionState
    command: Optional[CommandName] = None
    triggered_by: str = "system"  # "system", "command", "timeout", "error"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    transition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reason: str = ""


@dataclass
class ModuleState:
    """State for a single factory module.
    
    Contains all stateful information for deterministic simulation
    and replay capability.
    """

    module_id: str
    module_type: str  # "conveyor", "robot", "crane", etc.
    state: ProductionState = ProductionState.IDLE
    speed: int = 0  # 0-100, conveyor speed setting
    position: int = 0  # Current position (encoder ticks or similar)
    error_code: Optional[str] = None
    error_message: str = ""
    sequence: int = 0  # Monotonically increasing for deduplication
    last_transition: Optional[StateTransition] = None
    transitions: list[StateTransition] = field(default_factory=list)
    # Deterministic simulation state
    simulated_ticks: int = 0
    _state_ticks: int = 0  # Ticks spent in current state (for auto-transition)
    last_update: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def transition_to(
        self,
        new_state: ProductionState,
        command: Optional[CommandName] = None,
        triggered_by: str = "system",
        reason: str = "",
    ) -> StateTransition:
        """Perform a deterministic state transition."""
        transition = StateTransition(
            from_state=self.state,
            to_state=new_state,
            command=command,
            triggered_by=triggered_by,
            reason=reason,
        )
        self.state = new_state
        self.last_transition = transition
        self.transitions.append(transition)
        self.last_update = datetime.now(timezone.utc).isoformat()
        self.sequence += 1
        # Reset ticks for auto-transition states
        if new_state in (ProductionState.INITIALIZING, ProductionState.STOPPING):
            self._state_ticks = 0
        return transition

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "module_id": self.module_id,
            "module_type": self.module_type,
            "state": self.state.value,
            "speed": self.speed,
            "position": self.position,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "sequence": self.sequence,
            "last_transition": (
                {
                    "from_state": self.last_transition.from_state.value,
                    "to_state": self.last_transition.to_state.value,
                    "command": self.last_transition.command.value
                    if self.last_transition.command
                    else None,
                    "triggered_by": self.last_transition.triggered_by,
                    "timestamp": self.last_transition.timestamp,
                    "transition_id": self.last_transition.transition_id,
                    "reason": self.last_transition.reason,
                }
                if self.last_transition
                else None
            ),
            "simulated_ticks": self.simulated_ticks,
            "last_update": self.last_update,
        }


# Valid state transitions - defines deterministic behavior
VALID_TRANSITIONS: dict[ProductionState, dict[CommandName, ProductionState]] = {
    ProductionState.IDLE: {
        CommandName.PING: ProductionState.IDLE,
        CommandName.RESET: ProductionState.INITIALIZING,
        CommandName.ESTOP: ProductionState.ESTOP,
    },
    ProductionState.INITIALIZING: {
        CommandName.PING: ProductionState.INITIALIZING,
        CommandName.ESTOP: ProductionState.ESTOP,
    },
    # Initialization completes to READY after simulated time
    ProductionState.READY: {
        CommandName.CONVEYOR_START: ProductionState.RUNNING,
        CommandName.PING: ProductionState.READY,
        CommandName.ESTOP: ProductionState.ESTOP,
        CommandName.PAUSE: ProductionState.PAUSED,
    },
    ProductionState.RUNNING: {
        CommandName.CONVEYOR_STOP: ProductionState.STOPPING,
        CommandName.PAUSE: ProductionState.PAUSED,
        CommandName.ESTOP: ProductionState.ESTOP,
        CommandName.PING: ProductionState.RUNNING,
    },
    ProductionState.PAUSED: {
        CommandName.RESUME: ProductionState.RUNNING,
        CommandName.CONVEYOR_STOP: ProductionState.STOPPING,
        CommandName.ESTOP: ProductionState.ESTOP,
        CommandName.PING: ProductionState.PAUSED,
    },
    ProductionState.STOPPING: {
        CommandName.PING: ProductionState.STOPPING,
        CommandName.ESTOP: ProductionState.ESTOP,
    },
    # STOPPING completes to STOPPED after simulated time
    ProductionState.STOPPED: {
        CommandName.RESET: ProductionState.READY,
        CommandName.PING: ProductionState.STOPPED,
        CommandName.ESTOP: ProductionState.ESTOP,
    },
    ProductionState.ERROR: {
        CommandName.RESET: ProductionState.INITIALIZING,
        CommandName.PING: ProductionState.ERROR,
    },
    ProductionState.ESTOP: {
        CommandName.RESET: ProductionState.INITIALIZING,
        CommandName.PING: ProductionState.ESTOP,
    },
}


class ProductionStateMachine:
    """Deterministic production state machine.
    
    Enforces valid state transitions and provides traceable state history.
    Each transition is deterministic and deterministic-simulatable.
    """

    def __init__(self, module_id: str, module_type: str):
        self.module = ModuleState(module_id=module_id, module_type=module_type)
        self._valid_transitions = VALID_TRANSITIONS

    @property
    def state(self) -> ProductionState:
        """Current production state."""
        return self.module.state

    @property
    def module_id(self) -> str:
        """Module identifier."""
        return self.module.module_id

    def can_transition(self, command: CommandName) -> bool:
        """Check if command can be executed in current state."""
        state_transitions = self._valid_transitions.get(self.module.state, {})
        return command in state_transitions

    def execute_command(
        self,
        command: CommandName,
        arguments: Optional[list[str]] = None,
    ) -> tuple[bool, Optional[str]]:
        """Execute a command with deterministic state transition.
        
        Returns:
            (success, error_message)
            - success: True if command was executed
            - error_message: None on success, error description on failure
        """
        arguments = arguments or []

        # Check if transition is valid
        state_transitions = self._valid_transitions.get(self.module.state, {})
        if command not in state_transitions:
            return False, f"Command {command.value} not valid in state {self.module.state.value}"

        new_state = state_transitions[command]

        # Handle special commands
        if command == CommandName.CONVEYOR_START:
            if arguments and len(arguments) > 0:
                try:
                    speed = int(arguments[0])
                    if 1 <= speed <= 100:
                        self.module.speed = speed
                    else:
                        return False, f"Invalid speed {speed}, must be 1-100"
                except ValueError:
                    return False, f"Invalid speed argument: {arguments[0]}"
            else:
                self.module.speed = 60  # Default speed

        elif command == CommandName.SET_OUTPUT:
            if arguments and len(arguments) >= 2:
                # SET_OUTPUT takes channel and value
                pass  # Simulated, no actual hardware
            else:
                return False, "SET_OUTPUT requires channel and value arguments"

        # Perform transition
        reason = f"Command: {command.value}"
        if arguments:
            reason += f" args: {arguments}"
        self.module.transition_to(new_state, command, "command", reason)

        return True, None

    def tick(self) -> None:
        """Advance simulation by one tick.
        
        Handles state machine completion (e.g., INITIALIZING -> READY).
        This is deterministic - same input always produces same output.
        """
        self.module.simulated_ticks += 1
        self.module._state_ticks += 1

        # Handle auto-transitions (state machine completion)
        if self.module.state == ProductionState.INITIALIZING:
            # Simulate initialization time (deterministic: 10 ticks)
            if self.module._state_ticks >= 10:
                self.module.transition_to(
                    ProductionState.READY,
                    triggered_by="system",
                    reason="Initialization complete",
                )

        elif self.module.state == ProductionState.STOPPING:
            # Simulate stop time (deterministic: 5 ticks)
            if self.module._state_ticks >= 5:
                self.module.transition_to(
                    ProductionState.STOPPED,
                    triggered_by="system",
                    reason="Stop complete",
                )

        elif self.module.state == ProductionState.RUNNING:
            # Simulate position advancement when running
            self.module.position += self.module.speed

        self.module.last_update = datetime.now(timezone.utc).isoformat()

    def reset(self) -> None:
        """Reset state machine to IDLE."""
        self.module = ModuleState(
            module_id=self.module.module_id,
            module_type=self.module.module_type,
        )

    def get_state(self) -> dict:
        """Get current state as dictionary."""
        return self.module.to_dict()

    def get_history(self) -> list[dict]:
        """Get state transition history."""
        return [
            {
                "from_state": t.from_state.value,
                "to_state": t.to_state.value,
                "command": t.command.value if t.command else None,
                "triggered_by": t.triggered_by,
                "timestamp": t.timestamp,
                "transition_id": t.transition_id,
                "reason": t.reason,
            }
            for t in self.module.transitions
        ]
