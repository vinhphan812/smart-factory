#include <string.h>

#include "amlp.h"
#include "ukit_endpoint.h"
#include "unity.h"

typedef struct {
    uint8_t last_frame[AMLP_MAX_FRAME_LENGTH];
    size_t last_length;
    unsigned int send_count;
    unsigned int command_count;
} fixture_t;

static int capture_send(const uint8_t *data, size_t length, void *context) {
    fixture_t *fixture = (fixture_t *)context;
    TEST_ASSERT_LESS_OR_EQUAL(sizeof(fixture->last_frame), length);
    memcpy(fixture->last_frame, data, length);
    fixture->last_length = length;
    fixture->send_count++;
    return 0;
}

static ukit_ack_status_t count_command(
    const char *command,
    const char *const *arguments,
    uint8_t argument_count,
    void *context
) {
    fixture_t *fixture = (fixture_t *)context;
    fixture->command_count++;
    if (strcmp(command, "SET_OUTPUT") == 0 && argument_count == 2u &&
        strcmp(arguments[0], "1") == 0 && strcmp(arguments[1], "1") == 0) {
        return UKIT_ACK_OK;
    }
    return UKIT_ACK_UNKNOWN_COMMAND;
}

void setUp(void) {}
void tearDown(void) {}

static void test_crc_standard_vector(void) {
    static const uint8_t vector[] = "123456789";
    TEST_ASSERT_EQUAL_HEX16(0x29B1u, amlp_crc16_ccitt_false(vector, 9u));
}

static void test_crc_golden_vectors(void) {
    /* All three AMLP body CRCs from shared/protocol-spec/test-vectors.json */
    TEST_ASSERT_EQUAL_HEX16(
        0xC942u,
        amlp_crc16_ccitt_false((const uint8_t *)"CMD,102,CONVEYOR_START,60", 27u));
    TEST_ASSERT_EQUAL_HEX16(
        0x22A0u,
        amlp_crc16_ccitt_false((const uint8_t *)"ACK,102,OK", 11u));
    TEST_ASSERT_EQUAL_HEX16(
        0x0942u,
        amlp_crc16_ccitt_false((const uint8_t *)"TEL,CONVEYOR,RUNNING,60,SENSOR1=1", 37u));
}

static void test_encode_ack_golden_vector(void) {
    amlp_frame_t frame;
    char encoded[AMLP_MAX_FRAME_LENGTH];
    size_t encoded_length = 0u;
    /* Golden vector: ACK,102,OK -> 22A0 */
    static const char expected[] = "@ACK,102,OK*22A0\r\n";

    amlp_frame_init(&frame, AMLP_TYPE_ACK);
    TEST_ASSERT_TRUE(amlp_frame_set_field(&frame, 0u, "102"));
    TEST_ASSERT_TRUE(amlp_frame_set_field(&frame, 1u, "OK"));
    TEST_ASSERT_EQUAL(AMLP_OK,
        amlp_encode(&frame, encoded, sizeof(encoded), &encoded_length));
    TEST_ASSERT_EQUAL_UINT(sizeof(expected) - 1u, encoded_length);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(
        (const uint8_t *)expected, (const uint8_t *)encoded, encoded_length);
}

static void test_encode_tel_golden_vector(void) {
    amlp_frame_t frame;
    char encoded[AMLP_MAX_FRAME_LENGTH];
    size_t encoded_length = 0u;
    /* Golden vector: TEL,CONVEYOR,RUNNING,60,SENSOR1=1 -> 0942 */
    static const char expected[] = "@TEL,CONVEYOR,RUNNING,60,SENSOR1=1*0942\r\n";

    amlp_frame_init(&frame, AMLP_TYPE_TEL);
    TEST_ASSERT_TRUE(amlp_frame_set_field(&frame, 0u, "CONVEYOR"));
    TEST_ASSERT_TRUE(amlp_frame_set_field(&frame, 1u, "RUNNING"));
    TEST_ASSERT_TRUE(amlp_frame_set_field(&frame, 2u, "60"));
    TEST_ASSERT_TRUE(amlp_frame_set_field(&frame, 3u, "SENSOR1=1"));
    TEST_ASSERT_EQUAL(AMLP_OK,
        amlp_encode(&frame, encoded, sizeof(encoded), &encoded_length));
    TEST_ASSERT_EQUAL_UINT(sizeof(expected) - 1u, encoded_length);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(
        (const uint8_t *)expected, (const uint8_t *)encoded, encoded_length);
}

static void test_shared_vectors_and_lf_decode(void) {
    amlp_frame_t command;
    amlp_frame_t decoded;
    char encoded[AMLP_MAX_FRAME_LENGTH];
    size_t encoded_length = 0u;
    /* Golden vector: CMD,102,CONVEYOR_START,60 -> C942 */
    static const char expected[] = "@CMD,102,CONVEYOR_START,60*C942\r\n";
    static const char lf_only[]   = "@CMD,102,CONVEYOR_START,60*C942\n";

    amlp_frame_init(&command, AMLP_TYPE_CMD);
    TEST_ASSERT_TRUE(amlp_frame_set_field(&command, 0u, "102"));
    TEST_ASSERT_TRUE(amlp_frame_set_field(&command, 1u, "CONVEYOR_START"));
    TEST_ASSERT_TRUE(amlp_frame_set_field(&command, 2u, "60"));
    TEST_ASSERT_EQUAL(AMLP_OK, amlp_encode(&command, encoded, sizeof(encoded), &encoded_length));
    TEST_ASSERT_EQUAL_UINT(sizeof(expected) - 1u, encoded_length);
    TEST_ASSERT_EQUAL_UINT8_ARRAY((const uint8_t *)expected, (const uint8_t *)encoded, encoded_length);
    TEST_ASSERT_EQUAL(AMLP_OK, amlp_decode(lf_only, sizeof(lf_only) - 1u, &decoded));
    TEST_ASSERT_EQUAL(AMLP_TYPE_CMD, decoded.type);
    TEST_ASSERT_EQUAL_STRING("102", decoded.fields[0]);
    TEST_ASSERT_EQUAL_STRING("CONVEYOR_START", decoded.fields[1]);
    TEST_ASSERT_EQUAL_STRING("60", decoded.fields[2]);
}

