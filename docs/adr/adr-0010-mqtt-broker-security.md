# ADR-0010: MQTT Broker Identity, TLS Trust Chain, and ACL Authorization

**Status:** Proposed
**Date:** 2026-10-15
**Deciders:** Issue #41
**Related issues:** #41

**ID Ownership Note:** ADR-0010 is reserved for MQTT broker security (this document). ADR-0010 for dashboard safety is in PR #100 (branch `feat/dashboard-safety-adr`); this ADR will be renumbered by the dependent task after PR #102 is merged.

---

## Context

Issue #41 (Harden MQTT broker authentication, TLS and secret management) is a P1 open implementation issue that introduces or materially changes a security mechanism. Per ADR Trigger Rule 3, this requires an ADR before implementation merge.

ADR-0006 (Local Physical Command Safety) documents Layer 1 MQTT broker ACL enforcement at a high level ("per Issue #41") but does not specify broker identity verification, TLS trust chain configuration, or the full authorization boundary. ADR-0007 (Signed HTTPS OTA) does not address MQTT broker security. Neither ADR contains documented evidence of broker identity, TLS certificate trust anchor, credential storage, or session authorization scope.

Without a dedicated ADR, implementation of Issue #41 lacks an auditable decision record, and the coverage claim in the issue-to-ADR table is unsupported.

## Decision

The following architectural decisions are established for MQTT broker security and MUST be documented before Issue #41 implementation proceeds:

**Broker Identity and TLS Trust Chain:**
- Bridge and all service clients MUST verify the broker's TLS certificate against a pinned trust anchor. Self-signed certificates are acceptable if the CA cert is pinned at build time; publicly-trusted CAs are preferred where feasible.
- Broker hostname verification MUST be enforced; IP-only connections are not permitted for production deployments.
- No certificate chain validation bypass is permitted, even in non-production environments.

**Authentication:**
- All clients MUST authenticate with the broker using credentials stored in a secrets manager (not hardcoded). Supported mechanisms: TLS client certificates (preferred for services) or username/password over TLS (minimum for constrained devices).
- Bridge credentials MUST be scoped to bridge-only topics; they MUST NOT have admin or cross-tenant access.
- Long-lived static credentials MUST be rotatable without service downtime (credential versioning or dual-credential window).

**Note:** The broker uses username/password authentication over TLS (port 8883), not SASL PLAIN. SASL PLAIN transmits credentials in cleartext over the wire; TLS encrypts the entire connection, providing transport security.

**Authorization (ACL):**

The following ACL matrix defines the authorized topic patterns based on the source contracts:

- **esp32-ukit-bridge/docs/mqtt-contract.md** — defines bridge publish/subscribe behavior
- **iot-gateway/src/iot_gateway/config.py** — defines gateway subscribe patterns (`DEFAULT_TOPICS`)

| Client | Subscribe | Publish | Rationale |
|--------|-----------|---------|-----------|
| bridge | `smart-factory/{deviceId}/command/down` | `smart-factory/{deviceId}/command/ack`<br>`smart-factory/{deviceId}/telemetry`<br>`smart-factory/{deviceId}/status` | Command ingress via per-device subscription; command ACK, telemetry, and status egress |
| gateway | `smart-factory/+/command/ack`<br>`smart-factory/+/status` | — | Listens to all device ACKs and status for canonical event normalization (see `config.py` `DEFAULT_TOPICS`) |

**Notes:**
- The gateway does NOT currently subscribe to `smart-factory/+/telemetry` (future enhancement; see `models.py` EventType.TELEMETRY comment).
- The gateway does NOT currently subscribe to heartbeat topics (marked as future in `models.py` EventType.HEARTBEAT).
- ACLs for dashboard, edge-ai, and ota-manager are out of scope for this ADR; they require separate ADRs once those components are wired to MQTT.

### Positive ACL Examples (allowed)

1. **Bridge receives command:**
   - Topic: `smart-factory/ukit-00000000/command/down`
   - Client: bridge (deviceId: ukit-00000000)
   - Action: ALLOW — bridge subscribes to its own per-device command topic

2. **Bridge publishes ACK:**
   - Topic: `smart-factory/ukit-00000000/command/ack`
   - Client: bridge (deviceId: ukit-00000000)
   - Action: ALLOW — bridge publishes ACK for its own commands

