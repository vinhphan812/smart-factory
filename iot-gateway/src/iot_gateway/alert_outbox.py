"""Persistent incident and Yanshee alert dispatch outbox.

This module provides:
- DB-backed outbox for alert/incident notifications
- Yanshee notification dispatch (topic per robot skill)
- Retry with exponential backoff
- Dead-letter queue for failed dispatches
- Session-based ordering (same-session alerts in order)

The outbox pattern ensures reliable alert delivery:
1. Alerts are persisted to the outbox table first
2. A background worker processes the outbox
3. Successful dispatches are marked complete
4. Failed dispatches are retried with backoff
5. After max retries, alerts move to dead-letter queue
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
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class AlertOutboxState(str, Enum):
    """Outbox entry states."""

    PENDING = "pending"       # Not yet dispatched
    DISPATCHING = "dispatching"  # Currently being dispatched
    DISPATCHED = "dispatched"   # Successfully dispatched
    FAILED = "failed"        # Failed, will retry
    DEAD_LETTER = "dead_letter"  # Failed permanently after max retries


class AlertType(str, Enum):
    """Types of alerts in the outbox."""

    INCIDENT = "incident"     # Incident notification
    ALERT = "alert"          # General alert
    YANSHEE_NOTIFICATION = "yanshee_notification"  # Yanshee robot notification


class YansheeSkill(str, Enum):
    """Yanshee robot skill topics for notifications."""

    MOVEMENT = "yanshee/movement"
    GRABBING = "yanshee/grabbing"
    SPEECH = "yanshee/speech"
    EMOTION = "yanshee/emotion"
    NAVIGATION = "yanshee/navigation"


@dataclass
class AlertOutboxEntry:
    """Represents an alert entry in the outbox."""

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    alert_type: AlertType = AlertType.ALERT
    alert_id: str | None = None  # Reference to source alert/incident
    device_id: str | None = None
    session_id: str | None = None  # For ordering: alerts in same session in order
    sequence: int = 0  # Sequence number for ordering within session

    # Content
    title: str = ""
    message: str = ""
    severity: str = "info"  # info, warning, critical
    metadata: dict[str, Any] = field(default_factory=dict)

    # Yanshee-specific
    yanshee_skill: YansheeSkill | None = None

    # State
    state: AlertOutboxState = AlertOutboxState.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dispatched_at: str | None = None
    last_attempt_at: str | None = None
    attempt_count: int = 0

    # Retry config
    max_retries: int = 3
    retry_backoff_base: int = 2  # seconds, exponential backoff

    # Dead-letter info
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entry_id": self.entry_id,
            "alert_type": self.alert_type.value,
            "alert_id": self.alert_id,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "metadata": self.metadata,
            "yanshee_skill": self.yanshee_skill.value if self.yanshee_skill else None,
            "state": self.state.value,
            "created_at": self.created_at,
            "dispatched_at": self.dispatched_at,
            "last_attempt_at": self.last_attempt_at,
            "attempt_count": self.attempt_count,
            "max_retries": self.max_retries,
            "retry_backoff_base": self.retry_backoff_base,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AlertOutboxEntry":
        """Create AlertOutboxEntry from dictionary."""
        yanshee_skill = data.get("yanshee_skill")
        return cls(
            entry_id=data["entry_id"],
            alert_type=AlertType(data["alert_type"]),
            alert_id=data.get("alert_id"),
            device_id=data.get("device_id"),
            session_id=data.get("session_id"),
            sequence=data.get("sequence", 0),
            title=data.get("title", ""),
            message=data.get("message", ""),
            severity=data.get("severity", "info"),
            metadata=data.get("metadata", {}),
            yanshee_skill=YansheeSkill(yanshee_skill) if yanshee_skill else None,
            state=AlertOutboxState(data.get("state", AlertOutboxState.PENDING.value)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            dispatched_at=data.get("dispatched_at"),
            last_attempt_at=data.get("last_attempt_at"),
            attempt_count=data.get("attempt_count", 0),
            max_retries=data.get("max_retries", 3),
            retry_backoff_base=data.get("retry_backoff_base", 2),
            error_message=data.get("error_message"),
        )


# --- SQLAlchemy Models ---

class OutboxBase(DeclarativeBase):
    """Base class for outbox models."""
    pass


class AlertOutboxRecord(OutboxBase):
    """SQLAlchemy model for alert outbox entries."""

    __tablename__ = "alert_outbox"

    entry_id = Column(String(36), primary_key=True)
    alert_type = Column(String(24), nullable=False, index=True)
    alert_id = Column(String(36), nullable=True, index=True)
    device_id = Column(String(64), nullable=True, index=True)
    session_id = Column(String(36), nullable=True, index=True)
    sequence = Column(Integer, nullable=False, default=0)

    # Content
    title = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(16), nullable=False, default="info")
    alert_metadata = Column(JSON, nullable=False, default=dict)  # renamed to avoid SA warning

    # Yanshee-specific
    yanshee_skill = Column(String(32), nullable=True)

    # State
    state = Column(String(16), nullable=False, default=AlertOutboxState.PENDING.value, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)

    # Retry config
    max_retries = Column(Integer, nullable=False, default=3)
    retry_backoff_base = Column(Integer, nullable=False, default=2)

    # Dead-letter info
    error_message = Column(Text, nullable=True)


# --- Alert Dispatcher ---

class AlertDispatcher:
    """Base class for dispatching alerts to external systems.

    Implement dispatch() to provide custom alert dispatch (MQTT, HTTP, etc.)
    """

    async def dispatch(self, entry: AlertOutboxEntry) -> tuple[bool, str | None]:
        """Dispatch an alert entry.

        Args:
            entry: The alert outbox entry to dispatch.

        Returns:
            Tuple of (success: bool, error_message: str | None).
        """
        raise NotImplementedError("Subclasses must implement dispatch()")


class MqttAlertDispatcher(AlertDispatcher):
    """MQTT-based alert dispatcher.

    Publishes alerts to configurable MQTT topics.
    """

    def __init__(
        self,
        mqtt_client: Any | None = None,
        mqtt_publish: Callable[[str, str, int], None] | None = None,
    ) -> None:
        """Initialize the MQTT alert dispatcher.

        Args:
            mqtt_client: Optional paho-mqtt client for publishing.
            mqtt_publish: Optional publish function(topic, payload, qos).
        """
        self._mqtt_client = mqtt_client
        self._mqtt_publish = mqtt_publish

    async def dispatch(self, entry: AlertOutboxEntry) -> tuple[bool, str | None]:
        """Publish alert to MQTT topic."""
        import json

        # Determine topic based on alert type and Yanshee skill
        if entry.yanshee_skill:
            topic = f"smart-factory/alerts/{entry.yanshee_skill.value}"
        else:
            topic = f"smart-factory/alerts/{entry.alert_type.value}"

        # Add device_id to topic if present
        if entry.device_id:
            topic = f"smart-factory/alerts/{entry.device_id}/{entry.alert_type.value}"

        payload = json.dumps({
            "entry_id": entry.entry_id,
            "alert_id": entry.alert_id,
            "title": entry.title,
            "message": entry.message,
            "severity": entry.severity,
            "device_id": entry.device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": entry.metadata,
        })

        try:
            if self._mqtt_publish:
                self._mqtt_publish(topic, payload, qos=1)
            elif self._mqtt_client:
                result = self._mqtt_client.publish(topic, payload, qos=1)
                if result.rc != 0:
                    return False, f"MQTT publish failed with rc={result.rc}"
            else:
                return False, "No MQTT client or publish function configured"

            logger.info(
                "Alert %s dispatched to %s: %s",
                entry.entry_id,
                topic,
                entry.title,
            )
            return True, None

        except Exception as exc:
            logger.exception("Failed to dispatch alert %s", entry.entry_id)
            return False, str(exc)


# --- Alert Outbox ---

class AlertOutbox:
    """Persistent alert dispatch outbox with retry and dead-letter support.

    Manages alert lifecycle from creation through dispatch, retry, and
    dead-letter handling. Persists state to SQLite.

    Args:
        database_url: SQLite database URL for outbox persistence.
        dispatcher: Alert dispatcher for sending alerts to external systems.
        max_retries: Default maximum retry attempts.
        retry_backoff_base: Base for exponential backoff (in seconds).
        poll_interval: Seconds between outbox polls.
    """

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF_BASE = 2
    DEFAULT_POLL_INTERVAL = 5

    def __init__(
        self,
        database_url: str,
        dispatcher: AlertDispatcher | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff_base: int = DEFAULT_BACKOFF_BASE,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
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
        self._dispatcher = dispatcher or MqttAlertDispatcher()
        self._default_max_retries = max_retries
        self._default_backoff_base = retry_backoff_base
        self._poll_interval = poll_interval
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._sequence_counter: dict[str, int] = {}  # session_id -> sequence

    async def init(self) -> None:
        """Initialize the outbox and create tables."""
        async with self._engine.begin() as conn:
            await conn.run_sync(OutboxBase.metadata.create_all)
        logger.info("AlertOutbox initialized")

    async def close(self) -> None:
        """Stop the worker and close database connections."""
        await self.stop_worker()
        await self._engine.dispose()

    # --- Enqueue ---

    async def enqueue(
        self,
        alert_type: AlertType,
        title: str,
        message: str,
        severity: str = "info",
        alert_id: str | None = None,
        device_id: str | None = None,
        session_id: str | None = None,
        yanshee_skill: YansheeSkill | None = None,
        metadata: dict[str, Any] | None = None,
        max_retries: int | None = None,
    ) -> AlertOutboxEntry:
        """Enqueue an alert for dispatch.

        Args:
            alert_type: Type of alert (INCIDENT, ALERT, YANSHEE_NOTIFICATION).
            title: Alert title.
            message: Alert message.
            severity: Alert severity (info, warning, critical).
            alert_id: Optional reference to source alert/incident.
            device_id: Optional target device ID.
            session_id: Optional session ID for ordering.
            yanshee_skill: Optional Yanshee skill for robot notifications.
            metadata: Optional additional metadata.
            max_retries: Optional override for max retries.

        Returns:
            The enqueued AlertOutboxEntry.
        """
        # Get sequence for session ordering
        sequence = 0
        if session_id:
            sequence = self._sequence_counter.get(session_id, 0)
            self._sequence_counter[session_id] = sequence + 1

        entry = AlertOutboxEntry(
            alert_type=alert_type,
            alert_id=alert_id,
            device_id=device_id,
            session_id=session_id,
            sequence=sequence,
            title=title,
            message=message,
            severity=severity,
            metadata=metadata or {},
            yanshee_skill=yanshee_skill,
            max_retries=max_retries if max_retries is not None else self._default_max_retries,
        )

        await self._persist_entry(entry)
        logger.info(
            "Alert %s enqueued: type=%s severity=%s (session=%s seq=%d)",
            entry.entry_id,
            alert_type.value,
            severity,
            session_id or "none",
            sequence,
        )
        return entry

    async def enqueue_incident(
        self,
        incident_id: str,
        title: str,
        message: str,
        severity: str = "info",
        device_id: str | None = None,
        session_id: str | None = None,
    ) -> AlertOutboxEntry:
        """Convenience method to enqueue an incident notification."""
        return await self.enqueue(
            alert_type=AlertType.INCIDENT,
            alert_id=incident_id,
            title=title,
            message=message,
            severity=severity,
            device_id=device_id,
            session_id=session_id,
        )

    async def enqueue_yanshee(
        self,
        skill: YansheeSkill,
        title: str,
        message: str,
        severity: str = "info",
        device_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AlertOutboxEntry:
        """Convenience method to enqueue a Yanshee notification."""
        return await self.enqueue(
            alert_type=AlertType.YANSHEE_NOTIFICATION,
            title=title,
            message=message,
            severity=severity,
            device_id=device_id,
            session_id=session_id,
            yanshee_skill=skill,
            metadata=metadata,
        )

    # --- Dispatch ---

    async def dispatch_entry(self, entry: AlertOutboxEntry) -> AlertOutboxEntry:
        """Dispatch a single outbox entry.

        Args:
            entry: The entry to dispatch.

        Returns:
            The updated entry with dispatch result.
        """
        # Transition to DISPATCHING
        entry.state = AlertOutboxState.DISPATCHING
        entry.last_attempt_at = datetime.now(timezone.utc).isoformat()
        entry.attempt_count += 1
        await self._persist_entry(entry)

        # Dispatch
        success, error = await self._dispatcher.dispatch(entry)

        if success:
            entry.state = AlertOutboxState.DISPATCHED
            entry.dispatched_at = datetime.now(timezone.utc).isoformat()
            entry.error_message = None
            logger.info("Alert %s dispatched successfully", entry.entry_id)
        else:
            entry.error_message = error
            if entry.attempt_count >= entry.max_retries:
                # Move to dead letter
                entry.state = AlertOutboxState.DEAD_LETTER
                logger.error(
                    "Alert %s moved to dead letter after %d attempts: %s",
                    entry.entry_id,
                    entry.attempt_count,
                    error,
                )
            else:
                # Mark for retry
                entry.state = AlertOutboxState.FAILED
                logger.warning(
                    "Alert %s dispatch failed (attempt %d/%d): %s",
                    entry.entry_id,
                    entry.attempt_count,
                    entry.max_retries,
                    error,
                )

        await self._persist_entry(entry)
        return entry

    # --- Worker ---

    async def start_worker(self) -> None:
        """Start the background outbox worker."""
        if self._running:
            logger.warning("Outbox worker already running")
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("AlertOutbox worker started")

    async def stop_worker(self) -> None:
        """Stop the background outbox worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("AlertOutbox worker stopped")

    async def _worker_loop(self) -> None:
        """Background loop that processes the outbox.

        Processes entries in priority order:
        1. PENDING entries (by session, then sequence)
        2. FAILED entries (respecting backoff)
        """
        while self._running:
            try:
                await self._process_outbox()
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Error in outbox worker: %s", exc)
                await asyncio.sleep(self._poll_interval)

    async def _process_outbox(self) -> None:
        """Process pending and failed entries in the outbox."""
        now = datetime.now(timezone.utc)

        # Get pending entries ordered by session/sequence
        pending = await self._get_entries_by_states([
            AlertOutboxState.PENDING,
        ], limit=10)

        # Get failed entries that are due for retry
        failed = await self._get_entries_by_states([
            AlertOutboxState.FAILED,
        ], limit=10)

        # Combine and process
        entries = pending + failed

        for entry in entries:
            # Check backoff for failed entries
            if entry.state == AlertOutboxState.FAILED and entry.last_attempt_at:
                last_attempt = datetime.fromisoformat(entry.last_attempt_at)
                backoff = entry.retry_backoff_base ** (entry.attempt_count - 1)
                if (now - last_attempt).total_seconds() < backoff:
                    continue  # Skip, not time for retry yet

            await self.dispatch_entry(entry)

    # --- Queries ---

    async def get_entry(self, entry_id: str) -> AlertOutboxEntry | None:
        """Get an outbox entry by ID."""
        async with self._session_maker() as session:
            row = await session.get(AlertOutboxRecord, entry_id)
            if row is None:
                return None
            return self._record_to_entry(row)

    async def get_entries_by_session(
        self,
        session_id: str,
        state: AlertOutboxState | None = None,
    ) -> list[AlertOutboxEntry]:
        """Get all entries in a session (for ordering)."""
        async with self._session_maker() as session:
            q = select(AlertOutboxRecord).where(
                AlertOutboxRecord.session_id == session_id
            )
            if state:
                q = q.where(AlertOutboxRecord.state == state.value)
            q = q.order_by(AlertOutboxRecord.sequence.asc())
            rows = (await session.execute(q)).scalars().all()
            return [self._record_to_entry(r) for r in rows]

    async def get_dead_letter_entries(self) -> list[AlertOutboxEntry]:
        """Get all dead-letter entries."""
        return await self._get_entries_by_states([AlertOutboxState.DEAD_LETTER])

    async def retry_dead_letter(self, entry_id: str) -> AlertOutboxEntry | None:
        """Retry a dead-letter entry (reset for processing).

        Args:
            entry_id: The dead-letter entry to retry.

        Returns:
            The reset entry, or None if not found or not in dead-letter state.
        """
        entry = await self.get_entry(entry_id)
        if entry is None or entry.state != AlertOutboxState.DEAD_LETTER:
            return None

        # Reset for retry
        entry.state = AlertOutboxState.PENDING
        entry.attempt_count = 0
        entry.error_message = None
        await self._persist_entry(entry)
        logger.info("Dead-letter entry %s reset for retry", entry_id)
        return entry

    # --- Persistence ---

    async def _persist_entry(self, entry: AlertOutboxEntry) -> None:
        """Persist entry to database."""
        async with self._session_maker() as session:
            # Check if entry exists
            existing = await session.get(AlertOutboxRecord, entry.entry_id)
            record = AlertOutboxRecord(
                entry_id=entry.entry_id,
                alert_type=entry.alert_type.value,
                alert_id=entry.alert_id,
                device_id=entry.device_id,
                session_id=entry.session_id,
                sequence=entry.sequence,
                title=entry.title,
                message=entry.message,
                severity=entry.severity,
                alert_metadata=entry.metadata,
                yanshee_skill=entry.yanshee_skill.value if entry.yanshee_skill else None,
                state=entry.state.value,
                created_at=datetime.fromisoformat(entry.created_at),
                dispatched_at=datetime.fromisoformat(entry.dispatched_at) if entry.dispatched_at else None,
                last_attempt_at=datetime.fromisoformat(entry.last_attempt_at) if entry.last_attempt_at else None,
                attempt_count=entry.attempt_count,
                max_retries=entry.max_retries,
                retry_backoff_base=entry.retry_backoff_base,
                error_message=entry.error_message,
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

    async def _get_entries_by_states(
        self,
        states: list[AlertOutboxState],
        limit: int = 100,
    ) -> list[AlertOutboxEntry]:
        """Get entries by states, ordered for processing."""
        async with self._session_maker() as session:
            state_values = [s.value for s in states]
            q = (
                select(AlertOutboxRecord)
                .where(AlertOutboxRecord.state.in_(state_values))
                .order_by(AlertOutboxRecord.session_id.asc(), AlertOutboxRecord.sequence.asc())
                .limit(limit)
            )
            rows = (await session.execute(q)).scalars().all()
            return [self._record_to_entry(r) for r in rows]

    def _record_to_entry(self, record: AlertOutboxRecord) -> AlertOutboxEntry:
        """Convert database record to AlertOutboxEntry."""
        yanshee_skill = record.yanshee_skill
        return AlertOutboxEntry(
            entry_id=record.entry_id,
            alert_type=AlertType(record.alert_type),
            alert_id=record.alert_id,
            device_id=record.device_id,
            session_id=record.session_id,
            sequence=record.sequence,
            title=record.title,
            message=record.message,
            severity=record.severity,
            metadata=record.alert_metadata or {},
            yanshee_skill=YansheeSkill(yanshee_skill) if yanshee_skill else None,
            state=AlertOutboxState(record.state),
            created_at=record.created_at.isoformat() if record.created_at else "",
            dispatched_at=record.dispatched_at.isoformat() if record.dispatched_at else None,
            last_attempt_at=record.last_attempt_at.isoformat() if record.last_attempt_at else None,
            attempt_count=record.attempt_count,
            max_retries=record.max_retries,
            retry_backoff_base=record.retry_backoff_base,
            error_message=record.error_message,
        )
