#ifndef UKIT_ENDPOINT_H
#define UKIT_ENDPOINT_H

#include "amlp.h"

#ifdef __cplusplus
extern "C" {
#endif

#define UKIT_DEDUPE_SIZE 8u

typedef enum {
    UKIT_ACK_OK = 0,
    UKIT_ACK_UNKNOWN_COMMAND = 1,
    UKIT_ACK_INVALID_ARGUMENT = 2,
    UKIT_ACK_INTERNAL_ERROR = 3
} ukit_ack_status_t;

typedef int (*ukit_send_fn)(const uint8_t *data, size_t length, void *context);

typedef ukit_ack_status_t (*ukit_command_fn)(
    const char *command,
    const char *const *arguments,
    uint8_t argument_count,
    void *context
);

typedef struct {
    amlp_parser_t parser;
    ukit_send_fn send;
    ukit_command_fn command;
    void *context;
    uint32_t seen_ids[UKIT_DEDUPE_SIZE];
    uint8_t seen_statuses[UKIT_DEDUPE_SIZE];
    uint8_t seen_valid[UKIT_DEDUPE_SIZE];
    uint8_t dedupe_next;
} ukit_endpoint_t;

void ukit_endpoint_init(
    ukit_endpoint_t *endpoint,
    ukit_send_fn send,
    ukit_command_fn command,
    void *context
);

void ukit_endpoint_receive(
    ukit_endpoint_t *endpoint,
    const uint8_t *data,
    size_t length,
    uint32_t now_ms
);

void ukit_endpoint_check_timeout(ukit_endpoint_t *endpoint, uint32_t now_ms);

int ukit_endpoint_send_telemetry(
    ukit_endpoint_t *endpoint,
    uint32_t uptime_ms,
    int16_t temperature_centi_c,
    uint16_t humidity_centi_percent,
    uint16_t digital_inputs
);

#ifdef __cplusplus
}
#endif

#endif
