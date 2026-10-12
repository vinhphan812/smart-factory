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

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_rejects_invalid_and_bounds_queue);
  RUN_TEST(test_deduplicates_request_id_in_queue_pending_and_recent_cache);
  RUN_TEST(test_correlates_ack_and_reports_status);
  RUN_TEST(test_retries_each_second_and_stops_after_three_attempts);
  RUN_TEST(test_retry_clock_handles_millis_wraparound);
  return UNITY_END();
}
