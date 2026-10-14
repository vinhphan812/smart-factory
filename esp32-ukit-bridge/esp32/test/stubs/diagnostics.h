// Minimal DiagnosticsCounters stub for native unit tests.
// Replaces diagnostics.h / diagnostics.cpp in the native (non-ESP32) test build.

#pragma once

#include <cstdint>

namespace bridge {

struct DiagnosticsCounters {
  uint32_t tx_frames = 0;
  uint32_t rx_frames = 0;
  uint32_t crc_errors = 0;
  uint32_t parse_errors = 0;
  uint32_t retries = 0;
  uint16_t queue_depth = 0;
  uint32_t mqtt_publishes = 0;
  uint32_t mqtt_connects = 0;
  uint32_t mqtt_connect_fails = 0;
  uint32_t wifi_reconnects = 0;
  uint32_t heartbeats_sent = 0;
  uint32_t telemetry_timeout_count = 0;
  uint32_t telemetry_recovered_count = 0;
};

// Tentative definition: every TU that includes this header gets one.
// The linker merges all tentative definitions for the same symbol into a single
// instance (C++ standard [basic.link]/3).  This avoids both multiple-definition
// errors (no strong definition elsewhere in the TU) and undefined-reference
// errors (the tentative definition provides the object).
DiagnosticsCounters g_diagnostics;

}  // namespace bridge
