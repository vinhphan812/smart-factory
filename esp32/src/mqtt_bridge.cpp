#include "mqtt_bridge.h"

#include <ArduinoJson.h>

#include <cstdio>
#include <cstring>

#include "amlp/amlp.hpp"
#include "bridge_config.h"

namespace {

constexpr char kOfflinePayload[] =
    "{\"online\":false,\"reason\":\"mqtt_disconnect\"}";

bool copyText(char* destination, std::size_t capacity, const char* source) {
  if (destination == nullptr || capacity == 0 || source == nullptr) {
    return false;
  }
  const std::size_t length = std::strlen(source);
  if (length == 0 || length >= capacity) {
    return false;
  }
  std::memcpy(destination, source, length + 1);
  return true;
}

bool buildAmlpCommand(JsonDocument& document, uint16_t sequence,
                      bridge::Command& command) {
  const char* requestId = document["request_id"] | nullptr;
  const char* commandName = document["command"] | nullptr;
  if (!copyText(command.requestId, sizeof(command.requestId), requestId) ||
      !copyText(command.commandName, sizeof(command.commandName), commandName)) {
    return false;
  }

  amlp::Frame frame{};
  frame.type = amlp::Type::Cmd;
  char sequenceText[6]{};
  std::snprintf(sequenceText, sizeof(sequenceText), "%u",
                static_cast<unsigned int>(sequence));
  if (!frame.set_field(0, sequenceText)) {
    return false;
  }

  if (std::strcmp(commandName, "ping") == 0) {
    if (!frame.set_field(1, "PING")) {
      return false;
    }
  } else if (std::strcmp(commandName, "reset") == 0) {
    if (!frame.set_field(1, "RESET")) {
      return false;
    }
  } else if (std::strcmp(commandName, "set_output") == 0) {
    const JsonVariant channelValue = document["channel"];
    const JsonVariant outputValue = document["value"];
    if (!channelValue.is<unsigned int>() ||
        channelValue.as<unsigned int>() > 255U || !outputValue.is<bool>()) {
      return false;
    }
    char channelText[4]{};
    std::snprintf(channelText, sizeof(channelText), "%u",
                  channelValue.as<unsigned int>());
    if (!frame.set_field(1, "SET_OUTPUT") ||
        !frame.set_field(2, channelText) ||
        !frame.set_field(3, outputValue.as<bool>() ? "1" : "0")) {
      return false;
    }
  } else {
    return false;
  }

  char encoded[amlp::kMaxFrameLength]{};
  std::size_t written = 0;
  if (amlp::encode(frame, encoded, sizeof(encoded), written) !=
          amlp::Error::None ||
      written == 0 || written > bridge::kMaxPayloadSize) {
    return false;
  }

  command.sequence = sequence;
  command.payloadLength = static_cast<uint16_t>(written);
  std::memcpy(command.payload, encoded, written);
  return true;
}

const char* statusName(int16_t statusCode) {
  switch (statusCode) {
    case 0:
      return "ok";
    case 1:
      return "unknown_command";
    case 2:
      return "invalid_argument";
    case 3:
      return "internal_error";
    default:
      return "internal_error";
  }
}

}  // namespace

MqttBridge* MqttBridge::instance_ = nullptr;

MqttBridge::MqttBridge(PubSubClient& client, bridge::BridgeCore& core,
                       const char* host, uint16_t port, const char* username,
                       const char* password, const char* deviceId)
    : client_(client),
      core_(core),
      host_(host),
      port_(port),
      username_(username),
      password_(password),
      deviceId_(deviceId) {}

