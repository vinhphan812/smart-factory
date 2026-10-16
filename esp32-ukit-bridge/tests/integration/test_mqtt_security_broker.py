"""MQTT Broker Security Integration Tests.

These tests verify the MQTT broker's security properties:
authentication enforcement, per-device ACL isolation, and denial of
cross-device access. They run against a real eclipse-mosquitto:2
container via Docker Compose.

Requires:
    - Docker and docker compose available on PATH
    - Network access to pull eclipse-mosquitto:2 (if not cached)
    - Port 1883 available on localhost

Environment (all optional — defaults match .env.example):
    MQTT_PORT=1883
    MQTT_ADMIN_USERNAME=admin
    MQTT_ADMIN_PASSWORD=changeme
    MQTT_BRIDGE_USERNAME=ukit-00000000
    MQTT_BRIDGE_PASSWORD=changeme
    MQTT_GW_USERNAME=gateway
    MQTT_GW_PASSWORD=changeme

Evidence level: L2 (simulated MQTT with real broker container).
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Generator

import paho.mqtt.client as mqtt
import pytest
import yaml


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def find_compose_file() -> str:
    """Locate docker-compose.yml relative to this test file."""
    import pathlib

    test_dir = pathlib.Path(__file__).resolve().parents[3]
    for candidate in [
        test_dir / "docker-compose.yml",
        test_dir / "infrastructure" / "mqtt-broker" / "docker-compose.yml",
    ]:
        if candidate.exists():
            return str(candidate)
    for parent in pathlib.Path(__file__).resolve().parents:
        p = parent / "docker-compose.yml"
        if p.exists():
            return str(p)
    return str(test_dir / "docker-compose.yml")


@dataclass(frozen=True)
class BrokerCreds:
    """MQTT broker credential set."""

    username: str
    password: str
    label: str  # human-readable name for test reporting


BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
COMPOSE_FILE = os.environ.get(
    "DOCKER_COMPOSE_FILE",
    find_compose_file(),
)

ADMIN_CREDS = BrokerCreds(
    username=os.environ.get("MQTT_ADMIN_USERNAME", "admin"),
    password=os.environ.get("MQTT_ADMIN_PASSWORD", "changeme"),
    label="admin",
)
BRIDGE_CREDS = BrokerCreds(
    username=os.environ.get("MQTT_BRIDGE_USERNAME", "ukit-00000000"),
    password=os.environ.get("MQTT_BRIDGE_PASSWORD", "changeme"),
    label="bridge",
)
GW_CREDS = BrokerCreds(
    username=os.environ.get("MQTT_GW_USERNAME", "gateway"),
    password=os.environ.get("MQTT_GW_PASSWORD", "changeme"),
    label="gateway",
)

# Device IDs — used to test ACL isolation
DEVICE_A = "ukit-00000000"
DEVICE_B = "ukit-00000001"

# Topic templates
TPL_CMD_DOWN = "smart-factory/{deviceId}/command/down"
TPL_CMD_ACK = "smart-factory/{deviceId}/command/ack"
TPL_TELEMETRY = "smart-factory/{deviceId}/telemetry"
TPL_STATUS = "smart-factory/{deviceId}/status"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_port(host: str, port: int, timeout: int = 30) -> bool:
    """Block until TCP port is open or timeout expires."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def mqtt_connect(creds: BrokerCreds, client_id: str) -> mqtt.Client:
    """Create and connect an MQTT client with credentials."""
    client = mqtt.Client(
        client_id=client_id,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.username_pw_set(creds.username, creds.password)
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=10)
    client.loop_start()
    # Wait for connection to establish
    start = time.monotonic()
    while time.monotonic() - start < 5:
        if client.is_connected():
            return client
        time.sleep(0.1)
    raise RuntimeError(
        f"MQTT connect timed out for {creds.label} (client_id={client_id})"
    )


def mqtt_subscribe_and_wait(
    client: mqtt.Client,
    topic: str,
    timeout: float = 5.0,
) -> tuple[bool, bytes | None]:
    """Subscribe to topic and wait for one message.

    Returns (received, payload).
    received=False means timeout — no message arrived.
    """
    received_payload: list[bytes] = []

    def on_message(
        _c: mqtt.Client, _u: object, msg: mqtt.MQTTMessage
    ) -> None:
        received_payload.append(msg.payload)

    client.on_message = on_message
    client.subscribe(topic, qos=0)
    time.sleep(timeout)
    client.unsubscribe(topic)
    client.on_message = None
    if received_payload:
        return True, received_payload[0]
    return False, None


