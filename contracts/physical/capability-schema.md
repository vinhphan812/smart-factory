# Physical Capability Schema and Capability Admission — Contract Note

**Status:** IMPLEMENTED (L1) | **Owner:** AIBOT / DNTU | **Related issues:** #174, #9, #42
**Governing ADR:** [ADR-0020](../../docs/adr/adr-0020-versioned-capability-schema-and-admission-layer.md)

## Purpose

This note documents the versioned, executable capability schema and the
pre-actuator admission layer that consumes it. The schema turns the L0
physical contract (`capability-matrix.md`) into a machine-readable catalogue;
the admission layer decides whether a command may proceed towards an actuator
path at all.

The L0 matrix remains the **source of truth**. The schema is derived from it,
and a conformance test parses the matrix at test time and fails if the schema
and the matrix disagree in either direction.

## Artefacts

| Artefact | Role |
|---|---|
| `contracts/physical/capability-matrix.md` | L0 source of truth (prose + tables) |
| `contracts/physical/capability-schema.v1.json` | Versioned executable catalogue |
| `factory-control/src/capability_schema.py` | Loader + structural validator |
| `factory-control/src/capability_admission.py` | Admission layer + typed rejection contract |
| `factory-control/src/capability_fixtures.py` | Deterministic NORMAL CYCLE fixture runner |

## Versioning

The schema file name carries the version (`capability-schema.v1.json`) and the
document body carries:

| Field | Value | Meaning |
|---|---|---|
| `schema_id` | `smart-factory.physical.capability` | Stable identifier |
| `schema_version` | `1.0.0` | Semantic version of the document body |
| `contract_status` | `planned_controller_contract_v0.1` | Planning artefact, not a published wire contract |
| `evidence_level` | `L1` | Executable validation and unit/integration tests |

`contract_status` is load-bearing. The module-specific commands in the matrix
are **planned** controller-contract v0.1; `contracts/physical/factory-interface.md`
records that the published v1 bridge command envelope supports only
`CONVEYOR_START`, `CONVEYOR_STOP`, `RESET`, `PING` and `SET_OUTPUT`, and that
publishing the planned commands through the bridge requires a future controller
schema version plus a compatibility review. The schema does **not** extend
`contracts/v1/schemas/command.schema.json` or
`contracts/v1/schemas/telemetry.schema.json`; those remain the only published
wire contracts. A future incompatible change produces
`capability-schema.v2.json`, not an in-place edit.

## Schema content

Per module the schema declares:

- **equipment identity** — `module_id`, `name`, `role`, `construct`
  (`physical` / `structural` / `orchestrated`) and `physical_controller`;
- **controller board** — family and allocation status, with the provenance
  pointer; `null` for Brackets and Combine;
- **motor/sensor counts** — `io_counts` per IO type, `derived_counts` and
  `count_status` notes wherever the L0 contract leaves a count unresolved
  (Parking `DI` is `N+1` with `N` unspecified, Parking and Packaging gate and
  seal actuators are `SERVO` or `DO`, Brackets `ESTOP` is optional);
- **supported modes** and the **declared mode transitions** with their trigger
  kind, trigger value and precondition;
- **typed IO signals** — channel, IO type, direction, value type, unit, range,
  purpose and fault codes;
- **capabilities** — name, capability id, actuation flag, transition policy,
  argument schema (type, unit, required, range, range owner, range source,
  enforcement, allowed values) and the L0 reject codes;
- **watchdog ownership** and **local-interlock ownership** and rules;
- **pin-mapping provenance** — status, source pointer, verification note,
  declared pins and the channels whose allocation is still undeclared.

`brackets-01` and `combine-01` carry `physical_controller: false`, no
controller board, no watchdog of their own and no actuating capability.

### Range ownership

Every numeric argument declares a `range_owner` (and, where a bound exists, a
`range_source`), and one of three `enforcement` levels:

| Enforcement | Meaning |
|---|---|
| `admission` | The admission layer checks the range or allowed set. |
| `type_only` | Only the declared type is checked; no value set is declared. |
| `deferred_to_local_controller` | The bound is controller-owned and stays with the local controller (ADR-0006). |

Only `CONVEYOR_START.speedMmPerSec` (`10..100`, from
`factory-control/src/models.py:ConveyorLimits`) and
`SORTING.ROUTE_MANUAL.destination` (the `RouteDestination` set from
`factory-control/src/models.py:RouteDestination`) are admission-enforced. The
crane, forklift, dump-truck and packaging bounds are **not** asserted: the L0
contract leaves them to the controller, and inventing them would fabricate a
safety envelope.

## Admission layer

`CapabilityAdmission.admit(command)` is a pure decision function.
`CapabilityAdmission.dispatch(command, actuator)` evaluates the command and
invokes the actuator callable **only** when the command is admitted — this is
the boundary that a rejected command must never cross.

