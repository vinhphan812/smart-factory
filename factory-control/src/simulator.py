"""Factory simulator for offline testing and E2E testing.

Provides a deterministic factory simulator that can run without hardware.
Supports multiple device types and generates events for downstream consumers
(gateway, twin, dashboard).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
import asyncio
import logging

from adapters import DeviceAdapter, ConveyorAdapter, RobotAdapter, CraneAdapter
from state_machine import CommandName, ProductionState

logger = logging.getLogger(__name__)


@dataclass
class SimulatorConfig:
    """Configuration for the factory simulator."""

    tick_interval_ms: int = 100  # Simulation tick interval
    enable_telemetry: bool = True  # Generate telemetry events
    enable_events: bool = True  # Generate state change events


class FactorySimulator:
    """Deterministic factory simulator.
    
    Manages multiple device adapters and provides a unified interface
    for simulation control. Events are generated for downstream consumers.
    """

    def __init__(self, config: Optional[SimulatorConfig] = None):
        self._config = config or SimulatorConfig()
        self._devices: dict[str, DeviceAdapter] = {}
        self._running = False
        self._tick_count = 0
        self._event_callbacks: list[callable] = []
        self._telemetry_callbacks: list[callable] = []

    def register_device(self, device: DeviceAdapter) -> None:
        """Register a device adapter with the simulator."""
        self._devices[device.device_id] = device
        logger.info("Registered device: %s (%s)", device.device_id, device.device_type)

    def create_device(
        self,
        device_id: str,
        device_type: str,
    ) -> DeviceAdapter:
        """Create and register a new device.
        
        Factory method for creating devices by type.
        """
        if device_type == "conveyor":
            device = ConveyorAdapter(device_id)
        elif device_type == "robot":
            device = RobotAdapter(device_id)
        elif device_type == "crane":
            device = CraneAdapter(device_id)
        else:
            device = DeviceAdapter(device_id, device_type)
        
        self.register_device(device)
        return device

    def get_device(self, device_id: str) -> Optional[DeviceAdapter]:
        """Get a device by ID."""
        return self._devices.get(device_id)

    def list_devices(self) -> list[str]:
        """List all registered device IDs."""
        return list(self._devices.keys())

    def on_event(self, callback: callable) -> None:
        """Register a callback for device events."""
        self._event_callbacks.append(callback)

    def on_telemetry(self, callback: callable) -> None:
        """Register a callback for telemetry events."""
        self._telemetry_callbacks.append(callback)

    def execute_command(
        self,
        device_id: str,
        command_name: str,
        arguments: Optional[list[str]] = None,
        command_id: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> dict:
        """Execute a command on a device.
        
        Returns a command result dictionary matching the MQTT ACK format.
        """
        from adapters import Command

        device = self._devices.get(device_id)
        if not device:
            return {
                "request_id": request_id or str(command_id or ""),
                "status": "failed",
                "status_code": 5,  # device_not_found
                "error_message": f"Device {device_id} not found",
            }

        try:
            cmd = Command(
                command_id=command_id,
                request_id=request_id,
                device_id=device_id,
                command_name=CommandName(command_name),
                arguments=arguments or [],
            )
        except ValueError as e:
            return {
                "request_id": request_id or str(command_id or ""),
                "status": "failed",
                "status_code": 1,  # unknown_command
                "error_message": str(e),
            }

        result = device.execute(cmd)
        
        return {
            "request_id": result.request_id,
            "sequence": result.sequence,
            "command": result.command,
            "status": result.status.value,
            "status_code": result.status_code,
            "attempts": result.attempts,
            "error_message": result.error_message,
            "timestamp": result.timestamp,
        }

    async def tick_async(self) -> None:
        """Advance simulation by one tick (async version)."""
        self._tick_count += 1
        
        # Tick all devices
        for device in self._devices.values():
            previous_state = device.state
            device.tick()
            
            # Generate state change events
            if self._config.enable_events and previous_state != device.state:
                event = device.generate_event(
                    "status_change",
                    {
                        "previous_state": previous_state.value,
                        "current_state": device.state.value,
                    },
                )
                for callback in self._event_callbacks:
                    try:
                        await callback(event)
                    except Exception as e:
                        logger.exception("Event callback error: %s", e)
            
            # Generate telemetry
            if self._config.enable_telemetry and self._tick_count % 10 == 0:
                telemetry = device.get_telemetry()
                for callback in self._telemetry_callbacks:
                    try:
                        await callback(telemetry)
                    except Exception as e:
                        logger.exception("Telemetry callback error: %s", e)

    def tick(self) -> None:
        """Advance simulation by one tick (sync version)."""
        self._tick_count += 1
        
        # Tick all devices
        for device in self._devices.values():
            previous_state = device.state
            device.tick()
            
            # Generate state change events
            if self._config.enable_events and previous_state != device.state:
                event = device.generate_event(
                    "status_change",
                    {
                        "previous_state": previous_state.value,
                        "current_state": device.state.value,
                    },
                )
                for callback in self._event_callbacks:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.exception("Event callback error: %s", e)
            
            # Generate telemetry
            if self._config.enable_telemetry and self._tick_count % 10 == 0:
                telemetry = device.get_telemetry()
                for callback in self._telemetry_callbacks:
                    try:
                        callback(telemetry)
                    except Exception as e:
                        logger.exception("Telemetry callback error: %s", e)

    def run(self, ticks: int) -> None:
        """Run simulation for a specified number of ticks."""
        for _ in range(ticks):
            self.tick()

    async def run_async(self, ticks: int) -> None:
        """Run simulation for a specified number of ticks (async version)."""
        for _ in range(ticks):
            await self.tick_async()

    def get_state(self) -> dict:
        """Get the current state of all devices."""
        return {
            "tick": self._tick_count,
            "devices": {
                device_id: device.get_state_dict()
                for device_id, device in self._devices.items()
            },
            "running": self._running,
        }

    def reset(self) -> None:
        """Reset all devices to initial state."""
        for device in self._devices.values():
            device.reset()
        self._tick_count = 0
        logger.info("Factory simulator reset")


# Factory presets for common configurations
def create_demo_factory() -> FactorySimulator:
    """Create a demo factory with typical modules.
    
    Returns a simulator with:
    - conveyor-01: Main conveyor
    - conveyor-02: Secondary conveyor
    - robot-01: Robotic arm
    - crane-01: Tower crane
    """
    simulator = FactorySimulator()
    
    simulator.create_device("conveyor-01", "conveyor")
    simulator.create_device("conveyor-02", "conveyor")
    simulator.create_device("robot-01", "robot")
    simulator.create_device("crane-01", "crane")
    
    return simulator


def create_minimal_factory() -> FactorySimulator:
    """Create a minimal factory for basic testing.
    
    Returns a simulator with a single conveyor.
    """
    simulator = FactorySimulator()
    simulator.create_device("conveyor-01", "conveyor")
    return simulator
