# ADR-0010: MQTT Broker Identity, TLS Trust Chain, and ACL Authorization

**Status:** Proposed
**Date:** 2026-10-15
**Deciders:** Issue #41
**Related issues:** #41

## Context

Issue #41 (Harden MQTT broker authentication, TLS and secret management) is a P1 open implementation issue that introduces or materially changes a security mechanism. Per ADR Trigger Rule 3, this requires an ADR before implementation merge.

ADR-0006 (Local Physical Command Safety) documents Layer 1 MQTT broker ACL enforcement at a high level ("per Issue #41") but does not specify broker identity verification, TLS trust chain configuration, or the authorization boundary. ADR-0007 (Signed HTTPS OTA) does not address MQTT broker security. Neither ADR records broker identity, TLS certificate trust-anchor, credential-storage, or session-authorization evidence.

ADR-0010 is reserved for this broker-security decision. PR #100 must use ADR-0011; this ADR must not be renumbered or repurposed.

The current bridge MQTT contract defines only these per-device topics:

| Topic | Bridge direction |
|---|---|
| `smart-factory/{deviceId}/command/down` | Subscribe |
| `smart-factory/{deviceId}/command/ack` | Publish |
| `smart-factory/{deviceId}/telemetry` | Publish |
| `smart-factory/{deviceId}/status` | Publish |

The gateway configuration subscribes to `smart-factory/+/command/ack` and `smart-factory/+/status`; PR #100 additionally proposes to add `smart-factory/+/telemetry` and `smart-factory/+/heartbeat`. Heartbeat topic is not in the current bridge contract and requires a separate accepted decision before inclusion. This ADR proposes the authorization policy for gateway ingestion of the bridge-published telemetry, status, and command-ack topics. It does not claim that a broker ACL, TLS listener, or client configuration is already implemented.

## Decision

The following policy is proposed for MQTT broker security before Issue #41 implementation proceeds.

### Broker identity and TLS trust chain

- Bridge and service clients MUST verify the broker TLS certificate against a configured trust anchor.
- Broker hostname verification MUST be enforced for production deployments; IP-only connections are not permitted for production deployments.
- Certificate-chain validation bypass is not permitted.
- Whether the trust anchor is a pinned private CA or a publicly trusted CA, and how it rotates, requires implementation-specific review before an Accepted ADR or deployment claim.

### Authentication

- Clients MUST authenticate in the MQTT CONNECT packet with a username and password over a TLS-protected connection, unless a later accepted decision selects a different MQTT authentication mechanism.
- Credentials MUST NOT be hard-coded or emitted in MQTT payloads, status, or logs.
- Bridge credentials MUST be scoped to the bridge identity and its permitted topics; they MUST NOT grant administration or cross-device access.
- Credential rotation must be designed before implementation; this Proposed policy does not establish an implemented rotation mechanism.

### Authorization (proposed ACL policy)

The broker is intended to enforce topic-level ACLs. The following is the proposed enforcement table, grounded only in current bridge topic forms. `{deviceId}` represents the identity-bound bridge device and `+` represents a gateway subscription across device IDs.

| Client identity | Allow publish | Allow subscribe | Rationale |
|---|---|---|---|
| Bridge for `{deviceId}` | `smart-factory/{deviceId}/command/ack`, `smart-factory/{deviceId}/telemetry`, `smart-factory/{deviceId}/status` | `smart-factory/{deviceId}/command/down` | Matches the bridge contract: commands enter the bridge; ACK, telemetry, and status leave it. |
| Gateway | — | `smart-factory/+/telemetry`, `smart-factory/+/status`, `smart-factory/+/command/ack` | Gateway ingests bridge-origin telemetry, status, and completion/validation ACKs. |

Heartbeat is not included because the current bridge MQTT contract does not define a heartbeat topic. No `/telemetry/up`, `/status/#`, `action/proposed`, or `ota/#` pattern is part of this current ACL enforcement table.

### ACL examples

Positive examples under the proposed policy:

- A bridge credential bound to `ukit-00000000` may subscribe to `smart-factory/ukit-00000000/command/down`.
- That bridge credential may publish telemetry to `smart-factory/ukit-00000000/telemetry`, status to `smart-factory/ukit-00000000/status`, and ACKs to `smart-factory/ukit-00000000/command/ack`.
- A gateway credential may subscribe to `smart-factory/+/telemetry`, `smart-factory/+/status`, and `smart-factory/+/command/ack`.

Negative examples that the proposed broker ACL must deny:

- A bridge credential for `ukit-00000000` subscribing to `smart-factory/ukit-00000001/command/down` (cross-device command subscription).
- A bridge credential subscribing to `smart-factory/ukit-00000000/telemetry` or `smart-factory/ukit-00000000/status` (bridge-origin topics are publish-only for the bridge).
- A gateway credential publishing to `smart-factory/ukit-00000000/telemetry`, `smart-factory/ukit-00000000/status`, or `smart-factory/ukit-00000000/command/ack` (bridge-origin topics).
- Either credential publishing or subscribing to an unknown pattern such as `smart-factory/ukit-00000000/unknown`.

This is a **Proposed policy**, not evidence of implemented broker enforcement. A future implementation must configure the selected broker and supply separate verification evidence for TLS and every allow/deny case.

## Consequences

**Easier:**
- Issue #41 has a specific decision record for broker identity, TLS, MQTT CONNECT credentials, and ACL scope.
- The bridge and gateway topic directions have a single contract-grounded authorization boundary.
- Identity-bound bridge credentials reduce the impact of a compromised bridge credential.

**Harder:**
- Broker-side ACL configuration and negative authorization tests are required before this policy can be considered enforced.
- TLS trust-anchor provisioning, hostname verification, and credential rotation require operational design and test evidence.
- The constrained ESP32 bridge requires implementation validation; this ADR does not establish hardware or production TLS evidence.

## Alternatives considered

**Option A — rely on network isolation (broker not exposed outside VLAN)**
- Rejected: a factory network boundary is not a sufficient security control; TLS and authorization provide defence in depth.

**Option B — client-side topic conventions without broker ACLs**
- Rejected: client convention cannot prevent a compromised client from publishing or subscribing outside its intended scope.

**Option C — defer broker security to deployment documentation (no ADR)**
- Rejected: ADR Trigger Rule 3 requires an ADR before implementing a material security-mechanism change.

## Evidence

- `esp32-ukit-bridge/docs/mqtt-contract.md` — current bridge topic names and publish/subscribe directions.
- `iot-gateway/src/iot_gateway/config.py` — gateway MQTT credential configuration and current ACK/status subscriptions.
- Issue #41 — "Harden MQTT broker authentication, TLS and secret management".
- ADR-0006 — local physical command safety references broker ACLs at a high level but does not define broker identity, TLS trust, or topic authorization.
- ADR-0007 — signed HTTPS OTA does not define MQTT broker security.
