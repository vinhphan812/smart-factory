# TLS Certificate Generation for MQTT Broker

**Status:** Proposed — Issue #41

## Prerequisites

- OpenSSL installed
- `eclipse-mosquitto:2` container image available

## Quick Start

```bash
cd infrastructure/mqtt-broker/config/tls
./generate-certs.sh
./create-creds.sh
```

Then copy the resulting `*.crt` and `*.key` files to the appropriate location, or use the `mqtt-tls` Docker Compose profile.

## Certificate Structure

```
CA (self-signed)
  └── Server certificate (signed by CA)
  └── Client certificates (signed by CA) — for future client-cert auth
```

## Files Generated

| File | Purpose |
|------|---------|
| `ca.crt` | CA certificate — embed in ESP32 SPIFFS for TLS verification |
| `ca.key` | CA private key — keep SECURE, never commit |
| `server.crt` | Mosquitto server certificate |
| `server.key` | Mosquitto server private key — never commit |
| `bridge.crt` | Future: client cert for ESP32 bridge |
| `bridge.key` | Future: client cert key for ESP32 bridge |
| `dhparam.pem` | Diffie-Hellman parameters (optional, for forward secrecy) |

## mosquitto.conf TLS Settings

```properties
listener 8883 127.0.0.1
tls-version specific tlsv1.2
cafile /mosquitto/certs/ca.crt
certfile /mosquitto/certs/server.crt
keyfile /mosquitto/certs/server.key
require_certificate false
```

`require_certificate false` means TLS is used but client certificates are optional. Set to `true` to require client certificates (Phase 3 of the TLS roadmap — not yet implemented).

## ESP32 Bridge: Loading the CA Certificate

```cpp
// Load CA from SPIFFS
File caFile = SPIFFS.open("/certs/ca.crt", "r");
if (caFile) {
    size_t len = caFile.size();
    char* buf = new char[len + 1];
    caFile.readBytes(buf, len);
    buf[len] = '\0';
    wifiClient.setCACert(buf);  // mbedTLS copies the cert
    delete[] buf;
}

// Connect with TLS
PubSubClient mqttClient(wifiClient);
mqttClient.setServer(BRIDGE_MQTT_HOST, 8883);
```

See `esp32-ukit-bridge/docs/mqtt-security.md` for full TLS wiring instructions.

## Security Notes

- Keep `ca.key`, `server.key`, and `bridge.key` out of version control.
- Use a strong passphrase for the CA key in production.
- Rotate certificates before expiry (default: 365 days in the generation script).
- For production, use a proper CA (Let's Encrypt, internal PKI) rather than a self-signed CA.