void MqttBridge::begin() {
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

void MqttBridge::tick(uint32_t nowMs, bool networkReady) {
  if (!enabled_) {
    return;
  }

  if (!networkReady) {
    if (client_.connected()) {
      client_.disconnect();
    }
    return;
  }

  if (!client_.connected()) {
    if (due(nowMs, reconnectAtMs_)) {
      connectOnce(nowMs);
    }
    return;
  }

  client_.loop();
  publishCompletions();
}

void MqttBridge::callbackThunk(char* topic, uint8_t* payload,
                               unsigned int length) {
  if (instance_ != nullptr) {
    instance_->onMessage(topic, payload, length);
  }
}

void MqttBridge::onMessage(const char* topic, const uint8_t* payload,
                           std::size_t length) {
  if (topic == nullptr || std::strcmp(topic, commandTopic_) != 0) {
    return;
  }

  JsonDocument document;
  const DeserializationError error = deserializeJson(document, payload, length);
  if (error || !document.is<JsonObject>()) {
    publishImmediateAck("invalid", 0, "invalid", "invalid_argument", 2);
    return;
  }

  const char* requestId = document["request_id"] | nullptr;
  const char* commandName = document["command"] | nullptr;
  if (requestId == nullptr || commandName == nullptr) {
    publishImmediateAck(requestId == nullptr ? "invalid" : requestId, 0,
                        commandName == nullptr ? "invalid" : commandName,
                        "invalid_argument", 2);
    return;
  }

  uint16_t existingSequence = 0;
  if (core_.findRequest(requestId, existingSequence)) {
    return;
  }

  uint16_t sequence = 0;
  if (!allocateSequence(sequence)) {
    publishImmediateAck(requestId, 0, commandName, "internal_error", 3);
    return;
  }

  bridge::Command command{};
  if (!buildAmlpCommand(document, sequence, command)) {
    publishImmediateAck(requestId, sequence, commandName, "invalid_argument", 2);
    return;
  }

  const bridge::EnqueueResult result = core_.enqueue(command);
  if (result == bridge::EnqueueResult::QueueFull) {
    publishImmediateAck(requestId, sequence, commandName, "internal_error", 3);
  } else if (result == bridge::EnqueueResult::Invalid) {
    publishImmediateAck(requestId, sequence, commandName, "invalid_argument", 2);
  }
}

void MqttBridge::connectOnce(uint32_t nowMs) {
  reconnectAtMs_ = nowMs + bridge_config::kMqttRetryMs;

  const bool hasUsername = username_ != nullptr && username_[0] != '\0';
  const bool connected =
      hasUsername
          ? client_.connect(deviceId_, username_,
                            password_ == nullptr ? "" : password_, statusTopic_,
                            1, true, kOfflinePayload)
          : client_.connect(deviceId_, statusTopic_, 1, true, kOfflinePayload);
  if (!connected) {
    return;
  }

  if (client_.subscribe(commandTopic_, 1)) {
    publishOnlineStatus();
  } else {
    client_.disconnect();
  }
}

bool MqttBridge::allocateSequence(uint16_t& sequence) {
  for (uint32_t attempt = 0; attempt <= UINT16_MAX; ++attempt) {
    const uint16_t candidate = nextSequence_++;
    if (!core_.sequenceInUse(candidate)) {
      sequence = candidate;
      return true;
    }
  }
  return false;
}

void MqttBridge::publishImmediateAck(const char* requestId, uint16_t sequence,
                                     const char* command, const char* status,
                                     int16_t statusCode) {
  JsonDocument document;
  document["request_id"] = requestId;
  document["sequence"] = sequence;
  document["command"] = command;
  document["status"] = status;
  document["status_code"] = statusCode;
  char buffer[256]{};
  serializeJson(document, buffer, sizeof(buffer));
  client_.publish(ackTopic_, buffer, false);
}

void MqttBridge::publishCompletions() {
  while (client_.connected()) {
    if (!completionPendingPublish_) {
      if (!core_.popCompletion(completionPending_)) {
        return;
      }
      completionPendingPublish_ = true;
    }

    if (!publishCompletion(completionPending_)) {
      return;
    }
    completionPendingPublish_ = false;
  }
}

bool MqttBridge::publishCompletion(const bridge::Completion& completion) {
  JsonDocument document;
  document["request_id"] = completion.command.requestId;
  document["sequence"] = completion.command.sequence;
  document["command"] = completion.command.commandName;
  if (completion.reason == bridge::CompletionReason::AttemptsExhausted) {
    document["status"] = "timeout";
    document["status_code"] = nullptr;
  } else {
    document["status"] = statusName(completion.statusCode);
    document["status_code"] = completion.statusCode;
  }

  char buffer[256]{};
  serializeJson(document, buffer, sizeof(buffer));
  return client_.publish(ackTopic_, buffer, false);
}

void MqttBridge::publishOnlineStatus() {
  JsonDocument document;
  document["online"] = true;
  document["protocol"] = "amlp/1";
  document["firmware"] = "0.1.0";
  char buffer[160]{};
  serializeJson(document, buffer, sizeof(buffer));
  client_.publish(statusTopic_, buffer, true);
}

bool MqttBridge::due(uint32_t nowMs, uint32_t deadlineMs) {
  return static_cast<int32_t>(nowMs - deadlineMs) >= 0;
}
