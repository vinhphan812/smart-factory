"""Durable event storage using SQLite + SQLAlchemy async."""

import json
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
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .models import CanonicalEvent, EventType

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class EventRecord(Base):
    """SQLAlchemy model for stored canonical events."""

    __tablename__ = "events"

    event_id = Column(String(36), primary_key=True)
    device_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    mqtt_topic = Column(String(256), nullable=False)
    mqtt_timestamp_ms = Column(Integer, nullable=False, default=0)
    ingested_at = Column(DateTime(timezone=True), nullable=False)
    sequence = Column(Integer, nullable=False, index=True)


class EventStore:
    """Async SQLite-backed event store with bounded retention."""

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

    async def init(self) -> None:
        """Create tables if they don't exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("EventStore initialized at %s", self._engine.url)

    async def insert(self, event: CanonicalEvent) -> None:
        """Store a canonical event."""
        await self.insert_dict(event.to_dict())

    async def insert_dict(self, event_dict: dict[str, Any]) -> None:
        """Store an event from its dict representation (used by the write queue)."""
        record = EventRecord(
            event_id=event_dict["event_id"],
            device_id=event_dict["device_id"],
            event_type=event_dict["event_type"],
            payload=event_dict["payload"],
            mqtt_topic=event_dict["mqtt_topic"],
            mqtt_timestamp_ms=event_dict["mqtt_timestamp_ms"],
            ingested_at=datetime.fromisoformat(event_dict["ingested_at"]),
            sequence=event_dict["sequence"],
        )
        async with self._session_maker() as session:
            session.add(record)
            await session.commit()

        # Enforce retention limit: delete oldest by sequence
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

    async def query(
        self,
        device_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query events with optional filters."""
        async with self._session_maker() as session:
            q = select(EventRecord).order_by(EventRecord.sequence.desc()).limit(limit)
            if device_id:
                q = q.where(EventRecord.device_id == device_id)
            if event_type:
                q = q.where(EventRecord.event_type == event_type)
            rows = (await session.execute(q)).scalars().all()
            return [
                {
                    "event_id": r.event_id,
                    "device_id": r.device_id,
                    "event_type": r.event_type,
                    "payload": r.payload,
                    "mqtt_topic": r.mqtt_topic,
                    "mqtt_timestamp_ms": r.mqtt_timestamp_ms,
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
                "ingested_at": row.ingested_at.isoformat(),
                "sequence": row.sequence,
            }

    async def count(self) -> int:
        """Return total event count."""
        async with self._session_maker() as session:
            return (await session.execute(select(func.count()).select_from(EventRecord))).scalar() or 0

    async def close(self) -> None:
        await self._engine.dispose()
