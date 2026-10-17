"""Unit and simulation tests for the Conveyor Belt adapter (Issue #22)."""

import pytest

from adapters.conveyor import ConveyorAdapter
from models import ConveyorLimits, ConveyorSensors, ConveyorState, EStopSource


@pytest.fixture
def adapter() -> ConveyorAdapter:
    limits = ConveyorLimits(min_speed=10, max_speed=100, default_speed=50)
    sensors = ConveyorSensors()
    return ConveyorAdapter(device_id="conveyor-01", limits=limits, sensors=sensors)


def test_start_at_allowed_speed_succeeds(adapter: ConveyorAdapter):
    cmd = {
        "command_id": 101,
        "command_name": "CONVEYOR_START",
        "arguments": ["60"],
    }
    result = adapter.handle_command(cmd)
    assert result.status == "acknowledged"
    assert result.observed_state == ConveyorState.RUNNING
    assert result.speed == 60


def test_command_id_zero_is_not_treated_as_missing(adapter: ConveyorAdapter):
    cmd = {
        "command_id": 0,
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    }
    result = adapter.handle_command(cmd)
    assert result.status == "acknowledged"
    assert result.command_id == 0


def test_exact_payload_returns_idempotent_duplicate(adapter: ConveyorAdapter):
    cmd = {
        "command_id": 201,
        "command_name": "CONVEYOR_START",
        "arguments": ["40"],
    }
    res1 = adapter.handle_command(cmd)
    assert res1.status == "acknowledged"
    assert res1.duplicate is False

    res2 = adapter.handle_command(cmd)
    assert res2.status == "acknowledged"
    assert res2.duplicate is True


def test_conflicting_payload_reuse_rejected(adapter: ConveyorAdapter):
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


def test_physical_estop_cannot_be_cleared_by_software_reset(adapter: ConveyorAdapter):
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


def test_jam_interlock_and_reset(adapter: ConveyorAdapter):
    adapter.handle_command({
        "command_id": 401,
        "command_name": "CONVEYOR_START",
        "arguments": ["50"],
    })
    adapter.update_sensors(jam_sensor=True)
    assert adapter.state == ConveyorState.E_STOP

    # Reset refused while jam still active
    res_fail = adapter.handle_command({"command_id": 402, "command_name": "RESET"})
    assert res_fail.status == "rejected"

    # Reset succeeds when jam removed
    adapter.update_sensors(jam_sensor=False)
    res_ok = adapter.handle_command({"command_id": 403, "command_name": "RESET"})
    assert res_ok.status == "acknowledged"
    assert adapter.state == ConveyorState.IDLE


def test_normal_stop(adapter: ConveyorAdapter):
    adapter.handle_command({"command_id": 501, "command_name": "CONVEYOR_START", "arguments": ["60"]})
    assert adapter.state == ConveyorState.RUNNING
    res = adapter.handle_command({"command_id": 502, "command_name": "CONVEYOR_STOP"})
    assert res.status == "acknowledged"
    assert adapter.state == ConveyorState.STOPPED
