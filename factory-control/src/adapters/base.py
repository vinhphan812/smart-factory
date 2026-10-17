"""Base device adapter for Smart Factory physical and simulated modules."""

import abc
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from models import CachedCommand, CommandResult


class BaseDeviceAdapter(abc.ABC):
    """Abstract base class for all module adapters.
    
    Provides:
    - Command deduplication & idempotency caching with strict payload binding (P0 safety requirement).
    - Lifecycle hooks and event callbacks (state change, telemetry).
    - Local safety interlock interfaces.
    """

    def __init__(
        self,
        device_id: str,
        device_type: str,
        max_idempotency_cache: int = 1000,
        idempotency_window_seconds: float = 300.0,
    ) -> None:
        self.device_id = device_id
        self.device_type = device_type
        self.max_idempotency_cache = max_idempotency_cache
        self.idempotency_window_seconds = idempotency_window_seconds
        
        # Deduplication cache: "type:id" -> CachedCommand
        self._command_cache: Dict[str, CachedCommand] = {}
        
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

    def _cache_key(self, command_id: Union[int, str]) -> str:
        """Construct a type-safe cache key to prevent collision between int and str."""
        return f"{type(command_id).__name__}:{command_id}"

    def check_idempotency(
        self,
        command_id: Union[int, str],
        command_name: str,
        arguments: List[str],
    ) -> Tuple[Optional[CommandResult], Optional[str]]:
        """Verify command correlation ID against idempotency cache with payload binding.
        
        Returns:
            (cached_result, conflict_error_code)
            - If exact duplicate: (result_with_duplicate_flag, None)
            - If conflicting payload reuse: (None, "CONFLICTING_COMMAND_REUSE")
            - If fresh command: (None, None)
        """
        key = self._cache_key(command_id)
        if key in self._command_cache:
            cached = self._command_cache[key]
            
            # Check time-window expiry
            now = time.monotonic()
            if (now - cached.created_at) > self.idempotency_window_seconds:
                # Expired: purge and allow fresh execution
                del self._command_cache[key]
                return None, None

            # Verify payload binding (command_name and arguments)
            if cached.command_name == command_name and cached.arguments == arguments:
                # Exact identical duplicate
                dup_result = CommandResult(
                    command_id=command_id,
                    status=cached.result.status,
                    observed_state=cached.result.observed_state,
                    speed=cached.result.speed,
                    error_code=cached.result.error_code,
                    message=cached.result.message,
                    duplicate=True,
                    data=cached.result.data,
                )
                return dup_result, None
            else:
                # Conflicting reuse of same command_id with different command or parameters!
                return None, "CONFLICTING_COMMAND_REUSE"

        return None, None

    def cache_command_result(
        self,
        command_id: Union[int, str],
        command_name: str,
        arguments: List[str],
        result: CommandResult,
    ) -> None:
        """Cache a command execution result for idempotency."""
        key = self._cache_key(command_id)
        if len(self._command_cache) >= self.max_idempotency_cache:
            first_key = next(iter(self._command_cache))
            del self._command_cache[first_key]

        self._command_cache[key] = CachedCommand(
            command_id=command_id,
            id_type=type(command_id).__name__,
            command_name=command_name,
            arguments=list(arguments),
            result=result,
            created_at=time.monotonic(),
        )

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
