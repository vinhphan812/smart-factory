"""Unit and simulation tests for the Conveyor Belt adapter (Issue #22).

Evidence level: L1 (Unit tests) & L2 (Software simulation).
Verifies:
- FSM state transitions & speed bounds.
- Explicit 'is not None' correlation ID handling (including command_id = 0 and type isolation).
- Payload-bound idempotency cache rejecting conflicting command reuse.
- Strict separation between physical hardware E-Stop and software/jam interlock reset (ADR-0006).
"""

import time
import pytest

from adapters.conveyor import ConveyorAdapter
from models import ConveyorLimits, ConveyorSensors, ConveyorState, EStopSource


@pytest.fixture
def adapter() -> ConveyorAdapter:
    """Fixture providing a clean ConveyorAdapter instance."""
    limits = ConveyorLimits(min_speed=10, max_speed=100, default_speed=50)
    sensors = ConveyorSensors()
    return ConveyorAdapter(device_id="conveyor-01", limits=limits, sensors=sensors)


# ---------------------------------------------------------------------------
# Finding (1): Correlation ID extraction with explicit 'is not None' & command_id=0
# ---------------------------------------------------------------------------
def test_finding1_numeric_command_id_zero_is_not_treated_as_missing(adapter: ConveyorAdapter):
    """command_id=0 must NOT be treated as falsy/missing."""
    cmd = {
        "command_id": 0,
        "command_name": "CONVEYOR_START",
        "arguments": ["60"],
    }
    result = adapter.handle_command(cmd)

    assert result.status == "acknowledged"
    assert result.command_id == 0
    assert result.observed_state == ConveyorState.RUNNING
    assert adapter.state == ConveyorState.RUNNING


def test_finding1_type_isolation_int_zero_vs_str_zero(adapter: ConveyorAdapter):
    """Integer command_id=0 and string request_id='0' are isolated by type in cache."""
    # First issue with integer command_id = 0
    cmd1 = {
        "command_id": 0,
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    }
    res1 = adapter.handle_command(cmd1)
    assert res1.status == "acknowledged"
    assert res1.duplicate is False

    # Issue with string request_id = "0"
    cmd2 = {
        "request_id": "0",
        "command_name": "CONVEYOR_START",
        "arguments": ["70"],
    }
    res2 = adapter.handle_command(cmd2)
    assert res2.status == "acknowledged"
    assert res2.duplicate is False
    assert res2.speed == 70


def test_finding1_negative_command_id_rejected(adapter: ConveyorAdapter):
    """Negative integer command_id is rejected fail-closed."""
    cmd = {
        "command_id": -5,
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    }
    result = adapter.handle_command(cmd)
    assert result.status == "rejected"
    assert result.error_code == "INVALID_CORRELATION_ID"


def test_finding1_missing_correlation_id_rejected(adapter: ConveyorAdapter):
    """Command with neither command_id nor request_id is rejected."""
    cmd = {
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    }
    result = adapter.handle_command(cmd)
    assert result.status == "rejected"
    assert result.error_code == "MISSING_CORRELATION_ID"


# ---------------------------------------------------------------------------
# Finding (2): Idempotency with payload binding & conflicting reuse rejection
# ---------------------------------------------------------------------------
def test_finding2_exact_payload_returns_idempotent_duplicate(adapter: ConveyorAdapter):
    """Replaying exact same command_id with identical command_name and arguments returns duplicate=True."""
    cmd = {
        "command_id": 101,
        "command_name": "CONVEYOR_START",
        "arguments": ["60"],
    }
    res1 = adapter.handle_command(cmd)
    assert res1.status == "acknowledged"
    assert res1.duplicate is False

    res2 = adapter.handle_command(cmd)
    assert res2.status == "acknowledged"
    assert res2.duplicate is True
    assert res2.speed == 60


