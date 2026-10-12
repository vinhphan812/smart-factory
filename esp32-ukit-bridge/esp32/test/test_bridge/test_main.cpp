#include <unity.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "bridge_core.h"

namespace {

class FakeTransport final : public bridge::Transport {
 public:
  bool send(const uint8_t* data, std::size_t length) override {
    ++sendCount;
    lastLength = length;
    firstByte = length > 0 ? data[0] : 0;
    return result;
  }

  bool result = true;
  unsigned int sendCount = 0;
  std::size_t lastLength = 0;
  uint8_t firstByte = 0;
};

bridge::Command makeCommand(uint16_t sequence, const char* requestId = nullptr,
                            uint8_t value = 0x42) {
  bridge::Command command{};
  command.sequence = sequence;
  if (requestId == nullptr) {
    std::snprintf(command.requestId, sizeof(command.requestId), "request-%u",
                  static_cast<unsigned int>(sequence));
  } else {
    std::strncpy(command.requestId, requestId, sizeof(command.requestId) - 1);
  }
  std::strncpy(command.commandName, "ping", sizeof(command.commandName) - 1);
  command.payloadLength = 1;
  command.payload[0] = value;
  return command;
}

void test_rejects_invalid_and_bounds_queue() {
  bridge::BridgeCore core;
  bridge::Command invalid{};
  TEST_ASSERT_EQUAL_INT(static_cast<int>(bridge::EnqueueResult::Invalid),
                        static_cast<int>(core.enqueue(invalid)));

  for (uint16_t sequence = 1; sequence <= bridge::kCommandQueueCapacity;
       ++sequence) {
    TEST_ASSERT_EQUAL_INT(
        static_cast<int>(bridge::EnqueueResult::Accepted),
        static_cast<int>(core.enqueue(makeCommand(sequence))));
  }
  TEST_ASSERT_EQUAL_size_t(bridge::kCommandQueueCapacity, core.queuedCount());
  TEST_ASSERT_EQUAL_INT(static_cast<int>(bridge::EnqueueResult::QueueFull),
                        static_cast<int>(core.enqueue(makeCommand(99))));
}

void test_deduplicates_request_id_in_queue_pending_and_recent_cache() {
  bridge::BridgeCore core;
  FakeTransport transport;
  const bridge::Command command = makeCommand(77, "req-77");

  TEST_ASSERT_EQUAL_INT(static_cast<int>(bridge::EnqueueResult::Accepted),
                        static_cast<int>(core.enqueue(command)));
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(bridge::EnqueueResult::Duplicate),
      static_cast<int>(core.enqueue(makeCommand(78, "req-77"))));

  core.tick(0, transport);
  TEST_ASSERT_TRUE(core.hasPending());
  uint16_t existingSequence = 0;
  TEST_ASSERT_TRUE(core.findRequest("req-77", existingSequence));
  TEST_ASSERT_EQUAL_UINT16(77, existingSequence);

  TEST_ASSERT_TRUE(core.acknowledge(77));
  TEST_ASSERT_TRUE(core.findRequest("req-77", existingSequence));
  TEST_ASSERT_EQUAL_UINT16(77, existingSequence);
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(bridge::EnqueueResult::Duplicate),
      static_cast<int>(core.enqueue(makeCommand(79, "req-77"))));
}

void test_correlates_ack_and_reports_status() {
  bridge::BridgeCore core;
  FakeTransport transport;
  core.enqueue(makeCommand(123, "req-123", 0xAB));

  core.tick(10, transport);
  TEST_ASSERT_EQUAL_UINT(1, transport.sendCount);
  TEST_ASSERT_EQUAL_UINT8(0xAB, transport.firstByte);
  TEST_ASSERT_FALSE(core.acknowledge(124, 0));
  TEST_ASSERT_TRUE(core.hasPending());
  TEST_ASSERT_TRUE(core.acknowledge(123, 2));
  TEST_ASSERT_FALSE(core.hasPending());

  bridge::Completion completion{};
  TEST_ASSERT_TRUE(core.popCompletion(completion));
  TEST_ASSERT_EQUAL_UINT16(123, completion.command.sequence);
  TEST_ASSERT_EQUAL_STRING("req-123", completion.command.requestId);
  TEST_ASSERT_EQUAL_UINT8(1, completion.attempts);
  TEST_ASSERT_EQUAL_INT16(2, completion.statusCode);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(bridge::CompletionReason::Acknowledged),
                        static_cast<int>(completion.reason));
  TEST_ASSERT_FALSE(core.popCompletion(completion));
}

