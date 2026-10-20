"""Server-authorized command orchestrator with durable state machine.

This module provides:
- Command lifecycle: enqueue → execute → observe → complete/timeout/fail
- Durable state machine using SQLite (via EventStore)
- Observed completion: poll device state or use ack pattern
- Command authorization using X-Operator-Token header

Command State Machine:
    PENDING → EXECUTING → WAITING_ACK → COMPLETED
         ↓         ↓            ↓
       FAILED   FAILED      TIMEOUT/FAILED

The orchestrator persists command state to the database so commands survive
process restarts and can be observed for completion.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    select,
    text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class CommandState(str, Enum):
    """Command lifecycle states."""

    PENDING = "pending"           # Command enqueued, not yet executed
    EXECUTING = "executing"       # Command sent to device
    WAITING_ACK = "waiting_ack"   # Awaiting device acknowledgment
    COMPLETED = "completed"        # Device acknowledged success
    FAILED = "failed"             # Device reported failure
    TIMEOUT = "timeout"           # No response within timeout window


class CommandPriority(int, Enum):
    """Command priority levels (lower = higher priority)."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class Command:
    """Represents a server-authorized command to be executed on a device."""

    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = ""
    command_name: str = ""         # e.g., "MOVE", "GRAB", "RELEASE"
    command_args: dict[str, Any] = field(default_factory=dict)
    priority: CommandPriority = CommandPriority.NORMAL
    session_id: str | None = None  # For ordering: commands in same session execute in order

    # State
    state: CommandState = CommandState.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    executed_at: str | None = None
    completed_at: str | None = None

    # Result
    result: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    # Authorization
    operator_token: str | None = None
    authorized_by: str | None = None

    # Observation
    ack_received: bool = False
    observation_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "command_id": self.command_id,
            "device_id": self.device_id,
            "command_name": self.command_name,
            "command_args": self.command_args,
            "priority": self.priority.value,
            "session_id": self.session_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error_message": self.error_message,
            "operator_token": self.operator_token,
            "authorized_by": self.authorized_by,
            "ack_received": self.ack_received,
            "observation_count": self.observation_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Command":
        """Create Command from dictionary."""
        return cls(
            command_id=data["command_id"],
            device_id=data["device_id"],
            command_name=data["command_name"],
            command_args=data.get("command_args", {}),
            priority=CommandPriority(data.get("priority", CommandPriority.NORMAL.value)),
            session_id=data.get("session_id"),
            state=CommandState(data.get("state", CommandState.PENDING.value)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            executed_at=data.get("executed_at"),
            completed_at=data.get("completed_at"),
            result=data.get("result", {}),
            error_message=data.get("error_message"),
            operator_token=data.get("operator_token"),
            authorized_by=data.get("authorized_by"),
            ack_received=data.get("ack_received", False),
            observation_count=data.get("observation_count", 0),
        )


# --- SQLAlchemy Models ---

class CommandBase(DeclarativeBase):
    """Base class for command models."""
    pass


class CommandRecord(CommandBase):
    """SQLAlchemy model for persisted commands."""

    __tablename__ = "commands"

    command_id = Column(String(36), primary_key=True)
    device_id = Column(String(64), nullable=False, index=True)
    command_name = Column(String(64), nullable=False)
    command_args = Column(JSON, nullable=False, default=dict)
    priority = Column(Integer, nullable=False, default=CommandPriority.NORMAL.value)
    session_id = Column(String(36), nullable=True, index=True)

    # State
    state = Column(String(16), nullable=False, default=CommandState.PENDING.value)
    created_at = Column(DateTime(timezone=True), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Result
    result = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)

    # Authorization
    operator_token = Column(String(64), nullable=True)
    authorized_by = Column(String(64), nullable=True)

    # Observation
    ack_received = Column(Integer, nullable=False, default=0)
    observation_count = Column(Integer, nullable=False, default=0)


# --- Command Executor Protocol ---

class CommandExecutor:
    """Base class for executing commands on devices.

    Implement execute() to provide custom command execution (MQTT, HTTP, etc.)
    """

    async def execute(self, command: Command) -> tuple[bool, dict[str, Any]]:
        """Execute a command on the target device.

        Args:
            command: The command to execute.

        Returns:
            Tuple of (success: bool, result: dict).
            The result dict should contain device response data on success,
            or error details on failure.
        """
        raise NotImplementedError("Subclasses must implement execute()")


class MqttCommandExecutor(CommandExecutor):
    """MQTT-based command executor.

    Publishes commands to device command topics and handles responses.
    """

    def __init__(
        self,
        mqtt_client: Any | None = None,
        mqtt_publish: Callable[[str, str, int], None] | None = None,
    ) -> None:
        """Initialize the MQTT command executor.

        Args:
            mqtt_client: Optional paho-mqtt client for publishing.
            mqtt_publish: Optional publish function(topic, payload, qos).
                          If not provided, uses mqtt_client.publish if available.
        """
        self._mqtt_client = mqtt_client
        self._mqtt_publish = mqtt_publish

    async def execute(self, command: Command) -> tuple[bool, dict[str, Any]]:
        """Publish command to device MQTT topic."""
        import json

        topic = f"smart-factory/{command.device_id}/command"
        payload = json.dumps({
            "command_id": command.command_id,
            "command_name": command.command_name,
            "command_args": command.command_args,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        try:
            if self._mqtt_publish:
                self._mqtt_publish(topic, payload, qos=1)
            elif self._mqtt_client:
                result = self._mqtt_client.publish(topic, payload, qos=1)
                if result.rc != 0:
                    return False, {"error": f"MQTT publish failed with rc={result.rc}"}
            else:
                return False, {"error": "No MQTT client or publish function configured"}

            logger.info(
                "Command %s published to %s: %s",
                command.command_id,
                command.device_id,
                command.command_name,
            )
            return True, {"topic": topic, "published": True}

        except Exception as exc:
            logger.exception("Failed to execute command %s", command.command_id)
            return False, {"error": str(exc)}


# --- Command Orchestrator ---

class CommandOrchestrator:
    """Server-authorized command orchestrator with durable state machine.

    Manages command lifecycle from enqueue through execution, observation,
    and final completion/timeout/fail states. Persists state to SQLite.

    Args:
        database_url: SQLite database URL for command persistence.
        executor: Command executor for sending commands to devices.
        ack_timeout_seconds: Seconds to wait for acknowledgment before timeout.
        observation_interval_seconds: Seconds between observation polls.
    """

    # Default timeouts
    DEFAULT_ACK_TIMEOUT = 30
    DEFAULT_OBSERVATION_INTERVAL = 2

    def __init__(
        self,
        database_url: str,
        executor: CommandExecutor | None = None,
        ack_timeout_seconds: int = DEFAULT_ACK_TIMEOUT,
        observation_interval_seconds: int = DEFAULT_OBSERVATION_INTERVAL,
    ) -> None:
        connect_args: dict[str, object] = {}
        if database_url.startswith("sqlite"):
            connect_args["timeout"] = 30
        self._engine = create_async_engine(
            database_url, echo=False, connect_args=connect_args
        )
        self._session_maker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._executor = executor or MqttCommandExecutor()
        self._ack_timeout = ack_timeout_seconds
        self._observation_interval = observation_interval_seconds
        self._running = False
        self._observer_task: asyncio.Task | None = None

    async def init(self) -> None:
        """Initialize the orchestrator and create tables."""
        async with self._engine.begin() as conn:
            await conn.run_sync(CommandBase.metadata.create_all)
        logger.info("CommandOrchestrator initialized")

    async def close(self) -> None:
        """Stop the observer and close database connections."""
        await self.stop_observer()
        await self._engine.dispose()

    # --- Authorization ---

    def validate_operator_token(self, token: str, expected: str) -> bool:
        """Validate operator token using constant-time comparison.

        Args:
            token: The token to validate.
            expected: The expected token value.

        Returns:
            True if tokens match, False otherwise.
        """
        import secrets
        return secrets.compare_digest(token, expected)

    # --- Command Lifecycle ---

    async def enqueue_command(
        self,
        device_id: str,
        command_name: str,
        command_args: dict[str, Any] | None = None,
        priority: CommandPriority = CommandPriority.NORMAL,
        session_id: str | None = None,
        operator_token: str | None = None,
    ) -> Command:
        """Enqueue a new command for execution.

        The command is persisted to the database in PENDING state.
        Use start_observer() to begin execution and observation.

        Args:
            device_id: Target device identifier.
            command_name: Name of the command (e.g., "MOVE", "GRAB").
            command_args: Optional command arguments dictionary.
            priority: Command priority (lower = higher priority).
            session_id: Optional session ID for ordering.
            operator_token: Optional operator token for authorization.

        Returns:
            The enqueued Command object.
        """
        command = Command(
            device_id=device_id,
            command_name=command_name,
            command_args=command_args or {},
            priority=priority,
            session_id=session_id,
            operator_token=operator_token,
        )

        await self._persist_command(command)
        logger.info(
            "Command %s enqueued for device %s: %s (priority=%s)",
            command.command_id,
            device_id,
            command_name,
            priority.name,
        )
        return command

    async def execute_command(self, command: Command) -> tuple[CommandState, dict[str, Any]]:
        """Execute a pending command.

        Transitions command to EXECUTING state, sends to device via executor,
        then transitions to WAITING_ACK for observation.

        Args:
            command: The command to execute (must be in PENDING state).

        Returns:
            Tuple of (final state, result dict).
        """
        if command.state != CommandState.PENDING:
            logger.warning(
                "Command %s not in PENDING state, skipping execution",
                command.command_id,
            )
            return command.state, command.result

        # Transition to EXECUTING
        command.state = CommandState.EXECUTING
        command.executed_at = datetime.now(timezone.utc).isoformat()
        await self._persist_command(command)

        # Execute via executor
        success, result = await self._executor.execute(command)

        if success:
            command.state = CommandState.WAITING_ACK
            command.result = result
        else:
            command.state = CommandState.FAILED
            command.error_message = result.get("error", "Unknown error")
            command.result = result

        await self._persist_command(command)
        return command.state, command.result

    async def observe_command(
        self,
        command: Command,
        ack_received: bool = False,
        device_state: dict[str, Any] | None = None,
    ) -> Command:
        """Observe command state from device.

        Call this when:
        - An acknowledgment is received from the device
        - Polling device state returns updated state

        Args:
            command: The command to observe.
            ack_received: Whether an ACK was received from the device.
            device_state: Optional current device state from polling.

        Returns:
            The updated Command object.
        """
        command.observation_count += 1

        if ack_received:
            command.ack_received = True
            command.state = CommandState.COMPLETED
            command.completed_at = datetime.now(timezone.utc).isoformat()
            if device_state:
                command.result = device_state
            logger.info("Command %s completed (ACK received)", command.command_id)

        await self._persist_command(command)
        return command

    async def mark_timeout(self, command: Command) -> Command:
        """Mark a command as timed out.

        Args:
            command: The command to mark as timeout.

        Returns:
            The updated Command object.
        """
        command.state = CommandState.TIMEOUT
        command.completed_at = datetime.now(timezone.utc).isoformat()
        command.error_message = f"No ACK received within {self._ack_timeout}s"
        await self._persist_command(command)
        logger.warning("Command %s timed out", command.command_id)
        return command

    async def mark_failed(self, command: Command, error: str) -> Command:
        """Mark a command as failed.

        Args:
            command: The command to mark as failed.
            error: Error message describing the failure.

        Returns:
            The updated Command object.
        """
        command.state = CommandState.FAILED
        command.completed_at = datetime.now(timezone.utc).isoformat()
        command.error_message = error
        await self._persist_command(command)
        logger.error("Command %s failed: %s", command.command_id, error)
        return command

    # --- Observer ---

    async def start_observer(self) -> None:
        """Start the background observer task."""
        if self._running:
            logger.warning("Observer already running")
            return
        self._running = True
        self._observer_task = asyncio.create_task(self._observer_loop())
        logger.info("Command observer started")

    async def stop_observer(self) -> None:
        """Stop the background observer task."""
        self._running = False
        if self._observer_task:
            self._observer_task.cancel()
            try:
                await self._observer_task
            except asyncio.CancelledError:
                pass
            self._observer_task = None
        logger.info("Command observer stopped")

    async def _observer_loop(self) -> None:
        """Background loop that observes waiting commands.

        Polls commands in WAITING_ACK state and checks for timeouts.
        """
        while self._running:
            try:
                await self._observe_waiting_commands()
                await asyncio.sleep(self._observation_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Error in observer loop: %s", exc)
                await asyncio.sleep(self._observation_interval)

    async def _observe_waiting_commands(self) -> None:
        """Observe all commands in WAITING_ACK state."""
        commands = await self._get_commands_by_state(CommandState.WAITING_ACK)
        now = datetime.now(timezone.utc)

        for cmd in commands:
            # Check timeout
            if cmd.executed_at:
                executed_dt = datetime.fromisoformat(cmd.executed_at)
                elapsed = (now - executed_dt).total_seconds()
                if elapsed > self._ack_timeout:
                    await self.mark_timeout(cmd)
                    continue

            # TODO: In production, poll device state or listen for ACKs
            # For now, commands stay in WAITING_ACK until timeout
            # External callers should call observe_command() when ACKs arrive

    # --- Queries ---

    async def get_command(self, command_id: str) -> Command | None:
        """Get a command by ID."""
        async with self._session_maker() as session:
            row = await session.get(CommandRecord, command_id)
            if row is None:
                return None
            return self._record_to_command(row)

    async def get_commands_by_device(
        self,
        device_id: str,
        state: CommandState | None = None,
        limit: int = 100,
    ) -> list[Command]:
        """Get commands for a device, optionally filtered by state."""
        async with self._session_maker() as session:
            q = select(CommandRecord).where(CommandRecord.device_id == device_id)
            if state:
                q = q.where(CommandRecord.state == state.value)
            q = q.order_by(CommandRecord.created_at.desc()).limit(limit)
            rows = (await session.execute(q)).scalars().all()
            return [self._record_to_command(r) for r in rows]

    async def get_commands_by_session(
        self,
        session_id: str,
        state: CommandState | None = None,
    ) -> list[Command]:
        """Get all commands in a session (for ordering)."""
        async with self._session_maker() as session:
            q = select(CommandRecord).where(CommandRecord.session_id == session_id)
            if state:
                q = q.where(CommandRecord.state == state.value)
            q = q.order_by(CommandRecord.created_at.asc())
            rows = (await session.execute(q)).scalars().all()
            return [self._record_to_command(r) for r in rows]

    async def get_pending_commands(self) -> list[Command]:
        """Get all pending commands ordered by priority."""
        async with self._session_maker() as session:
            q = (
                select(CommandRecord)
                .where(CommandRecord.state == CommandState.PENDING.value)
                .order_by(CommandRecord.priority.asc(), CommandRecord.created_at.asc())
            )
            rows = (await session.execute(q)).scalars().all()
            return [self._record_to_command(r) for r in rows]

    # --- Persistence ---

    async def _persist_command(self, command: Command) -> None:
        """Persist command to database."""
        async with self._session_maker() as session:
            # Check if command exists
            existing = await session.get(CommandRecord, command.command_id)
            record = CommandRecord(
                command_id=command.command_id,
                device_id=command.device_id,
                command_name=command.command_name,
                command_args=command.command_args,
                priority=command.priority.value,
                session_id=command.session_id,
                state=command.state.value,
                created_at=datetime.fromisoformat(command.created_at),
                executed_at=datetime.fromisoformat(command.executed_at) if command.executed_at else None,
                completed_at=datetime.fromisoformat(command.completed_at) if command.completed_at else None,
                result=command.result,
                error_message=command.error_message,
                operator_token=command.operator_token,
                authorized_by=command.authorized_by,
                ack_received=int(command.ack_received),
                observation_count=command.observation_count,
            )
            if existing:
                # Update existing record
                for key, value in record.__dict__.items():
                    if not key.startswith('_'):
                        setattr(existing, key, value)
                await session.commit()
            else:
                session.add(record)
                await session.commit()

    async def _get_commands_by_state(self, state: CommandState) -> list[Command]:
        """Get all commands in a specific state."""
        async with self._session_maker() as session:
            q = (
                select(CommandRecord)
                .where(CommandRecord.state == state.value)
                .order_by(CommandRecord.created_at.asc())
            )
            rows = (await session.execute(q)).scalars().all()
            return [self._record_to_command(r) for r in rows]

    def _record_to_command(self, record: CommandRecord) -> Command:
        """Convert database record to Command object."""
        return Command(
            command_id=record.command_id,
            device_id=record.device_id,
            command_name=record.command_name,
            command_args=record.command_args or {},
            priority=CommandPriority(record.priority),
            session_id=record.session_id,
            state=CommandState(record.state),
            created_at=record.created_at.isoformat() if record.created_at else "",
            executed_at=record.executed_at.isoformat() if record.executed_at else None,
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
            result=record.result or {},
            error_message=record.error_message,
            operator_token=record.operator_token,
            authorized_by=record.authorized_by,
            ack_received=bool(record.ack_received),
            observation_count=record.observation_count,
        )
