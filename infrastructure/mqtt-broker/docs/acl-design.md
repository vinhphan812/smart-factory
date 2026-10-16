# MQTT Broker ACL Design

**Status:** Proposed — Issue #41

## Problem

The bridge credential must be restricted to subscribing only to its own device's command topic. Cross-device command injection must be denied by the broker ACL.

## Why MQTT Wildcards Don't Work in ACLs

### The + wildcard in topic patterns ≠ permission to subscribe to any device

The `+` MQTT single-level wildcard is valid for **subscribing** to multiple topics (e.g., `smart-factory/+/command/down` matches `smart-factory/ukit-00000000/command/down` **and** `smart-factory/ukit-00000001/command/down`).

However, in a mosquitto ACL file, `topic read smart-factory/+/command/down` means: *"this user may subscribe to any topic matching this pattern"*. That includes `smart-factory/ukit-00000001/command/down` — a different device's command topic.

This is **not** device isolation.

### Why environment variable expansion doesn't solve it

One might try:

```
topic read smart-factory/$MQTT_BRIDGE_USERNAME/command/down
```

Mosquitto ACL files do **not** expand environment variables. The `$MQTT_BRIDGE_USERNAME` would be treated as a literal string (or cause a parse error in newer versions). The solution must use literal strings.

### Why single-credential + multiple-topic doesn't work

Using ONE credential named `bridge` with:

```
user bridge
topic read smart-factory/ukit-00000000/command/down
topic read smart-factory/ukit-00000001/command/down
```

still allows the `bridge` credential to subscribe to BOTH devices' commands — defeating the isolation requirement.

## Correct Design: Per-Device Credentials

### Rule

The bridge credential's **username MUST equal the deviceId**, and the ACL must use the **literal username string** as the deviceId in the topic path.

| deviceId          | MQTT_BRIDGE_USERNAME | ACL topic line                                      |
|-------------------|---------------------|-----------------------------------------------------|
| ukit-00000000     | ukit-00000000       | `topic read smart-factory/ukit-00000000/command/down` |
| ukit-00000001     | ukit-00000001       | `topic read smart-factory/ukit-00000001/command/down` |
| ukit-00000002     | ukit-00000002       | `topic read smart-factory/ukit-00000002/command/down` |

### How it works

When the bridge connects with username `ukit-00000000`, the broker matches:

```
CONNECT username=ukit-00000000
  → ACL user block: user ukit-00000000
  → topic read smart-factory/ukit-00000000/command/down
     → SUBSCRIBE to smart-factory/ukit-00000000/command/down  ✓ ALLOWED
     → SUBSCRIBE to smart-factory/ukit-00000001/command/down  ✗ DENIED (no matching ACL line)
```

### How mosquitto processes ACLs

1. Mosquitto extracts the username from the CONNECT packet.
2. It searches for `user <username>` in the ACL file.
3. For each `topic`/`pattern` directive under that user block, it checks the subscribe topic against the pattern.
4. If no matching ACL line allows the subscription, it is **denied**.

Since the username IS the deviceId, and the ACL topic path uses that same literal string, the bridge can only read its own command topic.

## ACL File Generation

The `init.sh` entrypoint writes the ACL file with the **literal** value of `MQTT_BRIDGE_USERNAME` (not an env var reference):

```sh
user ${MQTT_BRIDGE_USERNAME}
topic read smart-factory/${MQTT_BRIDGE_USERNAME}/command/down
```

This means if `MQTT_BRIDGE_USERNAME=ukit-00000000`, the ACL file contains:

```
user ukit-00000000
topic read smart-factory/ukit-00000000/command/down
```

## Adding a Second Bridge

1. Choose a unique deviceId for the new bridge (e.g., `ukit-00000001`).
2. Add a new credential pair to `.env`:
   ```env
   MQTT_BRIDGE_USERNAME_2=ukit-00000001
   MQTT_BRIDGE_PASSWORD_2=...
   ```
3. Modify `init.sh` to add the second credential and ACL block (or use a loop).
4. Each bridge binary must be compiled with its deviceId matching the credential username.

## Negative Test Requirement

The integration test `test_mqtt_security_broker.py` MUST verify that a bridge credential cannot subscribe to another device's command topic. See the test file for the exact procedure.

## References

- [ADR-0010](docs/adr/adr-0010-mqtt-broker-security.md) — broker identity, TLS, and ACL authorization
- [ADR-0002](docs/adr/adr-0002-bridge-mqtt-amlp-contract.md) — bridge MQTT ↔ AMLP contract and topic patterns
- `infrastructure/mqtt-broker/entrypoint.d/init.sh` — ACL generation script
