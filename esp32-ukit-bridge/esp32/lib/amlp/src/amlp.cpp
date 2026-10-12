#include "amlp/amlp.hpp"

#include <cstring>

namespace amlp {
namespace {

constexpr char kHex[] = "0123456789ABCDEF";

bool is_field_character(char ch) {
  const auto byte = static_cast<unsigned char>(ch);
  return byte >= 0x20U && byte <= 0x7EU && ch != ',' && ch != '*' &&
         ch != '@';
}

bool is_upper_hex(char ch) {
  return (ch >= '0' && ch <= '9') || (ch >= 'A' && ch <= 'F');
}

std::uint8_t hex_value(char ch) {
  return static_cast<std::uint8_t>(ch <= '9' ? ch - '0' : ch - 'A' + 10);
}

Error validate_field(std::string_view field) {
  if (field.empty()) {
    return Error::InvalidFormat;
  }
  if (field.size() > kMaxFieldLength) {
    return Error::FieldTooLong;
  }
  for (char ch : field) {
    if (!is_field_character(ch)) {
      return Error::InvalidCharacter;
    }
  }
  return Error::None;
}

bool parse_type(std::string_view token, Type& type) {
  if (token == "CMD") {
    type = Type::Cmd;
    return true;
  }
  if (token == "ACK") {
    type = Type::Ack;
    return true;
  }
  if (token == "TEL") {
    type = Type::Tel;
    return true;
  }
  return false;
}

}  // namespace

void Frame::clear() {
  type = Type::Cmd;
  field_count = 0;
  field_lengths.fill(0);
  for (auto& value : fields) {
    value.fill('\0');
  }
}

std::string_view Frame::field(std::size_t index) const {
  if (index >= field_count) {
    return {};
  }
  return {fields[index].data(), field_lengths[index]};
}

bool Frame::set_field(std::size_t index, std::string_view value) {
  if (index >= kMaxPayloadFields || validate_field(value) != Error::None) {
    return false;
  }
  std::memcpy(fields[index].data(), value.data(), value.size());
  fields[index][value.size()] = '\0';
  field_lengths[index] = static_cast<std::uint8_t>(value.size());
  if (index >= field_count) {
    field_count = static_cast<std::uint8_t>(index + 1);
  }
  return true;
}

std::string_view type_name(Type type) {
  switch (type) {
    case Type::Cmd:
      return "CMD";
    case Type::Ack:
      return "ACK";
    case Type::Tel:
      return "TEL";
  }
  return {};
}

const char* error_string(Error error) {
  switch (error) {
    case Error::None:
      return "none";
    case Error::Timeout:
      return "timeout";
    case Error::FrameTooLong:
      return "frame too long";
    case Error::BufferTooSmall:
      return "buffer too small";
    case Error::InvalidFormat:
      return "invalid format";
    case Error::InvalidCrc:
      return "invalid CRC";
    case Error::InvalidCharacter:
      return "invalid character";
    case Error::UnsupportedType:
      return "unsupported type";
    case Error::TooManyFields:
      return "too many fields";
    case Error::FieldTooLong:
      return "field too long";
  }
  return "unknown error";
}

std::uint16_t crc16_ccitt_false(const std::uint8_t* data,
                                std::size_t length) {
  std::uint16_t crc = 0xFFFFU;
  for (std::size_t index = 0; index < length; ++index) {
    crc ^= static_cast<std::uint16_t>(data[index]) << 8U;
    for (int bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x8000U) != 0U
                ? static_cast<std::uint16_t>((crc << 1U) ^ 0x1021U)
                : static_cast<std::uint16_t>(crc << 1U);
    }
  }
  return crc;
}

std::uint16_t crc16_ccitt_false(std::string_view data) {
  return crc16_ccitt_false(
      reinterpret_cast<const std::uint8_t*>(data.data()), data.size());
}

Error encode(const Frame& frame, char* output, std::size_t capacity,
             std::size_t& written) {
  written = 0;
  if (output == nullptr) {
    return Error::BufferTooSmall;
  }

  const std::string_view type = type_name(frame.type);
  if (type.empty()) {
    return Error::UnsupportedType;
  }
  if (frame.field_count > kMaxPayloadFields) {
    return Error::TooManyFields;
  }

  std::size_t body_length = type.size();
  for (std::size_t index = 0; index < frame.field_count; ++index) {
    const std::string_view field = frame.field(index);
    const Error error = validate_field(field);
    if (error != Error::None) {
      return error;
    }
    body_length += 1U + field.size();
  }

  constexpr std::size_t kOverhead = 1U + 1U + 4U + 2U;  // @, *, CRC, CRLF
  const std::size_t frame_length = body_length + kOverhead;
  if (frame_length > kMaxFrameLength) {
    return Error::FrameTooLong;
  }
  if (capacity < frame_length) {
    return Error::BufferTooSmall;
  }

  std::size_t cursor = 0;
  output[cursor++] = '@';
  std::memcpy(output + cursor, type.data(), type.size());
  cursor += type.size();
  for (std::size_t index = 0; index < frame.field_count; ++index) {
    output[cursor++] = ',';
    const std::string_view field = frame.field(index);
    std::memcpy(output + cursor, field.data(), field.size());
    cursor += field.size();
  }

  const std::uint16_t crc = crc16_ccitt_false(
      reinterpret_cast<const std::uint8_t*>(output + 1), body_length);
  output[cursor++] = '*';
  output[cursor++] = kHex[(crc >> 12U) & 0x0FU];
  output[cursor++] = kHex[(crc >> 8U) & 0x0FU];
  output[cursor++] = kHex[(crc >> 4U) & 0x0FU];
  output[cursor++] = kHex[crc & 0x0FU];
  output[cursor++] = '\r';
  output[cursor++] = '\n';
  written = cursor;
  return Error::None;
}

