# Cross-system contracts — Smart Factory

**Owner:** monorepo foundation / interface governance, Issue #65.

This root module holds **validated versioned interfaces shared by multiple root modules** (gateway, bridge, factory control, Digital Twin, dashboard, robot), including canonical event envelopes, device identity, telemetry semantics and authorized command schemas.

## Source of truth

- `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md` remains bridge-local; do **not** copy AMLP into this directory.
- `contracts/v1/` holds cross-system schemas: command-lifecycle.md, command.schema.json, telemetry.schema.json, device-event.schema.json, and examples.
- `contracts/v2/` holds v2 schemas: telemetry.schema.json and examples.
- `contracts/gateway/` holds gateway-specific canonical documentation including telemetry-schema-v2.md.
- `contracts/physical/` holds the physical layer contracts: the L0 capability matrix, the factory interface, the end-to-end sequence, and the **versioned executable capability schema** (`capability-schema.v1.json`) with its contract note. The capability schema is a **planning artefact** (`contract_status: planned_controller_contract_v0.1`); it does not extend the published v1 bridge command envelope. See [ADR-0020](../docs/adr/adr-0020-versioned-capability-schema-and-admission-layer.md).
- In particular, `telemetry.schema.json` requires `timestamp` and `state`, whereas issue #66 firmware TEL payload uses `received_at_ms`, `values`, and `pairs`. This mismatch has been resolved by v2 schema (Issue #166, `contracts/gateway/telemetry-schema-v2.md`).
- A schema is **canonical** only when its version, producer, consumers, examples, validation tests and compatibility policy are documented. No duplicate authoritative schema copies.
- See [ADR-0009: Telemetry Schema Compatibility](../docs/adr/adr-0009-telemetry-schema-compatibility.md) for the known mismatch between `telemetry.schema.json` and the actual bridge telemetry format.

## Schema governance

1. Inventory every bridge-local contract and all references in code, docs, CI and fixtures.
2. Classify as **bridge-private** (leave in the bridge) or **cross-system** (move under root, with compatibility and versioning).
3. Validate producer/consumer payloads; document aliases, translators and migration paths if current shapes differ.
4. Move validated schemas, update references and tests in a focused commit/PR; preserve deployed topics and backwards compatibility.

**Status:** `v1/` schemas moved from `esp32-ukit-bridge/contracts/v1/`. Telemetry schema compatibility audit pending.
