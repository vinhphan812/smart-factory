"""Durable event storage using SQLite + SQLAlchemy async.

Migration strategy (for backward compatibility with existing SQLite DBs):
  - init() runs _migrate_schema() before create_all() on every startup.
  - _migrate_schema() uses PRAGMA table_info to detect which columns exist
    and issues ADD COLUMN only for missing ones — idempotent and safe on
    both fresh and pre-migration DBs.
  - See iot-gateway/migrations/001_add_timing_columns.md for the documented
    schema change (informational reference; migration is applied by init()).

Sequence persistence:
  - _sequence is persisted in the gateway_metadata table so that the global
    event sequence survives process restarts.
  - On init(), load_sequence() reads the current sequence from DB; on insert,
    increment_and_persist() atomically increments and writes back.
  - This guarantees deterministic replay ordering across restarts.

Snapshot semantics:
  - /snapshot returns events sorted by sequence, up to limit (default 1000).
  - high_watermark = highest sequence in the store (last confirmed event).
  - per_device_latest = most recent event per device_id (by sequence).
  - Clients reconnecting should request /snapshot?since_sequence=<last_seq>
    and apply any newer events from WebSocket to get a consistent state.
  - Overflow: when retention limit is reached, oldest events are purged.
    Clients that missed events will see a gap in sequence numbers and should
    call /snapshot to re-synchronize.

Concurrency notes:
  - SQLite WAL mode is NOT used; aiosqlite handles concurrent async writes via
    its background thread pool and a 30-second busy-timeout.
  - snapshot() / high_watermark() / per_device_latest() are read-only and safe
    to call concurrently with writes — each opens its own session.
  - per_device_latest() is not atomic with high_watermark() in a single call;
    callers that need a consistent snapshot should use the /snapshot endpoint
    which queries both within the same logical response scope.
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    delete,
    func,
    select,
    text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .models import CanonicalEvent, EventType

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class EventRecord(Base):
    """SQLAlchemy model for stored canonical events.

    Includes timing metadata for staleness tracking and snapshot resync.
    """

    __tablename__ = "events"

    event_id = Column(String(36), primary_key=True)
    device_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    mqtt_topic = Column(String(256), nullable=False)
    mqtt_timestamp_ms = Column(Integer, nullable=False, default=0)
    # Timing metadata
    event_timestamp_ms = Column(Integer, nullable=False, default=0)
    received_at = Column(DateTime(timezone=True), nullable=False)
    latency_ms = Column(Integer, nullable=False, default=0)
    stale = Column(Integer, nullable=False, default=0)
    out_of_order = Column(Integer, nullable=False, default=0)
    ingested_at = Column(DateTime(timezone=True), nullable=False)
    sequence = Column(Integer, nullable=False, index=True)


class GatewayMetadata(Base):
    """Lightweight key/value store for gateway state that must survive restarts.

    Currently used for: sequence counter persistence.
    """

    __tablename__ = "gateway_metadata"

    key = Column(String(64), primary_key=True)
    value = Column(String(256), nullable=False)


class EventStore:
    """Async SQLite-backed event store with bounded retention and
    restart-proof sequence numbering."""

    _SEQUENCE_KEY = "global_sequence"

    def __init__(self, database_url: str, max_events: int = 10000) -> None:
        connect_args: dict[str, object] = {}
        if database_url.startswith("sqlite"):
            # Increase default timeout to handle concurrent async writes without
            # "database is locked" errors from aiosqlite's background threads.
            connect_args["timeout"] = 30
        self._engine = create_async_engine(
            database_url, echo=False, connect_args=connect_args
        )
        self._session_maker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._max_events = max_events

    # ------------------------------------------------------------------
    # Schema migration
    # ------------------------------------------------------------------

    async def _migrate_schema(self) -> None:
        """Add missing columns to existing events table without data loss.

        Uses PRAGMA table_info to detect columns that exist in the old schema.
        Only issues ALTER TABLE ADD COLUMN for missing ones. Safe to run on
        both fresh databases (columns already exist via create_all) and
        pre-migration databases (missing columns added here).
        """
        TIMING_COLUMNS = {
            "event_timestamp_ms": "INTEGER NOT NULL DEFAULT 0",
            "received_at": "TEXT NOT NULL DEFAULT ''",
            "latency_ms": "INTEGER NOT NULL DEFAULT 0",
            "stale": "INTEGER NOT NULL DEFAULT 0",
            "out_of_order": "INTEGER NOT NULL DEFAULT 0",
        }

        async with self._engine.begin() as conn:
            # Check if events table exists at all before trying to migrate it
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
            )
            table_exists = result.fetchone() is not None
            if not table_exists:
                logger.debug("events table does not exist yet — migration skipped")
            else:
                result = await conn.execute(text("PRAGMA table_info(events)"))
                existing = {row[1] for row in result.fetchall()}
                for col_name, col_def in TIMING_COLUMNS.items():
                    if col_name not in existing:
                        logger.info(
                            "Migrating events table: adding column %s", col_name
                        )
                        await conn.execute(
                            text(f"ALTER TABLE events ADD COLUMN {col_name} {col_def}")
                        )

            # Ensure gateway_metadata table exists (for sequence persistence)
            await conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS gateway_metadata ("
                    "  key TEXT PRIMARY KEY,"
                    "  value TEXT NOT NULL"
                    ")"
                )
            )

    async def init(self) -> None:
        """Create missing tables then migrate any pre-existing schema."""
        # Run create_all FIRST so the events table exists on fresh DBs.
        # On pre-existing DBs the table is already there and create_all is a no-op.
        # Then _migrate_schema() adds any missing columns idempotently.
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await self._migrate_schema()
        logger.info("EventStore initialized at %s", self._engine.url)

    # ------------------------------------------------------------------
    # Sequence persistence
    # ------------------------------------------------------------------

    async def _load_sequence(self) -> int:
        """Load the persisted sequence counter, or 0 if not yet set."""
        async with self._session_maker() as session:
            row = await session.get(GatewayMetadata, self._SEQUENCE_KEY)
            if row is None:
                return 0
            try:
                return int(row.value)
            except (ValueError, TypeError):
                return 0

    async def _save_sequence(self, seq: int) -> None:
        """Persist the sequence counter."""
        async with self._session_maker() as session:
            row = GatewayMetadata(key=self._SEQUENCE_KEY, value=str(seq))
            session.merge(row)
            await session.commit()

    async def _increment_sequence(self) -> int:
        """Atomically increment and persist the sequence counter.

        Uses a single UPDATE with RETURNING wrapped in an explicit begin/commit
        so concurrent callers each get a distinct value without a race.
        """
        async with self._session_maker() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        "UPDATE gateway_metadata "
                        "SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) "
                        "WHERE key = :key "
                        "RETURNING CAST(value AS INTEGER)"
                    ),
                    {"key": self._SEQUENCE_KEY},
                )
                row = result.fetchone()
                if row is not None:
                    return row[0]

            # Key does not exist — INSERT initial value 1
            session.add(GatewayMetadata(key=self._SEQUENCE_KEY, value="1"))
            await session.commit()
            return 1

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def insert(self, event: CanonicalEvent) -> None:
        """Store a canonical event."""
        await self.insert_dict(event.to_dict())

    async def insert_dict(self, event_dict: dict[str, Any]) -> None:
        """Store an event from its dict representation (used by the write queue).

        The sequence number is loaded from and persisted to gateway_metadata
        so that ordering is deterministic across restarts.
        """
        # Parse received_at: prefer explicit field, fallback to ingested_at
        received_at_str = event_dict.get("received_at", event_dict["ingested_at"])
        if isinstance(received_at_str, str):
            received_at = datetime.fromisoformat(received_at_str)
        else:
            received_at = datetime.fromisoformat(event_dict["ingested_at"])

        # Use the normalizer-provided sequence if present (deterministic, in-order).
        # Fall back to persisted counter only when sequence is missing (e.g. direct
        # insert_dict calls without going through the normalizer).
        sequence = event_dict.get("sequence")
        if sequence is None or sequence == 0:
            # Single atomic transaction: read, increment, write + insert
            sequence = await self._increment_sequence()

        record = EventRecord(
            event_id=event_dict["event_id"],
            device_id=event_dict["device_id"],
            event_type=event_dict["event_type"],
            payload=event_dict["payload"],
            mqtt_topic=event_dict["mqtt_topic"],
            mqtt_timestamp_ms=event_dict.get("mqtt_timestamp_ms", 0),
            event_timestamp_ms=event_dict.get(
                "event_timestamp_ms", event_dict.get("timestamp", 0)
            ),
            received_at=received_at,
            latency_ms=event_dict.get("latency_ms", 0),
            stale=int(bool(event_dict.get("stale", False))),
            out_of_order=int(bool(event_dict.get("out_of_order", False))),
            ingested_at=datetime.fromisoformat(event_dict["ingested_at"]),
            sequence=sequence,
        )
        async with self._session_maker() as session:
            session.add(record)
            await session.commit()

        # Enforce retention limit: delete oldest by sequence
        await self._prune_old_events()

    async def _prune_old_events(self) -> None:
        """Delete oldest events when retention limit is exceeded."""
        async with self._session_maker() as session:
            count_q = select(func.count()).select_from(EventRecord)
            total = (await session.execute(count_q)).scalar() or 0
            if total > self._max_events:
                excess = total - self._max_events
                del_q = (
                    delete(EventRecord)
                    .where(
                        EventRecord.sequence.in_(
                            select(EventRecord.sequence)
                            .order_by(EventRecord.sequence.asc())
                            .limit(excess)
                        )
                    )
                )
                await session.execute(del_q)
                await session.commit()
                logger.debug("Purged %d old events (retention=%d)", excess, self._max_events)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def query(
        self,
        device_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        since_sequence: int = 0,
    ) -> list[dict[str, Any]]:
        """Query events with optional filters and sequence cursor.

        Args:
            device_id: Filter by device.
            event_type: Filter by event type.
            limit: Maximum events to return.
            since_sequence: Return only events with sequence > this value.
                           Use 0 to return all (no lower bound).
        """
        async with self._session_maker() as session:
            q = select(EventRecord).order_by(EventRecord.sequence.asc())
            if since_sequence > 0:
                q = q.where(EventRecord.sequence > since_sequence)
            if device_id:
                q = q.where(EventRecord.device_id == device_id)
            if event_type:
                q = q.where(EventRecord.event_type == event_type)
            q = q.limit(limit)
            rows = (await session.execute(q)).scalars().all()
            return [
                {
                    "event_id": r.event_id,
                    "device_id": r.device_id,
                    "event_type": r.event_type,
                    "payload": r.payload,
                    "mqtt_topic": r.mqtt_topic,
                    "mqtt_timestamp_ms": r.mqtt_timestamp_ms,
                    "event_timestamp_ms": r.event_timestamp_ms,
                    "received_at": r.received_at.isoformat() if r.received_at else r.ingested_at.isoformat(),
                    "latency_ms": r.latency_ms,
                    "stale": bool(r.stale),
                    "out_of_order": bool(r.out_of_order),
                    "ingested_at": r.ingested_at.isoformat(),
                    "sequence": r.sequence,
                }
                for r in rows
            ]

    async def get(self, event_id: str) -> dict[str, Any] | None:
        """Get a single event by ID."""
        async with self._session_maker() as session:
            row = (
                await session.execute(
                    select(EventRecord).where(EventRecord.event_id == event_id)
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return {
                "event_id": row.event_id,
                "device_id": row.device_id,
                "event_type": row.event_type,
                "payload": row.payload,
                "mqtt_topic": row.mqtt_topic,
                "mqtt_timestamp_ms": row.mqtt_timestamp_ms,
                "event_timestamp_ms": row.event_timestamp_ms,
                "received_at": row.received_at.isoformat() if row.received_at else row.ingested_at.isoformat(),
                "latency_ms": row.latency_ms,
                "stale": bool(row.stale),
                "out_of_order": bool(row.out_of_order),
                "ingested_at": row.ingested_at.isoformat(),
                "sequence": row.sequence,
            }

    async def high_watermark(self) -> int:
        """Return the highest sequence number in the store (last confirmed event).

        Returns 0 if the store is empty.
        """
        async with self._session_maker() as session:
            row = await session.execute(
                select(func.max(EventRecord.sequence))
            )
            return row.scalar() or 0

    async def per_device_latest(self) -> dict[str, dict[str, Any] | None]:
        """Return the most recent event per device_id (by highest sequence).

        Useful for snapshot to give clients a current-state overview without
        replaying the full history.
        """
        async with self._session_maker() as session:
            # Subquery: max sequence per device
            subq = (
                select(
                    EventRecord.device_id,
                    func.max(EventRecord.sequence).label("max_seq"),
                )
                .group_by(EventRecord.device_id)
                .subquery()
            )
            q = (
                select(EventRecord)
                .join(
                    subq,
                    (EventRecord.device_id == subq.c.device_id)
                    & (EventRecord.sequence == subq.c.max_seq),
                )
                .order_by(EventRecord.sequence.desc())
            )
            rows = (await session.execute(q)).scalars().all()
            result: dict[str, dict[str, Any] | None] = {}
            for r in rows:
                result[r.device_id] = await self.get(r.event_id)
            return result

    async def count(self) -> int:
        """Return total event count."""
        async with self._session_maker() as session:
            return (await session.execute(select(func.count()).select_from(EventRecord))).scalar() or 0

    async def close(self) -> None:
        await self._engine.dispose()
