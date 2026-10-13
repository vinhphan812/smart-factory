#include <unity.h>

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <string_view>

#include "amlp/amlp.hpp"
#include "telemetry_frame.h"

// ---------------------------------------------------------------------------
// Integration test declarations — implemented in test_integration.cpp
// ---------------------------------------------------------------------------

void test_feed_bytes_dispatches_valid_tel_to_handler(void);
void test_feed_bytes_rejects_corrupt_crc(void);
void test_dispatch_frame_with_nullptr_handler_does_not_crash(void);
void test_dispatch_frame_ignores_ack_frames(void);
void test_dispatch_frame_ignores_cmd_frames(void);
void test_multiple_tel_frames_all_dispatched(void);
void test_dispatch_frame_timestamp_matches_input(void);
void test_feed_bytes_multiple_sensors_one_frame(void);
void test_dispatch_telemetry_tracks_overflow_dropped_values(void);
void test_dispatch_telemetry_tracks_overflow_dropped_pairs(void);
void test_dispatch_telemetry_no_overflow_when_within_limits(void);

// MqttBridge telemetry tests (test_mqtt_bridge_telemetry.cpp)
void test_publishTelemetry_rejects_oversize_json_exceeding_384_bytes(void);
void test_publishTelemetry_emits_truncated_flag_when_values_overflow(void);
void test_publishTelemetry_emits_truncated_flag_when_pairs_overflow(void);
void test_publishTelemetry_normal_frame_has_no_truncated_flag(void);
void test_onTelemetry_increments_telDropped_when_disabled(void);

