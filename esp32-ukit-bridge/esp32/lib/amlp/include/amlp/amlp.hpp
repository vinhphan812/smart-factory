#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string_view>

namespace amlp {

constexpr std::size_t kMaxFrameLength = 256;
constexpr std::size_t kMaxFields = 12;  // Includes the CMD/ACK/TEL type token.
constexpr std::size_t kMaxPayloadFields = kMaxFields - 1;
constexpr std::size_t kMaxFieldLength = 64;
constexpr std::uint32_t kParserTimeoutMs = 250;

enum class Type : std::uint8_t {
  Cmd,
  Ack,
  Tel,
};

enum class Error : std::uint8_t {
  None,
  Timeout,
  FrameTooLong,
  BufferTooSmall,
  InvalidFormat,
  InvalidCrc,
  InvalidCharacter,
  UnsupportedType,
  TooManyFields,
  FieldTooLong,
};

enum class ParseStatus : std::uint8_t {
  None,
  FrameReady,
  Error,
};

struct ParseResult {
  ParseStatus status{ParseStatus::None};
  Error error{Error::None};
};

struct Frame {
  Type type{Type::Cmd};
  std::uint8_t field_count{0};  // Payload fields only; the type token is separate.
  std::array<std::array<char, kMaxFieldLength + 1>, kMaxPayloadFields> fields{};
  std::array<std::uint8_t, kMaxPayloadFields> field_lengths{};

  void clear();
  std::string_view field(std::size_t index) const;
  bool set_field(std::size_t index, std::string_view value);
};

std::string_view type_name(Type type);
const char* error_string(Error error);

std::uint16_t crc16_ccitt_false(const std::uint8_t* data, std::size_t length);
std::uint16_t crc16_ccitt_false(std::string_view data);

// Encodes the canonical AMLP wire form: @BODY*CRC4\r\n.
Error encode(const Frame& frame, char* output, std::size_t capacity,
             std::size_t& written);

class Parser {
 public:
  Parser() = default;

  // Bytes outside a frame are ignored. A new '@' always starts a fresh frame.
  ParseResult feed(std::uint8_t byte, std::uint32_t now_ms, Frame& output);

  // Call while input is idle so a partial frame can expire without a new byte.
  ParseResult check_timeout(std::uint32_t now_ms);

  void reset();
  bool active() const { return active_; }

 private:
  ParseResult parse_complete(Frame& output);
  void start(std::uint32_t now_ms);

  std::array<char, kMaxFrameLength> buffer_{};
  std::size_t used_{0};
  std::uint32_t last_byte_ms_{0};
  bool active_{false};
};

}  // namespace amlp
