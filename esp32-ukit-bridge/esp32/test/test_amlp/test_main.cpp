#include <unity.h>

#include <cstdint>
#include <string>
#include <string_view>

#include "amlp/amlp.hpp"

namespace {

std::string make_wire(std::string_view body, bool crlf = true) {
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
  if (crlf) {
    wire.push_back('\r');
  }
  wire.push_back('\n');
  return wire;
}

amlp::ParseResult feed_all(amlp::Parser& parser, std::string_view bytes,
                           amlp::Frame& frame, std::uint32_t start_ms = 0) {
  amlp::ParseResult result{};
  std::uint32_t now = start_ms;
  for (const char ch : bytes) {
    const amlp::ParseResult current =
        parser.feed(static_cast<std::uint8_t>(ch), now++, frame);
    if (current.status != amlp::ParseStatus::None) {
      result = current;
    }
  }
  return result;
}

void assert_parse_error(std::string_view wire, amlp::Error expected) {
  amlp::Parser parser;
  amlp::Frame frame;
  const amlp::ParseResult result = feed_all(parser, wire, frame);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::Error),
                        static_cast<int>(result.status));
  TEST_ASSERT_EQUAL_INT(static_cast<int>(expected),
                        static_cast<int>(result.error));
}

void test_crc_vectors() {
  TEST_ASSERT_EQUAL_HEX16(0xC942,
                          amlp::crc16_ccitt_false("CMD,102,CONVEYOR_START,60"));
  TEST_ASSERT_EQUAL_HEX16(0x22A0, amlp::crc16_ccitt_false("ACK,102,OK"));
  TEST_ASSERT_EQUAL_HEX16(
      0x0942,
      amlp::crc16_ccitt_false("TEL,CONVEYOR,RUNNING,60,SENSOR1=1"));
  TEST_ASSERT_EQUAL_HEX16(0x29B1,
                          amlp::crc16_ccitt_false("123456789"));
}

void test_encode_canonical_crlf() {
  // ---- CMD golden vector: CMD,102,CONVEYOR_START,60 -> C942 ----
  {
    amlp::Frame frame;
    frame.type = amlp::Type::Cmd;
    TEST_ASSERT_TRUE(frame.set_field(0, "102"));
    TEST_ASSERT_TRUE(frame.set_field(1, "CONVEYOR_START"));
    TEST_ASSERT_TRUE(frame.set_field(2, "60"));

    char output[amlp::kMaxFrameLength];
    std::size_t written = 0;
    TEST_ASSERT_EQUAL_INT(
        static_cast<int>(amlp::Error::None),
        static_cast<int>(amlp::encode(frame, output, sizeof(output), written)));
    TEST_ASSERT_EQUAL_STRING_LEN("@CMD,102,CONVEYOR_START,60*C942\r\n",
                                 output, written);
  }
  // ---- ACK golden vector: ACK,102,OK -> 22A0 ----
  {
    amlp::Frame frame;
    frame.type = amlp::Type::Ack;
    TEST_ASSERT_TRUE(frame.set_field(0, "102"));
    TEST_ASSERT_TRUE(frame.set_field(1, "OK"));

    char output[amlp::kMaxFrameLength];
    std::size_t written = 0;
    TEST_ASSERT_EQUAL_INT(
        static_cast<int>(amlp::Error::None),
        static_cast<int>(amlp::encode(frame, output, sizeof(output), written)));
    TEST_ASSERT_EQUAL_STRING_LEN("@ACK,102,OK*22A0\r\n", output, written);
  }
  // ---- TEL golden vector: TEL,CONVEYOR,RUNNING,60,SENSOR1=1 -> 0942 ----
  {
    amlp::Frame frame;
    frame.type = amlp::Type::Tel;
    TEST_ASSERT_TRUE(frame.set_field(0, "CONVEYOR"));
    TEST_ASSERT_TRUE(frame.set_field(1, "RUNNING"));
    TEST_ASSERT_TRUE(frame.set_field(2, "60"));
    TEST_ASSERT_TRUE(frame.set_field(3, "SENSOR1=1"));

    char output[amlp::kMaxFrameLength];
    std::size_t written = 0;
    TEST_ASSERT_EQUAL_INT(
        static_cast<int>(amlp::Error::None),
        static_cast<int>(amlp::encode(frame, output, sizeof(output), written)));
    TEST_ASSERT_EQUAL_STRING_LEN("@TEL,CONVEYOR,RUNNING,60,SENSOR1=1*0942\r\n",
                                 output, written);
  }
}

