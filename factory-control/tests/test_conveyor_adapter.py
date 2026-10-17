"""Unit and simulation tests for the Conveyor Belt adapter (Issue #22).

Evidence level: L1 (Unit tests) & L2 (Software simulation).
"""

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
# TC1: Start at allowed speed succeeds
# ---------------------------------------------------------------------------
def test_tc1_start_at_allowed_speed_succeeds(adapter: ConveyorAdapter):
    """TC1: Start at allowed speed transitions to RUNNING and sets speed."""
    cmd = {
        "command_id": 101,
        "command_name": "CONVEYOR_START",
        "arguments": ["60"],
    }
    result = adapter.handle_command(cmd)

    assert result.status == "acknowledged"
    assert result.observed_state == ConveyorState.RUNNING
    assert result.speed == 60
    assert adapter.state == ConveyorState.RUNNING
    assert adapter.current_speed == 60

    # Verify telemetry
    telemetry = adapter.get_telemetry()
    assert telemetry["device_id"] == "conveyor-01"
    assert telemetry["state"] == "RUNNING"
    assert telemetry["speed"] == 60
    assert "timestamp" in telemetry
    assert "sensors" in telemetry
    assert isinstance(telemetry["uptime"], int)


def test_tc1_start_default_speed_when_no_arguments(adapter: ConveyorAdapter):
    """Start without arguments uses default speed."""
    cmd = {
        "command_id": 102,
        "command_name": "CONVEYOR_START",
        "arguments": [],
    }
    result = adapter.handle_command(cmd)

    assert result.status == "acknowledged"
    assert result.observed_state == ConveyorState.RUNNING
    assert result.speed == 50  # default speed


def test_command_id_zero_is_not_treated_as_missing(adapter: ConveyorAdapter):
    """command_id=0 must not be silently discarded (0 is a valid integer)."""
    cmd = {
        "command_id": 0,
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    }
    result = adapter.handle_command(cmd)
    assert result.status == "acknowledged"
    assert result.command_id == 0


# ---------------------------------------------------------------------------
# TC2: Out-of-range speed rejected
# ---------------------------------------------------------------------------
def test_tc2_speed_exceeds_max_rejected(adapter: ConveyorAdapter):
    """Speed > max_speed is rejected fail-closed; state remains unchanged."""
    cmd = {
        "command_id": 201,
        "command_name": "CONVEYOR_START",
        "arguments": ["150"],  # max is 100
    }
    result = adapter.handle_command(cmd)

    assert result.status == "rejected"
    assert result.error_code == "SPEED_EXCEEDS_MAX"
    assert adapter.state == ConveyorState.IDLE
    assert adapter.current_speed == 0


def test_tc2_speed_below_min_rejected(adapter: ConveyorAdapter):
    """Speed < min_speed (and > 0) is rejected fail-closed."""
    cmd = {
        "command_id": 202,
        "command_name": "CONVEYOR_START",
        "arguments": ["5"],  # min is 10
    }
    result = adapter.handle_command(cmd)

    assert result.status == "rejected"
    assert result.error_code == "SPEED_BELOW_MIN"
    assert adapter.state == ConveyorState.IDLE
    assert adapter.current_speed == 0


def test_tc2_negative_speed_rejected(adapter: ConveyorAdapter):
    """Negative speeds are rejected."""
    cmd = {
        "command_id": 203,
        "command_name": "CONVEYOR_START",
        "arguments": ["-30"],
    }
    result = adapter.handle_command(cmd)

    assert result.status == "rejected"
    assert result.error_code == "NEGATIVE_SPEED_NOT_ALLOWED"
    assert adapter.state == ConveyorState.IDLE


def test_tc2_invalid_speed_format_rejected(adapter: ConveyorAdapter):
    """Non-numeric speed string is rejected."""
    cmd = {
        "command_id": 204,
        "command_name": "CONVEYOR_START",
        "arguments": ["fast"],
    }
    result = adapter.handle_command(cmd)

    assert result.status == "rejected"
    assert result.error_code == "INVALID_SPEED_FORMAT"
    assert adapter.state == ConveyorState.IDLE


# ---------------------------------------------------------------------------
# TC3: Repeated command ID is idempotent (payload-bound)
# ---------------------------------------------------------------------------
def test_tc3_repeated_command_id_is_idempotent(adapter: ConveyorAdapter):
    """Sending the exact same command_id returns duplicate cached result."""
    cmd = {
        "command_id": 301,
        "command_name": "CONVEYOR_START",
        "arguments": ["40"],
    }
    res1 = adapter.handle_command(cmd)
    assert res1.status == "acknowledged"
    assert res1.duplicate is False

    # Second invocation with same command_id
    res2 = adapter.handle_command(cmd)
    assert res2.status == "acknowledged"
    assert res2.duplicate is True
    assert res2.observed_state == ConveyorState.RUNNING
    assert res2.speed == 40


