# ADR-0020: Versioned Physical Capability Schema and Pre-Actuator Admission Layer

**Status:** Proposed
**Date:** 2026-10-24
**Deciders:** Vinh Phan, System Architect
**Related issues:** #174, #9, #42

## Context

The physical layer of the Smart Factory already has an L0 design contract. `contracts/physical/capability-matrix.md` names the nine physical modules, their typed IO channels, their command interfaces, their planned telemetry and their ADR-0006 safety constraints. `contracts/physical/factory-interface.md` states the module states and the rejection codes that a controller is expected to enforce. `contracts/physical/end-to-end-sequence.md` sequences the modules across a production cycle.

Three gaps remain between that L0 document set and an executable runtime contract.

First, the L0 contract is prose plus markdown tables. A controller implementation, a simulator, the gateway and the digital twin all have to re-derive the same module list, the same channel names, the same command tokens and the same state transitions by reading prose. Nothing in the repository mechanically prevents an implementation from inventing a sensor or a drive that the matrix never declared. The closure audit recorded on `docs/tracking/issue-closure-audit-2026-10-22.md` names this gap explicitly: "turning the L0 matrix into versioned executable schema, capability admission validation, all-module fixture library, registry binding, and Unity mapping — no open PR implements the integrated matrix-to-runtime contract".

Second, nothing in the repository rejects a command that is addressed to a module that does not exist, or to a module that does not support the requested capability, before the command can travel towards an actuator. ADR-0006 places the authoritative safety enforcement on the device-local controller, and that must not change. But ADR-0006 also assumes that the network side never asks for something the module cannot do. Today that assumption is unenforced anywhere in code.

Third, the physical contracts are explicitly planned. `contracts/physical/factory-interface.md` records that the v1 bridge command envelope supports only `CONVEYOR_START`, `CONVEYOR_STOP`, `RESET`, `PING` and `SET_OUTPUT`, and that the module-specific commands in the matrix are planned controller-contract v0.1 that require a future controller schema version and a compatibility review before publication through the bridge. Any executable artefact built on the matrix must therefore carry its own version and must not silently become a wire contract.

The scope of this decision is one increment: the versioned executable schema and the admission validation that consumes it. The all-module fixture library, the device-registry binding, the Unity prefab and scene mapping, and the UNKNOWN and SIMULATED telemetry states are separate increments and remain open.

## Decision

We will introduce `contracts/physical/capability-schema.v1.json` as the versioned, machine-readable capability schema for the nine physical modules, and `factory-control/src/capability_schema.py`, `factory-control/src/capability_admission.py` and `factory-control/src/capability_fixtures.py` as the executable layers that consume it.

The schema file name carries the version. The document body carries an explicit `schema_version` field (`1.0.0`), a `schema_id` (`smart-factory.physical.capability`), a `contract_status` of `planned_controller_contract_v0.1` and an `evidence_level` of `L1`. The schema is a planning artefact: it does not extend the published v1 bridge command envelope, and the `contracts/v1/schemas/command.schema.json` and `contracts/v1/schemas/telemetry.schema.json` envelopes remain the only published wire contracts. Publishing the planned controller commands through the bridge requires a separate future controller schema version and a compatibility review.

The schema declares, per module: equipment identity and role, whether the module is a physical, structural or orchestrated construct, the controller board family and its allocation status, declared IO counts with an explicit `count_status` note wherever the L0 contract leaves a count unresolved, typed IO signals with direction, value type, unit, range, purpose and fault codes, the supported modes and the declared mode transitions, the capabilities with their argument schema, range, range owner, range source and enforcement level, watchdog ownership, local-interlock ownership and rules, the pin-mapping provenance pointer with its verification status, and the declared normal cycle.

Brackets (`brackets-01`) and Combine (`combine-01`) are marked as a structural and an orchestrated construct respectively, with `physical_controller: false`, no controller board, no watchdog of their own and no actuating capability. Remote actuation on either construct is rejected by the admission layer.

The admission layer is a network-side admission filter placed before any actuator path. It rejects, with a typed and machine-readable error that names the module, the capability and the violated constraint: a command addressed to an unknown module (`UNKNOWN_MODULE`), a command addressed to a module that does not support the requested capability (`CAPABILITY_NOT_SUPPORTED`), an unknown argument (`UNKNOWN_ARGUMENT`), a missing required argument (`MISSING_ARGUMENT`), an argument of the wrong declared type (`INVALID_ARGUMENT_TYPE`), a value outside a schema-declared admission-enforced range (`ARGUMENT_OUT_OF_RANGE`), a value outside a schema-declared allowed set (`ARGUMENT_VALUE_NOT_ALLOWED`), a command whose observed state is not a declared source state of the capability (`ILLEGAL_TRANSITION`) and a transition-checked command whose observed state is unknown or stale (`STATE_UNKNOWN`).

Only arguments the schema marks `enforcement: admission` are range-checked at the admission layer. Ranges that the L0 contract leaves with the local controller stay with the local controller and are marked `enforcement: deferred_to_local_controller` in the schema. The admission layer never infers a state: an unknown or stale observed state is surfaced, never assumed to be safe or to be a valid source state.