def test_finding2_conflicting_arguments_reuse_rejected(adapter: ConveyorAdapter):
    """Reusing same command_id with DIFFERENT arguments must be rejected as conflicting."""
    cmd1 = {
        "command_id": 102,
        "command_name": "CONVEYOR_START",
        "arguments": ["40"],
    }
    res1 = adapter.handle_command(cmd1)
    assert res1.status == "acknowledged"

    # Conflicting reuse: same command_id 102, but speed changed to 80
    cmd2 = {
        "command_id": 102,
        "command_name": "CONVEYOR_START",
        "arguments": ["80"],
    }
    res2 = adapter.handle_command(cmd2)
    assert res2.status == "rejected"
    assert res2.error_code == "CONFLICTING_COMMAND_REUSE"
    # Adapter speed remains at original 40, not overwritten by conflicting reuse
    assert adapter.current_speed == 40


def test_finding2_conflicting_command_name_reuse_rejected(adapter: ConveyorAdapter):
    """Reusing same command_id with a completely different command_name is rejected."""
    cmd1 = {
        "command_id": 103,
        "command_name": "CONVEYOR_START",
        "arguments": ["60"],
    }
    res1 = adapter.handle_command(cmd1)
    assert res1.status == "acknowledged"

    # Conflicting reuse: same command_id 103, but command_name is CONVEYOR_STOP
    cmd2 = {
        "command_id": 103,
        "command_name": "CONVEYOR_STOP",
    }
    res2 = adapter.handle_command(cmd2)
    assert res2.status == "rejected"
    assert res2.error_code == "CONFLICTING_COMMAND_REUSE"
    # Conveyor must still be running
    assert adapter.state == ConveyorState.RUNNING


# ---------------------------------------------------------------------------
# Finding (3): Physical Hardware E-Stop vs Software/Jam Interlock Reset
# ---------------------------------------------------------------------------
def test_finding3_software_reset_cannot_clear_physical_estop(adapter: ConveyorAdapter):
    """A network RESET command must NOT clear a physical hardware E-Stop (ADR-0006)."""
    # Start conveyor
    adapter.handle_command({
        "command_id": 201,
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    })
    assert adapter.state == ConveyorState.RUNNING

    # Physical E-Stop button pressed
    adapter.update_sensors(physical_estop_button=True)
    assert adapter.state == ConveyorState.E_STOP
    assert adapter.estop_source == EStopSource.PHYSICAL_HARDWARE
    assert adapter.current_speed == 0

    # Attempt to reset via software network command while physical button is still engaged
    reset_res = adapter.handle_command({
        "command_id": 202,
        "command_name": "RESET",
    })
    assert reset_res.status == "rejected"
    assert reset_res.error_code == "PHYSICAL_ESTOP_ACTIVE"
    assert adapter.state == ConveyorState.E_STOP

    # Even after physical button is released, manual on-site reset must be registered before software reset
    adapter.update_sensors(physical_estop_button=False)
    # estop_source remains PHYSICAL_HARDWARE until explicit technician clear
    reset_res2 = adapter.handle_command({
        "command_id": 203,
        "command_name": "RESET",
    })
    assert reset_res2.status == "rejected"
    assert reset_res2.error_code == "PHYSICAL_ESTOP_ACTIVE"


def test_finding3_jam_interlock_resets_only_when_cleared(adapter: ConveyorAdapter):
    """Software/sensor jam interlock can be reset once the physical jam obstruction is cleared."""
    adapter.handle_command({
        "command_id": 301,
        "command_name": "CONVEYOR_START",
        "arguments": ["60"],
    })

    # Sensor trips on jam obstruction
    adapter.update_sensors(jam_sensor=True)
    assert adapter.state == ConveyorState.E_STOP
    assert adapter.estop_source == EStopSource.JAM_SENSOR

    # Reset attempted while obstruction still present
    res_fail = adapter.handle_command({
        "command_id": 302,
        "command_name": "RESET",
    })
    assert res_fail.status == "rejected"
    assert res_fail.error_code == "JAM_OBSTRUCTION_PRESENT"
    assert adapter.state == ConveyorState.E_STOP

    # Obstruction physically removed / sensor cleared
    adapter.update_sensors(jam_sensor=False)
    res_ok = adapter.handle_command({
        "command_id": 303,
        "command_name": "RESET",
    })
    assert res_ok.status == "acknowledged"
    assert res_ok.observed_state == ConveyorState.IDLE
    assert adapter.state == ConveyorState.IDLE
    assert adapter.estop_source == EStopSource.NONE


