# ADR-0016: Lineage Module Deduplication, Persistence Boundary and Concurrency Model

**Status:** Proposed
**Date:** 2026-10-23
**Deciders:** Vinh Phan (System Architect)
**Related issues:** PR #242, Finding 4

## Context
During Maintainer Review Iteration #3 on PR #242, Finding 4 identified that `iot-gateway/src/iot_gateway/lineage.py` and `factory-control/src/lineage.py` were 463-line near-identical duplicates. Both defined separate in-memory `JobStore` and `MaterialStore` singletons, resulting in lineage state being lost on process restart and not shared across factory backend services. Furthermore, durability and concurrent-writer semantics were not explicitly defined.

## Decision
1. **Canonical Owner**: We establish `iot-gateway/src/iot_gateway/lineage.py` as the single authoritative owner of the job and material lineage state model and store logic, in accordance with repository root-module ownership rules (backend services are siblings at repository root).
2. **Deduplication**: We remove `factory-control/src/lineage.py` entirely, ensuring no duplicate copy of the lineage state model remains in the repository.
3. **Durability & Persistence**: We implement durable persistence for `JobStore` and `MaterialStore` backed by SQLite/SQLAlchemy tables (`lineage_jobs`, `lineage_materials`) sharing the gateway database (`gateway.db`). Authoritative event IDs (UUIDv4) and event logs ensure complete traceability. State survives process restarts.
4. **Concurrency Model**: We adopt single-writer serialization via aiosqlite transaction locking and busy timeouts combined with idempotent event ID uniqueness constraints, ensuring race-free state transitions and deterministic audit logs under concurrent operations.

## Consequences
- **Easier**: Unified lineage implementation eliminates code drift and state synchronization bugs between services; restarts no longer flush active job and material lineage state.
- **Harder / Trade-offs**: Requires async session management for database operations, requiring careful handling in API handlers.
- **Risks Mitigated**: State loss upon gateway restart and split-brain lineage state between duplicate modules are fully resolved.

## Alternatives considered
- **Retain In-Memory Duplicate Stores**: Rejected because state is volatile, lost on restart, and violates DRY and architectural encapsulation.
- **Microservice Event Bus (Kafka/RabbitMQ)**: Rejected as over-engineered for the mini-factory scale; embedded SQLite with aiosqlite provides sufficient durability and zero operational overhead.

## Evidence
- `iot-gateway/src/iot_gateway/lineage.py`
- `iot-gateway/tests/test_lineage.py`
- PR #242 Maintainer Review Iteration #3 Finding 4 remediation.