def test_tc3_string_request_id_supported(adapter: ConveyorAdapter):
    """UUID-based or string request_id is also deduplicated."""
    cmd = {
        "request_id": "req-uuid-abc-123",
        "command_name": "CONVEYOR_START",
        "arguments": ["70"],
    }
    res1 = adapter.handle_command(cmd)
    assert res1.status == "acknowledged"
    assert res1.duplicate is False

    res2 = adapter.handle_command(cmd)
    assert res2.status == "acknowledged"
    assert res2.duplicate is True


def test_conflicting_payload_reuse_rejected(adapter: ConveyorAdapter):
    """Same command_id with different arguments is rejected as conflicting."""
    cmd1 = {
        "command_id": 202,
        "command_name": "CONVEYOR_START",
        "arguments": ["40"],
    }
    adapter.handle_command(cmd1)

    cmd2 = {
        "command_id": 202,
        "command_name": "CONVEYOR_START",
        "arguments": ["80"],
    }
    res2 = adapter.handle_command(cmd2)
    assert res2.status == "rejected"
    assert res2.error_code == "CONFLICTING_COMMAND_REUSE"


# ---------------------------------------------------------------------------
# TC4: Jam sensor triggers immediate local E-Stop
# ---------------------------------------------------------------------------
def test_tc4_jam_sensor_triggers_immediate_estop(adapter: ConveyorAdapter):
    """When running, jam sensor trigger causes immediate local E-Stop."""
    adapter.handle_command({
        "command_id": 401,
        "command_name": "CONVEYOR_START",
        "arguments": ["60"],
    })
    assert adapter.state == ConveyorState.RUNNING
    assert adapter.current_speed == 60

    adapter.update_sensors(jam_sensor=True)

    assert adapter.state == ConveyorState.E_STOP
    assert adapter.current_speed == 0

    res = adapter.handle_command({
        "command_id": 402,
        "command_name": "CONVEYOR_START",
        "arguments": ["60"],
    })
    assert res.status == "rejected"
    assert res.error_code == "CANNOT_START_IN_ESTOP"


def test_physical_estop_cannot_be_cleared_by_software_reset(adapter: ConveyorAdapter):
    """Physical E-stop cannot be cleared by network RESET command."""
    adapter.handle_command({
        "command_id": 301,
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    })
    adapter.update_sensors(physical_estop_button=True)
    assert adapter.state == ConveyorState.E_STOP
    assert adapter.estop_source == EStopSource.PHYSICAL_HARDWARE

    res = adapter.handle_command({
        "command_id": 302,
        "command_name": "RESET",
    })
    assert res.status == "rejected"
    assert res.error_code == "PHYSICAL_ESTOP_ACTIVE"


# ---------------------------------------------------------------------------
# TC5: Reset behavior & obstruction check
# ---------------------------------------------------------------------------
def test_tc5_reset_rejected_if_jam_sensor_still_active(adapter: ConveyorAdapter):
    """Reset is refused if physical jam obstruction is still detected."""
    adapter.emergency_stop(reason="Test E-Stop")
    adapter.update_sensors(jam_sensor=True)

    res = adapter.handle_command({
        "command_id": 501,
        "command_name": "RESET",
    })
    assert res.status == "rejected"
    assert res.error_code == "JAM_OBSTRUCTION_PRESENT"
    assert adapter.state == ConveyorState.E_STOP


def test_tc5_reset_succeeds_when_cleared(adapter: ConveyorAdapter):
    """Reset succeeds once jam sensor is cleared, returning state to IDLE."""
    adapter.emergency_stop(reason="Test E-Stop")
    adapter.update_sensors(jam_sensor=False)

    res = adapter.handle_command({
        "command_id": 502,
        "command_name": "RESET",
    })
    assert res.status == "acknowledged"
    assert res.observed_state == ConveyorState.IDLE
    assert adapter.state == ConveyorState.IDLE
    assert adapter.current_speed == 0


def test_jam_interlock_and_reset(adapter: ConveyorAdapter):
    """Reset refused while jam active; succeeds once cleared."""
    adapter.handle_command({
        "command_id": 401,
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    })
    adapter.update_sensors(jam_sensor=True)
    assert adapter.state == ConveyorState.E_STOP

    res_fail = adapter.handle_command({"command_id": 402, "command_name": "RESET"})
    assert res_fail.status == "rejected"

    adapter.update_sensors(jam_sensor=False)
    res_ok = adapter.handle_command({"command_id": 403, "command_name": "RESET"})
    assert res_ok.status == "acknowledged"
    assert adapter.state == ConveyorState.IDLE


