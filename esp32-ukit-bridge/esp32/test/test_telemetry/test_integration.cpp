// ---------------------------------------------------------------------------
// Integration tests — production decoder via feedBytes / dispatchFrame
// These call the actual UartAdapter::dispatchTelemetry() through
// feedBytes() and dispatchFrame(), verifying the real production code path.
// ---------------------------------------------------------------------------

#include <string>
#include <cstring>

#include <unity.h>

#include "amlp/amlp.hpp"
#include "bridge_core.h"
#include "telemetry_frame.h"
#include "uart_adapter.h"

// Minimal no-op BridgeCore for integration tests.
// feedBytes / dispatchFrame do not call BridgeCore methods for telemetry.
static bridge::BridgeCore kFakeCore{};

// Records the last frame dispatched to onTelemetry().
static bridge::TelemetryFrame kLastTelemetry{};
static bool kTelemetryCalled = false;

struct FakeTelemetryHandler final : public bridge::TelemetryHandler {
  void onTelemetry(const bridge::TelemetryFrame& frame) override {
    kLastTelemetry = frame;
    kTelemetryCalled = true;
  }
};

static void reset_telemetry_state(void) {
  kTelemetryCalled = false;
  kLastTelemetry = bridge::TelemetryFrame{};
}

// Encode a wire frame and return the bytes (same as in test_main.cpp).
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

void test_feed_bytes_dispatches_valid_tel_to_handler(void) {
  // TC1: Valid TEL frame produces exactly one onTelemetry call.
  reset_telemetry_state();
  FakeTelemetryHandler handler{};
  HardwareSerial serial(0);
  UartAdapter adapter(serial);

  const std::string wire = make_wire("TEL,CONVEYOR,RUNNING,60,SENSOR1=1");
  adapter.feedBytes(reinterpret_cast<const uint8_t*>(wire.data()),
                   wire.size(), 1000, kFakeCore, &handler);

  TEST_ASSERT_TRUE(kTelemetryCalled);
  TEST_ASSERT_EQUAL_UINT8(3, kLastTelemetry.num_values);
  TEST_ASSERT_EQUAL_UINT8(1, kLastTelemetry.num_pairs);
  TEST_ASSERT_EQUAL_STRING("CONVEYOR", kLastTelemetry.values[0].text);
  TEST_ASSERT_EQUAL_STRING("60", kLastTelemetry.values[2].text);
  TEST_ASSERT_EQUAL_STRING("SENSOR1", kLastTelemetry.pairs[0].key);
  TEST_ASSERT_EQUAL_STRING("1", kLastTelemetry.pairs[0].value);
}

void test_feed_bytes_rejects_corrupt_crc(void) {
  // TC2: Corrupted CRC produces no onTelemetry call.
  reset_telemetry_state();
  FakeTelemetryHandler handler{};
  HardwareSerial serial(0);
  UartAdapter adapter(serial);

  std::string wire = make_wire("TEL,CONVEYOR,RUNNING,60,SENSOR1=1");
  // Corrupt a CRC byte so the frame is rejected.
  const std::size_t star = wire.find('*');
  wire[star + 1] = (wire[star + 1] == 'A') ? 'B' : 'A';

  adapter.feedBytes(reinterpret_cast<const uint8_t*>(wire.data()),
                   wire.size(), 2000, kFakeCore, &handler);

  TEST_ASSERT_FALSE(kTelemetryCalled);
}

void test_dispatch_frame_with_nullptr_handler_does_not_crash(void) {
  // TC4: Null handler must not crash.
  HardwareSerial serial(0);
  UartAdapter adapter(serial);
  amlp::Frame frame{};
  frame.type = amlp::Type::Tel;
  TEST_ASSERT_TRUE(frame.set_field(0, "CONVEYOR"));
  TEST_ASSERT_TRUE(frame.set_field(1, "RUNNING"));
  // Pass nullptr — must not crash.
  adapter.dispatchFrame(frame, 3000, nullptr);
  TEST_ASSERT_FALSE(kTelemetryCalled);
}

