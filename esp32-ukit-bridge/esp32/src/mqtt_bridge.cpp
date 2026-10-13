#include "mqtt_bridge.h"

#include <ArduinoJson.h>

#include <algorithm>
#include <cstdio>
#include <cstring>

#include "amlp/amlp.hpp"
#include "bridge_config.h"
#include "command_mapper.h"
#include "json_adapter.h"

namespace {

constexpr char kOfflinePayload[] =
    "{\"online\":false,\"reason\":\"mqtt_disconnect\"}";

const char* mapperStatusName(bridge::CommandMapperResult::Code code) {
  switch (code) {
    case bridge::CommandMapperResult::kOk:
      return "queued";
    case bridge::CommandMapperResult::kUnknownCommand:
      return "unknown_command";
    case bridge::CommandMapperResult::kInvalidArgument:
      return "invalid_argument";
    case bridge::CommandMapperResult::kInternalError:
    default:
      return "internal_error";
  }
}

int16_t mapperStatusCode(bridge::CommandMapperResult::Code code) {
  switch (code) {
    case bridge::CommandMapperResult::kOk:
      return 0;
    case bridge::CommandMapperResult::kUnknownCommand:
      return 1;
    case bridge::CommandMapperResult::kInvalidArgument:
      return 2;
    case bridge::CommandMapperResult::kInternalError:
    default:
      return 3;
  }
}

bridge::CommandMapper g_mapper;

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

  // -------------------------------------------------------------------------
  // Canonical envelope: prefer integer command_id; fall back to request_id.
  // The incoming field name for the operation is command_name (schema canonical).
  // -------------------------------------------------------------------------
  char requestIdBuf[bridge::kMaxRequestIdLength + 1]{};
  const char* requestId = nullptr;

  if (document["command_id"].is<int64_t>()) {
    // Integer command_id (uint32) — convert to string.
    const int64_t idInt = document["command_id"].as<int64_t>();
    if (idInt > 0 && idInt <= 0xFFFFFFFFLL) {
      std::snprintf(requestIdBuf, sizeof(requestIdBuf), "%lld",
                     static_cast<long long>(idInt));
      requestId = requestIdBuf;
    }
  }

  if (requestId == nullptr) {
    // Fall back to string request_id. Reject if empty or exceeds max length
    // to prevent dedupe cache collisions from truncation.
    const char* fallback = document["request_id"] | nullptr;
    if (fallback != nullptr && fallback[0] != '\0' &&
        std::strlen(fallback) <= bridge::kMaxRequestIdLength) {
      std::strncpy(requestIdBuf, fallback, bridge::kMaxRequestIdLength);
      requestIdBuf[bridge::kMaxRequestIdLength] = '\0';
      requestId = requestIdBuf;
    }
  }

  const char* commandName = document["command_name"] | nullptr;
  if (requestId == nullptr || commandName == nullptr) {
    publishImmediateAck(requestId != nullptr ? requestId : "invalid", 0,
                        commandName != nullptr ? commandName : "invalid",
                        "invalid_argument", 2);
    return;
  }

  // Check deduplication before allocating a sequence.
  uint16_t existingSequence = 0;
  if (core_.findRequest(requestId, existingSequence)) {
    return;
  }

  uint16_t sequence = 0;
  if (!allocateSequence(sequence)) {
    publishImmediateAck(requestId, 0, commandName, "internal_error", 3);
    return;
  }

  // -----------------------------------------------------------------------
  // Extract arguments from the canonical arguments array.
  // Strictly require a JSON array — a non-array or absent "arguments" means
  // zero arguments for all commands (including SET_OUTPUT and CONVEYOR_START).
  // -----------------------------------------------------------------------
  unsigned int channel = 0;
  bool outputValue = false;
  bool channelParsed = false;
  bool valueParsed = false;
  int speedArg = -1;
  bool speedParsed = false;
  uint8_t argCount = 0;
  const char* arg0 = nullptr;
  const char* arg1 = nullptr;

  if (document["arguments"].is<JsonArray>()) {
    JsonArrayConst args = document["arguments"].as<JsonArrayConst>();
    if (args.size() > 2) {
      publishImmediateAck(requestId, 0, commandName, "invalid_argument", 2);
      return;
    }
    argCount = static_cast<uint8_t>(args.size());
    if (argCount >= 1) {
      arg0 = args[0].as<const char*>();
    }
    if (argCount >= 2) {
      arg1 = args[1].as<const char*>();
    }
  } else if (document["arguments"].is<JsonVariant>()) {
    // "arguments" is present but not an array — structural error.
    publishImmediateAck(requestId, 0, commandName, "invalid_argument", 2);
    return;
  }

