"""Tests for provisioning.py — bootstrap tokens, enrollment, certificate renewal."""

import pytest

from iot_gateway.device_registry import Device, DeviceRegistry, DeviceStatus
from iot_gateway.provisioning import (
    BootstrapToken,
    ProvisioningService,
    SimpleCA,
    CERT_VALIDITY_DAYS,
    BOOTSTRAP_TOKEN_TTL_MINUTES,
)


# ---------------------------------------------------------------------------
# SimpleCA tests
# ---------------------------------------------------------------------------

def test_ca_issues_device_cert() -> None:
    """CA should issue a valid device certificate."""
    ca = SimpleCA.get_instance()
    cert_pem, key_pem, serial, fingerprint = ca.issue_device_cert(
        device_id="urn:ngsi-ld:Device:bridge-001",
        device_name="Bridge 001",
    )

    assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
    assert serial
    assert len(fingerprint) == 64  # SHA-256 hex = 64 chars
    assert key_pem.startswith(b"-----BEGIN PRIVATE KEY-----")


def test_ca_issues_cert_from_csr_requires_load_pem_x509_csr() -> None:
    """When load_pem_x509_csr is not available, CSR-based cert issuance raises a clear error."""
    # Reset singleton for a clean test
    SimpleCA._instance = None
    ca = SimpleCA()

    with pytest.raises(ValueError, match="CSR parsing not available"):
        ca.issue_device_cert(
            device_id="urn:ngsi-ld:Device:bridge-002",
            device_name="Bridge 002",
            csr_pem=b"-----BEGIN CERTIFICATE REQUEST-----\n dummy CSR \n-----END CERTIFICATE REQUEST-----",
        )

    # Reset singleton
    SimpleCA._instance = None


def test_ca_revocation() -> None:
    """CA should track revoked certificate serials."""
    ca = SimpleCA.get_instance()
    assert ca.is_revoked("deadbeef") is False
    ca.revoke_cert("deadbeef")
    assert ca.is_revoked("deadbeef") is True


def test_ca_returns_ca_cert_pem() -> None:
    """CA should return a valid CA certificate PEM."""
    ca = SimpleCA.get_instance()
    pem = ca.get_ca_cert_pem()
    assert pem.startswith(b"-----BEGIN CERTIFICATE-----")


# ---------------------------------------------------------------------------
# BootstrapToken tests
# ---------------------------------------------------------------------------

def test_bootstrap_token_is_valid() -> None:
    """A fresh token should be valid."""
    bt = BootstrapToken(token="test-token")
    assert bt.is_valid() is True


