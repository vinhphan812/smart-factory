#ifndef AMLP_H
#define AMLP_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define AMLP_MAX_FRAME_LENGTH 256u
#define AMLP_MAX_FIELDS 12u
#define AMLP_MAX_PAYLOAD_FIELDS 11u
#define AMLP_MAX_FIELD_LENGTH 64u
#define AMLP_PARSER_TIMEOUT_MS 250u

typedef enum {
    AMLP_TYPE_CMD = 0,
    AMLP_TYPE_ACK = 1,
    AMLP_TYPE_TEL = 2
} amlp_type_t;

typedef enum {
    AMLP_OK = 0,
    AMLP_ERROR_ARGUMENT = -1,
    AMLP_ERROR_CAPACITY = -2,
    AMLP_ERROR_FORMAT = -3,
    AMLP_ERROR_CRC = -4,
    AMLP_ERROR_UNSUPPORTED_TYPE = -5,
    AMLP_ERROR_TIMEOUT = -6
} amlp_result_t;

typedef enum {
    AMLP_PARSE_NONE = 0,
    AMLP_PARSE_FRAME = 1,
    AMLP_PARSE_ERROR = -1
} amlp_parse_result_t;

typedef struct {
    amlp_type_t type;
    uint8_t field_count;
    char fields[AMLP_MAX_PAYLOAD_FIELDS][AMLP_MAX_FIELD_LENGTH + 1u];
    uint8_t field_lengths[AMLP_MAX_PAYLOAD_FIELDS];
} amlp_frame_t;

typedef struct {
    char buffer[AMLP_MAX_FRAME_LENGTH];
    size_t length;
    uint32_t last_byte_ms;
    uint8_t active;
} amlp_parser_t;

uint16_t amlp_crc16_ccitt_false(const uint8_t *data, size_t length);
void amlp_frame_init(amlp_frame_t *frame, amlp_type_t type);
int amlp_frame_set_field(amlp_frame_t *frame, uint8_t index, const char *value);
const char *amlp_type_name(amlp_type_t type);

amlp_result_t amlp_encode(
    const amlp_frame_t *frame,
    char *output,
    size_t output_capacity,
    size_t *output_length
);

amlp_result_t amlp_decode(const char *data, size_t length, amlp_frame_t *frame);

void amlp_parser_init(amlp_parser_t *parser);
amlp_result_t amlp_parser_check_timeout(amlp_parser_t *parser, uint32_t now_ms);
amlp_parse_result_t amlp_parser_feed(
    amlp_parser_t *parser,
    uint8_t byte,
    uint32_t now_ms,
    amlp_frame_t *frame
);

#ifdef __cplusplus
}
#endif

#endif
