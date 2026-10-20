"""OTA control plane — job management, ESP32 OTA integration, progress tracking.

OTA flow (based on ADR-0007 signed HTTPS OTA, ADR-0008 event-driven OtaManager):
  1. Operator/agent creates an OTA job via the API (create_ota_job)
  2. Job is scheduled; gateway exposes an HTTP OTA endpoint that devices poll/fetch
     their assigned firmware from
  3. Device reports progress via progress callbacks → stored in job record
  4. Job transitions: pending → in_progress → completed | failed | cancelled

The HTTP OTA endpoint at GET /ota/firmware/<job_id>/<device_id> serves the firmware
binary from the configured storage path. Devices are authenticated via a short-lived
OTA token issued alongside the job.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    JSON,
    select,
    func,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .event_store import Base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OTA settings
# ---------------------------------------------------------------------------

OTA_TOKEN_TTL_MINUTES = 60
OTA_DEFAULT_TIMEOUT_SECONDS = 600  # 10 minutes default per-job timeout
OTA_CHUNK_SIZE = 4096  # bytes; ESP32 flash alignment

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OtaJobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OtaJobTarget(str, Enum):
    ESP32_BRIDGE = "esp32_bridge"
    MEGA_REFERENCE = "mega_reference"
    SIMULATOR = "simulator"


# ---------------------------------------------------------------------------
# SQLAlchemy model
# ---------------------------------------------------------------------------

class OtaJob(Base):
    """SQLAlchemy model for OTA job records."""

    __tablename__ = "ota_jobs"

    job_id = Column(String(64), primary_key=True)  # "ota-<uuid>"
    target_device_ids = Column(JSON, nullable=False, default=list)  # list[str]
    target_type = Column(String(32), nullable=False)  # OtaJobTarget
    firmware_version = Column(String(64), nullable=False)
    firmware_url = Column(String(512), nullable=False)  # local or remote URL
    firmware_sha256 = Column(String(64), nullable=True)  # hex digest
    firmware_size_bytes = Column(BigInteger, nullable=True)
    status = Column(String(16), nullable=False, default=OtaJobStatus.PENDING.value)
    schedule_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    modified_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(128), nullable=True)
    notes = Column(Text, nullable=True)
    # Per-device progress: dict[device_id, dict with pct, bytes, error]
    progress = Column(JSON, nullable=False, default=dict)
    timeout_seconds = Column(Integer, nullable=False, default=OTA_DEFAULT_TIMEOUT_SECONDS)


class OtaToken(Base):
    """Short-lived OTA access token for device authentication."""

    __tablename__ = "ota_tokens"

    token = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    device_id = Column(String(64), nullable=False, index=True)
    issued_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

@dataclass
class OtaJobRecord:
    """In-memory OTA job record."""

    job_id: str
    target_device_ids: list[str]
    target_type: OtaJobTarget | str
    firmware_version: str
    firmware_url: str
    firmware_sha256: str | None = None
    firmware_size_bytes: int | None = None
    status: OtaJobStatus | str = OtaJobStatus.PENDING
    schedule_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime | None = None
    created_by: str | None = None
    notes: str | None = None
    progress: dict[str, dict[str, Any]] = field(default_factory=dict)
    timeout_seconds: int = OTA_DEFAULT_TIMEOUT_SECONDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "target_device_ids": self.target_device_ids,
            "target_type": self.target_type,
            "firmware_version": self.firmware_version,
            "firmware_url": self.firmware_url,
            "firmware_sha256": self.firmware_sha256,
            "firmware_size_bytes": self.firmware_size_bytes,
            "status": self.status,
            "schedule_at": self.schedule_at.isoformat() if self.schedule_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "created_by": self.created_by,
            "notes": self.notes,
            "progress": self.progress,
            "timeout_seconds": self.timeout_seconds,
        }

    def to_summary_dict(self) -> dict[str, Any]:
        """Compact summary for list responses."""
        return {
            "job_id": self.job_id,
            "target_type": self.target_type,
            "firmware_version": self.firmware_version,
            "status": self.status,
            "target_count": len(self.target_device_ids),
            "schedule_at": self.schedule_at.isoformat() if self.schedule_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DeviceProgress:
    """Per-device OTA progress entry."""
    device_id: str
    job_id: str
    status: str  # "downloading", "flashing", "verifying", "completed", "failed"
    bytes_downloaded: int = 0
    bytes_total: int = 0
    percentage: int = 0
    error: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "job_id": self.job_id,
            "status": self.status,
            "bytes_downloaded": self.bytes_downloaded,
            "bytes_total": self.bytes_total,
            "percentage": self.percentage,
            "error": self.error,
            "updated_at": self.updated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# OTA Control Service
# ---------------------------------------------------------------------------

class OtaControl:
    """OTA job management service backed by SQLite."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_job(row: OtaJob) -> OtaJobRecord:
        return OtaJobRecord(
            job_id=row.job_id,
            target_device_ids=row.target_device_ids or [],
            target_type=row.target_type,
            firmware_version=row.firmware_version,
            firmware_url=row.firmware_url,
            firmware_sha256=row.firmware_sha256,
            firmware_size_bytes=row.firmware_size_bytes,
            status=row.status,
            schedule_at=row.schedule_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            created_at=row.created_at,
            modified_at=row.modified_at,
            created_by=row.created_by,
            notes=row.notes,
            progress=row.progress or {},
            timeout_seconds=row.timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    async def create_job(
        self,
        target_device_ids: list[str],
        target_type: str,
        firmware_version: str,
        firmware_url: str,
        firmware_sha256: str | None = None,
        firmware_size_bytes: int | None = None,
        schedule_at: datetime | None = None,
        created_by: str | None = None,
        notes: str | None = None,
        timeout_seconds: int = OTA_DEFAULT_TIMEOUT_SECONDS,
    ) -> OtaJobRecord:
        """Create and persist a new OTA job.

        Job starts in PENDING state. Transition to IN_PROGRESS happens
        when schedule_at is reached or start() is called explicitly.
        """
        now = datetime.now(timezone.utc)
        job_id = f"ota-{uuid.uuid4().hex[:12]}"

        row = OtaJob(
            job_id=job_id,
            target_device_ids=target_device_ids,
            target_type=target_type,
            firmware_version=firmware_version,
            firmware_url=firmware_url,
            firmware_sha256=firmware_sha256,
            firmware_size_bytes=firmware_size_bytes,
            status=OtaJobStatus.PENDING.value,
            schedule_at=schedule_at,
            created_at=now,
            modified_at=now,
            created_by=created_by,
            notes=notes,
            progress={},
            timeout_seconds=timeout_seconds,
        )

        async with self._session_maker() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)

        logger.info(
            "OTA job created: job_id=%s targets=%s version=%s",
            job_id, target_device_ids, firmware_version,
        )
        return self._row_to_job(row)

    async def get_job(self, job_id: str) -> OtaJobRecord | None:
        """Return a job by ID, or None if not found."""
        async with self._session_maker() as session:
            row = await session.get(OtaJob, job_id)
            if row is None:
                return None
            return self._row_to_job(row)

    async def list_jobs(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[OtaJobRecord], int]:
        """Return OTA jobs matching filters and total count."""
        async with self._session_maker() as session:
            q = select(OtaJob).order_by(OtaJob.created_at.desc())
            count_q = select(func.count()).select_from(OtaJob)

            if status:
                q = q.where(OtaJob.status == status)
                count_q = count_q.where(OtaJob.status == status)

            total = (await session.execute(count_q)).scalar() or 0
            q = q.offset(offset).limit(limit)
            rows = (await session.execute(q)).scalars().all()
            return [self._row_to_job(r) for r in rows], int(total)

    async def start_job(self, job_id: str) -> OtaJobRecord | None:
        """Transition a PENDING job to IN_PROGRESS.

        Issues OTA tokens for each target device.
        """
        now = datetime.now(timezone.utc)
        async with self._session_maker() as session:
            row = await session.get(OtaJob, job_id)
            if row is None:
                return None
            if row.status not in (OtaJobStatus.PENDING.value,):
                raise ValueError(f"Job {job_id!r} cannot be started (status={row.status!r})")

            row.status = OtaJobStatus.IN_PROGRESS.value
            row.started_at = now
            row.modified_at = now

            # Issue OTA tokens for each target device
            for device_id in (row.target_device_ids or []):
                token = secrets.token_urlsafe(32)
                expires = now + timedelta(minutes=OTA_TOKEN_TTL_MINUTES)
                tok_row = OtaToken(
                    token=token,
                    job_id=job_id,
                    device_id=device_id,
                    issued_at=now,
                    expires_at=expires,
                )
                session.add(tok_row)

            await session.commit()
            await session.refresh(row)

        logger.info("OTA job started: %s", job_id)
        return self._row_to_job(row)

    async def cancel_job(self, job_id: str) -> OtaJobRecord | None:
        """Cancel a pending or in-progress job."""
        now = datetime.now(timezone.utc)
        async with self._session_maker() as session:
            row = await session.get(OtaJob, job_id)
            if row is None:
                return None
            if row.status in (OtaJobStatus.COMPLETED.value, OtaJobStatus.CANCELLED.value):
                raise ValueError(f"Job {job_id!r} is already terminal (status={row.status!r})")

            row.status = OtaJobStatus.CANCELLED.value
            row.completed_at = now
            row.modified_at = now
            await session.commit()
            await session.refresh(row)

        logger.info("OTA job cancelled: %s", job_id)
        return self._row_to_job(row)

    async def complete_job(self, job_id: str) -> OtaJobRecord | None:
        """Mark a job as completed (all devices succeeded)."""
        now = datetime.now(timezone.utc)
        async with self._session_maker() as session:
            row = await session.get(OtaJob, job_id)
            if row is None:
                return None
            row.status = OtaJobStatus.COMPLETED.value
            row.completed_at = now
            row.modified_at = now
            await session.commit()
            await session.refresh(row)

        logger.info("OTA job completed: %s", job_id)
        return self._row_to_job(row)

    async def fail_job(self, job_id: str) -> OtaJobRecord | None:
        """Mark a job as failed."""
        now = datetime.now(timezone.utc)
        async with self._session_maker() as session:
            row = await session.get(OtaJob, job_id)
            if row is None:
                return None
            row.status = OtaJobStatus.FAILED.value
            row.completed_at = now
            row.modified_at = now
            await session.commit()
            await session.refresh(row)

        logger.warning("OTA job failed: %s", job_id)
        return self._row_to_job(row)

    # ------------------------------------------------------------------
    # Progress tracking
    # ------------------------------------------------------------------

    async def update_progress(
        self,
        job_id: str,
        device_id: str,
        status: str,
        bytes_downloaded: int = 0,
        bytes_total: int = 0,
        error: str | None = None,
    ) -> OtaJobRecord | None:
        """Update progress for a specific device within a job.

        Automatically transitions the job to IN_PROGRESS if it was PENDING.
        Transitions to COMPLETED if all devices are done; FAILED if any device failed.
        """
        now = datetime.now(timezone.utc)
        percentage = 0
        if bytes_total > 0:
            percentage = min(100, int(bytes_downloaded * 100 / bytes_total))

        async with self._session_maker() as session:
            row = await session.get(OtaJob, job_id)
            if row is None:
                return None

            # Auto-start if pending
            if row.status == OtaJobStatus.PENDING.value:
                row.status = OtaJobStatus.IN_PROGRESS.value
                row.started_at = row.started_at or now

            progress = dict(row.progress or {})
            progress[device_id] = {
                "status": status,
                "bytes_downloaded": bytes_downloaded,
                "bytes_total": bytes_total,
                "percentage": percentage,
                "error": error,
                "updated_at": now.isoformat(),
            }
            row.progress = progress
            row.modified_at = now

            # Auto-complete or auto-fail based on progress
            pending_count = sum(
                1 for d in progress.values()
                if d.get("status") not in ("completed", "failed", "cancelled")
            )
            has_failure = any(d.get("status") == "failed" for d in progress.values())
            all_done = pending_count == 0

            if all_done and not has_failure:
                row.status = OtaJobStatus.COMPLETED.value
                row.completed_at = now
            elif has_failure and all_done:
                row.status = OtaJobStatus.FAILED.value
                row.completed_at = now

            await session.commit()
            await session.refresh(row)

        return self._row_to_job(row)

    async def get_device_progress(self, job_id: str, device_id: str) -> dict[str, Any] | None:
        """Return progress for a specific device in a job."""
        job = await self.get_job(job_id)
        if job is None:
            return None
        return job.progress.get(device_id)

    # ------------------------------------------------------------------
    # OTA token management
    # ------------------------------------------------------------------

    async def issue_ota_token(self, job_id: str, device_id: str) -> tuple[str, datetime]:
        """Issue a short-lived OTA token for a specific job and device.

        Returns (token, expires_at).
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=OTA_TOKEN_TTL_MINUTES)
        token = secrets.token_urlsafe(32)

        async with self._session_maker() as session:
            tok_row = OtaToken(
                token=token,
                job_id=job_id,
                device_id=device_id,
                issued_at=now,
                expires_at=expires,
            )
            session.add(tok_row)
            await session.commit()

        return token, expires

    async def validate_ota_token(self, token: str, job_id: str, device_id: str) -> bool:
        """Validate an OTA token for a specific job/device.

        Returns True if valid and not expired. Marks token as used.
        """
        async with self._session_maker() as session:
            result = await session.execute(
                select(OtaToken).where(
                    OtaToken.token == token,
                    OtaToken.job_id == job_id,
                    OtaToken.device_id == device_id,
                )
            )
            tok_row = result.scalar_one_or_none()
            if tok_row is None:
                return False
            if datetime.now(timezone.utc) > tok_row.expires_at:
                return False
            if tok_row.used:
                return False
            tok_row.used = 1
            await session.commit()
            return True

    # ------------------------------------------------------------------
    # Scheduled job processing
    # ------------------------------------------------------------------

    async def process_scheduled_jobs(self) -> list[OtaJobRecord]:
        """Start all PENDING jobs whose schedule_at has passed.

        Call this periodically (e.g. from a background task or on each request).
        Returns list of started jobs.
        """
        now = datetime.now(timezone.utc)
        async with self._session_maker() as session:
            result = await session.execute(
                select(OtaJob).where(
                    OtaJob.status == OtaJobStatus.PENDING.value,
                    OtaJob.schedule_at != None,  # noqa: E711
                    OtaJob.schedule_at <= now,
                )
            )
            rows = result.scalars().all()
            started: list[OtaJobRecord] = []
            for row in rows:
                job_rec = self._row_to_job(row)
                started_rec = await self.start_job(job_rec.job_id)
                if started_rec:
                    started.append(started_rec)
        return started
