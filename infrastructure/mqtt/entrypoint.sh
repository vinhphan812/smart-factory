#!/usr/bin/env sh
# Mosquitto entrypoint: generates mosquitto.conf and password file at container start.
#
# Credentials are injected via docker-compose environment, never hardcoded.
#
# mosquitto.conf generation:
#   - TLS_MODE=yes  -> includes listener 8883 with cert directives
#   - TLS_MODE!="yes" (or unset) -> plaintext only on 1883
#     No listener 8883 block -> mosquitto refuses to start on 8883, no silent fallback.
#
# Password file:
#   Written to /mosquitto/passwords/passwd (mqtt-passwords named volume).
#   The ./mqtt/ config tree is mounted :ro; passwords go to the dedicated volume.
#
# Entrypoint approach (not include_dir) because mosquitto 2.x conf.d includes
# cannot be guarded by environment variables; both files in a conf.d dir are
# always loaded. Conditional config assembly here is the standard pattern.

set -e

# Writable directories (named volumes mounted by compose)
PASSWD_DIR="/mosquitto/passwords"
CONF_GENERATED_DIR="/mosquitto/config-generated"
mkdir -p "$PASSWD_DIR" "$CONF_GENERATED_DIR"
chown mosquitto:mosquitto "$PASSWD_DIR" "$CONF_GENERATED_DIR" || true
chmod 700 "$PASSWD_DIR" || true

# ---------------------------------------------------------------------------
# 1. Generate mosquitto.conf from template
# ---------------------------------------------------------------------------

echo "Generating mosquitto.conf (TLS_MODE=${TLS_MODE:-not set})..."

cat > "$CONF_GENERATED_DIR/mosquitto.conf" << 'MOSQUITTO_CONF_EOF'
# mosquitto.conf -- generated at container start by entrypoint.sh
# TLS_MODE=yes  -> includes listener 8883 + certs
# TLS_MODE!="yes" -> plaintext only on 1883
allow_anonymous false
password_file /mosquitto/passwords/passwd
acl_file /mosquitto/config/acl
listener 1883
persistence true
persistence_location /mosquitto/data/
log_dest stdout
MOSQUITTO_CONF_EOF

# ---------------------------------------------------------------------------
# 2. Generate password file
# ---------------------------------------------------------------------------

echo "Generating Mosquitto password file from environment variables..."

touch "$PASSWD_DIR/passwd"
chmod 600 "$PASSWD_DIR/passwd"

# Generate passwords for each configured user
_register_user() {
    _user="$1"
    _pass="$2"
    if [ -n "$_user" ] && [ -n "$_pass" ]; then
        mosquitto_passwd -b "$PASSWD_DIR/passwd" "$_user" "$_pass"
        echo "Registered user: $_user"
    fi
}

_register_user "${MQTT_BRIDGE_USERNAME:-}" "${MQTT_BRIDGE_PASSWORD:-}"
_register_user "${MQTT_GATEWAY_USERNAME:-}" "${MQTT_GATEWAY_PASSWORD:-}"
_register_user "${MQTT_OPERATOR_USERNAME:-}" "${MQTT_OPERATOR_PASSWORD:-}"

# ---------------------------------------------------------------------------
# 3. TLS block -- appended to mosquitto.conf only when TLS_MODE=yes
# ---------------------------------------------------------------------------

if [ "$TLS_MODE" = "yes" ]; then
    echo "TLS_MODE=yes detected -- enabling TLS listener on port 8883..."

    # Verify cert files exist before starting broker
    for _cert in ca.crt server.crt server.key; do
        if [ ! -f "/mosquitto/certs/$_cert" ]; then
            echo "FATAL: TLS_MODE=yes but /mosquitto/certs/$_cert is missing." >&2
            echo "FATAL: Mount certificates via -v \"\$(pwd)/certs:/mosquitto/certs:ro\" or" >&2
            echo "FATAL: generate them: cd infrastructure && ./scripts/generate-dev-certs.sh" >&2
            exit 1
        fi
    done

    # Append TLS listener block to the generated conf
    cat >> "$CONF_GENERATED_DIR/mosquitto.conf" << 'TLS_BLOCK_EOF'

# TLS listener -- ACTIVE (TLS_MODE=yes)
listener 8883
cafile /mosquitto/certs/ca.crt
certfile /mosquitto/certs/server.crt
keyfile /mosquitto/certs/server.key
require_certificate false
use_identity_as_username false
TLS_BLOCK_EOF
else
    echo "TLS_MODE not set -- broker serves plaintext on port 1883 only."
    echo "  To enable TLS: docker compose --profile tls up -d mqtt"
fi

echo "Starting Mosquitto broker with $CONF_GENERATED_DIR/mosquitto.conf..."
exec mosquitto -c "$CONF_GENERATED_DIR/mosquitto.conf"