void test_dispatch_frame_ignores_ack_frames(void) {
  // ACK frames must not be dispatched to the telemetry handler.
  reset_telemetry_state();
  FakeTelemetryHandler handler{};
  HardwareSerial serial(0);
  UartAdapter adapter(serial);

  amlp::Frame ack_frame{};
  ack_frame.type = amlp::Type::Ack;
  TEST_ASSERT_TRUE(ack_frame.set_field(0, "102"));
  TEST_ASSERT_TRUE(ack_frame.set_field(1, "OK"));

  adapter.dispatchFrame(ack_frame, 4000, &handler);
  TEST_ASSERT_FALSE(kTelemetryCalled);
}

void test_dispatch_frame_ignores_cmd_frames(void) {
  reset_telemetry_state();
  FakeTelemetryHandler handler{};
  HardwareSerial serial(0);
  UartAdapter adapter(serial);

  amlp::Frame cmd_frame{};
  cmd_frame.type = amlp::Type::Cmd;
  TEST_ASSERT_TRUE(cmd_frame.set_field(0, "42"));
  TEST_ASSERT_TRUE(cmd_frame.set_field(1, "PING"));

  adapter.dispatchFrame(cmd_frame, 5000, &handler);
  TEST_ASSERT_FALSE(kTelemetryCalled);
}

void test_multiple_tel_frames_all_dispatched(void) {
  // Multiple TEL frames each produce an onTelemetry call with correct data.
  reset_telemetry_state();
  FakeTelemetryHandler handler{};
  HardwareSerial serial(0);
  UartAdapter adapter(serial);

  const std::string wire1 = make_wire("TEL,SENSOR1,1");
  const std::string wire2 = make_wire("TEL,SENSOR2,0");

  adapter.feedBytes(reinterpret_cast<const uint8_t*>(wire1.data()),
                   wire1.size(), 6000, kFakeCore, &handler);
  TEST_ASSERT_TRUE(kTelemetryCalled);
  TEST_ASSERT_EQUAL_STRING("SENSOR1", kLastTelemetry.values[0].text);

  reset_telemetry_state();
  adapter.feedBytes(reinterpret_cast<const uint8_t*>(wire2.data()),
                   wire2.size(), 7000, kFakeCore, &handler);
  TEST_ASSERT_TRUE(kTelemetryCalled);
  TEST_ASSERT_EQUAL_STRING("SENSOR2", kLastTelemetry.values[0].text);
}

void test_dispatch_frame_timestamp_matches_input(void) {
  // received_at_ms must be the exact nowMs passed to dispatchFrame.
  reset_telemetry_state();
  FakeTelemetryHandler handler{};
  HardwareSerial serial(0);
  UartAdapter adapter(serial);

  amlp::Frame frame{};
  frame.type = amlp::Type::Tel;
  TEST_ASSERT_TRUE(frame.set_field(0, "CONVEYOR"));
  TEST_ASSERT_TRUE(frame.set_field(1, "IDLE"));

  adapter.dispatchFrame(frame, 0x12345678U, &handler);
  TEST_ASSERT_TRUE(kTelemetryCalled);
  TEST_ASSERT_EQUAL_UINT32(0x12345678U, kLastTelemetry.received_at_ms);
}

void test_feed_bytes_multiple_sensors_one_frame(void) {
  // TC1 variant: multiple SENSOR pairs in one frame.
  reset_telemetry_state();
  FakeTelemetryHandler handler{};
  HardwareSerial serial(0);
  UartAdapter adapter(serial);

  const std::string wire =
      make_wire("TEL,TEMP,25,HUMIDITY=65,SENSOR1=1,SENSOR2=0");
  adapter.feedBytes(reinterpret_cast<const uint8_t*>(wire.data()),
                   wire.size(), 8000, kFakeCore, &handler);

  TEST_ASSERT_TRUE(kTelemetryCalled);
  TEST_ASSERT_EQUAL_UINT8(2, kLastTelemetry.num_values);     // TEMP, 25
  TEST_ASSERT_EQUAL_UINT8(3, kLastTelemetry.num_pairs);   // HUMIDITY, SENSOR1, SENSOR2
  TEST_ASSERT_EQUAL_STRING("HUMIDITY", kLastTelemetry.pairs[0].key);
  TEST_ASSERT_EQUAL_STRING("65", kLastTelemetry.pairs[0].value);
  TEST_ASSERT_EQUAL_STRING("SENSOR1", kLastTelemetry.pairs[1].key);
  TEST_ASSERT_EQUAL_STRING("1", kLastTelemetry.pairs[1].value);
  TEST_ASSERT_EQUAL_STRING("SENSOR2", kLastTelemetry.pairs[2].key);
  TEST_ASSERT_EQUAL_STRING("0", kLastTelemetry.pairs[2].value);
}

