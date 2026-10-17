"""Tests for factory device adapters."""

import pytest
from adapters import (
    DeviceAdapter,
    ConveyorAdapter,
    RobotAdapter,
    CraneAdapter,
    Command,
    CommandResult,
)
from state_machine import ProductionState, CommandName, CommandStatus


class TestCommand:
    """Tests for Command dataclass."""

    def test_command_with_command_id(self):
        """Command uses command_id as correlation ID."""
        cmd = Command(command_id=123, command_name=CommandName.PING)
        assert cmd.correlation_id == "123"

    def test_command_with_request_id(self):
        """Command uses request_id as correlation ID."""
        cmd = Command(request_id="abc-456", command_name=CommandName.PING)
        assert cmd.correlation_id == "abc-456"

    def test_command_generates_uuid_if_no_id(self):
        """Command generates UUID if no correlation ID provided."""
        cmd = Command(command_name=CommandName.PING)
        assert cmd.correlation_id != ""
        # Should be a valid UUID string
        uuid_str = cmd.correlation_id
        assert len(uuid_str) == 36  # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx


class TestDeviceAdapter:
    """Tests for DeviceAdapter base class."""

    def test_initial_state(self):
        """Adapter starts in IDLE state."""
        adapter = DeviceAdapter("test-01", "generic")
        assert adapter.state == ProductionState.IDLE
        assert adapter.device_id == "test-01"
        assert adapter.device_type == "generic"

    def test_can_execute_ping(self):
        """PING command is allowed in IDLE state."""
        adapter = DeviceAdapter("test-01", "generic")
        cmd = Command(command_id=1, command_name=CommandName.PING)  # Need correlation ID
        can_exec, error = adapter.can_execute(cmd)
        assert can_exec is True
        assert error is None

    def test_rejects_ttl_too_low(self):
        """Rejects TTL less than 1."""
        adapter = DeviceAdapter("test-01", "generic")
        cmd = Command(command_name=CommandName.PING, ttl_seconds=0)
        can_exec, error = adapter.can_execute(cmd)
        assert can_exec is False
        assert "ttl_seconds" in error.lower()

    def test_rejects_ttl_too_high(self):
        """Rejects TTL greater than 300."""
        adapter = DeviceAdapter("test-01", "generic")
        cmd = Command(command_name=CommandName.PING, ttl_seconds=500)
        can_exec, error = adapter.can_execute(cmd)
        assert can_exec is False
        assert "ttl_seconds" in error.lower()

    def test_rejects_missing_correlation_id(self):
        """Rejects command without correlation ID."""
        adapter = DeviceAdapter("test-01", "generic")
        cmd = Command(command_name=CommandName.PING)
        cmd.command_id = None
        cmd.request_id = None
        can_exec, error = adapter.can_execute(cmd)
        assert can_exec is False
        assert "command_id" in error.lower() or "request_id" in error.lower()

    def test_execute_valid_command(self):
        """Executes valid command successfully."""
        adapter = DeviceAdapter("test-01", "generic")
        cmd = Command(command_id=1, command_name=CommandName.PING)
        result = adapter.execute(cmd)
        
        assert result.status == CommandStatus.ACKNOWLEDGED
        assert result.status_code == 0
        assert result.command == "PING"

    def test_execute_resets_module_state(self):
        """Reset command changes state."""
        adapter = DeviceAdapter("test-01", "generic")
        cmd = Command(command_id=1, command_name=CommandName.RESET)
        result = adapter.execute(cmd)
        
        assert result.status == CommandStatus.ACKNOWLEDGED
        assert adapter.state == ProductionState.INITIALIZING

    def test_get_telemetry(self):
        """Generates valid telemetry."""
        adapter = DeviceAdapter("test-01", "generic")
        telemetry = adapter.get_telemetry()
        
        assert "device_id" in telemetry
        assert "timestamp" in telemetry
        assert "state" in telemetry
        assert "speed" in telemetry
        assert "sensors" in telemetry

    def test_generate_event(self):
        """Generates valid event."""
        adapter = DeviceAdapter("test-01", "generic")
        event = adapter.generate_event("command_acknowledged", {"status": "ok"})
        
        assert "event_id" in event
        assert event["device_id"] == "test-01"
        assert event["event_type"] == "command_acknowledged"

    def test_reset_clears_state(self):
        """Reset clears adapter state."""
        adapter = DeviceAdapter("test-01", "generic")
        adapter.execute(Command(command_id=1, command_name=CommandName.RESET))
        
        adapter.reset()
        
        assert adapter.state == ProductionState.IDLE

    def test_get_state_dict(self):
        """Returns state as dictionary."""
        adapter = DeviceAdapter("test-01", "generic")
        state = adapter.get_state_dict()
        
        assert "module_id" in state
        assert state["module_id"] == "test-01"
        assert "state" in state


