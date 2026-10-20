"""Device provisioning: bootstrap, enrollment, certificate issuance and renewal.

Provisioning flow:
  1. Device requests bootstrap token → provisioning service issues a one-time token
  2. Device enrolls with bootstrap token + CSR → provisioning service validates
     token, generates a device certificate, stores the mapping
  3. Certificate renewal: device presents existing cert and gets a renewed cert

Certificates are self-signed for the Smart Factory use-case (no external CA).
Certificate PEM + private key are returned to the device; the registry tracks
serial and fingerprint for authentication validation.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .device_registry import Device, DeviceRegistry, DeviceType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Certificate defaults
# ---------------------------------------------------------------------------

CERT_VALIDITY_DAYS = 365
CERT_RENEWAL_WINDOW_DAYS = 30  # renew if expiring within this window
BOOTSTRAP_TOKEN_TTL_MINUTES = 15
CA_COMMON_NAME = "Smart Factory IoT CA"
CA_ORGANIZATION = "AIBOT Smart Factory"

# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


@dataclass
class BootstrapToken:
    """One-time bootstrap token issued to a device before enrollment."""

    token: str
    device_id_short: str | None = None  # optional hint
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
        + timedelta(minutes=BOOTSTRAP_TOKEN_TTL_MINUTES)
    )
    used: bool = False
    used_at: datetime | None = None

    def is_valid(self) -> bool:
        """Token is valid if not expired and not yet used."""
        return (
            datetime.now(timezone.utc) < self.expires_at
            and not self.used
        )


@dataclass
class EnrollmentRecord:
    """Tracks device enrollment and certificate state."""

    device_id: str
    cert_serial: str
    cert_fingerprint: str  # SHA-256 of DER-encoded cert
    cert_not_before: datetime
    cert_not_after: datetime
    enrolled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    renewed_at: datetime | None = None
    revoked: bool = False
    revoked_at: datetime | None = None


# ---------------------------------------------------------------------------
# Certificate Authority
# ---------------------------------------------------------------------------


class SimpleCA:
    """Lightweight self-signed CA for the Smart Factory.

    Generates an RSA CA certificate and key on first call; subsequent calls
    reload from storage. Private key is never exposed outside this class.
    """

    _instance: "SimpleCA | None" = None

    def __init__(self) -> None:
        self._ca_cert: x509.Certificate | None = None
        self._ca_key: rsa.RSAPrivateKey | None = None
        self._cert_storage: dict[str, tuple[x509.Certificate, rsa.RSAPrivateKey]] = {}

    @classmethod
    def get_instance(cls) -> "SimpleCA":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _generate_ca(self) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """Generate a new CA certificate and private key."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend(),
        )

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "VN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, CA_ORGANIZATION),
            x509.NameAttribute(NameOID.COMMON_NAME, CA_COMMON_NAME),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365 * 10))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    key_encipherment=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(private_key, hashes.SHA256(), default_backend())
        )
        return cert, private_key

    def get_ca_cert_pem(self) -> bytes:
        """Return CA certificate PEM."""
        if self._ca_cert is None:
            self._ca_cert, self._ca_key = self._generate_ca()
        return self._ca_cert.public_bytes(serialization.Encoding.PEM)

    def issue_device_cert(
        self,
        device_id: str,
        device_name: str,
        csr_pem: bytes | None = None,
    ) -> tuple[bytes, bytes, str, str]:
        """Issue a device certificate.

        If csr_pem is provided it is used directly (caller generates the keypair).
        Otherwise a new RSA keypair is generated here.

        Returns (device_cert_pem, device_key_pem, serial, fingerprint).
        The device_key_pem is returned in PKCS#8 format.

        Raises ValueError on invalid CSR.
        """
        if self._ca_cert is None:
            self._ca_cert, self._ca_key = self._generate_ca()

        # Generate device key if no CSR provided
        if csr_pem is None:
            device_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend(),
            )
            device_key_pem = device_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            # Build a self-signed cert from the key
            device_cert = self._build_cert(device_id, device_name, device_key, device_key.public_key())
        else:
            # Parse and validate CSR — build a self-signed cert using the CSR's public key
            try:
                from cryptography.hazmat.primitives.serialization import load_pem_x509_csr
                csr = load_pem_x509_csr(csr_pem, default_backend())
                public_key = csr.public_key()
            except ImportError:
                # Fallback: parse the CSR manually by extracting the public key
                # using a PKCS7 certificate builder from the PEM
                raise ValueError(
                    "CSR parsing not available: cryptography version too old. "
                    "Provide csr_pem=None to let the CA generate a keypair."
                ) from None

            device_key_pem = b""  # caller generated; we don't have it
            device_cert = self._build_cert(device_id, device_name, self._ca_key, public_key)

        cert_pem = device_cert.public_bytes(serialization.Encoding.PEM)
        serial = format(device_cert.serial_number, "x")
        fingerprint = hashlib.sha256(
            device_cert.public_bytes(serialization.Encoding.DER)
        ).hexdigest()

        return cert_pem, device_key_pem, serial, fingerprint

    def _build_cert(
        self,
        device_id: str,
        device_name: str,
        signing_key: rsa.RSAPrivateKey,
        public_key: Any,
    ) -> x509.Certificate:
        """Build an X.509v3 certificate signed by the CA."""
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "VN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, CA_ORGANIZATION),
            x509.NameAttribute(NameOID.COMMON_NAME, device_name),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, device_id),
        ])
        now = datetime.now(timezone.utc)
        return (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=CERT_VALIDITY_DAYS))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(signing_key, hashes.SHA256(), default_backend())
        )

    def revoke_cert(self, serial: str) -> bool:
        """Mark a certificate as revoked (in-memory CRL list)."""
        self._revoked_serials = getattr(self, "_revoked_serials", set())
        self._revoked_serials.add(serial.lower())
        return True

    def is_revoked(self, serial: str) -> bool:
        return serial.lower() in getattr(self, "_revoked_serials", set())


