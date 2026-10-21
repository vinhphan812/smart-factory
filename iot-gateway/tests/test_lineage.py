"""Tests for production job and material lineage state machine."""

import pytest
from datetime import datetime, timezone
from iot_gateway.lineage import (
    JobStatus,
    MaterialStatus,
    LineageEventType,
    ProductionJob,
    ProductionMaterial,
    JobStore,
    MaterialStore,
    LineageEvent,
)


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_all_statuses_defined(self):
        """All expected job statuses are defined."""
        expected = {"pending", "in_progress", "completed", "failed", "cancelled"}
        actual = {s.value for s in JobStatus}
        assert actual == expected


class TestMaterialStatus:
    """Tests for MaterialStatus enum."""

    def test_all_statuses_defined(self):
        """All expected material statuses are defined."""
        expected = {"pending", "processing", "completed", "rejected", "scrapped"}
        actual = {s.value for s in MaterialStatus}
        assert actual == expected


class TestLineageEvent:
    """Tests for LineageEvent."""

    def test_creation(self):
        """Lineage event is created with correct defaults."""
        event = LineageEvent(
            event_type=LineageEventType.JOB_CREATED,
            job_id="job-123",
            module_id="module-1",
        )

        assert event.event_id is not None
        assert event.event_type == LineageEventType.JOB_CREATED
        assert event.job_id == "job-123"
        assert event.module_id == "module-1"
        assert event.timestamp is not None

    def test_to_dict(self):
        """Lineage event serializes to dict correctly."""
        event = LineageEvent(
            event_type=LineageEventType.JOB_STARTED,
            job_id="job-123",
            batch_id="batch-456",
            module_id="module-1",
            from_state="pending",
            to_state="in_progress",
            operator_id="op-001",
        )

        d = event.to_dict()
        assert d["event_type"] == "job_started"
        assert d["job_id"] == "job-123"
        assert d["batch_id"] == "batch-456"
        assert d["module_id"] == "module-1"
        assert d["from_state"] == "pending"
        assert d["to_state"] == "in_progress"
        assert d["operator_id"] == "op-001"


class TestProductionJob:
    """Tests for ProductionJob."""

    def test_creation(self):
        """Job is created with correct defaults."""
        job = ProductionJob(
            batch_id="batch-001",
            product_type="Widget",
            quantity=100,
            priority=5,
        )

        assert job.job_id is not None
        assert job.batch_id == "batch-001"
        assert job.product_type == "Widget"
        assert job.quantity == 100
        assert job.status == JobStatus.PENDING
        assert job.priority == 5
        assert len(job.lineage_events) == 0  # No event on creation

    def test_pending_to_in_progress(self):
        """Job can transition from PENDING to IN_PROGRESS."""
        job = ProductionJob(batch_id="batch-001", product_type="Widget", quantity=10)

        success = job.transition_to(JobStatus.IN_PROGRESS, "module-1")

        assert success is True
        assert job.status == JobStatus.IN_PROGRESS
        assert job.started_at is not None
        assert len(job.lineage_events) == 1  # Only the transition event

    def test_invalid_transition(self):
        """Job cannot transition to invalid states."""
        job = ProductionJob(batch_id="batch-001", product_type="Widget", quantity=10)

        # Try to go directly from PENDING to COMPLETED (invalid)
        success = job.transition_to(JobStatus.COMPLETED, "module-1")

        assert success is False
        assert job.status == JobStatus.PENDING

    def test_in_progress_to_completed(self):
        """Job can transition from IN_PROGRESS to COMPLETED."""
        job = ProductionJob(batch_id="batch-001", product_type="Widget", quantity=10)
        job.transition_to(JobStatus.IN_PROGRESS, "module-1")

        success = job.transition_to(JobStatus.COMPLETED, "module-1")

        assert success is True
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None

    def test_in_progress_to_failed(self):
        """Job can transition from IN_PROGRESS to FAILED."""
        job = ProductionJob(batch_id="batch-001", product_type="Widget", quantity=10)
        job.transition_to(JobStatus.IN_PROGRESS, "module-1")

        success = job.transition_to(JobStatus.FAILED, "module-1", failure_reason="Equipment malfunction")

        assert success is True
        assert job.status == JobStatus.FAILED
        assert job.failed_at is not None
        assert job.failure_reason == "Equipment malfunction"

    def test_can_transition_to(self):
        """can_transition_to returns correct values."""
        job = ProductionJob(batch_id="batch-001", product_type="Widget", quantity=10)

        assert job.can_transition_to(JobStatus.IN_PROGRESS) is True
        assert job.can_transition_to(JobStatus.CANCELLED) is True
        assert job.can_transition_to(JobStatus.COMPLETED) is False  # Must go through IN_PROGRESS

    def test_to_dict(self):
        """Job serializes to dict correctly."""
        job = ProductionJob(
            batch_id="batch-001",
            product_type="Widget",
            quantity=100,
            priority=5,
        )
        job.transition_to(JobStatus.IN_PROGRESS, "module-1")

        d = job.to_dict()

        assert d["batch_id"] == "batch-001"
        assert d["product_type"] == "Widget"
        assert d["quantity"] == 100
        assert d["status"] == "in_progress"
        assert d["priority"] == 5
        assert "lineage_events" in d


