#pragma once

#if defined(PLATFORMIO_NATIVE_TEST)
#include "../test/stubs/PubSubClient.h"
#else
#include <PubSubClient.h>
#endif

#include <ArduinoJson.h>

#include <cstddef>
#include <cstdint>

#include "bridge_core.h"
#include "telemetry_frame.h"

namespace bridge {

// Builds a telemetry JSON payload into buffer[BufferSize] and returns the
// serialised byte count.  Returns 0 on measureJson overflow or serializeJson
// failure.  This function is the single canonical implementation shared by both
// production (ESP32) and native unit tests.
template <std::size_t BufferSize, typename PubSubClientLike>
std::size_t publishTelemetry(const TelemetryFrame& frame,
                              PubSubClientLike& client,
                              char (&buffer)[BufferSize],
                              const char* device_id,
                              const char* telemetry_topic,
                              std::uint32_t& tel_dropped,
                              std::uint32_t& tel_published) {
  JsonDocument doc;
  doc["device_id"] = device_id;
  doc["received_at_ms"] = frame.received_at_ms;

  if (frame.num_values > 0) {
    JsonArray vals = doc["values"].to<JsonArray>();
    for (std::uint8_t i = 0; i < frame.num_values; ++i) {
      vals.add(frame.values[i].text);
    }
  }

  if (frame.num_pairs > 0) {
    JsonObject pairs = doc["pairs"].to<JsonObject>();
    for (std::uint8_t i = 0; i < frame.num_pairs; ++i) {
      pairs[frame.pairs[i].key] = frame.pairs[i].value;
    }
  }

  if (frame.overflow_dropped_values > 0 || frame.overflow_dropped_pairs > 0) {
    doc["truncated"] = true;
    doc["overflow_dropped_values"] = frame.overflow_dropped_values;
    doc["overflow_dropped_pairs"] = frame.overflow_dropped_pairs;
  }

  const std::size_t measured = measureJson(doc);
  if (measured + 1 > BufferSize) {
    ++tel_dropped;
    return 0;
  }

  char tmp[BufferSize]{};
  const std::size_t len = serializeJson(doc, tmp, sizeof(tmp));
  if (len == 0) {
    ++tel_dropped;
    return 0;
  }

  // Copy into caller's buffer so the caller can inspect it.
  for (std::size_t i = 0; i < len && i < BufferSize; ++i) {
    buffer[i] = tmp[i];
  }

  const bool ok = client.publish(telemetry_topic, buffer, false);
  if (ok) {
    ++tel_published;
  } else {
    ++tel_dropped;
  }
  return len;
}

}  // namespace bridge

class MqttBridge final : public bridge::TelemetryHandler {
 public:
  MqttBridge(PubSubClient& client, bridge::BridgeCore& core,
             const char* host, uint16_t port, const char* username,
             const char* password, const char* deviceId);

  void begin();
  void tick(uint32_t nowMs, bool networkReady);

  // bridge::TelemetryHandler — called by UartAdapter when a TEL frame arrives.
  void onTelemetry(const bridge::TelemetryFrame& frame) override;

  // Constructs the telemetry JSON and stores it in buffer (max BufferSize bytes).
  // Returns the number of bytes written, or 0 on failure.
  // Tests can call this directly; production publishTelemetry delegates to it.
  template <std::size_t BufferSize>
  std::size_t buildTelemetryPayload(const bridge::TelemetryFrame& frame,
                                   char (&buffer)[BufferSize]) const {
    JsonDocument doc;
    doc["device_id"] = deviceId_;
    doc["received_at_ms"] = frame.received_at_ms;

    if (frame.num_values > 0) {
      JsonArray vals = doc["values"].to<JsonArray>();
      for (std::uint8_t i = 0; i < frame.num_values; ++i) {
        vals.add(frame.values[i].text);
      }
    }

    if (frame.num_pairs > 0) {
      JsonObject pairs = doc["pairs"].to<JsonObject>();
      for (std::uint8_t i = 0; i < frame.num_pairs; ++i) {
        pairs[frame.pairs[i].key] = frame.pairs[i].value;
      }
    }

    if (frame.overflow_dropped_values > 0 || frame.overflow_dropped_pairs > 0) {
      doc["truncated"] = true;
      doc["overflow_dropped_values"] = frame.overflow_dropped_values;
      doc["overflow_dropped_pairs"] = frame.overflow_dropped_pairs;
    }

    const std::size_t measured = measureJson(doc);
    if (measured + 1 > BufferSize) {
      return 0;
    }

    const std::size_t len = serializeJson(doc, buffer, BufferSize);
    return (len == 0) ? 0 : len;
  }

