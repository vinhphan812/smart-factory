"""Production job and material lineage state machine for the gateway.

This module implements the job and material tracking state machine
across the nine factory modules. Used by the gateway API.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


class JobStatus(str, Enum):
    """Job states in the production pipeline."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MaterialStatus(str, Enum):
    """Material states."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    SCRAPPED = "scrapped"


class LineageEventType(str, Enum):
    """Lineage event types for tracking state changes."""
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"
    MATERIAL_RECEIVED = "material_received"
    MATERIAL_PROCESSING = "material_processing"
    MATERIAL_COMPLETED = "material_completed"
    MATERIAL_REJECTED = "material_rejected"
    MATERIAL_SCRAPPED = "material_scraped"
    MATERIAL_TRANSFERRED = "material_transferred"


# Valid job state transitions
JOB_VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {JobStatus.IN_PROGRESS, JobStatus.CANCELLED},
    JobStatus.IN_PROGRESS: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.COMPLETED: set(),  # Terminal state
    JobStatus.FAILED: {JobStatus.PENDING},  # Can retry
    JobStatus.CANCELLED: {JobStatus.PENDING},  # Can restart
}

# Valid material state transitions
MATERIAL_VALID_TRANSITIONS: dict[MaterialStatus, set[MaterialStatus]] = {
    MaterialStatus.PENDING: {MaterialStatus.PROCESSING, MaterialStatus.REJECTED},
    MaterialStatus.PROCESSING: {MaterialStatus.COMPLETED, MaterialStatus.REJECTED, MaterialStatus.SCRAPPED},
    MaterialStatus.COMPLETED: set(),  # Terminal state
    MaterialStatus.REJECTED: {MaterialStatus.PROCESSING},  # Can retry
    MaterialStatus.SCRAPPED: set(),  # Terminal state
}


@dataclass
class LineageEvent:
    """Lineage event for tracking state changes with timestamp and module."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: LineageEventType = LineageEventType.JOB_CREATED
    job_id: Optional[str] = None
    material_id: Optional[str] = None
    batch_id: Optional[str] = None
    module_id: str = ""
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operator_id: Optional[str] = None
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "job_id": self.job_id,
            "material_id": self.material_id,
            "batch_id": self.batch_id,
            "module_id": self.module_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "timestamp": self.timestamp,
            "operator_id": self.operator_id,
            "details": self.details,
        }


