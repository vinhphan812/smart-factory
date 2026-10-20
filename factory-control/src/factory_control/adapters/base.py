"""Base device adapter for Smart Factory physical and simulated modules."""

import abc
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from factory_control.models import CommandResult


class BaseDeviceAdapter(abc.ABC):
    """Abstract base class for all module adapters.
    
    Provides:
    - Command deduplication & idempotency caching (P0 safety requirement).
    - Lifecycle hooks and event callbacks (state change, telemetry).
    - Local safety interlock interfaces.
    """

    def __init__(
        self,
        device_id: str,
        device_type: str,
        max_idempotency_cache: int = 1000,
    ) -> None:
        self.device_id = device_id
        self.device_type = device_type
        self.max_idempotency_cache = max_idempotency_cache
        
        # Deduplication cache: key -> CommandResult
        self._command_cache: Dict[str, CommandResult] = {}
        
        # Listener callbacks
        self._state_listeners: List[Callable[[str, str, str], None]] = []
        self._telemetry_listeners: List[Callable[[Dict[str, Any]], None]] = []
        
        # Start time for uptime calculations
        self._uptime_start = time.monotonic()

    @property
    def uptime_ms(self) -> int:
        """Return uptime in milliseconds."""
        return int((time.monotonic() - self._uptime_start) * 1000)

    def register_state_listener(self, callback: Callable[[str, str, str], None]) -> None:
        """Register a callback for state changes: callback(device_id, old_state, new_state)."""
        self._state_listeners.append(callback)

    def register_telemetry_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for telemetry emissions: callback(telemetry_dict)."""
        self._telemetry_listeners.append(callback)

    def _notify_state_change(self, old_state: str, new_state: str) -> None:
        """Notify all registered state change listeners."""
        for cb in self._state_listeners:
            try:
                cb(self.device_id, old_state, new_state)
            except Exception:
                pass

    def _notify_telemetry(self, telemetry_data: Dict[str, Any]) -> None:
        """Notify all registered telemetry listeners."""
        for cb in self._telemetry_listeners:
            try:
                cb(telemetry_data)
            except Exception:
                pass

    def _check_idempotency(self, command_id: Union[int, str]) -> Optional[CommandResult]:
        """Check if command ID has already been executed.
        Returns cached result with duplicate=True if found.
        """
        key = str(command_id)
        if key in self._command_cache:
            cached = self._command_cache[key]
            # Return duplicate copy with current timestamp
            return CommandResult(
                command_id=command_id,
                status=cached.status,
                observed_state=cached.observed_state,
                speed=cached.speed,
                error_code=cached.error_code,
                message=cached.message,
                duplicate=True,
            )
        return None

    def _cache_command_result(self, command_id: Union[int, str], result: CommandResult) -> None:
        """Cache a command execution result for idempotency."""
        key = str(command_id)
        if len(self._command_cache) >= self.max_idempotency_cache:
            # Drop oldest key (FIFO)
            first_key = next(iter(self._command_cache))
            del self._command_cache[first_key]
        self._command_cache[key] = result

    @abc.abstractmethod
    def handle_command(self, command: Dict[str, Any]) -> CommandResult:
        """Process an inbound command envelope conforming to contracts/v1."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_telemetry(self) -> Dict[str, Any]:
        """Return canonical telemetry payload conforming to contracts/v1."""
        raise NotImplementedError

    @abc.abstractmethod
    def emergency_stop(self, reason: str = "Manual E-Stop") -> CommandResult:
        """Immediately engage local emergency stop interlock."""
        raise NotImplementedError

    @abc.abstractmethod
    def reset(self, command_id: Optional[Union[int, str]] = None) -> CommandResult:
        """Attempt to reset adapter from FAULT/E_STOP to IDLE."""
        raise NotImplementedError