namespace {

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Encode a wire frame and return the bytes.
std::string make_wire(std::string_view body) {
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

// Feed every byte of `wire` into `parser` and return the resulting frame.
amlp::ParseResult feed_all(amlp::Parser& parser, const std::string& wire,
                           amlp::Frame& frame, std::uint32_t start_ms = 0) {
  amlp::ParseResult result{};
  std::uint32_t now = start_ms;
  for (char ch : wire) {
    const amlp::ParseResult current =
        parser.feed(static_cast<std::uint8_t>(ch), now++, frame);
    if (current.status != amlp::ParseStatus::None) {
      result = current;
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// TelemetryFrame field parsing (simulates what UartAdapter::handleFrame does)
// ---------------------------------------------------------------------------

// Replicates the key=value and plain-value parsing from uart_adapter.cpp.
void parseTelemetryFrame(const amlp::Frame& frame, uint32_t nowMs,
                        bridge::TelemetryFrame& out) {
  out.received_at_ms = nowMs;

  for (std::uint8_t i = 0; i < frame.field_count; ++i) {
    const std::string_view field = frame.field(i);
    if (field.empty()) continue;

    // Find '=' for key=value detection.
    std::size_t eq = std::string_view::npos;
    for (std::size_t j = 0; j < field.size(); ++j) {
      if (field[j] == '=') {
        eq = j;
        break;
      }
    }

    if (eq != std::string_view::npos) {
      if (out.num_pairs < bridge::kMaxTelemetryPairs) {
        auto& pair = out.pairs[out.num_pairs];
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
        ++out.num_pairs;
      } else {
        ++out.overflow_dropped_pairs;
      }
    } else {
      if (out.num_values < bridge::kMaxTelemetryValues) {
        auto& val = out.values[out.num_values];
        const std::size_t copyLen =
            (field.size() < amlp::kMaxFieldLength) ? field.size()
                                                    : amlp::kMaxFieldLength;
        std::memcpy(val.text, field.data(), copyLen);
        val.text[copyLen] = '\0';
        val.length = static_cast<std::uint8_t>(copyLen);
        ++out.num_values;
      } else {
        ++out.overflow_dropped_values;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Test cases
// ---------------------------------------------------------------------------

void test_valid_tel_frame_produces_correct_fields(void) {
  // @TEL,CONVEYOR,RUNNING,60,SENSOR1=1*....\r\n
  amlp::Parser parser;
  amlp::Frame frame;
  const std::string wire = make_wire("TEL,CONVEYOR,RUNNING,60,SENSOR1=1");
  const amlp::ParseResult result = feed_all(parser, wire, frame);

  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::FrameReady),
                        static_cast<int>(result.status));
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::Type::Tel),
                        static_cast<int>(frame.type));

  bridge::TelemetryFrame tel{};
  parseTelemetryFrame(frame, 1000, tel);

  TEST_ASSERT_EQUAL_UINT32(1000, tel.received_at_ms);
  // Fields: CONVEYOR, RUNNING, 60, SENSOR1=1  (4 fields)
  TEST_ASSERT_EQUAL_UINT8(3, tel.num_values);   // CONVEYOR, RUNNING, 60
  TEST_ASSERT_EQUAL_UINT8(1, tel.num_pairs);    // SENSOR1=1

  TEST_ASSERT_EQUAL_STRING("CONVEYOR", tel.values[0].text);
  TEST_ASSERT_EQUAL_STRING("RUNNING", tel.values[1].text);
  TEST_ASSERT_EQUAL_STRING("60", tel.values[2].text);

  TEST_ASSERT_EQUAL_STRING("SENSOR1", tel.pairs[0].key);
  TEST_ASSERT_EQUAL_STRING("1", tel.pairs[0].value);

  TEST_ASSERT_TRUE(tel.has_data());
}

void test_tel_frame_with_multiple_pairs(void) {
  // @TEL,TEMP,22,HUMIDITY=65,SENSOR2=0*....\r\n
  amlp::Parser parser;
  amlp::Frame frame;
  const std::string wire = make_wire("TEL,TEMP,22,HUMIDITY=65,SENSOR2=0");
  feed_all(parser, wire, frame);

  bridge::TelemetryFrame tel{};
  parseTelemetryFrame(frame, 500, tel);

  TEST_ASSERT_EQUAL_UINT8(2, tel.num_values);    // TEMP, 22
  TEST_ASSERT_EQUAL_UINT8(2, tel.num_pairs);     // HUMIDITY=65, SENSOR2=0

  TEST_ASSERT_EQUAL_STRING("TEMP", tel.values[0].text);
  TEST_ASSERT_EQUAL_STRING("22", tel.values[1].text);
  TEST_ASSERT_EQUAL_STRING("HUMIDITY", tel.pairs[0].key);
  TEST_ASSERT_EQUAL_STRING("65", tel.pairs[0].value);
  TEST_ASSERT_EQUAL_STRING("SENSOR2", tel.pairs[1].key);
  TEST_ASSERT_EQUAL_STRING("0", tel.pairs[1].value);
}

void test_tel_frame_with_only_plain_values(void) {
  // @TEL,MOTOR,75,42,100*....\r\n
  amlp::Parser parser;
  amlp::Frame frame;
  const std::string wire = make_wire("TEL,MOTOR,75,42,100");
  feed_all(parser, wire, frame);

  bridge::TelemetryFrame tel{};
  parseTelemetryFrame(frame, 2000, tel);

  TEST_ASSERT_EQUAL_UINT8(4, tel.num_values);
  TEST_ASSERT_EQUAL_UINT8(0, tel.num_pairs);

  TEST_ASSERT_EQUAL_STRING("MOTOR", tel.values[0].text);
  TEST_ASSERT_EQUAL_STRING("75", tel.values[1].text);
  TEST_ASSERT_EQUAL_STRING("42", tel.values[2].text);
  TEST_ASSERT_EQUAL_STRING("100", tel.values[3].text);
}

void test_tel_frame_empty_is_rejected(void) {
  bridge::TelemetryFrame tel{};
  TEST_ASSERT_FALSE(tel.has_data());
}

void test_tel_frame_truncates_at_max_values(void) {
  // Create a frame with more values than kMaxTelemetryValues (6).
  amlp::Parser parser;
  amlp::Frame frame;
  frame.type = amlp::Type::Tel;
  // 8 fields — more than kMaxTelemetryValues (6)
  TEST_ASSERT_TRUE(frame.set_field(0, "A"));
  TEST_ASSERT_TRUE(frame.set_field(1, "B"));
  TEST_ASSERT_TRUE(frame.set_field(2, "C"));
  TEST_ASSERT_TRUE(frame.set_field(3, "D"));
  TEST_ASSERT_TRUE(frame.set_field(4, "E"));
  TEST_ASSERT_TRUE(frame.set_field(5, "F"));
  TEST_ASSERT_TRUE(frame.set_field(6, "G"));
  TEST_ASSERT_TRUE(frame.set_field(7, "H"));

  bridge::TelemetryFrame tel{};
  parseTelemetryFrame(frame, 0, tel);

  // Only 6 values stored.
  TEST_ASSERT_EQUAL_UINT8(bridge::kMaxTelemetryValues, tel.num_values);
  TEST_ASSERT_EQUAL_STRING("A", tel.values[0].text);
  TEST_ASSERT_EQUAL_STRING("F", tel.values[5].text);
  // G and H were truncated — overflow counter must be set.
  TEST_ASSERT_EQUAL_UINT8(2, tel.overflow_dropped_values);
  TEST_ASSERT_EQUAL_UINT8(0, tel.overflow_dropped_pairs);
}

void test_tel_frame_truncates_at_max_pairs(void) {
  amlp::Frame frame;
  frame.type = amlp::Type::Tel;
  // Set 6 key=value fields.
  for (std::uint8_t i = 0; i < 6; ++i) {
    char key[8];
    char val[8];
    std::snprintf(key, sizeof(key), "K%u", static_cast<unsigned int>(i));
    std::snprintf(val, sizeof(val), "V%u", static_cast<unsigned int>(i));
    char pair[16];
    std::snprintf(pair, sizeof(pair), "%s=%s", key, val);
    TEST_ASSERT_TRUE(frame.set_field(i, pair));
  }

  bridge::TelemetryFrame tel{};
  parseTelemetryFrame(frame, 0, tel);

  TEST_ASSERT_EQUAL_UINT8(bridge::kMaxTelemetryPairs, tel.num_pairs);
  TEST_ASSERT_EQUAL_STRING("K0", tel.pairs[0].key);
  TEST_ASSERT_EQUAL_STRING("K3", tel.pairs[3].key);
  // kMaxTelemetryPairs = 4: only first 4 pairs stored (indices 0-3).
  // K4 and K5 were truncated — overflow counter must be set.
  TEST_ASSERT_EQUAL_UINT8(0, tel.overflow_dropped_values);
  TEST_ASSERT_EQUAL_UINT8(2, tel.overflow_dropped_pairs);
}

void test_tel_frame_with_mixed_values_and_pairs(void) {
  // @TEL,STATUS,OK,TEMP=25,PRESSURE=1013*....\r\n
  amlp::Parser parser;
  amlp::Frame frame;
  const std::string wire = make_wire("TEL,STATUS,OK,TEMP=25,PRESSURE=1013");
  feed_all(parser, wire, frame);

  bridge::TelemetryFrame tel{};
  parseTelemetryFrame(frame, 42, tel);

  TEST_ASSERT_EQUAL_UINT32(42, tel.received_at_ms);
  TEST_ASSERT_EQUAL_UINT8(2, tel.num_values);    // STATUS, OK
  TEST_ASSERT_EQUAL_UINT8(2, tel.num_pairs);     // TEMP=25, PRESSURE=1013

  TEST_ASSERT_EQUAL_STRING("STATUS", tel.values[0].text);
  TEST_ASSERT_EQUAL_STRING("OK", tel.values[1].text);
  TEST_ASSERT_EQUAL_STRING("TEMP", tel.pairs[0].key);
  TEST_ASSERT_EQUAL_STRING("25", tel.pairs[0].value);
  TEST_ASSERT_EQUAL_STRING("PRESSURE", tel.pairs[1].key);
  TEST_ASSERT_EQUAL_STRING("1013", tel.pairs[1].value);
}

void test_crc_error_frame_not_parsed(void) {
  // Valid TEL frame but with a wrong CRC byte at the end.
  amlp::Parser parser;
  amlp::Frame frame;
  const std::string wire = make_wire("TEL,CONVEYOR,RUNNING,60,SENSOR1=1");
  // Corrupt the last hex digit of the CRC.
  std::string bad_wire = wire;
  const std::size_t crc_start = wire.find('*') + 1;
  if (crc_start < bad_wire.size()) {
    char& last = bad_wire[crc_start + 3];   // last hex digit
    last = (last == '1') ? '2' : '1';
  }

  amlp::ParseResult result = feed_all(parser, bad_wire, frame);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::Error),
                        static_cast<int>(result.status));
}

void test_ack_frame_not_treated_as_telemetry(void) {
  // ACK frames are parsed as plain values (no ='=' sign) so has_data() returns
  // true.  The firmware distinguishes frame type - only Type::Tel is dispatched.
  amlp::Parser parser;
  amlp::Frame frame;
  const std::string wire = make_wire("ACK,102,OK");
  feed_all(parser, wire, frame);

  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::Type::Ack),
                        static_cast<int>(frame.type));
  // The firmware checks frame.type before calling onTelemetry - ACK is never
  // dispatched to MQTT telemetry.
  TEST_ASSERT_FALSE(frame.type == amlp::Type::Tel);
}

void test_tel_frame_received_timestamp_recorded(void) {
  amlp::Parser parser;
  amlp::Frame frame;
  const std::string wire = make_wire("TEL,SENSOR,123");
  feed_all(parser, wire, frame);

  bridge::TelemetryFrame tel{};
  parseTelemetryFrame(frame, 0xDEADBEEFU, tel);
  TEST_ASSERT_EQUAL_UINT32(0xDEADBEEFU, tel.received_at_ms);
}

void test_empty_tel_field_skipped(void) {
  // The AMLP parser rejects empty fields (validate_field returns Error::InvalidFormat),
  // so set_field returns false for empty strings.  parseTelemetryFrame guards with
  // if (field.empty()) continue; - verify this correctly skips empty strings.
  amlp::Frame frame;
  frame.type = amlp::Type::Tel;
  // set_field returns false for empty - verify AMLP spec compliance.
  TEST_ASSERT_FALSE(frame.set_field(0, ""));
  // Valid non-empty fields work.
  TEST_ASSERT_TRUE(frame.set_field(0, "CONVEYOR"));
  TEST_ASSERT_TRUE(frame.set_field(1, "IDLE"));

  bridge::TelemetryFrame tel{};
  parseTelemetryFrame(frame, 0, tel);
  TEST_ASSERT_EQUAL_UINT8(2, tel.num_values);
  TEST_ASSERT_EQUAL_STRING("CONVEYOR", tel.values[0].text);
  TEST_ASSERT_EQUAL_STRING("IDLE", tel.values[1].text);
}

void test_tel_frame_key_value_with_long_value(void) {
  // Key=value where value fills the 64-char field limit exactly.
  // KEY= is 4 chars, so value is 60 chars of X to reach exactly 64 total.
  amlp::Frame frame;
  frame.type = amlp::Type::Tel;
  std::string long_val(amlp::kMaxFieldLength - 4, 'X');  // 60 Xs -> total 64
  char pair[128];
  std::snprintf(pair, sizeof(pair), "KEY=%s", long_val.c_str());
  TEST_ASSERT_TRUE(frame.set_field(0, pair));

  bridge::TelemetryFrame tel{};
  parseTelemetryFrame(frame, 0, tel);

  TEST_ASSERT_EQUAL_UINT8(1, tel.num_pairs);
  TEST_ASSERT_EQUAL_STRING("KEY", tel.pairs[0].key);
  TEST_ASSERT_EQUAL_UINT(amlp::kMaxFieldLength - 4,
                         std::strlen(tel.pairs[0].value));
}

}  // namespace

