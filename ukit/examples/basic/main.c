/*
 * Reference integration example. Replace uart_write()/clock_read with the actual
 * uKit SDK API when the SDK and hardware documentation are available.
 */
#include "ukit_endpoint.h"

#include <stdlib.h>
#include <string.h>

static int uart_write(const uint8_t *data, size_t length, void *context) {
    (void)data;
    (void)length;
    (void)context;
    /* TODO: call the uKit SDK UART TX function. */
    return 0;
}

static ukit_ack_status_t on_command(
    const char *command,
    const char *const *arguments,
    uint8_t argument_count,
    void *context
) {
    (void)context;
    if (strcmp(command, "PING") == 0 && argument_count == 0u) {
        return UKIT_ACK_OK;
    }
    if (strcmp(command, "SET_OUTPUT") == 0 && argument_count == 2u) {
        char *end = NULL;
        long channel = strtol(arguments[0], &end, 10);
        if (end != arguments[0] && *end == '\0' && channel >= 0 && channel <= 255 &&
            (strcmp(arguments[1], "0") == 0 || strcmp(arguments[1], "1") == 0)) {
            /* TODO: set output channel to arguments[1]. */
            return UKIT_ACK_OK;
        }
        return UKIT_ACK_INVALID_ARGUMENT;
    }
    if (strcmp(command, "RESET") == 0 && argument_count == 0u) {
        /* TODO: put uKit application into a safe state. */
        return UKIT_ACK_OK;
    }
    return UKIT_ACK_UNKNOWN_COMMAND;
}

int main(void) {
    ukit_endpoint_t endpoint;
    uint8_t rx_buffer[64];
    size_t received = 0u;
    uint32_t now_ms = 0u;

    ukit_endpoint_init(&endpoint, uart_write, on_command, NULL);
    for (;;) {
        /* TODO: received = ukit_uart_read(rx_buffer, sizeof(rx_buffer)); */
        if (received != 0u) {
            ukit_endpoint_receive(&endpoint, rx_buffer, received, now_ms);
            received = 0u;
        } else {
            ukit_endpoint_check_timeout(&endpoint, now_ms);
        }
        (void)ukit_endpoint_send_telemetry(&endpoint, now_ms, 2500, 5000u, 0u);
        break; /* Omit break in real firmware. */
    }
    return 0;
}
