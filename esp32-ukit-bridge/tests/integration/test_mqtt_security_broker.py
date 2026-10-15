"""MQTT Broker Security Tests — Issue #41.

These tests verify the MQTT broker security configuration:
- TC9:  Valid credentials connect successfully
- TC10: Invalid credentials rejected
- TC11: Anonymous connection rejected
- TC12: ACL violation denied (wrong topic, cross-device, command publish restriction)
- TC13: TLS connection with certificate validation

SCOPE LIMITATION (P5 FINDING):
  This test suite covers configuration correctness and live broker behavior.
  Live broker tests skip when mosquitto is unreachable (ports 1883/8883 not listening).
  For the PR #103 scope (config + ACL tests), this is acceptable -- the test file
  validates all security properties from source without requiring a running broker.
  Full TC9-TC13 live broker coverage requires:
    1. Docker daemon available in CI
    2. A separate 'mqtt-test-broker' container spun up per test class
    3. Test certs in infrastructure/certs/ committed or mounted in CI
  Live broker test results (pass/fail/skip) do NOT gate configuration-only tests.

P0 ACL FINDING:
  The original acl file used `pattern` rules inside user blocks. Mosquitto
  pattern rules apply GLOBALLY regardless of which user block they appear in,
  so a `pattern write smart-factory/%u/telemetry` rule in the "user bridge"
  block grants write access to ANY username. Fixed by replacing with literal
  `topic` rules (which ARE scoped per user) inside each user block.

ADR-0010 reference: docs/adr/adr-0010-mqtt-broker-security.md
Bridge contract:    esp32-ukit-bridge/docs/mqtt-contract.md
"""

from __future__ import annotations

import os
import re
import socket
import ssl
import subprocess
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
INFRA_DIR = REPO_ROOT / "infrastructure"
MOSQUITTO_CONF = INFRA_DIR / "mqtt" / "mosquitto.conf"
ACL_FILE = INFRA_DIR / "mqtt" / "acl"
ENTRYPOINT = INFRA_DIR / "mqtt" / "entrypoint.sh"
DOCKER_COMPOSE = INFRA_DIR / "docker-compose.yml"
CERTS_DIR = INFRA_DIR / "certs"


# ---------------------------------------------------------------------------
# Live-broker detection
# ---------------------------------------------------------------------------

def _is_docker_available() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _is_port_listening(port: int, timeout_s: float = 3.0) -> bool:
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=timeout_s)
        sock.close()
        return True
    except OSError:
        return False


DOCKER_AVAILABLE = _is_docker_available()
BROKER_AVAILABLE = _is_port_listening(1883)
TLS_BROKER_AVAILABLE = _is_port_listening(8883)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture
def conf_text() -> str:
    return _read(MOSQUITTO_CONF)


@pytest.fixture
def acl_text() -> str:
    return _read(ACL_FILE)


@pytest.fixture
def entrypoint_text() -> str:
    return _read(ENTRYPOINT)


@pytest.fixture
def compose_text() -> str:
    return _read(DOCKER_COMPOSE)


@pytest.fixture
def cert_dir() -> Path:
    return CERTS_DIR


# ---------------------------------------------------------------------------
# TC11: Anonymous denied
# ---------------------------------------------------------------------------

