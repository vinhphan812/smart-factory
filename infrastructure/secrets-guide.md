# Smart Factory Secrets & MQTT Security Guide

This guide covers secure credential injection, MQTT broker hardening, ACL enforcement, TLS certificate generation for development, and threat modeling for Issue #41.

## 1. Secret Management Principles
- **No hardcoded secrets**: All credentials, API keys, and private keys are strictly excluded from version control via `.gitignore`.
- **Environment injection**: Services and containers receive secrets via environment variables (e.g. `.env` files or CI secret stores).
- **Fail-closed authentication**: Devices and gateways refuse to connect if credentials are empty or missing.

## 2. MQTT Broker Authentication & ACLs
The Mosquitto broker configuration (`infrastructure/mqtt/mosquitto.conf`) enforces:
- **Anonymous connections disabled** (`allow_anonymous false`).
- **Password authentication** (`password_file /mosquitto/config/passwords`).
- **Topic-level ACLs** (`acl_file /mosquitto/config/acl`) enforcing per ADR-0010 policy:
  - Bridge devices: publish `smart-factory/{deviceId}/telemetry`, `smart-factory/{deviceId}/status`, `smart-factory/{deviceId}/command/ack`; subscribe `smart-factory/{deviceId}/command/down`
  - Gateways: subscribe to `smart-factory/+/telemetry`, `smart-factory/+/status`, `smart-factory/+/command/ack` (read-only)
  - Operators: read-only access to all bridge topics

## 3. TLS Configuration (Port 8883)
- Production and secure test environments support TLS on port 8883.
- CA certificates are pinned or verified via `WiFiClientSecure::setCACert()` on ESP32 devices.
- Self-signed certificates are restricted to local development and test containers (`infrastructure/certs/`).

## 4. Development Setup
Create a `.env` file (NOT committed to version control):
```bash
# Bridge credentials (device-bound)
MQTT_BRIDGE_USERNAME=bridge
MQTT_BRIDGE_PASSWORD=<secure-random-password>

# Gateway credentials
MQTT_GATEWAY_USERNAME=gateway
MQTT_GATEWAY_PASSWORD=<secure-random-password>

# Operator/monitoring credentials
MQTT_OPERATOR_USERNAME=operator
MQTT_OPERATOR_PASSWORD=<secure-random-password>
```

Run with Docker Compose:
```bash
cd infrastructure
docker compose up -d mqtt
```

## 5. Verification and Testing
- Run integration tests against a local Mosquitto test container.
- Verify grep audit passes with no hardcoded credentials in the source tree.
- Test cases (see `esp32-ukit-bridge/tests/integration/test_mqtt_security_broker.py`):
  - TC9: Valid credentials connect successfully
  - TC10: Invalid credentials rejected
  - TC11: Anonymous connection rejected
  - TC12: ACL violation denied
  - TC13: TLS configuration ready

## 6. L3/HIL Device TLS Verification (Out of Scope for Dev Broker)
This dev/test broker configuration provides authentication, ACLs, and TLS listener setup for development and integration testing. It does NOT include:
- Hardware-in-the-loop (HIL) ESP32 TLS verification
- Production PKI certificate chain validation
- Physical device certificate provisioning

These require separate L3 verification and are tracked as follow-up work in Issue #41.
