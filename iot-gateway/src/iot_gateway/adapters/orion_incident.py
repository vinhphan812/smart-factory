"""NGSI-LD Alert projection of Gateway incidents (Issue #204).

The Gateway owns the authoritative incident record
(:class:`iot_gateway.incidents.IncidentStore`). This module projects that
record onto an NGSI-LD ``Alert`` entity so that context consumers (Unity,
React dashboard, Yanshee response policy, research reports) can read it
through the FIWARE context layer.

Boundaries (ADR-0014 invariant 6, Issue #204 SPEC-2):

- The projection is a **read model**. It is not the authorization truth and
  it never replaces the Gateway incident store.
- Every alert carries provenance: ``traceId``, ``sourceEventId``,
  ``sourceSystem`` and the operator state, so a consumer can walk back to the
  originating Gateway event.
- The module never dispatches a robot skill. Skill dispatch stays exclusive
  to the Gateway-approved incident outbox.

Evidence level: L1 (unit).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .orion_robot import DataQuality, UNKNOWN_VALUE

#: Source system recorded on every projected alert.
SOURCE_SYSTEM = "iot-gateway"

#: Mapping of Gateway incident severity onto NGSI-LD alert severity.
SEVERITY_MAP: dict[str, str] = {
    "INFO": "info",
    "WARNING": "warning",
    "CRITICAL": "critical",
}

#: Mapping of Gateway incident status onto NGSI-LD alert status.
STATUS_MAP: dict[str, str] = {
    "open": "active",
    "acknowledged": "acknowledged",
    "resolved": "resolved",
}


@dataclass(frozen=True)
class IncidentProjection:
    """Inputs required to project an incident onto an NGSI-LD ``Alert``.

    Attributes:
        incident: The Gateway incident mapping (as produced by
            ``IncidentStore.query()`` / ``IncidentStore.get()``).
        trace_id: Trace identifier tying the alert to the originating
            request/decision chain. ``None`` yields ``UNKNOWN``.
        source_event_id: Gateway canonical event id that produced the
            incident. ``None`` yields ``UNKNOWN``.
        module_entity_id: NGSI-LD id of the Module the alert concerns.
        sensor_entity_id: NGSI-LD id of the Sensor that produced the alert.
        data_quality: Whether the underlying observation is physical or
            simulated.
    """

    incident: dict[str, Any]
    trace_id: str | None = None
    source_event_id: str | None = None
    module_entity_id: str | None = None
    sensor_entity_id: str | None = None
    data_quality: DataQuality = DataQuality.UNKNOWN


def alert_entity_id(incident_id: str) -> str:
    """Build the canonical NGSI-LD entity id for an alert."""
    return f"urn:ngsi-ld:Alert:{incident_id}"


def _operator_state(incident: dict[str, Any]) -> str:
    """Derive the operator-facing state of an incident."""
    if incident.get("resolved_at"):
        return "resolved"
    if incident.get("acknowledged_at"):
        return "acknowledged"
    return "unacknowledged"


def to_alert_entity(projection: IncidentProjection) -> dict:
    """Project a Gateway incident onto an NGSI-LD ``Alert`` entity."""
    incident = projection.incident
    incident_id = str(incident.get("id") or "unknown")

    severity = SEVERITY_MAP.get(
        str(incident.get("severity") or "").upper(), "info"
    )
    status = STATUS_MAP.get(
        str(incident.get("status") or "open").lower(), "active"
    )

    entity: dict = {
        "id": alert_entity_id(incident_id),
        "type": "Alert",
        "name": {
            "type": "Text",
            "value": str(incident.get("title") or incident_id),
        },
        "severity": {
            "type": "Text",
            "value": severity,
        },
        "category": {
            "type": "Text",
            "value": _category_for(incident),
        },
        "description": {
            "type": "Text",
            "value": str(incident.get("message") or ""),
        },
        "status": {
            "type": "Text",
            "value": status,
        },
        "timestamp": {
            "type": "DateTime",
            "value": str(
                incident.get("timestamp")
                or datetime.now(timezone.utc).isoformat()
            ),
        },
        "createdAt": {
            "type": "DateTime",
            "value": str(
                incident.get("timestamp")
                or datetime.now(timezone.utc).isoformat()
            ),
        },
        # --- provenance -------------------------------------------------
        "traceId": {
            "type": "Text",
            "value": projection.trace_id or UNKNOWN_VALUE,
        },
        "sourceEventId": {
            "type": "Text",
            "value": projection.source_event_id or UNKNOWN_VALUE,
        },
        "sourceSystem": {
            "type": "Text",
            "value": SOURCE_SYSTEM,
        },
        "incidentId": {
            "type": "Text",
            "value": incident_id,
        },
        "deviceId": {
            "type": "Text",
            "value": str(incident.get("device_id") or UNKNOWN_VALUE),
        },
        "dataQuality": {
            "type": "Text",
            "value": projection.data_quality.value,
        },
        # --- operator state ---------------------------------------------
        "operatorState": {
            "type": "Text",
            "value": _operator_state(incident),
        },
    }

    if incident.get("recommended_action"):
        entity["recommendedAction"] = {
            "type": "Text",
            "value": str(incident["recommended_action"]),
        }
    if incident.get("acknowledged_by"):
        entity["acknowledgedBy"] = {
            "type": "Text",
            "value": str(incident["acknowledged_by"]),
        }
    if incident.get("acknowledged_at"):
        entity["acknowledgedAt"] = {
            "type": "DateTime",
            "value": str(incident["acknowledged_at"]),
        }
    if incident.get("resolved_by"):
        entity["resolvedBy"] = {
            "type": "Text",
            "value": str(incident["resolved_by"]),
        }
    if incident.get("resolved_at"):
        entity["resolvedAt"] = {
            "type": "DateTime",
            "value": str(incident["resolved_at"]),
        }

    # --- relationships ---------------------------------------------------
    if projection.module_entity_id:
        entity["relatedTo"] = {
            "type": "Relationship",
            "object": projection.module_entity_id,
        }
    if projection.sensor_entity_id:
        entity["relatedToSensor"] = {
            "type": "Relationship",
            "object": projection.sensor_entity_id,
        }

    return entity


def _category_for(incident: dict[str, Any]) -> str:
    """Map an incident onto an NGSI-LD alert category.

    The Gateway incident record carries a free-form ``source`` string. Only
    explicit, unambiguous matches are mapped; anything else falls back to
    ``equipment`` rather than inventing a more specific category.
    """
    source = str(incident.get("source") or "").lower()
    if "safety" in source or "estop" in source or "e_stop" in source:
        return "safety"
    if "quality" in source:
        return "quality"
    if "performance" in source or "throughput" in source:
        return "performance"
    if "anomaly" in source or "sensor" in source:
        return "anomaly"
    return "equipment"
