#!/bin/sh
# Create credentials file for MQTT broker.
# Run from infrastructure/mqtt-broker/config/tls/
#
# Usage: ./create-creds.sh [password_file]
#
# Creates mosquitto passwd file with:
#   - admin credential
#   - bridge credential (ukit-00000000)
#   - gateway credential
#
# The credentials are written to a file for bind-mount into the container.

set -e

OUT_DIR="$(dirname "$0")"
PASSWD_FILE="${1:-${OUT_DIR}/passwd}"

# Default passwords — replace with strong random values for production
ADMIN_USER="${MQTT_ADMIN_USERNAME:-admin}"
ADMIN_PASS="${MQTT_ADMIN_PASSWORD:-changeme}"
BRIDGE_USER="${MQTT_BRIDGE_USERNAME:-ukit-00000000}"
BRIDGE_PASS="${MQTT_BRIDGE_PASSWORD:-changeme}"
GW_USER="${MQTT_GW_USERNAME:-gateway}"
GW_PASS="${MQTT_GW_PASSWORD:-changeme}"

echo "=== Creating MQTT Broker Credentials ==="
echo "Output file: ${PASSWD_FILE}"

# ---------------------------------------------------------------------------
# Build credentials file
# ---------------------------------------------------------------------------
: > "${PASSWD_FILE}"

echo "[GEN]  Adding admin credential: ${ADMIN_USER}"
mosquitto_passwd -b "${PASSWD_FILE}" "${ADMIN_USER}" "${ADMIN_PASS}"

echo "[GEN]  Adding bridge credential: ${BRIDGE_USER}"
mosquitto_passwd -b "${PASSWD_FILE}" "${BRIDGE_USER}" "${BRIDGE_PASS}"

echo "[GEN]  Adding gateway credential: ${GW_USER}"
mosquitto_passwd -b "${PASSWD_FILE}" "${GW_USER}" "${GW_PASS}"

echo "[OK]   Credentials written to: ${PASSWD_FILE}"
echo ""
echo "Next step: add the credentials file to your Docker Compose volume or bind-mount,"
echo "then start the broker: docker compose --profile tls up -d mqtt-tls"