def test_bootstrap_token_expired() -> None:
    """An expired token should be invalid."""
    from datetime import datetime, timedelta, timezone
    bt = BootstrapToken(
        token="test-token",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    assert bt.is_valid() is False


def test_bootstrap_token_used() -> None:
    """A used token should be invalid."""
    bt = BootstrapToken(token="test-token", used=True)
    assert bt.is_valid() is False


# ---------------------------------------------------------------------------
# ProvisioningService tests
# ---------------------------------------------------------------------------

class DummyRegistry:
    """Stand-in for DeviceRegistry using an in-memory dict."""

    def __init__(self):
        self._devices: dict[str, Device] = {}

    async def create(self, device: Device) -> Device:
        if device.device_id in self._devices:
            raise ValueError(f"Device {device.device_id!r} already exists")
        self._devices[device.device_id] = device
        return device

    async def get(self, device_id: str) -> Device | None:
        return self._devices.get(device_id)

    async def update(self, device_id: str, updates: dict) -> Device | None:
        dev = self._devices.get(device_id)
        if dev is None:
            return None
        for k, v in updates.items():
            if hasattr(dev, k):
                setattr(dev, k, v)
        return dev

    async def update_tls_cert(self, device_id: str, **kwargs) -> Device | None:
        return await self.update(device_id, kwargs)

    async def set_status(self, device_id: str, status: str) -> Device | None:
        return await self.update(device_id, {"status": status})


@pytest.mark.asyncio
async def test_issue_bootstrap_token() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    token, expires = await prov.issue_bootstrap_token("bridge-001")

    assert token
    assert len(token) > 20
    assert expires is not None


@pytest.mark.asyncio
async def test_consume_bootstrap_token_succeeds() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    token, _ = await prov.issue_bootstrap_token()
    bt = await prov.consume_bootstrap_token(token)

    assert bt.token == token
    assert bt.used is True
    assert bt.used_at is not None


@pytest.mark.asyncio
async def test_consume_invalid_token_raises() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    with pytest.raises(ValueError, match="not found"):
        await prov.consume_bootstrap_token("nonexistent-token")


@pytest.mark.asyncio
async def test_enroll_device_success() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    token, _ = await prov.issue_bootstrap_token()
    result = await prov.enroll_device(
        short_device_id="bridge-001",
        device_name="ESP32 Bridge Unit 1",
        device_type="esp32_bridge",
        bootstrap_token=token,
        capabilities=["CONVEYOR_START", "get_telemetry"],
        manufacturer="Espressif",
        firmware_version="v1.2.0",
    )

    assert result["device_id"] == "urn:ngsi-ld:Device:bridge-001"
    assert result["cert_serial"]
    assert result["cert_fingerprint"]
    assert "device_cert_pem" in result
    assert "ca_cert_pem" in result
    assert result["enrolled_at"]


@pytest.mark.asyncio
async def test_enroll_device_invalid_token() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    with pytest.raises(ValueError, match="not found"):
        await prov.enroll_device(
            short_device_id="bridge-001",
            device_name="Bridge",
            device_type="esp32_bridge",
            bootstrap_token="bad-token",
        )


@pytest.mark.asyncio
async def test_enroll_device_invalid_type() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    token, _ = await prov.issue_bootstrap_token()

    with pytest.raises(ValueError, match="Invalid device_type"):
        await prov.enroll_device(
            short_device_id="bridge-001",
            device_name="Bridge",
            device_type="invalid_type",
            bootstrap_token=token,
        )


@pytest.mark.asyncio
async def test_enroll_device_duplicate_reenrolls() -> None:
    """Re-enrolling an existing device should update its cert info."""
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    token1, _ = await prov.issue_bootstrap_token()
    await prov.enroll_device(
        short_device_id="bridge-001",
        device_name="ESP32 Bridge",
        device_type="esp32_bridge",
        bootstrap_token=token1,
    )

    token2, _ = await prov.issue_bootstrap_token()
    result = await prov.enroll_device(
        short_device_id="bridge-001",
        device_name="ESP32 Bridge",
        device_type="esp32_bridge",
        bootstrap_token=token2,
    )

    # Should succeed (reenrolled)
    assert result["device_id"] == "urn:ngsi-ld:Device:bridge-001"


@pytest.mark.asyncio
async def test_renew_cert_success() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    token, _ = await prov.issue_bootstrap_token()
    await prov.enroll_device(
        short_device_id="bridge-001",
        device_name="Bridge",
        device_type="esp32_bridge",
        bootstrap_token=token,
    )

    # Renew — cert is fresh, so within renewal window (any status)
    from datetime import datetime, timedelta, timezone
    dev = await registry.get("urn:ngsi-ld:Device:bridge-001")
    # Force cert_not_after to be in the past to allow renewal
    dev.tls_cert_not_after = datetime.now(timezone.utc) - timedelta(days=1)

    result = await prov.renew_cert("urn:ngsi-ld:Device:bridge-001")

    assert result["device_id"] == "urn:ngsi-ld:Device:bridge-001"
    assert result["cert_serial"]
    assert "renewed_at" in result


@pytest.mark.asyncio
async def test_renew_cert_device_not_found() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    with pytest.raises(ValueError, match="Device not found"):
        await prov.renew_cert("urn:ngsi-ld:Device:unknown")


@pytest.mark.asyncio
async def test_register_capabilities() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    token, _ = await prov.issue_bootstrap_token()
    await prov.enroll_device(
        short_device_id="bridge-001",
        device_name="Bridge",
        device_type="esp32_bridge",
        bootstrap_token=token,
    )

    result = await prov.register_capabilities(
        "urn:ngsi-ld:Device:bridge-001",
        ["CONVEYOR_START", "CONVEYOR_STOP", "CRANE_MOVE"],
    )

    assert result is not None
    assert "CRANE_MOVE" in result.capabilities


@pytest.mark.asyncio
async def test_revoke_device() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    token, _ = await prov.issue_bootstrap_token()
    await prov.enroll_device(
        short_device_id="bridge-001",
        device_name="Bridge",
        device_type="esp32_bridge",
        bootstrap_token=token,
    )

    ok = await prov.revoke_device("urn:ngsi-ld:Device:bridge-001")

    assert ok is True
    dev = await registry.get("urn:ngsi-ld:Device:bridge-001")
    assert dev.status == DeviceStatus.OFFLINE.value


@pytest.mark.asyncio
async def test_revoke_nonexistent_device() -> None:
    registry = DummyRegistry()
    prov = ProvisioningService(registry)

    ok = await prov.revoke_device("urn:ngsi-ld:Device:unknown")

    assert ok is False
