"""Unit and simulation tests for the Sorting module adapter (Issue #23).

Evidence level: L1 (Unit tests) & L2 (Software simulation).
Verifies:
- TC1: Correct class routes to bin (METAL -> BIN_1, PLASTIC -> BIN_2, WOOD -> BIN_3)
- TC2: Unknown class enters reject (UNKNOWN / DEFECTIVE -> REJECT_LANE)
- TC3: Duplicate item event counted once
- TC4: Jam stops movement (fail-closed E-Stop)
- TC5: Loss of sensor yields alarm / FAULT state
- TC6: Physical hardware E-Stop vs software reset authority (ADR-0006)
- TC7: Payload-bound command idempotency & conflict rejection
- TC8: Telemetry compliance
"""

import pytest

from adapters.sorting import SortingAdapter
from models import (
    CommandResult,
    EStopSource,
    ItemClass,
    RouteDestination,
    SortingSensors,
    SortingState,
)


@pytest.fixture
def adapter() -> SortingAdapter:
    """Fixture providing a clean SortingAdapter instance."""
    sensors = SortingSensors()
    return SortingAdapter(device_id="sorter-01", sensors=sensors)


# ---------------------------------------------------------------------------
# TC1: Correct class routes to bin
# ---------------------------------------------------------------------------
def test_tc1_metal_routes_to_bin_1(adapter: SortingAdapter):
    """METAL item is routed to BIN_1 and bin_1_count increments."""
    cmd = {
        "command_id": 101,
        "command_name": "SORT_ITEM",
        "arguments": ["item-metal-01", "METAL"],
    }
    result = adapter.handle_command(cmd)

    assert result.status == "acknowledged"
    assert result.observed_state == SortingState.IDLE
    assert result.data["destination"] == RouteDestination.BIN_1.value
    assert result.data["item_class"] == ItemClass.METAL.value
    assert adapter.counts.bin_1_count == 1
    assert adapter.counts.total_processed == 1


def test_tc1_plastic_routes_to_bin_2(adapter: SortingAdapter):
    """PLASTIC item is routed to BIN_2 and bin_2_count increments."""
    cmd = {
        "command_id": 102,
        "command_name": "SORT_ITEM",
        "arguments": ["item-plastic-01", "PLASTIC"],
    }
    result = adapter.handle_command(cmd)

    assert result.status == "acknowledged"
    assert result.data["destination"] == RouteDestination.BIN_2.value
    assert adapter.counts.bin_2_count == 1
    assert adapter.counts.total_processed == 1


def test_tc1_wood_routes_to_bin_3(adapter: SortingAdapter):
    """WOOD item is routed to BIN_3 and bin_3_count increments."""
    cmd = {
        "command_id": 103,
        "command_name": "SORT_ITEM",
        "arguments": ["item-wood-01", "WOOD"],
    }
    result = adapter.handle_command(cmd)

    assert result.status == "acknowledged"
    assert result.data["destination"] == RouteDestination.BIN_3.value
    assert adapter.counts.bin_3_count == 1
    assert adapter.counts.total_processed == 1


def test_tc1_sensor_based_auto_classification(adapter: SortingAdapter):
    """When class argument is omitted, hardware sensors auto-classify the item."""
    # Inductive sensor triggers metal detection
    adapter.update_sensors(inductive_sensor=True)
    cmd = {
        "command_id": 104,
        "command_name": "SORT_ITEM",
        "arguments": ["item-auto-01"],
    }
    result = adapter.handle_command(cmd)
    assert result.status == "acknowledged"
    assert result.data["destination"] == RouteDestination.BIN_1.value


# ---------------------------------------------------------------------------
# TC2: Unknown class enters reject lane
# ---------------------------------------------------------------------------
def test_tc2_unknown_class_enters_reject_lane(adapter: SortingAdapter):
    """UNKNOWN class deterministically routes to REJECT_LANE."""
    cmd = {
        "command_id": 201,
        "command_name": "SORT_ITEM",
        "arguments": ["item-unknown-01", "UNKNOWN"],
    }
    result = adapter.handle_command(cmd)

    assert result.status == "acknowledged"
    assert result.data["destination"] == RouteDestination.REJECT_LANE.value
    assert adapter.counts.reject_count == 1
    assert adapter.counts.total_processed == 1


def test_tc2_defective_and_unrecognized_items_enter_reject(adapter: SortingAdapter):
    """Defective or unclassifiable items route to REJECT_LANE."""
    cmd = {
        "command_id": 202,
        "command_name": "SORT_ITEM",
        "arguments": ["item-broken-01", "DEFECTIVE"],
    }
    result = adapter.handle_command(cmd)
    assert result.data["destination"] == RouteDestination.REJECT_LANE.value
    assert adapter.counts.reject_count == 1


# ---------------------------------------------------------------------------
# TC3: Duplicate item event counted once
# ---------------------------------------------------------------------------
def test_tc3_duplicate_item_counted_once(adapter: SortingAdapter):
    """Processing the exact same item_id again is ignored and counted only once."""
    cmd1 = {
        "command_id": 301,
        "command_name": "SORT_ITEM",
        "arguments": ["part-unique-999", "METAL"],
    }
    res1 = adapter.handle_command(cmd1)
    assert res1.status == "acknowledged"
    assert adapter.counts.total_processed == 1
    assert adapter.counts.bin_1_count == 1

    # Second arrival of the same item ID
    cmd2 = {
        "command_id": 302,
        "command_name": "SORT_ITEM",
        "arguments": ["part-unique-999", "METAL"],
    }
    res2 = adapter.handle_command(cmd2)
    assert res2.status == "acknowledged"
    assert res2.duplicate is True
    # total_processed must STILL be 1! (not 2)
    assert adapter.counts.total_processed == 1
    assert adapter.counts.bin_1_count == 1
    assert adapter.counts.duplicate_item_events_ignored == 1


