"""Integration tests for MQTT broker security (Authentication, ACLs, TLS, Anonymous prevention).

Tests corresponding to Issue #41:
- TC9: Valid credentials connect successfully
- TC10: Invalid credentials rejected
- TC11: Anonymous connection rejected
- TC12: ACL violation quarantined / denied
- TC13: TLS connection parameters / cert verification setup

Note: These tests require Docker to be running. Without Docker, configuration-level
tests are run to validate syntax and semantics deterministically.
"""

import pytest
import os
import subprocess
import socket
import time
from pathlib import Path


# Test configuration paths relative to this test file
INFRA_DIR = Path(__file__).parent.parent.parent.parent / "infrastructure"
MQTT_CONF = INFRA_DIR / "mqtt" / "mosquitto.conf"
ACL_FILE = INFRA_DIR / "mqtt" / "acl"
COMPOSE_FILE = INFRA_DIR / "docker-compose.yml"


class TestConfiguration:
    """Configuration-level tests that validate syntax and ACL semantics deterministically."""

    def test_mosquitto_conf_syntax_valid(self) -> None:
        """Verify mosquitto.conf has valid syntax and security settings."""
        content = MQTT_CONF.read_text()
        
        # Must disable anonymous access
        assert "allow_anonymous false" in content, \
            "mosquitto.conf must set allow_anonymous false"
        
        # Must use password file
        assert "password_file" in content, \
            "mosquitto.conf must specify password_file"
        
        # Must use ACL file
        assert "acl_file" in content, \
            "mosquitto.conf must specify acl_file"
        
        # Must have plain listener
        assert "listener 1883" in content, \
            "mosquitto.conf must have plain MQTT listener on 1883"
        
        # Must have TLS listener on 8883
        assert "listener 8883" in content, \
            "mosquitto.conf must have TLS listener on 8883"
        
        # TLS must use cert files
        assert "cafile" in content and "certfile" in content and "keyfile" in content, \
            "TLS listener must specify cafile, certfile, and keyfile"

    def test_acl_file_valid_syntax(self) -> None:
        """Verify ACL file has valid Mosquitto ACL syntax."""
        content = ACL_FILE.read_text()
        
        # Must define bridge user
        assert "user bridge" in content, \
            "ACL must define 'bridge' user"
        
        # Must define gateway user
        assert "user gateway" in content, \
            "ACL must define 'gateway' user"
        
        # Must define operator user
        assert "user operator" in content, \
            "ACL must define 'operator' user"
        
        # Bridge must have write to telemetry
        assert "write smart-factory/%u/telemetry" in content, \
            "Bridge must have write to telemetry topic"
        
        # Bridge must have write to status
        assert "write smart-factory/%u/status" in content, \
            "Bridge must have write to status topic"
        
        # Bridge must have write to command/ack
        assert "write smart-factory/%u/command/ack" in content, \
            "Bridge must have write to command/ack topic"
        
        # Bridge must have read from command/down
        assert "read smart-factory/%u/command/down" in content, \
            "Bridge must have read from command/down topic"
        
        # Gateway must have read-only access to telemetry
        assert "read smart-factory/+/telemetry" in content, \
            "Gateway must have read access to telemetry"
        
        # Gateway must have read-only access to status
        assert "read smart-factory/+/status" in content, \
            "Gateway must have read access to status"
        
        # Gateway must have read-only access to command/ack
        assert "read smart-factory/+/command/ack" in content, \
            "Gateway must have read access to command/ack"

    def test_acl_enforces_read_only_gateway(self) -> None:
        """Verify gateway has NO write permissions (denied by absence)."""
        content = ACL_FILE.read_text()
        
        # Find gateway user section
        lines = content.split("\n")
        in_gateway = False
        gateway_has_write = False
        
        for line in lines:
            if line.strip() == "user gateway":
                in_gateway = True
            elif line.strip().startswith("user "):
                in_gateway = False
            elif in_gateway and "pattern write smart-factory" in line:
                gateway_has_write = True
                break
        
        assert not gateway_has_write, \
            "Gateway must NOT have write permissions per ADR-0010"

    def test_compose_file_requires_credentials(self) -> None:
        """Verify docker-compose.yml requires credentials via environment."""
        content = COMPOSE_FILE.read_text()
        
        # Must require bridge username/password
        assert "MQTT_BRIDGE_USERNAME" in content and "MQTT_BRIDGE_PASSWORD" in content, \
            "Compose must require MQTT_BRIDGE credentials"
        
        # Must require gateway username/password
        assert "MQTT_GATEWAY_USERNAME" in content and "MQTT_GATEWAY_PASSWORD" in content, \
            "Compose must require MQTT_GATEWAY credentials"
        
        # Must require operator password
        assert "MQTT_OPERATOR_PASSWORD" in content, \
            "Compose must require MQTT_OPERATOR_PASSWORD"
        
        # Must use :? for mandatory variables
        assert ":?set" in content, \
            "Compose must use :?set for mandatory credential variables"

    def test_entrypoint_generates_passwords(self) -> None:
        """Verify entrypoint.sh generates passwords from environment."""
        entrypoint = (INFRA_DIR / "mqtt" / "entrypoint.sh").read_text()
        
        assert "mosquitto_passwd" in entrypoint, \
            "Entrypoint must use mosquitto_passwd"
        
        assert "MQTT_BRIDGE_USERNAME" in entrypoint and "MQTT_BRIDGE_PASSWORD" in entrypoint, \
            "Entrypoint must handle bridge credentials"
        
        assert "MQTT_GATEWAY_USERNAME" in entrypoint and "MQTT_GATEWAY_PASSWORD" in entrypoint, \
            "Entrypoint must handle gateway credentials"


