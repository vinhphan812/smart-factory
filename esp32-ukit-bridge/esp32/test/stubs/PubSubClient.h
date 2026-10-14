// Minimal PubSubClient stub for native unit tests.
// Provides enough of the PubSubClient interface for MqttBridge compilation
// without requiring the full Arduino PubSubClient library.

#pragma once

#include <cstddef>
#include <cstdint>

class PubSubClient {
 public:
  PubSubClient() = default;
  explicit PubSubClient(const char*, uint16_t, void (*)(char*, uint8_t*, unsigned int)) {}

  void setServer(const char*, uint16_t) {}
  void setCallback(void (*)(char*, uint8_t*, unsigned int)) {}
  void setKeepAlive(uint16_t) {}
  void setSocketTimeout(int) {}
  void setBufferSize(int) {}
  bool connect(const char*, const char*, const char*, const char*, uint8_t, bool,
               const char*) {
    return connected_;
  }
  void disconnect() {}
  bool connected() const { return connected_; }
  void setConnected(bool v) { connected_ = v; }
  bool publish(const char*, const char*, bool) { return publishReturn_; }
  void setPublishReturn(bool v) { publishReturn_ = v; }
  bool subscribe(const char*, uint8_t) { return true; }
  bool loop() { return true; }

 private:
  bool connected_ = false;
  bool publishReturn_ = true;
};
