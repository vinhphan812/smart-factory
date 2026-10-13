// ---------------------------------------------------------------------------
// Integration tests for MqttBridge telemetry publishing.
//
// Both production ESP32 and native tests call the same shared function:
//   bridge::publishTelemetry(frame, client, buffer, device_id,
//                            telemetry_topic, tel_dropped, tel_published)
//
// Tests verify the shared function directly using a FakePubSubClient.
// ---------------------------------------------------------------------------

#include <cstring>
#include <string>

#include <unity.h>

#include "amlp/amlp.hpp"
#include "bridge_core.h"
#include "mqtt_bridge.h"
#include "telemetry_frame.h"

// ---------------------------------------------------------------------------
// FakePubSubClient — captures published payloads and return value.
// ---------------------------------------------------------------------------

struct FakePubSubClient {
  bool connected() const { return connected_; }
  void setConnected(bool v) { connected_ = v; }

  // Simulates PubSubClient::publish(topic, payload, retained).
  // Stores a copy of payload for test assertions.
  bool publish(const char* topic, const char* payload, bool /*retained*/) {
    lastTopic_ = topic;
    lastPayload_.assign(payload, std::strlen(payload));
    lastPayloadSize_ = lastPayload_.size();
    return publishReturn_;
  }
  void setPublishReturn(bool v) { publishReturn_ = v; }

  const char* lastTopic_ = nullptr;
  std::string lastPayload_;
  std::size_t lastPayloadSize_ = 0;
  bool publishReturn_ = true;
  bool connected_ = true;
};

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

// Encode a wire frame (same as in test_main.cpp / test_integration.cpp).
static std::string make_wire(std::string_view body) {
  static constexpr char hex[] = "0123456789ABCDEF";
  const std::uint16_t crc = amlp::crc16_ccitt_false(body);
  std::string wire;
  wire.reserve(body.size() + 8);
  wire.push_back('@');
  wire.append(body.data(), body.size());
  wire.push_back('*');
  wire.push_back(hex[(crc >> 12U) & 0x0FU]);
  wire.push_back(hex[(crc >> 8U) & 0x0FU]);
  wire.push_back(hex[(crc >> 4U) & 0x0FU]);
  wire.push_back(hex[crc & 0x0FU]);
  wire.push_back('\r');
  wire.push_back('\n');
  return wire;
}

// ---------------------------------------------------------------------------
// Test cases
// ---------------------------------------------------------------------------

void test_publishTelemetry_rejects_oversize_json_exceeding_384_bytes(void) {
  // Build a TelemetryFrame whose serialised JSON exceeds 384 bytes.
  // TelemetryFrame caps at kMaxTelemetryValues=6 values and kMaxTelemetryPairs=4 pairs.
  // We use 6 values of 64 chars each to push the JSON over the 384-byte limit.
  bridge::TelemetryFrame frame{};
  frame.received_at_ms = 0;

  for (int i = 0; i < bridge::kMaxTelemetryValues; ++i) {
    std::memset(frame.values[i].text, 'A', 64);
    frame.values[i].text[64] = '\0';
    frame.values[i].length = 64;
    ++frame.num_values;
  }

  bridge::BridgeCore kDummyCore{};
  PubSubClient nullClient;
  MqttBridge bridgeObj(nullClient, kDummyCore, "localhost", 1883, "user",
                       "pass", "test-device");
  bridgeObj.begin();

  FakePubSubClient fake{};
  char buffer[384]{};
  std::uint32_t dropped = 0;
  std::uint32_t published = 0;
  const std::size_t result = bridge::publishTelemetry(
      frame, fake, buffer, bridgeObj.deviceId(),
      bridgeObj.telemetryTopic(), dropped, published);

  // Oversize payload: measureJson detected >384 bytes, dropped was incremented,
  // and publish was skipped (returns 0).
  TEST_ASSERT_EQUAL_UINT32(0, result);
  TEST_ASSERT_EQUAL_UINT32(1, dropped);
  TEST_ASSERT_EQUAL_UINT32(0, published);
  TEST_ASSERT_TRUE(fake.lastPayload_.empty());
}

void test_publishTelemetry_emits_truncated_flag_when_values_overflow(void) {
  bridge::TelemetryFrame frame{};
  frame.received_at_ms = 2000;
  frame.num_values = bridge::kMaxTelemetryValues;
  std::strncpy(frame.values[0].text, "V0",
               amlp::kMaxFieldLength);
  std::strncpy(frame.values[1].text, "V1",
               amlp::kMaxFieldLength);
  std::strncpy(frame.values[2].text, "V2",
               amlp::kMaxFieldLength);
  std::strncpy(frame.values[3].text, "V3",
               amlp::kMaxFieldLength);
  std::strncpy(frame.values[4].text, "V4",
               amlp::kMaxFieldLength);
  std::strncpy(frame.values[5].text, "V5",
               amlp::kMaxFieldLength);
  frame.overflow_dropped_values = 3;  // 3 extra values were dropped.

  bridge::BridgeCore kDummyCore{};
  PubSubClient nullClient;
  MqttBridge bridgeObj(nullClient, kDummyCore, "localhost", 1883, "user",
                       "pass", "overflow-test");
  bridgeObj.begin();

  FakePubSubClient fake{};
  char buffer[384]{};
  std::uint32_t dropped = 0;
  std::uint32_t published = 0;
  bridge::publishTelemetry(frame, fake, buffer, bridgeObj.deviceId(),
                           bridgeObj.telemetryTopic(), dropped, published);

  TEST_ASSERT_EQUAL_UINT32(1, published);
  TEST_ASSERT_EQUAL_UINT32(0, dropped);
  TEST_ASSERT_FALSE(fake.lastPayload_.empty());
  TEST_ASSERT_NOT_NULL(fake.lastTopic_);

  // Verify "truncated":true is in the payload.
  TEST_ASSERT_TRUE(fake.lastPayload_.find("\"truncated\":true") !=
                   std::string::npos);
  TEST_ASSERT_TRUE(fake.lastPayload_.find("\"overflow_dropped_values\":3") !=
                   std::string::npos);
  TEST_ASSERT_TRUE(fake.lastPayload_.find("\"overflow_dropped_pairs\":0") !=
                   std::string::npos);
}

