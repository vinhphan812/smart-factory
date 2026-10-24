"""TC-2: capability admission rejects invalid commands before any actuator path.

Evidence level: L1 (executable admission validation + unit/integration tests).

TC-2 covers the negative admission behaviour required by issue #174:

* a command addressed to an unknown module is rejected;
* a command addressed to a module that does not support the requested
  capability is rejected;
* a command whose value is outside the declared range is rejected;
* a command that would make an illegal transition is rejected;
* every rejection is typed, machine-readable and names the module, the
  capability and the violated constraint;
* the rejection happens **in the admission layer**, not downstream — the
  actuator callable is never invoked for a rejected command.

The tests use the real schema and the real admission code path. No hardware,
HIL or deployment claim is made.
"""

from __future__ import annotations

import pytest

from capability_admission import (
    ADMISSION_ERROR_CODES,
    AdmissionErrorCode,
    CapabilityAdmission,
    CapabilityAdmissionError,
    CapabilityCommand,
)
from capability_schema import CapabilitySchema, load_capability_schema


@pytest.fixture(scope="module")
def schema() -> CapabilitySchema:
    """The canonical capability schema."""
    return load_capability_schema()


@pytest.fixture(scope="module")
def admission(schema: CapabilitySchema) -> CapabilityAdmission:
    """The admission layer under test."""
    return CapabilityAdmission(schema)


class _ActuatorSpy:
    """Records whether the actuator path was reached."""

    def __init__(self) -> None:
        self.calls = []

    def __call__(self, command: CapabilityCommand):
        self.calls.append(command)
        return "actuated"


