# Cross-system contracts — Smart Factory

**Owner:** monorepo foundation / interface governance, Issue #65.

This root module holds **validated versioned interfaces shared by multiple root modules** (gateway, bridge, factory control, Digital Twin, dashboard, robot), including canonical event envelopes, device identity, telemetry semantics and authorized command schemas.

## Source of truth

- `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md` remains bridge-local; do **not** copy AMLP into this directory.
- `contracts/v1/` holds cross-system schemas: command-lifecycle.md, command.schema.json, telemetry.schema.json, device-event.schema.json, and examples.
- In particular, `telemetry.schema.json` requires `timestamp` and `state`, whereas issue #66 firmware TEL payload uses `received_at_ms`, `values`, and `pairs`. This mismatch requires a versioned compatibility decision before promoting the file as canonical. See `v1/schemas/telemetry.schema.json` and `esp32-ukit-bridge/docs/mqtt-contract.md` for current wire formats.
- A schema is **canonical** only when its version, producer, consumers, examples, validation tests and compatibility policy are documented. No duplicate authoritative schema copies.

## Schema governance

1. Inventory every bridge-local contract and all references in code, docs, CI and fixtures.
2. Classify as **bridge-private** (leave in the bridge) or **cross-system** (move under root, with compatibility and versioning).
3. Validate producer/consumer payloads; document aliases, translators and migration paths if current shapes differ.
4. Move validated schemas, update references and tests in a focused commit/PR; preserve deployed topics and backwards compatibility.

**Status:** `v1/` schemas moved from `esp32-ukit-bridge/contracts/v1/`. Telemetry schema compatibility audit pending.