3. **Gateway receives all ACKs:**
   - Topic: `smart-factory/+/command/ack`
   - Client: gateway
   - Action: ALLOW — gateway subscribes to canonical ACK stream

4. **Gateway receives all status:**
   - Topic: `smart-factory/+/status`
   - Client: gateway
   - Action: ALLOW — gateway subscribes to status updates

### Negative ACL Examples (denied)

1. **Bridge attempts to subscribe to another device's command:**
   - Topic: `smart-factory/ukit-00000001/command/down`
   - Client: bridge (deviceId: ukit-00000000)
   - Action: DENY — bridge can only subscribe to its own deviceId

2. **Bridge attempts to subscribe to telemetry:**
   - Topic: `smart-factory/ukit-00000000/telemetry`
   - Client: bridge
   - Action: DENY — bridge does not subscribe to telemetry; it only publishes it

3. **Gateway attempts to publish to bridge command topic:**
   - Topic: `smart-factory/ukit-00000000/command/down`
   - Client: gateway
   - Action: DENY — gateway only subscribes; commands originate from external systems

4. **Unrecognized topic pattern:**
   - Topic: `smart-factory/+/events/#`
   - Client: any
   - Action: DENY — no component is authorized to use this topic pattern

### Policy vs. Implementation

**This ADR establishes policy decisions**, not implementation state. The ACL matrix describes what *should* be enforced once Issue #41 is implemented. It does not claim that broker-enforced ACLs are currently active.

- Current state: Clients may honor topic conventions, but there is no broker-side ACL enforcement.
- Target state: Broker ACLs enforce the patterns in the matrix above.
- This ADR does not cover dashboard, edge-ai, or ota-manager MQTT integration — those are separate future work.

---

**Audit Gap Acknowledgement:**
The following are explicitly NOT covered by this ADR and require separate ADRs before implementation:
- Broker deployment topology (on-prem vs cloud) — covered by Trigger 6 (deployment topology) if it changes.
- Integration with a secrets management service (HashiCorp Vault, AWS Secrets Manager) — requires a dedicated ADR specifying the secret injection mechanism.
- Certificate pinning rotation policy — requires a dedicated ADR.

## Consequences

**Easier:**
- Issue #41 can now reference a specific ADR governing broker identity, TLS, and ACL decisions.
- Security review has a single authoritative record for the broker trust model.
- Credential scoping reduces blast radius of a compromised credential.

**Harder:**
- TLS client certificates require PKI infrastructure (CA, issuance, distribution, revocation).
- Broker ACL enforcement requires broker-side ACL configuration; not all brokers (e.g., public cloud IoT services) expose fine-grained topic ACLs.
- Constrained ESP32 bridge may have limited TLS stack; certificate-based auth on resource-constrained devices requires evaluation.
- Secrets manager integration adds operational complexity.

## Alternatives considered

**Option A — TLS with pre-shared key (PSK)**
- Lower computational overhead than certificate-based TLS.
- Rejected for production: PSK material must be embedded or provisioned securely; rotation requires device update.
- Acceptable as a transitional measure for constrained devices pending full PKI rollout.

**Option B — rely on network isolation (broker not exposed outside VLAN)**
- Rejected: physical factory network boundary is not a sufficient security control; TLS provides defense-in-depth and broker identity assurance even on a trusted network.

**Option C — defer to broker deployment documentation (no ADR)**
- Rejected: ADR Trigger Rule 3 requires an ADR before implementing a security mechanism change. Implementation of Issue #41 without this ADR would bypass the architecture gate.

## Evidence

- Issue #41: "Harden MQTT broker authentication, TLS and secret management"
- ADR-0006: Layer 1 MQTT broker ACL (acknowledges Issue #41 but does not detail TLS trust chain or credential scoping)
- ADR-0007: OTA over HTTPS (does not address MQTT broker security)
- `esp32-ukit-bridge/docs/mqtt-contract.md` — bridge topic contract (source of truth for bridge publish/subscribe)
- `iot-gateway/src/iot_gateway/config.py` — gateway DEFAULT_TOPICS (source of truth for gateway subscribe)
- `iot-gateway/src/iot_gateway/models.py` — EventType enum showing telemetry/heartbeat as future
- `esp32-ukit-bridge/docs/threat-safety-model.md` — threat model reference
- `docs/architecture/repository-layout.md` — module boundary rules