void test_dispatch_telemetry_tracks_overflow_dropped_values(void) {
  // When a frame has more plain values than kMaxTelemetryValues (6),
  // dispatchTelemetry() must set overflow_dropped_values on the received frame.
  reset_telemetry_state();
  FakeTelemetryHandler handler{};
  HardwareSerial serial(0);
  UartAdapter adapter(serial);

  // Construct a frame with 8 plain value fields (exceeds kMaxTelemetryValues=6).
  amlp::Frame frame{};
  frame.type = amlp::Type::Tel;
  for (std::uint8_t i = 0; i < 8; ++i) {
    char val[8];
    std::snprintf(val, sizeof(val), "V%u", static_cast<unsigned int>(i));
    TEST_ASSERT_TRUE(frame.set_field(i, val));
  }

  adapter.dispatchFrame(frame, 9000, &handler);

  TEST_ASSERT_TRUE(kTelemetryCalled);
  // Only 6 values stored (kMaxTelemetryValues).
  TEST_ASSERT_EQUAL_UINT8(bridge::kMaxTelemetryValues, kLastTelemetry.num_values);
  // 2 extra values were silently dropped — overflow counter must be set.
  TEST_ASSERT_EQUAL_UINT8(2, kLastTelemetry.overflow_dropped_values);
  TEST_ASSERT_EQUAL_UINT8(0, kLastTelemetry.overflow_dropped_pairs);
}

void test_dispatch_telemetry_tracks_overflow_dropped_pairs(void) {
  // When a frame has more key=value pairs than kMaxTelemetryPairs (4),
  // dispatchTelemetry() must set overflow_dropped_pairs on the received frame.
  reset_telemetry_state();
  FakeTelemetryHandler handler{};
  HardwareSerial serial(0);
  UartAdapter adapter(serial);

  // Construct a frame with 6 key=value fields (exceeds kMaxTelemetryPairs=4).
  amlp::Frame frame{};
  frame.type = amlp::Type::Tel;
  for (std::uint8_t i = 0; i < 6; ++i) {
    char pair[16];
    std::snprintf(pair, sizeof(pair), "K%u=V%u",
                  static_cast<unsigned int>(i),
                  static_cast<unsigned int>(i));
    TEST_ASSERT_TRUE(frame.set_field(i, pair));
  }

  adapter.dispatchFrame(frame, 10000, &handler);

  TEST_ASSERT_TRUE(kTelemetryCalled);
  // Only 4 pairs stored (kMaxTelemetryPairs).
  TEST_ASSERT_EQUAL_UINT8(bridge::kMaxTelemetryPairs, kLastTelemetry.num_pairs);
  // 2 extra pairs were silently dropped — overflow counter must be set.
  TEST_ASSERT_EQUAL_UINT8(0, kLastTelemetry.overflow_dropped_values);
  TEST_ASSERT_EQUAL_UINT8(2, kLastTelemetry.overflow_dropped_pairs);
}

void test_dispatch_telemetry_no_overflow_when_within_limits(void) {
  // Within capacity limits, overflow counters must remain zero.
  reset_telemetry_state();
  FakeTelemetryHandler handler{};
  HardwareSerial serial(0);
  UartAdapter adapter(serial);

  amlp::Frame frame{};
  frame.type = amlp::Type::Tel;
  TEST_ASSERT_TRUE(frame.set_field(0, "STATUS"));
  TEST_ASSERT_TRUE(frame.set_field(1, "OK"));
  TEST_ASSERT_TRUE(frame.set_field(2, "A=1"));
  TEST_ASSERT_TRUE(frame.set_field(3, "B=2"));

  adapter.dispatchFrame(frame, 11000, &handler);

  TEST_ASSERT_TRUE(kTelemetryCalled);
  TEST_ASSERT_EQUAL_UINT8(0, kLastTelemetry.overflow_dropped_values);
  TEST_ASSERT_EQUAL_UINT8(0, kLastTelemetry.overflow_dropped_pairs);
}
