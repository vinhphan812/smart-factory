#pragma once

#include <cstdint>

class WifiStateMachine {
 public:
  enum class State : uint8_t {
    Disabled,
    Waiting,
    Connecting,
    Connected,
  };

  WifiStateMachine(const char* ssid, const char* password);

  void begin(uint32_t nowMs);
  void tick(uint32_t nowMs);
  bool connected() const;
  State state() const;

 private:
  void startAttempt(uint32_t nowMs);
  void scheduleRetry(uint32_t nowMs);
  static bool due(uint32_t nowMs, uint32_t deadlineMs);

  const char* ssid_;
  const char* password_;
  State state_ = State::Disabled;
  uint32_t stateSinceMs_ = 0;
  uint32_t retryAtMs_ = 0;
  uint32_t retryDelayMs_ = 0;
};
