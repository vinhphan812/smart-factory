"""Unit tests for the NGSI-LD Robot entity mapping (Issue #204).

Covers the positive path (verified capability) and the negative path
(unverified capability must degrade to UNKNOWN, never fabricate values).
"""

from datetime import datetime, timezone

from iot_gateway.adapters.orion_robot import (
    DEFAULT_FACTORY_ENTITY_ID,
    UNKNOWN_VALUE,
    DataQuality,
    RobotCapability,
    StaticRobotCapabilitySource,
    UnverifiedRobotCapabilitySource,
    VerificationStatus,
    robot_entity_id,
    to_robot_entity,
)


class TestUnverifiedSource:
    """The default source must never assert unmeasured robot state."""

    def test_all_measured_fields_are_unknown(self) -> None:
        source = UnverifiedRobotCapabilitySource()
        capability = source.fetch()

        assert capability.status == UNKNOWN_VALUE
        assert capability.battery_level is None
        assert capability.supported_actions == ()
        assert capability.verified is False
        assert capability.data_quality is DataQuality.UNKNOWN

    def test_observed_at_is_not_fabricated(self) -> None:
        source = UnverifiedRobotCapabilitySource()
        capability = source.fetch()

        assert capability.observed_at is None

    def test_robot_id_is_preserved(self) -> None:
        source = UnverifiedRobotCapabilitySource(robot_id="yanshee-02")
        assert source.fetch().robot_id == "yanshee-02"


class TestToRobotEntityUnverified:
    """Entity mapping of an unverified reading."""

    def _entity(self) -> dict:
        source = UnverifiedRobotCapabilitySource(name="UBTECH Yanshee")
        return to_robot_entity(source.fetch())

    def test_status_is_unknown(self) -> None:
        entity = self._entity()
        assert entity["status"]["value"] == UNKNOWN_VALUE

    def test_battery_is_unknown(self) -> None:
        entity = self._entity()
        assert entity["batteryLevel"]["value"] == UNKNOWN_VALUE
        assert entity["batteryLevel"]["type"] == "Text"

    def test_supported_actions_empty(self) -> None:
        entity = self._entity()
        assert entity["supportedActions"]["value"] == []

    def test_verification_status_is_unverified(self) -> None:
        entity = self._entity()
        assert (
            entity["verificationStatus"]["value"]
            == VerificationStatus.UNVERIFIED.value
        )

    def test_verification_source_is_recorded(self) -> None:
        entity = self._entity()
        assert entity["verificationSource"]["value"] == (
            "unverified-no-sdk-audit"
        )

    def test_data_quality_is_recorded(self) -> None:
        entity = self._entity()
        assert entity["dataQuality"]["value"] == DataQuality.UNKNOWN.value

    def test_observed_at_omitted_when_unknown(self) -> None:
        entity = self._entity()
        assert "observedAt" not in entity

    def test_entity_id_and_type(self) -> None:
        entity = self._entity()
        assert entity["id"] == "urn:ngsi-ld:Robot:yanshee-01"
        assert entity["type"] == "Robot"

    def test_name_falls_back_to_robot_id(self) -> None:
        capability = RobotCapability(robot_id="yanshee-07")
        entity = to_robot_entity(capability)
        assert entity["name"]["value"] == "yanshee-07"


class TestToRobotEntityVerified:
    """Entity mapping of a verified reading."""

    def _capability(self, **overrides) -> RobotCapability:
        defaults = dict(
            robot_id="yanshee-01",
            name="UBTECH Yanshee",
            status="idle",
            battery_level=87.5,
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk@0.1.0",
            data_quality=DataQuality.PHYSICAL,
            observed_at="2026-10-23T08:00:00+00:00",
            factory_entity_id=DEFAULT_FACTORY_ENTITY_ID,
        )
        defaults.update(overrides)
        return RobotCapability(**defaults)

    def test_status_reported(self) -> None:
        entity = to_robot_entity(self._capability())
        assert entity["status"]["value"] == "idle"

    def test_battery_is_numeric(self) -> None:
        entity = to_robot_entity(self._capability())
        assert entity["batteryLevel"]["type"] == "Number"
        assert entity["batteryLevel"]["value"] == 87.5

    def test_supported_actions_reported(self) -> None:
        entity = to_robot_entity(self._capability())
        assert entity["supportedActions"]["value"] == ["notify_operator"]

    def test_verification_status_is_verified(self) -> None:
        entity = to_robot_entity(self._capability())
        assert (
            entity["verificationStatus"]["value"]
            == VerificationStatus.VERIFIED.value
        )

    def test_data_quality_is_physical(self) -> None:
        entity = to_robot_entity(self._capability())
        assert entity["dataQuality"]["value"] == DataQuality.PHYSICAL.value

    def test_observed_at_present(self) -> None:
        entity = to_robot_entity(self._capability())
        assert entity["observedAt"]["value"] == "2026-10-23T08:00:00+00:00"

    def test_part_of_relationship_present(self) -> None:
        entity = to_robot_entity(self._capability())
        assert entity["partOf"]["type"] == "Relationship"
        assert entity["partOf"]["object"] == DEFAULT_FACTORY_ENTITY_ID

    def test_simulated_reading_is_labelled_simulated(self) -> None:
        capability = self._capability(data_quality=DataQuality.SIMULATED)
        entity = to_robot_entity(capability)
        assert entity["dataQuality"]["value"] == DataQuality.SIMULATED.value

    def test_verified_reading_without_observed_at_omits_it(self) -> None:
        capability = self._capability(observed_at=None)
        entity = to_robot_entity(capability)
        assert "observedAt" not in entity

    def test_static_source_returns_configured_capability(self) -> None:
        capability = self._capability()
        source = StaticRobotCapabilitySource(capability)
        assert source.fetch() is capability