void test_retries_each_second_and_stops_after_three_attempts() {
  bridge::BridgeCore core({1000, 3});
  FakeTransport transport;
  core.enqueue(makeCommand(55));

  core.tick(0, transport);
  core.tick(999, transport);
  TEST_ASSERT_EQUAL_UINT(1, transport.sendCount);

  core.tick(1000, transport);
  TEST_ASSERT_EQUAL_UINT(2, transport.sendCount);
  core.tick(1999, transport);
  TEST_ASSERT_EQUAL_UINT(2, transport.sendCount);

  core.tick(2000, transport);
  TEST_ASSERT_EQUAL_UINT(3, transport.sendCount);
  TEST_ASSERT_TRUE(core.hasPending());

  core.tick(3000, transport);
  TEST_ASSERT_FALSE(core.hasPending());
  TEST_ASSERT_EQUAL_UINT(3, transport.sendCount);

  bridge::Completion completion{};
  TEST_ASSERT_TRUE(core.popCompletion(completion));
  TEST_ASSERT_EQUAL_UINT16(55, completion.command.sequence);
  TEST_ASSERT_EQUAL_UINT8(3, completion.attempts);
  TEST_ASSERT_EQUAL_INT16(-1, completion.statusCode);
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(bridge::CompletionReason::AttemptsExhausted),
      static_cast<int>(completion.reason));
}

void test_retry_clock_handles_millis_wraparound() {
  bridge::BridgeCore core({1000, 3});
  FakeTransport transport;
  core.enqueue(makeCommand(9));

  core.tick(0xFFFFFF00u, transport);
  core.tick(0x000002E7u, transport);  // 999 ms after the first attempt.
  TEST_ASSERT_EQUAL_UINT(1, transport.sendCount);
  core.tick(0x000002E8u, transport);  // 1000 ms after the first attempt.
  TEST_ASSERT_EQUAL_UINT(2, transport.sendCount);
}

}  // namespace

void setUp() {}
void tearDown() {}

// ---------------------------------------------------------------------------
// CommandMapper tests — JSON-independent, native-compilable
// ---------------------------------------------------------------------------

#include "command_mapper.h"
#include "bridge_core.h"