# ---------------------------------------------------------------------------
# TC4: Jam stops movement (fail-closed E-Stop)
# ---------------------------------------------------------------------------
def test_tc4_jam_sensor_trips_immediate_estop(adapter: SortingAdapter):
    """Jam sensor trigger immediately stops sorter and forces E_STOP state."""
    adapter.update_sensors(jam_sensor=True)

    assert adapter.state == SortingState.E_STOP
    assert adapter.estop_source == EStopSource.JAM_SENSOR

    # Further sorting commands must be rejected fail-closed
    cmd = {
        "command_id": 401,
        "command_name": "SORT_ITEM",
        "arguments": ["item-fail-01", "METAL"],
    }
    result = adapter.handle_command(cmd)
    assert result.status == "rejected"
    assert result.error_code == "CANNOT_SORT_IN_ESTOP"


def test_tc4_jam_interlock_clears_on_reset_after_removal(adapter: SortingAdapter):
    """Reset is rejected while jam is active, but succeeds once obstruction is cleared."""
    adapter.update_sensors(jam_sensor=True)

    # Reset attempted while jam present
    res_fail = adapter.handle_command({"command_id": 402, "command_name": "RESET"})
    assert res_fail.status == "rejected"
    assert res_fail.error_code == "JAM_OBSTRUCTION_PRESENT"

    # Obstruction cleared
    adapter.update_sensors(jam_sensor=False)
    res_ok = adapter.handle_command({"command_id": 403, "command_name": "RESET"})
    assert res_ok.status == "acknowledged"
    assert adapter.state == SortingState.IDLE


# ---------------------------------------------------------------------------
# TC5: Loss of sensor yields alarm and FAULT state
# ---------------------------------------------------------------------------
def test_tc5_loss_of_sensor_yields_fault_alarm(adapter: SortingAdapter):
    """Sensor heartbeat/communication loss transitions sorter to FAULT."""
    adapter.update_sensors(sensor_alive=False)

    assert adapter.state == SortingState.FAULT

    # Commands refused in FAULT state
    cmd = {
        "command_id": 501,
        "command_name": "SORT_ITEM",
        "arguments": ["item-501", "METAL"],
    }
    result = adapter.handle_command(cmd)
    assert result.status == "rejected"
    assert result.error_code == "CANNOT_SORT_IN_FAULT"

    # Reset refused while sensor offline
    res_rst = adapter.handle_command({"command_id": 502, "command_name": "RESET"})
    assert res_rst.status == "rejected"
    assert res_rst.error_code == "SENSOR_LOSS_ACTIVE"

    # Sensor recovers
    adapter.update_sensors(sensor_alive=True)
    res_ok = adapter.handle_command({"command_id": 503, "command_name": "RESET"})
    assert res_ok.status == "acknowledged"
    assert adapter.state == SortingState.IDLE


# ---------------------------------------------------------------------------
# TC6: Physical E-stop vs software reset authority
# ---------------------------------------------------------------------------
def test_tc6_physical_estop_button_cannot_be_cleared_by_software(adapter: SortingAdapter):
    """Physical button press strictly blocks software network RESET (ADR-0006)."""
    adapter.update_sensors(physical_estop_button=True)
    assert adapter.state == SortingState.E_STOP
    assert adapter.estop_source == EStopSource.PHYSICAL_HARDWARE

    res = adapter.handle_command({"command_id": 601, "command_name": "RESET"})
    assert res.status == "rejected"
    assert res.error_code == "PHYSICAL_ESTOP_ACTIVE"


# ---------------------------------------------------------------------------
# TC7: Command Idempotency & Conflicting Reuse
# ---------------------------------------------------------------------------
def test_tc7_idempotency_payload_binding(adapter: SortingAdapter):
    """Replaying exact same command returns duplicate; conflicting reuse is rejected."""
    cmd1 = {
        "command_id": 701,
        "command_name": "SORT_ITEM",
        "arguments": ["item-701", "METAL"],
    }
    res1 = adapter.handle_command(cmd1)
    assert res1.status == "acknowledged"

    # Exact replay
    res2 = adapter.handle_command(cmd1)
    assert res2.status == "acknowledged"
    assert res2.duplicate is True

    # Conflicting reuse: same command_id 701, but different class
    cmd_conflict = {
        "command_id": 701,
        "command_name": "SORT_ITEM",
        "arguments": ["item-701", "PLASTIC"],
    }
    res_conflict = adapter.handle_command(cmd_conflict)
    assert res_conflict.status == "rejected"
    assert res_conflict.error_code == "CONFLICTING_COMMAND_REUSE"


# ---------------------------------------------------------------------------
# TC8: Telemetry Schema Compliance & Ping
# ---------------------------------------------------------------------------
def test_tc8_telemetry_payload_compliance(adapter: SortingAdapter):
    """Telemetry payload complies with contracts/v1."""
    tel = adapter.get_telemetry()
    assert tel["device_id"] == "sorter-01"
    assert tel["state"] == "IDLE"
    assert "timestamp" in tel
    assert "sensors" in tel
    assert "digital_inputs" in tel["sensors"]
    assert isinstance(tel["uptime"], int)


def test_tc8_ping_command(adapter: SortingAdapter):
    """PING returns pong."""
    res = adapter.handle_command({"command_id": 801, "command_name": "PING"})
    assert res.status == "acknowledged"
    assert res.message == "pong"
