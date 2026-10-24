"""Deterministic NORMAL CYCLE fixture runner for the capability schema.

The capability schema declares, per module, a ``normal_cycle``: the ordered
sequence of command and event steps that returns the module to its terminal
state. This module executes that declared cycle against the real admission
layer and the real declared mode transitions.

Scope boundary (issue #174, this increment):

* Only the NORMAL CYCLE fixture is implemented here.
* The jam, missing-sensor, limit-switch, E-stop, offline and
  calibration-expiry fixtures remain a **separate increment** and are NOT
  simulated by this module.
* Runs of this module are L2 (software simulation) at best; the underlying
  schema decisions are L1.

The runner never invents behaviour: every state change is taken from the
declared ``mode_transitions`` of the schema, and every command step passes
through :class:`capability_admission.CapabilityAdmission`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from capability_admission import (
    AdmissionDecision,
    CapabilityAdmission,
    CapabilityCommand,
)
from capability_schema import CapabilitySchema, ModuleSpec

__all__ = [
    "CycleStepResult",
    "NormalCycleResult",
    "NormalCycleRunner",
]


@dataclass(frozen=True)
class CycleStepResult:
    """Result of executing one declared normal-cycle step."""

    index: int
    kind: str
    detail: str
    state_before: str
    state_after: str
    expected_state: str
    admission: Optional[AdmissionDecision] = None

    @property
    def matched(self) -> bool:
        """Whether the step reached the state the schema declares."""
        return self.state_after == self.expected_state


@dataclass(frozen=True)
class NormalCycleResult:
    """Result of executing the declared normal cycle of one module."""

    module_id: str
    initial_state: str
    terminal_state: str
    final_state: str
    steps: Tuple[CycleStepResult, ...] = field(default_factory=tuple)
    rejection: Optional[str] = None

    @property
    def ok(self) -> bool:
        """Whether every step matched its declared expected state."""
        if self.rejection is not None:
            return False
        return all(step.matched for step in self.steps) and self.final_state == self.terminal_state

    def to_dict(self) -> Dict[str, Any]:
        """Return a machine-readable summary of the cycle run."""
        return {
            "module_id": self.module_id,
            "initial_state": self.initial_state,
            "terminal_state": self.terminal_state,
            "final_state": self.final_state,
            "ok": self.ok,
            "rejection": self.rejection,
            "steps": [
                {
                    "index": step.index,
                    "kind": step.kind,
                    "detail": step.detail,
                    "state_before": step.state_before,
                    "state_after": step.state_after,
                    "expected_state": step.expected_state,
                    "matched": step.matched,
                    "admitted": None if step.admission is None else step.admission.admitted,
                }
                for step in self.steps
            ],
        }


class NormalCycleRunner:
    """Executes the declared normal cycle of a module from the schema."""

    def __init__(self, schema: CapabilitySchema, admission: Optional[CapabilityAdmission] = None) -> None:
        self._schema = schema
        self._admission = admission or CapabilityAdmission(schema)

    @property
    def schema(self) -> CapabilitySchema:
        """The capability schema this runner consumes."""
        return self._schema

    def run(self, module_id: str) -> NormalCycleResult:
        """Run the declared normal cycle of ``module_id``.

        Raises ``KeyError`` when the module is unknown to the schema.
        """
        module = self._schema.module(module_id)
        if module is None:
            raise KeyError(f"Unknown module {module_id!r} in capability schema")

        cycle = module.normal_cycle
        initial_state = str(cycle.get("initial_state"))
        terminal_state = str(cycle.get("terminal_state"))
        state = initial_state
        results: List[CycleStepResult] = []

        for index, step in enumerate(cycle.get("steps", ())):
            kind = str(step.get("kind"))
            expected_state = str(step.get("expect_state"))
            state_before = state
            admission: Optional[AdmissionDecision] = None
            detail = ""

            if kind == "command":
                capability = str(step.get("capability"))
                args = dict(step.get("args", {}))
                command = CapabilityCommand(
                    module_id=module.module_id,
                    capability=capability,
                    args=args,
                    observed_state=state,
                )
                decision = self._admission.admit(command)
                admission = decision
                detail = capability
                if not decision.admitted:
                    assert decision.error is not None
                    return NormalCycleResult(
                        module_id=module.module_id,
                        initial_state=initial_state,
                        terminal_state=terminal_state,
                        final_state=state,
                        steps=tuple(results),
                        rejection=decision.error.to_dict()["code"],
                    )
                state = self._next_state(module, "command", capability, state)
            elif kind == "event":
                trigger = str(step.get("trigger"))
                detail = trigger
                state = self._next_state(module, "event", trigger, state)
            elif kind == "observation":
                detail = str(step.get("trigger"))
                # An observation never changes the module state.
            else:  # pragma: no cover - guarded by schema validation
                raise ValueError(f"Unsupported normal-cycle step kind {kind!r}")

            results.append(
                CycleStepResult(
                    index=index,
                    kind=kind,
                    detail=detail,
                    state_before=state_before,
                    state_after=state,
                    expected_state=expected_state,
                    admission=admission,
                )
            )

        return NormalCycleResult(
            module_id=module.module_id,
            initial_state=initial_state,
            terminal_state=terminal_state,
            final_state=state,
            steps=tuple(results),
        )

    def run_all(self) -> Dict[str, NormalCycleResult]:
        """Run the declared normal cycle of every module in the schema."""
        return {module.module_id: self.run(module.module_id) for module in self._schema.modules}

    def _next_state(self, module: ModuleSpec, kind: str, value: str, state: str) -> str:
        """Resolve the next state from the declared mode transitions."""
        transitions = (
            module.command_transitions(value)
            if kind == "command"
            else module.event_transitions(value)
        )
        for transition in transitions:
            source = transition["from"]
            if source == "ANY" or source == state:
                return str(transition["to"])
        raise ValueError(
            f"Module {module.module_id!r} declares no {kind} transition {value!r} from state {state!r}"
        )
