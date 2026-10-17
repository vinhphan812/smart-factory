"""Data models, enums, and safety contracts for Factory Control."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field


class EStopSource(str, Enum):
    """Discriminator for Emergency Stop source.
    
    Distinguishes software/sensor-triggered interlocks from physical hardware E-Stop (ADR-0006).
    Software network resets MUST NOT clear physical E-Stops.
    """
    NONE = "NONE"
    SOFTWARE = "SOFTWARE"                    # Programmatic or operator network E-Stop command
    JAM_SENSOR = "JAM_SENSOR"                # Optical/mechanical jam detection interlock
    SENSOR_LOSS = "SENSOR_LOSS"              # Sensor heartbeat timeout / cable disconnect
    PHYSICAL_HARDWARE = "PHYSICAL_HARDWARE"  # Physical push-button / hardware safety relay


# ---------------------------------------------------------------------------
# Conveyor Module Models (Module 1 - Issue #22)
# ---------------------------------------------------------------------------
class ConveyorState(str, Enum):
    """Finite State Machine states for the Conveyor Belt module."""
    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAULT = "FAULT"
    E_STOP = "E_STOP"


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
        """Update and return the 16-bit digital inputs bitmask."""
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


# ---------------------------------------------------------------------------
# Sorting Module Models (Module 2 - Issue #23)
# ---------------------------------------------------------------------------
class SortingState(str, Enum):
    """Finite State Machine states for the Sorting module."""
    IDLE = "IDLE"
    CLASSIFYING = "CLASSIFYING"
    ROUTING = "ROUTING"
    REJECTING = "REJECTING"
    STOPPED = "STOPPED"
    FAULT = "FAULT"
    E_STOP = "E_STOP"


class ItemClass(str, Enum):
    """Material / classification categories for factory goods."""
    METAL = "METAL"
    PLASTIC = "PLASTIC"
    WOOD = "WOOD"
    DEFECTIVE = "DEFECTIVE"
    UNKNOWN = "UNKNOWN"


class RouteDestination(str, Enum):
    """Physical diverter routing destinations."""
    BIN_1 = "BIN_1"           # Default for METAL
    BIN_2 = "BIN_2"           # Default for PLASTIC
    BIN_3 = "BIN_3"           # Default for WOOD
    REJECT_LANE = "REJECT_LANE"  # Default for UNKNOWN / DEFECTIVE


class SortingSensors(BaseModel):
    """Raw and processed sensor readings for the Sorting module."""
    optical_entry: bool = Field(default=False, description="Inlet optical presence sensor")
    inductive_sensor: bool = Field(default=False, description="Inductive sensor for metal detection")
    color_code: int = Field(default=0, description="Optical color sensor code (0=none, 1=plastic, 2=wood)")
    diverter_position: int = Field(default=0, description="Diverter servo angle (0=center/straight, -45=bin1, 45=bin2, 90=reject)")
    bin_1_sensor: bool = Field(default=False, description="Presence sensor at Bin 1")
    bin_2_sensor: bool = Field(default=False, description="Presence sensor at Bin 2")
    bin_3_sensor: bool = Field(default=False, description="Presence sensor at Bin 3")
    reject_sensor: bool = Field(default=False, description="Presence sensor at Reject lane")
    jam_sensor: bool = Field(default=False, description="Obstruction sensor in sorting/diverter channel")
    physical_estop_button: bool = Field(default=False, description="Physical hardware E-Stop button")
    sensor_alive: bool = Field(default=True, description="Sensor bus health / heartbeat status")
    digital_inputs: int = Field(default=0, description="16-bit digital input bitmask")

    def update_digital_bitmask(self) -> int:
        """Bitmask mapping:
        Bit 0: Optical entry
        Bit 1: Inductive (Metal)
        Bit 2: Jam sensor
        Bit 3: Physical E-Stop button
        Bit 4: Bin 1 sensor
        Bit 5: Bin 2 sensor
        Bit 6: Bin 3 sensor
        Bit 7: Reject sensor
        Bit 8: Sensor bus healthy
        """
        mask = 0
        if self.optical_entry:
            mask |= 1 << 0
        if self.inductive_sensor:
            mask |= 1 << 1
        if self.jam_sensor:
            mask |= 1 << 2
        if self.physical_estop_button:
            mask |= 1 << 3
        if self.bin_1_sensor:
            mask |= 1 << 4
        if self.bin_2_sensor:
            mask |= 1 << 5
        if self.bin_3_sensor:
            mask |= 1 << 6
        if self.reject_sensor:
            mask |= 1 << 7
        if self.sensor_alive:
            mask |= 1 << 8
        self.digital_inputs = mask
        return mask


class SortingCounts(BaseModel):
    """Production accounting counts for sorted goods."""
    total_processed: int = 0
    bin_1_count: int = 0
    bin_2_count: int = 0
    bin_3_count: int = 0
    reject_count: int = 0
    duplicate_item_events_ignored: int = 0


# ---------------------------------------------------------------------------
# Common Command & Result Models
# ---------------------------------------------------------------------------
class CommandResult(BaseModel):
    """Unified result payload for a command execution."""
    command_id: Union[int, str] = Field(description="Correlation ID of the command")
    status: str = Field(description="Execution status (acknowledged, rejected, failed, duplicate)")
    observed_state: Union[ConveyorState, SortingState, str] = Field(description="Current state of module after processing")
    speed: int = Field(default=0, description="Observed speed or actuator metric")
    error_code: Optional[str] = Field(default=None, description="Error code if rejected or failed")
    message: Optional[str] = Field(default=None, description="Human-readable detail message")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp"
    )
    duplicate: bool = Field(default=False, description="Whether this command was a duplicate replay")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Optional command-specific response payload")


class CachedCommand(BaseModel):
    """Cached command entry for idempotency verification with payload binding."""
    command_id: Union[int, str]
    id_type: str  # "int" or "str" to avoid cross-type collisions
    command_name: str
    arguments: List[str]
    result: CommandResult
    created_at: float  # monotonic time