void test_decode_cmd_ack_tel() {
  const char* bodies[] = {"CMD,102,CONVEYOR_START,60", "ACK,102,OK",
                          "TEL,CONVEYOR,RUNNING,60,SENSOR1=1"};
  const amlp::Type types[] = {amlp::Type::Cmd, amlp::Type::Ack,
                              amlp::Type::Tel};
  const std::uint8_t field_counts[] = {3, 2, 4};

  for (std::size_t index = 0; index < 3; ++index) {
    amlp::Parser parser;
    amlp::Frame frame;
    const std::string wire = make_wire(bodies[index]);
    const amlp::ParseResult result = feed_all(parser, wire, frame);
    TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::FrameReady),
                          static_cast<int>(result.status));
    TEST_ASSERT_EQUAL_INT(static_cast<int>(types[index]),
                          static_cast<int>(frame.type));
    TEST_ASSERT_EQUAL_UINT8(field_counts[index], frame.field_count);
  }
}

void test_decode_accepts_lf_only() {
  amlp::Parser parser;
  amlp::Frame frame;
  const std::string wire = make_wire("ACK,102,OK", false);
  const amlp::ParseResult result = feed_all(parser, wire, frame);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::FrameReady),
                        static_cast<int>(result.status));
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::Type::Ack),
                        static_cast<int>(frame.type));
  TEST_ASSERT_EQUAL_STRING_LEN("102", frame.field(0).data(),
                               frame.field(0).size());
  TEST_ASSERT_EQUAL_STRING_LEN("OK", frame.field(1).data(),
                               frame.field(1).size());
}

void test_malformed_crc_is_rejected() {
  assert_parse_error("@CMD,102,CONVEYOR_START,60*C943\r\n", amlp::Error::InvalidCrc);
}

void test_lowercase_crc_is_rejected() {
  assert_parse_error("@CMD,102,CONVEYOR_START,60*c942\r\n", amlp::Error::InvalidFormat);
}

void test_empty_field_is_rejected() {
  const std::string wire = make_wire("CMD,,PING");
  assert_parse_error(wire, amlp::Error::InvalidFormat);
}

void test_unknown_type_is_rejected() {
  const std::string wire = make_wire("REQ,1,PING");
  assert_parse_error(wire, amlp::Error::UnsupportedType);
}

void test_invalid_character_is_rejected() {
  const std::string wire = make_wire(std::string("TEL,TEMP,") + '\t');
  assert_parse_error(wire, amlp::Error::InvalidCharacter);
}

void test_timeout_at_250_ms() {
  amlp::Parser parser;
  amlp::Frame frame;
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(amlp::ParseStatus::None),
      static_cast<int>(parser.feed('@', 1000, frame).status));
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(amlp::ParseStatus::None),
      static_cast<int>(parser.feed('C', 1001, frame).status));

  const amlp::ParseResult result = parser.check_timeout(1251);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::Error),
                        static_cast<int>(result.status));
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::Error::Timeout),
                        static_cast<int>(result.error));
  TEST_ASSERT_FALSE(parser.active());
}

void test_resync_on_new_start_marker() {
  amlp::Parser parser;
  amlp::Frame frame;
  (void)feed_all(parser, "noise@CMD,broken", frame);

  const std::string valid = make_wire("ACK,102,OK");
  const amlp::ParseResult result = feed_all(parser, valid, frame, 20);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::FrameReady),
                        static_cast<int>(result.status));
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::Type::Ack),
                        static_cast<int>(frame.type));
  TEST_ASSERT_EQUAL_STRING_LEN("102", frame.field(0).data(),
                               frame.field(0).size());
}

void test_field_length_boundaries() {
  const std::string field64(amlp::kMaxFieldLength, 'A');
  const std::string field65(amlp::kMaxFieldLength + 1U, 'A');

  amlp::Parser parser;
  amlp::Frame frame;
  amlp::ParseResult result = feed_all(parser, make_wire("TEL," + field64), frame);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::FrameReady),
                        static_cast<int>(result.status));
  TEST_ASSERT_EQUAL_UINT(amlp::kMaxFieldLength, frame.field(0).size());

  assert_parse_error(make_wire("TEL," + field65), amlp::Error::FieldTooLong);
}

void test_field_count_boundary() {
  std::string valid = "TEL";
  for (std::size_t index = 0; index < amlp::kMaxPayloadFields; ++index) {
    valid += ",X";
  }
  amlp::Parser parser;
  amlp::Frame frame;
  amlp::ParseResult result = feed_all(parser, make_wire(valid), frame);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::FrameReady),
                        static_cast<int>(result.status));
  TEST_ASSERT_EQUAL_UINT8(amlp::kMaxPayloadFields, frame.field_count);

  assert_parse_error(make_wire(valid + ",X"), amlp::Error::TooManyFields);
}

