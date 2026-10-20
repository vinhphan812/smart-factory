"""Tests for anomaly detection."""

import pytest

from edge_ai_robot.detection import (
    Alarm,
    AlarmCategory,
    AlarmSeverity,
    AnomalyDetector,
)


class TestAnomalyDetector:
    """Test AnomalyDetector functionality."""

    @pytest.fixture
    def detector(self):
        """Create detector instance."""
        return AnomalyDetector()

    @pytest.mark.asyncio
    async def test_initial_state(self, detector):
        """Test detector starts with no alarms."""
        alarms = await detector.get_active_alarms()
        assert len(alarms) == 0

    @pytest.mark.asyncio
    async def test_device_offline_generates_alarm(self, detector):
        """Device offline event generates alarm."""
        event = {
            "device_id": "device-001",
            "event_type": "status_offline",
            "payload": {},
        }
        alarms = await detector.process_event(event)
        assert len(alarms) == 1
        assert alarms[0].category == AlarmCategory.CONNECTIVITY
        assert alarms[0].severity == AlarmSeverity.WARNING

    @pytest.mark.asyncio
    async def test_stale_telemetry_generates_alarm(self, detector):
        """Stale telemetry generates alarm."""
        event = {
            "device_id": "device-001",
            "event_type": "telemetry",
            "stale": True,
        }
        alarms = await detector.process_event(event)
        assert len(alarms) == 1
        assert alarms[0].category == AlarmCategory.CONNECTIVITY
        assert alarms[0].severity == AlarmSeverity.INFO

    @pytest.mark.asyncio
    async def test_command_failure_generates_alarm(self, detector):
        """Failed command generates alarm."""
        event = {
            "device_id": "device-001",
            "event_type": "command_ack",
            "payload": {
                "status": "failed",
                "error": "timeout",
            },
        }
        alarms = await detector.process_event(event)
        assert len(alarms) == 1
        assert alarms[0].category == AlarmCategory.PERFORMANCE
        assert alarms[0].severity == AlarmSeverity.WARNING

    @pytest.mark.asyncio
    async def test_out_of_order_generates_alarm(self, detector):
        """Out-of-order event generates alarm."""
        event = {
            "device_id": "device-001",
            "event_type": "telemetry",
            "out_of_order": True,
        }
        alarms = await detector.process_event(event)
        assert len(alarms) == 1
        assert alarms[0].category == AlarmCategory.PERFORMANCE

    @pytest.mark.asyncio
    async def test_high_latency_generates_alarm(self, detector):
        """High latency (>5s) generates alarm."""
        event = {
            "device_id": "device-001",
            "event_type": "telemetry",
            "latency_ms": 6000,  # 6 seconds
        }
        alarms = await detector.process_event(event)
        assert len(alarms) == 1
        assert alarms[0].category == AlarmCategory.PERFORMANCE
        assert alarms[0].severity == AlarmSeverity.WARNING

    @pytest.mark.asyncio
    async def test_normal_event_no_alarm(self, detector):
        """Normal event with no anomalies generates no alarm."""
        event = {
            "device_id": "device-001",
            "event_type": "telemetry",
            "payload": {"temperature": 25.0},
        }
        alarms = await detector.process_event(event)
        assert len(alarms) == 0

    @pytest.mark.asyncio
    async def test_multiple_alarms_from_one_event(self, detector):
        """One event can generate multiple alarms."""
        event = {
            "device_id": "device-001",
            "event_type": "status_offline",
            "stale": True,
            "latency_ms": 10000,
        }
        alarms = await detector.process_event(event)
        # Should have 3 alarms: offline, stale, high latency
        assert len(alarms) == 3

    @pytest.mark.asyncio
    async def test_acknowledge_alarm(self, detector):
        """Alarm can be acknowledged."""
        event = {"device_id": "device-001", "event_type": "status_offline"}
        alarms = await detector.process_event(event)
        alarm_id = alarms[0].alarm_id

        result = await detector.acknowledge_alarm(alarm_id)
        assert result is True

        alarm = await detector.get_alarm(alarm_id)
        assert alarm.acknowledged is True

    @pytest.mark.asyncio
    async def test_resolve_alarm(self, detector):
        """Alarm can be resolved."""
        event = {"device_id": "device-001", "event_type": "status_offline"}
        alarms = await detector.process_event(event)
        alarm_id = alarms[0].alarm_id

        result = await detector.resolve_alarm(alarm_id)
        assert result is True

        active_alarms = await detector.get_active_alarms()
        assert len(active_alarms) == 0

    @pytest.mark.asyncio
    async def test_filter_alarms_by_category(self, detector):
        """Alarms can be filtered by category."""
        # Generate different types of alarms
        await detector.process_event({"device_id": "dev-1", "event_type": "status_offline"})
        await detector.process_event({
            "device_id": "dev-2",
            "event_type": "command_ack",
            "payload": {"status": "failed"},
        })

        connectivity_alarms = await detector.get_active_alarms(
            category=AlarmCategory.CONNECTIVITY
        )
        assert len(connectivity_alarms) == 1

    @pytest.mark.asyncio
    async def test_filter_alarms_by_severity(self, detector):
        """Alarms can be filtered by severity."""
        await detector.process_event({"device_id": "dev-1", "event_type": "status_offline"})
        await detector.process_event({"device_id": "dev-2", "stale": True})

        critical_alarms = await detector.get_active_alarms(
            severity=AlarmSeverity.CRITICAL
        )
        warning_alarms = await detector.get_active_alarms(
            severity=AlarmSeverity.WARNING
        )
        assert len(warning_alarms) >= 1

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_alarm(self, detector):
        """Acknowledge returns False for nonexistent alarm."""
        result = await detector.acknowledge_alarm("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_all_alarms_includes_resolved(self, detector):
        """get_all_alarms includes resolved alarms."""
        event = {"device_id": "device-001", "event_type": "status_offline"}
        alarms = await detector.process_event(event)
        alarm_id = alarms[0].alarm_id

        await detector.resolve_alarm(alarm_id)

        all_alarms = await detector.get_all_alarms()
        assert len(all_alarms) == 1
        assert all_alarms[0].resolved is True