# ---------------------------------------------------------------------------
# Core Speed Bounds & Normal Transitions
# ---------------------------------------------------------------------------
def test_speed_bounds_enforcement(adapter: ConveyorAdapter):
    """Speed bounds (10 - 100) are enforced."""
    # Over max
    res_high = adapter.handle_command({
        "command_id": 401,
        "command_name": "CONVEYOR_START",
        "arguments": ["120"],
    })
    assert res_high.status == "rejected"
    assert res_high.error_code == "SPEED_EXCEEDS_MAX"

    # Below min
    res_low = adapter.handle_command({
        "command_id": 402,
        "command_name": "CONVEYOR_START",
        "arguments": ["5"],
    })
    assert res_low.status == "rejected"
    assert res_low.error_code == "SPEED_BELOW_MIN"

    # Negative
    res_neg = adapter.handle_command({
        "command_id": 403,
        "command_name": "CONVEYOR_START",
        "arguments": ["-10"],
    })
    assert res_neg.status == "rejected"
    assert res_neg.error_code == "NEGATIVE_SPEED_NOT_ALLOWED"

    # Invalid non-numeric string
    res_nan = adapter.handle_command({
        "command_id": 404,
        "command_name": "CONVEYOR_START",
        "arguments": ["warp_speed"],
    })
    assert res_nan.status == "rejected"
    assert res_nan.error_code == "INVALID_SPEED_FORMAT"


def test_normal_stop_transition(adapter: ConveyorAdapter):
    """CONVEYOR_STOP transitions RUNNING -> STOPPED with speed 0."""
    adapter.handle_command({
        "command_id": 501,
        "command_name": "CONVEYOR_START",
        "arguments": ["75"],
    })
    assert adapter.state == ConveyorState.RUNNING

    stop_res = adapter.handle_command({
        "command_id": 502,
        "command_name": "CONVEYOR_STOP",
    })
    assert stop_res.status == "acknowledged"
    assert stop_res.observed_state == ConveyorState.STOPPED
    assert adapter.current_speed == 0


def test_telemetry_schema_and_digital_inputs(adapter: ConveyorAdapter):
    """Telemetry payload conforms to schema with bitmask updates."""
    # Bit 0: entry, Bit 1: exit, Bit 2: jam, Bit 3: physical estop
    adapter.update_sensors(
        optical_entry=True,
        optical_exit=True,
        jam_sensor=False,
        physical_estop_button=False,
    )
    tel = adapter.get_telemetry()
    assert tel["device_id"] == "conveyor-01"
    assert tel["state"] == "IDLE"
    assert tel["speed"] == 0
    assert tel["sensors"]["digital_inputs"] == 3  # 0b0011 (entry + exit)
    assert "timestamp" in tel
    assert isinstance(tel["uptime"], int)


def test_ping_command(adapter: ConveyorAdapter):
    """PING returns pong without modifying state."""
    res = adapter.handle_command({
        "command_id": 601,
        "command_name": "PING",
    })
    assert res.status == "acknowledged"
    assert res.message == "pong"


def test_unknown_command_rejected(adapter: ConveyorAdapter):
    """Unknown command is rejected fail-closed."""
    res = adapter.handle_command({
        "command_id": 701,
        "command_name": "TELEPORT",
    })
    assert res.status == "rejected"
    assert res.error_code == "UNKNOWN_COMMAND"