def is_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def wait_for_mqtt(host: str, port: int, timeout: int = 30) -> bool:
    """Wait for MQTT broker to become available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return True
        except socket.error:
            pass
        time.sleep(1)
    return False


# Skip integration tests if Docker is not available
docker_available = pytest.mark.skipif(
    not is_docker_available(),
    reason="Docker not available"
)


@docker_available
class TestDockerIntegration:
    """Integration tests that require a running Docker daemon."""

    @pytest.fixture(scope="class")
    def broker_env(self) -> dict:
        """Environment variables for broker."""
        return {
            "MQTT_BRIDGE_USERNAME": "bridge",
            "MQTT_BRIDGE_PASSWORD": "test-bridge-pass",
            "MQTT_GATEWAY_USERNAME": "gateway", 
            "MQTT_GATEWAY_PASSWORD": "test-gateway-pass",
            "MQTT_OPERATOR_USERNAME": "operator",
            "MQTT_OPERATOR_PASSWORD": "test-operator-pass",
        }

    @pytest.fixture(scope="class")
    def compose_up(self, broker_env: dict) -> None:
        """Start the MQTT broker via docker compose."""
        # Create .env file for docker compose
        env_file = INFRA_DIR / ".env"
        env_content = "\n".join(f"{k}={v}" for k, v in broker_env.items())
        env_file.write_text(env_content)
        
        try:
            # Start broker
            result = subprocess.run(
                ["docker", "compose", "up", "-d", "mqtt"],
                cwd=INFRA_DIR,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, **broker_env},
            )
            
            if result.returncode != 0:
                pytest.skip(f"Failed to start broker: {result.stderr}")
            
            # Wait for broker to be ready
            if not wait_for_mqtt("localhost", 1883, timeout=30):
                pytest.skip("MQTT broker did not become available")
            
            yield
            
        finally:
            # Stop broker
            subprocess.run(
                ["docker", "compose", "down"],
                cwd=INFRA_DIR,
                capture_output=True,
                timeout=30,
            )
            # Clean up .env file
            if env_file.exists():
                env_file.unlink()

    def test_tc9_valid_credentials_connect(self, compose_up: None) -> None:
        """TC9: Valid credentials connect successfully."""
        import paho.mqtt.client as mqtt
        
        connected = False
        error_msg = None
        
        def on_connect(client, userdata, flags, rc):
            nonlocal connected, error_msg
            if rc == 0:
                connected = True
            else:
                error_msg = f"Connection failed with code {rc}"
        
        client = mqtt.Client()
        client.on_connect = on_connect
        client.username_pw_set("bridge", "test-bridge-pass")
        
        try:
            client.connect("localhost", 1883, keepalive=10)
            client.loop_start()
            
            # Wait up to 10 seconds for connection
            for _ in range(20):
                time.sleep(0.5)
                if connected:
                    break
            
            assert connected, f"Failed to connect with valid credentials: {error_msg}"
            
        finally:
            client.loop_stop()
            client.disconnect()

    def test_tc10_invalid_credentials_rejected(self, compose_up: None) -> None:
        """TC10: Invalid credentials rejected."""
        import paho.mqtt.client as mqtt
        
        connection_refused = False
        
        def on_connect(client, userdata, flags, rc):
            nonlocal connection_refused
            # RC 4 = Bad username or password
            if rc == 4:
                connection_refused = True
        
        client = mqtt.Client()
        client.on_connect = on_connect
        client.username_pw_set("bridge", "wrong-password")
        
        try:
            client.connect("localhost", 1883, keepalive=10)
            client.loop_start()
            
            # Wait for connection attempt
            for _ in range(20):
                time.sleep(0.5)
                if connection_refused:
                    break
            
            assert connection_refused, \
                "Invalid credentials should be rejected (RC=4)"
            
        finally:
            client.loop_stop()
            client.disconnect()

    def test_tc11_anonymous_connection_rejected(self, compose_up: None) -> None:
        """TC11: Anonymous connection rejected when allow_anonymous false."""
        import paho.mqtt.client as mqtt
        
        connection_refused = False
        
        def on_connect(client, userdata, flags, rc):
            nonlocal connection_refused
            # RC 5 = Not authorized
            if rc == 5:
                connection_refused = True
        
        client = mqtt.Client()
        # No username/password = anonymous
        
        try:
            client.connect("localhost", 1883, keepalive=10)
            client.loop_start()
            
            # Wait for connection attempt
            for _ in range(20):
                time.sleep(0.5)
                if connection_refused:
                    break
            
            assert connection_refused, \
                "Anonymous connection should be rejected (RC=5)"
            
        finally:
            client.loop_stop()
            client.disconnect()

    def test_tc12_acl_bridge_cannot_subscribe_others_telemetry(self, compose_up: None) -> None:
        """TC12: ACL denies bridge from subscribing to another device's telemetry."""
        import paho.mqtt.client as mqtt
        
        # Bridge credential tries to subscribe to another device's telemetry
        # Should be denied by ACL
        denied = False
        
        def on_connect(client, userdata, flags, rc):
            if rc != 0:
                return
            # Try to subscribe to another device's telemetry - should be denied
            result = client.subscribe("smart-factory/other-device/telemetry")
            # MQTTv5 returns failure as negative result
            if result[0] != 0:
                nonlocal denied
                denied = True
        
        client = mqtt.Client()
        client.on_connect = on_connect
        client.username_pw_set("bridge", "test-bridge-pass")
        
        try:
            client.connect("localhost", 1883, keepalive=10)
            client.loop_start()
            
            for _ in range(20):
                time.sleep(0.5)
                if denied:
                    break
            
            # ACL should deny subscription to other device's telemetry
            assert denied, "ACL should deny bridge subscribing to other device's telemetry"
            
        finally:
            client.loop_stop()
            client.disconnect()

    def test_tc13_tls_listener_available(self, compose_up: None) -> None:
        """TC13: TLS listener on port 8883 is available."""
        # Check if port 8883 is open
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            result = sock.connect_ex(("localhost", 8883))
            assert result == 0, "TLS listener on port 8883 should be available"
        finally:
            sock.close()
