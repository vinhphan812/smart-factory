"""Capability admission validation for the nine physical modules.

This module is the *executable* half of the versioned capability schema
(``contracts/physical/capability-schema.v1.json``). The schema describes what
each module is and what it may do; this module decides whether a command may
proceed towards an actuator path at all.

Design rules (ADR-0006, ``contracts/physical/capability-matrix.md``):

1. The admission layer is a **network-side admission filter**, not a substitute
   for a device-local interlock. Local controllers keep ownership of motion
   limits, E-stop authority and every controller-owned range.
2. A command that is not admitted **never** reaches an actuator path. The
   :meth:`CapabilityAdmission.dispatch` helper enforces that ordering: the
   actuator callable is invoked only for an admitted command.
3. Every rejection is typed and machine-readable. The error names the module,
   the capability and the violated constraint.

Evidence level: L1 (executable validation + unit/integration tests). Simulator
runs of this layer are L2 only. No physical, HIL or deployment claim is made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from capability_schema import CapabilitySchema, ModuleSpec

__all__ = [
    "AdmissionErrorCode",
    "CapabilityAdmissionError",
    "AdmissionDecision",
    "CapabilityCommand",
    "CapabilityAdmission",
    "ADMISSION_ERROR_CODES",
]


class AdmissionErrorCode(str, Enum):
    """Machine-readable rejection codes produced by the admission layer."""

    UNKNOWN_MODULE = "UNKNOWN_MODULE"
    CAPABILITY_NOT_SUPPORTED = "CAPABILITY_NOT_SUPPORTED"
    UNKNOWN_ARGUMENT = "UNKNOWN_ARGUMENT"
    MISSING_ARGUMENT = "MISSING_ARGUMENT"
    INVALID_ARGUMENT_TYPE = "INVALID_ARGUMENT_TYPE"
    ARGUMENT_OUT_OF_RANGE = "ARGUMENT_OUT_OF_RANGE"
    ARGUMENT_VALUE_NOT_ALLOWED = "ARGUMENT_VALUE_NOT_ALLOWED"
    ILLEGAL_TRANSITION = "ILLEGAL_TRANSITION"
    STATE_UNKNOWN = "STATE_UNKNOWN"


#: The rejection codes this layer can emit. The schema's
#: ``admission_contract.error_codes`` list must stay in sync with this set.
ADMISSION_ERROR_CODES: Tuple[str, ...] = tuple(code.value for code in AdmissionErrorCode)


class CapabilityAdmissionError(Exception):
    """Typed, machine-readable rejection raised by the admission layer."""

    def __init__(
        self,
        code: AdmissionErrorCode,
        module_id: str,
        capability: str,
        constraint: str,
        detail: str,
        evidence_level: str = "L1",
    ) -> None:
        super().__init__(f"{code.value} module={module_id} capability={capability} constraint={constraint}: {detail}")
        self.code = code
        self.module_id = module_id
        self.capability = capability
        self.constraint = constraint
        self.detail = detail
        self.evidence_level = evidence_level

    def to_dict(self) -> Dict[str, Any]:
        """Return the machine-readable rejection payload."""
        return {
            "code": self.code.value,
            "module_id": self.module_id,
            "capability": self.capability,
            "constraint": self.constraint,
            "detail": self.detail,
            "evidence_level": self.evidence_level,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"CapabilityAdmissionError(code={self.code.value!r}, module_id={self.module_id!r}, "
            f"capability={self.capability!r}, constraint={self.constraint!r})"
        )


@dataclass(frozen=True)
class AdmissionDecision:
    """Outcome of an admission evaluation."""

    admitted: bool
    module_id: str
    capability: str
    error: Optional[CapabilityAdmissionError] = None

    @property
    def code(self) -> Optional[str]:
        """The machine-readable rejection code, or ``None`` when admitted."""
        return self.error.code.value if self.error else None

    @property
    def constraint(self) -> Optional[str]:
        """The violated constraint, or ``None`` when admitted."""
        return self.error.constraint if self.error else None

    def to_dict(self) -> Dict[str, Any]:
        """Return the machine-readable decision payload."""
        if self.error is not None:
            return {"admitted": False, **self.error.to_dict()}
        return {"admitted": True, "module_id": self.module_id, "capability": self.capability}


@dataclass(frozen=True)
class CapabilityCommand:
    """A command offered to the admission layer.

    ``observed_state`` is the last observed module state. It is required for
    transition-checked capabilities; ``None`` means the state is unknown or
    stale and is never inferred (ADR-0006).
    """

    module_id: str
    capability: str
    args: Mapping[str, Any] = field(default_factory=dict)
    observed_state: Optional[str] = None


class CapabilityAdmission:
    """Evaluates commands against the versioned capability schema."""

    def __init__(self, schema: CapabilitySchema) -> None:
        self._schema = schema

    @property
    def schema(self) -> CapabilitySchema:
        """The capability schema this admission layer consumes."""
        return self._schema

    # -- public API ---------------------------------------------------------

    def admit(self, command: CapabilityCommand) -> AdmissionDecision:
        """Evaluate ``command`` and return a typed decision.

        The command is never executed here; this is a pure decision function.
        """
        error = self._evaluate(command)
        if error is not None:
            return AdmissionDecision(
                admitted=False,
                module_id=command.module_id,
                capability=command.capability,
                error=error,
            )
        return AdmissionDecision(admitted=True, module_id=command.module_id, capability=command.capability)

    def dispatch(
        self,
        command: CapabilityCommand,
        actuator: Callable[[CapabilityCommand], Any],
    ) -> AdmissionDecision:
        """Admit ``command`` and, only when admitted, invoke ``actuator``.

        The actuator callable is the boundary that must not be reached by a
        rejected command. A rejection is returned, never raised, so the caller
        observes the machine-readable decision.
        """
        decision = self.admit(command)
        if decision.admitted:
            actuator(command)
        return decision

    # -- internals ----------------------------------------------------------

    def _evaluate(self, command: CapabilityCommand) -> Optional[CapabilityAdmissionError]:
        module = self._schema.module(command.module_id)
        if module is None:
            return CapabilityAdmissionError(
                code=AdmissionErrorCode.UNKNOWN_MODULE,
                module_id=command.module_id,
                capability=command.capability,
                constraint=f"module:{command.module_id}",
                detail=(
                    f"Module {command.module_id!r} is not declared in capability schema "
                    f"{self._schema.schema_id} v{self._schema.schema_version}."
                ),
                evidence_level=self._schema.evidence_level or "L1",
            )

        capability = module.capability(command.capability)
        if capability is None:
            return CapabilityAdmissionError(
                code=AdmissionErrorCode.CAPABILITY_NOT_SUPPORTED,
                module_id=module.module_id,
                capability=command.capability,
                constraint=f"capability:{command.capability}",
                detail=(
                    f"Module {module.module_id!r} does not support capability "
                    f"{command.capability!r}. Supported capabilities: "
                    f"{', '.join(module.capability_names) or '(none)'}."
                ),
                evidence_level=self._schema.evidence_level or "L1",
            )

        error = self._check_actuation(module, capability)
        if error is not None:
            return error

        error = self._check_arguments(module, capability, command)
        if error is not None:
            return error

        return self._check_transition(module, capability, command)

    def _check_actuation(
        self,
        module: ModuleSpec,
        capability: Mapping[str, Any],
    ) -> Optional[CapabilityAdmissionError]:
        """Reject actuation on a module that has no physical controller."""
        if not capability.get("actuation"):
            return None
        if module.physical_controller:
            return None
        return CapabilityAdmissionError(
            code=AdmissionErrorCode.CAPABILITY_NOT_SUPPORTED,
            module_id=module.module_id,
            capability=str(capability["name"]),
            constraint="physical_controller:none",
            detail=(
                f"Module {module.module_id!r} is a {module.construct} construct with no physical "
                "controller; remote actuation is not permitted."
            ),
            evidence_level=self._schema.evidence_level or "L1",
        )

    def _check_arguments(
        self,
        module: ModuleSpec,
        capability: Mapping[str, Any],
        command: CapabilityCommand,
    ) -> Optional[CapabilityAdmissionError]:
        declared_args = list(capability.get("args", ()))
        declared_by_name = {argument["name"]: argument for argument in declared_args}
        supplied = dict(command.args or {})

        for name in supplied:
            if name not in declared_by_name:
                return CapabilityAdmissionError(
                    code=AdmissionErrorCode.UNKNOWN_ARGUMENT,
                    module_id=module.module_id,
                    capability=str(capability["name"]),
                    constraint=f"argument:{name}",
                    detail=(
                        f"Capability {capability['name']!r} of module {module.module_id!r} does not "
                        f"declare argument {name!r}."
                    ),
                    evidence_level=self._schema.evidence_level or "L1",
                )

        for argument in declared_args:
            name = argument["name"]
            if name not in supplied:
                if argument.get("required"):
                    return CapabilityAdmissionError(
                        code=AdmissionErrorCode.MISSING_ARGUMENT,
                        module_id=module.module_id,
                        capability=str(capability["name"]),
                        constraint=f"argument:{name}",
                        detail=(
                            f"Capability {capability['name']!r} of module {module.module_id!r} requires "
                            f"argument {name!r}."
                        ),
                        evidence_level=self._schema.evidence_level or "L1",
                    )
                continue

            error = self._check_argument_type(module, capability, argument, supplied[name])
            if error is not None:
                return error

            error = self._check_argument_value(module, capability, argument, supplied[name])
            if error is not None:
                return error

        return None

    def _check_argument_type(
        self,
        module: ModuleSpec,
        capability: Mapping[str, Any],
        argument: Mapping[str, Any],
        value: Any,
    ) -> Optional[CapabilityAdmissionError]:
        expected = argument.get("type")
        if not _value_matches_type(value, expected):
            return CapabilityAdmissionError(
                code=AdmissionErrorCode.INVALID_ARGUMENT_TYPE,
                module_id=module.module_id,
                capability=str(capability["name"]),
                constraint=f"type:{argument['name']}:{expected}",
                detail=(
                    f"Argument {argument['name']!r} of capability {capability['name']!r} expects type "
                    f"{expected!r}, received {type(value).__name__}."
                ),
                evidence_level=self._schema.evidence_level or "L1",
            )
        return None

    def _check_argument_value(
        self,
        module: ModuleSpec,
        capability: Mapping[str, Any],
        argument: Mapping[str, Any],
        value: Any,
    ) -> Optional[CapabilityAdmissionError]:
        # Only arguments the schema marks as admission-enforced carry an
        # enforceable range or value set here. Controller-owned ranges stay
        # with the local controller.
        if argument.get("enforcement") != "admission":
            return None

        allowed_values = argument.get("allowed_values")
        if allowed_values is not None and value not in allowed_values:
            return CapabilityAdmissionError(
                code=AdmissionErrorCode.ARGUMENT_VALUE_NOT_ALLOWED,
                module_id=module.module_id,
                capability=str(capability["name"]),
                constraint=f"allowed_values:{argument['name']}:{'|'.join(str(v) for v in allowed_values)}",
                detail=(
                    f"Argument {argument['name']!r} of capability {capability['name']!r} does not accept "
                    f"value {value!r}."
                ),
                evidence_level=self._schema.evidence_level or "L1",
            )

        declared_range = argument.get("range")
        if declared_range and isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = declared_range.get("min")
            maximum = declared_range.get("max")
            if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
                return CapabilityAdmissionError(
                    code=AdmissionErrorCode.ARGUMENT_OUT_OF_RANGE,
                    module_id=module.module_id,
                    capability=str(capability["name"]),
                    constraint=f"range:{argument['name']}:{minimum}..{maximum}",
                    detail=(
                        f"Argument {argument['name']!r} of capability {capability['name']!r} accepts "
                        f"{minimum}..{maximum}, received {value!r}."
                    ),
                    evidence_level=self._schema.evidence_level or "L1",
                )

        return None

    def _check_transition(
        self,
        module: ModuleSpec,
        capability: Mapping[str, Any],
        command: CapabilityCommand,
    ) -> Optional[CapabilityAdmissionError]:
        policy = capability.get("transition_policy")
        if policy != "declared_edge":
            # ``always_allowed``: the L0 contract accepts the command from any
            # state; the local controller still applies its own state rules.
            return None

        transitions = module.command_transitions(str(capability["name"]))
        if not transitions:
            return CapabilityAdmissionError(
                code=AdmissionErrorCode.ILLEGAL_TRANSITION,
                module_id=module.module_id,
                capability=str(capability["name"]),
                constraint=f"transition:{capability['name']}:no_declared_edge",
                detail=(
                    f"Capability {capability['name']!r} of module {module.module_id!r} is transition-checked "
                    "but declares no command-triggered edge."
                ),
                evidence_level=self._schema.evidence_level or "L1",
            )

        source_states = {transition["from"] for transition in transitions}
        if "ANY" in source_states:
            return None

        observed_state = command.observed_state
        if observed_state is None:
            return CapabilityAdmissionError(
                code=AdmissionErrorCode.STATE_UNKNOWN,
                module_id=module.module_id,
                capability=str(capability["name"]),
                constraint=f"transition:{capability['name']}:state_unknown",
                detail=(
                    f"Capability {capability['name']!r} of module {module.module_id!r} is transition-checked "
                    "but the observed module state is unknown or stale; the state is never inferred."
                ),
                evidence_level=self._schema.evidence_level or "L1",
            )

        if observed_state not in source_states:
            return CapabilityAdmissionError(
                code=AdmissionErrorCode.ILLEGAL_TRANSITION,
                module_id=module.module_id,
                capability=str(capability["name"]),
                constraint=f"transition:{capability['name']}:{observed_state}",
                detail=(
                    f"Capability {capability['name']!r} of module {module.module_id!r} may not be issued in "
                    f"state {observed_state!r}; allowed source states: {', '.join(sorted(source_states))}."
                ),
                evidence_level=self._schema.evidence_level or "L1",
            )

        return None


def _value_matches_type(value: Any, expected: Optional[str]) -> bool:
    """Return whether ``value`` matches the declared argument ``type``."""
    if expected is None:
        return True
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    return True