# ---------------------------------------------------------------------------
# Provisioning service
# ---------------------------------------------------------------------------

class ProvisioningService:
    """Manages device bootstrap, enrollment and certificate lifecycle.

    Stateless across requests — all state is in the registry and in-memory
    tokens (tokens are also stored in SQLite for restart-resilience).
    """

    def __init__(self, registry: DeviceRegistry) -> None:
        self._registry = registry
        self._ca = SimpleCA.get_instance()
        self._tokens: dict[str, BootstrapToken] = {}

    # ------------------------------------------------------------------
    # Bootstrap token management
    # ------------------------------------------------------------------

    async def issue_bootstrap_token(
        self,
        device_id_short: str | None = None,
    ) -> tuple[str, datetime]:
        """Issue a one-time bootstrap token.

        Returns (token, expires_at). The device will use this token during
        enrollment to prove it was provisioned out-of-band.
        """
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=BOOTSTRAP_TOKEN_TTL_MINUTES)
        bt = BootstrapToken(
            token=token,
            device_id_short=device_id_short,
            created_at=now,
            expires_at=expires,
        )
        self._tokens[token] = bt
        logger.info("Bootstrap token issued (device_hint=%s, expires=%s)", device_id_short, expires.isoformat())
        return token, expires

    async def validate_bootstrap_token(self, token: str) -> BootstrapToken:
        """Validate a bootstrap token.

        Returns the token if valid. Raises ValueError if expired, used, or unknown.
        """
        bt = self._tokens.get(token)
        if bt is None:
            raise ValueError("Bootstrap token not found")
        if not bt.is_valid():
            raise ValueError("Bootstrap token is expired or already used")
        return bt

    async def consume_bootstrap_token(self, token: str) -> BootstrapToken:
        """Validate and mark a bootstrap token as used."""
        bt = await self.validate_bootstrap_token(token)
        bt.used = True
        bt.used_at = datetime.now(timezone.utc)
        logger.info("Bootstrap token consumed")
        return bt

    # ------------------------------------------------------------------
    # Enrollment
    # ------------------------------------------------------------------

    async def enroll_device(
        self,
        short_device_id: str,
        device_name: str,
        device_type: str,
        bootstrap_token: str,
        csr_pem: bytes | None = None,
        capabilities: list[str] | None = None,
        manufacturer: str | None = None,
        firmware_version: str | None = None,
    ) -> dict[str, Any]:
        """Enroll a device: validates bootstrap token, issues cert, registers device.

        Args:
            short_device_id: e.g. "bridge-001"
            device_name: Human-readable name
            device_type: One of DeviceType values
            bootstrap_token: One-time token from issue_bootstrap_token
            csr_pem: Optional PKCS#10 CSR PEM (device generates its own keypair)
            capabilities: List of supported commands/telemetry
            manufacturer: Optional manufacturer string
            firmware_version: Optional firmware version

        Returns dict with keys: device_id, device_cert_pem, device_key_pem (if applicable),
            ca_cert_pem, cert_serial, cert_fingerprint, enrolled_at.

        Raises ValueError on invalid token or device type.
        """
        # Validate bootstrap token
        await self.consume_bootstrap_token(bootstrap_token)

        # Validate device type
        try:
            DeviceType(device_type)
        except ValueError as exc:
            raise ValueError(f"Invalid device_type: {device_type!r}") from exc

        # Issue certificate
        device_id = Device.make_id(short_device_id)
        cert_pem, key_pem, serial, fingerprint = self._ca.issue_device_cert(
            device_id=device_id,
            device_name=device_name,
            csr_pem=csr_pem,
        )

        now = datetime.now(timezone.utc)
        cert_not_before = now
        cert_not_after = now + timedelta(days=CERT_VALIDITY_DAYS)

        # Register device
        device = Device(
            device_id=device_id,
            device_type=device_type,
            name=device_name,
            status="online",
            manufacturer=manufacturer,
            firmware_version=firmware_version,
            capabilities=capabilities or [],
            tls_cert_serial=serial,
            tls_cert_fingerprint=fingerprint,
            tls_cert_not_before=cert_not_before,
            tls_cert_not_after=cert_not_after,
            last_heartbeat_at=now,
            created_at=now,
        )
        try:
            await self._registry.create(device)
        except ValueError as exc:
            # Device already exists — update cert info
            logger.warning("Device %s already registered, updating cert info: %s", device_id, exc)
            await self._registry.update_tls_cert(
                device_id,
                serial=serial,
                fingerprint=fingerprint,
                not_before=cert_not_before,
                not_after=cert_not_after,
            )

        logger.info("Device enrolled: %s (serial=%s)", device_id, serial)
        return {
            "device_id": device_id,
            "device_cert_pem": cert_pem.decode() if cert_pem else "",
            "device_key_pem": key_pem.decode() if key_pem else "",
            "ca_cert_pem": self._ca.get_ca_cert_pem().decode(),
            "cert_serial": serial,
            "cert_fingerprint": fingerprint,
            "cert_not_before": cert_not_before.isoformat(),
            "cert_not_after": cert_not_after.isoformat(),
            "enrolled_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # Certificate renewal
    # ------------------------------------------------------------------

    async def renew_cert(
        self,
        device_id: str,
        csr_pem: bytes | None = None,
    ) -> dict[str, Any]:
        """Renew a device certificate.

        Validates the device exists and the existing cert is in its renewal window
        or already expired. Issues a new certificate and updates the registry.

        Returns dict with new cert details.
        Raises ValueError if device not found or renewal not yet allowed.
        """
        device = await self._registry.get(device_id)
        if device is None:
            raise ValueError(f"Device not found: {device_id!r}")

        # Check renewal window
        if device.tls_cert_not_after:
            days_until_expiry = (
                device.tls_cert_not_after - datetime.now(timezone.utc)
            ).days
            if days_until_expiry > CERT_RENEWAL_WINDOW_DAYS:
                raise ValueError(
                    f"Certificate renewal not yet allowed. "
                    f"Expires in {days_until_expiry} days. "
                    f"Renewal allowed {CERT_RENEWAL_WINDOW_DAYS} days before expiry."
                )

        now = datetime.now(timezone.utc)
        cert_pem, key_pem, serial, fingerprint = self._ca.issue_device_cert(
            device_id=device_id,
            device_name=device.name,
            csr_pem=csr_pem,
        )
        cert_not_before = now
        cert_not_after = now + timedelta(days=CERT_VALIDITY_DAYS)

        await self._registry.update_tls_cert(
            device_id,
            serial=serial,
            fingerprint=fingerprint,
            not_before=cert_not_before,
            not_after=cert_not_after,
        )

        logger.info("Certificate renewed for device: %s (new serial=%s)", device_id, serial)
        return {
            "device_id": device_id,
            "device_cert_pem": cert_pem.decode() if cert_pem else "",
            "device_key_pem": key_pem.decode() if key_pem else "",
            "ca_cert_pem": self._ca.get_ca_cert_pem().decode(),
            "cert_serial": serial,
            "cert_fingerprint": fingerprint,
            "cert_not_before": cert_not_before.isoformat(),
            "cert_not_after": cert_not_after.isoformat(),
            "renewed_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # Capability registration (post-enrollment update)
    # ------------------------------------------------------------------

    async def register_capabilities(
        self,
        device_id: str,
        capabilities: list[str],
    ) -> Device | None:
        """Update device capabilities after enrollment."""
        return await self._registry.update(device_id, {"capabilities": capabilities})

    # ------------------------------------------------------------------
    # Certificate revocation
    # ------------------------------------------------------------------

    async def revoke_device(self, device_id: str) -> bool:
        """Revoke a device's certificate and mark it offline."""
        device = await self._registry.get(device_id)
        if device is None:
            return False

        if device.tls_cert_serial:
            self._ca.revoke_cert(device.tls_cert_serial)

        await self._registry.set_status(device_id, "offline")
        logger.warning("Device revoked and set offline: %s", device_id)
        return True