void setUp() {}
void tearDown() {}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_valid_tel_frame_produces_correct_fields);
  RUN_TEST(test_tel_frame_with_multiple_pairs);
  RUN_TEST(test_tel_frame_with_only_plain_values);
  RUN_TEST(test_tel_frame_empty_is_rejected);
  RUN_TEST(test_tel_frame_truncates_at_max_values);
  RUN_TEST(test_tel_frame_truncates_at_max_pairs);
  RUN_TEST(test_tel_frame_with_mixed_values_and_pairs);
  RUN_TEST(test_crc_error_frame_not_parsed);
  RUN_TEST(test_ack_frame_not_treated_as_telemetry);
  RUN_TEST(test_tel_frame_received_timestamp_recorded);
  RUN_TEST(test_empty_tel_field_skipped);
  RUN_TEST(test_tel_frame_key_value_with_long_value);
  // Integration tests — production decoder via feedBytes / dispatchFrame
  RUN_TEST(test_feed_bytes_dispatches_valid_tel_to_handler);
  RUN_TEST(test_feed_bytes_rejects_corrupt_crc);
  RUN_TEST(test_dispatch_frame_with_nullptr_handler_does_not_crash);
  RUN_TEST(test_dispatch_frame_ignores_ack_frames);
  RUN_TEST(test_dispatch_frame_ignores_cmd_frames);
  RUN_TEST(test_multiple_tel_frames_all_dispatched);
  RUN_TEST(test_dispatch_frame_timestamp_matches_input);
  RUN_TEST(test_feed_bytes_multiple_sensors_one_frame);
  RUN_TEST(test_dispatch_telemetry_tracks_overflow_dropped_values);
  RUN_TEST(test_dispatch_telemetry_tracks_overflow_dropped_pairs);
  RUN_TEST(test_dispatch_telemetry_no_overflow_when_within_limits);
  // MqttBridge telemetry tests
  RUN_TEST(test_publishTelemetry_rejects_oversize_json_exceeding_384_bytes);
  RUN_TEST(test_publishTelemetry_emits_truncated_flag_when_values_overflow);
  RUN_TEST(test_publishTelemetry_emits_truncated_flag_when_pairs_overflow);
  RUN_TEST(test_publishTelemetry_normal_frame_has_no_truncated_flag);
  RUN_TEST(test_onTelemetry_increments_telDropped_when_disabled);
  return UNITY_END();
}
