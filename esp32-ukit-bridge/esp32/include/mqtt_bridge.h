#pragma once

#include <PubSubClient.h>

#include <cstddef>
#include <cstdint>

#include "bridge_core.h"
#include "telemetry_frame.h"

class MqttBridge final : public bridge::TelemetryHandler {
 public:
  MqttBridge(PubSubClient& client, bridge::BridgeCore& core,
             const char* host, uint16_t port, const char* username,
             const char* password, const char* deviceId);

  void begin();
  void tick(uint32_t nowMs, bool networkReady);

  // bridge::TelemetryHandler — called by UartAdapter when a TEL frame arrives.
  void onTelemetry(const bridge::TelemetryFrame& frame) override;

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

  static MqttBridge* instance_;

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
