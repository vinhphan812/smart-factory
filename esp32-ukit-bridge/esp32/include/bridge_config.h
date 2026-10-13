#pragma once

#include <cstddef>
#include <cstdint>

namespace bridge_config {

constexpr int kUartRxPin = 18;
constexpr int kUartTxPin = 17;
constexpr uint32_t kUartBaud = 115200;

constexpr uint32_t kWifiConnectTimeoutMs = 15000;
constexpr uint32_t kWifiInitialRetryMs = 5000;
constexpr uint32_t kWifiMaxRetryMs = 60000;
constexpr uint32_t kMqttRetryMs = 5000;

// Heartbeat
constexpr uint32_t kHeartbeatIntervalMs = 30000;  // 30 seconds

// Telemetry health
constexpr uint32_t kTelemetryTimeoutMs = 60000;   // 60 seconds; "stale" after this
constexpr uint32_t kTelemetryCriticalTimeoutMs =
    120000;  // 120 seconds; publish event after this

// MQTT reconnect backoff
constexpr uint32_t kMqttBackoffInitialMs = 5000;
constexpr uint32_t kMqttBackoffMaxMs = 60000;

}  // namespace bridge_config
