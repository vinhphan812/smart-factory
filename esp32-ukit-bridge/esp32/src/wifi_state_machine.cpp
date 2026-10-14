#include "wifi_state_machine.h"

#include <Arduino.h>
#include <WiFi.h>

#include "bridge_config.h"
#include "diagnostics.h"

WifiStateMachine::WifiStateMachine(const char* ssid, const char* password)
    : ssid_(ssid), password_(password) {}

void WifiStateMachine::begin(uint32_t nowMs) {
  if (ssid_ == nullptr || ssid_[0] == '\0') {
    state_ = State::Disabled;
    return;
  }

  WiFi.persistent(false);
  WiFi.setAutoReconnect(false);
  WiFi.mode(WIFI_STA);
  retryDelayMs_ = bridge_config::kWifiInitialRetryMs;
  startAttempt(nowMs);
}

void WifiStateMachine::tick(uint32_t nowMs) {
  if (state_ == State::Disabled) {
    return;
  }

  const wl_status_t status = WiFi.status();
  if (status == WL_CONNECTED) {
    if (state_ != State::Connected) {
      state_ = State::Connected;
      stateSinceMs_ = nowMs;
      retryDelayMs_ = bridge_config::kWifiInitialRetryMs;
      ++bridge::g_diagnostics.wifi_reconnects;
    }
    return;
  }

  if (state_ == State::Connected) {
    scheduleRetry(nowMs);
    return;
  }

  if (state_ == State::Connecting &&
      static_cast<uint32_t>(nowMs - stateSinceMs_) >=
          bridge_config::kWifiConnectTimeoutMs) {
    WiFi.disconnect(false, false);
    scheduleRetry(nowMs);
    return;
  }

  if (state_ == State::Waiting && due(nowMs, retryAtMs_)) {
    startAttempt(nowMs);
  }
}

bool WifiStateMachine::connected() const {
  return state_ == State::Connected && WiFi.status() == WL_CONNECTED;
}

WifiStateMachine::State WifiStateMachine::state() const { return state_; }

void WifiStateMachine::startAttempt(uint32_t nowMs) {
  WiFi.begin(ssid_, password_ == nullptr ? "" : password_);
  state_ = State::Connecting;
  stateSinceMs_ = nowMs;
}

void WifiStateMachine::scheduleRetry(uint32_t nowMs) {
  state_ = State::Waiting;
  stateSinceMs_ = nowMs;
  retryAtMs_ = nowMs + retryDelayMs_;
  if (retryDelayMs_ < bridge_config::kWifiMaxRetryMs) {
    retryDelayMs_ *= 2;
    if (retryDelayMs_ > bridge_config::kWifiMaxRetryMs) {
      retryDelayMs_ = bridge_config::kWifiMaxRetryMs;
    }
  }
}

bool WifiStateMachine::due(uint32_t nowMs, uint32_t deadlineMs) {
  return static_cast<int32_t>(nowMs - deadlineMs) >= 0;
}