class TestAnonymousDenied:
    """TC11: Anonymous connections are rejected (allow_anonymous false)."""

    def test_conf_deny_anonymous(self, conf_text: str) -> None:
        """Active (non-comment) allow_anonymous directive must be 'false'."""
        active = {
            line.strip()
            for line in conf_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        assert "allow_anonymous false" in active, (
            "allow_anonymous must be 'false' in mosquitto.conf; "
            "anonymous access is not permitted per ADR-0010."
        )

    def test_no_conflicting_anonymous_true(self, conf_text: str) -> None:
        """No active line may set allow_anonymous to true."""
        for line in conf_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if stripped.startswith("allow_anonymous"):
                assert stripped == "allow_anonymous false", (
                    f"allow_anonymous must be false, got: {stripped!r}"
                )


# ---------------------------------------------------------------------------
# TC5: Credentials via environment (no hardcoded secrets)
# ---------------------------------------------------------------------------

class TestCredentialsEnvInjected:
    """TC5: No secrets in repo; credentials injected via environment variables."""

    def test_compose_requires_bridge_creds_via_env(self, compose_text: str) -> None:
        """docker-compose.yml must use ${VAR:?...} for bridge credentials."""
        assert "MQTT_BRIDGE_USERNAME" in compose_text
        assert "MQTT_BRIDGE_PASSWORD" in compose_text
        assert ":?set" in compose_text, "Bridge credentials must use :?set (mandatory env)."
    def test_compose_requires_gateway_creds_via_env(self, compose_text: str) -> None:
        """docker-compose.yml must use ${VAR:?...} for gateway credentials."""
        assert "MQTT_GATEWAY_USERNAME" in compose_text
        assert "MQTT_GATEWAY_PASSWORD" in compose_text
    def test_compose_requires_operator_creds_via_env(self, compose_text: str) -> None:
        """docker-compose.yml must require operator credentials via environment."""
        assert "MQTT_OPERATOR_PASSWORD" in compose_text
    def test_compose_no_literal_passwords(self, compose_text: str) -> None:
        """docker-compose.yml must not contain uncommented hardcoded password strings."""
        import re
        for line in compose_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            # healthcheck uses shell variable syntax ($VAR), not YAML env vars
            if stripped.startswith("test:"):
                continue
            lower = stripped.lower()
            if "password" in lower and "mqtt_" in lower:
                # Must reference env var (YAML ${VAR} substitution)
                assert (
                    "${" in line
                ), f"Line may contain hardcoded password: {line!r}"

    def test_entrypoint_reads_creds_from_env(self, entrypoint_text: str) -> None:
        """entrypoint.sh must read credentials from environment variables."""
        # New entrypoint uses ${VAR:-} parameter expansion syntax
        assert "${MQTT_BRIDGE_USERNAME" in entrypoint_text
        assert "${MQTT_BRIDGE_PASSWORD" in entrypoint_text
        assert "${MQTT_GATEWAY_USERNAME" in entrypoint_text
        assert "${MQTT_GATEWAY_PASSWORD" in entrypoint_text
        assert "mosquitto_passwd" in entrypoint_text

    def test_entrypoint_no_literal_passwords(self, entrypoint_text: str) -> None:
        """entrypoint.sh must not contain hardcoded literal password strings."""
        active_lines = [
            l.strip()
            for l in entrypoint_text.splitlines()
            if l.strip()
            and not l.strip().startswith("#")
            and not l.strip().startswith("echo")
            and not l.strip().startswith("set -e")
            and not l.strip().startswith("touch")
            and not l.strip().startswith("chown")
            and not l.strip().startswith("chmod")
        ]
        for line in active_lines:
            if re.search(r'"\w{8,}"', line):
                pytest.fail(f"Potential hardcoded credential in entrypoint.sh: {line!r}")

    def test_secrets_guide_documents_env_injection(self) -> None:
        """infrastructure/secrets-guide.md must document the env-var pattern."""
        guide = INFRA_DIR / "secrets-guide.md"
        assert guide.exists(), "infrastructure/secrets-guide.md must exist per ADR-0010."
        text = guide.read_text(encoding="utf-8").lower()
        assert "environment" in text or "env" in text


# ---------------------------------------------------------------------------
# TC2: ACL directions match bridge contract
# ---------------------------------------------------------------------------

class TestAclDirectionsMatchContract:
    """TC2: ACL rules enforce the exact publish/subscribe directions from
    esp32-ukit-bridge/docs/mqtt-contract.md and ADR-0010.

    Bridge publishes:  telemetry, status, command/ack
    Bridge subscribes: command/down  (all devices via + wildcard)
    Gateway subscribes: telemetry, status, command/ack  (all devices via +)
    Gateway does NOT publish to bridge topics.

    P0 FIX: all rules use literal `topic` directives (NOT `pattern`).
    Pattern rules apply globally regardless of user block, meaning a pattern
    rule inside "user bridge" grants that permission to ANY username.
    Literal `topic` rules are scoped to the user block they appear in.
    """

    def _block(self, text: str, user: str) -> str | None:
        m = re.search(
            rf"(?i)user\s+{re.escape(user)}\s+(.*?)(?=\nuser\s|\Z)",
            text, re.DOTALL,
        )
        return m.group(1) if m else None

    def _has_rule(self, block: str, directive: str, access: str, topic: str) -> bool:
        return bool(re.search(
            rf"(?i){re.escape(directive)}\s+{re.escape(access)}\s+{re.escape(topic)}", block
        ))

    def _has_no_rule(self, block: str, directive: str, access: str, topic: str) -> bool:
        return not self._has_rule(block, directive, access, topic)

    # -- Bridge positive rules ----------------------------------------------------

    def test_bridge_can_write_telemetry(self, acl_text: str) -> None:
        block = self._block(acl_text, "bridge")
        assert block is not None
        assert self._has_rule(block, "topic", "write", "smart-factory/+/telemetry")

    def test_bridge_can_write_status(self, acl_text: str) -> None:
        block = self._block(acl_text, "bridge")
        assert block is not None
        assert self._has_rule(block, "topic", "write", "smart-factory/+/status")

    def test_bridge_can_write_command_ack(self, acl_text: str) -> None:
        block = self._block(acl_text, "bridge")
        assert block is not None
        assert self._has_rule(block, "topic", "write", "smart-factory/+/command/ack")

    def test_bridge_subscribes_command_down(self, acl_text: str) -> None:
        block = self._block(acl_text, "bridge")
        assert block is not None
        assert self._has_rule(block, "topic", "read", "smart-factory/+/command/down")

    # -- Bridge negative rules ----------------------------------------------------

    def test_bridge_cannot_write_command_down(self, acl_text: str) -> None:
        """Bridge must NOT publish commands -- only authorized services do."""
        block = self._block(acl_text, "bridge")
        assert block is not None
        assert self._has_no_rule(
            block, "topic", "write", "smart-factory/+/command/down"
        ), "Bridge must NOT write to command/down."

    def test_no_pattern_rules_in_acl(self, acl_text: str) -> None:
        """P0 FIX: no pattern directives must exist in the ACL file.

        Pattern rules apply globally regardless of which user block they appear in.
        Replacing them with literal topic rules is the core P0 fix.
        """
        pattern_directives = re.findall(r"^\s*pattern\s+", acl_text, re.MULTILINE)
        assert not pattern_directives, (
            f"ACL must not contain 'pattern' directives. "
            f"Found: {pattern_directives}. Use literal 'topic' rules instead."
        )

    def test_gateway_subscribes_telemetry(self, acl_text: str) -> None:
        block = self._block(acl_text, "gateway")
        assert block is not None
        assert self._has_rule(block, "topic", "read", "smart-factory/+/telemetry")

    def test_gateway_subscribes_status(self, acl_text: str) -> None:
        block = self._block(acl_text, "gateway")
        assert block is not None
        assert self._has_rule(block, "topic", "read", "smart-factory/+/status")

    def test_gateway_subscribes_command_ack(self, acl_text: str) -> None:
        block = self._block(acl_text, "gateway")
        assert block is not None
        assert self._has_rule(block, "topic", "read", "smart-factory/+/command/ack")

    def test_gateway_cannot_write_bridge_topics(self, acl_text: str) -> None:
        """Gateway must NOT publish telemetry, status, or command/ack per ADR-0010."""
        block = self._block(acl_text, "gateway")
        assert block is not None
        for topic in ("telemetry", "status", "command/ack"):
            assert self._has_no_rule(
                block, "topic", "write", f"smart-factory/+/{topic}"
            ), f"Gateway must NOT write to {topic}."

    def test_operator_is_readonly(self, acl_text: str) -> None:
        """Operator must have no write access to any topic."""
        block = self._block(acl_text, "operator")
        if block is None:
            pytest.skip("Operator user not defined in ACL (optional role).")
        assert self._has_no_rule(block, "topic", "write", "smart-factory/+/")


# ---------------------------------------------------------------------------
# TC10: Invalid credentials rejected
# ---------------------------------------------------------------------------

class TestInvalidCredentialsRejected:
    """TC10: Invalid credentials are rejected by the broker."""

    def test_conf_has_password_file(self, conf_text: str) -> None:
        """mosquitto.conf must reference a password file."""
        active = {
            line.strip()
            for line in conf_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        assert any(line.startswith("password_file") for line in active)

    @pytest.mark.skipif(not BROKER_AVAILABLE, reason="No live broker on port 1883")
    def test_broker_rejects_wrong_password(self) -> None:
        """Live broker: correct username, wrong password -> RC 4."""
        import paho.mqtt.client as mqtt

        results: dict = {}

        def on_connect(_c, _ud, _flags, rc, _props):
            results["rc"] = rc
            _c.disconnect()

        client = mqtt.Client(
            client_id="test-reject-wrong-pw",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.username_pw_set("bridge", "wrong_password_12345")
        client.on_connect = on_connect
        client.connect("127.0.0.1", 1883, keepalive=10)
        client.loop_start()

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if "rc" in results:
                break
            time.sleep(0.2)
        client.loop_stop()

        assert results.get("rc") == 4, (
            f"Wrong password -> RC 4 expected, got RC={results.get('rc')}. "
            "This verifies TC10: invalid credentials are rejected."
        )

    @pytest.mark.skipif(not BROKER_AVAILABLE, reason="No live broker on port 1883")
    def test_broker_rejects_unknown_user(self) -> None:
        """Live broker: completely unknown username -> RC 4 or 5."""
        import paho.mqtt.client as mqtt

        results: dict = {}

        def on_connect(_c, _ud, _flags, rc, _props):
            results["rc"] = rc
            _c.disconnect()

        client = mqtt.Client(
            client_id="test-unknown-user",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.username_pw_set("nonexistent_user_xyz123", "anypassword")
        client.on_connect = on_connect
        client.connect("127.0.0.1", 1883, keepalive=10)
        client.loop_start()

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if "rc" in results:
                break
            time.sleep(0.2)
        client.loop_stop()

        assert results.get("rc") in (4, 5), (
            f"Unknown user -> RC 4 or 5 expected, got RC={results.get('rc')}."
        )


# ---------------------------------------------------------------------------
# TC9: Valid credentials connect successfully
# ---------------------------------------------------------------------------

class TestValidCredentials:
    """TC9: Valid credentials connect successfully with the live broker."""

    @pytest.mark.skipif(not BROKER_AVAILABLE, reason="No live broker on port 1883")
    def test_valid_bridge_credentials_connect(self) -> None:
        """Valid bridge credentials connect successfully (RC=0)."""
        import paho.mqtt.client as mqtt

        username = os.environ.get("MQTT_BRIDGE_USERNAME", "")
        password = os.environ.get("MQTT_BRIDGE_PASSWORD", "")
        if not username or not password:
            pytest.skip(
                "MQTT_BRIDGE_USERNAME and MQTT_BRIDGE_PASSWORD must be set in environment."
            )

        results: dict = {}

        def on_connect(_c, _ud, _flags, rc, _props):
            results["rc"] = rc
            _c.disconnect()

        client = mqtt.Client(
            client_id="test-valid-creds",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.username_pw_set(username, password)
        client.on_connect = on_connect
        client.connect("127.0.0.1", 1883, keepalive=10)
        client.loop_start()

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if "rc" in results:
                break
            time.sleep(0.2)
        client.loop_stop()

        assert results.get("rc") == 0, (
            f"Valid credentials must connect (RC=0), got RC={results.get('rc')}."
        )


# ---------------------------------------------------------------------------
# TC13: TLS configuration and certificate material
# ---------------------------------------------------------------------------

class TestTlsConfiguration:
    """TC4/TC13: TLS listener configuration and certificate validation.

    P2 FIX: the static mosquitto.conf no longer contains `listener 8883` or cert
    directives unconditionally. The entrypoint generates them only when TLS_MODE=yes
    (tls compose profile). The static conf tests verify cert lines are absent from
    the source file (no silent plaintext fallback when certs are mounted).
    """

    def test_tls_listener_NOT_in_static_conf(self, conf_text: str) -> None:
        """P2 FIX: static mosquitto.conf must NOT unconditionally declare listener 8883.

        If listener 8883 is in the static config, mosquitto will fail at startup when
        cert files are mounted but TLS is not desired. The TLS listener must only be
        present in the entrypoint-generated config (when TLS_MODE=yes).
        """
        active = {
            line.strip()
            for line in conf_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        assert "listener 8883" not in active, (
            "listener 8883 must NOT be in the static mosquitto.conf. "
            "P2 FIX: it is conditionally appended by entrypoint.sh when TLS_MODE=yes."
        )

    def test_tls_cert_directives_NOT_in_static_conf(self, conf_text: str) -> None:
        """P2 FIX: cert directives must not be in static conf (conditional only)."""
        for line in conf_text.splitlines():
            s = line.strip()
            if s.startswith("#") or not s:
                continue
            assert not s.startswith("cafile "), (
                f"cafile must NOT be in static mosquitto.conf (P2 fix). Got: {s!r}"
            )
            assert not s.startswith("certfile "), (
                f"certfile must NOT be in static mosquitto.conf (P2 fix). Got: {s!r}"
            )
            assert not s.startswith("keyfile "), (
                f"keyfile must NOT be in static mosquitto.conf (P2 fix). Got: {s!r}"
            )

    def test_entrypoint_generates_tls_block(self, entrypoint_text: str) -> None:
        """Entrypoint must conditionally append listener 8883 + certs when TLS_MODE=yes.

        This is the P2 fix mechanism: cert lines are NOT in static conf, but are
        appended by entrypoint only when TLS_MODE=yes. If certs are mounted without
        TLS_MODE=yes, mosquitto still starts cleanly on plaintext 1883 (no 8883).
        """
        assert 'if [ "$TLS_MODE" = "yes" ]; then' in entrypoint_text, (
            "Entrypoint must check TLS_MODE=yes to enable TLS."
        )
        assert "listener 8883" in entrypoint_text, (
            "Entrypoint must append 'listener 8883' when TLS_MODE=yes."
        )
        assert "cafile" in entrypoint_text, (
            "Entrypoint must append 'cafile' directive when TLS_MODE=yes."
        )
        assert "certfile" in entrypoint_text, (
            "Entrypoint must append 'certfile' directive when TLS_MODE=yes."
        )
        assert "keyfile" in entrypoint_text, (
            "Entrypoint must append 'keyfile' directive when TLS_MODE=yes."
        )
        # Entrypoint must exit non-zero if certs are missing with TLS_MODE=yes
        assert "FATAL" in entrypoint_text, (
            "Entrypoint must exit with error if certs missing and TLS_MODE=yes."
        )

    def test_tls_cert_files_exist(self, cert_dir: Path) -> None:
        """Required TLS files must exist in infrastructure/certs/."""
        for name in ("ca.crt", "server.crt", "server.key"):
            path = cert_dir / name
            assert path.exists(), f"TLS file missing: {path}."

    def test_ca_cert_is_valid_pem(self, cert_dir: Path) -> None:
        """ca.crt must be a valid PEM X.509 certificate."""
        r = subprocess.run(
            ["openssl", "x509", "-in", str(cert_dir / "ca.crt"), "-noout", "-subject"],
            capture_output=True, text=True, timeout=5,
        )
        assert r.returncode == 0, f"ca.crt is not valid X.509 PEM: {r.stderr}"

    def test_server_cert_is_valid_pem(self, cert_dir: Path) -> None:
        """server.crt must be a valid PEM X.509 certificate."""
        r = subprocess.run(
            ["openssl", "x509", "-in", str(cert_dir / "server.crt"), "-noout", "-subject"],
            capture_output=True, text=True, timeout=5,
        )
        assert r.returncode == 0, f"server.crt is not valid X.509 PEM: {r.stderr}"

    def test_server_key_is_valid(self, cert_dir: Path) -> None:
        """server.key must be a valid EC or RSA private key."""
        srv_key = cert_dir / "server.key"
        r = subprocess.run(
            ["openssl", "ec", "-in", str(srv_key), "-noout"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            r = subprocess.run(
                ["openssl", "rsa", "-in", str(srv_key), "-noout"],
                capture_output=True, text=True, timeout=5,
            )
        assert r.returncode == 0, f"server.key is not valid EC/RSA key: {r.stderr}"

    def test_server_cert_signed_by_ca(self, cert_dir: Path) -> None:
        """server.crt must be signed by ca.crt."""
        r = subprocess.run(
            [
                "openssl", "verify", "-CAfile", str(cert_dir / "ca.crt"),
                str(cert_dir / "server.crt"),
            ],
            capture_output=True, text=True, timeout=5,
        )
        assert r.returncode == 0 and "OK" in r.stdout, (
            f"Server cert not signed by CA. Output: {r.stdout} {r.stderr}"
        )

    def test_ca_cert_not_expired(self, cert_dir: Path) -> None:
        """CA certificate must not be expired."""
        import datetime
        from email.utils import parsedate_to_datetime

        r = subprocess.run(
            ["openssl", "x509", "-in", str(cert_dir / "ca.crt"), "-noout", "-enddate"],
            capture_output=True, text=True, timeout=5,
        )
        assert r.returncode == 0, f"Cannot read CA end date: {r.stderr}"
        date_str = r.stdout.split("=", 1)[1].strip()
        expiry = parsedate_to_datetime(date_str)
        now = datetime.datetime.now(datetime.timezone.utc)
        assert expiry > now, f"CA certificate expired on {expiry}."

    def test_tls_connection_with_valid_ca(self, cert_dir: Path) -> None:
        """Live TLS broker: connection with correct CA succeeds (TLS handshake OK).

        ESP32 hardware TLS/HIL is not claimed -- this validates Python + broker only.
        """
        if not TLS_BROKER_AVAILABLE:
            pytest.skip("No live TLS broker on port 8883.")

        import paho.mqtt.client as mqtt

        results: dict = {}

        def on_connect(_c, _ud, _flags, rc, _props):
            results["rc"] = rc
            _c.disconnect()

        client = mqtt.Client(
            client_id="test-tls-valid",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.tls_set(
            ca_certs=str(cert_dir / "ca.crt"),
            cert_reqs=ssl.CERT_REQUIRED,
        )
        client.on_connect = on_connect

        try:
            client.connect("127.0.0.1", 8883, keepalive=10)
            client.loop_start()

            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if "rc" in results:
                    break
                time.sleep(0.3)
            client.loop_stop()

            # RC 0 = TLS OK + auth OK; RC 5 = TLS OK but not authorized
            assert results.get("rc") in (0, 5), (
                f"TLS+valid CA: expected RC 0 or 5, got RC={results.get('rc')}."
            )
        except ssl.SSLError as e:
            pytest.fail(f"TLS handshake failed with correct CA: {e}")

    def test_tls_connection_rejects_wrong_ca(self) -> None:
        """Live TLS broker: connection with wrong/missing CA must fail at TLS level."""
        if not TLS_BROKER_AVAILABLE:
            pytest.skip("No live TLS broker on port 8883.")

        import paho.mqtt.client as mqtt

        results: dict = {}

        def on_connect(_c, _ud, _flags, rc, _props):
            results["rc"] = rc
            _c.disconnect()

        client = mqtt.Client(
            client_id="test-tls-wrong-ca",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.tls_set(
            ca_certs="/nonexistent/path/to/ca.crt",
            cert_reqs=ssl.CERT_REQUIRED,
        )
        client.on_connect = on_connect

        client.connect("127.0.0.1", 8883, keepalive=5)
        client.loop_start()

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if "rc" in results:
                break
            time.sleep(0.3)
        client.loop_stop()

        assert results.get("rc", -1) != 0, (
            "TLS connection with wrong CA must be rejected."
        )

    def test_production_require_certificate_documented(self, entrypoint_text: str) -> None:
        """require_certificate setting must be documented (dev=false, prod=true)."""
        assert "require_certificate" in entrypoint_text, (
            "Entrypoint must set require_certificate in the TLS block."
        )


# ---------------------------------------------------------------------------
# TC12: ACL denial (live broker)
# ---------------------------------------------------------------------------

class TestAclEnforcementLive:
    """TC12: Live broker enforces ACL — wrong topic, cross-device, command publish."""

    @pytest.mark.skipif(not BROKER_AVAILABLE, reason="No live broker on port 1883")
    def test_bridge_credential_cannot_write_command_down(self) -> None:
        """Bridge credential must be denied when trying to publish to command/down.

        Per ADR-0010 negative example: bridge publishes telemetry/status/ACK,
        not commands.
        """
        username = os.environ.get("MQTT_BRIDGE_USERNAME", "bridge")
        password = os.environ.get("MQTT_BRIDGE_PASSWORD", "")

        import paho.mqtt.client as mqtt

        results: dict = {}

        def on_connect(_c, _ud, _flags, rc, _props):
            results["rc"] = rc
            if rc == 0:
                res = _c.publish(
                    f"smart-factory/{username}/command/down",
                    b'{"command_name":"CONVEYOR_START","arguments":["60"]}',
                )
                results["pub_rc"] = res.rc
                _c.disconnect()

        client = mqtt.Client(
            client_id="test-acl-command-publish",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.username_pw_set(username, password)
        client.on_connect = on_connect
        client.connect("127.0.0.1", 1883, keepalive=10)
        client.loop_start()

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if "pub_rc" in results:
                break
            time.sleep(0.2)
        client.loop_stop()

        # MQTT client publish() returns 0=success, 1=error, 2=acl_denied
        pub_rc = results.get("pub_rc")
        assert pub_rc == 2, (
            f"Publishing command/down with bridge credential must be ACL-denied "
            f"(rc=2), got rc={pub_rc}."
        )

    @pytest.mark.skipif(not BROKER_AVAILABLE, reason="No live broker on port 1883")
    def test_gateway_credential_cannot_publish_telemetry(self) -> None:
        """Gateway credential must be denied when trying to publish telemetry."""
        username = os.environ.get("MQTT_GATEWAY_USERNAME", "gateway")
        password = os.environ.get("MQTT_GATEWAY_PASSWORD", "")

        import paho.mqtt.client as mqtt

        results: dict = {}

        def on_connect(_c, _ud, _flags, rc, _props):
            results["rc"] = rc
            if rc == 0:
                res = _c.publish(
                    f"smart-factory/{username}/telemetry",
                    b'{"device_id":"test","values":["CONVEYOR","RUNNING"]}',
                )
                results["pub_rc"] = res.rc
                _c.disconnect()

        client = mqtt.Client(
            client_id="test-acl-gateway-publish",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.username_pw_set(username, password)
        client.on_connect = on_connect
        client.connect("127.0.0.1", 1883, keepalive=10)
        client.loop_start()

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if "pub_rc" in results:
                break
            time.sleep(0.2)
        client.loop_stop()

        pub_rc = results.get("pub_rc")
        assert pub_rc == 2, (
            f"Gateway publishing telemetry must be ACL-denied (rc=2), got rc={pub_rc}."
        )


# ---------------------------------------------------------------------------
# Configuration syntax validation
# ---------------------------------------------------------------------------

class TestConfigSyntax:
    """Configuration files must be syntactically valid and complete."""

    def test_mosquitto_conf_has_listener(self, conf_text: str) -> None:
        active = {
            line.strip()
            for line in conf_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        assert any(line.startswith("listener ") for line in active)

    def test_mosquitto_conf_has_acl_file(self, conf_text: str) -> None:
        active = {
            line.strip()
            for line in conf_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        assert any(line.startswith("acl_file ") for line in active)

    def test_mosquitto_conf_has_password_file(self, conf_text: str) -> None:
        active = {
            line.strip()
            for line in conf_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        assert any(line.startswith("password_file ") for line in active)

    def test_acl_file_not_empty(self, acl_text: str) -> None:
        lines = [
            l.strip()
            for l in acl_text.splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
        assert lines, "ACL file is empty. ACL enforcement is required per ADR-0010."

    def test_acl_defines_bridge_and_gateway(self, acl_text: str) -> None:
        assert re.search(r"(?i)\buser\s+bridge\b", acl_text)
        assert re.search(r"(?i)\buser\s+gateway\b", acl_text)

    def test_entrypoint_calls_mosquitto(self, entrypoint_text: str) -> None:
        assert "mosquitto_passwd" in entrypoint_text
        assert "exec mosquitto" in entrypoint_text

    def test_compose_defines_mqtt_service(self, compose_text: str) -> None:
        assert "services:" in compose_text
        assert "mqtt:" in compose_text
        assert "eclipse-mosquitto" in compose_text

    def test_compose_no_conf_mount(self, compose_text: str) -> None:
        """mosquitto.conf must NOT be mounted from host.

        P1 FIX: mosquitto.conf is generated at container start by entrypoint.sh
        into the mqtt-conf named volume. Mounting it from host would prevent the
        entrypoint from generating the TLS-conditional config.
        """
        for line in compose_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            assert not (
                stripped.startswith("- ") and "/mosquitto/config/mosquitto.conf" in stripped
            ), f"mosquitto.conf must not be mounted from host. Got line: {line!r}"
        assert "acl" in compose_text
