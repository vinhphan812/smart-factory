#pragma once

#include <cstdint>
#include <cstring>

#include "amlp/amlp.hpp"

namespace bridge {

// Maximum number of key=value pairs that can be embedded in a single
// telemetry frame field (e.g. "SENSOR1=1,SENSOR2=0").
constexpr std::size_t kMaxTelemetryPairs = 4;

// Maximum number of raw value fields in a telemetry frame (excluding
// key=value pairs).
constexpr std::size_t kMaxTelemetryValues = 6;

// ---------------------------------------------------------------------------
// TelemetryFrame — parsed representation of an AMLP TEL frame
// ---------------------------------------------------------------------------

struct TelemetryValue {
  char text[amlp::kMaxFieldLength + 1]{};
  std::uint8_t length = 0;
};

struct TelemetryPair {
  char key[amlp::kMaxFieldLength + 1]{};     // max field (64) + null terminator
  char value[amlp::kMaxFieldLength + 1 + 4]{}; // allows val to fill 64 bytes + null
};

struct TelemetryFrame {
  // Monotonic millisecond timestamp captured at the moment the frame was
  // recognised as complete (written by UartAdapter::handleFrame).
  std::uint32_t received_at_ms = 0;

  // Number of raw value fields (indices 1..N that are not key=value format).
  std::uint8_t num_values = 0;
  TelemetryValue values[kMaxTelemetryValues]{};

  // Number of key=value pairs found in fields.
  std::uint8_t num_pairs = 0;
  TelemetryPair pairs[kMaxTelemetryPairs]{};

  // Overflow tracking: set by UartAdapter::dispatchTelemetry() when one or more
  // fields were silently dropped due to capacity limits.  Used by MqttBridge to
  // emit "truncated":true in the JSON payload and update diagnostics.
  std::uint8_t overflow_dropped_values = 0;
  std::uint8_t overflow_dropped_pairs = 0;

  // True if at least one field was parsed into pairs or values.
  bool has_data() const {
    return num_values > 0 || num_pairs > 0;
  }
};

// ---------------------------------------------------------------------------
// TelemetryHandler — callback interface used by UartAdapter to dispatch
// parsed telemetry frames.  The bridge (MqttBridge) implements this
// interface to publish frames over MQTT.
// ---------------------------------------------------------------------------

class TelemetryHandler {
 public:
  virtual ~TelemetryHandler() = default;

  // Called by UartAdapter when a valid AMLP TEL frame is received.
  // The frame is guaranteed to have passed CRC validation.
  // Implementations must not block — return quickly or offload to a queue.
  virtual void onTelemetry(const TelemetryFrame& frame) = 0;
};

}  // namespace bridge
