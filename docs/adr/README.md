# Architecture Decision Records — Smart Factory

Owner: Issue #65 (monorepo foundation)

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-0001](adr-0001-modular-monorepo.md) | Modular Monorepo Structure | Proposed | 2026-10-14 |
| [ADR-0002](adr-0002-bridge-mqtt-amlp-contract.md) | Bridge MQTT ↔ AMLP Contract | Proposed | 2026-10-14 |
| [ADR-0003](adr-0003-digital-twin-engine.md) | Digital Twin Engine: Unreal vs Unity | Proposed | 2026-10-14 |
| [ADR-0004](adr-0004-mega-sdk-boundary.md) | Mega SDK Boundary: Portable C99 vs UBTEDU | Proposed | 2026-10-14 |
| [ADR-0005](adr-0005-gateway-canonical-events.md) | Gateway Canonical Event Envelope | Proposed | 2026-10-14 |
| [ADR-0006](adr-0006-local-physical-safety.md) | Local Physical Command Safety | Proposed | 2026-10-14 |
| [ADR-0007](adr-0007-signed-ota-ab-rollback.md) | Signed HTTPS OTA with A/B Rollback | Proposed | 2026-10-14 |
| [ADR-0008](adr-0008-ota-manager-event-driven.md) | Event-driven OtaManager (No Dedicated FreeRTOS Task) | Proposed | 2026-10-14 |
| [ADR-0009](adr-0009-telemetry-schema-compatibility.md) | Telemetry Schema Compatibility | Proposed | 2026-10-14 |

## Status conventions

- **Proposed** — recorded, pending explicit approval evidence
- **Accepted** — approved by reviewer with documented acceptance
- **Superseded** — replaced by a later ADR (link to replacement)
- **Deprecated** — no longer applicable

## Creating a new ADR

1. Copy `adr-TEMPLATE.md` to `adr-XXXX-name.md`
2. Fill in all sections
3. Add entry to this index
4. Link from relevant issues

## Governance

ADRs are governed by Issue #79 (ADR governance). CI lint checks and architecture gates are implemented in Issue #80:
- **Linter script:** `scripts/check_adrs.py` validates ADR naming, metadata, required sections (Context, Decision, Consequences, Alternatives considered, Evidence), status values, and README index synchronization.
- **Architecture Impact Gate:** Any PR modifying architectural paths (`docs/architecture/`, `src/`, `iot-gateway/src/`, `esp32-ukit-bridge/`, `digital-twin/`) requires an accompanying ADR in `docs/adr/` unless exempted via `skip-adr` label, `[skip-adr]` commit message, or `FORCE_BYPASS_ADR=1` break-glass exception.
- **Workflow:** `.github/workflows/adr-lint.yml` runs automated linter checks and pytest fixture tests (TC-1 through TC-6) on push and pull requests.