void test_frame_length_bound_is_enforced() {
  amlp::Parser parser;
  amlp::Frame frame;
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(amlp::ParseStatus::None),
      static_cast<int>(parser.feed('@', 0, frame).status));

  amlp::ParseResult result{};
  for (std::size_t index = 0; index < amlp::kMaxFrameLength; ++index) {
    result = parser.feed('A', static_cast<std::uint32_t>(index + 1U), frame);
    if (result.status == amlp::ParseStatus::Error) {
      break;
    }
  }
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::Error),
                        static_cast<int>(result.status));
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::Error::FrameTooLong),
                        static_cast<int>(result.error));
}

void test_exact_256_byte_frame_boundary() {
  amlp::Frame frame;
  frame.type = amlp::Type::Tel;
  const std::string field64(64, 'A');
  const std::string field49(49, 'B');
  TEST_ASSERT_TRUE(frame.set_field(0, field64));
  TEST_ASSERT_TRUE(frame.set_field(1, field64));
  TEST_ASSERT_TRUE(frame.set_field(2, field64));
  TEST_ASSERT_TRUE(frame.set_field(3, field49));

  char output[amlp::kMaxFrameLength];
  std::size_t written = 0;
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(amlp::Error::None),
      static_cast<int>(amlp::encode(frame, output, sizeof(output), written)));
  TEST_ASSERT_EQUAL_UINT(amlp::kMaxFrameLength, written);

  amlp::Parser parser;
  amlp::Frame decoded;
  const amlp::ParseResult result =
      feed_all(parser, std::string_view(output, written), decoded);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(amlp::ParseStatus::FrameReady),
                        static_cast<int>(result.status));
  TEST_ASSERT_EQUAL_UINT8(4, decoded.field_count);

  TEST_ASSERT_TRUE(frame.set_field(3, std::string(50, 'B')));
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(amlp::Error::FrameTooLong),
      static_cast<int>(amlp::encode(frame, output, sizeof(output), written)));
}

void test_encode_rejects_small_buffer_and_oversized_frame() {
  amlp::Frame frame;
  frame.type = amlp::Type::Tel;
  TEST_ASSERT_TRUE(frame.set_field(0, "TEMP"));
  TEST_ASSERT_TRUE(frame.set_field(1, "1294"));

  char small[8];
  std::size_t written = 99;
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(amlp::Error::BufferTooSmall),
      static_cast<int>(amlp::encode(frame, small, sizeof(small), written)));
  TEST_ASSERT_EQUAL_UINT(0, written);

  amlp::Frame oversized;
  oversized.type = amlp::Type::Tel;
  const std::string field64(amlp::kMaxFieldLength, 'B');
  for (std::size_t index = 0; index < 4; ++index) {
    TEST_ASSERT_TRUE(oversized.set_field(index, field64));
  }
  char output[amlp::kMaxFrameLength];
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(amlp::Error::FrameTooLong),
      static_cast<int>(amlp::encode(oversized, output, sizeof(output), written)));
}

void run_tests() {
  RUN_TEST(test_crc_vectors);
  RUN_TEST(test_encode_canonical_crlf);
  RUN_TEST(test_decode_cmd_ack_tel);
  RUN_TEST(test_decode_accepts_lf_only);
  RUN_TEST(test_malformed_crc_is_rejected);
  RUN_TEST(test_lowercase_crc_is_rejected);
  RUN_TEST(test_empty_field_is_rejected);
  RUN_TEST(test_unknown_type_is_rejected);
  RUN_TEST(test_invalid_character_is_rejected);
  RUN_TEST(test_timeout_at_250_ms);
  RUN_TEST(test_resync_on_new_start_marker);
  RUN_TEST(test_field_length_boundaries);
  RUN_TEST(test_field_count_boundary);
  RUN_TEST(test_frame_length_bound_is_enforced);
  RUN_TEST(test_exact_256_byte_frame_boundary);
  RUN_TEST(test_encode_rejects_small_buffer_and_oversized_frame);
}

}  // namespace

void setUp() {}
void tearDown() {}

#ifdef ARDUINO
void setup() {
  UNITY_BEGIN();
  run_tests();
  UNITY_END();
}
void loop() {}
#else
int main(int, char**) {
  UNITY_BEGIN();
  run_tests();
  return UNITY_END();
}
#endif
