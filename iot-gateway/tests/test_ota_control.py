"""Tests for ota_control.py — job lifecycle, progress tracking, token management."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from iot_gateway.ota_control import (
    DeviceProgress,
    OtaControl,
    OtaJob,
    OtaJobRecord,
    OtaJobStatus,
    OtaJobTarget,
    OtaToken,
    OTA_DEFAULT_TIMEOUT_SECONDS,
    OTA_TOKEN_TTL_MINUTES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
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
def ota(mock_session_maker):
    return OtaControl(mock_session_maker)


# ---------------------------------------------------------------------------
# Domain model tests
# ---------------------------------------------------------------------------

def test_ota_job_record_to_dict() -> None:
    now = datetime.now(timezone.utc)
    job = OtaJobRecord(
        job_id="ota-abc123",
        target_device_ids=["urn:ngsi-ld:Device:bridge-001"],
        target_type=OtaJobTarget.ESP32_BRIDGE,
        firmware_version="v1.3.0",
        firmware_url="https://fw.example.com/v1.3.0.bin",
        firmware_sha256="deadbeef",
        status=OtaJobStatus.PENDING,
        created_at=now,
    )
    out = job.to_dict()
    assert out["job_id"] == "ota-abc123"
    assert out["status"] == "pending"
    assert "firmware_version" in out


def test_ota_job_record_to_summary_dict() -> None:
    now = datetime.now(timezone.utc)
    job = OtaJobRecord(
        job_id="ota-abc123",
        target_device_ids=["urn:ngsi-ld:Device:bridge-001", "urn:ngsi-ld:Device:bridge-002"],
        target_type=OtaJobTarget.ESP32_BRIDGE,
        firmware_version="v1.3.0",
        firmware_url="https://fw.example.com/v1.3.0.bin",
        created_at=now,
    )
    summary = job.to_summary_dict()
    assert summary["target_count"] == 2
    assert summary["status"] == "pending"


def test_device_progress_to_dict() -> None:
    now = datetime.now(timezone.utc)
    dp = DeviceProgress(
        device_id="urn:ngsi-ld:Device:bridge-001",
        job_id="ota-abc123",
        status="downloading",
        bytes_downloaded=4096,
        bytes_total=102400,
        percentage=4,
        updated_at=now,
    )
    out = dp.to_dict()
    assert out["percentage"] == 4
    assert out["status"] == "downloading"


# ---------------------------------------------------------------------------
# OtaControl.create_job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_job_inserts_and_returns_job(ota, mock_session):
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    job = await ota.create_job(
        target_device_ids=["urn:ngsi-ld:Device:bridge-001"],
        target_type="esp32_bridge",
        firmware_version="v1.3.0",
        firmware_url="https://fw.example.com/v1.3.0.bin",
        firmware_sha256="deadbeef",
        firmware_size_bytes=102400,
        created_by="operator-1",
        notes="Production OTA",
    )

    assert job.job_id.startswith("ota-")
    assert job.target_type == "esp32_bridge"
    assert job.firmware_version == "v1.3.0"
    assert job.status == OtaJobStatus.PENDING
    assert mock_session.add.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_create_job_with_schedule(ota, mock_session):
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    future = datetime.now(timezone.utc) + timedelta(hours=1)
    job = await ota.create_job(
        target_device_ids=["urn:ngsi-ld:Device:bridge-001"],
        target_type="esp32_bridge",
        firmware_version="v1.3.0",
        firmware_url="https://fw.example.com/v1.3.0.bin",
        schedule_at=future,
    )

    assert job.schedule_at == future
    assert job.status == OtaJobStatus.PENDING


# ---------------------------------------------------------------------------
# OtaControl.get_job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_job_returns_job(ota, mock_session):
    row = MagicMock(spec=OtaJob)
    row.job_id = "ota-abc123"
    row.target_device_ids = ["urn:ngsi-ld:Device:bridge-001"]
    row.target_type = "esp32_bridge"
    row.firmware_version = "v1.3.0"
    row.firmware_url = "https://fw.example.com/v1.3.0.bin"
    row.firmware_sha256 = "deadbeef"
    row.firmware_size_bytes = 102400
    row.status = "pending"
    row.schedule_at = None
    row.started_at = None
    row.completed_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.created_by = None
    row.notes = None
    row.progress = {}
    row.timeout_seconds = OTA_DEFAULT_TIMEOUT_SECONDS

    mock_session.get = AsyncMock(return_value=row)

    result = await ota.get_job("ota-abc123")

    assert result is not None
    assert result.job_id == "ota-abc123"
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_get_job_returns_none_when_not_found(ota, mock_session):
    mock_session.get = AsyncMock(return_value=None)

    result = await ota.get_job("ota-abc123")

    assert result is None


# ---------------------------------------------------------------------------
# OtaControl.start_job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_job_transitions_pending_to_in_progress(ota, mock_session):
    row = MagicMock(spec=OtaJob)
    row.job_id = "ota-abc123"
    row.target_device_ids = ["urn:ngsi-ld:Device:bridge-001"]
    row.target_type = "esp32_bridge"
    row.firmware_version = "v1.3.0"
    row.firmware_url = "https://fw.example.com/v1.3.0.bin"
    row.firmware_sha256 = None
    row.firmware_size_bytes = None
    row.status = "pending"
    row.schedule_at = None
    row.started_at = None
    row.completed_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.created_by = None
    row.notes = None
    row.progress = {}
    row.timeout_seconds = OTA_DEFAULT_TIMEOUT_SECONDS

    mock_session.get = AsyncMock(return_value=row)
    mock_session.add = MagicMock()  # add() is sync in SQLAlchemy
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await ota.start_job("ota-abc123")

    assert result is not None
    assert result.status == OtaJobStatus.IN_PROGRESS
    assert result.started_at is not None
    # Tokens should have been issued (session.add called for each device)
    assert mock_session.add.called


@pytest.mark.asyncio
async def test_start_job_raises_on_already_started(ota, mock_session):
    row = MagicMock(spec=OtaJob)
    row.job_id = "ota-abc123"
    row.target_device_ids = []
    row.target_type = "esp32_bridge"
    row.firmware_version = "v1.3.0"
    row.firmware_url = "https://fw.example.com/v1.3.0.bin"
    row.firmware_sha256 = None
    row.firmware_size_bytes = None
    row.status = "in_progress"
    row.schedule_at = None
    row.started_at = datetime.now(timezone.utc)
    row.completed_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.created_by = None
    row.notes = None
    row.progress = {}
    row.timeout_seconds = OTA_DEFAULT_TIMEOUT_SECONDS

    mock_session.get = AsyncMock(return_value=row)

    with pytest.raises(ValueError, match="cannot be started"):
        await ota.start_job("ota-abc123")


# ---------------------------------------------------------------------------
# OtaControl.update_progress
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_progress_autostarts_pending_job(ota, mock_session):
    row = MagicMock(spec=OtaJob)
    row.job_id = "ota-abc123"
    row.target_device_ids = ["urn:ngsi-ld:Device:bridge-001"]
    row.target_type = "esp32_bridge"
    row.firmware_version = "v1.3.0"
    row.firmware_url = "https://fw.example.com/v1.3.0.bin"
    row.firmware_sha256 = None
    row.firmware_size_bytes = None
    row.status = "pending"
    row.schedule_at = None
    row.started_at = None
    row.completed_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.created_by = None
    row.notes = None
    row.progress = {}
    row.timeout_seconds = OTA_DEFAULT_TIMEOUT_SECONDS

    mock_session.get = AsyncMock(return_value=row)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await ota.update_progress(
        job_id="ota-abc123",
        device_id="urn:ngsi-ld:Device:bridge-001",
        status="downloading",
        bytes_downloaded=4096,
        bytes_total=102400,
    )

    assert result is not None
    assert result.status == OtaJobStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_update_progress_completes_when_all_done(ota, mock_session):
    """When all devices report completed, job transitions to completed."""
    row = MagicMock(spec=OtaJob)
    row.job_id = "ota-abc123"
    row.target_device_ids = ["urn:ngsi-ld:Device:bridge-001"]
    row.target_type = "esp32_bridge"
    row.firmware_version = "v1.3.0"
    row.firmware_url = "https://fw.example.com/v1.3.0.bin"
    row.firmware_sha256 = None
    row.firmware_size_bytes = None
    row.status = "in_progress"
    row.schedule_at = None
    row.started_at = datetime.now(timezone.utc)
    row.completed_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.created_by = None
    row.notes = None
    row.progress = {}
    row.timeout_seconds = OTA_DEFAULT_TIMEOUT_SECONDS

    mock_session.get = AsyncMock(return_value=row)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await ota.update_progress(
        job_id="ota-abc123",
        device_id="urn:ngsi-ld:Device:bridge-001",
        status="completed",
        bytes_downloaded=102400,
        bytes_total=102400,
    )

    assert result is not None
    assert result.status == OtaJobStatus.COMPLETED


@pytest.mark.asyncio
async def test_update_progress_fails_when_device_fails(ota, mock_session):
    """When any device reports failed, job transitions to failed."""
    row = MagicMock(spec=OtaJob)
    row.job_id = "ota-abc123"
    row.target_device_ids = ["urn:ngsi-ld:Device:bridge-001"]
    row.target_type = "esp32_bridge"
    row.firmware_version = "v1.3.0"
    row.firmware_url = "https://fw.example.com/v1.3.0.bin"
    row.firmware_sha256 = None
    row.firmware_size_bytes = None
    row.status = "in_progress"
    row.schedule_at = None
    row.started_at = datetime.now(timezone.utc)
    row.completed_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.created_by = None
    row.notes = None
    row.progress = {}
    row.timeout_seconds = OTA_DEFAULT_TIMEOUT_SECONDS

    mock_session.get = AsyncMock(return_value=row)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await ota.update_progress(
        job_id="ota-abc123",
        device_id="urn:ngsi-ld:Device:bridge-001",
        status="failed",
        error="Flash write error at sector 0",
    )

    assert result is not None
    assert result.status == OtaJobStatus.FAILED


# ---------------------------------------------------------------------------
# OtaControl.cancel_job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_job_transitions_to_cancelled(ota, mock_session):
    row = MagicMock(spec=OtaJob)
    row.job_id = "ota-abc123"
    row.target_device_ids = []
    row.target_type = "esp32_bridge"
    row.firmware_version = "v1.3.0"
    row.firmware_url = "https://fw.example.com/v1.3.0.bin"
    row.firmware_sha256 = None
    row.firmware_size_bytes = None
    row.status = "pending"
    row.schedule_at = None
    row.started_at = None
    row.completed_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.created_by = None
    row.notes = None
    row.progress = {}
    row.timeout_seconds = OTA_DEFAULT_TIMEOUT_SECONDS

    mock_session.get = AsyncMock(return_value=row)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await ota.cancel_job("ota-abc123")

    assert result is not None
    assert result.status == OtaJobStatus.CANCELLED
    assert result.completed_at is not None


@pytest.mark.asyncio
async def test_cancel_job_raises_on_completed(ota, mock_session):
    row = MagicMock(spec=OtaJob)
    row.job_id = "ota-abc123"
    row.target_device_ids = []
    row.target_type = "esp32_bridge"
    row.firmware_version = "v1.3.0"
    row.firmware_url = "https://fw.example.com/v1.3.0.bin"
    row.firmware_sha256 = None
    row.firmware_size_bytes = None
    row.status = "completed"
    row.schedule_at = None
    row.started_at = datetime.now(timezone.utc)
    row.completed_at = datetime.now(timezone.utc)
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.created_by = None
    row.notes = None
    row.progress = {}
    row.timeout_seconds = OTA_DEFAULT_TIMEOUT_SECONDS

    mock_session.get = AsyncMock(return_value=row)

    with pytest.raises(ValueError, match="already terminal"):
        await ota.cancel_job("ota-abc123")


# ---------------------------------------------------------------------------
# OtaControl.list_jobs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_jobs_returns_paginated_results(ota, mock_session):
    row = MagicMock(spec=OtaJob)
    row.job_id = "ota-abc123"
    row.target_device_ids = ["urn:ngsi-ld:Device:bridge-001"]
    row.target_type = "esp32_bridge"
    row.firmware_version = "v1.3.0"
    row.firmware_url = "https://fw.example.com/v1.3.0.bin"
    row.firmware_sha256 = None
    row.firmware_size_bytes = None
    row.status = "pending"
    row.schedule_at = None
    row.started_at = None
    row.completed_at = None
    row.created_at = datetime.now(timezone.utc)
    row.modified_at = None
    row.created_by = None
    row.notes = None
    row.progress = {}
    row.timeout_seconds = OTA_DEFAULT_TIMEOUT_SECONDS

    # Build two chained AsyncMock returns: count query then list query
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=1)
    list_result = MagicMock()
    list_scalars = MagicMock()
    list_scalars.all = MagicMock(return_value=[row])  # scalars().all() is sync in SQLAlchemy 2.1
    list_result.scalars = MagicMock(return_value=list_scalars)

    mock_session.execute = AsyncMock(
        side_effect=[count_result, list_result]
    )

    jobs, total = await ota.list_jobs(status="pending", limit=50, offset=0)

    assert total == 1
    assert len(jobs) == 1
    assert jobs[0].job_id == "ota-abc123"


# ---------------------------------------------------------------------------
# OtaControl.issue_ota_token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_issue_ota_token(ota, mock_session):
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    token, expires = await ota.issue_ota_token(
        job_id="ota-abc123",
        device_id="urn:ngsi-ld:Device:bridge-001",
    )

    assert token
    assert len(token) > 20
    assert expires is not None
    assert mock_session.add.called


# ---------------------------------------------------------------------------
# OtaControl.validate_ota_token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_ota_token_succeeds(ota, mock_session):
    now = datetime.now(timezone.utc)
    tok_row = MagicMock(spec=OtaToken)
    tok_row.token = "good-token"
    tok_row.job_id = "ota-abc123"
    tok_row.device_id = "urn:ngsi-ld:Device:bridge-001"
    tok_row.issued_at = now
    tok_row.expires_at = now + timedelta(minutes=OTA_TOKEN_TTL_MINUTES)
    tok_row.used = 0

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=tok_row)
    exec_mock = AsyncMock(return_value=result_mock)
    mock_session.execute = exec_mock
    mock_session.commit = AsyncMock()

    valid = await ota.validate_ota_token("good-token", "ota-abc123", "urn:ngsi-ld:Device:bridge-001")

    assert valid is True
    assert tok_row.used == 1


@pytest.mark.asyncio
async def test_validate_ota_token_expired(ota, mock_session):
    now = datetime.now(timezone.utc)
    tok_row = MagicMock(spec=OtaToken)
    tok_row.token = "expired-token"
    tok_row.job_id = "ota-abc123"
    tok_row.device_id = "urn:ngsi-ld:Device:bridge-001"
    tok_row.issued_at = now - timedelta(hours=2)
    tok_row.expires_at = now - timedelta(minutes=1)  # expired
    tok_row.used = 0

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=tok_row)
    mock_session.execute = AsyncMock(return_value=result_mock)

    valid = await ota.validate_ota_token("expired-token", "ota-abc123", "urn:ngsi-ld:Device:bridge-001")

    assert valid is False


@pytest.mark.asyncio
async def test_validate_ota_token_not_found(ota, mock_session):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=result_mock)

    valid = await ota.validate_ota_token("unknown-token", "ota-abc123", "urn:ngsi-ld:Device:bridge-001")

    assert valid is False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_ota_job_status_values() -> None:
    assert OtaJobStatus.PENDING.value == "pending"
    assert OtaJobStatus.IN_PROGRESS.value == "in_progress"
    assert OtaJobStatus.COMPLETED.value == "completed"
    assert OtaJobStatus.FAILED.value == "failed"
    assert OtaJobStatus.CANCELLED.value == "cancelled"


def test_ota_job_target_values() -> None:
    assert OtaJobTarget.ESP32_BRIDGE.value == "esp32_bridge"
    assert OtaJobTarget.MEGA_REFERENCE.value == "mega_reference"
    assert OtaJobTarget.SIMULATOR.value == "simulator"
