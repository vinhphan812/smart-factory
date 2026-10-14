#pragma once

#include "Arduino.h"

#include <cstddef>
#include <cstdint>

#include "amlp/amlp.hpp"
#include "bridge_core.h"
#include "telemetry_frame.h"

class UartAdapter final : public bridge::Transport {
 public:
  explicit UartAdapter(HardwareSerial& serial);

  void begin();
  void poll(uint32_t nowMs, bridge::BridgeCore& core);
  bool send(const uint8_t* data, std::size_t length) override;

  // Registers a handler for parsed AMLP TEL frames.  The handler's
  // onTelemetry() is called from poll() on the same task context.
  // Only one handler is active at a time (replaces any previous one).
  void setTelemetryHandler(bridge::TelemetryHandler* handler);

  // Milliseconds since the last valid AMLP frame (ACK or TEL) was received.
  // Returns 0 on first call until a frame arrives.
  uint32_t lastFrameAgeMs(uint32_t nowMs) const;

  // --- Testable overloads: feed bytes or a raw frame with an explicit handler.
  // These bypass the Arduino HardwareSerial dependency so the production decoder
  // can be unit-tested without a physical UART or mock serial.

  // Feeds raw bytes through the AMLP parser and dispatches the resulting frame.
  // Calls onTelemetry() on `handler` if the frame is a valid AMLP TEL.
  void feedBytes(const uint8_t* bytes, std::size_t count, uint32_t nowMs,
                 bridge::BridgeCore& core, bridge::TelemetryHandler* handler);

  // Dispatches a raw AMLP Frame directly to the telemetry handler.
  // The caller is responsible for populating `frame` (e.g. from a parser).
  void dispatchFrame(const amlp::Frame& frame, uint32_t nowMs,
                     bridge::TelemetryHandler* handler);

 private:
  void consume(uint8_t byte, uint32_t nowMs, bridge::BridgeCore& core);
  void handleFrame(const amlp::Frame& frame, uint32_t nowMs,
                   bridge::BridgeCore& core);
  void dispatchTelemetry(const amlp::Frame& frame, uint32_t nowMs,
                         bridge::TelemetryHandler* handler);

  // Parses an AMLP field into either a key=value pair or a plain value.
  // Returns true if the field was consumed (as either type).
  bool parseField(std::string_view field, bridge::TelemetryFrame& out) const;

  HardwareSerial& serial_;
  amlp::Parser parser_;
  amlp::Frame receivedFrame_{};
  uint32_t lastFrameReceivedMs_ = 0;

  // Registered telemetry consumer (owned by MqttBridge).
  bridge::TelemetryHandler* telemetryHandler_ = nullptr;
};
