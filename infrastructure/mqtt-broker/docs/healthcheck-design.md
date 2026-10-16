# MQTT Broker Healthcheck Design

**Status:** Proposed — Issue #41

## Problem

The original healthcheck used:

```yaml
healthcheck:
  test: ["CMD", "mosquitto_sub", "-C", "1", "-W", "5", "-t", "smart-factory/+/command/down"]
```

This has two problems:

1. **False negatives**: `mosquitto_sub -C 1 -W 5` waits up to 5 seconds for a message. If no commands are published during that window (normal operation — commands are infrequent), the healthcheck times out and Docker marks the container **unhealthy** even though the broker is perfectly healthy.

2. **ACL issues**: The mosquitto_sub healthcheck runs as the mosquitto process user (inside the container), not as any registered client. The healthcheck's access to topics depends on whether `allow_anonymous` is true or whether the mosquitto user has implicit ACL access.

## Solutions

### Option A (Recommended): Subscribe to a Broker-Internal Topic

Subscribe to `$SYS/broker/clients/connected` — a broker-published topic that updates whenever a client connects or disconnects.

```yaml
healthcheck:
  test: ["CMD-SHELL", "mosquitto_sub -C 1 -W 3 -t '$SYS/broker/clients/connected' || exit 1"]
```

This topic is published by mosquitto itself on every change. It updates frequently enough that the 3-second window almost always receives at least one message during normal operation.

**Limitation**: If the broker is running but completely idle (no client ever connects), this still times out. For a broker in a deployed system, there should always be at least one client connected.

### Option B: Remove Healthcheck Entirely

Docker restarts the container on crash (exit non-zero). If mosquitto exits cleanly, the container stays up with no healthcheck overhead.

```yaml
healthcheck:
  disable: true
```

This is the simplest option and avoids false negatives. Use this if you prefer to rely on `restart: unless-stopped` rather than a probing healthcheck.

### Option C: Credential Verification

Use `mosquitto_passwd` to verify the credentials file is readable and the credentials are valid (without connecting to the broker):

```yaml
healthcheck:
  test: ["CMD-SHELL", "echo 'Testing credential validity' && mosquitto_passwd -c /dev/null testuser testpass || true"]
```

This only verifies the password utility works, not the broker itself.

### Option D: Use mosquitto_ctrl (mosquitto 2.x)

mosquitto 2.x provides `mosquitto_ctrl` for broker management:

```yaml
healthcheck:
  test: ["CMD-SHELL", "timeout 3 mosquitto_ctrl gateway looptime 2 || exit 1"]
```

Requires mosquitto 2.x broker plugin configuration. Not tested in this project.

## Selected Approach

**Option B (remove healthcheck)** is the safest for the current deployment because:

- `restart: unless-stopped` handles crashes cleanly.
- No false-negative healthchecks marking a healthy broker as unhealthy.
- Avoids the complexity of choosing a topic that always has traffic.

For production monitoring, use an external tool (e.g., MQTT Explorer, or a separate monitoring client with credentials) rather than the container healthcheck.

## Implementation

The current `docker-compose.yml` does NOT define a `healthcheck` key on the `mqtt` service. This is intentional — Option B is applied. If you need a healthcheck, add one based on Option A above to `infrastructure/mqtt-broker/config/healthcheck-compose-override.yaml` rather than the main compose file.

## References

- `docker-compose.yml` — current compose with no healthcheck
- `infrastructure/mqtt-broker/entrypoint.d/init.sh` — entrypoint that writes mosquitto.conf
