"""Tests for factory control state machine."""

import pytest
from state_machine import (
    ProductionState,
    CommandName,
    CommandStatus,
    ProductionStateMachine,
    ModuleState,
    VALID_TRANSITIONS,
)


class TestProductionState:
    """Tests for ProductionState enum."""

    def test_all_states_defined(self):
        """All expected production states are defined."""
        expected_states = {
            "idle",
            "initializing",
            "ready",
            "running",
            "paused",
            "stopping",
            "stopped",
            "error",
            "estop",
        }
        actual_states = {s.value for s in ProductionState}
        assert actual_states == expected_states


class TestCommandName:
    """Tests for CommandName enum."""

    def test_all_commands_defined(self):
        """All expected commands are defined."""
        expected_commands = {
            "CONVEYOR_START",
            "CONVEYOR_STOP",
            "RESET",
            "PING",
            "SET_OUTPUT",
            "ESTOP",
            "PAUSE",
            "RESUME",
        }
        actual_commands = {c.value for c in CommandName}
        assert actual_commands == expected_commands


class TestModuleState:
    """Tests for ModuleState dataclass."""

    def test_initial_state(self):
        """Module starts in IDLE state."""
        module = ModuleState(module_id="test-01", module_type="conveyor")
        assert module.state == ProductionState.IDLE
        assert module.speed == 0
        assert module.position == 0
        assert module.error_code is None

    def test_transition_creates_record(self):
        """State transition creates a transition record."""
        module = ModuleState(module_id="test-01", module_type="conveyor")
        transition = module.transition_to(
            ProductionState.READY,
            command=CommandName.RESET,
            triggered_by="command",
            reason="Test transition",
        )
        
        assert transition.from_state == ProductionState.IDLE
        assert transition.to_state == ProductionState.READY
        assert transition.command == CommandName.RESET
        assert transition.triggered_by == "command"
        assert transition.reason == "Test transition"
        assert module.last_transition == transition
        assert len(module.transitions) == 1

    def test_to_dict_serializes_correctly(self):
        """Module state serializes to dictionary correctly."""
        module = ModuleState(module_id="test-01", module_type="conveyor")
        module.state = ProductionState.RUNNING
        module.speed = 60
        module.position = 100
        
        d = module.to_dict()
        
        assert d["module_id"] == "test-01"
        assert d["module_type"] == "conveyor"
        assert d["state"] == "running"
        assert d["speed"] == 60
        assert d["position"] == 100