  bool enabled() const { return enabled_; }
  std::uint32_t telDropped() const { return telDropped_; }
  std::uint32_t telPublished() const { return telPublished_; }

  // Exposed for test injection: publishes a frame using an arbitrary client.
  // Delegates to the shared bridge::publishTelemetry free function.
  template <typename PubSubClientLike>
  std::size_t publishWith(const bridge::TelemetryFrame& frame,
                          PubSubClientLike& client) const {
    char buffer[384]{};
    return bridge::publishTelemetry(frame, client, buffer, deviceId_,
                                   telemetryTopic_, telDropped_, telPublished_);
  }

 private:
  void publishTelemetry(const bridge::TelemetryFrame& frame);
  static void callbackThunk(char* topic, uint8_t* payload,
                            unsigned int length);
  void onMessage(const char* topic, const uint8_t* payload,
                 std::size_t length);
  void connectOnce(uint32_t nowMs);
  bool allocateSequence(uint16_t& sequence);
  void publishImmediateAck(const char* requestId, uint16_t sequence,
                           const char* command, const char* status,
                           int16_t statusCode);
  void publishCompletions();
  bool publishCompletion(const bridge::Completion& completion);
  void publishOnlineStatus();
  static bool due(uint32_t nowMs, uint32_t deadlineMs);

  inline static MqttBridge* instance_;

  PubSubClient& client_;
  bridge::BridgeCore& core_;
  const char* host_;
  uint16_t port_;
  const char* username_;
  const char* password_;
  const char* deviceId_;
  char commandTopic_[128]{};
  char ackTopic_[128]{};
  char telemetryTopic_[128]{};
  char statusTopic_[128]{};
  uint16_t nextSequence_ = 0;
  uint32_t reconnectAtMs_ = 0;
  bool enabled_ = false;
  bool completionPendingPublish_ = false;
  bridge::Completion completionPending_{};

  // Telemetry QoS/backpressure: if the MQTT write buffer is full, drop rather
  // than block the UART poll loop.  Backpressure accounting is diagnostic only.
  uint32_t telDropped_ = 0;
  uint32_t telPublished_ = 0;
};

// ---------------------------------------------------------------------------
// Inline constructor and begin() — defined here so they are always compiled
// (both ESP32 via mqtt_bridge.cpp and native tests via this header).
// ---------------------------------------------------------------------------

inline MqttBridge::MqttBridge(PubSubClient& client, bridge::BridgeCore& core,
                               const char* host, uint16_t port, const char* username,
                               const char* password, const char* deviceId)
    : client_(client),
      core_(core),
      host_(host),
      port_(port),
      username_(username),
      password_(password),
      deviceId_(deviceId) {}

inline void MqttBridge::begin() {
  enabled_ = host_ != nullptr && host_[0] != '\0' && deviceId_ != nullptr &&
             deviceId_[0] != '\0';
  if (!enabled_) {
    return;
  }

  std::snprintf(commandTopic_, sizeof(commandTopic_),
                "smart-factory/%s/command/down", deviceId_);
  std::snprintf(ackTopic_, sizeof(ackTopic_),
                "smart-factory/%s/command/ack", deviceId_);
  std::snprintf(telemetryTopic_, sizeof(telemetryTopic_),
                "smart-factory/%s/telemetry", deviceId_);
  std::snprintf(statusTopic_, sizeof(statusTopic_),
                "smart-factory/%s/status", deviceId_);

  instance_ = this;
  client_.setServer(host_, port_);
  client_.setCallback(callbackThunk);
  client_.setKeepAlive(30);
  client_.setSocketTimeout(1);
  client_.setBufferSize(768);
}

// ---------------------------------------------------------------------------
// Inline callbackThunk — stub for native tests.  In the ESP32 build the real
// version from mqtt_bridge.cpp is compiled (PLATFORMIO_NATIVE_TEST is not set).
// ---------------------------------------------------------------------------
#if defined(PLATFORMIO_NATIVE_TEST)
inline void MqttBridge::callbackThunk(char*, uint8_t*, unsigned int) {}
#endif