class TestConveyorAdapter:
    """Tests for ConveyorAdapter."""

    def test_initial_state(self):
        """Conveyor adapter starts correctly."""
        adapter = ConveyorAdapter("conveyor-01")
        assert adapter.device_type == "conveyor"
        assert adapter.state == ProductionState.IDLE
        assert adapter._direction == 1

    def test_get_telemetry_includes_position(self):
        """Conveyor telemetry includes position."""
        adapter = ConveyorAdapter("conveyor-01")
        telemetry = adapter.get_telemetry()
        
        assert "position" in telemetry
        assert "direction" in telemetry

    def test_speed_control(self):
        """Controls speed through commands."""
        adapter = ConveyorAdapter("conveyor-01")
        
        # Initialize
        adapter.execute(Command(command_id=1, command_name=CommandName.RESET))
        for _ in range(10):
            adapter.tick()
        
        # Start with speed
        adapter.execute(Command(command_id=2, command_name=CommandName.CONVEYOR_START, arguments=["75"]))
        
        assert adapter.get_module_state().speed == 75


class TestRobotAdapter:
    """Tests for RobotAdapter."""

    def test_initial_state(self):
        """Robot adapter starts correctly."""
        adapter = RobotAdapter("robot-01")
        assert adapter.device_type == "robot"
        assert adapter._gripper_state == "open"
        assert len(adapter._joint_positions) == 4

    def test_get_telemetry_includes_gripper(self):
        """Robot telemetry includes gripper state."""
        adapter = RobotAdapter("robot-01")
        telemetry = adapter.get_telemetry()
        
        assert "gripper_state" in telemetry
        assert "joint_positions" in telemetry


class TestCraneAdapter:
    """Tests for CraneAdapter."""

    def test_initial_state(self):
        """Crane adapter starts correctly."""
        adapter = CraneAdapter("crane-01")
        assert adapter.device_type == "crane"
        assert adapter._hoist_position == 0
        assert adapter._trolley_position == 0
        assert adapter._rotation == 0

    def test_get_telemetry_includes_crane_specific(self):
        """Crane telemetry includes crane-specific fields."""
        adapter = CraneAdapter("crane-01")
        telemetry = adapter.get_telemetry()
        
        assert "hoist_position" in telemetry
        assert "trolley_position" in telemetry
        assert "rotation" in telemetry


class TestAdapterIntegration:
    """Integration tests for adapters."""

    def test_command_lifecycle(self):
        """Tests complete command lifecycle."""
        adapter = DeviceAdapter("test-01", "conveyor")
        
        # PENDING -> SENT via execute
        cmd = Command(command_id=1, command_name=CommandName.RESET)
        result = adapter.execute(cmd)
        
        assert result.status == CommandStatus.ACKNOWLEDGED
        assert result.status_code == 0
        
        # Tick through initialization
        for _ in range(10):
            adapter.tick()
        
        assert adapter.state == ProductionState.READY
        
        # Start conveyor
        cmd2 = Command(command_id=2, command_name=CommandName.CONVEYOR_START, arguments=["50"])
        result2 = adapter.execute(cmd2)
        
        assert result2.status == CommandStatus.ACKNOWLEDGED
        assert adapter.state == ProductionState.RUNNING

    def test_estop_from_running(self):
        """ESTOP works from RUNNING state."""
        adapter = DeviceAdapter("test-01", "conveyor")
        
        # Setup to RUNNING
        adapter.execute(Command(command_id=1, command_name=CommandName.RESET))
        for _ in range(10):
            adapter.tick()
        adapter.execute(Command(command_id=2, command_name=CommandName.CONVEYOR_START))
        
        # Trigger ESTOP
        cmd = Command(command_id=3, command_name=CommandName.ESTOP)
        result = adapter.execute(cmd)
        
        assert result.status == CommandStatus.ACKNOWLEDGED
        assert adapter.state == ProductionState.ESTOP


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
