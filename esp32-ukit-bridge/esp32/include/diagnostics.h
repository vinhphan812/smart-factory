#pragma once

#include <cstdint>

// Forward declaration — PubSubClient.h is included by the caller
// (mqtt_bridge.cpp / diagnostics.cpp) to avoid pulling Arduino headers into
// every file that only needs the diagnostics counters.
class PubSubClient;

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
#if defined(PLATFORMIO_NATIVE_TEST)
DiagnosticsCounters g_diagnostics;
#else
extern DiagnosticsCounters g_diagnostics;
#endif

}  // namespace bridge

// ---------------------------------------------------------------------------
// Diagnostics functions — defined in diagnostics.cpp (ESP32 build).
// The native_test build exercises these via stubs or direct calls.
// ---------------------------------------------------------------------------

// Publishes a heartbeat JSON to smart-factory/{deviceId}/heartbeat every
// kHeartbeatIntervalMs (30 s). Increments heartbeats_sent counter.
bool publishHeartbeat(PubSubClient& client, const char* deviceId,
                      uint16_t queueDepth, uint32_t lastTelAgeMs);

// Checks telemetry staleness. On first stale detection: increments
// telemetry_timeout_count and publishes warning event. On critical timeout
// (2x): publishes critical event. On recovery: publishes recovery event and
// increments telemetry_recovered_count.
bool checkTelemetryHealth(PubSubClient& client, const char* deviceId,
                          uint32_t nowMs, uint32_t lastTelAgeMs,
                          bool& wasStale);