void test_publishTelemetry_emits_truncated_flag_when_pairs_overflow(void) {
  bridge::TelemetryFrame frame{};
  frame.received_at_ms = 3000;
  frame.num_pairs = bridge::kMaxTelemetryPairs;
  frame.overflow_dropped_pairs = 2;  // 2 extra pairs were dropped.

  PubSubClient nullClient;
  bridge::BridgeCore kDummyCore{};
  MqttBridge bridgeObj(nullClient, kDummyCore, "localhost", 1883, "user",
                       "pass", "pair-overflow");
  bridgeObj.begin();

  FakePubSubClient fake{};
  char buffer[384]{};
  std::uint32_t dropped = 0;
  std::uint32_t published = 0;
  bridge::publishTelemetry(frame, fake, buffer, bridgeObj.deviceId(),
                           bridgeObj.telemetryTopic(), dropped, published);

  TEST_ASSERT_EQUAL_UINT32(1, published);
  TEST_ASSERT_EQUAL_UINT32(0, dropped);
  TEST_ASSERT_FALSE(fake.lastPayload_.empty());
  TEST_ASSERT_TRUE(fake.lastPayload_.find("\"truncated\":true") !=
                   std::string::npos);
  TEST_ASSERT_TRUE(fake.lastPayload_.find("\"overflow_dropped_pairs\":2") !=
                   std::string::npos);
}

void test_publishTelemetry_normal_frame_has_no_truncated_flag(void) {
  // A frame that fits within capacity must NOT have "truncated" in JSON.
  bridge::TelemetryFrame frame{};
  frame.received_at_ms = 4000;
  frame.num_values = 2;
  std::strncpy(frame.values[0].text, "TEMP",
               amlp::kMaxFieldLength);
  std::strncpy(frame.values[1].text, "25",
               amlp::kMaxFieldLength);
  frame.num_pairs = 1;
  std::strncpy(frame.pairs[0].key, "SENSOR1",
               bridge::kMaxTelemetryPairs);
  frame.pairs[0].key[bridge::kMaxTelemetryPairs] = '\0';
  std::strncpy(frame.pairs[0].value, "1",
               amlp::kMaxFieldLength + 4);
  // No overflow fields — truncated must be absent.

  PubSubClient nullClient;
  bridge::BridgeCore kDummyCore{};
  MqttBridge bridgeObj(nullClient, kDummyCore, "localhost", 1883, "user",
                       "pass", "normal-frame");
  bridgeObj.begin();

  FakePubSubClient fake{};
  char buffer[384]{};
  std::uint32_t dropped = 0;
  std::uint32_t published = 0;
  bridge::publishTelemetry(frame, fake, buffer, bridgeObj.deviceId(),
                           bridgeObj.telemetryTopic(), dropped, published);

  TEST_ASSERT_EQUAL_UINT32(1, published);
  TEST_ASSERT_EQUAL_UINT32(0, dropped);
  TEST_ASSERT_FALSE(fake.lastPayload_.empty());
  TEST_ASSERT_TRUE(fake.lastPayload_.find("\"truncated\"") ==
                   std::string::npos);
}

void test_onTelemetry_increments_telDropped_when_disabled(void) {
  // onTelemetry() must increment telDropped_ when MQTT is not enabled.
  PubSubClient nullClient;
  bridge::BridgeCore kDummyCore{};
  MqttBridge bridge(nullClient, kDummyCore, nullptr, 1883, "user",
                    "pass", nullptr);  // nullptr deviceId → not enabled
  bridge.begin();
  TEST_ASSERT_FALSE(bridge.enabled());

  bridge::TelemetryFrame frame{};
  frame.received_at_ms = 5000;
  frame.num_values = 1;
  std::strncpy(frame.values[0].text, "DATA",
               amlp::kMaxFieldLength);

  bridge.onTelemetry(frame);

  // Disabled path: telDropped_ must be incremented.
  TEST_ASSERT_EQUAL_UINT32(1, bridge.telDropped());
}

// ---------------------------------------------------------------------------
// Unity entry point (declarations in test_main.cpp)
// ---------------------------------------------------------------------------

void test_publishTelemetry_rejects_oversize_json_exceeding_384_bytes(void);
void test_publishTelemetry_emits_truncated_flag_when_values_overflow(void);
void test_publishTelemetry_emits_truncated_flag_when_pairs_overflow(void);
void test_publishTelemetry_normal_frame_has_no_truncated_flag(void);
void test_onTelemetry_increments_telDropped_when_disabled(void);
