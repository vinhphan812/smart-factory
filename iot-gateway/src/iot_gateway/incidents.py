"""In-memory incident store with audit trail for the IoT Gateway."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class IncidentStatus:
    """Incident status constants."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class IncidentSeverity:
    """Incident severity constants."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class IncidentAuditEntry:
    """Audit trail entry for incident state changes."""
    id: str
    incident_id: str
    action: str  # created, acknowledged, resolved, note_added
    operator_id: str | None = None
    operator_name: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "action": self.action,
            "operator_id": self.operator_id,
            "operator_name": self.operator_name,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class Incident:
    """Incident data model."""
    id: str
    severity: str
    device_id: str
    title: str
    message: str
    timestamp: str
    status: str = IncidentStatus.OPEN
    source: str | None = None
    recommended_action: str | None = None
    acknowledged_by: str | None = None
    acknowledged_at: str | None = None
    resolved_by: str | None = None
    resolved_at: str | None = None
    notes: str | None = None
    audit_trail: list[IncidentAuditEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "device_id": self.device_id,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp,
            "status": self.status,
            "source": self.source,
            "recommended_action": self.recommended_action,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at,
            "notes": self.notes,
            "audit_trail": [entry.to_dict() for entry in self.audit_trail],
        }


class IncidentStore:
    """In-memory incident store with audit trail support."""

    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        # Seed with some demo incidents for testing
        self._seed_demo_incidents()

    def _seed_demo_incidents(self) -> None:
        """Create demo incidents for testing."""
        demo_incidents = [
            Incident(
                id="INC-001",
                severity=IncidentSeverity.CRITICAL,
                device_id="conveyor-01",
                title="Conveyor belt motor overheating",
                message="Temperature sensor reports 85°C, exceeds threshold of 75°C. Immediate attention required.",
                timestamp=datetime.now(timezone.utc).isoformat(),
                status=IncidentStatus.OPEN,
                source="temperature-sensor",
                recommended_action="Check motor cooling system and reduce load",
            ),
            Incident(
                id="INC-002",
                severity=IncidentSeverity.WARNING,
                device_id="robotic-arm-01",
                title="Servo motor calibration drift detected",
                message="Position accuracy deviation > 2mm from expected trajectory.",
                timestamp=datetime.now(timezone.utc).isoformat(),
                status=IncidentStatus.ACKNOWLEDGED,
                acknowledged_by="operator-001",
                acknowledged_at=datetime.now(timezone.utc).isoformat(),
                source="motion-controller",
                recommended_action="Recalibrate servo motors",
            ),
            Incident(
                id="INC-003",
                severity=IncidentSeverity.INFO,
                device_id="cnc-mill-01",
                title="Scheduled maintenance reminder",
                message="Spindle bearing replacement due in 500 operating hours.",
                timestamp=datetime.now(timezone.utc).isoformat(),
                status=IncidentStatus.RESOLVED,
                acknowledged_by="operator-001",
                acknowledged_at=datetime.now(timezone.utc).isoformat(),
                resolved_by="operator-002",
                resolved_at=datetime.now(timezone.utc).isoformat(),
                source="maintenance-scheduler",
                recommended_action="Schedule bearing replacement",
            ),
        ]

        for inc in demo_incidents:
            self._incidents[inc.id] = inc
            # Add created audit entry
            inc.audit_trail.append(
                IncidentAuditEntry(
                    id=str(uuid.uuid4()),
                    incident_id=inc.id,
                    action="created",
                    details=f"Incident created from {inc.source}",
                )
            )

    def query(
        self,
        status: str | None = None,
        severity: str | None = None,
        device_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query incidents with optional filters."""
        results = list(self._incidents.values())

        if status:
            results = [i for i in results if i.status == status]
        if severity:
            results = [i for i in results if i.severity == severity]
        if device_id:
            results = [i for i in results if i.device_id == device_id]

        # Sort by timestamp descending (most recent first)
        results.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply limit
        return [i.to_dict() for i in results[:limit]]

    def get(self, incident_id: str) -> dict[str, Any] | None:
        """Get a single incident by ID."""
        incident = self._incidents.get(incident_id)
        return incident.to_dict() if incident else None

    def acknowledge(
        self, incident_id: str, operator_id: str, notes: str | None = None
    ) -> dict[str, Any] | None:
        """Acknowledge an incident."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return None

        if incident.status == IncidentStatus.RESOLVED:
            logger.warning(f"Cannot acknowledge resolved incident {incident_id}")
            return incident.to_dict()

        if incident.status != IncidentStatus.ACKNOWLEDGED:
            incident.status = IncidentStatus.ACKNOWLEDGED
            incident.acknowledged_by = operator_id
            incident.acknowledged_at = datetime.now(timezone.utc).isoformat()

            # Add audit entry
            audit_entry = IncidentAuditEntry(
                id=str(uuid.uuid4()),
                incident_id=incident_id,
                action="acknowledged",
                operator_id=operator_id,
                details=notes,
            )
            incident.audit_trail.append(audit_entry)

            # Update notes if provided
            if notes:
                if incident.notes:
                    incident.notes = f"{incident.notes}\n\n[{datetime.now(timezone.utc).isoformat()}] Acknowledged: {notes}"
                else:
                    incident.notes = f"[{datetime.now(timezone.utc).isoformat()}] Acknowledged: {notes}"

        return incident.to_dict()

    def resolve(
        self, incident_id: str, operator_id: str, notes: str | None = None
    ) -> dict[str, Any] | None:
        """Resolve an incident."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return None

        if incident.status == IncidentStatus.RESOLVED:
            logger.warning(f"Incident {incident_id} already resolved")
            return incident.to_dict()

        incident.status = IncidentStatus.RESOLVED
        incident.resolved_by = operator_id
        incident.resolved_at = datetime.now(timezone.utc).isoformat()

        # Add audit entry
        audit_entry = IncidentAuditEntry(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            action="resolved",
            operator_id=operator_id,
            details=notes,
        )
        incident.audit_trail.append(audit_entry)

        # Update notes if provided
        if notes:
            if incident.notes:
                incident.notes = f"{incident.notes}\n\n[{datetime.now(timezone.utc).isoformat()}] Resolved: {notes}"
            else:
                incident.notes = f"[{datetime.now(timezone.utc).isoformat()}] Resolved: {notes}"

        return incident.to_dict()


# Global incident store instance
_incident_store = IncidentStore()


def get_incident_store() -> IncidentStore:
    """Get the global incident store instance."""
    return _incident_store
