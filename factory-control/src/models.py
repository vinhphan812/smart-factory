"""Data models, enums, and safety contracts for Factory Control."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field


class ConveyorState(str, Enum):
    """Finite State Machine states for the Conveyor Belt module."""
    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAULT = "FAULT"
    E_STOP = "E_STOP"


class EStopSource(str, Enum):
    """Discriminator for Emergency Stop source.
    
    Distinguishes software/sensor-triggered interlocks from physical hardware E-Stop (ADR-0006).
    Software network resets MUST NOT clear physical E-Stops.
    """
    NONE = "NONE"
    SOFTWARE = "SOFTWARE"              # Programmatic or operator network E-Stop command
    JAM_SENSOR = "JAM_SENSOR"          # Optical/mechanical jam detection interlock
    PHYSICAL_HARDWARE = "PHYSICAL_HARDWARE"  # Physical push-button / hardware safety relay


class ConveyorSensors(BaseModel):
    """Raw and processed sensor readings for the Conveyor Belt."""
    optical_entry: bool = Field(default=False, description="Entry photoelectric sensor")
    optical_exit: bool = Field(default=False, description="Exit photoelectric sensor")
    jam_sensor: bool = Field(default=False, description="Optical or mechanical jam detection sensor")
    physical_estop_button: bool = Field(
        default=False,
        description="Physical emergency stop button/relay state (True = engaged/open-circuit)"
    )
    temperature_centi_c: int = Field(default=2500, description="Temperature in hundredths of °C (25.00°C)")
    humidity_centi_percent: int = Field(default=5000, description="Relative humidity in hundredths of % (50.00%)")
    digital_inputs: int = Field(default=0, description="16-bit digital input bitmask")

    def update_digital_bitmask(self) -> int:
        """Update and return the 16-bit digital inputs bitmask.
        Bit 0: Optical entry
        Bit 1: Optical exit
        Bit 2: Jam sensor
        Bit 3: Physical E-Stop button
        """
        mask = 0
        if self.optical_entry:
            mask |= 1 << 0
        if self.optical_exit:
            mask |= 1 << 1
        if self.jam_sensor:
            mask |= 1 << 2
        if self.physical_estop_button:
            mask |= 1 << 3
        self.digital_inputs = mask
        return mask


class ConveyorLimits(BaseModel):
    """Configurable physical and safety limits for the Conveyor Belt."""
    min_speed: int = Field(default=10, description="Minimum allowable non-zero operating speed (mm/s or %)")
    max_speed: int = Field(default=100, description="Maximum allowable operating speed (mm/s or %)")
    default_speed: int = Field(default=50, description="Default operating speed if unspecified")
    acceleration_step_time_s: float = Field(default=0.05, description="Simulated acceleration step duration")
    watchdog_timeout_s: float = Field(default=300.0, description="Maximum continuous run duration before timeout")


class CommandResult(BaseModel):
    """Unified result payload for a command execution."""
    command_id: Union[int, str] = Field(description="Correlation ID of the command")
    status: str = Field(description="Execution status (acknowledged, rejected, failed, duplicate)")
    observed_state: ConveyorState = Field(description="Current state of the conveyor after processing")
    speed: int = Field(default=0, description="Observed speed after processing")
    error_code: Optional[str] = Field(default=None, description="Error code if rejected or failed")
    message: Optional[str] = Field(default=None, description="Human-readable detail message")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp"
    )
    duplicate: bool = Field(default=False, description="Whether this command was a duplicate replay")


class CachedCommand(BaseModel):
    """Cached command entry for idempotency verification with payload binding."""
    command_id: Union[int, str]
    id_type: str  # "int" or "str" to avoid cross-type collisions
    command_name: str
    arguments: List[str]
    result: CommandResult
    created_at: float  # monotonic time
