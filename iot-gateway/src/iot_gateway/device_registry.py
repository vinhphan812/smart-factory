"""Authoritative device registry — CRUD, heartbeat monitoring, TLS cert tracking.

Schema aligns with contracts/fiware/ngsi-ld-entity-schema.md Device entity.
Stores device records in SQLite alongside the event store so both share the
same database file (gateway.db) and lifetime.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    select,
    func,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .event_store import Base

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain enums
# ---------------------------------------------------------------------------

class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class DeviceType(str, Enum):
    ESP32_BRIDGE = "esp32_bridge"
    MEGA_REFERENCE = "mega_reference"
    SIMULATOR = "simulator"
    IOT_GATEWAY = "iot_gateway"


# ---------------------------------------------------------------------------
# SQLAlchemy model
# ---------------------------------------------------------------------------

class DeviceRecord(Base):
    """SQLAlchemy model for the devices table."""

    __tablename__ = "devices"

    device_id = Column(String(64), primary_key=True)  # urn:ngsi-ld:Device:<device_id>
    device_id_short = Column(String(64), nullable=False, index=True)  # e.g. "bridge-001"
    device_type = Column(String(32), nullable=False)
    name = Column(String(128), nullable=False)
    manufacturer = Column(String(128), nullable=True)
    firmware_version = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, default=DeviceStatus.OFFLINE.value)
    capabilities = Column(JSON, nullable=False, default=list)  # list[str]
    owner = Column(String(128), nullable=True)
    controlled_by_module = Column(String(128), nullable=True)
    location = Column(SQLiteJSON, nullable=True)  # GeoJSON Point
    tls_cert_serial = Column(String(64), nullable=True)
    tls_cert_fingerprint = Column(String(128), nullable=True)
    tls_cert_not_before = Column(DateTime(timezone=True), nullable=True)
    tls_cert_not_after = Column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    modified_at = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column(JSON, nullable=True)  # extra key-value metadata


# ---------------------------------------------------------------------------
# Domain object
# ---------------------------------------------------------------------------

@dataclass
class Device:
    """In-memory device record — mirrors the SQLAlchemy model."""

    device_id: str  # full URN, e.g. "urn:ngsi-ld:Device:bridge-001"
    device_type: DeviceType | str
    name: str
    status: DeviceStatus | str = DeviceStatus.OFFLINE
    manufacturer: str | None = None
    firmware_version: str | None = None
    capabilities: list[str] = field(default_factory=list)
    owner: str | None = None
    controlled_by_module: str | None = None
    location: dict | None = None
    # TLS / identity
    tls_cert_serial: str | None = None
    tls_cert_fingerprint: str | None = None
    tls_cert_not_before: datetime | None = None
    tls_cert_not_after: datetime | None = None
    # Heartbeat
    last_heartbeat_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def make_id(cls, short_id: str) -> str:
        """Build a URN-style device ID."""
        return f"urn:ngsi-ld:Device:{short_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.device_id,
            "type": "Device",
            "name": self.name,
            "deviceType": {"type": "Text", "value": self.device_type},
            "deviceId": {"type": "Text", "value": self.device_id.replace("urn:ngsi-ld:Device:", "")},
            "deviceTypeValue": self.device_type,
            "manufacturer": {"type": "Text", "value": self.manufacturer} if self.manufacturer else None,
            "firmwareVersion": {"type": "Text", "value": self.firmware_version} if self.firmware_version else None,
            "capabilities": {"type": "Array", "value": self.capabilities},
            "status": {"type": "Text", "value": self.status},
            "location": {"type": "GeoProperty", "value": self.location} if self.location else None,
            "owner": {"type": "Relationship", "value": self.owner} if self.owner else None,
            "controlledBy": {"type": "Relationship", "value": self.controlled_by_module} if self.controlled_by_module else None,
            "lastSeen": {"type": "DateTime", "value": self.last_heartbeat_at.isoformat()} if self.last_heartbeat_at else None,
            "tlsCertSerial": self.tls_cert_serial,
            "tlsCertFingerprint": self.tls_cert_fingerprint,
            "createdAt": {"type": "DateTime", "value": self.created_at.isoformat()},
            "modifiedAt": {"type": "DateTime", "value": self.modified_at.isoformat()} if self.modified_at else None,
            "metadata": self.metadata,
        }

    def to_summary_dict(self) -> dict[str, Any]:
        """Compact dict for registry list responses."""
        return {
            "device_id": self.device_id,
            "device_id_short": self.device_id.replace("urn:ngsi-ld:Device:", ""),
            "device_type": self.device_type,
            "name": self.name,
            "status": self.status,
            "manufacturer": self.manufacturer,
            "firmware_version": self.firmware_version,
            "capabilities": self.capabilities,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
        }


# ---------------------------------------------------------------------------
# Registry service
# ---------------------------------------------------------------------------

class DeviceRegistry:
    """CRUD + heartbeat service backed by SQLite.

    Shares the same database as EventStore so migrations run once.
    """

    # Heartbeat stale threshold in seconds (default 5 minutes)
    DEFAULT_STALE_THRESHOLD_SECONDS = 300

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    # ------------------------------------------------------------------
    # Helper: row → domain object
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_device(row: DeviceRecord) -> Device:
        return Device(
            device_id=row.device_id,
            device_type=row.device_type,
            name=row.name,
            status=row.status,
            manufacturer=row.manufacturer,
            firmware_version=row.firmware_version,
            capabilities=row.capabilities or [],
            owner=row.owner,
            controlled_by_module=row.controlled_by_module,
            location=row.location,
            tls_cert_serial=row.tls_cert_serial,
            tls_cert_fingerprint=row.tls_cert_fingerprint,
            tls_cert_not_before=row.tls_cert_not_before,
            tls_cert_not_after=row.tls_cert_not_after,
            last_heartbeat_at=row.last_heartbeat_at,
            created_at=row.created_at,
            modified_at=row.modified_at,
            metadata=row.metadata_ or {},
        )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(self, device: Device) -> Device:
        """Insert a new device record. Raises ValueError if device_id already exists."""
        async with self._session_maker() as session:
            existing = await session.get(DeviceRecord, device.device_id)
            if existing is not None:
                raise ValueError(f"Device {device.device_id!r} already exists")

            now = datetime.now(timezone.utc)
            row = DeviceRecord(
                device_id=device.device_id,
                device_id_short=device.device_id.replace("urn:ngsi-ld:Device:", ""),
                device_type=str(device.device_type),
                name=device.name,
                manufacturer=device.manufacturer,
                firmware_version=device.firmware_version,
                status=str(device.status),
                capabilities=device.capabilities,
                owner=device.owner,
                controlled_by_module=device.controlled_by_module,
                location=device.location,
                tls_cert_serial=device.tls_cert_serial,
                tls_cert_fingerprint=device.tls_cert_fingerprint,
                tls_cert_not_before=device.tls_cert_not_before,
                tls_cert_not_after=device.tls_cert_not_after,
                last_heartbeat_at=device.last_heartbeat_at,
                created_at=now,
                modified_at=now,
                metadata_=device.metadata,
            )
            session.add(row)
            await session.commit()
            logger.info("Device registered: %s (%s)", device.device_id, device.name)
            return device

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, device_id: str) -> Device | None:
        """Return a device by URN, or None if not found."""
        async with self._session_maker() as session:
            row = await session.get(DeviceRecord, device_id)
            if row is None:
                return None
            return self._row_to_device(row)

    async def get_by_short_id(self, short_id: str) -> Device | None:
        """Return a device by short ID, or None if not found."""
        urn = Device.make_id(short_id)
        return await self.get(urn)

    async def list_all(
        self,
        status: str | None = None,
        device_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Device], int]:
        """Return devices matching filters and total count."""
        async with self._session_maker() as session:
            q = select(DeviceRecord)
            count_q = select(func.count()).select_from(DeviceRecord)

            if status:
                q = q.where(DeviceRecord.status == status)
                count_q = count_q.where(DeviceRecord.status == status)
            if device_type:
                q = q.where(DeviceRecord.device_type == device_type)
                count_q = count_q.where(DeviceRecord.device_type == device_type)

            total = (await session.execute(count_q)).scalar() or 0

            q = q.order_by(DeviceRecord.created_at.desc()).offset(offset).limit(limit)
            rows = (await session.execute(q)).scalars().all()

            return [self._row_to_device(r) for r in rows], int(total)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(self, device_id: str, updates: dict[str, Any]) -> Device | None:
        """Apply partial updates to a device record. Returns updated record or None."""
        now = datetime.now(timezone.utc)
        async with self._session_maker() as session:
            row = await session.get(DeviceRecord, device_id)
            if row is None:
                return None

            ALLOWED = {
                "name", "manufacturer", "firmware_version", "status",
                "capabilities", "owner", "controlled_by_module", "location",
                "tls_cert_serial", "tls_cert_fingerprint",
                "tls_cert_not_before", "tls_cert_not_after",
                "last_heartbeat_at", "metadata",
            }
            for key, value in updates.items():
                if key in ALLOWED:
                    setattr(row, key, value)
            row.modified_at = now

            await session.commit()
            await session.refresh(row)
            device = self._row_to_device(row)
            logger.info("Device updated: %s", device_id)
            return device

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, device_id: str) -> bool:
        """Remove a device record. Returns True if deleted, False if not found."""
        async with self._session_maker() as session:
            row = await session.get(DeviceRecord, device_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            logger.info("Device deregistered: %s", device_id)
            return True

    # ------------------------------------------------------------------
    # Heartbeat / stale detection
    # ------------------------------------------------------------------

    async def update_heartbeat(self, device_id: str) -> Device | None:
        """Record a heartbeat for a device. Returns updated record or None."""
        now = datetime.now(timezone.utc)
        return await self.update(device_id, {"last_heartbeat_at": now})

    async def list_stale_devices(
        self,
        threshold_seconds: int | None = None,
    ) -> list[Device]:
        """Return devices whose last heartbeat is older than threshold.

        Uses a simple SQL comparison — no timezone conversion needed since
        both sides are UTC-aware.
        """
        import time as _time
        threshold = threshold_seconds or self.DEFAULT_STALE_THRESHOLD_SECONDS
        cutoff = datetime.fromtimestamp(
            _time.time() - threshold, tz=timezone.utc
        )
        async with self._session_maker() as session:
            q = (
                select(DeviceRecord)
                .where(DeviceRecord.last_heartbeat_at != None)  # noqa: E711
                .where(DeviceRecord.last_heartbeat_at < cutoff)
                .order_by(DeviceRecord.last_heartbeat_at.asc())
            )
            rows = (await session.execute(q)).scalars().all()
            return [self._row_to_device(r) for r in rows]

    async def list_online_devices(self) -> list[Device]:
        """Return all devices currently marked as online."""
        devices, _ = await self.list_all(status=DeviceStatus.ONLINE.value, limit=10000)
        return devices

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    async def set_status(self, device_id: str, status: str) -> Device | None:
        """Update only the status field."""
        return await self.update(device_id, {"status": status})

    # ------------------------------------------------------------------
    # TLS certificate tracking
    # ------------------------------------------------------------------

    async def update_tls_cert(
        self,
        device_id: str,
        serial: str | None = None,
        fingerprint: str | None = None,
        not_before: datetime | None = None,
        not_after: datetime | None = None,
    ) -> Device | None:
        """Update TLS certificate fields for a device."""
        updates: dict[str, Any] = {}
        if serial is not None:
            updates["tls_cert_serial"] = serial
        if fingerprint is not None:
            updates["tls_cert_fingerprint"] = fingerprint
        if not_before is not None:
            updates["tls_cert_not_before"] = not_before
        if not_after is not None:
            updates["tls_cert_not_after"] = not_after
        if not updates:
            return await self.get(device_id)
        return await self.update(device_id, updates)
