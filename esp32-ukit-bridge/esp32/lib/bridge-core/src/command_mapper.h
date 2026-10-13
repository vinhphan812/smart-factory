#pragma once

#include <cstddef>
#include <cstdint>

#include "bridge_core.h"

namespace bridge {

/**
 * @brief Result of mapping an incoming command to an AMLP frame.
 *
 * @note On kOk the caller should enqueue 'out' with BridgeCore and
 *       publish a queued acknowledgement. On error the caller publishes
 *       an immediate negative acknowledgement and does NOT enqueue.
 */
struct CommandMapperResult {
  enum Code {
    kOk,             ///< Mapping succeeded; 'out' contains a valid AMLP frame.
    kUnknownCommand, ///< commandName not in the allowlist.
    kInvalidArgument,///< arguments failed validation.
    kInternalError,  ///< Sequence allocation or encoding failure.
  } code;
  const char* canonicalRequestId;  ///< Canonical string ID used for ACKs.
};

/**
 * @brief Maps a validated command to an AMLP CMD wire frame.
 *
 * This class is transport-agnostic: it has no Arduino, PubSubClient or
 * ArduinoJson dependencies and can be compiled and unit-tested in the
 * PlatformIO native environment.
 *
 * Responsibilities:
 *   - Enforce the command-name allowlist.
 *   - Validate argument shapes (type, range, count).
 *   - Build an amlp::Frame with the correct token and fields.
 *   - Encode the frame to a wire buffer.
 *
 * Usage:
 *   CommandMapper mapper;
 *   Command cmd{};
 *   auto result = mapper.build("CONVEYOR_START", "req-1", 42, 0, false, 60, cmd);
 *   if (result.code == CommandMapperResult::kOk) {
 *     core.enqueue(cmd);
 *   } else {
 *     bridge.publishImmediateNack(result.code, result.canonicalRequestId);
 *   }
 */
class CommandMapper {
 public:
  /**
   * @brief Build an AMLP CMD frame from validated input.
   *
   * @param commandName  The operation name, e.g. "CONVEYOR_START".
   * @param requestId   Canonical string correlation ID (must not be null).
   * @param sequence    Bridge-assigned 16-bit sequence number.
   * @param channel     SET_OUTPUT channel (0..255); unused by other commands.
   * @param outputValue SET_OUTPUT value; unused by other commands.
   * @param speedArg    CONVEYOR_START speed (1..100); -1 if not applicable.
   * @param argCount    Number of positional arguments present in the JSON.
   * @param arg0        First positional argument as string, or nullptr.
   * @param arg1        Second positional argument as string, or nullptr.
   * @param out         Output Command to fill on kOk.
   *
   * @return CommandMapperResult with kOk on success or an error code.
   */
  CommandMapperResult build(const char* commandName,
                           const char* requestId,
                           uint16_t sequence,
                           unsigned int channel,
                           bool outputValue,
                           int speedArg,
                           uint8_t argCount,
                           const char* arg0,
                           const char* arg1,
                           Command& out) const;

 private:
  static bool validSpeed(int s);
  static bool validChannel(unsigned int c);
};

}  // namespace bridge