The admission layer is explicitly not a substitute for a device-local interlock. Motion limits, E-stop authority and every controller-owned range remain owned by the local controller under ADR-0006. The admission layer is a filter that reduces the set of commands that can reach a controller at all.

## Consequences

The module catalogue, the channel names, the command tokens, the IO types and the state transitions now exist once, in a versioned form that code reads. A second implementation cannot silently disagree with the matrix: `factory-control/tests/test_capability_matrix_conformance.py` parses `contracts/physical/capability-matrix.md` at test time and asserts that the schema declares exactly the channels, the IO types and the commands of the L0 matrix, in both directions. A module, sensor or drive that is not in the matrix fails the test suite.

A command that is invalid for structural reasons is now rejected before it can travel towards an actuator, and the rejection is machine-readable rather than a log line. The rejection payload is stable: `code`, `module_id`, `capability`, `constraint`, `detail` and `evidence_level`.

The schema introduces a maintenance obligation. The matrix, the schema and the conformance test must move together; changing one without the other fails CI. The version suffix in the schema file name is the handle for that obligation: a future incompatible change produces `capability-schema.v2.json` and a corresponding schema version, rather than an in-place edit of a published artefact.

The admission layer is a new boundary in the command path. A caller that bypasses it can still energise an actuator. This is a real limitation and the reason the local interlocks of ADR-0006 remain authoritative and remain mandatory.

The evidence ceiling of this increment is L1 (executable validation plus unit and integration tests). A run of the normal-cycle fixture is L2 (software simulation) at most. TC-4 (measured pinout and tolerances) and TC-5 (power loss and safety stop) require physical HIL evidence and cannot be satisfied by this work; they remain open. Device deployment remains blocked wherever the controller and channel allocation is unverified.

Only the NORMAL CYCLE fixture is implemented. The jam, missing-sensor, limit-switch, E-stop, offline and calibration-expiry fixtures remain a separate increment and are not simulated here.

## Alternatives considered

Generate the executable schema from the markdown matrix at build time. This keeps a single source of truth and eliminates the dual-maintenance obligation, but it requires a markdown parser in the build and the CI path, turns the L0 document into an input to the toolchain, and makes the schema's version and status fields artefacts of a generator rather than reviewable committed content. The committed, versioned JSON with a conformance test was chosen because the schema is itself an artefact that later increments (registry binding, Unity mapping) must bind to by version.

Encode the capability catalogue in Python dataclasses only, with no JSON artefact. This avoids a second file and keeps the catalogue close to the code, but it gives the catalogue no version, no reviewable diff and no stable handle for other modules (the gateway, the digital twin) to bind to. It also makes the conformance check against the matrix impossible without duplicating the catalogue in the test.

Place the admission check inside the existing device adapters, one method per adapter. This keeps the change local to the adapters and needs no new layer, but it puts the check after the point where a command has already been routed and addressed, it duplicates the check per adapter, and it makes the "rejected before any actuator path" property an emergent property of each adapter rather than a single testable boundary.

Validate the range of every argument at the admission layer, including the controller-owned ranges. This would give a uniform rule but it would require inventing the crane, forklift, dump-truck and packaging bounds that the L0 contract leaves unresolved, which is precisely the fabrication this increment must avoid.

Treat the schema as the published wire contract and extend the v1 bridge command envelope with the module-specific commands. This would make the schema immediately consumable by the bridge and the gateway, but it would change a published wire format without the compatibility review that `contracts/physical/factory-interface.md` requires, and it would turn a planning contract into a deployed one. The schema therefore stays a versioned planning artefact with an explicit `contract_status`, and the v1 bridge envelope is untouched.

## Evidence

- `contracts/physical/capability-matrix.md` — the L0 source of truth for the nine modules, the IO channels, the commands and the physical constraints.
- `contracts/physical/factory-interface.md` — the module states, the rejection-code authority and the statement that the module-specific commands are planned controller-contract v0.1.
- `contracts/physical/capability-schema.v1.json` — the versioned executable schema introduced by this decision.
- `factory-control/src/capability_schema.py` — the schema loader and the structural validator.
- `factory-control/src/capability_admission.py` — the admission layer and its typed rejection contract.
- `factory-control/src/capability_fixtures.py` — the deterministic NORMAL CYCLE fixture runner.
- `factory-control/tests/test_capability_schema.py` — TC-1, the nine-module catalogue validates from the schema itself.
- `factory-control/tests/test_capability_matrix_conformance.py` — the two-way cross-check against the L0 matrix.
- `factory-control/tests/test_capability_admission.py` — TC-2, the negative admission behaviour and the proof that rejection happens in the admission layer.
- `factory-control/tests/test_capability_normal_cycle.py` — TC-3 (partial), the reproducible NORMAL CYCLE fixture.
- `docs/adr/adr-0006-local-physical-safety.md` — the local-safety authority that this admission layer does not replace.
- `docs/tracking/issue-closure-audit-2026-10-22.md` — the closure audit that records the uncovered gap this increment addresses.
