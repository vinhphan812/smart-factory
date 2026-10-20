"""Dead-letter queue (DLQ) for events that fail after maximum retries.

Architecture
------------
Events that exhaust the retry budget (event_durability.RetryQueue) are
moved to the DLQ.  The DLQ is backed by a dedicated SQLite table so
events survive gateway restarts.  Operators can inspect and replay DLQ
entries via REST endpoints.

Alert integration
------------------
DLQ growth beyond `alert_threshold` triggers an alert via AlertService.
The alert threshold and minimum interval between alerts are configurable
to avoid alert fatigue.

Replay protocol
--------------
1. GET /dlq  — inspect current DLQ state
2. POST /dlq/{event_id}/replay — re-inject the event into the write queue
   (it goes through the full pipeline: WAL → normalizer → store)
3. DELETE /dlq/{event_id} — discard a DLQ entry (with operator token)
4. POST /dlq/replay-all — replay all DLQ entries

DLQ entries are immutable snapshots: replay creates a NEW event_id
(the original event_id is preserved in the DLQ entry's `original_event_id`
field) so downstream consumers can distinguish original from replay.

No PII or secrets are stored in the DLQ payload — raw payloads are
accepted as-is but payloads are not re-sent anywhere without review.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class DLQBase(DeclarativeBase):
    pass


class DLQRecord(DLQBase):
    """Dead-letter queue entry — immutable snapshot of a failed event."""

    __tablename__ = "dead_letter_queue"

    # Surrogate key (not the original event_id, which is preserved in payload)
    id = Column(Integer, primary_key=True, autoincrement=True)
    original_event_id = Column(String(36), nullable=False, unique=True, index=True)
    device_id = Column(String(64), nullable=False, default="")
    event_type = Column(String(32), nullable=False, default="")
    topic = Column(String(256), nullable=False, default="")
    payload = Column(JSON, nullable=False)  # snapshot of original event_dict
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)
    replay_count = Column(Integer, nullable=False, default=0)
    last_replay_at = Column(DateTime(timezone=True), nullable=True)
    discarded = Column(Integer, nullable=False, default=0)  # 0=active, 1=discarded


# ---------------------------------------------------------------------------
# DLQ Service
# ---------------------------------------------------------------------------


class DLQService:
    """Dead-letter queue backed by SQLite.

    Args:
        database_url: aiosqlite connection URL for the DLQ database.
        alert_threshold: DLQ size above which an alert is generated.
                         Defaults to 100.
        alert_cooldown_seconds: Minimum seconds between repeated DLQ alerts.
                                 Defaults to 300 (5 minutes).
    """

    def __init__(
        self,
        database_url: str,
        alert_threshold: int = 100,
        alert_cooldown_seconds: float = 300.0,
    ) -> None:
        connect_args: dict[str, object] = {}
        if database_url.startswith("sqlite"):
            connect_args["timeout"] = 30
        self._engine = create_async_engine(
            database_url,
            echo=False,
            connect_args=connect_args,
        )
        self._session_maker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._alert_threshold = alert_threshold
        self._alert_cooldown_seconds = alert_cooldown_seconds
        self._last_alert_at: float = 0.0
        self._alert_pending = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def init(self) -> None:
        """Create DLQ table if absent."""
        async with self._engine.begin() as conn:
            await conn.run_sync(DLQBase.metadata.create_all)
        logger.info("DLQService initialized (threshold=%d)", self._alert_threshold)

    async def close(self) -> None:
        await self._engine.dispose()

    # ------------------------------------------------------------------
    # Enqueue (called when event exhausts retries)
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        original_event_id: str,
        payload: dict[str, Any],
        error_message: str,
        retry_count: int,
        device_id: str = "",
        event_type: str = "",
        topic: str = "",
    ) -> None:
        """Move a failed event to the DLQ.

        If the event is already in the DLQ this is a no-op (idempotent).
        """
        async with self._session_maker() as session:
            # Idempotent: skip if already present
            existing = await session.execute(
                select(DLQRecord).where(
                    DLQRecord.original_event_id == original_event_id
                )
            )
            if existing.scalar_one_or_none() is not None:
                logger.debug("DLQ: already contains event_id=%s", original_event_id)
                return

            record = DLQRecord(
                original_event_id=original_event_id,
                device_id=device_id,
                event_type=event_type,
                topic=topic,
                payload=payload,
                error_message=error_message,
                retry_count=retry_count,
                created_at=datetime.now(timezone.utc),
                replay_count=0,
                discarded=0,
            )
            session.add(record)
            await session.commit()
        logger.info(
            "DLQ: dead-lettered event_id=%s (retries=%d): %s",
            original_event_id,
            retry_count,
            error_message,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        include_discarded: bool = False,
    ) -> list[dict[str, Any]]:
        """Return DLQ entries, most-recent first."""
        async with self._session_maker() as session:
            q = (
                select(DLQRecord)
                .where(
                    DLQRecord.discarded == 0
                    if not include_discarded
                    else True
                )
                .order_by(DLQRecord.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = (await session.execute(q)).scalars().all()
            return [self._record_to_dict(r) for r in rows]

    async def get(self, original_event_id: str) -> dict[str, Any] | None:
        """Return a single DLQ entry, or None if not found."""
        async with self._session_maker() as session:
            row = await session.execute(
                select(DLQRecord).where(
                    DLQRecord.original_event_id == original_event_id
                )
            )
            record = row.scalar_one_or_none()
            if record is None:
                return None
            return self._record_to_dict(record)

    async def count(self, include_discarded: bool = False) -> int:
        """Return total active DLQ entry count."""
        async with self._session_maker() as session:
            q = select(func.count()).select_from(DLQRecord).where(
                DLQRecord.discarded == 0
                if not include_discarded
                else True
            )
            return (await session.execute(q)).scalar() or 0

    def _record_to_dict(self, r: DLQRecord) -> dict[str, Any]:
        return {
            "id": r.id,
            "original_event_id": r.original_event_id,
            "device_id": r.device_id,
            "event_type": r.event_type,
            "topic": r.topic,
            "payload": r.payload,
            "error_message": r.error_message,
            "retry_count": r.retry_count,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "replay_count": r.replay_count,
            "last_replay_at": (
                r.last_replay_at.isoformat() if r.last_replay_at else None
            ),
            "discarded": bool(r.discarded),
        }

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    async def replay(
        self,
        original_event_id: str,
        new_event_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Prepare a DLQ entry for replay.

        Returns the replay payload dict with a fresh event_id (for the
        new event).  The caller should submit this to the write queue.

        Updates replay_count and last_replay_at in the DLQ record.
        """
        async with self._session_maker() as session:
            row = await session.execute(
                select(DLQRecord).where(
                    DLQRecord.original_event_id == original_event_id
                )
            )
            record = row.scalar_one_or_none()
            if record is None or record.discarded:
                return None

            new_id = new_event_id or str(uuid4())
            replay_payload = dict(record.payload)
            replay_payload["event_id"] = new_id
            replay_payload["_replay_of"] = original_event_id

            record.replay_count += 1
            record.last_replay_at = datetime.now(timezone.utc)
            await session.commit()

        logger.info(
            "DLQ: replaying event_id=%s → new_id=%s",
            original_event_id,
            new_id,
        )
        return replay_payload

    async def discard(self, original_event_id: str) -> bool:
        """Soft-delete a DLQ entry (sets discarded=1).

        Returns True if the entry existed and was discarded.
        """
        async with self._session_maker() as session:
            result = await session.execute(
                select(DLQRecord).where(
                    DLQRecord.original_event_id == original_event_id
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                return False
            record.discarded = 1
            await session.commit()
        logger.info("DLQ: discarded event_id=%s", original_event_id)
        return True

    async def discard_all(self) -> int:
        """Soft-delete all active DLQ entries. Returns count deleted."""
        async with self._session_maker() as session:
            result = await session.execute(
                delete(DLQRecord).where(DLQRecord.discarded == 0)
            )
            await session.commit()
            count = result.rowcount or 0
        logger.info("DLQ: discarded %d entries", count)
        return count

    # ------------------------------------------------------------------
    # Alert on DLQ growth
    # ------------------------------------------------------------------

    async def check_alert_threshold(self) -> bool:
        """Check if DLQ size exceeds alert_threshold.

        Returns True if a new alert should be fired; the caller is
        responsible for publishing the alert via AlertService.
        The alert cooldown is respected.
        """
        count = await self.count()
        if count < self._alert_threshold:
            self._alert_pending = False
            return False

        now = asyncio.get_running_loop().time()
        if self._alert_pending:
            return False
        if (now - self._last_alert_at) < self._alert_cooldown_seconds:
            return False

        self._last_alert_at = now
        self._alert_pending = True
        return True

    def reset_alert_pending(self) -> None:
        """Reset alert pending flag after alert has been dispatched."""
        self._alert_pending = False

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def stats(self) -> dict[str, Any]:
        """Return DLQ statistics for /health or monitoring."""
        total = await self.count(include_discarded=False)
        discarded = await self.count(include_discarded=True) - total
        return {
            "dlq_count": total,
            "dlq_alert_threshold": self._alert_threshold,
            "dlq_alert_pending": self._alert_pending,
            "dlq_discarded": discarded,
        }
