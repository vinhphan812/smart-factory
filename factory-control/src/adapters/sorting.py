"""Sorting module adapter: classify, route, and reject flows (Issue #23).

Responsibilities:
- Finite State Machine: IDLE, CLASSIFYING, ROUTING, REJECTING, STOPPED, FAULT, E_STOP.
- Decision routing rules: classify item -> drive diverter gate to designated bin.
- Reject handling: unknown/defective items are deterministically routed to REJECT_LANE.
- Duplicate item deduplication: unique item_ids are counted once.
- Fail-closed safety interlocks: jam sensor trips immediate E-Stop; sensor bus loss triggers FAULT alarm.
- Canonical telemetry and command deduplication compliant with contracts/v1.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union

from adapters.base import BaseDeviceAdapter
from models import (
    CommandResult,
    EStopSource,
    ItemClass,
    RouteDestination,
    SortingCounts,
    SortingSensors,
    SortingState,
)


class SortingAdapter(BaseDeviceAdapter):
    """Device adapter for the Smart Factory Sorting module (Module 2)."""

    def __init__(
        self,
        device_id: str = "sorter-01",
        sensors: Optional[SortingSensors] = None,
        max_idempotency_cache: int = 1000,
        idempotency_window_seconds: float = 300.0,
    ) -> None:
        super().__init__(
            device_id=device_id,
            device_type="sorter",
            max_idempotency_cache=max_idempotency_cache,
            idempotency_window_seconds=idempotency_window_seconds,
        )
        self.sensors = sensors or SortingSensors()
        self.counts = SortingCounts()
        
        self._state: SortingState = SortingState.IDLE
        self._estop_source: EStopSource = EStopSource.NONE
        self._last_error: Optional[str] = None
        self._current_destination: RouteDestination = RouteDestination.BIN_1
        
        # Item deduplication tracking (TC3)
        self._processed_item_ids: Set[str] = set()
        
        self.sensors.update_digital_bitmask()

    @property
    def state(self) -> SortingState:
        """Current operational state."""
        return self._state

    @property
    def estop_source(self) -> EStopSource:
        """Source of active Emergency Stop."""
        return self._estop_source

    @property
    def current_destination(self) -> RouteDestination:
        """Currently active diverter destination."""
        return self._current_destination

    def _set_state(self, new_state: SortingState) -> None:
        """Transition state and notify listeners."""
        if self._state != new_state:
            old = self._state.value
            self._state = new_state
            self._notify_state_change(old, new_state.value)

    def classify_item(self, class_str: Optional[str] = None) -> ItemClass:
        """Determine item class from argument or hardware sensors."""
        if class_str is not None:
            normalized = class_str.strip().upper()
            try:
                return ItemClass(normalized)
            except ValueError:
                return ItemClass.UNKNOWN

        # Auto-classify based on hardware sensor signals
        if self.sensors.inductive_sensor:
            return ItemClass.METAL
        if self.sensors.color_code == 1:
            return ItemClass.PLASTIC
        if self.sensors.color_code == 2:
            return ItemClass.WOOD

        return ItemClass.UNKNOWN

    def route_destination_for_class(self, item_class: ItemClass) -> RouteDestination:
        """Decision matrix: map item class to destination bin or reject lane."""
        if item_class == ItemClass.METAL:
            return RouteDestination.BIN_1
        elif item_class == ItemClass.PLASTIC:
            return RouteDestination.BIN_2
        elif item_class == ItemClass.WOOD:
            return RouteDestination.BIN_3
        else:
            # UNKNOWN, DEFECTIVE, or unclassifiable items route to REJECT_LANE (TC2)
            return RouteDestination.REJECT_LANE

    def handle_command(self, command: Dict[str, Any]) -> CommandResult:
        """Process an inbound command envelope conforming to contracts/v1."""
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
                error_code="MISSING_CORRELATION_ID",
                message="Command rejected: neither command_id nor request_id provided",
            )

        if isinstance(command_id, int) and command_id < 0:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
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
                error_code="CONFLICTING_COMMAND_REUSE",
                message=f"Command ID '{command_id}' was previously issued with different payload/arguments",
            )
        if cached_result is not None:
            return cached_result

        # Dispatch command
        if command_name == "SORT_ITEM":
            result = self._handle_sort_item(command_id, args)
        elif command_name == "ROUTE_MANUAL":
            result = self._handle_route_manual(command_id, args)
        elif command_name == "SORTING_STOP":
            result = self._handle_stop(command_id)
        elif command_name == "RESET":
            result = self._handle_reset(command_id)
        elif command_name == "PING":
            result = self._handle_ping(command_id)
        else:
            result = CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                error_code="UNKNOWN_COMMAND",
                message=f"Command '{command_name}' is not recognized for sorting adapter",
            )

        self.cache_command_result(command_id, command_name, args, result)
        return result

    def _handle_sort_item(self, command_id: Union[int, str], args: List[str]) -> CommandResult:
        """Handle SORT_ITEM command: classify, route to bin or reject, and update counts."""
        # Safety checks (fail-closed)
        if self._state == SortingState.E_STOP:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                error_code="CANNOT_SORT_IN_ESTOP",
                message=f"Sorter is locked in E-Stop ({self._estop_source.value}). Operator/hardware reset required.",
            )

        if self._state == SortingState.FAULT:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                error_code="CANNOT_SORT_IN_FAULT",
                message=f"Sorter is in fault state: {self._last_error}. Clear fault and reset before sorting.",
            )

        if self.sensors.jam_sensor:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                error_code="JAM_SENSOR_ACTIVE",
                message="Sorter cannot operate: jam sensor indicates diverter obstruction.",
            )

        if not self.sensors.sensor_alive:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                error_code="SENSOR_LOSS_FAULT",
                message="Sorter cannot operate: sensor bus connection lost.",
            )

        # Extract item identifier and class
        item_id = args[0] if len(args) > 0 else f"item-{self.counts.total_processed + 1}"
        class_hint = args[1] if len(args) > 1 else None

        # Duplicate item check (TC3): If item was already processed, ignore and count once
        if item_id in self._processed_item_ids:
            self.counts.duplicate_item_events_ignored += 1
            return CommandResult(
                command_id=command_id,
                status="acknowledged",
                observed_state=self._state,
                duplicate=True,
                data={
                    "item_id": item_id,
                    "duplicate_item": True,
                    "action": "ignored_duplicate_item",
                    "destination": self._current_destination.value,
                },
                message=f"Item '{item_id}' was already sorted previously; duplicate event counted once.",
            )

        # Step 1: Classify
        self._set_state(SortingState.CLASSIFYING)
        item_class = self.classify_item(class_hint)
        destination = self.route_destination_for_class(item_class)
        self._current_destination = destination

        # Step 2: Route or Reject
        if destination == RouteDestination.REJECT_LANE:
            # Unknown or defective class enters reject (TC2)
            self._set_state(SortingState.REJECTING)
            self.counts.reject_count += 1
            action_desc = f"Item '{item_id}' ({item_class.value}) routed to REJECT_LANE"
        else:
            # Correct class routes to intended bin (TC1)
            self._set_state(SortingState.ROUTING)
            if destination == RouteDestination.BIN_1:
                self.counts.bin_1_count += 1
            elif destination == RouteDestination.BIN_2:
                self.counts.bin_2_count += 1
            elif destination == RouteDestination.BIN_3:
                self.counts.bin_3_count += 1
            action_desc = f"Item '{item_id}' ({item_class.value}) routed to {destination.value}"

        self.counts.total_processed += 1
        self._processed_item_ids.add(item_id)

        # Complete sorting cycle and return to IDLE
        self._set_state(SortingState.IDLE)
        self._notify_telemetry(self.get_telemetry())

        return CommandResult(
            command_id=command_id,
            status="acknowledged",
            observed_state=self._state,
            data={
                "item_id": item_id,
                "item_class": item_class.value,
                "destination": destination.value,
                "total_processed": self.counts.total_processed,
            },
            message=action_desc,
        )

    def _handle_route_manual(self, command_id: Union[int, str], args: List[str]) -> CommandResult:
        """Handle manual operator diverter routing."""
        if not args:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                error_code="MISSING_DESTINATION",
                message="ROUTE_MANUAL requires destination argument (e.g. BIN_1, REJECT_LANE)",
            )

        dest_str = args[0].strip().upper()
        try:
            dest = RouteDestination(dest_str)
        except ValueError:
            return CommandResult(
                command_id=command_id,
                status="rejected",
                observed_state=self._state,
                error_code="INVALID_DESTINATION",
                message=f"Invalid destination: {args[0]}",
            )

        self._current_destination = dest
        self._set_state(SortingState.ROUTING)
        self._set_state(SortingState.IDLE)
        self._notify_telemetry(self.get_telemetry())

        return CommandResult(
            command_id=command_id,
            status="acknowledged",
            observed_state=self._state,
            message=f"Diverter manually routed to {dest.value}",
        )

    def _handle_stop(self, command_id: Union[int, str]) -> CommandResult:
        """Handle SORTING_STOP command."""
        self._set_state(SortingState.STOPPED)
        self._notify_telemetry(self.get_telemetry())
        return CommandResult(
            command_id=command_id,
            status="acknowledged",
            observed_state=self._state,
            message="Sorter stopped successfully",
        )

    def _handle_reset(self, command_id: Union[int, str]) -> CommandResult:
        """Handle RESET command."""
        return self.reset(command_id=command_id)

    def _handle_ping(self, command_id: Union[int, str]) -> CommandResult:
        """Handle PING command."""
        return CommandResult(
            command_id=command_id,
            status="acknowledged",
            observed_state=self._state,
            message="pong",
        )

    def update_sensors(
        self,
        optical_entry: Optional[bool] = None,
        inductive_sensor: Optional[bool] = None,
        color_code: Optional[int] = None,
        jam_sensor: Optional[bool] = None,
        physical_estop_button: Optional[bool] = None,
        sensor_alive: Optional[bool] = None,
    ) -> None:
        """Update sensor inputs and evaluate safety interlocks."""
        if optical_entry is not None:
            self.sensors.optical_entry = optical_entry
        if inductive_sensor is not None:
            self.sensors.inductive_sensor = inductive_sensor
        if color_code is not None:
            self.sensors.color_code = color_code
        if jam_sensor is not None:
            self.sensors.jam_sensor = jam_sensor
        if physical_estop_button is not None:
            self.sensors.physical_estop_button = physical_estop_button
        if sensor_alive is not None:
            self.sensors.sensor_alive = sensor_alive

        self.sensors.update_digital_bitmask()

        # Physical E-Stop button interlock (ADR-0006)
        if self.sensors.physical_estop_button and self._state != SortingState.E_STOP:
            self.emergency_stop(
                reason="Physical hardware emergency stop button pressed",
                source=EStopSource.PHYSICAL_HARDWARE,
            )
            return

        # Jam sensor trip (TC4)
        if self.sensors.jam_sensor and self._state in (
            SortingState.ROUTING,
            SortingState.CLASSIFYING,
            SortingState.REJECTING,
            SortingState.IDLE,
        ):
            self.emergency_stop(
                reason="Obstruction detected in diverter channel",
                source=EStopSource.JAM_SENSOR,
            )
            return

        # Sensor loss yields alarm and FAULT (TC5)
        if not self.sensors.sensor_alive and self._state not in (SortingState.FAULT, SortingState.E_STOP):
            self._last_error = "Sensor bus heartbeat timeout / cable disconnected"
            self._set_state(SortingState.FAULT)
            self._notify_telemetry(self.get_telemetry())

    def emergency_stop(
        self,
        reason: str = "Manual E-Stop",
        source: EStopSource = EStopSource.SOFTWARE,
    ) -> CommandResult:
        """Engage immediate local emergency stop interlock."""
        self._last_error = reason
        self._estop_source = source
        self._set_state(SortingState.E_STOP)
        self._notify_telemetry(self.get_telemetry())

        return CommandResult(
            command_id="estop",
            status="acknowledged",
            observed_state=SortingState.E_STOP,
            error_code="EMERGENCY_STOP",
            message=f"Emergency stop engaged [{source.value}]: {reason}",
        )

    def reset(self, command_id: Optional[Union[int, str]] = None) -> CommandResult:
        """Attempt to reset sorter from E_STOP or FAULT to IDLE."""
        cid = command_id if command_id is not None else "reset"

        # Check physical button release
        if self.sensors.physical_estop_button or self._estop_source == EStopSource.PHYSICAL_HARDWARE:
            return CommandResult(
                command_id=cid,
                status="rejected",
                observed_state=self._state,
                error_code="PHYSICAL_ESTOP_ACTIVE",
                message="Cannot reset via network: physical hardware emergency stop must be manually released on-site first",
            )

        if self.sensors.jam_sensor:
            return CommandResult(
                command_id=cid,
                status="rejected",
                observed_state=self._state,
                error_code="JAM_OBSTRUCTION_PRESENT",
                message="Cannot reset sorter: physical jam obstruction is still detected by sensor",
            )

        if not self.sensors.sensor_alive:
            return CommandResult(
                command_id=cid,
                status="rejected",
                observed_state=self._state,
                error_code="SENSOR_LOSS_ACTIVE",
                message="Cannot reset sorter: sensor bus connection is offline",
            )

        self._last_error = None
        self._estop_source = EStopSource.NONE
        self._set_state(SortingState.IDLE)
        self._notify_telemetry(self.get_telemetry())

        return CommandResult(
            command_id=cid,
            status="acknowledged",
            observed_state=SortingState.IDLE,
            message="Sorter successfully reset to IDLE state",
        )

    def get_telemetry(self) -> Dict[str, Any]:
        """Generate telemetry payload strictly conforming to contracts/v1/schemas/telemetry.schema.json."""
        self.sensors.update_digital_bitmask()
        return {
            "device_id": self.device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": self._state.value,
            "speed": self.sensors.diverter_position,
            "sensors": {
                "temperature_centi_c": 2500,
                "humidity_centi_percent": 5000,
                "digital_inputs": self.sensors.digital_inputs,
            },
            "uptime": self.uptime_ms,
        }