@dataclass
class ProductionJob:
    """Production job representing a batch of work to be processed."""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    batch_id: str = ""
    product_type: str = ""
    quantity: int = 0
    status: JobStatus = JobStatus.PENDING
    priority: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    failed_at: Optional[str] = None
    failure_reason: Optional[str] = None
    current_module: Optional[str] = None
    lineage_events: list[LineageEvent] = field(default_factory=list)

    def add_lineage_event(
        self,
        event_type: LineageEventType,
        module_id: str,
        from_state: Optional[JobStatus] = None,
        to_state: Optional[JobStatus] = None,
        operator_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> LineageEvent:
        """Add a lineage event to this job."""
        event = LineageEvent(
            event_type=event_type,
            job_id=self.job_id,
            batch_id=self.batch_id,
            module_id=module_id,
            from_state=from_state.value if from_state else None,
            to_state=to_state.value if to_state else None,
            operator_id=operator_id,
            details=details or {},
        )
        self.lineage_events.append(event)
        return event

    def can_transition_to(self, new_status: JobStatus) -> bool:
        """Check if transition to new status is valid."""
        return new_status in JOB_VALID_TRANSITIONS.get(self.status, set())

    def transition_to(
        self,
        new_status: JobStatus,
        module_id: str,
        operator_id: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> bool:
        """Transition job to new status."""
        if not self.can_transition_to(new_status):
            return False

        old_status = self.status
        self.status = new_status

        # Update timestamps
        now = datetime.now(timezone.utc).isoformat()
        if new_status == JobStatus.IN_PROGRESS:
            self.started_at = now
        elif new_status == JobStatus.COMPLETED:
            self.completed_at = now
        elif new_status == JobStatus.FAILED:
            self.failed_at = now
            self.failure_reason = failure_reason

        # Add lineage event
        event_type_map = {
            JobStatus.IN_PROGRESS: LineageEventType.JOB_STARTED,
            JobStatus.COMPLETED: LineageEventType.JOB_COMPLETED,
            JobStatus.FAILED: LineageEventType.JOB_FAILED,
            JobStatus.CANCELLED: LineageEventType.JOB_CANCELLED,
        }

        event_type = event_type_map.get(new_status, LineageEventType.JOB_CREATED)
        self.add_lineage_event(
            event_type=event_type,
            module_id=module_id,
            from_state=old_status,
            to_state=new_status,
            operator_id=operator_id,
            details={"failure_reason": failure_reason} if failure_reason else {},
        )

        return True

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "batch_id": self.batch_id,
            "product_type": self.product_type,
            "quantity": self.quantity,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "failed_at": self.failed_at,
            "failure_reason": self.failure_reason,
            "current_module": self.current_module,
            "lineage_events": [e.to_dict() for e in self.lineage_events],
        }


@dataclass
class ProductionMaterial:
    """Material in production pipeline."""
    material_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    batch_id: str = ""
    current_module: str = ""
    status: MaterialStatus = MaterialStatus.PENDING
    received_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_at: Optional[str] = None
    completed_at: Optional[str] = None
    rejected_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    properties: dict = field(default_factory=dict)
    lineage_events: list[LineageEvent] = field(default_factory=list)

    def add_lineage_event(
        self,
        event_type: LineageEventType,
        module_id: str,
        from_state: Optional[MaterialStatus] = None,
        to_state: Optional[MaterialStatus] = None,
        operator_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> LineageEvent:
        """Add a lineage event to this material."""
        event = LineageEvent(
            event_type=event_type,
            material_id=self.material_id,
            batch_id=self.batch_id,
            module_id=module_id,
            from_state=from_state.value if from_state else None,
            to_state=to_state.value if to_state else None,
            operator_id=operator_id,
            details=details or {},
        )
        self.lineage_events.append(event)
        return event

    def can_transition_to(self, new_status: MaterialStatus) -> bool:
        """Check if transition to new status is valid."""
        return new_status in MATERIAL_VALID_TRANSITIONS.get(self.status, set())

    def transition_to(
        self,
        new_status: MaterialStatus,
        module_id: str,
        operator_id: Optional[str] = None,
        rejection_reason: Optional[str] = None,
    ) -> bool:
        """Transition material to new status."""
        if not self.can_transition_to(new_status):
            return False

        old_status = self.status
        self.status = new_status
        self.current_module = module_id

        # Update timestamps
        now = datetime.now(timezone.utc).isoformat()
        if new_status == MaterialStatus.PROCESSING:
            self.processed_at = now
        elif new_status == MaterialStatus.COMPLETED:
            self.completed_at = now
        elif new_status == MaterialStatus.REJECTED:
            self.rejected_at = now
            self.rejection_reason = rejection_reason
        elif new_status == MaterialStatus.SCRAPPED:
            self.rejected_at = now

        # Add lineage event
        event_type_map = {
            MaterialStatus.PROCESSING: LineageEventType.MATERIAL_PROCESSING,
            MaterialStatus.COMPLETED: LineageEventType.MATERIAL_COMPLETED,
            MaterialStatus.REJECTED: LineageEventType.MATERIAL_REJECTED,
            MaterialStatus.SCRAPPED: LineageEventType.MATERIAL_SCRAPPED,
        }

        event_type = event_type_map.get(new_status, LineageEventType.MATERIAL_RECEIVED)
        self.add_lineage_event(
            event_type=event_type,
            module_id=module_id,
            from_state=old_status,
            to_state=new_status,
            operator_id=operator_id,
            details={"rejection_reason": rejection_reason} if rejection_reason else {},
        )

        return True

    def transfer_to(self, new_module: str, operator_id: Optional[str] = None) -> None:
        """Transfer material to a new module."""
        self.add_lineage_event(
            event_type=LineageEventType.MATERIAL_TRANSFERRED,
            module_id=new_module,
            from_state=self.status,
            to_state=self.status,
            operator_id=operator_id,
            details={"from_module": self.current_module, "to_module": new_module},
        )
        self.current_module = new_module

    def to_dict(self) -> dict:
        return {
            "material_id": self.material_id,
            "batch_id": self.batch_id,
            "current_module": self.current_module,
            "status": self.status.value,
            "received_at": self.received_at,
            "processed_at": self.processed_at,
            "completed_at": self.completed_at,
            "rejected_at": self.rejected_at,
            "rejection_reason": self.rejection_reason,
            "properties": self.properties,
            "lineage_events": [e.to_dict() for e in self.lineage_events],
        }


class JobStore:
    """In-memory store for production jobs."""

    def __init__(self):
        self._jobs: dict[str, ProductionJob] = {}

    def create(
        self,
        batch_id: str,
        product_type: str,
        quantity: int,
        priority: int = 0,
        module_id: str = "entry",
    ) -> ProductionJob:
        """Create a new production job."""
        job = ProductionJob(
            batch_id=batch_id,
            product_type=product_type,
            quantity=quantity,
            priority=priority,
        )

        # Add creation event
        job.add_lineage_event(
            event_type=LineageEventType.JOB_CREATED,
            module_id=module_id,
            from_state=None,
            to_state=JobStatus.PENDING,
        )

        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[ProductionJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def list(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> list[ProductionJob]:
        """List jobs with optional filters."""
        jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        # Sort by priority and creation time
        jobs.sort(key=lambda j: (-j.priority, j.created_at))

        return jobs[:limit]

    def update(
        self,
        job_id: str,
        new_status: JobStatus,
        module_id: str,
        operator_id: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> Optional[ProductionJob]:
        """Update job status."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        job.transition_to(new_status, module_id, operator_id, failure_reason)
        return job


class MaterialStore:
    """In-memory store for production materials."""

    def __init__(self):
        self._materials: dict[str, ProductionMaterial] = {}

    def create(
        self,
        batch_id: str,
        module_id: str,
        properties: Optional[dict] = None,
    ) -> ProductionMaterial:
        """Create a new material entry."""
        material = ProductionMaterial(
            batch_id=batch_id,
            current_module=module_id,
            properties=properties or {},
        )

        # Add received event
        material.add_lineage_event(
            event_type=LineageEventType.MATERIAL_RECEIVED,
            module_id=module_id,
            from_state=None,
            to_state=MaterialStatus.PENDING,
        )

        self._materials[material.material_id] = material
        return material

    def get(self, material_id: str) -> Optional[ProductionMaterial]:
        """Get material by ID."""
        return self._materials.get(material_id)

    def list(
        self,
        status: Optional[MaterialStatus] = None,
        batch_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[ProductionMaterial]:
        """List materials with optional filters."""
        materials = list(self._materials.values())

        if status:
            materials = [m for m in materials if m.status == status]

        if batch_id:
            materials = [m for m in materials if m.batch_id == batch_id]

        # Sort by received time
        materials.sort(key=lambda m: m.received_at)

        return materials[:limit]

    def update(
        self,
        material_id: str,
        new_status: MaterialStatus,
        module_id: str,
        operator_id: Optional[str] = None,
        rejection_reason: Optional[str] = None,
    ) -> Optional[ProductionMaterial]:
        """Update material status."""
        material = self._materials.get(material_id)
        if not material:
            return None

        material.transition_to(new_status, module_id, operator_id, rejection_reason)
        return material


# Global stores
job_store = JobStore()
material_store = MaterialStore()