namespace {

bridge::CommandMapper mapper;

void test_conveyor_start_valid(void) {
  bridge::Command out{};
  auto r = mapper.build("CONVEYOR_START", "req-1", 42,
                        0, false, 60, 1, "60", nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kOk, r.code);
  TEST_ASSERT_EQUAL_STRING("req-1", r.canonicalRequestId);
  TEST_ASSERT_EQUAL_UINT16(42, out.sequence);
  // Wire bytes start with '@'
  TEST_ASSERT_EQUAL_UINT8('@', out.payload[0]);
}

void test_conveyor_start_speed_out_of_range(void) {
  bridge::Command out{};
  auto r = mapper.build("CONVEYOR_START", "req-2", 1,
                        0, false, 0, 1, "0", nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
  auto r2 = mapper.build("CONVEYOR_START", "req-3", 2,
                         0, false, 101, 1, "101", nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r2.code);
}

void test_conveyor_start_wrong_arg_count(void) {
  bridge::Command out{};
  auto r = mapper.build("CONVEYOR_START", "req-4", 3,
                        0, false, -1, 0, nullptr, nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
}

void test_conveyor_stop_valid(void) {
  bridge::Command out{};
  auto r = mapper.build("CONVEYOR_STOP", "req-5", 99,
                        0, false, -1, 0, nullptr, nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kOk, r.code);
  TEST_ASSERT_EQUAL_STRING("req-5", r.canonicalRequestId);
}

void test_conveyor_stop_wrong_arg_count(void) {
  bridge::Command out{};
  auto r = mapper.build("CONVEYOR_STOP", "req-6", 7,
                        0, false, -1, 1, "0", nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
}

void test_ping_valid(void) {
  bridge::Command out{};
  auto r = mapper.build("PING", "req-ping", 55,
                        0, false, -1, 0, nullptr, nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kOk, r.code);
}

void test_reset_valid(void) {
  bridge::Command out{};
  auto r = mapper.build("RESET", "req-reset", 7,
                        0, false, -1, 0, nullptr, nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kOk, r.code);
}

void test_set_output_valid(void) {
  bridge::Command out{};
  auto r = mapper.build("SET_OUTPUT", "req-so", 8,
                        5, true, -1, 2, "5", "1", out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kOk, r.code);
}

void test_set_output_channel_out_of_range(void) {
  bridge::Command out{};
  auto r = mapper.build("SET_OUTPUT", "req-so2", 9,
                        256, false, -1, 2, "256", "0", out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
}

void test_set_output_wrong_arg_count(void) {
  bridge::Command out{};
  auto r = mapper.build("SET_OUTPUT", "req-so3", 10,
                        0, false, -1, 1, "1", nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
}

// Fail-open prevention: malformed channel/value must NOT produce a valid AMLP
// frame. The JSON adapter (mqtt_bridge.cpp) pre-parses these fields before
// calling CommandMapper::build(). On parse failure it publishes 'invalid_argument'
// and never enqueues. These tests verify the CommandMapper layer rejects the
// parameter combinations that the JSON adapter would encounter.

void test_set_output_wrong_value_rejected(void) {
  // value "2" — strtoul("2")=2, valid uint but not 0 or 1.
  // JSON adapter: valueParsed=false → publishes 'invalid_argument', never calls
  // CommandMapper. Test: CommandMapper must reject value outside {0,1}.
  bridge::Command out{};
  auto r = mapper.build("SET_OUTPUT", "req-so-wrongval", 20,
                        5, true, -1, 2, "5", "2", out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
}

void test_conveyor_start_non_decimal_speed_rejected(void) {
  // Speed "abc" — strtol fails; JSON adapter sets speedParsed=false and
  // speedArg=-1. CommandMapper::build() receives speedArg=-1; validSpeed(-1)=false.
  bridge::Command out{};
  auto r = mapper.build("CONVEYOR_START", "req-cs-nondigit", 21,
                        0, false, -1, 1, "abc", nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
}

void test_conveyor_start_negative_speed_rejected(void) {
  // Speed "-1" — strtol("-1")=-1, endptr at end, but validSpeed(-1)=false.
  bridge::Command out{};
  auto r = mapper.build("CONVEYOR_START", "req-cs-neg", 22,
                        0, false, -1, 1, "-1", nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
}

void test_conveyor_start_float_speed_rejected(void) {
  // Speed "60.5" — strtol stops at '6', endptr at '.', not end of string.
  bridge::Command out{};
  auto r = mapper.build("CONVEYOR_START", "req-cs-float", 23,
                        0, false, -1, 1, "60.5", nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
}

void test_conveyor_start_zero_speed_rejected(void) {
  // Speed 0 — strtol succeeds but validSpeed(0)=false (min is 1).
  bridge::Command out{};
  auto r = mapper.build("CONVEYOR_START", "req-cs-zero", 26,
                        0, false, 0, 1, "0", nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
}

void test_conveyor_start_101_speed_rejected(void) {
  // Speed 101 — strtol succeeds but validSpeed(101)=false (max is 100).
  bridge::Command out{};
  auto r = mapper.build("CONVEYOR_START", "req-cs-101", 27,
                        0, false, 101, 1, "101", nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInvalidArgument, r.code);
}

void test_unknown_command_rejected(void) {
  bridge::Command out{};
  auto r = mapper.build("EMERGENCY_STOP", "req-e", 11,
                        0, false, -1, 0, nullptr, nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kUnknownCommand, r.code);
}

void test_null_command_name_rejected(void) {
  bridge::Command out{};
  auto r = mapper.build(nullptr, "req-null", 12,
                        0, false, -1, 0, nullptr, nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInternalError, r.code);
}

void test_null_request_id_rejected(void) {
  bridge::Command out{};
  auto r = mapper.build("PING", nullptr, 13,
                        0, false, -1, 0, nullptr, nullptr, out);
  TEST_ASSERT_EQUAL_INT(bridge::CommandMapperResult::kInternalError, r.code);
}

}  // namespace

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_rejects_invalid_and_bounds_queue);
  RUN_TEST(test_deduplicates_request_id_in_queue_pending_and_recent_cache);
  RUN_TEST(test_correlates_ack_and_reports_status);
  RUN_TEST(test_retries_each_second_and_stops_after_three_attempts);
  RUN_TEST(test_retry_clock_handles_millis_wraparound);
  // CommandMapper — JSON-independent command validation
  RUN_TEST(test_conveyor_start_valid);
  RUN_TEST(test_conveyor_start_speed_out_of_range);
  RUN_TEST(test_conveyor_start_wrong_arg_count);
  RUN_TEST(test_conveyor_stop_valid);
  RUN_TEST(test_conveyor_stop_wrong_arg_count);
  RUN_TEST(test_ping_valid);
  RUN_TEST(test_reset_valid);
  RUN_TEST(test_set_output_valid);
  RUN_TEST(test_set_output_channel_out_of_range);
  RUN_TEST(test_set_output_wrong_arg_count);
  RUN_TEST(test_set_output_wrong_value_rejected);
  RUN_TEST(test_conveyor_start_non_decimal_speed_rejected);
  RUN_TEST(test_conveyor_start_negative_speed_rejected);
  RUN_TEST(test_conveyor_start_float_speed_rejected);
  RUN_TEST(test_conveyor_start_zero_speed_rejected);
  RUN_TEST(test_conveyor_start_101_speed_rejected);
  RUN_TEST(test_unknown_command_rejected);
  RUN_TEST(test_null_command_name_rejected);
  RUN_TEST(test_null_request_id_rejected);
  return UNITY_END();
}
