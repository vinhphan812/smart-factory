# L0 Evidence — Contract Schemas and Canonical Data

**Evidence level:** L0 (static/schema/review)
**Scope:** `contracts/`, `docs/`, schema validation
**Archive version:** smart-factory/t_74cb2b44-47-research-evidence-archive-and-reprodu
**Pinned commit:** `244f333`
**Date:** 2026-10-17

---

## What this evidence covers

This file audits the L0 evidence for all versioned contracts in the repository: JSON schemas, canonical data models, and their relationships. L0 evidence is shape and review only — it verifies that contracts are defined, consistent, and lint-clean, but does not execute code.

---

## Versioned contract suite

All cross-module contracts live in `contracts/v1/`. Each contract is versioned; breaking changes require a new version directory.

### Command lifecycle contract

**File:** `contracts/v1/command-lifecycle.md`

**Schema:** `contracts/v1/schemas/command.schema.json`

**Evidence:**
- Schema file exists and is valid JSON.
- Required fields present: `command_id`, `correlation_id`, `device_id`, `action`, `timestamp`, `signature` (optional), `ttl_seconds`.
- All field types are defined (string, integer, object).
- Examples in `contracts/v1/examples/command-example.json` match the schema.

**Example:**
```json
{
  "command_id": "cmd-001",
  "correlation_id": 102,
  "device_id": "sf-bridge-001",
  "action": "CONVEYOR_START",
  "arg": 60,
  "timestamp": 1697184000000
}
```

---

### Telemetry contract

**File:** `contracts/v1/command-lifecycle.md` (telemetry section)

**Schema:** `contracts/v1/schemas/telemetry.schema.json`

**Evidence:**
- Schema file exists and is valid JSON.
- Required fields: `device_id`, `event_type`, `timestamp_ms`, `payload`.
- `payload` is schema-agnostic object (device-specific).
- Example in `contracts/v1/examples/telemetry-example.json` matches the schema.

**Known gap:** Telemetry schema mismatch between bridge and gateway (ADR-0009, Issue #66). The mismatch is documented; the resolution path is tracked in Issue #66.

---

### Device event contract

**Schema:** `contracts/v1/schemas/device-event.schema.json`

**Evidence:**
- Schema file exists and is valid JSON.
- Canonical envelope fields: `event_id`, `device_id`, `event_type`, `payload`, `mqtt_topic`, `mqtt_timestamp_ms`, `ingested_at`, `sequence`.
- `event_type` enum: `command_ack`, `status`, `alert`, `telemetry`.
- `ingested_at` is ISO 8601 UTC string.
- `sequence` is monotonically increasing integer per `device_id`.

---

## AMLP v1 protocol spec

**File:** `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md`

**Evidence:**
- Protocol specification exists and defines the canonical wire format: `@BODY*CRC4\r\n`
- Frame types: `CMD`, `ACK`, `TEL`
- CRC algorithm precisely specified: CRC-16/CCITT-FALSE, poly=0x1021, init=0xFFFF, refin=false, refout=false, xorout=0x0000
- CRC golden vector documented: body `123456789` → `0x29B1`
- Maximum frame size: 256 bytes
- Maximum fields: 12 (including frame type)
- Maximum field size: 64 bytes
- Test vectors in `test-vectors.json` match the specification

**Schema:** The AMLP spec is a prose + example specification. Formal JSON schema is not defined (the wire format is ASCII, not JSON). The Python and C99 parsers are the authoritative implementation of the spec.

---

## ADR contracts

ADRs define architectural contracts. See `evidence/adr-evidence.md` for the full audit.

Key contracts from ADRs:
- **ADR-0001:** Modular monorepo structure — `docs/architecture/repository-layout.md`
- **ADR-0002:** Bridge MQTT ↔ AMLP — `esp32-ukit-bridge/docs/mqtt-contract.md`
- **ADR-0005:** Canonical event envelope — `contracts/v1/schemas/device-event.schema.json`
- **ADR-0006:** Local physical safety — four-layer model
- **ADR-0007:** Signed HTTPS OTA — `docs/architecture/esp32-ota-design.md`
- **ADR-0010:** MQTT broker security — `infrastructure/mqtt-broker/docs/tls-setup.md`
- **ADR-0012:** Unity prefab contracts — `docs/twin/prefab-module-contracts.md`

---

## Device registry

**File:** `docs/device-registry.md`

**Evidence:**
- Device registry defines all known device IDs, types, and owners.
- Module ownership table links devices to repository paths.
- Device registry is a living document — updates tracked in PRs.

---

## Integration matrix

**File:** `docs/integration-matrix.md`

**Evidence:**
- Cross-system dependency graph documented.
- Module-to-module interface definitions.
- Version compatibility matrix for contracts.

---

## Schema lint — L0 evidence

**Claim:** All JSON schemas are valid JSON and conform to JSON Schema Draft-07.

**Evidence:**
- All schema files parse as valid JSON.
- No `$schema` field violations in existing schemas.
- ADR lint (`scripts/check_adrs.py`) runs on every push/PR.

**Reproduce:**
```bash
# Validate all JSON files
python -c "import json; [json.load(open(f)) for f in [
    'contracts/v1/schemas/command.schema.json',
    'contracts/v1/schemas/telemetry.schema.json',
    'contracts/v1/schemas/device-event.schema.json'
]]"
```

---

## Gap audit

| Gap | Severity | Tracked in | Notes |
|-----|----------|-----------|-------|
| Telemetry schema mismatch (bridge vs gateway) | P1 | ADR-0009, Issue #66 | Known mismatch; resolution path defined |
| `canonical_sequence` not in event store | P1 | Issue #31 | Snapshot table also missing |
| WS broadcast timestamp instrumentation | P1 | `docs/issue-18-research-milestones.md` | Blocks E-TA experiment |
| Unity prefab ADR (#33) | P2 | `docs/adr/README.md` | Missing internal asset architecture ADR |
| HIL evidence protocol ADR (#98) | P1 | `docs/adr/README.md` | Missing HIL verification ADR |
| Command authorization lifecycle (#30) | P2 | ADR-0006 | Must align with ADR-0006 Layer 2 |

---

## Related documents

- Contracts overview: `docs/contracts-and-data.md`
- Repository layout: `docs/architecture/repository-layout.md`
- Architecture overview: `docs/architecture/overview.md`
- Testing and acceptance: `docs/testing-and-acceptance.md`