# ---------------------------------------------------------------------------
# TC6: Normal stop
# ---------------------------------------------------------------------------
def test_tc6_normal_stop(adapter: ConveyorAdapter):
    """CONVEYOR_STOP stops the conveyor and sets speed to 0."""
    adapter.handle_command({
        "command_id": 601,
        "command_name": "CONVEYOR_START",
        "arguments": ["80"],
    })
    assert adapter.state == ConveyorState.RUNNING

    stop_res = adapter.handle_command({
        "command_id": 602,
        "command_name": "CONVEYOR_STOP",
    })
    assert stop_res.status == "acknowledged"
    assert stop_res.observed_state == ConveyorState.STOPPED
    assert stop_res.speed == 0
    assert adapter.state == ConveyorState.STOPPED
    assert adapter.current_speed == 0


def test_tc6_speed_zero_triggers_stop(adapter: ConveyorAdapter):
    """Starting with speed 0 is treated as a stop request."""
    adapter.handle_command({
        "command_id": 603,
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    })
    res = adapter.handle_command({
        "command_id": 604,
        "command_name": "CONVEYOR_START",
        "arguments": ["0"],
    })
    assert res.status == "acknowledged"
    assert res.observed_state == ConveyorState.STOPPED
    assert adapter.current_speed == 0


def test_normal_stop(adapter: ConveyorAdapter):
    """CONVEYOR_STOP transitions to STOPPED state."""
    adapter.handle_command({"command_id": 501, "command_name": "CONVEYOR_START", "arguments": ["60"]})
    assert adapter.state == ConveyorState.RUNNING
    res = adapter.handle_command({"command_id": 502, "command_name": "CONVEYOR_STOP"})
    assert res.status == "acknowledged"
    assert adapter.state == ConveyorState.STOPPED


# ---------------------------------------------------------------------------
# TC7: Telemetry & digital inputs bitmask
# ---------------------------------------------------------------------------
def test_tc7_digital_inputs_bitmask(adapter: ConveyorAdapter):
    """Verify bitmask encoding: Bit 0 = entry, Bit 1 = exit, Bit 2 = jam."""
    adapter.update_sensors(optical_entry=True, optical_exit=False, jam_sensor=False)
    tel1 = adapter.get_telemetry()
    assert tel1["sensors"]["digital_inputs"] == 1  # 0b001

    adapter.update_sensors(optical_entry=False, optical_exit=True, jam_sensor=False)
    tel2 = adapter.get_telemetry()
    assert tel2["sensors"]["digital_inputs"] == 2  # 0b010

    adapter.update_sensors(optical_entry=True, optical_exit=True, jam_sensor=False)
    tel3 = adapter.get_telemetry()
    assert tel3["sensors"]["digital_inputs"] == 3  # 0b011

    adapter.update_sensors(optical_entry=True, optical_exit=True, jam_sensor=True)
    tel4 = adapter.get_telemetry()
    assert tel4["sensors"]["digital_inputs"] == 7  # 0b111


# ---------------------------------------------------------------------------
# TC8: Edge cases & Listener notifications
# ---------------------------------------------------------------------------
def test_tc8_ping_command(adapter: ConveyorAdapter):
    """PING command returns status acknowledged and pong message."""
    res = adapter.handle_command({
        "command_id": 801,
        "command_name": "PING",
    })
    assert res.status == "acknowledged"
    assert res.message == "pong"


def test_tc8_missing_correlation_id(adapter: ConveyorAdapter):
    """Missing correlation id is rejected."""
    res = adapter.handle_command({
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    })
    assert res.status == "rejected"
    assert res.error_code == "MISSING_CORRELATION_ID"


def test_tc8_unknown_command(adapter: ConveyorAdapter):
    """Unknown command is rejected."""
    res = adapter.handle_command({
        "command_id": 802,
        "command_name": "FLY_TO_MOON",
    })
    assert res.status == "rejected"
    assert res.error_code == "UNKNOWN_COMMAND"


def test_tc8_state_and_telemetry_listeners(adapter: ConveyorAdapter):
    """Listeners are notified on state changes and telemetry emissions."""
    state_transitions = []
    telemetries = []

    adapter.register_state_listener(lambda dev, old, new: state_transitions.append((old, new)))
    adapter.register_telemetry_listener(lambda tel: telemetries.append(tel))

    adapter.handle_command({
        "command_id": 803,
        "command_name": "CONVEYOR_START",
        "arguments": ["60"],
    })

    assert len(state_transitions) >= 2  # IDLE -> STARTING -> RUNNING
    assert ("STARTING", "RUNNING") in state_transitions
    assert len(telemetries) >= 1
    assert telemetries[-1]["state"] == "RUNNING"
