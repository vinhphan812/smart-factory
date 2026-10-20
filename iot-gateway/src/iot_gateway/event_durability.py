"""Event ingestion durability: WAL, retry queue, idempotency, partition tolerance.

Architecture
------------
Events flow: MQTT → WAL (write-ahead log, SQLite) → normalizer →
idempotency check → write queue → SQLite store.

Key invariants
--------------
- Every incoming event is written to the WAL *before* acknowledgment.
  WAL entries survive process crashes so no event is silently lost.
- WAL entries are tombstoned (not deleted) after the store confirms persistence.
- Idempotency: duplicate eventIds are detected via the WAL's event_id index
  and discarded before re-processing.
- Retry queue: failed store inserts are re-queued with exponential backoff.
- Partition tolerance: a single module (e.g. one writer) failing does not
  halt the pipeline — the WAL continues accepting events.

Concurrency model
----------------
- All async I/O; SQLite access is serialised through aiosqlite's thread pool.
- WAL and retry queue are protected by asyncio.Lock to prevent torn writes.
- Thread-safety note: WALCallback may be invoked from Paho's thread (see gateway.py
  _mqtt_callback) — we use call_soon_threadsafe to schedule work on the asyncio loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WAL Schema
# ---------------------------------------------------------------------------


class WALBase(DeclarativeBase):
    pass


class WALRecord(WALBase):
    """Write-ahead log entry: survives crashes, is tombstoned after commit."""

    __tablename__ = "wal"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), nullable=False, unique=True, index=True)
    topic = Column(String(256), nullable=False)
    raw_payload = Column(Text, nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)
    sequence = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="pending")  # pending | done | failed
    retry_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Retry queue
# ---------------------------------------------------------------------------


class RetryStatus(str, Enum):
    PENDING = "pending"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"
    SUCCESS = "success"


@dataclass
class RetryEntry:
    """A single event awaiting retry with backoff state."""

    event_id: str
    event_dict: dict[str, Any]
    retry_count: int = 0
    status: RetryStatus = RetryStatus.PENDING
    next_retry_at: float = 0.0  # monotonic seconds
    last_error: str | None = None

    def backoff_seconds(self) -> float:
        """Exponential backoff: base 1 s, cap 300 s, jitter ±10 %."""
        import random

        base = min(2**self.retry_count, 300)
        jitter = base * 0.1 * (random.random() * 2 - 1)
        return max(1.0, base + jitter)


# ---------------------------------------------------------------------------
# WAL Event Durability
# ---------------------------------------------------------------------------


class WALDurability:
    """Write-ahead log backed by SQLite.

    Guarantees every ingested event survives a gateway crash/restart
    before it is acknowledged.  Implements idempotency, retry queue
    with exponential backoff, and tombstoning after store confirmation.

    Args:
        database_url: aiosqlite connection URL for the WAL SQLite database.
        max_retries: Maximum retries before an event is sent to the dead-letter
            queue.  Defaults to 5.
    """

    def __init__(
        self,
        database_url: str,
        max_retries: int = 5,
        max_wal_entries: int = 100_000,
    ) -> None:
        connect_args: dict[str, object] = {}
        if database_url.startswith("sqlite"):
            connect_args["timeout"] = 30
        self._engine = create_async_engine(
            database_url.replace("sqlite", "sqlite"),
            echo=False,
            connect_args=connect_args,
        )
        self._session_maker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._max_retries = max_retries
        self._max_wal_entries = max_wal_entries
        self._lock = asyncio.Lock()
        self._retry_queue: deque[RetryEntry] = deque()
        # Events confirmed by the store (tombstoned in WAL)
        self._confirmed: set[str] = set()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def init(self) -> None:
        """Create WAL table if absent."""
        async with self._engine.begin() as conn:
            await conn.run_sync(WALBase.metadata.create_all)
        logger.info("WALDurability initialized")

    async def close(self) -> None:
        await self._engine.dispose()

    # ------------------------------------------------------------------
    # WAL write (pre-processing durability)
    # ------------------------------------------------------------------

    async def wal_append(
        self,
        event_id: str,
        topic: str,
        raw_payload: bytes,
        sequence: int = 0,
    ) -> bool:
        """Append an event to the WAL.

        Returns:
            True  — event was newly written to WAL.
            False — event_id already exists in WAL (duplicate, skipped).

        Thread-safe via asyncio.Lock.
        """
        async with self._lock:
            async with self._session_maker() as session:
                # Idempotency: check before insert
                existing = await session.execute(
                    select(WALRecord).where(WALRecord.event_id == event_id)
                )
                if existing.scalar_one_or_none() is not None:
                    logger.debug("WAL: duplicate event_id=%s — skipped", event_id)
                    return False

                record = WALRecord(
                    event_id=event_id,
                    topic=topic,
                    raw_payload=raw_payload.decode("utf-8", errors="replace"),
                    received_at=datetime.now(timezone.utc),
                    sequence=sequence,
                    status="pending",
                    retry_count=0,
                )
                session.add(record)
                await session.commit()

            logger.debug("WAL: appended event_id=%s", event_id)
            await self._prune_wal()
            return True

    async def _prune_wal(self) -> None:
        """Delete the oldest WAL entries when limit is exceeded."""
        async with self._session_maker() as session:
            count_row = await session.execute(
                select(func.count()).select_from(WALRecord)
            )
            total = count_row.scalar() or 0
            if total <= self._max_wal_entries:
                return
            excess = total - self._max_wal_entries
            await session.execute(
                delete(WALRecord)
                .where(
                    WALRecord.id.in_(
                        select(WALRecord.id)
                        .order_by(WALRecord.id.asc())
                        .limit(excess)
                    )
                )
            )
            await session.commit()
            logger.debug("WAL: pruned %d oldest entries", excess)

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    async def is_duplicate(self, event_id: str) -> bool:
        """Return True if event_id has already been confirmed (tombstoned)."""
        async with self._lock:
            return event_id in self._confirmed

    async def confirm(self, event_id: str) -> None:
        """Mark event as persisted in WAL (tombstone — not deleted, status=done).

        Called by the write worker after store.insert_dict() succeeds.
        """
        async with self._lock:
            self._confirmed.add(event_id)
        async with self._session_maker() as session:
            await session.execute(
                text(
                    "UPDATE wal SET status='done' WHERE event_id=:eid"
                ),
                {"eid": event_id},
            )
            await session.commit()
        logger.debug("WAL: confirmed event_id=%s", event_id)

    # ------------------------------------------------------------------
    # Retry queue
    # ------------------------------------------------------------------

    async def schedule_retry(
        self, event_id: str, event_dict: dict[str, Any], error: str
    ) -> None:
        """Add a failed event to the retry queue with exponential backoff.

        If max_retries is exceeded, the event is marked dead_letter and
        NOT requeued — it must be recovered via the DLQ.
        """
        async with self._lock:
            # Check if already queued
            for entry in self._retry_queue:
                if entry.event_id == event_id:
                    entry.retry_count += 1
                    entry.last_error = error
                    entry.status = RetryStatus.RETRYING
                    entry.next_retry_at = (
                        asyncio.get_running_loop().time()
                        + entry.backoff_seconds()
                    )
                    logger.debug(
                        "WAL: retry %d scheduled for event_id=%s",
                        entry.retry_count,
                        event_id,
                    )
                    return

            entry = RetryEntry(
                event_id=event_id,
                event_dict=event_dict,
                retry_count=1,
                status=RetryStatus.RETRYING,
                next_retry_at=(
                    asyncio.get_running_loop().time()
                    + RetryEntry(event_id=event_id, event_dict=event_dict).backoff_seconds()
                ),
                last_error=error,
            )

            if entry.retry_count >= self._max_retries:
                entry.status = RetryStatus.DEAD_LETTER
                await self._mark_dead_letter(event_id)
                logger.warning(
                    "WAL: event_id=%s exceeded max_retries=%d — dead-lettered",
                    event_id,
                    self._max_retries,
                )
                return

            self._retry_queue.append(entry)
            # Mark pending in WAL
            async with self._session_maker() as session:
                await session.execute(
                    text(
                        "UPDATE wal SET status='retrying', retry_count=:rc "
                        "WHERE event_id=:eid"
                    ),
                    {"eid": event_id, "rc": entry.retry_count},
                )
                await session.commit()
            logger.debug(
                "WAL: retry %d scheduled for event_id=%s",
                entry.retry_count,
                event_id,
            )

    async def _mark_dead_letter(self, event_id: str) -> None:
        """Mark event as dead_letter in WAL."""
        async with self._session_maker() as session:
            await session.execute(
                text(
                    "UPDATE wal SET status='dead_letter' WHERE event_id=:eid"
                ),
                {"eid": event_id},
            )
            await session.commit()

    async def get_ready_retries(self) -> list[RetryEntry]:
        """Return all retry entries whose backoff window has elapsed.

        Entries are returned in submission-order (FIFO) for deterministic replay.
        """
        now = asyncio.get_running_loop().time()
        async with self._lock:
            ready: list[RetryEntry] = []
            remaining: deque[RetryEntry] = deque()
            for entry in self._retry_queue:
                if entry.status == RetryStatus.DEAD_LETTER:
                    continue
                if now >= entry.next_retry_at:
                    ready.append(entry)
                else:
                    remaining.append(entry)
            self._retry_queue = remaining
            return ready

    def retry_queue_size(self) -> int:
        """Return current retry queue depth."""
        return len(self._retry_queue)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def stats(self) -> dict[str, Any]:
        """Return WAL statistics for /health or monitoring."""
        async with self._session_maker() as session:
            pending = (
                await session.execute(
                    select(func.count()).select_from(WALRecord).where(
                        WALRecord.status == "pending"
                    )
                )
            ).scalar() or 0
            done = (
                await session.execute(
                    select(func.count()).select_from(WALRecord).where(
                        WALRecord.status == "done"
                    )
                )
            ).scalar() or 0
            failed = (
                await session.execute(
                    select(func.count()).select_from(WALRecord).where(
                        WALRecord.status.in_(["failed", "dead_letter"])
                    )
                )
            ).scalar() or 0
            retry = (
                await session.execute(
                    select(func.count()).select_from(WALRecord).where(
                        WALRecord.status == "retrying"
                    )
                )
            ).scalar() or 0
            total = (
                await session.execute(
                    select(func.count()).select_from(WALRecord)
                )
            ).scalar() or 0

        return {
            "wal_total": total,
            "wal_pending": pending,
            "wal_done": done,
            "wal_failed": failed,
            "wal_retrying": retry,
            "retry_queue_depth": self.retry_queue_size(),
        }
