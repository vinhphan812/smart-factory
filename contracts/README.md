# Cross-system contracts — Smart Factory

**Owner:** monorepo foundation / interface governance, Issue #65.

This root module holds **validated versioned interfaces shared by multiple root modules** (gateway, bridge, factory control, Digital Twin, dashboard, robot), including canonical event envelopes, device identity, telemetry semantics and authorized command schemas.

## Source of truth and migration gate

- `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md` remains bridge-local; do **not** copy AMLP into this directory.
- Existing `esp32-ukit-bridge/contracts/v1/` currently includes files named `device-event.schema.json`, `command.schema.json` and `telemetry.schema.json`, some of which **describe cross-system contracts** despite their location. Their schema definitions must be audited against actual current ESP32 MQTT payloads and Gateway normalization before adopting/moving them as the canonical root contracts. Moving files is **not** permission to change wire formats.
- In particular, existing `telemetry.schema.json` requires `timestamp` and `state`, whereas issue #66 firmware TEL payload uses `received_at_ms`, `values`, and `pairs`. This mismatch requires a versioned compatibility decision before promoting the file to a canonical root schema.
- A schema is **canonical** only when its version, producer, consumers, examples, validation tests and compatibility policy are documented. No duplicate authoritative schema copies.

## Acceptance of contract extraction (#65)

1. Inventory every bridge-local contract and all references in code, docs, CI and fixtures.
2. Classify as **bridge-private** (leave in the bridge) or **cross-system** (move under root, with compatibility and versioning).
3. Validate producer/consumer payloads; document aliases, translators and migration paths if current shapes differ.
4. Move the validated shared schemas, update references and tests in a separate focused commit/PR; preserve deployed topics and backwards compatibility.

**Status:** GOVERNANCE SCAFFOLD ONLY. No newly validated root schemas are claimed by this README.
