#include "command_mapper.h"

#include <algorithm>
#include <cstdio>
#include <cstring>

#include "amlp/amlp.hpp"

namespace bridge {

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

bool CommandMapper::validSpeed(int s) {
  return s >= 1 && s <= 100;
}

bool CommandMapper::validChannel(unsigned int c) {
  return c <= 255U;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

CommandMapperResult CommandMapper::build(
    const char* commandName,
    const char* requestId,
    uint16_t sequence,
    unsigned int channel,
    bool outputValue,
    int speedArg,
    uint8_t argCount,
    const char* arg0,
    const char* arg1,
    Command& out) const {

  CommandMapperResult result{};
  result.canonicalRequestId = requestId;

  // Guard against null pointers from the caller.
  if (commandName == nullptr || requestId == nullptr) {
    result.code = CommandMapperResult::kInternalError;
    return result;
  }

  // -------------------------------------------------------------------------
  // Command routing — allowlist enforcement
  // -------------------------------------------------------------------------

  if (std::strcmp(commandName, "CONVEYOR_START") == 0) {
    // CONVEYOR_START requires exactly one argument: speed (integer 1..100).
    if (argCount != 1u || arg0 == nullptr) {
      result.code = CommandMapperResult::kInvalidArgument;
      return result;
    }
    // speedArg comes pre-parsed from JSON; validate it.
    if (!validSpeed(speedArg)) {
      result.code = CommandMapperResult::kInvalidArgument;
      return result;
    }
    // Build the AMLP frame: CMD,<sequence>,CONVEYOR_START,<speed>
    amlp::Frame frame{};
    frame.type = amlp::Type::Cmd;
    char seqBuf[6]{};
    std::snprintf(seqBuf, sizeof(seqBuf), "%u", static_cast<unsigned>(sequence));
    char speedBuf[4]{};
    std::snprintf(speedBuf, sizeof(speedBuf), "%d", speedArg);
    if (!frame.set_field(0, seqBuf) ||
        !frame.set_field(1, "CONVEYOR_START") ||
        !frame.set_field(2, speedBuf)) {
      result.code = CommandMapperResult::kInternalError;
      return result;
    }

    char wire[amlp::kMaxFrameLength]{};
    std::size_t written = 0;
    if (amlp::encode(frame, wire, sizeof(wire), written) != amlp::Error::None ||
        written == 0 || written > kMaxPayloadSize) {
      result.code = CommandMapperResult::kInternalError;
      return result;
    }

    out.sequence = sequence;
    std::strncpy(out.requestId, requestId, kMaxRequestIdLength);
    out.requestId[kMaxRequestIdLength] = '\0';
    std::strncpy(out.commandName, commandName, kMaxCommandNameLength);
    out.commandName[kMaxCommandNameLength] = '\0';
    out.payloadLength = static_cast<uint16_t>(written);
    std::memcpy(out.payload, wire, written);
    result.code = CommandMapperResult::kOk;
    return result;
  }

  if (std::strcmp(commandName, "CONVEYOR_STOP") == 0) {
    // CONVEYOR_STOP takes no arguments.
    if (argCount != 0u) {
      result.code = CommandMapperResult::kInvalidArgument;
      return result;
    }
    amlp::Frame frame{};
    frame.type = amlp::Type::Cmd;
    char seqBuf[6]{};
    std::snprintf(seqBuf, sizeof(seqBuf), "%u", static_cast<unsigned>(sequence));
    if (!frame.set_field(0, seqBuf) ||
        !frame.set_field(1, "CONVEYOR_STOP")) {
      result.code = CommandMapperResult::kInternalError;
      return result;
    }

    char wire[amlp::kMaxFrameLength]{};
    std::size_t written = 0;
    if (amlp::encode(frame, wire, sizeof(wire), written) != amlp::Error::None ||
        written == 0 || written > kMaxPayloadSize) {
      result.code = CommandMapperResult::kInternalError;
      return result;
    }

    out.sequence = sequence;
    std::strncpy(out.requestId, requestId, kMaxRequestIdLength);
    out.requestId[kMaxRequestIdLength] = '\0';
    std::strncpy(out.commandName, commandName, kMaxCommandNameLength);
    out.commandName[kMaxCommandNameLength] = '\0';
    out.payloadLength = static_cast<uint16_t>(written);
    std::memcpy(out.payload, wire, written);
    result.code = CommandMapperResult::kOk;
    return result;
  }

  if (std::strcmp(commandName, "RESET") == 0) {
    if (argCount != 0u) {
      result.code = CommandMapperResult::kInvalidArgument;
      return result;
    }
    amlp::Frame frame{};
    frame.type = amlp::Type::Cmd;
    char seqBuf[6]{};
    std::snprintf(seqBuf, sizeof(seqBuf), "%u", static_cast<unsigned>(sequence));
    if (!frame.set_field(0, seqBuf) ||
        !frame.set_field(1, "RESET")) {
      result.code = CommandMapperResult::kInternalError;
      return result;
    }

    char wire[amlp::kMaxFrameLength]{};
    std::size_t written = 0;
    if (amlp::encode(frame, wire, sizeof(wire), written) != amlp::Error::None ||
        written == 0 || written > kMaxPayloadSize) {
      result.code = CommandMapperResult::kInternalError;
      return result;
    }

    out.sequence = sequence;
    std::strncpy(out.requestId, requestId, kMaxRequestIdLength);
    out.requestId[kMaxRequestIdLength] = '\0';
    std::strncpy(out.commandName, commandName, kMaxCommandNameLength);
    out.commandName[kMaxCommandNameLength] = '\0';
    out.payloadLength = static_cast<uint16_t>(written);
    std::memcpy(out.payload, wire, written);
    result.code = CommandMapperResult::kOk;
    return result;
  }

  if (std::strcmp(commandName, "PING") == 0) {
    if (argCount != 0u) {
      result.code = CommandMapperResult::kInvalidArgument;
      return result;
    }
    amlp::Frame frame{};
    frame.type = amlp::Type::Cmd;
    char seqBuf[6]{};
    std::snprintf(seqBuf, sizeof(seqBuf), "%u", static_cast<unsigned>(sequence));
    if (!frame.set_field(0, seqBuf) ||
        !frame.set_field(1, "PING")) {
      result.code = CommandMapperResult::kInternalError;
      return result;
    }

    char wire[amlp::kMaxFrameLength]{};
    std::size_t written = 0;
    if (amlp::encode(frame, wire, sizeof(wire), written) != amlp::Error::None ||
        written == 0 || written > kMaxPayloadSize) {
      result.code = CommandMapperResult::kInternalError;
      return result;
    }

    out.sequence = sequence;
    std::strncpy(out.requestId, requestId, kMaxRequestIdLength);
    out.requestId[kMaxRequestIdLength] = '\0';
    std::strncpy(out.commandName, commandName, kMaxCommandNameLength);
    out.commandName[kMaxCommandNameLength] = '\0';
    out.payloadLength = static_cast<uint16_t>(written);
    std::memcpy(out.payload, wire, written);
    result.code = CommandMapperResult::kOk;
    return result;
  }

  if (std::strcmp(commandName, "SET_OUTPUT") == 0) {
    // SET_OUTPUT requires exactly two arguments: channel (uint 0..255) and value (0 or 1).
    if (argCount != 2u || arg0 == nullptr || arg1 == nullptr) {
      result.code = CommandMapperResult::kInvalidArgument;
      return result;
    }
    if (!validChannel(channel)) {
      result.code = CommandMapperResult::kInvalidArgument;
      return result;
    }
    // Reject value strings that are not exactly "0" or "1".
    // The JSON adapter pre-parses these; if parsing failed the adapter returns
    // early before calling build(). This defense-in-depth check catches any
    // caller that passes a raw boolean or malformed string for the value.
    if (std::strcmp(arg1, "0") != 0 && std::strcmp(arg1, "1") != 0) {
      result.code = CommandMapperResult::kInvalidArgument;
      return result;
    }
    amlp::Frame frame{};
    frame.type = amlp::Type::Cmd;
    char seqBuf[6]{};
    std::snprintf(seqBuf, sizeof(seqBuf), "%u", static_cast<unsigned>(sequence));
    char chBuf[4]{};
    std::snprintf(chBuf, sizeof(chBuf), "%u", channel);
    if (!frame.set_field(0, seqBuf) ||
        !frame.set_field(1, "SET_OUTPUT") ||
        !frame.set_field(2, chBuf) ||
        !frame.set_field(3, outputValue ? "1" : "0")) {
      result.code = CommandMapperResult::kInternalError;
      return result;
    }

    char wire[amlp::kMaxFrameLength]{};
    std::size_t written = 0;
    if (amlp::encode(frame, wire, sizeof(wire), written) != amlp::Error::None ||
        written == 0 || written > kMaxPayloadSize) {
      result.code = CommandMapperResult::kInternalError;
      return result;
    }

    out.sequence = sequence;
    std::strncpy(out.requestId, requestId, kMaxRequestIdLength);
    out.requestId[kMaxRequestIdLength] = '\0';
    std::strncpy(out.commandName, commandName, kMaxCommandNameLength);
    out.commandName[kMaxCommandNameLength] = '\0';
    out.payloadLength = static_cast<uint16_t>(written);
    std::memcpy(out.payload, wire, written);
    result.code = CommandMapperResult::kOk;
    return result;
  }

  // Unknown command — not in the allowlist.
  result.code = CommandMapperResult::kUnknownCommand;
  return result;
}

}  // namespace bridge
