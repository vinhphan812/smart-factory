"""Loader and structural validator for the versioned physical capability schema.

The canonical schema is ``contracts/physical/capability-schema.v1.json``. It is a
cross-system contract (root ``contracts/``) that this module consumes as the
controller-side catalogue of the nine physical modules.

This module is deliberately read-only: it parses the schema, exposes immutable
views of it and reports structural inconsistencies. It performs **no** admission
decision — that is :mod:`capability_admission`.

Evidence level: L1 (executable schema parsing and unit tests). No hardware,
HIL or deployment claim is made or implied.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

SCHEMA_ID = "smart-factory.physical.capability"
SCHEMA_VERSION = "1.0.0"

#: Location of the canonical schema relative to the repository root.
DEFAULT_SCHEMA_RELATIVE_PATH = Path("contracts") / "physical" / "capability-schema.v1.json"

#: Environment override for deployments that mount the contract elsewhere.
SCHEMA_PATH_ENV_VAR = "SMART_FACTORY_CAPABILITY_SCHEMA"

#: IO types whose concrete actuator type the L0 contract leaves unresolved.
COMPOSITE_IO_TYPES = frozenset({"SERVO|DO"})

#: Trigger kinds a mode transition may declare.
VALID_TRIGGER_KINDS = frozenset({"command", "event"})


class CapabilitySchemaError(Exception):
    """Raised when the capability schema cannot be loaded or is inconsistent."""


@dataclass(frozen=True)
class ModuleSpec:
    """Immutable view of one module entry in the capability schema."""

    module_id: str
    name: str
    role: str
    construct: str
    physical_controller: bool
    controller_board: Optional[Mapping[str, Any]]
    io_counts: Mapping[str, Any]
    count_status: Mapping[str, Any]
    derived_counts: Mapping[str, Any]
    io_signals: Tuple[Mapping[str, Any], ...]
    supported_modes: Tuple[str, ...]
    mode_transitions: Tuple[Mapping[str, Any], ...]
    capabilities: Tuple[Mapping[str, Any], ...]
    transition_optional_capabilities: frozenset
    watchdog: Mapping[str, Any]
    local_interlocks: Mapping[str, Any]
    pin_mapping_provenance: Mapping[str, Any]
    normal_cycle: Mapping[str, Any]

    @property
    def capability_names(self) -> Tuple[str, ...]:
        """Names of the capabilities declared for this module."""
        return tuple(str(capability["name"]) for capability in self.capabilities)

    def capability(self, name: str) -> Optional[Mapping[str, Any]]:
        """Return the declared capability ``name`` or ``None`` when absent."""
        for capability in self.capabilities:
            if capability["name"] == name:
                return capability
        return None

    def command_transitions(self, capability_name: str) -> Tuple[Mapping[str, Any], ...]:
        """Return the declared command-triggered transitions for a capability."""
        return tuple(
            transition
            for transition in self.mode_transitions
            if transition.get("trigger", {}).get("kind") == "command"
            and transition["trigger"].get("value") == capability_name
        )

    def event_transitions(self, trigger_value: str) -> Tuple[Mapping[str, Any], ...]:
        """Return the declared event-triggered transitions for an event."""
        return tuple(
            transition
            for transition in self.mode_transitions
            if transition.get("trigger", {}).get("kind") == "event"
            and transition["trigger"].get("value") == trigger_value
        )


@dataclass(frozen=True)
class CapabilitySchema:
    """Parsed capability schema with indexed modules."""

    schema_id: str
    schema_version: str
    contract_status: str
    evidence_level: str
    provenance: Mapping[str, Any]
    io_types: Mapping[str, Any]
    admission_contract: Mapping[str, Any]
    open_increments: Tuple[str, ...]
    cross_module_invariants: Tuple[Mapping[str, Any], ...]
    modules: Tuple[ModuleSpec, ...]

    @property
    def module_ids(self) -> Tuple[str, ...]:
        """Identifiers of every module in the catalogue."""
        return tuple(module.module_id for module in self.modules)

    def module(self, module_id: str) -> Optional[ModuleSpec]:
        """Return the module with ``module_id`` or ``None`` when unknown."""
        for module in self.modules:
            if module.module_id == module_id:
                return module
        return None

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "CapabilitySchema":
        """Build a schema from an already-parsed document."""
        issues = validate_schema_document(document)
        if issues:
            raise CapabilitySchemaError(
                "Capability schema is structurally inconsistent:\n- " + "\n- ".join(issues)
            )

        modules = tuple(
            ModuleSpec(
                module_id=str(entry["module_id"]),
                name=str(entry.get("name", entry["module_id"])),
                role=str(entry.get("role", "")),
                construct=str(entry.get("construct", "physical")),
                physical_controller=bool(entry.get("physical_controller", False)),
                controller_board=entry.get("controller_board"),
                io_counts=dict(entry.get("io_counts", {})),
                count_status=dict(entry.get("count_status", {})),
                derived_counts=dict(entry.get("derived_counts", {})),
                io_signals=tuple(entry.get("io_signals", ())),
                supported_modes=tuple(entry.get("supported_modes", ())),
                mode_transitions=tuple(entry.get("mode_transitions", ())),
                capabilities=tuple(entry.get("capabilities", ())),
                transition_optional_capabilities=frozenset(
                    entry.get("transition_optional_capabilities", ())
                ),
                watchdog=dict(entry.get("watchdog", {})),
                local_interlocks=dict(entry.get("local_interlocks", {})),
                pin_mapping_provenance=dict(entry.get("pin_mapping_provenance", {})),
                normal_cycle=dict(entry.get("normal_cycle", {})),
            )
            for entry in document["modules"]
        )

        return cls(
            schema_id=str(document["schema_id"]),
            schema_version=str(document["schema_version"]),
            contract_status=str(document.get("contract_status", "")),
            evidence_level=str(document.get("evidence_level", "")),
            provenance=dict(document.get("provenance", {})),
            io_types=dict(document.get("io_types", {})),
            admission_contract=dict(document.get("admission_contract", {})),
            open_increments=tuple(document.get("open_increments", ())),
            cross_module_invariants=tuple(document.get("cross_module_invariants", ())),
            modules=modules,
        )

    @classmethod
    def from_path(cls, path: Path) -> "CapabilitySchema":
        """Load and validate the schema from a JSON file."""
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CapabilitySchemaError(f"Capability schema not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise CapabilitySchemaError(f"Capability schema is not valid JSON: {path}: {exc}") from exc
        return cls.from_document(document)


def resolve_schema_path(explicit: Optional[Path] = None) -> Path:
    """Resolve the capability schema path.

    Resolution order: explicit argument, environment override, then a search
    upwards from this file for the repository root containing
    ``contracts/physical/capability-schema.v1.json``.
    """
    if explicit is not None:
        return Path(explicit)

    env_value = os.environ.get(SCHEMA_PATH_ENV_VAR)
    if env_value:
        return Path(env_value)

    here = Path(__file__).resolve()
    for candidate in here.parents:
        schema = candidate / DEFAULT_SCHEMA_RELATIVE_PATH
        if schema.is_file():
            return schema
    raise CapabilitySchemaError(
        "Unable to locate "
        f"{DEFAULT_SCHEMA_RELATIVE_PATH.as_posix()}; set ${SCHEMA_PATH_ENV_VAR} explicitly."
    )


def load_capability_schema(explicit: Optional[Path] = None) -> CapabilitySchema:
    """Load the canonical capability schema."""
    return CapabilitySchema.from_path(resolve_schema_path(explicit))


def _count_io_signals(io_signals: Iterable[Mapping[str, Any]], io_type: str) -> int:
    """Count declared signals of one IO type, ignoring composite placeholders."""
    if io_type in COMPOSITE_IO_TYPES:
        return 0
    return sum(1 for signal in io_signals if signal.get("io_type") == io_type)


def validate_schema_document(document: Mapping[str, Any]) -> List[str]:
    """Return the list of structural problems in a capability schema document.

    An empty list means the document is internally consistent. The checks are
    derived entirely from the document itself: no module, sensor, drive or
    channel is invented here.
    """
    issues: List[str] = []

    if document.get("schema_id") != SCHEMA_ID:
        issues.append(f"schema_id must be {SCHEMA_ID!r}, found {document.get('schema_id')!r}")

    version = document.get("schema_version")
    if not isinstance(version, str) or not version:
        issues.append("schema_version must be a non-empty string")

    modules = document.get("modules")
    if not isinstance(modules, list) or not modules:
        issues.append("modules must be a non-empty list")
        return issues

    io_types = document.get("io_types", {})
    seen_module_ids = set()

    for module in modules:
        module_id = module.get("module_id")
        if not module_id:
            issues.append("every module requires a module_id")
            continue
        if module_id in seen_module_ids:
            issues.append(f"duplicate module_id {module_id!r}")
        seen_module_ids.add(module_id)

        # --- IO signals and counts -------------------------------------
        io_signals = module.get("io_signals", [])
        io_counts = module.get("io_counts", {})
        count_status = module.get("count_status", {})

        for signal in io_signals:
            io_type = signal.get("io_type")
            if io_type not in io_types:
                issues.append(f"{module_id}: channel {signal.get('channel')!r} uses undeclared io_type {io_type!r}")

        seen_channels = set()
        for signal in io_signals:
            channel = signal.get("channel")
            if channel in seen_channels:
                issues.append(f"{module_id}: duplicate channel {channel!r}")
            seen_channels.add(channel)

        for io_type, declared in io_counts.items():
            if io_type not in io_types:
                issues.append(f"{module_id}: io_counts declares undeclared io_type {io_type!r}")
            if declared is None:
                if io_type not in count_status:
                    issues.append(f"{module_id}: io_counts[{io_type!r}] is null without a count_status note")
                continue
            observed = _count_io_signals(io_signals, io_type)
            if observed != declared:
                issues.append(
                    f"{module_id}: io_counts[{io_type!r}] declares {declared} but {observed} signals are declared"
                )

        # --- Derived counts --------------------------------------------
        derived = module.get("derived_counts", {})
        sensors = sum(
            (io_counts.get(io_type) or 0) for io_type in ("DI", "AI", "ENC")
        )
        if derived.get("sensors") is not None and derived["sensors"] != sensors:
            issues.append(
                f"{module_id}: derived_counts.sensors is {derived['sensors']} but inputs total {sensors}"
            )
        if derived.get("motors") is not None and derived["motors"] != (io_counts.get("MOTOR") or 0):
            issues.append(f"{module_id}: derived_counts.motors does not match io_counts.MOTOR")
        if derived.get("encoders") is not None and derived["encoders"] != (io_counts.get("ENC") or 0):
            issues.append(f"{module_id}: derived_counts.encoders does not match io_counts.ENC")
        if derived.get("estop_channels") is not None and derived["estop_channels"] != (io_counts.get("ESTOP") or 0):
            issues.append(f"{module_id}: derived_counts.estop_channels does not match io_counts.ESTOP")

        # --- Modes and transitions -------------------------------------
        modes = set(module.get("supported_modes", ()))
        for transition in module.get("mode_transitions", ()):
            trigger = transition.get("trigger", {})
            if trigger.get("kind") not in VALID_TRIGGER_KINDS:
                issues.append(
                    f"{module_id}: transition {transition.get('from')}->{transition.get('to')} has an invalid trigger kind"
                )
            for endpoint in ("from", "to"):
                state = transition.get(endpoint)
                if state != "ANY" and state not in modes:
                    issues.append(f"{module_id}: transition references undeclared state {state!r}")
            if trigger.get("kind") == "command":
                capability_names = {capability["name"] for capability in module.get("capabilities", ())}
                if trigger.get("value") not in capability_names:
                    issues.append(
                        f"{module_id}: command transition references undeclared capability {trigger.get('value')!r}"
                    )

        # --- Capabilities ----------------------------------------------
        capability_names = set()
        for capability in module.get("capabilities", ()):
            name = capability.get("name")
            if not name:
                issues.append(f"{module_id}: every capability requires a name")
                continue
            if name in capability_names:
                issues.append(f"{module_id}: duplicate capability {name!r}")
            capability_names.add(name)
            arg_names = set()
            for argument in capability.get("args", ()):
                argument_name = argument.get("name")
                if not argument_name:
                    issues.append(f"{module_id}: capability {name!r} has an unnamed argument")
                    continue
                if argument_name in arg_names:
                    issues.append(f"{module_id}: capability {name!r} has duplicate argument {argument_name!r}")
                arg_names.add(argument_name)
                if argument.get("range") is not None and not argument.get("range_owner"):
                    issues.append(
                        f"{module_id}: capability {name!r} argument {argument_name!r} declares a range without a range_owner"
                    )
            if not capability.get("reject_codes") and capability.get("actuation"):
                # Actuating capabilities may legitimately have no reject code in the
                # L0 matrix (for example an always-accepted stop), so this is not an
                # error. The admission layer still enforces the capability contract.
                pass

        for optional in module.get("transition_optional_capabilities", ()):
            if optional not in capability_names:
                issues.append(f"{module_id}: transition_optional_capabilities references unknown capability {optional!r}")

        # --- Normal cycle ----------------------------------------------
        cycle = module.get("normal_cycle", {})
        for endpoint in ("initial_state", "terminal_state"):
            state = cycle.get(endpoint)
            if state is not None and state not in modes:
                issues.append(f"{module_id}: normal_cycle.{endpoint} references undeclared state {state!r}")
        for step in cycle.get("steps", ()):
            kind = step.get("kind")
            if kind == "command":
                if step.get("capability") not in capability_names:
                    issues.append(
                        f"{module_id}: normal_cycle step references undeclared capability {step.get('capability')!r}"
                    )
            elif kind == "event":
                triggers = {
                    transition["trigger"].get("value")
                    for transition in module.get("mode_transitions", ())
                    if transition.get("trigger", {}).get("kind") == "event"
                }
                if step.get("trigger") not in triggers:
                    issues.append(
                        f"{module_id}: normal_cycle step references undeclared event {step.get('trigger')!r}"
                    )
            elif kind != "observation":
                issues.append(f"{module_id}: normal_cycle step has unknown kind {kind!r}")
            if step.get("expect_state") not in modes:
                issues.append(
                    f"{module_id}: normal_cycle step expects undeclared state {step.get('expect_state')!r}"
                )

    return issues
