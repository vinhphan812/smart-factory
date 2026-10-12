#include "ukit_endpoint.h"

#include <stdio.h>
#include <string.h>

static const char *status_name(ukit_ack_status_t status) {
    switch (status) {
        case UKIT_ACK_OK: return "OK";
        case UKIT_ACK_UNKNOWN_COMMAND: return "UNKNOWN_COMMAND";
        case UKIT_ACK_INVALID_ARGUMENT: return "INVALID_ARGUMENT";
        case UKIT_ACK_INTERNAL_ERROR: return "INTERNAL_ERROR";
        default: return "INTERNAL_ERROR";
    }
}

static int parse_correlation_id(const char *value, uint32_t *result) {
    uint32_t parsed = 0u;
    size_t index;
    size_t length;
    if (value == NULL || result == NULL || value[0] == '\0' || value[0] == '0') {
        return 0;
    }
    length = strlen(value);
    for (index = 0u; index < length; ++index) {
        uint8_t digit;
        if (value[index] < '0' || value[index] > '9') {
            return 0;
        }
        digit = (uint8_t)(value[index] - '0');
        if (parsed > (UINT32_MAX - digit) / 10u) {
            return 0;
        }
        parsed = parsed * 10u + digit;
    }
    if (parsed == 0u) {
        return 0;
    }
    *result = parsed;
    return 1;
}

static int send_frame(ukit_endpoint_t *endpoint, const amlp_frame_t *frame) {
    char encoded[AMLP_MAX_FRAME_LENGTH];
    size_t encoded_length = 0u;
    if (endpoint == NULL || endpoint->send == NULL) {
        return -1;
    }
    if (amlp_encode(frame, encoded, sizeof(encoded), &encoded_length) != AMLP_OK) {
        return -1;
    }
    return endpoint->send((const uint8_t *)encoded, encoded_length, endpoint->context);
}

static int send_ack(ukit_endpoint_t *endpoint, const char *id, ukit_ack_status_t status) {
    amlp_frame_t ack;
    amlp_frame_init(&ack, AMLP_TYPE_ACK);
    if (!amlp_frame_set_field(&ack, 0u, id) ||
        !amlp_frame_set_field(&ack, 1u, status_name(status))) {
        return -1;
    }
    return send_frame(endpoint, &ack);
}

static int find_duplicate(
    const ukit_endpoint_t *endpoint,
    uint32_t correlation_id,
    ukit_ack_status_t *status
) {
    uint8_t index;
    for (index = 0u; index < UKIT_DEDUPE_SIZE; ++index) {
        if (endpoint->seen_valid[index] != 0u && endpoint->seen_ids[index] == correlation_id) {
            *status = (ukit_ack_status_t)endpoint->seen_statuses[index];
            return 1;
        }
    }
    return 0;
}

static void remember_result(
    ukit_endpoint_t *endpoint,
    uint32_t correlation_id,
    ukit_ack_status_t status
) {
    uint8_t index = endpoint->dedupe_next;
    endpoint->seen_ids[index] = correlation_id;
    endpoint->seen_statuses[index] = (uint8_t)status;
    endpoint->seen_valid[index] = 1u;
    endpoint->dedupe_next = (uint8_t)((index + 1u) % UKIT_DEDUPE_SIZE);
}

static void process_frame(ukit_endpoint_t *endpoint, const amlp_frame_t *frame) {
    uint32_t correlation_id;
    ukit_ack_status_t status;
    const char *arguments[AMLP_MAX_PAYLOAD_FIELDS - 2u];
    uint8_t argument_count;
    uint8_t index;

    if (frame->type != AMLP_TYPE_CMD || frame->field_count < 2u ||
        !parse_correlation_id(frame->fields[0], &correlation_id)) {
        return;
    }
    if (find_duplicate(endpoint, correlation_id, &status)) {
        (void)send_ack(endpoint, frame->fields[0], status);
        return;
    }

    argument_count = (uint8_t)(frame->field_count - 2u);
    for (index = 0u; index < argument_count; ++index) {
        arguments[index] = frame->fields[index + 2u];
    }
    status = endpoint->command == NULL
        ? UKIT_ACK_UNKNOWN_COMMAND
        : endpoint->command(frame->fields[1], arguments, argument_count, endpoint->context);
    remember_result(endpoint, correlation_id, status);
    (void)send_ack(endpoint, frame->fields[0], status);
}

void ukit_endpoint_init(
    ukit_endpoint_t *endpoint,
    ukit_send_fn send,
    ukit_command_fn command,
    void *context
) {
    if (endpoint != NULL) {
        memset(endpoint, 0, sizeof(*endpoint));
        amlp_parser_init(&endpoint->parser);
        endpoint->send = send;
        endpoint->command = command;
        endpoint->context = context;
    }
}

void ukit_endpoint_receive(
    ukit_endpoint_t *endpoint,
    const uint8_t *data,
    size_t length,
    uint32_t now_ms
) {
    amlp_frame_t frame;
    size_t index;
    if (endpoint == NULL || (data == NULL && length != 0u)) {
        return;
    }
    for (index = 0u; index < length; ++index) {
        if (amlp_parser_feed(&endpoint->parser, data[index], now_ms, &frame) == AMLP_PARSE_FRAME) {
            process_frame(endpoint, &frame);
        }
    }
}

void ukit_endpoint_check_timeout(ukit_endpoint_t *endpoint, uint32_t now_ms) {
    if (endpoint != NULL) {
        (void)amlp_parser_check_timeout(&endpoint->parser, now_ms);
    }
}

int ukit_endpoint_send_telemetry(
    ukit_endpoint_t *endpoint,
    uint32_t uptime_ms,
    int16_t temperature_centi_c,
    uint16_t humidity_centi_percent,
    uint16_t digital_inputs
) {
    amlp_frame_t telemetry;
    char uptime[11];
    char temperature[7];
    char humidity[6];
    char inputs[6];

    if (endpoint == NULL ||
        snprintf(uptime, sizeof(uptime), "%lu", (unsigned long)uptime_ms) < 0 ||
        snprintf(temperature, sizeof(temperature), "%d", (int)temperature_centi_c) < 0 ||
        snprintf(humidity, sizeof(humidity), "%u", (unsigned int)humidity_centi_percent) < 0 ||
        snprintf(inputs, sizeof(inputs), "%u", (unsigned int)digital_inputs) < 0) {
        return -1;
    }

    amlp_frame_init(&telemetry, AMLP_TYPE_TEL);
    if (!amlp_frame_set_field(&telemetry, 0u, "STATE") ||
        !amlp_frame_set_field(&telemetry, 1u, uptime) ||
        !amlp_frame_set_field(&telemetry, 2u, temperature) ||
        !amlp_frame_set_field(&telemetry, 3u, humidity) ||
        !amlp_frame_set_field(&telemetry, 4u, inputs)) {
        return -1;
    }
    return send_frame(endpoint, &telemetry);
}
