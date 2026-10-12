/* PlatformIO native build harness for the portable C99 reference endpoint. */
#include "ukit_endpoint.h"

#include <stdio.h>
#include <string.h>

static int write_bytes(const uint8_t *data, size_t length, void *context) {
    (void)context;
    return fwrite(data, 1u, length, stdout) == length ? 0 : -1;
}

static ukit_ack_status_t handle_command(
    const char *command,
    const char *const *arguments,
    uint8_t argument_count,
    void *context
) {
    (void)arguments;
    (void)context;
    if (strcmp(command, "PING") == 0 && argument_count == 0u) {
        return UKIT_ACK_OK;
    }
    return UKIT_ACK_UNKNOWN_COMMAND;
}

int main(void) {
    ukit_endpoint_t endpoint;
    ukit_endpoint_init(&endpoint, write_bytes, handle_command, NULL);
    return ukit_endpoint_send_telemetry(&endpoint, 1000u, 2500, 5000u, 0u);
}
