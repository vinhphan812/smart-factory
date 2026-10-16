#!/bin/sh
# Generate self-signed CA and server certificates for Mosquitto MQTT broker TLS.
# Run from infrastructure/mqtt-broker/config/tls/
#
# Usage: ./generate-certs.sh
#
# Prerequisites: openssl
#
# WARNING: This is for LOCAL DEVELOPMENT ONLY.
# For production, use certificates from a trusted CA or internal PKI.

set -e

OUT_DIR="$(dirname "$0")"
CA_KEY="${OUT_DIR}/ca.key"
CA_CERT="${OUT_DIR}/ca.crt"
SERVER_KEY="${OUT_DIR}/server.key"
SERVER_CSR="${OUT_DIR}/server.csr"
SERVER_CERT="${OUT_DIR}/server.crt"
DHFILE="${OUT_DIR}/dhparam.pem"
VALIDITY_DAYS=365

echo "=== MQTT Broker TLS Certificate Generation ==="
echo "Output directory: ${OUT_DIR}"

# ---------------------------------------------------------------------------
# 1. CA key and certificate (self-signed)
# ---------------------------------------------------------------------------
if [ -f "${CA_KEY}" ]; then
    echo "[SKIP] CA key already exists: ${CA_KEY}"
else
    echo "[GEN]  Generating CA private key..."
    openssl genrsa -out "${CA_KEY}" 4096 2>/dev/null
    chmod 600 "${CA_KEY}"
    echo "[GEN]  Generating self-signed CA certificate..."
    openssl req -new -x509 -key "${CA_KEY}" -out "${CA_CERT}" \
        -days "${VALIDITY_DAYS}" -subj "/CN=SmartFactory-CA/O=AIBOT/C=VN" 2>/dev/null
    echo "[OK]   CA: ${CA_KEY} + ${CA_CERT}"
fi

# ---------------------------------------------------------------------------
# 2. Server key and certificate (signed by CA)
# ---------------------------------------------------------------------------
if [ -f "${SERVER_KEY}" ]; then
    echo "[SKIP] Server key already exists: ${SERVER_KEY}"
else
    echo "[GEN]  Generating server private key..."
    openssl genrsa -out "${SERVER_KEY}" 2048 2>/dev/null
    chmod 600 "${SERVER_KEY}"
    echo "[GEN]  Generating server CSR..."
    openssl req -new -key "${SERVER_KEY}" -out "${SERVER_CSR}" \
        -subj "/CN=localhost/O=SmartFactory/C=VN" 2>/dev/null
    echo "[GEN]  Signing server certificate with CA..."
    # Extended key usage: server authentication + client authentication
    openssl x509 -req -in "${SERVER_CSR}" -CA "${CA_CERT}" -CAkey "${CA_KEY}" \
        -out "${SERVER_CERT}" -days "${VALIDITY_DAYS}" -CAcreateserial \
        -extfile <(printf "basicConstraints=CA:FALSE\nkeyUsage=keyEncipherment,digitalSignature\nextKeyUsage=serverAuth,clientAuth") \
        2>/dev/null
    rm -f "${SERVER_CSR}"
    echo "[OK]   Server: ${SERVER_KEY} + ${SERVER_CERT}"
fi

# ---------------------------------------------------------------------------
# 3. Diffie-Hellman parameters (optional, for forward secrecy)
# ---------------------------------------------------------------------------
if [ -f "${DHFILE}" ]; then
    echo "[SKIP] DH params already exist: ${DHFILE}"
else
    echo "[GEN]  Generating DH parameters (this may take a while)..."
    openssl dhparam -out "${DHFILE}" 2048 2>/dev/null
    chmod 644 "${DHFILE}"
    echo "[OK]   DH: ${DHFILE}"
fi

echo ""
echo "=== Summary ==="
ls -la "${CA_KEY}" "${CA_CERT}" "${SERVER_KEY}" "${SERVER_CERT}" "${DHFILE}" 2>/dev/null
echo ""
echo "Next step: run ./create-creds.sh to create client credentials."
echo "Then copy the certs to the Docker volume or bind-mount location."