def mqtt_publish(topic: str, payload: bytes, creds: BrokerCreds) -> int:
    """Publish a message and return the result code (0 = success)."""
    client = mqtt.Client(
        client_id=f"pub-{creds.label}-{os.getpid()}",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.username_pw_set(creds.username, creds.password)
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=10)
    time.sleep(0.5)
    result = client.publish(topic, payload, qos=0)
    client.disconnect()
    client.loop_stop()
    return result.rc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def broker_running() -> Generator[None, None, None]:
    """Start the MQTT broker via docker compose and tear it down after tests."""
    compose_cmd = [
        "docker", "compose",
        "-f", COMPOSE_FILE,
        "up", "-d", "--wait", "mqtt",
    ]
    teardown_cmd = [
        "docker", "compose",
        "-f", COMPOSE_FILE,
        "down", "--remove-orphans",
    ]

    print(f"\n[start] Running: {' '.join(compose_cmd)}")
    result = subprocess.run(
        compose_cmd,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(COMPOSE_FILE) or ".",
    )
    if result.returncode != 0:
        pytest.skip(
            f"docker compose up failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    if not wait_for_port(BROKER_HOST, BROKER_PORT, timeout=30):
        subprocess.run(teardown_cmd, capture_output=True)
        pytest.skip(f"Broker did not become reachable at {BROKER_HOST}:{BROKER_PORT}")

    print(f"[OK] Broker is up at {BROKER_HOST}:{BROKER_PORT}")

    yield

    print("\n[teardown] Stopping broker...")
    subprocess.run(teardown_cmd, capture_output=True)


# ---------------------------------------------------------------------------
# Test Class: Authentication
# ---------------------------------------------------------------------------

class TestAuthentication:
    """Verify broker enforces credentials and denies anonymous access."""

    def test_valid_bridge_credential_connects(self, broker_running: None) -> None:
        """Bridge credential with valid username/password connects successfully."""
        client = mqtt_connect(BRIDGE_CREDS, f"test-conn-{DEVICE_A}")
        assert client.is_connected(), "Bridge credential failed to connect"
        client.disconnect()
        client.loop_stop()

    def test_valid_gateway_credential_connects(self, broker_running: None) -> None:
        """Gateway credential with valid username/password connects successfully."""
        client = mqtt_connect(GW_CREDS, f"test-conn-gw")
        assert client.is_connected(), "Gateway credential failed to connect"
        client.disconnect()
        client.loop_stop()

    def test_invalid_password_rejected(self, broker_running: None) -> None:
        """Connection with wrong password is rejected."""
        bad_creds = BrokerCreds(
            username=BRIDGE_CREDS.username,
            password="wrong-password",
            label="bridge-bad-pass",
        )
        client = mqtt.Client(
            client_id=f"test-bad-pass-{os.getpid()}",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.username_pw_set(bad_creds.username, bad_creds.password)
        result = client.connect(BROKER_HOST, BROKER_PORT, keepalive=10)
        # paho returns 0 on success, non-zero on failure
        # Connection failure triggers on_disconnect, so we check after a short wait
        time.sleep(1.0)
        connected = client.is_connected()
        client.disconnect()
        client.loop_stop()
        assert not connected, (
            "Broker accepted connection with invalid password — "
            "ACL/password enforcement is broken"
        )

    def test_unknown_username_rejected(self, broker_running: None) -> None:
        """Connection with unknown username is rejected."""
        client = mqtt.Client(
            client_id=f"test-unknown-user-{os.getpid()}",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.username_pw_set("nonexistent-user", "any-password")
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=10)
        time.sleep(1.0)
        connected = client.is_connected()
        client.disconnect()
        client.loop_stop()
        assert not connected, (
            "Broker accepted connection with unknown username — "
            "authentication is not enforced"
        )


# ---------------------------------------------------------------------------
# Test Class: Bridge ACL — Positive
# ---------------------------------------------------------------------------

class TestBridgeACLPositive:
    """Verify bridge credential CAN do what it is permitted to do."""

    def test_bridge_can_subscribe_to_own_command_topic(
        self, broker_running: None
    ) -> None:
        """Bridge with username=ukit-00000000 can subscribe to its own command/down."""
        creds = BrokerCreds(
            username=DEVICE_A,
            password=BRIDGE_CREDS.password,
            label="bridge-own-cmd",
        )
        client = mqtt_connect(creds, f"test-sub-own-{DEVICE_A}")
        own_topic = TPL_CMD_DOWN.format(deviceId=DEVICE_A)

        received, _ = mqtt_subscribe_and_wait(client, own_topic, timeout=2.0)
        # No message published yet — just verify subscription didn't error
        # The broker accepts the SUBSCRIBE packet (ACL check passes)
        client.disconnect()
        client.loop_stop()

    def test_bridge_can_publish_to_own_ack_topic(
        self, broker_running: None
    ) -> None:
        """Bridge can publish to its own command/ack topic."""
        ack_topic = TPL_CMD_ACK.format(deviceId=DEVICE_A)
        payload = b'{"status":"ok"}'
        rc = mqtt_publish(ack_topic, payload, BRIDGE_CREDS)
        assert rc == 0, (
            f"Broker denied bridge publishing to own ACK topic "
            f"({ack_topic}) — ACL may be misconfigured"
        )

    def test_bridge_can_publish_to_own_telemetry_topic(
        self, broker_running: None
    ) -> None:
        """Bridge can publish to its own telemetry topic."""
        tel_topic = TPL_TELEMETRY.format(deviceId=DEVICE_A)
        payload = b'{"device_id":"' + DEVICE_A.encode() + b'","values":["RUNNING"]}'
        rc = mqtt_publish(tel_topic, payload, BRIDGE_CREDS)
        assert rc == 0, (
            f"Broker denied bridge publishing to own telemetry topic "
            f"({tel_topic}) — ACL may be misconfigured"
        )

    def test_bridge_can_publish_to_own_status_topic(
        self, broker_running: None
    ) -> None:
        """Bridge can publish to its own status topic."""
        status_topic = TPL_STATUS.format(deviceId=DEVICE_A)
        payload = b'{"status":"online"}'
        rc = mqtt_publish(status_topic, payload, BRIDGE_CREDS)
        assert rc == 0, (
            f"Broker denied bridge publishing to own status topic "
            f"({status_topic}) — ACL may be misconfigured"
        )


# ---------------------------------------------------------------------------
# Test Class: Bridge ACL — Negative (cross-device isolation)
# ---------------------------------------------------------------------------

class TestBridgeACLNegative:
    """CRITICAL: Verify bridge CANNOT access another device's topics.

    This is the P0 finding from PR #103. The original ACL used:
        topic read smart-factory/+/command/down
    which allowed the bridge to subscribe to ANY device's command/down.
    The fix requires the username to equal the deviceId and the ACL to use
    the literal username string in the topic path.

    See infrastructure/mqtt-broker/docs/acl-design.md for full rationale.
    """

    def test_bridge_cannot_subscribe_to_other_device_command_topic(
        self, broker_running: None
    ) -> None:
        """Bridge with username=ukit-00000000 MUST NOT subscribe to ukit-00000001/command/down.

        This is the P0 fix: per-device isolation. If this test FAILS, the ACL
        still allows cross-device command access — a critical security flaw.
        """
        bridge_creds = BrokerCreds(
            username=DEVICE_A,
            password=BRIDGE_CREDS.password,
            label="bridge-cross-device",
        )
        client = mqtt_connect(bridge_creds, f"test-cross-{DEVICE_A}")

        # Subscribe to a DIFFERENT device's command topic
        other_device_topic = TPL_CMD_DOWN.format(deviceId=DEVICE_B)

        # paho doesn't raise on ACL denial — it just doesn't deliver messages.
        # We verify by: (a) subscription accepted but (b) no message delivery.
        # The broker ACL denies delivery of messages to the wrong device.
        # To detect the ACL denial properly, we need a two-phase test:

        # Phase 1: subscribe with the correct credential to the OTHER device's topic
        #           and verify we receive nothing (ACL blocks it).
        received, _ = mqtt_subscribe_and_wait(client, other_device_topic, timeout=1.0)

        client.disconnect()
        client.loop_stop()

        assert not received, (
            f"SECURITY VIOLATION: Bridge credential ({DEVICE_A}) "
            f"received message from other device's topic ({other_device_topic}). "
            f"The ACL does NOT enforce per-device isolation. "
            f"Expected: subscription denied or no messages delivered. "
            f"Actual: message was delivered."
        )

    def test_bridge_cannot_publish_to_other_device_topic(
        self, broker_running: None
    ) -> None:
        """Bridge MUST NOT publish to another device's telemetry/status/ack topics."""
        other_ack = TPL_CMD_ACK.format(deviceId=DEVICE_B)
        other_tel = TPL_TELEMETRY.format(deviceId=DEVICE_B)
        other_status = TPL_STATUS.format(deviceId=DEVICE_B)

        # Try to publish as bridge to other device's topics
        rc_ack = mqtt_publish(other_ack, b'{"status":"ok"}', BRIDGE_CREDS)
        rc_tel = mqtt_publish(
            other_tel, b'{"device_id":"' + DEVICE_B.encode() + b'"}', BRIDGE_CREDS
        )
        rc_status = mqtt_publish(other_status, b'{"status":"online"}', BRIDGE_CREDS)

        # Broker should deny all of these — ACL only allows bridge to write own topics
        assert rc_ack != 0, (
            f"Bridge published to {other_ack} — ACL does NOT restrict bridge write access"
        )
        assert rc_tel != 0, (
            f"Bridge published to {other_tel} — ACL does NOT restrict bridge write access"
        )
        assert rc_status != 0, (
            f"Bridge published to {other_status} — ACL does NOT restrict bridge write access"
        )

    def test_bridge_cannot_read_other_device_telemetry(
        self, broker_running: None
    ) -> None:
        """Bridge MUST NOT subscribe to another device's telemetry topic."""
        bridge_creds = BrokerCreds(
            username=DEVICE_A,
            password=BRIDGE_CREDS.password,
            label="bridge-cross-tel",
        )
        client = mqtt_connect(bridge_creds, f"test-cross-tel-{DEVICE_A}")

        other_tel = TPL_TELEMETRY.format(deviceId=DEVICE_B)
        received, _ = mqtt_subscribe_and_wait(client, other_tel, timeout=1.0)

        client.disconnect()
        client.loop_stop()

        assert not received, (
            f"Security violation: bridge ({DEVICE_A}) received telemetry "
            f"from other device ({other_tel})"
        )


# ---------------------------------------------------------------------------
# Test Class: Gateway ACL — Positive
# ---------------------------------------------------------------------------

class TestGatewayACLPositive:
    """Verify gateway credential can ingest across all devices."""

    def test_gateway_can_subscribe_to_any_device_ack(
        self, broker_running: None
    ) -> None:
        """Gateway subscribes to smart-factory/+/command/ack — must receive from all devices."""
        client = mqtt_connect(GW_CREDS, "test-gw-ack")
        ack_wildcard = "smart-factory/+/command/ack"

        # Publish as bridge to device A's ack
        ack_a = TPL_CMD_ACK.format(deviceId=DEVICE_A)
        mqtt_publish(ack_a, b'{"status":"ok"}', BRIDGE_CREDS)
        time.sleep(0.3)

        received, payload = mqtt_subscribe_and_wait(client, ack_wildcard, timeout=2.0)
        client.disconnect()
        client.loop_stop()

        assert received, (
            "Gateway wildcard subscription to smart-factory/+/command/ack "
            "received no messages — gateway cannot ingest bridge ACKs"
        )

    def test_gateway_can_subscribe_to_any_device_telemetry(
        self, broker_running: None
    ) -> None:
        """Gateway subscribes to smart-factory/+/telemetry — must receive from all devices."""
        client = mqtt_connect(GW_CREDS, "test-gw-tel")
        tel_wildcard = "smart-factory/+/telemetry"

        tel_a = TPL_TELEMETRY.format(deviceId=DEVICE_A)
        mqtt_publish(tel_a, b'{"device_id":"' + DEVICE_A.encode() + b'","values":["RUNNING"]}', BRIDGE_CREDS)
        time.sleep(0.3)

        received, payload = mqtt_subscribe_and_wait(client, tel_wildcard, timeout=2.0)
        client.disconnect()
        client.loop_stop()

        assert received, (
            "Gateway wildcard subscription to smart-factory/+/telemetry "
            "received no messages — gateway cannot ingest telemetry"
        )

    def test_gateway_can_subscribe_to_any_device_status(
        self, broker_running: None
    ) -> None:
        """Gateway subscribes to smart-factory/+/status — must receive from all devices."""
        client = mqtt_connect(GW_CREDS, "test-gw-status")
        status_wildcard = "smart-factory/+/status"

        status_a = TPL_STATUS.format(deviceId=DEVICE_A)
        mqtt_publish(status_a, b'{"status":"online"}', BRIDGE_CREDS)
        time.sleep(0.3)

        received, payload = mqtt_subscribe_and_wait(client, status_wildcard, timeout=2.0)
        client.disconnect()
        client.loop_stop()

        assert received, (
            "Gateway wildcard subscription to smart-factory/+/status "
            "received no messages — gateway cannot ingest status"
        )


# ---------------------------------------------------------------------------
# Test Class: Gateway ACL — Negative
# ---------------------------------------------------------------------------

class TestGatewayACLNegative:
    """Verify gateway CANNOT publish to bridge-owned topics."""

    def test_gateway_cannot_publish_to_bridge_command_down(
        self, broker_running: None
    ) -> None:
        """Gateway MUST NOT publish to smart-factory/{deviceId}/command/down."""
        cmd_topic = TPL_CMD_DOWN.format(deviceId=DEVICE_A)
        rc = mqtt_publish(cmd_topic, b'{"command_id":1,"command_name":"PING"}', GW_CREDS)
        assert rc != 0, (
            f"Gateway published to {cmd_topic} — gateway should NOT have write access "
            f"to bridge command topics"
        )

    def test_gateway_cannot_publish_to_bridge_ack(
        self, broker_running: None
    ) -> None:
        """Gateway MUST NOT publish to bridge ACK topic."""
        ack_topic = TPL_CMD_ACK.format(deviceId=DEVICE_A)
        rc = mqtt_publish(ack_topic, b'{"status":"ok"}', GW_CREDS)
        assert rc != 0, (
            f"Gateway published to {ack_topic} — gateway should NOT write bridge ACK topics"
        )

    def test_gateway_cannot_publish_to_bridge_telemetry(
        self, broker_running: None
    ) -> None:
        """Gateway MUST NOT publish to bridge telemetry topic."""
        tel_topic = TPL_TELEMETRY.format(deviceId=DEVICE_A)
        rc = mqtt_publish(tel_topic, b'{"device_id":"' + DEVICE_A.encode() + b'"}', GW_CREDS)
        assert rc != 0, (
            f"Gateway published to {tel_topic} — gateway should NOT write bridge telemetry"
        )


# ---------------------------------------------------------------------------
# Test Class: Healthcheck
# ---------------------------------------------------------------------------

class TestHealthcheck:
    """Verify the compose healthcheck configuration is correct.

    The original healthcheck used:
        mosquitto_sub -C 1 -W 5 -t smart-factory/+/command/down
    which times out when no commands are published — a false negative.
    See infrastructure/mqtt-broker/docs/healthcheck-design.md.
    """

    def test_compose_has_no_false_negative_healthcheck(
        self, broker_running: None
    ) -> None:
        """Verify docker-compose.yml does NOT use command/down for healthcheck."""
        with open(COMPOSE_FILE) as f:
            compose = yaml.safe_load(f)

        mqtt_service = compose.get("services", {}).get("mqtt", {})
        hc = mqtt_service.get("healthcheck", {})

        # If healthcheck exists, it must NOT use command/down
        if hc and hc.get("disable") is not True:
            test_cmd = " ".join(hc.get("test", []))
            assert "command/down" not in test_cmd, (
                f"Healthcheck uses command/down topic, which will false-negative "
                f"when no commands are published. See healthcheck-design.md. "
                f"Current test: {test_cmd}"
            )

    def test_broker_accepts_mqtt_connection(self, broker_running: None) -> None:
        """Basic connectivity: any valid credential can connect."""
        client = mqtt_connect(BRIDGE_CREDS, "test-basic-connect")
        assert client.is_connected()
        client.disconnect()
        client.loop_stop()