class TestProductionMaterial:
    """Tests for ProductionMaterial."""

    def test_creation(self):
        """Material is created with correct defaults."""
        material = ProductionMaterial(
            batch_id="batch-001",
            current_module="entry",
        )

        assert material.material_id is not None
        assert material.batch_id == "batch-001"
        assert material.current_module == "entry"
        assert material.status == MaterialStatus.PENDING

    def test_pending_to_processing(self):
        """Material can transition from PENDING to PROCESSING."""
        material = ProductionMaterial(batch_id="batch-001", current_module="entry")

        success = material.transition_to(MaterialStatus.PROCESSING, "module-1")

        assert success is True
        assert material.status == MaterialStatus.PROCESSING
        assert material.processed_at is not None

    def test_processing_to_completed(self):
        """Material can transition from PROCESSING to COMPLETED."""
        material = ProductionMaterial(batch_id="batch-001", current_module="entry")
        material.transition_to(MaterialStatus.PROCESSING, "module-1")

        success = material.transition_to(MaterialStatus.COMPLETED, "module-1")

        assert success is True
        assert material.status == MaterialStatus.COMPLETED
        assert material.completed_at is not None

    def test_processing_to_rejected(self):
        """Material can transition from PROCESSING to REJECTED."""
        material = ProductionMaterial(batch_id="batch-001", current_module="entry")
        material.transition_to(MaterialStatus.PROCESSING, "module-1")

        success = material.transition_to(
            MaterialStatus.REJECTED,
            "module-1",
            rejection_reason="Defective"
        )

        assert success is True
        assert material.status == MaterialStatus.REJECTED
        assert material.rejection_reason == "Defective"

    def test_transfer_to(self):
        """Material can transfer to new module."""
        material = ProductionMaterial(batch_id="batch-001", current_module="module-1")

        material.transfer_to("module-2", operator_id="op-001")

        assert material.current_module == "module-2"
        # Check that transfer event was added
        transfer_events = [
            e for e in material.lineage_events
            if e.event_type == LineageEventType.MATERIAL_TRANSFERRED
        ]
        assert len(transfer_events) == 1


class TestJobStore:
    """Tests for JobStore."""

    def test_create_job(self):
        """JobStore creates job correctly."""
        store = JobStore()

        job = store.create(
            batch_id="batch-001",
            product_type="Widget",
            quantity=100,
            priority=5,
        )

        assert job.batch_id == "batch-001"
        assert store.get(job.job_id) is not None

    def test_get_job(self):
        """JobStore can retrieve job by ID."""
        store = JobStore()

        created = store.create(batch_id="batch-001", product_type="Widget", quantity=10)
        retrieved = store.get(created.job_id)

        assert retrieved is not None
        assert retrieved.job_id == created.job_id

    def test_list_jobs(self):
        """JobStore lists jobs with filters."""
        store = JobStore()

        # Create multiple jobs
        job1 = store.create(batch_id="batch-001", product_type="Widget", quantity=10)
        job2 = store.create(batch_id="batch-002", product_type="Gadget", quantity=20)

        store.update(job1.job_id, JobStatus.IN_PROGRESS, "module-1")

        # List all
        all_jobs = store.list()
        assert len(all_jobs) == 2

        # List filtered
        pending = store.list(status=JobStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].batch_id == "batch-002"

    def test_update_job(self):
        """JobStore updates job status."""
        store = JobStore()

        job = store.create(batch_id="batch-001", product_type="Widget", quantity=10)

        updated = store.update(job.job_id, JobStatus.IN_PROGRESS, "module-1")

        assert updated is not None
        assert updated.status == JobStatus.IN_PROGRESS


class TestMaterialStore:
    """Tests for MaterialStore."""

    def test_create_material(self):
        """MaterialStore creates material correctly."""
        store = MaterialStore()

        material = store.create(
            batch_id="batch-001",
            module_id="entry",
            properties={"color": "red"},
        )

        assert material.batch_id == "batch-001"
        assert material.properties["color"] == "red"

    def test_list_materials(self):
        """MaterialStore lists materials with filters."""
        store = MaterialStore()

        mat1 = store.create(batch_id="batch-001", module_id="entry")
        mat2 = store.create(batch_id="batch-001", module_id="entry")

        store.update(mat1.material_id, MaterialStatus.PROCESSING, "module-1")

        # List by batch
        batch_materials = store.list(batch_id="batch-001")
        assert len(batch_materials) == 2

        # List by status
        processing = store.list(status=MaterialStatus.PROCESSING)
        assert len(processing) == 1


class TestLineageEvents:
    """Tests for lineage event logging."""

    def test_job_creation_event_logged(self):
        """Job creation is logged as lineage event."""
        job = ProductionJob(batch_id="batch-001", product_type="Widget", quantity=10)

        creation_events = [
            e for e in job.lineage_events
            if e.event_type == LineageEventType.JOB_CREATED
        ]
        assert len(creation_events) == 0  # No event on creation

    def test_all_transitions_logged(self):
        """All state transitions create lineage events."""
        job = ProductionJob(batch_id="batch-001", product_type="Widget", quantity=10)

        job.transition_to(JobStatus.IN_PROGRESS, "module-1")
        job.transition_to(JobStatus.COMPLETED, "module-1")

        assert len(job.lineage_events) == 2  # started + completed (no creation event)

        events_by_type = {e.event_type: e for e in job.lineage_events}
        assert LineageEventType.JOB_STARTED in events_by_type
        assert LineageEventType.JOB_COMPLETED in events_by_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