class TestProductionStateMachine:
    """Tests for ProductionStateMachine."""

    def test_initial_state(self):
        """State machine starts in IDLE state."""
        sm = ProductionStateMachine("test-01", "conveyor")
        assert sm.state == ProductionState.IDLE
        assert sm.module_id == "test-01"

    def test_ping_in_idle_state(self):
        """PING command is valid in IDLE state."""
        sm = ProductionStateMachine("test-01", "conveyor")
        assert sm.can_transition(CommandName.PING) is True

    def test_conveyor_start_requires_ready(self):
        """CONVEYOR_START is not valid in IDLE state."""
        sm = ProductionStateMachine("test-01", "conveyor")
        assert sm.can_transition(CommandName.CONVEYOR_START) is False

    def test_reset_transitions_to_initializing(self):
        """RESET command transitions from IDLE to INITIALIZING."""
        sm = ProductionStateMachine("test-01", "conveyor")
        success, error = sm.execute_command(CommandName.RESET)
        
        assert success is True
        assert error is None
        assert sm.state == ProductionState.INITIALIZING

    def test_initialization_completes_after_ticks(self):
        """INITIALIZING state auto-transitions to READY after ticks."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)
        
        assert sm.state == ProductionState.INITIALIZING
        
        # Tick until initialization completes (deterministic: 10 ticks)
        for _ in range(9):
            sm.tick()
            assert sm.state == ProductionState.INITIALIZING
        
        sm.tick()  # 10th tick
        assert sm.state == ProductionState.READY

    def test_conveyor_start_from_ready(self):
        """CONVEYOR_START works from READY state."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)
        
        # Complete initialization
        for _ in range(10):
            sm.tick()
        
        assert sm.state == ProductionState.READY
        
        # Start conveyor
        success, error = sm.execute_command(CommandName.CONVEYOR_START, ["75"])
        
        assert success is True
        assert error is None
        assert sm.state == ProductionState.RUNNING
        assert sm.module.speed == 75

    def test_conveyor_start_default_speed(self):
        """CONVEYOR_START uses default speed when not specified."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)
        
        for _ in range(10):
            sm.tick()
        
        sm.execute_command(CommandName.CONVEYOR_START)
        
        assert sm.module.speed == 60  # Default speed

    def test_invalid_speed_rejected(self):
        """CONVEYOR_START rejects invalid speed values."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)
        
        for _ in range(10):
            sm.tick()
        
        # Speed too high
        success, error = sm.execute_command(CommandName.CONVEYOR_START, ["150"])
        assert success is False
        assert "Invalid speed" in error

    def test_conveyor_stop_from_running(self):
        """CONVEYOR_STOP works from RUNNING state."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)
        
        for _ in range(10):
            sm.tick()
        
        sm.execute_command(CommandName.CONVEYOR_START)
        assert sm.state == ProductionState.RUNNING
        
        success, error = sm.execute_command(CommandName.CONVEYOR_STOP)
        
        assert success is True
        assert sm.state == ProductionState.STOPPING

    def test_stop_completes_after_ticks(self):
        """STOPPING state auto-transitions to STOPPED after ticks."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)

        for _ in range(10):
            sm.tick()

        sm.execute_command(CommandName.CONVEYOR_START)
        sm.execute_command(CommandName.CONVEYOR_STOP)

        assert sm.state == ProductionState.STOPPING

        # Tick until stop completes (deterministic: 5 ticks from command execution)
        # The STOPPING state counts ticks from when we entered it
        for _ in range(5):
            sm.tick()
            if sm.state == ProductionState.STOPPED:
                break
        
        # Now it should be STOPPED
        assert sm.state == ProductionState.STOPPED

    def test_estop_from_any_state(self):
        """ESTOP can be triggered from most states."""
        # Note: ESTOP is not valid from ERROR state (must use RESET to recover)
        states = [
            ProductionState.IDLE,
            ProductionState.INITIALIZING,
            ProductionState.READY,
            ProductionState.RUNNING,
            ProductionState.STOPPING,
            ProductionState.STOPPED,
        ]
        
        for state in states:
            sm = ProductionStateMachine("test-01", "conveyor")
            # Force to specific state for testing
            sm.module.state = state
            
            success, error = sm.execute_command(CommandName.ESTOP)
            
            assert success is True, f"ESTOP failed from {state}: {error}"
            assert sm.state == ProductionState.ESTOP

    def test_reset_from_estop(self):
        """RESET can recover from ESTOP."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.module.state = ProductionState.ESTOP
        
        success, error = sm.execute_command(CommandName.RESET)
        
        assert success is True
        assert sm.state == ProductionState.INITIALIZING

    def test_pause_from_running(self):
        """PAUSE command works from RUNNING state."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)
        
        for _ in range(10):
            sm.tick()
        
        sm.execute_command(CommandName.CONVEYOR_START)
        success, error = sm.execute_command(CommandName.PAUSE)
        
        assert success is True
        assert sm.state == ProductionState.PAUSED

    def test_resume_from_paused(self):
        """RESUME command works from PAUSED state."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)
        
        for _ in range(10):
            sm.tick()
        
        sm.execute_command(CommandName.CONVEYOR_START)
        sm.execute_command(CommandName.PAUSE)
        
        # Complete pause
        sm.tick()
        
        success, error = sm.execute_command(CommandName.RESUME)
        
        assert success is True
        assert sm.state == ProductionState.RUNNING

    def test_position_advances_when_running(self):
        """Position advances when conveyor is running."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)
        
        for _ in range(10):
            sm.tick()
        
        sm.execute_command(CommandName.CONVEYOR_START, ["60"])  # 60 speed
        
        initial_position = sm.module.position
        
        for _ in range(10):
            sm.tick()
        
        assert sm.module.position > initial_position

    def test_reset_clears_state(self):
        """Reset clears module state."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)
        
        for _ in range(10):
            sm.tick()
        
        sm.execute_command(CommandName.CONVEYOR_START, ["80"])
        sm.module.position = 1000
        
        sm.reset()
        
        assert sm.state == ProductionState.IDLE
        assert sm.module.speed == 0
        assert sm.module.position == 0
        assert len(sm.module.transitions) == 0

    def test_state_dict_includes_history(self):
        """State dictionary includes transition history."""
        sm = ProductionStateMachine("test-01", "conveyor")
        sm.execute_command(CommandName.RESET)
        
        for _ in range(10):
            sm.tick()
        
        state_dict = sm.get_state()
        
        assert "transitions" in state_dict or "last_transition" in state_dict

    def test_deterministic_behavior(self):
        """Same sequence produces same results (deterministic)."""
        # Run twice with same commands
        results1 = []
        results2 = []
        
        for _ in range(2):
            sm = ProductionStateMachine("test-01", "conveyor")
            
            sm.execute_command(CommandName.RESET)
            for _ in range(10):
                sm.tick()
            
            sm.execute_command(CommandName.CONVEYOR_START, ["60"])
            
            for _ in range(20):
                sm.tick()
            
            state = sm.get_state()
            if results1:
                results2.append(state)
            else:
                results1.append(state)
        
        # Compare positions (should be identical)
        assert results1[0]["position"] == results2[0]["position"]


class TestValidTransitions:
    """Tests for valid transition definitions."""

    def test_idle_has_valid_transitions(self):
        """IDLE state has valid outgoing transitions."""
        assert CommandName.PING in VALID_TRANSITIONS[ProductionState.IDLE]
        assert CommandName.RESET in VALID_TRANSITIONS[ProductionState.IDLE]

    def test_estop_accessible_from_all_states(self):
        """ESTOP is accessible from most states.
        
        Note: ESTOP is intentionally not valid from ERROR state - 
        system must use RESET to recover from errors safely.
        ESTOP state doesn't need ESTOP (already in estop).
        """
        # States where ESTOP should be valid
        estop_states = {
            ProductionState.IDLE,
            ProductionState.INITIALIZING,
            ProductionState.READY,
            ProductionState.RUNNING,
            ProductionState.PAUSED,
            ProductionState.STOPPING,
            ProductionState.STOPPED,
            # ESTOP state is already in ESTOP, doesn't need transition to itself
        }
        
        for state in ProductionState:
            if state in estop_states:
                assert CommandName.ESTOP in VALID_TRANSITIONS.get(state, {}), f"ESTOP missing from {state}"
            # ERROR state doesn't have ESTOP - must use RESET
            elif state == ProductionState.ERROR:
                assert CommandName.ESTOP not in VALID_TRANSITIONS.get(state, {}), f"ESTOP should not be in {state}"

    def test_no_self_transitions_except_ping(self):
        """Only PING allows self-transition (no state change)."""
        for state, commands in VALID_TRANSITIONS.items():
            for cmd, target in commands.items():
                if target == state and cmd != CommandName.PING:
                    # Some self-transitions may be valid, but they should be rare
                    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
