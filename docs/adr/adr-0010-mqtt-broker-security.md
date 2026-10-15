# ADR-0010: MQTT Broker Identity, TLS Trust Chain, and ACL Authorization

**Status:** Proposed
**Date:** 2026-10-15
**Deciders:** Issue #41
**Related issues:** #41

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
- All clients MUST authenticate with the broker using credentials stored in a secrets manager (not hardcoded). Supported mechanisms: TLS client certificates (preferred for services) or username/password with SASL PLAIN (minimum for constrained devices).
- Bridge credentials MUST be scoped to bridge-only topics; they MUST NOT have admin or cross-tenant access.
- Long-lived static credentials MUST be rotatable without service downtime (credential versioning or dual-credential window).

**Authorization (ACL):**
- Topic-level ACLs MUST enforce the read/write matrix defined below.
- ACL policy is broker-enforced, not client-honour-only.

| Client | Publish | Subscribe | rationale |
|--------|---------|-----------|-----------|
| bridge | `smart-factory/+/command/down` | `smart-factory/+/telemetry/up` | Command egress, telemetry ingress |
| gateway | `smart-factory/+/telemetry/up` | `smart-factory/+/command/down` | Canonical normalization |
| dashboard | — | `smart-factory/+/status/#` | Read-only status |
| edge-ai | — | `smart-factory/+/telemetry/up` | Anomaly detection input |
| edge-ai | `smart-factory/+/action/proposed` | — | Proposed action only (operator approval gate) |
| ota-manager | `smart-factory/+/ota/#` | `smart-factory/+/ota/#` | OTA coordination channel |

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
- `esp32-ukit-bridge/docs/threat-safety-model.md` — threat model reference
- `docs/architecture/repository-layout.md` — module boundary rules