void Parser::start(std::uint32_t now_ms) {
  active_ = true;
  used_ = 1;
  buffer_[0] = '@';
  last_byte_ms_ = now_ms;
}

void Parser::reset() {
  active_ = false;
  used_ = 0;
  last_byte_ms_ = 0;
}

ParseResult Parser::check_timeout(std::uint32_t now_ms) {
  if (active_ &&
      static_cast<std::uint32_t>(now_ms - last_byte_ms_) >=
          kParserTimeoutMs) {
    reset();
    return {ParseStatus::Error, Error::Timeout};
  }
  return {};
}

ParseResult Parser::feed(std::uint8_t byte, std::uint32_t now_ms,
                         Frame& output) {
  const ParseResult timeout = check_timeout(now_ms);

  if (byte == static_cast<std::uint8_t>('@')) {
    start(now_ms);
    return timeout.status == ParseStatus::Error ? timeout : ParseResult{};
  }

  if (!active_) {
    return timeout.status == ParseStatus::Error ? timeout : ParseResult{};
  }

  last_byte_ms_ = now_ms;
  if (byte == static_cast<std::uint8_t>('\n')) {
    const ParseResult result = parse_complete(output);
    reset();
    return result;
  }

  // Keep room for the terminating LF so the received wire frame stays <= 256.
  if (used_ >= kMaxFrameLength - 1U) {
    reset();
    return {ParseStatus::Error, Error::FrameTooLong};
  }

  buffer_[used_++] = static_cast<char>(byte);
  return timeout.status == ParseStatus::Error ? timeout : ParseResult{};
}

ParseResult Parser::parse_complete(Frame& output) {
  std::size_t content_end = used_;
  if (content_end > 1U && buffer_[content_end - 1U] == '\r') {
    --content_end;
  }

  // Minimum content is @CMD*0000 (nine bytes before line ending).
  if (content_end < 9U) {
    return {ParseStatus::Error, Error::InvalidFormat};
  }

  std::size_t star = content_end;
  for (std::size_t index = 1; index < content_end; ++index) {
    const char ch = buffer_[index];
    if (ch == '\r') {
      return {ParseStatus::Error, Error::InvalidCharacter};
    }
    if (ch == '*') {
      if (star != content_end) {
        return {ParseStatus::Error, Error::InvalidFormat};
      }
      star = index;
    }
  }

  if (star == content_end || star == 1U || star + 5U != content_end) {
    return {ParseStatus::Error, Error::InvalidFormat};
  }

  std::uint16_t received_crc = 0;
  for (std::size_t index = star + 1U; index < content_end; ++index) {
    if (!is_upper_hex(buffer_[index])) {
      return {ParseStatus::Error, Error::InvalidFormat};
    }
    received_crc = static_cast<std::uint16_t>(
        (received_crc << 4U) | hex_value(buffer_[index]));
  }

  const std::uint16_t calculated_crc = crc16_ccitt_false(
      reinterpret_cast<const std::uint8_t*>(buffer_.data() + 1U),
      star - 1U);
  if (received_crc != calculated_crc) {
    return {ParseStatus::Error, Error::InvalidCrc};
  }

  Frame decoded;
  decoded.clear();
  std::size_t token_start = 1U;
  std::size_t token_index = 0;
  while (token_start < star) {
    std::size_t token_end = token_start;
    while (token_end < star && buffer_[token_end] != ',') {
      ++token_end;
    }

    const std::string_view token(buffer_.data() + token_start,
                                 token_end - token_start);
    const Error field_error = validate_field(token);
    if (field_error != Error::None) {
      return {ParseStatus::Error, field_error};
    }
    if (token_index >= kMaxFields) {
      return {ParseStatus::Error, Error::TooManyFields};
    }

    if (token_index == 0U) {
      if (!parse_type(token, decoded.type)) {
        return {ParseStatus::Error, Error::UnsupportedType};
      }
    } else if (!decoded.set_field(token_index - 1U, token)) {
      return {ParseStatus::Error, Error::InvalidFormat};
    }

    ++token_index;
    if (token_end == star) {
      break;
    }
    token_start = token_end + 1U;
    if (token_start == star) {
      return {ParseStatus::Error, Error::InvalidFormat};
    }
  }

  if (token_index == 0U) {
    return {ParseStatus::Error, Error::InvalidFormat};
  }
  output = decoded;
  return {ParseStatus::FrameReady, Error::None};
}

}  // namespace amlp