class TestTC2Rejections:
    """TC-2: invalid commands are rejected by the admission layer."""

    def test_unknown_module_is_rejected(self, admission: CapabilityAdmission) -> None:
        """A command addressed to a module absent from the schema is rejected."""
        decision = admission.admit(
            CapabilityCommand(module_id="teleport-01", capability="CONVEYOR_START")
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.UNKNOWN_MODULE.value
        assert decision.error is not None
        assert decision.error.module_id == "teleport-01"
        assert decision.error.capability == "CONVEYOR_START"
        assert decision.error.constraint == "module:teleport-01"
        assert "teleport-01" in decision.error.detail

    def test_capability_mismatch_is_rejected(self, admission: CapabilityAdmission) -> None:
        """A capability the addressed module does not support is rejected."""
        decision = admission.admit(
            CapabilityCommand(module_id="sorting-01", capability="CONVEYOR_START")
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.CAPABILITY_NOT_SUPPORTED.value
        assert decision.error is not None
        assert decision.error.module_id == "sorting-01"
        assert decision.error.capability == "CONVEYOR_START"
        assert decision.error.constraint == "capability:CONVEYOR_START"

    def test_capability_of_another_module_is_not_borrowed(self, admission: CapabilityAdmission) -> None:
        """Every module accepts exactly the capabilities the L0 matrix declares."""
        schema = admission.schema
        for module in schema.modules:
            for capability in module.capabilities:
                transitions = module.command_transitions(capability["name"])
                observed_state = None
                if transitions:
                    sources = {transition["from"] for transition in transitions}
                    observed_state = None if "ANY" in sources else sorted(sources)[0]

                decision = admission.admit(
                    CapabilityCommand(
                        module_id=module.module_id,
                        capability=capability["name"],
                        observed_state=observed_state,
                    )
                )
                assert decision.admitted is True, (
                    f"{module.module_id}.{capability['name']} was rejected: "
                    f"{decision.error.to_dict() if decision.error else None}"
                )

    def test_value_outside_declared_range_is_rejected(self, admission: CapabilityAdmission) -> None:
        """A value outside the schema-declared range is rejected."""
        decision = admission.admit(
            CapabilityCommand(
                module_id="conveyor-01",
                capability="CONVEYOR_START",
                args={"speedMmPerSec": 500},
                observed_state="IDLE",
            )
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.ARGUMENT_OUT_OF_RANGE.value
        assert decision.error is not None
        assert decision.error.constraint == "range:speedMmPerSec:10..100"
        assert "500" in decision.error.detail

    def test_value_outside_declared_allowed_set_is_rejected(
        self, admission: CapabilityAdmission
    ) -> None:
        """A value outside the declared allowed set is rejected."""
        decision = admission.admit(
            CapabilityCommand(
                module_id="sorting-01",
                capability="ROUTE_MANUAL",
                args={"destination": "BIN_99"},
                observed_state="IDLE",
            )
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.ARGUMENT_VALUE_NOT_ALLOWED.value
        assert decision.error is not None
        assert decision.error.constraint.startswith("allowed_values:destination:")

    def test_illegal_transition_is_rejected(self, admission: CapabilityAdmission) -> None:
        """A command that is not a declared edge from the observed state is rejected."""
        decision = admission.admit(
            CapabilityCommand(
                module_id="conveyor-01",
                capability="CONVEYOR_START",
                args={"speedMmPerSec": 50},
                observed_state="RUNNING",
            )
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.ILLEGAL_TRANSITION.value
        assert decision.error is not None
        assert decision.error.constraint == "transition:CONVEYOR_START:RUNNING"
        assert "IDLE" in decision.error.detail

    def test_unknown_observed_state_is_rejected_not_inferred(self, admission: CapabilityAdmission) -> None:
        """An unknown or stale observed state is never inferred into a safe state."""
        decision = admission.admit(
            CapabilityCommand(
                module_id="conveyor-01",
                capability="CONVEYOR_START",
                args={"speedMmPerSec": 50},
                observed_state=None,
            )
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.STATE_UNKNOWN.value

    def test_unknown_argument_is_rejected(self, admission: CapabilityAdmission) -> None:
        """An argument the capability does not declare is rejected."""
        decision = admission.admit(
            CapabilityCommand(
                module_id="conveyor-01",
                capability="CONVEYOR_START",
                args={"speed": 50},
                observed_state="IDLE",
            )
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.UNKNOWN_ARGUMENT.value

    def test_wrong_argument_type_is_rejected(self, admission: CapabilityAdmission) -> None:
        """An argument of the wrong declared type is rejected."""
        decision = admission.admit(
            CapabilityCommand(
                module_id="conveyor-01",
                capability="CONVEYOR_START",
                args={"speedMmPerSec": "fast"},
                observed_state="IDLE",
            )
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.INVALID_ARGUMENT_TYPE.value

    def test_actuation_on_a_construct_without_controller_is_rejected(
        self, admission: CapabilityAdmission
    ) -> None:
        """The structural and orchestrated constructs cannot be actuated remotely."""
        for module_id in ("brackets-01", "combine-01"):
            decision = admission.admit(
                CapabilityCommand(module_id=module_id, capability="CONVEYOR_START")
            )
            assert decision.admitted is False
            assert decision.code == AdmissionErrorCode.CAPABILITY_NOT_SUPPORTED.value


class TestTC2RejectionHappensInTheAdmissionLayer:
    """TC-2: the rejection happens upstream, not in a downstream component."""

    def test_rejected_command_never_reaches_the_actuator(self, admission: CapabilityAdmission) -> None:
        """The actuator callable is not invoked for an unknown-module command."""
        actuator = _ActuatorSpy()
        decision = admission.dispatch(
            CapabilityCommand(module_id="teleport-01", capability="CONVEYOR_START"),
            actuator,
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.UNKNOWN_MODULE.value
        assert actuator.calls == []

    def test_capability_mismatch_never_reaches_the_actuator(
        self, admission: CapabilityAdmission
    ) -> None:
        """The actuator callable is not invoked for a capability mismatch."""
        actuator = _ActuatorSpy()
        decision = admission.dispatch(
            CapabilityCommand(module_id="sorting-01", capability="CONVEYOR_START"),
            actuator,
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.CAPABILITY_NOT_SUPPORTED.value
        assert actuator.calls == []

    def test_out_of_range_value_never_reaches_the_actuator(
        self, admission: CapabilityAdmission
    ) -> None:
        """The actuator callable is not invoked for an out-of-range value."""
        actuator = _ActuatorSpy()
        decision = admission.dispatch(
            CapabilityCommand(
                module_id="conveyor-01",
                capability="CONVEYOR_START",
                args={"speedMmPerSec": 500},
                observed_state="IDLE",
            ),
            actuator,
        )

        assert decision.admitted is False
        assert decision.code == AdmissionErrorCode.ARGUMENT_OUT_OF_RANGE.value
        assert actuator.calls == []

    def test_admitted_command_does_reach_the_actuator(self, admission: CapabilityAdmission) -> None:
        """The admission layer admits a valid command and forwards it."""
        actuator = _ActuatorSpy()
        decision = admission.dispatch(
            CapabilityCommand(
                module_id="conveyor-01",
                capability="CONVEYOR_START",
                args={"speedMmPerSec": 50},
                observed_state="IDLE",
            ),
            actuator,
        )

        assert decision.admitted is True
        assert decision.error is None
        assert len(actuator.calls) == 1


class TestTC2ErrorContract:
    """TC-2: rejections are typed and machine-readable."""

    def test_error_payload_shape(self, admission: CapabilityAdmission) -> None:
        """The machine-readable payload names module, capability and constraint."""
        decision = admission.admit(
            CapabilityCommand(module_id="teleport-01", capability="CONVEYOR_START")
        )
        assert decision.error is not None

        payload = decision.error.to_dict()
        assert set(payload) == {
            "code",
            "module_id",
            "capability",
            "constraint",
            "detail",
            "evidence_level",
        }
        assert payload["code"] == AdmissionErrorCode.UNKNOWN_MODULE.value
        assert payload["module_id"] == "teleport-01"
        assert payload["capability"] == "CONVEYOR_START"
        assert payload["constraint"]
        assert payload["detail"]
        assert payload["evidence_level"] == "L1"

    def test_error_is_an_exception_with_machine_readable_attributes(
        self, admission: CapabilityAdmission
    ) -> None:
        """The typed error carries the same fields as the payload."""
        error = CapabilityAdmissionError(
            code=AdmissionErrorCode.ILLEGAL_TRANSITION,
            module_id="conveyor-01",
            capability="CONVEYOR_START",
            constraint="transition:CONVEYOR_START:RUNNING",
            detail="detail",
        )
        assert isinstance(error, Exception)
        assert error.code is AdmissionErrorCode.ILLEGAL_TRANSITION
        assert error.to_dict()["code"] == "ILLEGAL_TRANSITION"

    def test_error_codes_match_the_schema_contract(self, schema: CapabilitySchema) -> None:
        """The schema's declared rejection codes match the implemented codes."""
        declared = schema.admission_contract.get("error_codes", [])
        assert sorted(declared) == sorted(ADMISSION_ERROR_CODES)
