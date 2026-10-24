"""TC-3 (partial): the NORMAL CYCLE fixture of each module is reproducible.

Evidence level: L1 (executable fixture + unit tests). A run of this fixture is
L2 (software simulation) at most.

SCOPE BOUNDARY — the full simulator fixture library is a SEPARATE INCREMENT.
This file covers the NORMAL CYCLE fixture only. The jam, missing-sensor,
limit-switch, E-stop, offline and calibration-expiry fixtures are NOT
implemented here and remain open.

TC-4 (measured pinout and tolerances) and TC-5 (power loss and safety stop)
require physical HIL evidence and are NOT claimed by this work.
"""

from __future__ import annotations

import pytest

from capability_admission import CapabilityAdmission
from capability_fixtures import NormalCycleRunner
from capability_schema import CapabilitySchema, load_capability_schema

EXPECTED_MODULE_IDS = (
    "conveyor-01",
    "sorting-01",
    "tower-crane-01",
    "parking-01",
    "forklift-01",
    "dump-truck-01",
    "packaging-01",
    "brackets-01",
    "combine-01",
)


@pytest.fixture(scope="module")
def schema() -> CapabilitySchema:
    """The canonical capability schema."""
    return load_capability_schema()


@pytest.fixture(scope="module")
def runner(schema: CapabilitySchema) -> NormalCycleRunner:
    """The normal-cycle fixture runner."""
    return NormalCycleRunner(schema, CapabilityAdmission(schema))


class TestTC3NormalCycle:
    """TC-3: the normal cycle of every module reaches its expected state."""

    @pytest.mark.parametrize("module_id", EXPECTED_MODULE_IDS)
    def test_normal_cycle_reaches_expected_state(self, runner: NormalCycleRunner, module_id: str) -> None:
        """Every declared step reaches the state the schema expects."""
        result = runner.run(module_id)

        assert result.rejection is None, f"{module_id} was rejected: {result.rejection}"
        assert result.steps, f"{module_id} declares no normal-cycle step"
        for step in result.steps:
            assert step.matched, (
                f"{module_id} step {step.index} ({step.kind} {step.detail}) reached "
                f"{step.state_after}, expected {step.expected_state}"
            )
        assert result.final_state == result.terminal_state

    @pytest.mark.parametrize("module_id", EXPECTED_MODULE_IDS)
    def test_normal_cycle_is_reproducible(self, runner: NormalCycleRunner, module_id: str) -> None:
        """Running the cycle twice yields the identical state trace."""
        first = runner.run(module_id)
        second = runner.run(module_id)

        assert first.to_dict() == second.to_dict()

    @pytest.mark.parametrize("module_id", EXPECTED_MODULE_IDS)
    def test_normal_cycle_command_steps_pass_the_admission_layer(
        self, runner: NormalCycleRunner, module_id: str
    ) -> None:
        """Every command step of the cycle is admitted by the real admission layer."""
        result = runner.run(module_id)

        for step in result.steps:
            if step.kind != "command":
                continue
            assert step.admission is not None, f"{module_id} step {step.index} skipped admission"
            assert step.admission.admitted is True

    def test_cycle_results_are_reproducible_across_the_whole_catalogue(
        self, runner: NormalCycleRunner
    ) -> None:
        """The whole-catalogue run is deterministic."""
        first = runner.run_all()
        second = runner.run_all()

        assert set(first) == set(EXPECTED_MODULE_IDS)
        assert all(result.ok for result in first.values())
        for module_id in first:
            assert first[module_id].to_dict() == second[module_id].to_dict()

    def test_unknown_module_raises(self, runner: NormalCycleRunner) -> None:
        """An unknown module cannot be run."""
        with pytest.raises(KeyError):
            runner.run("teleport-01")


class TestFixtureLibraryScope:
    """The remaining fixture library is explicitly out of scope for this card."""

    def test_only_the_normal_cycle_is_implemented(self, schema: CapabilitySchema) -> None:
        """Only NORMAL CYCLE fixtures exist; fault fixtures remain open."""
        for module in schema.modules:
            notes = module.normal_cycle.get("notes", "")
            assert notes, f"{module.module_id} declares no normal-cycle scope note"

    def test_open_increments_name_the_remaining_fixtures(self, schema: CapabilitySchema) -> None:
        """The schema records the fault fixtures as a separate increment."""
        open_increments = " ".join(schema.open_increments)
        assert "fixture library" in open_increments
        for fixture in ("jam", "missing sensor", "limit switch", "E-stop", "offline", "calibration"):
            assert fixture in open_increments