static void test_parser_restart_and_timeout(void) {
    amlp_parser_t parser;
    amlp_frame_t frame;
    static const char partial[] = "@CMD,1";
    static const char valid[] = "@ACK,102,OK*22A0\r\n";
    size_t index;
    amlp_parse_result_t result = AMLP_PARSE_NONE;

    amlp_parser_init(&parser);
    for (index = 0u; index < sizeof(partial) - 1u; ++index) {
        (void)amlp_parser_feed(&parser, (uint8_t)partial[index], 100u, &frame);
    }
    TEST_ASSERT_EQUAL(AMLP_OK, amlp_parser_check_timeout(&parser, 349u));
    TEST_ASSERT_EQUAL(AMLP_ERROR_TIMEOUT, amlp_parser_check_timeout(&parser, 350u));

    for (index = 0u; index < sizeof(valid) - 1u; ++index) {
        result = amlp_parser_feed(&parser, (uint8_t)valid[index], 400u, &frame);
    }
    TEST_ASSERT_EQUAL(AMLP_PARSE_FRAME, result);
    TEST_ASSERT_EQUAL(AMLP_TYPE_ACK, frame.type);
}

static void test_endpoint_ack_deduplicates_command(void) {
    fixture_t fixture;
    ukit_endpoint_t endpoint;
    amlp_frame_t command;
    amlp_frame_t ack;
    char encoded[AMLP_MAX_FRAME_LENGTH];
    size_t encoded_length = 0u;

    memset(&fixture, 0, sizeof(fixture));
    ukit_endpoint_init(&endpoint, capture_send, count_command, &fixture);
    amlp_frame_init(&command, AMLP_TYPE_CMD);
    TEST_ASSERT_TRUE(amlp_frame_set_field(&command, 0u, "7"));
    TEST_ASSERT_TRUE(amlp_frame_set_field(&command, 1u, "SET_OUTPUT"));
    TEST_ASSERT_TRUE(amlp_frame_set_field(&command, 2u, "1"));
    TEST_ASSERT_TRUE(amlp_frame_set_field(&command, 3u, "1"));
    TEST_ASSERT_EQUAL(AMLP_OK, amlp_encode(&command, encoded, sizeof(encoded), &encoded_length));

    ukit_endpoint_receive(&endpoint, (const uint8_t *)encoded, encoded_length, 10u);
    ukit_endpoint_receive(&endpoint, (const uint8_t *)encoded, encoded_length, 20u);

    TEST_ASSERT_EQUAL_UINT(1u, fixture.command_count);
    TEST_ASSERT_EQUAL_UINT(2u, fixture.send_count);
    TEST_ASSERT_EQUAL(AMLP_OK, amlp_decode((const char *)fixture.last_frame, fixture.last_length, &ack));
    TEST_ASSERT_EQUAL(AMLP_TYPE_ACK, ack.type);
    TEST_ASSERT_EQUAL_STRING("7", ack.fields[0]);
    TEST_ASSERT_EQUAL_STRING("OK", ack.fields[1]);
}

static void test_telemetry_fields(void) {
    fixture_t fixture;
    ukit_endpoint_t endpoint;
    amlp_frame_t telemetry;

    memset(&fixture, 0, sizeof(fixture));
    ukit_endpoint_init(&endpoint, capture_send, count_command, &fixture);
    TEST_ASSERT_EQUAL_INT(0, ukit_endpoint_send_telemetry(&endpoint, 1234u, -525, 6550u, 5u));
    TEST_ASSERT_EQUAL(AMLP_OK, amlp_decode((const char *)fixture.last_frame, fixture.last_length, &telemetry));
    TEST_ASSERT_EQUAL(AMLP_TYPE_TEL, telemetry.type);
    TEST_ASSERT_EQUAL_STRING("STATE", telemetry.fields[0]);
    TEST_ASSERT_EQUAL_STRING("1234", telemetry.fields[1]);
    TEST_ASSERT_EQUAL_STRING("-525", telemetry.fields[2]);
    TEST_ASSERT_EQUAL_STRING("6550", telemetry.fields[3]);
    TEST_ASSERT_EQUAL_STRING("5", telemetry.fields[4]);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_crc_standard_vector);
    RUN_TEST(test_crc_golden_vectors);
    RUN_TEST(test_shared_vectors_and_lf_decode);
    RUN_TEST(test_encode_ack_golden_vector);
    RUN_TEST(test_encode_tel_golden_vector);
    RUN_TEST(test_parser_restart_and_timeout);
    RUN_TEST(test_endpoint_ack_deduplicates_command);
    RUN_TEST(test_telemetry_fields);
    return UNITY_END();
}
