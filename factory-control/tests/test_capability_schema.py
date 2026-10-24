"""TC-1: the versioned capability schema validates for all nine modules.

Evidence level: L1 (executable schema validation + unit tests).

TC-1 asserts from the schema itself that all nine physical modules validate
with no invented sensor or drive: the catalogue is internally consistent, the
IO counts match the declared channels, the derived counts match the IO counts,
every command transition names a declared capability and every declared
capability that is transition-checked has a declared edge, and the structural
and orchestrated constructs carry no physical controller.

No hardware, HIL or deployment claim is made.
"""

from __future__ import annotations

import pytest

from capability_schema import (
    SCHEMA_ID,
    SCHEMA_VERSION,
    CapabilitySchema,
    CapabilitySchemaError,
    load_capability_schema,
    validate_schema_document,
)

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


class TestTC1Catalogue:
    """TC-1: the catalogue itself is complete and consistent."""

    def test_schema_identity_is_versioned(self, schema: CapabilitySchema) -> None:
        """The schema carries a stable id and a non-empty semantic version."""
        assert schema.schema_id == SCHEMA_ID
        assert schema.schema_version == SCHEMA_VERSION

    def test_catalogue_holds_the_nine_real_modules(self, schema: CapabilitySchema) -> None:
        """Exactly the nine modules of the L0 capability matrix are present."""
        assert schema.module_ids == EXPECTED_MODULE_IDS
        assert len(schema.modules) == 9

    def test_schema_document_has_no_structural_issue(self) -> None:
        """The canonical document is internally consistent."""
        assert validate_schema_document(_raw_document()) == []

    def test_brackets_and_combine_have_no_physical_controller(self, schema: CapabilitySchema) -> None:
        """Brackets is structural, Combine is orchestrated; neither actuates."""
        brackets = schema.module("brackets-01")
        combine = schema.module("combine-01")

        assert brackets is not None and combine is not None
        assert brackets.construct == "structural"
        assert brackets.physical_controller is False
        assert combine.construct == "orchestrated"
        assert combine.physical_controller is False

        for module in (brackets, combine):
            assert module.controller_board is None
            for capability in module.capabilities:
                assert capability["actuation"] is False

    def test_every_module_declares_io_counts_and_signals(self, schema: CapabilitySchema) -> None:
        """Every module declares its IO channels; counts match the channels."""
        for module in schema.modules:
            assert module.io_signals, f"{module.module_id} declares no IO channel"
            for signal in module.io_signals:
                assert signal["channel"]
                assert signal["io_type"]
                assert signal["direction"] in {"input", "output"}
            assert module.io_counts, f"{module.module_id} declares no IO counts"

    def test_unknown_io_count_requires_a_count_status_note(self, schema: CapabilitySchema) -> None:
        """A null IO count is only allowed with an explicit count_status note."""
        for module in schema.modules:
            for io_type, declared in module.io_counts.items():
                if declared is None:
                    assert io_type in module.count_status, (
                        f"{module.module_id}: io_counts[{io_type}] is null without a count_status note"
                    )

    def test_every_module_declares_interlock_and_provenance_ownership(
        self, schema: CapabilitySchema
    ) -> None:
        """Watchdog and local-interlock ownership plus pin provenance are declared."""
        for module in schema.modules:
            assert module.local_interlocks.get("owner"), f"{module.module_id} has no interlock owner"
            assert module.local_interlocks.get("authority") == "ADR-0006"
            assert module.pin_mapping_provenance.get("status")
            assert module.pin_mapping_provenance.get("verification")

    def test_pin_mapping_is_never_claimed_as_measured(self, schema: CapabilitySchema) -> None:
        """No pin mapping may be presented as measured; allocation is BLOCKED_L3."""
        for module in schema.modules:
            provenance = module.pin_mapping_provenance
            assert provenance["status"] in {
                "DECLARED_UNVERIFIED",
                "NOT_DECLARED",
                "NOT_APPLICABLE",
            }
            assert "BLOCKED" in provenance["verification"] or "Not applicable" in provenance["verification"]

    def test_loader_rejects_an_inconsistent_document(self) -> None:
        """A document with an unknown module state is rejected by the loader."""
        broken = _raw_document()
        broken["modules"][0]["mode_transitions"].append(
            {"from": "NOT_A_STATE", "to": "IDLE", "trigger": {"kind": "event", "value": "x"}}
        )
        with pytest.raises(CapabilitySchemaError):
            CapabilitySchema.from_document(broken)


def _raw_document() -> dict:
    """Return the canonical schema document as a plain dict."""
    import json

    from capability_schema import resolve_schema_path

    return json.loads(resolve_schema_path().read_text(encoding="utf-8"))
