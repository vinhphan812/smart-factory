#include "uart_adapter.h"

#include <cstdlib>
#include <cstring>

#include "bridge_config.h"

namespace {
constexpr std::size_t kMaxBytesPerPoll = 64;

int16_t parseStatus(std::string_view value) {
  if (value == "OK" || value == "0") return 0;
  if (value == "UNKNOWN_COMMAND" || value == "1") return 1;
  if (value == "INVALID_ARGUMENT" || value == "2") return 2;
  if (value == "INTERNAL_ERROR" || value == "3") return 3;
  return -1;
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
    handleFrame(receivedFrame_, core);
  }
}

void UartAdapter::handleFrame(const amlp::Frame& frame,
                              bridge::BridgeCore& core) {
  if (frame.type != amlp::Type::Ack || frame.field_count < 2) {
    return;
  }

  const std::string_view sequenceField = frame.field(0);
  if (sequenceField.empty() || sequenceField.size() >= 6) {
    return;
  }

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
