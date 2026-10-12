#pragma once

#include <cstddef>
#include <cstdint>

namespace bridge {

constexpr std::size_t kMaxPayloadSize = 256;
constexpr std::size_t kMaxRequestIdLength = 64;
constexpr std::size_t kMaxCommandNameLength = 16;
constexpr std::size_t kCommandQueueCapacity = 8;
constexpr std::size_t kCompletionQueueCapacity = 8;
constexpr std::size_t kDedupeCapacity = 16;

struct Command {
  uint16_t sequence = 0;
  char requestId[kMaxRequestIdLength + 1]{};
  char commandName[kMaxCommandNameLength + 1]{};
  uint16_t payloadLength = 0;
  uint8_t payload[kMaxPayloadSize]{};
};

enum class EnqueueResult : uint8_t {
  Accepted,
  Duplicate,
  QueueFull,
  Invalid,
};

enum class CompletionReason : uint8_t {
  Acknowledged,
  AttemptsExhausted,
};

struct Completion {
  Command command{};
  CompletionReason reason = CompletionReason::Acknowledged;
  uint8_t attempts = 0;
  int16_t statusCode = -1;
};

struct BridgeOptions {
  uint32_t retryIntervalMs = 1000;
  uint8_t maxAttempts = 3;
};

class Transport {
 public:
  virtual ~Transport() = default;
  virtual bool send(const uint8_t* data, std::size_t length) = 0;
};

class BridgeCore {
 public:
  explicit BridgeCore(BridgeOptions options = {});

  EnqueueResult enqueue(const Command& command);
  void tick(uint32_t nowMs, Transport& transport);
  bool acknowledge(uint16_t sequence, int16_t statusCode = 0);
  bool popCompletion(Completion& completion);

  bool findRequest(const char* requestId, uint16_t& sequence) const;
  bool sequenceInUse(uint16_t sequence) const;
  bool hasPending() const;
  uint16_t pendingSequence() const;
  uint8_t pendingAttempts() const;
  std::size_t queuedCount() const;

 private:
  struct RecentIdentity {
    char requestId[kMaxRequestIdLength + 1]{};
    uint16_t sequence = 0;
  };

  static bool validText(const char* text, std::size_t capacity);
  static bool sameText(const char* left, const char* right,
                       std::size_t capacity);
  bool queuePush(const Command& command);
  bool queuePop(Command& command);
  void remember(const Command& command);
  void completePending(CompletionReason reason, int16_t statusCode);
  void pushCompletion(const Completion& completion);
  void attemptSend(uint32_t nowMs, Transport& transport);
  static bool elapsed(uint32_t nowMs, uint32_t sinceMs, uint32_t intervalMs);

  BridgeOptions options_{};
  Command queue_[kCommandQueueCapacity]{};
  std::size_t queueHead_ = 0;
  std::size_t queueTail_ = 0;
  std::size_t queueSize_ = 0;

  bool pendingActive_ = false;
  Command pending_{};
  uint8_t pendingAttempts_ = 0;
  uint32_t lastAttemptMs_ = 0;

  Completion completions_[kCompletionQueueCapacity]{};
  std::size_t completionHead_ = 0;
  std::size_t completionTail_ = 0;
  std::size_t completionSize_ = 0;

  RecentIdentity recent_[kDedupeCapacity]{};
  std::size_t recentWrite_ = 0;
  std::size_t recentSize_ = 0;
};

}  // namespace bridge