### Rejection contract

Every rejection is typed and machine-readable:

```json
{
  "code": "ARGUMENT_OUT_OF_RANGE",
  "module_id": "conveyor-01",
  "capability": "CONVEYOR_START",
  "constraint": "range:speedMmPerSec:10..100",
  "detail": "Argument 'speedMmPerSec' of capability 'CONVEYOR_START' accepts 10..100, received 500.",
  "evidence_level": "L1"
}
```

| Code | Raised when |
|---|---|
| `UNKNOWN_MODULE` | The addressed module is not in the schema. |
| `CAPABILITY_NOT_SUPPORTED` | The module does not declare the capability, or the capability would actuate a construct with no physical controller. |
| `UNKNOWN_ARGUMENT` | The capability does not declare the supplied argument. |
| `MISSING_ARGUMENT` | A required argument is absent. |
| `INVALID_ARGUMENT_TYPE` | The value does not match the declared type. |
| `ARGUMENT_OUT_OF_RANGE` | The value is outside an admission-enforced range. |
| `ARGUMENT_VALUE_NOT_ALLOWED` | The value is outside an admission-enforced allowed set. |
| `ILLEGAL_TRANSITION` | The observed state is not a declared source state of the capability. |
| `STATE_UNKNOWN` | A transition-checked command arrives with an unknown or stale observed state. |

The schema's `admission_contract.error_codes` list and the implemented code set
are asserted to be identical by the test suite.

### Transition policies

| Policy | Behaviour |
|---|---|
| `declared_edge` | The observed state must be one of the declared source states of the capability. `ANY` matches every state. An unknown or stale observed state is rejected as `STATE_UNKNOWN`; the state is never inferred. |
| `always_allowed` | The L0 contract accepts the command from any state (for example a local safety stop). The admission layer does not check the transition; the local controller still applies its own state and fault rules. |

### Relationship to ADR-0006

The admission layer is a **network-side admission filter**, not a safety
mechanism. Motion limits, E-stop authority and every controller-owned range
stay with the device-local controller under ADR-0006. The admission layer only
reduces the set of commands that can reach a controller at all. A caller that
bypasses it can still energise an actuator — which is why the local interlocks
remain authoritative and mandatory.

## Test coverage

| Test | Criterion | What it proves |
|---|---|---|
| `test_capability_schema.py` | TC-1 | The nine-module catalogue validates from the schema itself; no null IO count without a `count_status` note; no pin mapping presented as measured; Brackets and Combine carry no physical controller. |
| `test_capability_matrix_conformance.py` | TC-1 | The schema declares exactly the channels, IO types and commands of `capability-matrix.md`, in both directions. No invented sensor or drive. |
| `test_capability_admission.py` | TC-2 | Unknown-module, capability-mismatch, out-of-range, disallowed-value, illegal-transition, unknown-state, unknown-argument and wrong-type commands are all rejected with a typed error; the actuator callable is **not** invoked for any of them. |
| `test_capability_normal_cycle.py` | TC-3 (partial) | The NORMAL CYCLE fixture of each of the nine modules reaches its expected state, reproducibly, with every command step passing the real admission layer. |

## Scope boundary — what is NOT covered

- **The all-module fixture library is a separate increment.** This work
  implements the NORMAL CYCLE fixture only. The jam, missing-sensor,
  limit-switch, E-stop, offline and calibration-expiry fixtures are **not**
  implemented and remain open.
- **TC-4 (measured pinout and tolerances) requires physical HIL evidence and
  cannot be satisfied by this work.** It remains open.
- **TC-5 (power loss and safety stop) requires physical HIL evidence and
  cannot be satisfied by this work.** It remains open.
- **Device deployment remains blocked** wherever the controller and channel
  allocation is unverified (Issue #98). The schema records every pin mapping
  as `DECLARED_UNVERIFIED`, `NOT_DECLARED` or `NOT_APPLICABLE`; none is
  presented as measured.
- **Registry binding** (Issue #32), **Unity prefab and scene mapping**
  (Issue #33) and the **UNKNOWN and SIMULATED telemetry states**
  (Issue #174 SPEC-5 / SPEC-6) are separate increments and remain open.

## Evidence ceiling

**L1** — executable validation plus unit and integration tests. A run of the
normal-cycle fixture is **L2** (software simulation) at most. No physical, HIL
or deployment claim is made by this work.

## Usage

```python
from capability_admission import CapabilityAdmission, CapabilityCommand
from capability_schema import load_capability_schema

schema = load_capability_schema()
admission = CapabilityAdmission(schema)

decision = admission.admit(
    CapabilityCommand(
        module_id="conveyor-01",
        capability="CONVEYOR_START",
        args={"speedMmPerSec": 50},
        observed_state="IDLE",
    )
)
if not decision.admitted:
    print(decision.error.to_dict())
```