class TestVerifiedGateOverridesStatus:
    """A verified=False reading must not leak a concrete status."""

    def test_concrete_status_is_suppressed(self) -> None:
        capability = RobotCapability(
            robot_id="yanshee-01",
            status="running",
            battery_level=50.0,
            supported_actions=("notify_operator",),
            verified=False,
        )
        entity = to_robot_entity(capability)

        assert entity["status"]["value"] == UNKNOWN_VALUE
        assert entity["batteryLevel"]["value"] == UNKNOWN_VALUE
        assert entity["supportedActions"]["value"] == []


class TestRobotSchemaRegistration:
    """The Robot entity must match the registered JSON Schema (L0 static)."""

    def _schema(self) -> dict:
        import json
        from pathlib import Path

        schema_path = (
            Path(__file__).resolve().parents[2]
            / "contracts"
            / "fiware"
            / "schemas"
            / "robot.json"
        )
        return json.loads(schema_path.read_text(encoding="utf-8"))

    def test_robot_schema_file_is_valid_json(self) -> None:
        schema = self._schema()
        assert schema["properties"]["type"]["const"] == "Robot"

    def test_schema_id_pattern_matches_entity_id(self) -> None:
        schema = self._schema()
        pattern = schema["properties"]["id"]["pattern"]
        entity = to_robot_entity(UnverifiedRobotCapabilitySource().fetch())
        import re

        assert re.match(pattern, entity["id"])

    def test_unverified_entity_satisfies_required_schema_keys(self) -> None:
        schema = self._schema()
        entity = to_robot_entity(UnverifiedRobotCapabilitySource().fetch())
        for key in schema["required"]:
            assert key in entity, f"missing required schema key: {key}"

    def test_verified_entity_satisfies_required_schema_keys(self) -> None:
        schema = self._schema()
        capability = RobotCapability(
            robot_id="yanshee-01",
            status="idle",
            battery_level=87.5,
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk@0.1.0",
            data_quality=DataQuality.PHYSICAL,
            observed_at="2026-10-23T08:00:00+00:00",
        )
        entity = to_robot_entity(capability)
        for key in schema["required"]:
            assert key in entity, f"missing required schema key: {key}"

    def test_verification_status_values_match_schema_enum(self) -> None:
        schema = self._schema()
        allowed = schema["properties"]["verificationStatus"]["properties"][
            "value"
        ]["enum"]
        for capability in (
            UnverifiedRobotCapabilitySource().fetch(),
            RobotCapability(robot_id="yanshee-01", verified=True),
        ):
            entity = to_robot_entity(capability)
            assert entity["verificationStatus"]["value"] in allowed

    def test_data_quality_values_match_schema_enum(self) -> None:
        schema = self._schema()
        allowed = schema["properties"]["dataQuality"]["properties"]["value"][
            "enum"
        ]
        for quality in (
            DataQuality.PHYSICAL,
            DataQuality.SIMULATED,
            DataQuality.UNKNOWN,
        ):
            capability = RobotCapability(
                robot_id="yanshee-01", data_quality=quality
            )
            entity = to_robot_entity(capability)
            assert entity["dataQuality"]["value"] in allowed


class TestRobotEntityId:
    """Entity id construction."""

    def test_id_format(self) -> None:
        assert robot_entity_id("yanshee-01") == "urn:ngsi-ld:Robot:yanshee-01"

    def test_id_matches_entity(self) -> None:
        capability = RobotCapability(robot_id="yanshee-03")
        entity = to_robot_entity(capability)
        assert entity["id"] == robot_entity_id("yanshee-03")


class TestRobotEntityValidatesAgainstSchema:
    """The produced entity must satisfy the registered JSON Schema, not just
    carry the required keys (Issue #204 / ADR-0017)."""

    def _schema(self) -> dict:
        import json
        from pathlib import Path

        schema_path = (
            Path(__file__).resolve().parents[2]
            / "contracts"
            / "fiware"
            / "schemas"
            / "robot.json"
        )
        return json.loads(schema_path.read_text(encoding="utf-8"))

    def test_unverified_entity_validates_against_robot_schema(self) -> None:
        import jsonschema

        entity = to_robot_entity(UnverifiedRobotCapabilitySource().fetch())
        jsonschema.validate(instance=entity, schema=self._schema())

    def test_verified_entity_validates_against_robot_schema(self) -> None:
        import jsonschema

        capability = RobotCapability(
            robot_id="yanshee-01",
            status="idle",
            battery_level=87.5,
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk@0.1.0",
            data_quality=DataQuality.PHYSICAL,
            observed_at="2026-10-24T08:00:00+00:00",
        )
        entity = to_robot_entity(capability)
        jsonschema.validate(instance=entity, schema=self._schema())
