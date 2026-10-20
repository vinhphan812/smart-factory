"""Tests for device_registry.py — CRUD, heartbeat, stale detection."""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from iot_gateway.device_registry import (
    Device,
    DeviceRegistry,
    DeviceRecord,
    DeviceStatus,
    DeviceType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    """Mock AsyncSession with async context manager."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def mock_session_maker(mock_session):
    maker = MagicMock()
    maker.return_value = mock_session
    return maker


@pytest.fixture
def registry(mock_session_maker):
    return DeviceRegistry(mock_session_maker)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_device(
    device_id: str = "urn:ngsi-ld:Device:bridge-001",
    **overrides,
) -> Device:
    defaults = dict(
        device_id=device_id,
        device_type=DeviceType.ESP32_BRIDGE,
        name="ESP32 Bridge Unit 1",
        status=DeviceStatus.OFFLINE,
        manufacturer="Espressif",
        firmware_version="v1.2.0",
        capabilities=["CONVEYOR_START", "CONVEYOR_STOP"],
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Device(**defaults)


# ---------------------------------------------------------------------------
# Domain model tests
# ---------------------------------------------------------------------------

def test_device_make_id() -> None:
    assert Device.make_id("bridge-001") == "urn:ngsi-ld:Device:bridge-001"
    assert Device.make_id("mega-01") == "urn:ngsi-ld:Device:mega-01"


def test_device_to_dict() -> None:
    now = datetime.now(timezone.utc)
    d = Device(
        device_id="urn:ngsi-ld:Device:bridge-001",
        device_type=DeviceType.ESP32_BRIDGE,
        name="Bridge",
        status=DeviceStatus.ONLINE,
        manufacturer="Espressif",
        firmware_version="v1.0.0",
        capabilities=["get_telemetry"],
        last_heartbeat_at=now,
        created_at=now,
    )
    out = d.to_dict()
    assert out["id"] == "urn:ngsi-ld:Device:bridge-001"
    assert out["deviceTypeValue"] == "esp32_bridge"
    assert out["status"]["value"] == "online"
    assert out["capabilities"]["value"] == ["get_telemetry"]
    assert out["lastSeen"]["value"] == now.isoformat()


def test_device_to_summary_dict() -> None:
    now = datetime.now(timezone.utc)
    d = Device(
        device_id="urn:ngsi-ld:Device:bridge-001",
        device_type=DeviceType.ESP32_BRIDGE,
        name="Bridge",
        status=DeviceStatus.ONLINE,
        created_at=now,
    )
    out = d.to_summary_dict()
    assert out["device_id"] == "urn:ngsi-ld:Device:bridge-001"
    assert out["device_id_short"] == "bridge-001"
    assert out["status"] == "online"


# ---------------------------------------------------------------------------
# DeviceRegistry.create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_inserts_device(registry, mock_session):
    device = make_device()

    # Simulate get() returns None (not found)
    mock_session.get = AsyncMock(return_value=None)
    mock_session.add = MagicMock()  # add() is sync in SQLAlchemy
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await registry.create(device)

    assert result.device_id == device.device_id
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_raises_on_duplicate(registry, mock_session):
    device = make_device()
    # Simulate device already exists
    mock_session.get = AsyncMock(return_value=MagicMock())

    with pytest.raises(ValueError, match="already exists"):
        await registry.create(device)


# ---------------------------------------------------------------------------
# DeviceRegistry.get
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_returns_device(registry, mock_session):
    row = MagicMock(spec=DeviceRecord)
    row.device_id = "urn:ngsi-ld:Device:bridge-001"
    row.device_id_short = "bridge-001"
    row.device_type = "esp32_bridge"
    row.name = "Bridge"
    row.status = "online"
    row.manufacturer = "Espressif"
    row.firmware_version = "v1.0.0"
    row.capabilities = ["CONVEYOR_START"]
    row.owner = None
    row.controlled_by_module = None
    row.location = None
    row.tls_cert_serial = None
    row.tls_cert_fingerprint = None
    row.tls_cert_not_before = None
    row.tls_cert_not_after = None
    row.last_heartbeat_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.metadata_ = {}

    mock_session.get = AsyncMock(return_value=row)

    result = await registry.get("urn:ngsi-ld:Device:bridge-001")

    assert result is not None
    assert result.device_id == "urn:ngsi-ld:Device:bridge-001"
    assert result.status == "online"


@pytest.mark.asyncio
async def test_get_returns_none_when_not_found(registry, mock_session):
    mock_session.get = AsyncMock(return_value=None)

    result = await registry.get("urn:ngsi-ld:Device:unknown")

    assert result is None


# ---------------------------------------------------------------------------
# DeviceRegistry.update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_applies_allowed_fields(registry, mock_session):
    row = MagicMock(spec=DeviceRecord)
    row.device_id = "urn:ngsi-ld:Device:bridge-001"
    row.device_id_short = "bridge-001"
    row.device_type = "esp32_bridge"
    row.name = "Bridge"
    row.status = "online"
    row.manufacturer = "Espressif"
    row.firmware_version = "v1.0.0"
    row.capabilities = []
    row.owner = None
    row.controlled_by_module = None
    row.location = None
    row.tls_cert_serial = None
    row.tls_cert_fingerprint = None
    row.tls_cert_not_before = None
    row.tls_cert_not_after = None
    row.last_heartbeat_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.metadata_ = {}

    mock_session.get = AsyncMock(return_value=row)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await registry.update(
        "urn:ngsi-ld:Device:bridge-001",
        {"firmware_version": "v1.1.0", "status": "maintenance"},
    )

    assert result is not None
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_update_returns_none_when_not_found(registry, mock_session):
    mock_session.get = AsyncMock(return_value=None)

    result = await registry.update("urn:ngsi-ld:Device:unknown", {"status": "online"})

    assert result is None


# ---------------------------------------------------------------------------
# DeviceRegistry.delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_removes_device(registry, mock_session):
    row = MagicMock(spec=DeviceRecord)
    mock_session.get = AsyncMock(return_value=row)
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()

    result = await registry.delete("urn:ngsi-ld:Device:bridge-001")

    assert result is True
    mock_session.delete.assert_called_once_with(row)


@pytest.mark.asyncio
async def test_delete_returns_false_when_not_found(registry, mock_session):
    mock_session.get = AsyncMock(return_value=None)

    result = await registry.delete("urn:ngsi-ld:Device:unknown")

    assert result is False


# ---------------------------------------------------------------------------
# DeviceRegistry.heartbeat
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_heartbeat_updates_timestamp(registry, mock_session):
    row = MagicMock(spec=DeviceRecord)
    row.device_id = "urn:ngsi-ld:Device:bridge-001"
    row.device_id_short = "bridge-001"
    row.device_type = "esp32_bridge"
    row.name = "Bridge"
    row.status = "online"
    row.manufacturer = None
    row.firmware_version = None
    row.capabilities = []
    row.owner = None
    row.controlled_by_module = None
    row.location = None
    row.tls_cert_serial = None
    row.tls_cert_fingerprint = None
    row.tls_cert_not_before = None
    row.tls_cert_not_after = None
    row.last_heartbeat_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.metadata_ = {}

    mock_session.get = AsyncMock(return_value=row)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await registry.update_heartbeat("urn:ngsi-ld:Device:bridge-001")

    assert result is not None
    assert result.last_heartbeat_at is not None


# ---------------------------------------------------------------------------
# DeviceStatus enum
# ---------------------------------------------------------------------------

def test_device_status_values() -> None:
    assert DeviceStatus.ONLINE.value == "online"
    assert DeviceStatus.OFFLINE.value == "offline"
    assert DeviceStatus.MAINTENANCE.value == "maintenance"
    assert DeviceStatus.ERROR.value == "error"


def test_device_type_values() -> None:
    assert DeviceType.ESP32_BRIDGE.value == "esp32_bridge"
    assert DeviceType.MEGA_REFERENCE.value == "mega_reference"
    assert DeviceType.SIMULATOR.value == "simulator"
    assert DeviceType.IOT_GATEWAY.value == "iot_gateway"
