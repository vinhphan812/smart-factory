# MQTT Security

This document describes the current security posture of the ESP32 MQTT bridge and outlines the path to production-grade security. Read this alongside [mqtt-contract.md](mqtt-contract.md).

---

## 1. MQTT Authentication

### Broker-Side Authentication

| Method | Current Status | Notes |
|--------|---------------|-------|
| Username / password | **Implemented** | Passed to `PubSubClient::connect()`. See `connectOnce()` in `mqtt_bridge.cpp`. |
| Client certificate (TLS client auth) | **Not implemented** | Planned for future. Requires broker support (e.g., Mosquitto with `certfile`/`keyfile`). |
| Anonymous | Disabled by default | Connection is refused unless `BRIDGE_MQTT_USERNAME` is non-empty. |

The broker must enforce credentials. The ESP32 bridge accepts any non-empty username; the broker is responsible for verifying the corresponding password.

### ESP32 Client Credentials

All MQTT credentials are defined in `esp32/include/secrets.h` (see [Secret Management](#3-secret-management)). They are passed as plain pointers into `PubSubClient`:

```cpp
// mqtt_bridge.cpp, MqttBridge constructor
host_(host), port_(port), username_(username), password_(password), deviceId_(deviceId)
```

The credentials are stored as `const char*` members and are used verbatim on every connection attempt. No token refresh, no hashing, no challenge-response.

### Client ID

The `deviceId` (passed as `BRIDGE_MQTT_CLIENT_ID` in `secrets.h`) is used as the MQTT client identifier:

```cpp
// mqtt_bridge.cpp, connectOnce()
client_.connect(deviceId_, username_, password_, ...);
```

- Each physical device must have a unique `deviceId`.
- The broker uses this ID for session persistence and last-will routing.
- The `deviceId` also appears in the topic hierarchy (`smart-factory/{deviceId}/...`).

### Access Control Lists (ACLs)

The broker should enforce ACLs to limit what each client can publish and subscribe. Recommended ACL per role:

| Role | Publish | Subscribe |
|------|---------|-----------|
| ESP32 bridge | `smart-factory/{deviceId}/command/ack`<br>`smart-factory/{deviceId}/status`<br>`smart-factory/{deviceId}/telemetry` | `smart-factory/{deviceId}/command/down` |
| Backend / cloud | `smart-factory/{deviceId}/command/down` | `smart-factory/{deviceId}/command/ack`<br>`smart-factory/{deviceId}/telemetry`<br>`smart-factory/{deviceId}/status` |
| Operator dashboard | (read-only) | same as backend subscriber |

MQTT wildcard subscriptions (`+` / `#`) should be restricted to trusted admin clients only.

---

## 2. TLS / SSL

### Current State: Plain MQTT

**The ESP32 bridge currently uses plain MQTT on port 1883. This is NOT safe for production.**

Plain MQTT transmits username, password, client ID, and all payload data in the clear. Any party on the same network segment can read or intercept:

- Broker credentials
- Command payloads (AML encoded)
- Telemetry data
- Device identifiers

This is acceptable in a fully isolated, air-gapped development lab. It is not acceptable over any network that carries untrusted traffic.

### Future: MQTT over TLS (port 8883)

To enable TLS:

1. Configure the broker for TLS (e.g., Mosquitto: add `listener 8883` + `cafile` + `require_certificate true`).
2. Add the broker CA certificate to the ESP32 SPIFFS partition.
3. Configure `PubSubClient` to use TLS:

```cpp
// Inside WiFiClient, BearSSL is used on ESP32 variants.
// Pass the WiFiClientSecure instance to PubSubClient:
WiFiClientSecure wifiClient;
wifiClient.setCACert(spiffs_ca_cert);  // load from SPIFFS
PubSubClient mqttClient(wifiClient);
mqttClient.setServer(BRIDGE_MQTT_HOST, 8883);  // TLS port
```

4. Set `BRIDGE_MQTT_PORT` to `8883` in `secrets.h`.

### BearSSL vs mbedTLS on ESP32

The ESP32 and ESP32-S3 use **BearSSL** (via `WiFiClientSecure`) rather than mbedTLS. Key implications:

- **No dynamic certificate loading** at runtime by default. Certificates are embedded at compile time via `setCACert()`.
- **To load from SPIFFS**, read the PEM file into a buffer and pass it to `wifiClient.setCACert()`.
- **Certificate pinning**: `wifiClient.setInsecure()` must NOT be used in production. Instead, pin the SHA-256 fingerprint of the broker certificate:

```cpp
wifiClient.setFingerprint(fingerprint_sha256);
```

- **Flash size**: RSA-2048 / EC-P256 certificates are small (< 2 KB). Ed25519 support depends on BearSSL version.
- **Session resumption**: Not supported by BearSSL on ESP32; each connection performs a full handshake (~12 KB additional RAM).

### CA Certificate Storage in SPIFFS

1. Create a SPIFFS partition that includes `certs/` (minimum 4 KB).
2. Upload `ca.crt` alongside the firmware: `pio run --target uploadfs` or `esptool.py write_spiffs`.
3. Load at boot:

```cpp
#include <SPIFFS.h>
File caFile = SPIFFS.open("/certs/ca.crt", "r");
if (caFile) {
    size_t len = caFile.size();
    char* buf = new char[len + 1];
    caFile.readBytes(buf, len);
    buf[len] = '\0';
    wifiClient.setCACert(buf);  // BearSSL copies the cert
    delete[] buf;
}
```

Alternatively, embed the CA at compile time if the same broker is used for all deployments.

---

## 3. Secret Management

### secrets.h Structure

Copy `esp32/include/secrets.example.h` to `esp32/include/secrets.h` and fill in the values. All fields are documented inline.

| Field | Example | Notes |
|-------|---------|-------|
| `BRIDGE_WIFI_SSID` | `"FactoryFloor_2.4GHz"` | 2.4 GHz only; ESP32 does not support 5 GHz. |
| `BRIDGE_WIFI_PASSWORD` | `"***"` | Minimum WPA2-Personal. See Section 4. |
| `BRIDGE_WIFI_BSSID` | `"DC:4A:3E:12:34:56"` | Optional. Pin to a specific AP to avoid roaming issues. |
| `BRIDGE_MQTT_HOST` | `"mqtt.factory.local"` or IP address | IP address avoids DNS dependency on device. |
| `BRIDGE_MQTT_PORT` | `1883` (plain) or `8883` (TLS) | Change to 8883 when TLS is enabled. |
| `BRIDGE_MQTT_USERNAME` | `"bridge-device-001"` | Must be non-empty to enable authentication. |
| `BRIDGE_MQTT_PASSWORD` | `"***"` | Strong, unique per device recommended. |
| `BRIDGE_MQTT_CLIENT_ID` | `"sf-bridge-001"` | Must be unique per device. |
| `BRIDGE_MQTT_TLS_FINGERPRINT` | SHA-256 hex string | Required for TLS with pinning. Empty when TLS is disabled. |
| `BRIDGE_MQTT_CA_CERT_PATH` | `"/spiffs/certs/ca.crt"` | Path in SPIFFS. Empty when TLS is disabled. |

### Never Commit secrets.h

The repository's `.gitignore` excludes `esp32/include/secrets.h`:

```
# Credentials and certificates
esp32/include/secrets.h
*.pem
*.key
```

`secrets.example.h` is versioned and contains empty defaults. Each deployment must provision its own `secrets.h`.

### Current Provisioning Method

Manual flash only:

```bash
# Using PlatformIO
pio run --target upload --project-dir esp32-ukit-bridge/esp32

# Or with esptool (after building)
esptool.py --port COM3 write_flash 0x1000 firmware.bin
# Then separately write secrets.h - but secrets.h is compiled in.
```

**Limitation**: In the current build system, secrets are compiled into the firmware binary. To rotate credentials, the device must be reflashed. Future work: store credentials in an external EEPROM or use ESP32 secure boot + flash encryption to protect the built-in partition.

### Future: Secrets Rotation and Vault Integration

Long-term improvements:

| Approach | Description |
|----------|-------------|
| Vault-backed provisioning | On first boot, device fetches credentials from HashiCorp Vault / AWS Secrets Manager over TLS. Requires device attestation (secure boot + ECDSA challenge). |
| Periodic rotation | Broker credentials rotated via OTA push. Requires storing a refresh token in secure storage (ESP32 `nvs` with flash encryption, or external secure element). |
| Hardware security module | ESP32-S3 with `esp_secure_cert_t` peripheral or ATECC608A TrustMANAGER for credential provisioning and rotation. |

---

## 4. Wi-Fi Security

### Minimum Requirements

| Setting | Minimum | Recommended |
|---------|---------|-------------|
| Protocol | WPA2-Personal | WPA3-Personal (ESP32-S3 supports WPA3; ESP32 does not) |
| Password length | 8 characters | 16+ characters, random |
| SSID | Not broadcast (hidden SSID provides no real security) | Same; do not rely on SSID hiding |

The ESP32 connects using `WiFi.begin(ssid, password)` with no further certificate verification.

### Hardcoded Fallback

`bridge_config.h` currently defines no fallback credentials. The Wi-Fi connection fails silently if `BRIDGE_WIFI_SSID` / `BRIDGE_WIFI_PASSWORD` are empty or incorrect, and the MQTT bridge remains disabled.

Do not add hardcoded fallback credentials. If provisioning fails, the device should remain offline rather than connect to an unintended network.

### Network Isolation Recommendations

- Deploy ESP32 bridges on a dedicated VLAN, isolated from corporate IT and office networks.
- The MQTT broker should be reachable only from the bridge VLAN, not from general office Wi-Fi.
- Disable `WiFi.disconnect(true)` auto-reconnect to avoid unintended AP associations if the configured SSID disappears.

---

## 5. Recommendations

### Production Deployment Checklist

Before deploying any device outside a fully isolated lab:

- [ ] **Enable TLS on the MQTT broker.** Set port to 8883. Do not run port 1883 on any network with untrusted actors.
- [ ] **Configure certificate pinning on the ESP32.** Use `WiFiClientSecure::setFingerprint()` or `setCACert()` with the broker CA loaded from SPIFFS.
- [ ] **Rotate default MQTT broker credentials.** Do not use admin/admin or any well-known default.
- [ ] **Assign a unique `BRIDGE_MQTT_CLIENT_ID` per device.** This is required for broker ACL enforcement.
- [ ] **Configure broker ACLs.** Restrict each client to its own topic prefix (`smart-factory/{deviceId}/#`). Do not allow cross-device topic access.
- [ ] **Use strong Wi-Fi passwords.** Minimum WPA2-Personal with 16+ random characters. Place bridges on an isolated VLAN.
- [ ] **Protect the firmware binary.** Enable ESP32 flash encryption and secure boot to prevent extraction of compiled-in credentials from dumped flash.
- [ ] **Enable Last Will and Testament (LWT).** The bridge already publishes an offline payload on disconnect. Verify the broker is configured to act on it.
- [ ] **Disable debug logging in production.** Ensure `BRIDGE_LOG_LEVEL` is not set to `DEBUG` in production builds. Leaking `deviceId` or connection state is low-risk but unnecessary.
- [ ] **Monitor for credential reuse.** Each device should have its own MQTT password. If one device is compromised, rotation should not affect other devices.

### Hardware Security Options

| Feature | ESP32 | ESP32-S3 | Notes |
|---------|-------|----------|-------|
| Flash encryption | Yes (requires secure boot for full protection) | Yes | Prevents offline extraction of firmware + secrets from flash dump. |
| Secure boot | Yes | Yes (improved) | Verifies firmware signature on every boot. Required for flash encryption to be fully effective. |
| eFuse PROTECT_JTAG | Recommended | Recommended | Disables JTAG debug interface. |
| ESP32-S3 specific: `esp_secure_cert_t` | N/A | Yes | Stores CA/client certificates in protected memory. |
| External secure element (ATECC608A) | External | External | Recommended for vault-backed credential provisioning. |

Flash encryption alone (without secure boot) prevents casual flash dumps but does not prevent a determined attacker who disables flash protection via esptool. Enable both for meaningful hardware security.

### TLS Implementation Roadmap

1. **Phase 1 (short term)**: Broker TLS with self-signed CA, CA embedded at compile time. No pinning; use `setCACert()`. Set `BRIDGE_MQTT_PORT=8883`.
2. **Phase 2 (medium term)**: Load CA from SPIFFS. Add certificate fingerprint pinning via `setFingerprint()`. Add `BRIDGE_MQTT_CA_CERT_PATH` to `secrets.h`.
3. **Phase 3 (production)**: Client certificate authentication. Generate per-device client certs, store in SPIFFS or external secure element. Enable broker `require_certificate true`.
4. **Phase 4 (long term)**: Vault integration with device attestation. Eliminate compile-time secrets entirely.

---

*Last reviewed: 2026-10-12*
*Related: [mqtt-contract.md](mqtt-contract.md), `esp32/include/secrets.example.h`, `esp32/src/mqtt_bridge.cpp`*
