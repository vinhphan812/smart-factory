#pragma once

#include <Arduino.h>

#include <cstddef>
#include <cstdint>

#include "amlp/amlp.hpp"
#include "bridge_core.h"

class UartAdapter final : public bridge::Transport {
 public:
  explicit UartAdapter(HardwareSerial& serial);

  void begin();
  void poll(uint32_t nowMs, bridge::BridgeCore& core);
  bool send(const uint8_t* data, std::size_t length) override;

 private:
  void consume(uint8_t byte, uint32_t nowMs, bridge::BridgeCore& core);
  void handleFrame(const amlp::Frame& frame, bridge::BridgeCore& core);

  HardwareSerial& serial_;
  amlp::Parser parser_;
  amlp::Frame receivedFrame_{};
};
