#include "uart_adapter.h"

#include <cstdlib>
#include <cstring>

#include "bridge_config.h"
#include "diagnostics.h"

namespace {
constexpr std::size_t kMaxBytesPerPoll = 64;

int16_t parseStatus(std::string_view value) {
  if (value == "OK" || value == "0") return 0;
  if (value == "UNKNOWN_COMMAND" || value == "1") return 1;
  if (value == "INVALID_ARGUMENT" || value == "2") return 2;
  if (value == "INTERNAL_ERROR" || value == "3") return 3;
  return -1;
}

// Returns the index of the first '=' in `field`, or field.npos if no '='.
std::size_t findEquals(std::string_view field) {
  for (std::size_t i = 0; i < field.size(); ++i) {
    if (field[i] == '=') return i;
  }
  return std::string_view::npos;
}

}  // namespace

UartAdapter::UartAdapter(HardwareSerial& serial) : serial_(serial) {}

void UartAdapter::begin() {
  serial_.begin(bridge_config::kUartBaud, SERIAL_8N1,
                bridge_config::kUartRxPin, bridge_config::kUartTxPin);
}

void UartAdapter::poll(uint32_t nowMs, bridge::BridgeCore& core) {
  std::size_t processed = 0;
  while (serial_.available() > 0 && processed < kMaxBytesPerPoll) {
    const int value = serial_.read();
    if (value >= 0) {
      consume(static_cast<uint8_t>(value), nowMs, core);
      ++processed;
    }
  }
  if (processed == 0) {
    parser_.check_timeout(nowMs);
  }
  // Update last-frame timestamp when any valid frame is received.
  // handleFrame() sets lastFrameReceivedMs_ on ACK and TEL frames.
  if (lastFrameReceivedMs_ != 0) {
    const uint32_t age = nowMs - lastFrameReceivedMs_;
    if (age < 0x80000000U) {   // Reject millis wraparound
      (void)age;
    }
  }
}

bool UartAdapter::send(const uint8_t* data, std::size_t length) {
  if (data == nullptr || length == 0) {
    return false;
  }
  return serial_.write(data, length) == length;
}

void UartAdapter::consume(uint8_t byte, uint32_t nowMs,
                          bridge::BridgeCore& core) {
  const amlp::ParseResult result = parser_.feed(byte, nowMs, receivedFrame_);
  if (result.status == amlp::ParseStatus::FrameReady) {
    handleFrame(receivedFrame_, nowMs, core);
  } else if (result.status == amlp::ParseStatus::Error) {
    ++bridge::g_diagnostics.parse_errors;
  }
}

void UartAdapter::handleFrame(const amlp::Frame& frame, uint32_t nowMs,
                              bridge::BridgeCore& core) {
  lastFrameReceivedMs_ = nowMs;
  ++bridge::g_diagnostics.rx_frames;

  if (frame.type == amlp::Type::Ack && frame.field_count >= 2) {
    // ---- AMLP ACK frame — correlate with pending command ----
    const std::string_view sequenceField = frame.field(0);
    if (!sequenceField.empty() && sequenceField.size() < 6) {
      char sequenceText[6]{};
      std::memcpy(sequenceText, sequenceField.data(), sequenceField.size());
      char* end = nullptr;
      const unsigned long parsed = std::strtoul(sequenceText, &end, 10);
      const int16_t statusCode = parseStatus(frame.field(1));
      if (end != sequenceText && end != nullptr && *end == '\0' &&
          parsed <= UINT16_MAX && statusCode >= 0) {
        core.acknowledge(static_cast<uint16_t>(parsed), statusCode);
      }
    }
    return;
  }

  if (frame.type == amlp::Type::Tel) {
    dispatchTelemetry(frame, nowMs, telemetryHandler_);
  }
  // Other frame types are silently dropped.
}

void UartAdapter::dispatchTelemetry(const amlp::Frame& frame, uint32_t nowMs,
                                   bridge::TelemetryHandler* handler) {
  if (handler == nullptr) {
    return;
  }

  bridge::TelemetryFrame tel{};
  tel.received_at_ms = nowMs;

  for (std::uint8_t i = 0; i < frame.field_count; ++i) {
    const std::string_view field = frame.field(i);
    if (field.empty()) {
      continue;
    }

    if (findEquals(field) != std::string_view::npos) {
      if (tel.num_pairs < bridge::kMaxTelemetryPairs) {
        auto& pair = tel.pairs[tel.num_pairs];
        const std::size_t eq = findEquals(field);
        const std::size_t keyLen =
            (eq < amlp::kMaxFieldLength) ? eq : amlp::kMaxFieldLength;
        const std::size_t valLen =
            (field.size() - eq - 1 < amlp::kMaxFieldLength)
                ? field.size() - eq - 1
                : amlp::kMaxFieldLength;
        std::memcpy(pair.key, field.data(), keyLen);
        pair.key[keyLen] = '\0';
        std::memcpy(pair.value, field.data() + eq + 1, valLen);
        pair.value[valLen] = '\0';
        ++tel.num_pairs;
      } else {
        ++tel.overflow_dropped_pairs;
      }
    } else {
      if (tel.num_values < bridge::kMaxTelemetryValues) {
        auto& val = tel.values[tel.num_values];
        const std::size_t copyLen =
            (field.size() < amlp::kMaxFieldLength) ? field.size()
                                                    : amlp::kMaxFieldLength;
        std::memcpy(val.text, field.data(), copyLen);
        val.text[copyLen] = '\0';
        val.length = static_cast<std::uint8_t>(copyLen);
        ++tel.num_values;
      } else {
        ++tel.overflow_dropped_values;
      }
    }
  }

  if (tel.has_data()) {
    handler->onTelemetry(tel);
  }
}

void UartAdapter::dispatchFrame(const amlp::Frame& frame, uint32_t nowMs,
                               bridge::TelemetryHandler* handler) {
  if (frame.type == amlp::Type::Tel) {
    dispatchTelemetry(frame, nowMs, handler);
  }
}

void UartAdapter::feedBytes(const uint8_t* bytes, std::size_t count,
                            uint32_t nowMs, bridge::BridgeCore& core,
                            bridge::TelemetryHandler* handler) {
  amlp::Parser parser;
  amlp::Frame frame;
  for (std::size_t i = 0; i < count; ++i) {
    const amlp::ParseResult result = parser.feed(bytes[i], nowMs + i, frame);
    if (result.status == amlp::ParseStatus::FrameReady) {
      dispatchFrame(frame, nowMs + i, handler);
      (void)core;  // core not used in this path
    }
  }
}

bool UartAdapter::parseField(std::string_view field,
                             bridge::TelemetryFrame& out) const {
  (void)field;
  (void)out;
  return false;  // Implemented inline in handleFrame for efficiency.
}

void UartAdapter::setTelemetryHandler(bridge::TelemetryHandler* handler) {
  telemetryHandler_ = handler;
}

uint32_t UartAdapter::lastFrameAgeMs(uint32_t nowMs) const {
  if (lastFrameReceivedMs_ == 0) {
    return 0;
  }
  const uint32_t diff = nowMs - lastFrameReceivedMs_;
  // Treat a negative diff as wraparound — return 0 so caller doesn't overflow.
  return (diff < 0x80000000U) ? diff : 0;
}
