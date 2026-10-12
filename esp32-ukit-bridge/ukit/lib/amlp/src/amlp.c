#include "amlp.h"

#include <string.h>

static const char k_hex[] = "0123456789ABCDEF";

static int is_field_character(char value) {
    unsigned char byte = (unsigned char)value;
    return byte >= 0x20u && byte <= 0x7Eu && value != ',' && value != '*' && value != '@';
}

static int is_upper_hex(char value) {
    return (value >= '0' && value <= '9') || (value >= 'A' && value <= 'F');
}

static uint8_t hex_value(char value) {
    return (uint8_t)(value <= '9' ? value - '0' : value - 'A' + 10);
}

static int validate_field(const char *value, size_t length) {
    size_t index;
    if (value == NULL || length == 0u || length > AMLP_MAX_FIELD_LENGTH) {
        return 0;
    }
    for (index = 0u; index < length; ++index) {
        if (!is_field_character(value[index])) {
            return 0;
        }
    }
    return 1;
}

static int parse_type(const char *value, size_t length, amlp_type_t *type) {
    if (length == 3u && memcmp(value, "CMD", 3u) == 0) {
        *type = AMLP_TYPE_CMD;
        return 1;
    }
    if (length == 3u && memcmp(value, "ACK", 3u) == 0) {
        *type = AMLP_TYPE_ACK;
        return 1;
    }
    if (length == 3u && memcmp(value, "TEL", 3u) == 0) {
        *type = AMLP_TYPE_TEL;
        return 1;
    }
    return 0;
}

