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

}  // namespace bridge_config