  // Pre-parse SET_OUTPUT channel and value using the shared adapter helper
  // (tested in test_json_adapter/). The helper validates: arg0 is 0..255 decimal
  // digit-only; arg1 is "0" or "1". Track parse success explicitly — a failed
  // parse must NOT produce a valid command that falls through to the actuator.
  if (std::strcmp(commandName, "SET_OUTPUT") == 0) {
    if (bridge::parseSetOutputArgs(arg0, arg1)) {
      // Helper confirmed digit-only + range + value. Extract actual values.
      channel = static_cast<unsigned int>(std::strtoul(arg0, nullptr, 10));
      outputValue = (std::strcmp(arg1, "1") == 0);
      channelParsed = true;
      valueParsed = true;
    }
    // Fail-open guard: malformed channel or value → reject immediately.
    // Do NOT fall through with channel=0, value=false defaults.
    if (!channelParsed || !valueParsed) {
      publishImmediateAck(requestId, sequence, commandName,
                          "invalid_argument", 2);
      return;
    }
  }

  // Pre-parse CONVEYOR_START speed using the shared adapter helper
  // (tested in test_json_adapter/). The helper validates: arg0 is 1..100
  // decimal digit-only.
  if (std::strcmp(commandName, "CONVEYOR_START") == 0) {
    if (bridge::parseConveyorStartArg(arg0)) {
      speedArg = static_cast<int>(std::strtol(arg0, nullptr, 10));
      speedParsed = true;
    }
  }

  bridge::Command cmd{};
  bridge::CommandMapperResult result =
      g_mapper.build(commandName, requestId, sequence,
                     channel, outputValue, speedArg,
                     argCount, arg0, arg1, cmd);

  if (result.code != bridge::CommandMapperResult::kOk) {
    publishImmediateAck(requestId, sequence, commandName,
                        mapperStatusName(result.code),
                        mapperStatusCode(result.code));
    return;
  }

  const bridge::EnqueueResult enqResult = core_.enqueue(cmd);
  if (enqResult == bridge::EnqueueResult::QueueFull) {
    publishImmediateAck(requestId, sequence, commandName, "queue_full", 4);
  } else if (enqResult == bridge::EnqueueResult::Invalid) {
    publishImmediateAck(requestId, sequence, commandName, "invalid_argument", 2);
  }
  // On EnqueueResult::Accepted and EnqueueResult::Duplicate: silently swallow.
  // Accepted gets a completion ACK later; Duplicate is already deduped.
}

void MqttBridge::connectOnce(uint32_t nowMs) {
  reconnectAtMs_ = nowMs + bridge_config::kMqttRetryMs;

  // Fail-closed: refuse to connect if credentials are unprovisioned.
  // Remain disconnected and retry on the next tick.
  if (username_ == nullptr || username_[0] == '\0') {
    return;
  }

  const bool connected =
      client_.connect(deviceId_, username_,
                     password_ == nullptr ? "" : password_, statusTopic_,
                     1, true, kOfflinePayload);
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
    // Map MEGA ACK status code (0..3) to named string.
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

#if !defined(PLATFORMIO_NATIVE_TEST)
void MqttBridge::onTelemetry(const bridge::TelemetryFrame& frame) {
  if (!enabled_ || !client_.connected()) {
    ++telDropped_;  // Count drops from disabled or disconnected MQTT path.
    return;
  }
  publishTelemetry(frame);
}

void MqttBridge::publishTelemetry(const bridge::TelemetryFrame& frame) {
  if (telemetryTopic_[0] == '\0') {
    return;
  }

  // Delegate to the shared buildTelemetryPayload helper.  This is the single
  // canonical implementation; both production and native tests call the same
  // JSON-building logic (tests via bridge::publishTelemetry free function).
  char buffer[384]{};
  const std::size_t len = buildTelemetryPayload(frame, buffer);
  if (len == 0) {
    ++telDropped_;
    return;
  }

  // QoS 0: fire-and-forget. Do not block if the MQTT write buffer is full.
  const bool ok = client_.publish(telemetryTopic_, buffer, false);
  if (ok) {
    ++telPublished_;
  } else {
    ++telDropped_;
  }
}
#endif  // !PLATFORMIO_NATIVE_TEST

bool MqttBridge::due(uint32_t nowMs, uint32_t deadlineMs) {
  return static_cast<int32_t>(nowMs - deadlineMs) >= 0;
}
