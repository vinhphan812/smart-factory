"""Unit tests for the NGSI-LD incident -> Alert projection (Issue #204).

Verifies that the projection is a faithful read model carrying provenance
(trace id, source event id) and operator state, and that it does not mutate
or replace the Gateway incident store.
"""

from iot_gateway.adapters.orion_incident import (
    SOURCE_SYSTEM,
    IncidentProjection,
    alert_entity_id,
    to_alert_entity,
)
from iot_gateway.adapters.orion_robot import DataQuality, UNKNOWN_VALUE


def _incident(**overrides) -> dict:
    base = {
        "id": "INC-001",
        "severity": "CRITICAL",
        "device_id": "conveyor-01",
        "title": "Conveyor belt motor overheating",
        "message": "Temperature sensor reports 85C, exceeds threshold of 75C.",
        "timestamp": "2026-10-23T08:00:00+00:00",
        "status": "open",
        "source": "temperature-sensor",
        "recommended_action": "Check motor cooling system and reduce load",
        "acknowledged_by": None,
        "acknowledged_at": None,
        "resolved_by": None,
        "resolved_at": None,
        "notes": None,
        "audit_trail": [],
    }
    base.update(overrides)
    return base


class TestAlertIdentity:
    """Entity identity."""

    def test_entity_id_format(self) -> None:
        assert alert_entity_id("INC-001") == "urn:ngsi-ld:Alert:INC-001"

    def test_entity_type_is_alert(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["type"] == "Alert"

    def test_entity_id_uses_incident_id(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["id"] == "urn:ngsi-ld:Alert:INC-001"

    def test_incident_id_is_carried(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["incidentId"]["value"] == "INC-001"


class TestAlertSeverityAndStatus:
    """Severity, status and category mapping."""

    def test_critical_maps_to_critical(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["severity"]["value"] == "critical"

    def test_warning_maps_to_warning(self) -> None:
        incident = _incident(severity="WARNING")
        entity = to_alert_entity(IncidentProjection(incident=incident))
        assert entity["severity"]["value"] == "warning"

    def test_info_maps_to_info(self) -> None:
        incident = _incident(severity="INFO")
        entity = to_alert_entity(IncidentProjection(incident=incident))
        assert entity["severity"]["value"] == "info"

    def test_unknown_severity_falls_back_to_info(self) -> None:
        incident = _incident(severity="WEIRD")
        entity = to_alert_entity(IncidentProjection(incident=incident))
        assert entity["severity"]["value"] == "info"

    def test_open_maps_to_active(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["status"]["value"] == "active"

    def test_acknowledged_maps_to_acknowledged(self) -> None:
        incident = _incident(status="acknowledged")
        entity = to_alert_entity(IncidentProjection(incident=incident))
        assert entity["status"]["value"] == "acknowledged"

    def test_resolved_maps_to_resolved(self) -> None:
        incident = _incident(status="resolved")
        entity = to_alert_entity(IncidentProjection(incident=incident))
        assert entity["status"]["value"] == "resolved"

    def test_sensor_source_maps_to_anomaly_category(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["category"]["value"] == "anomaly"

    def test_safety_source_maps_to_safety_category(self) -> None:
        incident = _incident(source="safety-loop")
        entity = to_alert_entity(IncidentProjection(incident=incident))
        assert entity["category"]["value"] == "safety"

    def test_unknown_source_maps_to_equipment(self) -> None:
        incident = _incident(source="")
        entity = to_alert_entity(IncidentProjection(incident=incident))
        assert entity["category"]["value"] == "equipment"


class TestAlertProvenance:
    """Provenance fields required by SPEC-2 / TC-1."""

    def test_trace_id_is_carried(self) -> None:
        projection = IncidentProjection(
            incident=_incident(), trace_id="trace-abc-123"
        )
        entity = to_alert_entity(projection)
        assert entity["traceId"]["value"] == "trace-abc-123"

    def test_source_event_id_is_carried(self) -> None:
        projection = IncidentProjection(
            incident=_incident(), source_event_id="evt-42"
        )
        entity = to_alert_entity(projection)
        assert entity["sourceEventId"]["value"] == "evt-42"

    def test_missing_trace_id_is_unknown_not_fabricated(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["traceId"]["value"] == UNKNOWN_VALUE

    def test_missing_source_event_id_is_unknown(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["sourceEventId"]["value"] == UNKNOWN_VALUE

    def test_source_system_is_gateway(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["sourceSystem"]["value"] == SOURCE_SYSTEM

    def test_device_id_is_carried(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["deviceId"]["value"] == "conveyor-01"

    def test_data_quality_is_recorded(self) -> None:
        projection = IncidentProjection(
            incident=_incident(), data_quality=DataQuality.SIMULATED
        )
        entity = to_alert_entity(projection)
        assert entity["dataQuality"]["value"] == DataQuality.SIMULATED.value


class TestAlertOperatorState:
    """Operator state fields."""

    def test_open_incident_is_unacknowledged(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["operatorState"]["value"] == "unacknowledged"

    def test_acknowledged_incident_reports_operator(self) -> None:
        incident = _incident(
            status="acknowledged",
            acknowledged_by="operator-001",
            acknowledged_at="2026-10-23T08:05:00+00:00",
        )
        entity = to_alert_entity(IncidentProjection(incident=incident))
        assert entity["operatorState"]["value"] == "acknowledged"
        assert entity["acknowledgedBy"]["value"] == "operator-001"
        assert (
            entity["acknowledgedAt"]["value"] == "2026-10-23T08:05:00+00:00"
        )

    def test_resolved_incident_reports_resolution(self) -> None:
        incident = _incident(
            status="resolved",
            acknowledged_by="operator-001",
            acknowledged_at="2026-10-23T08:05:00+00:00",
            resolved_by="operator-002",
            resolved_at="2026-10-23T09:00:00+00:00",
        )
        entity = to_alert_entity(IncidentProjection(incident=incident))
        assert entity["operatorState"]["value"] == "resolved"
        assert entity["resolvedBy"]["value"] == "operator-002"
        assert entity["resolvedAt"]["value"] == "2026-10-23T09:00:00+00:00"

    def test_recommended_action_is_carried(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert entity["recommendedAction"]["value"] == (
            "Check motor cooling system and reduce load"
        )


class TestAlertRelationships:
    """Relationship fields linking the alert to Module/Sensor."""

    def test_related_to_module(self) -> None:
        projection = IncidentProjection(
            incident=_incident(),
            module_entity_id="urn:ngsi-ld:Module:conveyor-01",
        )
        entity = to_alert_entity(projection)
        assert entity["relatedTo"]["type"] == "Relationship"
        assert entity["relatedTo"]["object"] == (
            "urn:ngsi-ld:Module:conveyor-01"
        )

    def test_related_to_sensor(self) -> None:
        projection = IncidentProjection(
            incident=_incident(),
            sensor_entity_id="urn:ngsi-ld:Sensor:conveyor-temp-01",
        )
        entity = to_alert_entity(projection)
        assert entity["relatedToSensor"]["object"] == (
            "urn:ngsi-ld:Sensor:conveyor-temp-01"
        )

    def test_no_relationship_keys_when_unlinked(self) -> None:
        entity = to_alert_entity(IncidentProjection(incident=_incident()))
        assert "relatedTo" not in entity
        assert "relatedToSensor" not in entity


class TestProjectionDoesNotMutateIncident:
    """The projection is a read model; it must not alter the source."""

    def test_source_incident_is_unchanged(self) -> None:
        incident = _incident()
        snapshot = dict(incident)
        to_alert_entity(IncidentProjection(incident=incident))
        assert incident == snapshot

    def test_projection_is_deterministic(self) -> None:
        incident = _incident()
        first = to_alert_entity(IncidentProjection(incident=incident))
        second = to_alert_entity(IncidentProjection(incident=incident))
        assert first == second
