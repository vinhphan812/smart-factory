#pragma once

// =============================================================================
// Smart Factory ESP32 Bridge — Secrets Configuration
// =============================================================================
// Copy this file to secrets.h and fill in the values for each deployed device.
// NEVER commit secrets.h to version control — it is excluded by .gitignore.
//
// For production deployments, also read docs/mqtt-security.md for TLS setup,
// Wi-Fi hardening, and credential rotation guidance.
// =============================================================================

// -----------------------------------------------------------------------------
// Wi-Fi Configuration
// -----------------------------------------------------------------------------
// The ESP32 connects to this SSID using WPA2-Personal (minimum) or WPA3.
// Use a 2.4 GHz network. The ESP32 does not support 5 GHz Wi-Fi.
// Leave both empty to disable Wi-Fi (useful for host-compiled unit tests).
#define BRIDGE_WIFI_SSID ""
#define BRIDGE_WIFI_PASSWORD ""

// Optional: Pin to a specific AP by MAC address to avoid roaming issues
// when multiple APs share the same SSID. Leave empty to connect to any AP
// with the matching SSID.
// Format: six hex bytes separated by colons, e.g. "DC:4A:3E:12:34:56"
#define BRIDGE_WIFI_BSSID ""

// -----------------------------------------------------------------------------
// MQTT Broker Configuration
// -----------------------------------------------------------------------------
// Connection endpoint. Use an IP address to avoid DNS dependency on the device,
// or a hostname if DNS resolution is reliably available on the network.
#define BRIDGE_MQTT_HOST ""

// Port: 1883 = plain MQTT (UNSAFE for production, see docs/mqtt-security.md).
//        8883 = MQTT over TLS (required for any deployment outside an isolated lab).
#define BRIDGE_MQTT_PORT 1883

// Authentication. Both must be non-empty to enable broker authentication.
// The broker is responsible for verifying the password.
//
// Compile-time enforcement: if BRIDGE_MQTT_USERNAME is empty, the firmware
// refuses to connect (fail-closed). Fill in both fields before deployment.
#define BRIDGE_MQTT_USERNAME ""
#define BRIDGE_MQTT_PASSWORD ""

// -----------------------------------------------------------------------------
// MQTT TLS Configuration
// -----------------------------------------------------------------------------
// These fields are only used when BRIDGE_MQTT_PORT is set to 8883 (TLS).
// Leave both empty when using plain MQTT on port 1883.
//
// Path to the broker CA certificate in SPIFFS, e.g. "/spiffs/certs/ca.crt".
// The certificate file must be uploaded to the SPIFFS partition separately
// from the firmware (see docs/mqtt-security.md Section 2).
// Leave empty when TLS is disabled.
#define BRIDGE_MQTT_CA_CERT_PATH ""

// SHA-256 fingerprint (hex, colon-separated) of the broker certificate for
// certificate pinning. Prevents MITM even if an attacker has the CA.
// To obtain: openssl x509 -in broker.crt -noout -fingerprint -sha256
// Example: "AA:BB:CC:DD:EE:FF:..."
// Leave empty to trust any certificate signed by the CA (less secure).
#define BRIDGE_MQTT_TLS_FINGERPRINT ""

// -----------------------------------------------------------------------------
// Device Identity
// -----------------------------------------------------------------------------
// Unique identifier for this device. Used as the MQTT client ID and as the
// topic prefix (smart-factory/{deviceId}/...).
// Each physical device must have a distinct ID. The broker uses this for
// session persistence, last-will routing, and ACL enforcement.
#define BRIDGE_MQTT_CLIENT_ID ""
