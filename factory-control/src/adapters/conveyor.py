"""Conveyor Belt module adapter with finite state machine and safety interlocks."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from adapters.base import BaseDeviceAdapter
from models import (
    CommandResult,
    ConveyorLimits,
    ConveyorSensors,
    ConveyorState,
    EStopSource,
)


class ConveyorAdapter(BaseDeviceAdapter):
    """Device adapter for the Smart Factory Conveyor Belt module (Module 1).
    
    Responsibilities:
    - Enforce local finite state machine (FSM): IDLE, STARTING, RUNNING, STOPPING, STOPPED, FAULT, E_STOP.
    - Check speed bounds against configured limits (default: 10 - 100 mm/s).
    - Local fail-closed emergency stop on sensor jam or physical E-Stop button (ADR-0006).
    - Deduplicate commands via correlation ID caching with payload binding (idempotency).
    - Strictly differentiate physical hardware E-Stop from software/jam interlock reset.
    - Generate canonical telemetry compliant with contracts/v1.
    """

    def __init__(
        self,
        device_id: str = "conveyor-01",
        limits: Optional[ConveyorLimits] = None,
        sensors: Optional[ConveyorSensors] = None,
        max_idempotency_cache: int = 1000,
        idempotency_window_seconds: float = 300.0,
    ) -> None:
        super().__init__(
            device_id=device_id,
            device_type="conveyor",
            max_idempotency_cache=max_idempotency_cache,
            idempotency_window_seconds=idempotency_window_seconds,
        )
        self.limits = limits or ConveyorLimits()
        self.sensors = sensors or ConveyorSensors()
        
        self._state: ConveyorState = ConveyorState.IDLE
        self._estop_source: EStopSource = EStopSource.NONE
        self._current_speed: int = 0
        self._target_speed: int = 0
        self._last_error: Optional[str] = None
        
        # Sync initial sensor bitmask
        self.sensors.update_digital_bitmask()

    @property
    def state(self) -> ConveyorState:
        """Current operational state."""
        return self._state

    @property
    def estop_source(self) -> EStopSource:
        """Current source of Emergency Stop."""
        return self._estop_source

    @property
    def current_speed(self) -> int:
        """Current observed belt speed."""
        return self._current_speed

    def _set_state(self, new_state: ConveyorState) -> None:
        """Transition state and notify listeners."""
        if self._state != new_state:
            old = self._state.value
            self._state = new_state
            self._notify_state_change(old, new_state.value)

    def handle_command(self, command: Dict[str, Any]) -> CommandResult:
        """Process an inbound command envelope.
        
        Accepts:
        - command_name: "CONVEYOR_START", "CONVEYOR_STOP", "RESET", "PING"
        - command_id / request_id: correlation identifier (explicit 'is not None' selection)
        - arguments: positional arguments (e.g. [speed])
        """
        command_id = None
        if "command_id" in command and command["command_id"] is not None:
            command_id = command["command_id"]
        elif "request_id" in command and command["request_id"] is not None:
            command_id = command["request_id"]

        if command_id is None:
            return CommandResult(
                command_id="unknown",
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="MISSING_CORRELATION_ID",
                message="Command rejected: neither command_id nor request_id provided",
            )

        if isinstance(command_id, int) and command_id < 0:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="INVALID_CORRELATION_ID",
                message=f"Command ID cannot be negative: {command_id}",
            )

        command_name = command.get("command_name", "")
        args = [str(a) for a in command.get("arguments", []) if a is not None]

        # Check Idempotency cache with payload binding
        cached_result, conflict_error = self.check_idempotency(command_id, command_name, args)
        if conflict_error == "CONFLICTING_COMMAND_REUSE":
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="CONFLICTING_COMMAND_REUSE",
                message=f"Command ID '{command_id}' was previously issued with different payload/arguments",
            )
        if cached_result is not None:
            return cached_result

        # Dispatch command
        if command_name == "CONVEYOR_START":
            result = self._handle_start(command_id, args)
        elif command_name == "CONVEYOR_STOP":
            result = self._handle_stop(command_id, args)
        elif command_name == "RESET":
            result = self._handle_reset(command_id)
        elif command_name == "PING":
            result = self._handle_ping(command_id)
        else:
            result = CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="UNKNOWN_COMMAND",
                message=f"Command '{command_name}' is not recognized for conveyor adapter",
            )

        self.cache_command_result(command_id, command_name, args, result)
        return result

    def _handle_start(self, command_id: Union[int, str], args: List[str]) -> CommandResult:
        """Handle CONVEYOR_START command with safety and speed checks."""
        if self._state == ConveyorState.E_STOP:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="CANNOT_START_IN_ESTOP",
                message=f"Conveyor is locked in E-Stop state ({self._estop_source.value}). Operator/hardware reset required.",
            )

        if self._state == ConveyorState.FAULT:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="CANNOT_START_IN_FAULT",
                message="Conveyor is in fault state. Clear fault and reset before starting.",
            )

        if self.sensors.jam_sensor:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="JAM_SENSOR_ACTIVE",
                message="Conveyor cannot start: jam sensor indicates product blockage.",
            )

        if self.sensors.physical_estop_button:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="PHYSICAL_ESTOP_ACTIVE",
                message="Conveyor cannot start: physical E-stop button is engaged on hardware.",
            )

        target_speed = self.limits.default_speed
        if args and len(args) > 0:
            try:
                target_speed = int(args[0])
            except (ValueError, TypeError):
                return CommandResult(
                    command_id=command_id,
                    status="rejected",
                    observed_state=self._state,
                    speed=self._current_speed,
                    error_code="INVALID_SPEED_FORMAT",
                    message=f"Speed argument must be an integer, got: {args[0]}",
                )

        if target_speed < 0:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="NEGATIVE_SPEED_NOT_ALLOWED",
                message="Speed must be positive; negative conveyor speeds are not permitted",
            )

        if target_speed == 0:
            return self._handle_stop(command_id, args)

        if target_speed < self.limits.min_speed:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="SPEED_BELOW_MIN",
                message=f"Speed {target_speed} is below safe minimum of {self.limits.min_speed}",
            )

        if target_speed > self.limits.max_speed:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="SPEED_EXCEEDS_MAX",
                message=f"Speed {target_speed} exceeds safe maximum of {self.limits.max_speed}",
            )

        self._target_speed = target_speed
        self._set_state(ConveyorState.STARTING)
        self._current_speed = target_speed
        self._set_state(ConveyorState.RUNNING)

        self._notify_telemetry(self.get_telemetry())

        return CommandResult(
            command_id=command_id,
            status="acknowledged",
            observed_state=self._state,
            speed=self._current_speed,
            message=f"Conveyor started successfully at speed {self._current_speed}",
        )

    def _handle_stop(self, command_id: Union[int, str], args: List[str]) -> CommandResult:
        """Handle CONVEYOR_STOP command."""
        if self._state == ConveyorState.E_STOP:
            return CommandResult(
                command_id=command_id,
                status="acknowledged",
                observed_state=self._state,
                speed=0,
                message="Conveyor already stopped (in E-Stop)",
            )

        self._set_state(ConveyorState.STOPPING)
        self._current_speed = 0
        self._target_speed = 0
        self._set_state(ConveyorState.STOPPED)

        self._notify_telemetry(self.get_telemetry())

        return CommandResult(
            command_id=command_id,
            status="acknowledged",
            observed_state=self._state,
            speed=0,
            message="Conveyor stopped successfully",
        )

    def _handle_reset(self, command_id: Union[int, str]) -> CommandResult:
        """Handle RESET command."""
        return self.reset(command_id=command_id)

    def _handle_ping(self, command_id: Union[int, str]) -> CommandResult:
        """Handle PING command without changing state."""
        return CommandResult(
            command_id=command_id,
            status="acknowledged",
            observed_state=self._state,
            speed=self._current_speed,
            message="pong",
        )

    def update_sensors(
        self,
        optical_entry: Optional[bool] = None,
        optical_exit: Optional[bool] = None,
        jam_sensor: Optional[bool] = None,
        physical_estop_button: Optional[bool] = None,
        temperature_centi_c: Optional[int] = None,
        humidity_centi_percent: Optional[int] = None,
    ) -> None:
        """Update sensor inputs and trigger safety interlocks if jam or physical E-stop detected."""
        if optical_entry is not None:
            self.sensors.optical_entry = optical_entry
        if optical_exit is not None:
            self.sensors.optical_exit = optical_exit
        if jam_sensor is not None:
            self.sensors.jam_sensor = jam_sensor
        if physical_estop_button is not None:
            self.sensors.physical_estop_button = physical_estop_button
        if temperature_centi_c is not None:
            self.sensors.temperature_centi_c = temperature_centi_c
        if humidity_centi_percent is not None:
            self.sensors.humidity_centi_percent = humidity_centi_percent

        self.sensors.update_digital_bitmask()

        if self.sensors.physical_estop_button and self._state != ConveyorState.E_STOP:
            self.emergency_stop(
                reason="Physical hardware emergency stop button pressed",
                source=EStopSource.PHYSICAL_HARDWARE,
            )
            return

        if self.sensors.jam_sensor and self._state in (ConveyorState.RUNNING, ConveyorState.STARTING):
            self.emergency_stop(
                reason="Obstruction detected by jam sensor",
                source=EStopSource.JAM_SENSOR,
            )

    def emergency_stop(
        self,
        reason: str = "Manual E-Stop",
        source: EStopSource = EStopSource.SOFTWARE,
    ) -> CommandResult:
        """Engage immediate local emergency stop interlock."""
        self._last_error = reason
        self._estop_source = source
        self._current_speed = 0
        self._target_speed = 0
        self._set_state(ConveyorState.E_STOP)

        self._notify_telemetry(self.get_telemetry())

        return CommandResult(
            command_id="estop",
            status="acknowledged",
            observed_state=ConveyorState.E_STOP,
            speed=0,
            error_code="EMERGENCY_STOP",
            message=f"Emergency stop engaged [{source.value}]: {reason}",
        )

    def reset(self, command_id: Optional[Union[int, str]] = None) -> CommandResult:
        """Attempt to reset adapter from E_STOP or FAULT to IDLE."""
        cid = command_id if command_id is not None else "reset"

        if self.sensors.physical_estop_button or self._estop_source == EStopSource.PHYSICAL_HARDWARE:
            return CommandResult(
                command_id=cid,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="PHYSICAL_ESTOP_ACTIVE",
                message="Cannot reset via network: physical hardware emergency stop must be manually released on-site first",
            )

        if self.sensors.jam_sensor:
            return CommandResult(
                command_id=cid,
                status="rejected",
                observed_state=self._state,
                speed=self._current_speed,
                error_code="JAM_OBSTRUCTION_PRESENT",
                message="Cannot reset conveyor: physical jam obstruction is still detected by sensor",
            )

        self._last_error = None
        self._estop_source = EStopSource.NONE
        self._current_speed = 0
        self._target_speed = 0
        self._set_state(ConveyorState.IDLE)

        self._notify_telemetry(self.get_telemetry())

        return CommandResult(
            command_id=cid,
            status="acknowledged",
            observed_state=ConveyorState.IDLE,
            speed=0,
            message="Conveyor successfully reset to IDLE state",
        )

    def get_telemetry(self) -> Dict[str, Any]:
        """Generate telemetry payload conforming strictly to contracts/v1/schemas/telemetry.schema.json."""
        self.sensors.update_digital_bitmask()
        return {
            "device_id": self.device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": self._state.value,
            "speed": self._current_speed,
            "sensors": {
                "temperature_centi_c": self.sensors.temperature_centi_c,
                "humidity_centi_percent": self.sensors.humidity_centi_percent,
                "digital_inputs": self.sensors.digital_inputs,
            },
            "uptime": self.uptime_ms,
        }
