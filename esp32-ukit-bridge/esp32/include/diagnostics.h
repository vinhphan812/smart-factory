#pragma once

#include <cstdint>

namespace bridge {

// Diagnostics counters tracked by the bridge.
// Counters are cumulative since boot; reset only on restart.
struct DiagnosticsCounters {
  // UART / AMLP layer
  uint32_t tx_frames = 0;       // AMLP frames sent to uKit over UART
  uint32_t rx_frames = 0;       // AMLP frames received from uKit over UART
  uint32_t crc_errors = 0;      // Frames rejected due to CRC mismatch
  uint32_t parse_errors = 0;    // Frames rejected due to syntax/format errors

  // Command layer
  uint32_t retries = 0;        // Command retransmission attempts
  uint16_t queue_depth = 0;    // Current pending command queue depth

  // MQTT layer
  uint32_t mqtt_publishes = 0;     // MQTT packets published (acks/results)
  uint32_t mqtt_connects = 0;      // Successful MQTT connect attempts
  uint32_t mqtt_connect_fails = 0; // Failed MQTT connect attempts

  // Wi-Fi layer
  uint32_t wifi_reconnects = 0;  // Wi-Fi reconnection events (Connecting → Connected)

  // Health layer
  uint32_t heartbeats_sent = 0;              // Heartbeat messages published
  uint32_t telemetry_timeout_count = 0;       // Times telemetry became stale
  uint32_t telemetry_recovered_count = 0;    // Times telemetry recovered after stale
};

// Global diagnostics instance.
// In native unit tests PLATFORMIO_NATIVE_TEST is defined by the native build system
// and we provide the definition here to avoid compiling diagnostics.cpp (which
// depends on Arduino/WiFi/ArduinoJson).  In the ESP32 build the real diagnostics.cpp
// provides the strong definition.
// Global diagnostics instance (strong definition lives in diagnostics.cpp for ESP32,
// or diagnostics_stub.cpp for the native_test build).
extern DiagnosticsCounters g_diagnostics;

}  // namespace bridge
