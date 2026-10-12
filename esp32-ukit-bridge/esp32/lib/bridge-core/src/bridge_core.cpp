#include "bridge_core.h"

#include <cstring>

namespace bridge {

BridgeCore::BridgeCore(BridgeOptions options) : options_(options) {
  if (options_.retryIntervalMs == 0) {
    options_.retryIntervalMs = 1000;
  }
  if (options_.maxAttempts == 0) {
    options_.maxAttempts = 3;
  }
}

EnqueueResult BridgeCore::enqueue(const Command& command) {
  if (!validText(command.requestId, sizeof(command.requestId)) ||
      !validText(command.commandName, sizeof(command.commandName)) ||
      command.payloadLength == 0 || command.payloadLength > kMaxPayloadSize) {
    return EnqueueResult::Invalid;
  }
  uint16_t existingSequence = 0;
  if (findRequest(command.requestId, existingSequence)) {
    return EnqueueResult::Duplicate;
  }
  if (sequenceInUse(command.sequence)) {
    return EnqueueResult::Invalid;
  }
  if (!queuePush(command)) {
    return EnqueueResult::QueueFull;
  }
  return EnqueueResult::Accepted;
}

void BridgeCore::tick(uint32_t nowMs, Transport& transport) {
  if (!pendingActive_) {
    if (!queuePop(pending_)) {
      return;
    }
    pendingActive_ = true;
    pendingAttempts_ = 0;
    attemptSend(nowMs, transport);
    return;
  }

  if (!elapsed(nowMs, lastAttemptMs_, options_.retryIntervalMs)) {
    return;
  }

  if (pendingAttempts_ >= options_.maxAttempts) {
    completePending(CompletionReason::AttemptsExhausted, -1);
    return;
  }

  attemptSend(nowMs, transport);
}

bool BridgeCore::acknowledge(uint16_t sequence, int16_t statusCode) {
  if (!pendingActive_ || pending_.sequence != sequence) {
    return false;
  }
  completePending(CompletionReason::Acknowledged, statusCode);
  return true;
}

bool BridgeCore::popCompletion(Completion& completion) {
  if (completionSize_ == 0) {
    return false;
  }
  completion = completions_[completionHead_];
  completionHead_ = (completionHead_ + 1) % kCompletionQueueCapacity;
  --completionSize_;
  return true;
}

bool BridgeCore::findRequest(const char* requestId, uint16_t& sequence) const {
  if (!validText(requestId, kMaxRequestIdLength + 1)) {
    return false;
  }
  if (pendingActive_ &&
      sameText(pending_.requestId, requestId, sizeof(pending_.requestId))) {
    sequence = pending_.sequence;
    return true;
  }
  for (std::size_t i = 0; i < queueSize_; ++i) {
    const std::size_t index = (queueHead_ + i) % kCommandQueueCapacity;
    if (sameText(queue_[index].requestId, requestId,
                 sizeof(queue_[index].requestId))) {
      sequence = queue_[index].sequence;
      return true;
    }
  }
  for (std::size_t i = 0; i < recentSize_; ++i) {
    if (sameText(recent_[i].requestId, requestId,
                 sizeof(recent_[i].requestId))) {
      sequence = recent_[i].sequence;
      return true;
    }
  }
  return false;
}

bool BridgeCore::sequenceInUse(uint16_t sequence) const {
  if (pendingActive_ && pending_.sequence == sequence) {
    return true;
  }
  for (std::size_t i = 0; i < queueSize_; ++i) {
    const std::size_t index = (queueHead_ + i) % kCommandQueueCapacity;
    if (queue_[index].sequence == sequence) {
      return true;
    }
  }
  for (std::size_t i = 0; i < recentSize_; ++i) {
    if (recent_[i].sequence == sequence) {
      return true;
    }
  }
  return false;
}

bool BridgeCore::hasPending() const { return pendingActive_; }

uint16_t BridgeCore::pendingSequence() const {
  return pendingActive_ ? pending_.sequence : 0;
}

uint8_t BridgeCore::pendingAttempts() const {
  return pendingActive_ ? pendingAttempts_ : 0;
}

std::size_t BridgeCore::queuedCount() const { return queueSize_; }

bool BridgeCore::validText(const char* text, std::size_t capacity) {
  if (text == nullptr || capacity < 2 || text[0] == '\0') {
    return false;
  }
  for (std::size_t i = 1; i < capacity; ++i) {
    if (text[i] == '\0') {
      return true;
    }
  }
  return false;
}

bool BridgeCore::sameText(const char* left, const char* right,
                          std::size_t capacity) {
  return std::strncmp(left, right, capacity) == 0;
}

bool BridgeCore::queuePush(const Command& command) {
  if (queueSize_ >= kCommandQueueCapacity) {
    return false;
  }
  queue_[queueTail_] = command;
  queueTail_ = (queueTail_ + 1) % kCommandQueueCapacity;
  ++queueSize_;
  return true;
}

bool BridgeCore::queuePop(Command& command) {
  if (queueSize_ == 0) {
    return false;
  }
  command = queue_[queueHead_];
  queueHead_ = (queueHead_ + 1) % kCommandQueueCapacity;
  --queueSize_;
  return true;
}

void BridgeCore::remember(const Command& command) {
  std::strncpy(recent_[recentWrite_].requestId, command.requestId,
               sizeof(recent_[recentWrite_].requestId) - 1);
  recent_[recentWrite_].requestId[sizeof(recent_[recentWrite_].requestId) - 1] =
      '\0';
  recent_[recentWrite_].sequence = command.sequence;
  recentWrite_ = (recentWrite_ + 1) % kDedupeCapacity;
  if (recentSize_ < kDedupeCapacity) {
    ++recentSize_;
  }
}

void BridgeCore::completePending(CompletionReason reason,
                                 int16_t statusCode) {
  Completion completion{};
  completion.command = pending_;
  completion.reason = reason;
  completion.attempts = pendingAttempts_;
  completion.statusCode = statusCode;
  remember(pending_);
  pushCompletion(completion);

  pendingActive_ = false;
  pending_ = {};
  pendingAttempts_ = 0;
  lastAttemptMs_ = 0;
}

void BridgeCore::pushCompletion(const Completion& completion) {
  if (completionSize_ >= kCompletionQueueCapacity) {
    completionHead_ = (completionHead_ + 1) % kCompletionQueueCapacity;
    --completionSize_;
  }
  completions_[completionTail_] = completion;
  completionTail_ = (completionTail_ + 1) % kCompletionQueueCapacity;
  ++completionSize_;
}

void BridgeCore::attemptSend(uint32_t nowMs, Transport& transport) {
  transport.send(pending_.payload, pending_.payloadLength);
  ++pendingAttempts_;
  lastAttemptMs_ = nowMs;
}

bool BridgeCore::elapsed(uint32_t nowMs, uint32_t sinceMs,
                         uint32_t intervalMs) {
  return static_cast<uint32_t>(nowMs - sinceMs) >= intervalMs;
}

}  // namespace bridge
