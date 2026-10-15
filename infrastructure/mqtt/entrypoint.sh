#!/usr/bin/env sh
# Mosquitto entrypoint: generates password file from environment variables.
# Credentials are injected via docker-compose environment, never hardcoded.

set -e

echo "Generating Mosquitto password file from environment variables..."

touch /mosquitto/config/passwords
chown mosquitto:mosquitto /mosquitto/config/passwords || true
chmod 600 /mosquitto/config/passwords || true

# Generate passwords for each configured user
if [ -n "$MQTT_BRIDGE_USERNAME" ] && [ -n "$MQTT_BRIDGE_PASSWORD" ]; then
    mosquitto_passwd -b /mosquitto/config/passwords "$MQTT_BRIDGE_USERNAME" "$MQTT_BRIDGE_PASSWORD"
    echo "Registered bridge user: $MQTT_BRIDGE_USERNAME"
fi

if [ -n "$MQTT_GATEWAY_USERNAME" ] && [ -n "$MQTT_GATEWAY_PASSWORD" ]; then
    mosquitto_passwd -b /mosquitto/config/passwords "$MQTT_GATEWAY_USERNAME" "$MQTT_GATEWAY_PASSWORD"
    echo "Registered gateway user: $MQTT_GATEWAY_USERNAME"
fi

if [ -n "$MQTT_OPERATOR_USERNAME" ] && [ -n "$MQTT_OPERATOR_PASSWORD" ]; then
    mosquitto_passwd -b /mosquitto/config/passwords "$MQTT_OPERATOR_USERNAME" "$MQTT_OPERATOR_PASSWORD"
    echo "Registered operator user: $MQTT_OPERATOR_USERNAME"
fi

echo "Starting Mosquitto broker..."
exec mosquitto -c /mosquitto/config/mosquitto.conf
