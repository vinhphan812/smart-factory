"""Tests for factory simulator."""

import pytest
from simulator import FactorySimulator, SimulatorConfig, create_demo_factory, create_minimal_factory
from state_machine import ProductionState, CommandName
from adapters import DeviceAdapter


class TestSimulatorConfig:
    """Tests for SimulatorConfig."""

    def test_default_config(self):
        """Default config has sensible defaults."""
        config = SimulatorConfig()
        assert config.tick_interval_ms == 100
        assert config.enable_telemetry is True
        assert config.enable_events is True


class TestFactorySimulator:
    """Tests for FactorySimulator."""

    def test_create_simulator(self):
        """Can create an empty simulator."""
        sim = FactorySimulator()
        assert sim.list_devices() == []

    def test_register_device(self):
        """Can register a device adapter."""
        from adapters import DeviceAdapter
        
        sim = FactorySimulator()
        device = DeviceAdapter("test-01", "conveyor")
        sim.register_device(device)
        
        assert "test-01" in sim.list_devices()
        assert sim.get_device("test-01") == device

    def test_create_device(self):
        """Can create devices via factory method."""
        sim = FactorySimulator()
        device = sim.create_device("conv-01", "conveyor")
        
        assert device.device_id == "conv-01"
        assert device.device_type == "conveyor"
        assert "conv-01" in sim.list_devices()

    def test_execute_command(self):
        """Can execute commands on devices."""
        sim = create_minimal_factory()
        
        result = sim.execute_command(
            "conveyor-01",
            "RESET",
            command_id=1,
        )
        
        assert result["status"] == "acknowledged"
        assert result["status_code"] == 0

    def test_run_simulation(self):
        """Can run simulation for ticks."""
        sim = create_minimal_factory()
        
        # Initialize
        sim.execute_command("conveyor-01", "RESET", command_id=1)
        
        # Run 10 ticks (should complete initialization)
        sim.run(10)
        
        state = sim.get_state()
        assert state["devices"]["conveyor-01"]["state"] == "ready"

    def test_tick_updates_state(self):
        """Tick advances simulation state."""
        sim = create_minimal_factory()
        
        # Initialize
        sim.execute_command("conveyor-01", "RESET", command_id=1)
        
        # Get initial tick
        initial_tick = sim.get_state()["tick"]
        
        # Tick
        sim.tick()
        
        assert sim.get_state()["tick"] == initial_tick + 1

    def test_reset(self):
        """Reset clears all device states."""
        sim = create_minimal_factory()
        
        # Initialize and run
        sim.execute_command("conveyor-01", "RESET", command_id=1)
        sim.run(10)
        
        # Reset
        sim.reset()
        
        state = sim.get_state()
        assert state["devices"]["conveyor-01"]["state"] == "idle"
        assert state["tick"] == 0


class TestFactoryPresets:
    """Tests for factory preset functions."""

    def test_create_minimal_factory(self):
        """Creates minimal factory with single conveyor."""
        sim = create_minimal_factory()
        
        assert "conveyor-01" in sim.list_devices()
        assert sim.get_device("conveyor-01").device_type == "conveyor"

    def test_create_demo_factory(self):
        """Creates demo factory with multiple modules."""
        sim = create_demo_factory()
        
        devices = sim.list_devices()
        assert "conveyor-01" in devices
        assert "conveyor-02" in devices
        assert "robot-01" in devices
        assert "crane-01" in devices
        assert len(devices) == 4


class TestSimulatorIntegration:
    """Integration tests for simulator."""

    def test_full_production_cycle(self):
        """Tests complete production cycle."""
        sim = create_minimal_factory()
        
        # Reset -> INITIALIZING -> READY (after 10 ticks)
        result = sim.execute_command("conveyor-01", "RESET", command_id=1)
        assert result["status"] == "acknowledged"
        
        sim.run(10)
        state = sim.get_state()["devices"]["conveyor-01"]
        assert state["state"] == "ready"
        
        # Start conveyor
        result = sim.execute_command(
            "conveyor-01", "CONVEYOR_START", 
            arguments=["60"], command_id=2
        )
        assert result["status"] == "acknowledged"
        
        state = sim.get_state()["devices"]["conveyor-01"]
        assert state["state"] == "running"
        assert state["speed"] == 60
        
        # Stop conveyor
        result = sim.execute_command("conveyor-01", "CONVEYOR_STOP", command_id=3)
        assert result["status"] == "acknowledged"
        
        # Let it stop (5 ticks)
        sim.run(5)
        
        state = sim.get_state()["devices"]["conveyor-01"]
        assert state["state"] == "stopped"

    def test_estop_integration(self):
        """ESTOP works from running state."""
        sim = create_minimal_factory()
        
        # Setup
        sim.execute_command("conveyor-01", "RESET", command_id=1)
        sim.run(10)
        sim.execute_command("conveyor-01", "CONVEYOR_START", command_id=2)
        
        # Trigger ESTOP
        result = sim.execute_command("conveyor-01", "ESTOP", command_id=3)
        assert result["status"] == "acknowledged"
        
        state = sim.get_state()["devices"]["conveyor-01"]
        assert state["state"] == "estop"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
