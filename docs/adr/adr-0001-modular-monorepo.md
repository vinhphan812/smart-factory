# ADR-0001: Modular Monorepo Structure

**Status:** Proposed
**Date:** 2026-10-14
**Deciders:** TBD (Issue #65)
**Related issues:** #65

## Context

The Smart Factory project spans multiple subsystems: ESP32 bridge firmware, uKit reference, Python gateway, physical device controllers, digital twin, AI robot, operator dashboard, and infrastructure. All of these must be developed, tested, and released together.

Alternative: split each subsystem into its own repository. This avoids repo size growth but introduces cross-repo dependency management, duplicate CI setup, inconsistent tooling, and harder atomic commits across boundaries.

## Decision

The project uses a **modular monorepo**: a single Git repository with all modules as top-level directories. Each module owns its code, tests, and CI configuration. Cross-module dependencies use versioned contracts in the root `contracts/` directory.

```
smart-factory/
├── esp32-ukit-bridge/     # ESP32-S3 firmware, AMLP, bridge tests
├── ukit/                   # Portable C99 AMLP endpoint (reference)
├── iot-gateway/            # Python MQTT ingest, normalization
├── factory-control/        # (planned) Physical device adapters
├── digital-twin/           # (planned) Digital twin
├── edge-ai-robot/          # (planned) AI robot adapter
├── dashboard/              # (planned) Operator dashboard
├── integration-tests/       # (planned) E2E reliability harness
├── infrastructure/         # (planned) Docker Compose dev stack
├── contracts/             # Cross-system schemas (validated)
└── docs/                  # Architecture, research, dev guides
```

## Consequences

**Easier:**
- Atomic commits across module boundaries (e.g., update contract schema + all consumers)
- Shared CI infrastructure and tooling
- Consistent code style and lint rules
- Single `git clone` for new contributors

**Harder:**
- Repo grows with all module history
- CI must scope to changed paths to avoid rebuilding unrelated modules
- Module-private code must not import across boundaries without contracts

## Alternatives considered

**Option A: One repo per module**
- Pros: independent release cycles, smaller checkouts
- Cons: cross-module PRs require two repos, tooling duplication, harder atomic changes
- Rejected because the system requires tight cross-module integration (MQTT contracts, schema validation)

**Option B: Git submodules**
- Pros: shared code without full repo duplication
- Cons: adds friction to development, submodule pointer management overhead
- Rejected because submodule update friction outweighs benefits for a research project

## Evidence

- `docs/architecture/repository-layout.md` — defines module map and boundary rules
- `docs/architecture/components.md` — module ownership and status
- Issue #65: "Bootstrap modular Smart Factory monorepo structure and module boundaries"
- Boundary rule 1: "code in one module must not be imported by another without an explicit versioned contract"