uint16_t amlp_crc16_ccitt_false(const uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFFu;
    size_t index;
    uint8_t bit;

    if (data == NULL && length != 0u) {
        return 0u;
    }
    for (index = 0u; index < length; ++index) {
        crc ^= (uint16_t)((uint16_t)data[index] << 8);
        for (bit = 0u; bit < 8u; ++bit) {
            crc = (crc & 0x8000u) != 0u
                ? (uint16_t)((crc << 1) ^ 0x1021u)
                : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

void amlp_frame_init(amlp_frame_t *frame, amlp_type_t type) {
    if (frame != NULL) {
        memset(frame, 0, sizeof(*frame));
        frame->type = type;
    }
}

int amlp_frame_set_field(amlp_frame_t *frame, uint8_t index, const char *value) {
    size_t length;
    if (frame == NULL || value == NULL || index >= AMLP_MAX_PAYLOAD_FIELDS) {
        return 0;
    }
    length = strlen(value);
    if (!validate_field(value, length)) {
        return 0;
    }
    memcpy(frame->fields[index], value, length);
    frame->fields[index][length] = '\0';
    frame->field_lengths[index] = (uint8_t)length;
    if (index >= frame->field_count) {
        frame->field_count = (uint8_t)(index + 1u);
    }
    return 1;
}

const char *amlp_type_name(amlp_type_t type) {
    switch (type) {
        case AMLP_TYPE_CMD: return "CMD";
        case AMLP_TYPE_ACK: return "ACK";
        case AMLP_TYPE_TEL: return "TEL";
        default: return NULL;
    }
}

amlp_result_t amlp_encode(
    const amlp_frame_t *frame,
    char *output,
    size_t output_capacity,
    size_t *output_length
) {
    const char *type_name;
    size_t cursor = 0u;
    size_t index;
    uint16_t crc;

    if (frame == NULL || output == NULL || output_length == NULL) {
        return AMLP_ERROR_ARGUMENT;
    }
    *output_length = 0u;
    type_name = amlp_type_name(frame->type);
    if (type_name == NULL) {
        return AMLP_ERROR_UNSUPPORTED_TYPE;
    }
    if (frame->field_count > AMLP_MAX_PAYLOAD_FIELDS) {
        return AMLP_ERROR_FORMAT;
    }

    if (output_capacity < 1u) {
        return AMLP_ERROR_CAPACITY;
    }
    output[cursor++] = '@';
    if (output_capacity - cursor < 3u) {
        return AMLP_ERROR_CAPACITY;
    }
    memcpy(&output[cursor], type_name, 3u);
    cursor += 3u;

    for (index = 0u; index < frame->field_count; ++index) {
        size_t field_length = frame->field_lengths[index];
        if (!validate_field(frame->fields[index], field_length)) {
            return AMLP_ERROR_FORMAT;
        }
        if (cursor + 1u + field_length + 7u > output_capacity ||
            cursor + 1u + field_length + 7u > AMLP_MAX_FRAME_LENGTH) {
            return AMLP_ERROR_CAPACITY;
        }
        output[cursor++] = ',';
        memcpy(&output[cursor], frame->fields[index], field_length);
        cursor += field_length;
    }

    if (cursor + 7u > output_capacity || cursor + 7u > AMLP_MAX_FRAME_LENGTH) {
        return AMLP_ERROR_CAPACITY;
    }
    crc = amlp_crc16_ccitt_false((const uint8_t *)&output[1], cursor - 1u);
    output[cursor++] = '*';
    output[cursor++] = k_hex[(crc >> 12) & 0x0Fu];
    output[cursor++] = k_hex[(crc >> 8) & 0x0Fu];
    output[cursor++] = k_hex[(crc >> 4) & 0x0Fu];
    output[cursor++] = k_hex[crc & 0x0Fu];
    output[cursor++] = '\r';
    output[cursor++] = '\n';
    *output_length = cursor;
    return AMLP_OK;
}

amlp_result_t amlp_decode(const char *data, size_t length, amlp_frame_t *frame) {
    size_t content_end;
    size_t star = 0u;
    size_t index;
    uint16_t received_crc = 0u;
    uint16_t calculated_crc;
    size_t token_start;
    uint8_t token_index = 0u;

    if (data == NULL || frame == NULL) {
        return AMLP_ERROR_ARGUMENT;
    }
    if (length > AMLP_MAX_FRAME_LENGTH || length < 10u || data[0] != '@' || data[length - 1u] != '\n') {
        return AMLP_ERROR_FORMAT;
    }
    content_end = length - 1u;
    if (content_end > 0u && data[content_end - 1u] == '\r') {
        --content_end;
    }
    for (index = 1u; index < content_end; ++index) {
        if (data[index] == '\r') {
            return AMLP_ERROR_FORMAT;
        }
        if (data[index] == '*') {
            if (star != 0u) {
                return AMLP_ERROR_FORMAT;
            }
            star = index;
        }
    }
    if (star <= 1u || star + 5u != content_end) {
        return AMLP_ERROR_FORMAT;
    }
    for (index = star + 1u; index < content_end; ++index) {
        if (!is_upper_hex(data[index])) {
            return AMLP_ERROR_FORMAT;
        }
        received_crc = (uint16_t)((received_crc << 4) | hex_value(data[index]));
    }
    calculated_crc = amlp_crc16_ccitt_false((const uint8_t *)&data[1], star - 1u);
    if (calculated_crc != received_crc) {
        return AMLP_ERROR_CRC;
    }

    amlp_frame_init(frame, AMLP_TYPE_CMD);
    token_start = 1u;
    while (token_start < star) {
        size_t token_end = token_start;
        size_t token_length;
        while (token_end < star && data[token_end] != ',') {
            ++token_end;
        }
        token_length = token_end - token_start;
        if (!validate_field(&data[token_start], token_length) || token_index >= AMLP_MAX_FIELDS) {
            return AMLP_ERROR_FORMAT;
        }
        if (token_index == 0u) {
            if (!parse_type(&data[token_start], token_length, &frame->type)) {
                return AMLP_ERROR_UNSUPPORTED_TYPE;
            }
        } else {
            uint8_t field_index = (uint8_t)(token_index - 1u);
            memcpy(frame->fields[field_index], &data[token_start], token_length);
            frame->fields[field_index][token_length] = '\0';
            frame->field_lengths[field_index] = (uint8_t)token_length;
            frame->field_count = (uint8_t)(field_index + 1u);
        }
        ++token_index;
        if (token_end == star) {
            break;
        }
        token_start = token_end + 1u;
        if (token_start == star) {
            return AMLP_ERROR_FORMAT;
        }
    }
    return token_index == 0u ? AMLP_ERROR_FORMAT : AMLP_OK;
}

void amlp_parser_init(amlp_parser_t *parser) {
    if (parser != NULL) {
        parser->length = 0u;
        parser->last_byte_ms = 0u;
        parser->active = 0u;
    }
}

amlp_result_t amlp_parser_check_timeout(amlp_parser_t *parser, uint32_t now_ms) {
    if (parser == NULL) {
        return AMLP_ERROR_ARGUMENT;
    }
    if (parser->active != 0u && (uint32_t)(now_ms - parser->last_byte_ms) >= AMLP_PARSER_TIMEOUT_MS) {
        amlp_parser_init(parser);
        return AMLP_ERROR_TIMEOUT;
    }
    return AMLP_OK;
}

amlp_parse_result_t amlp_parser_feed(
    amlp_parser_t *parser,
    uint8_t byte,
    uint32_t now_ms,
    amlp_frame_t *frame
) {
    amlp_result_t result;
    amlp_result_t timeout;
    if (parser == NULL || frame == NULL) {
        return AMLP_PARSE_ERROR;
    }
    timeout = amlp_parser_check_timeout(parser, now_ms);
    if (byte == (uint8_t)'@') {
        parser->buffer[0] = '@';
        parser->length = 1u;
        parser->last_byte_ms = now_ms;
        parser->active = 1u;
        return timeout == AMLP_ERROR_TIMEOUT ? AMLP_PARSE_ERROR : AMLP_PARSE_NONE;
    }
    if (parser->active == 0u) {
        return timeout == AMLP_ERROR_TIMEOUT ? AMLP_PARSE_ERROR : AMLP_PARSE_NONE;
    }
    if (parser->length >= AMLP_MAX_FRAME_LENGTH) {
        amlp_parser_init(parser);
        return AMLP_PARSE_ERROR;
    }
    parser->buffer[parser->length++] = (char)byte;
    parser->last_byte_ms = now_ms;
    if (byte != (uint8_t)'\n') {
        return AMLP_PARSE_NONE;
    }
    result = amlp_decode(parser->buffer, parser->length, frame);
    amlp_parser_init(parser);
    return result == AMLP_OK ? AMLP_PARSE_FRAME : AMLP_PARSE_ERROR;
}
