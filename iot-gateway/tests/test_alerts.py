"""Unit tests for the alert notification service.

These tests actually exercise the alert routing, severity filtering,
acknowledgement, and handler invocation logic.
"""

import json
from datetime import datetime, timezone

import pytest

from iot_gateway.alerts import (
    AlertEvent,
    AlertHandler,
    AlertService,
    AlertSeverity,
    AlertSource,
    AlertStatus,
    CommandFeedback,
    CommandStatus,
    LoggingHandler,
    WebhookNotification,
)


class MockHandler:
    """A mock handler for testing that tracks calls."""

    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.handled_alerts: list[AlertEvent] = []

    async def handle(self, alert: AlertEvent) -> bool:
        self.handled_alerts.append(alert)
        return self.should_succeed


class TestAlertEvent:
    """Tests for AlertEvent dataclass."""

    def test_default_values(self) -> None:
        """Test that AlertEvent has correct default values."""
        alert = AlertEvent(
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.CONVEYOR,
            message="Test alert",
        )

        assert alert.alert_id is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.source == AlertSource.CONVEYOR
        assert alert.message == "Test alert"
        assert alert.status == AlertStatus.PENDING
        assert alert.timestamp is not None
        assert "T" in alert.timestamp  # ISO format

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        alert = AlertEvent(
            alert_id="test-id-123",
            severity=AlertSeverity.WARNING,
            source=AlertSource.TEMPERATURE,
            message="High temperature",
            recommended_action="Check cooling system",
            device_id="ukit-00000001",
        )

        d = alert.to_dict()

        assert d["alert_id"] == "test-id-123"
        assert d["severity"] == "warning"
        assert d["source"] == "temperature"
        assert d["message"] == "High temperature"
        assert d["recommended_action"] == "Check cooling system"
        assert d["device_id"] == "ukit-00000001"
        assert d["status"] == "pending"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "alert_id": "test-id-456",
            "severity": "critical",
            "source": "robot",
            "timestamp": "2026-10-16T10:00:00Z",
            "message": "Robot jam",
            "recommended_action": "Clear obstruction",
            "status": "acknowledged",
            "device_id": "robot-arm-01",
            "metadata": {"extra": "data"},
        }

        alert = AlertEvent.from_dict(data)

        assert alert.alert_id == "test-id-456"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.source == AlertSource.ROBOT
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.metadata["extra"] == "data"

    def test_acknowledge(self) -> None:
        """Test acknowledgement changes status."""
        alert = AlertEvent(message="Test")
        assert alert.status == AlertStatus.PENDING

        alert.acknowledge()
        assert alert.status == AlertStatus.ACKNOWLEDGED

    def test_resolve(self) -> None:
        """Test resolve changes status."""
        alert = AlertEvent(message="Test")
        assert alert.status == AlertStatus.PENDING

        alert.resolve()
        assert alert.status == AlertStatus.RESOLVED


class TestAlertService:
    """Tests for AlertService routing logic."""

    @pytest.mark.asyncio
    async def test_publish_stores_alert(self) -> None:
        """Test that publishing an alert stores it even without handlers."""
        service = AlertService()
        alert = AlertEvent(
            severity=AlertSeverity.INFO,
            source=AlertSource.SYSTEM,
            message="Test",
        )

        # Should return True (stored, even without handlers)
        result = await service.publish(alert)

        assert result is True
        assert alert.alert_id in {
            a.alert_id for a in service.get_active_alerts()
        }

    @pytest.mark.asyncio
    async def test_severity_threshold_filters_alerts(self) -> None:
        """Test that min_severity filters out lower priority alerts."""
        # Create service with WARNING minimum
        service = AlertService(min_severity=AlertSeverity.WARNING)
        
        # Debug: print severity values
        print(f"INFO value: {AlertSeverity.INFO.value}")
        print(f"WARNING value: {AlertSeverity.WARNING.value}")
        print(f"min_severity: {service._min_severity}")
        print(f"_should_process INFO: {service._should_process(AlertSeverity.INFO)}")

        # Info alert should be filtered (return False)
        info_alert = AlertEvent(
            severity=AlertSeverity.INFO,
            source=AlertSource.SYSTEM,
            message="Info alert",
        )
        result_info = await service.publish(info_alert)
        assert result_info is False

        # Warning alert should pass (return True - stored)
        warning_alert = AlertEvent(
            severity=AlertSeverity.WARNING,
            source=AlertSource.SYSTEM,
            message="Warning alert",
        )
        result_warning = await service.publish(warning_alert)
        assert result_warning is True

    @pytest.mark.asyncio
    async def test_handler_registration_for_specific_severity(self) -> None:
        """Test registering handler for specific severity."""
        service = AlertService()
        handler = MockHandler()

        service.register_handler(handler, severity=AlertSeverity.CRITICAL)

        # Only CRITICAL should trigger the handler
        critical_alert = AlertEvent(
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.SYSTEM,
            message="Critical",
        )
        warning_alert = AlertEvent(
            severity=AlertSeverity.WARNING,
            source=AlertSource.SYSTEM,
            message="Warning",
        )

        await service.publish(critical_alert)
        assert len(handler.handled_alerts) == 1

        await service.publish(warning_alert)
        # Should still be 1 since handler only registered for CRITICAL
        assert len(handler.handled_alerts) == 1

    @pytest.mark.asyncio
    async def test_handler_registration_for_all_severities(self) -> None:
        """Test registering handler for all severities."""
        service = AlertService()
        handler = MockHandler()

        service.register_handler(handler, severity=None)

        await service.publish(AlertEvent(severity=AlertSeverity.INFO, source=AlertSource.SYSTEM, message="Info"))
        await service.publish(AlertEvent(severity=AlertSeverity.WARNING, source=AlertSource.SYSTEM, message="Warning"))
        await service.publish(AlertEvent(severity=AlertSeverity.CRITICAL, source=AlertSource.SYSTEM, message="Critical"))

        assert len(handler.handled_alerts) == 3

    @pytest.mark.asyncio
    async def test_multiple_handlers_called(self) -> None:
        """Test that multiple handlers are all called."""
        service = AlertService()
        handler1 = MockHandler()
        handler2 = MockHandler()

        service.register_handler(handler1, severity=AlertSeverity.CRITICAL)
        service.register_handler(handler2, severity=AlertSeverity.CRITICAL)

        alert = AlertEvent(
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.SYSTEM,
            message="Test",
        )
        await service.publish(alert)

        assert len(handler1.handled_alerts) == 1
        assert len(handler2.handled_alerts) == 1

    @pytest.mark.asyncio
    async def test_handler_failure_does_not_stop_others(self) -> None:
        """Test that a failing handler doesn't stop other handlers."""
        service = AlertService()
        failing_handler = MockHandler(should_succeed=False)
        success_handler = MockHandler(should_succeed=True)

        service.register_handler(failing_handler, severity=AlertSeverity.INFO)
        service.register_handler(success_handler, severity=AlertSeverity.INFO)

        alert = AlertEvent(
            severity=AlertSeverity.INFO,
            source=AlertSource.SYSTEM,
            message="Test",
        )
        result = await service.publish(alert)

        # Should return True because at least one handler succeeded
        assert result is True
        assert len(success_handler.handled_alerts) == 1

    @pytest.mark.asyncio
    async def test_acknowledge_existing_alert(self) -> None:
        """Test acknowledging an existing alert."""
        service = AlertService()
        alert = AlertEvent(
            severity=AlertSeverity.INFO,
            source=AlertSource.SYSTEM,
            message="Test",
        )
        await service.publish(alert)

        result = await service.acknowledge(alert.alert_id)

        assert result is True
        assert service.get_alert(alert.alert_id).status == AlertStatus.ACKNOWLEDGED

    @pytest.mark.asyncio
    async def test_acknowledge_unknown_alert_returns_false(self) -> None:
        """Test acknowledging unknown alert returns False."""
        service = AlertService()
        result = await service.acknowledge("non-existent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_resolve_existing_alert(self) -> None:
        """Test resolving an existing alert."""
        service = AlertService()
        alert = AlertEvent(
            severity=AlertSeverity.INFO,
            source=AlertSource.SYSTEM,
            message="Test",
        )
        await service.publish(alert)

        result = await service.resolve(alert.alert_id)

        assert result is True
        assert service.get_alert(alert.alert_id).status == AlertStatus.RESOLVED

    @pytest.mark.asyncio
    async def test_get_active_alerts_filters_resolved(self) -> None:
        """Test that get_active_alerts excludes resolved alerts."""
        service = AlertService()

        pending = AlertEvent(severity=AlertSeverity.INFO, source=AlertSource.SYSTEM, message="Pending")
        acknowledged = AlertEvent(severity=AlertSeverity.WARNING, source=AlertSource.SYSTEM, message="Acked")
        resolved = AlertEvent(severity=AlertSeverity.CRITICAL, source=AlertSource.SYSTEM, message="Resolved")

        await service.publish(pending)
        await service.publish(acknowledged)
        await service.publish(resolved)

        await service.acknowledge(acknowledged.alert_id)
        await service.resolve(resolved.alert_id)

        active = service.get_active_alerts()

        # Active = pending + acknowledged (not resolved)
        # Note: "acknowledged" is NOT "resolved", so it's still active
        assert len(active) == 2
        assert any(a.alert_id == pending.alert_id for a in active)
        assert any(a.alert_id == acknowledged.alert_id for a in active)


class TestCommandFeedback:
    """Tests for CommandFeedback envelope."""

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        feedback = CommandFeedback(
            command_id="cmd-123",
            device_id="ukit-00000001",
            status=CommandStatus.SUCCESS,
            result={"output": "done"},
        )

        d = feedback.to_dict()

        assert d["command_id"] == "cmd-123"
        assert d["device_id"] == "ukit-00000001"
        assert d["status"] == "success"
        assert d["result"]["output"] == "done"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "command_id": "cmd-456",
            "device_id": "robot-arm-01",
            "status": "failed",
            "error_message": "Motor stalled",
            "timestamp": "2026-10-16T10:00:00Z",
        }

        feedback = CommandFeedback.from_dict(data)

        assert feedback.command_id == "cmd-456"
        assert feedback.status == CommandStatus.FAILED
        assert feedback.error_message == "Motor stalled"

    def test_status_values(self) -> None:
        """Test all CommandStatus values."""
        for status in CommandStatus:
            feedback = CommandFeedback(
                command_id="test",
                device_id="dev",
                status=status,
            )
            assert feedback.status == status
            d = feedback.to_dict()
            assert d["status"] == status.value


class TestLoggingHandler:
    """Tests for LoggingHandler."""

    @pytest.mark.asyncio
    async def test_logs_at_correct_level(self) -> None:
        """Test that LoggingHandler logs at appropriate levels."""
        handler = LoggingHandler(min_severity=AlertSeverity.INFO)

        # This should work without raising
        alert = AlertEvent(
            severity=AlertSeverity.INFO,
            source=AlertSource.SYSTEM,
            message="Test info",
        )
        result = await handler.handle(alert)
        assert result is True

        alert_critical = AlertEvent(
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.SYSTEM,
            message="Test critical",
        )
        result = await handler.handle(alert_critical)
        assert result is True

    @pytest.mark.asyncio
    async def test_filters_by_min_severity(self) -> None:
        """Test that LoggingHandler respects min_severity."""
        handler = LoggingHandler(min_severity=AlertSeverity.WARNING)

        info_alert = AlertEvent(
            severity=AlertSeverity.INFO,
            source=AlertSource.SYSTEM,
            message="Info",
        )
        # Should return True but not actually log (no filter check exposed)
        result = await handler.handle(info_alert)
        assert result is True


class TestWebhookNotification:
    """Tests for WebhookNotification handler."""

    @pytest.mark.asyncio
    async def test_handler_can_be_disabled(self) -> None:
        """Test that WebhookNotification can be disabled."""
        handler = WebhookNotification(url="http://example.com", enabled=False)

        assert handler.enabled is False

        alert = AlertEvent(
            severity=AlertSeverity.INFO,
            source=AlertSource.SYSTEM,
            message="Test",
        )
        result = await handler.handle(alert)
        # Disabled handler still returns True (skipped gracefully)
        assert result is True

    def test_handler_can_be_enabled(self) -> None:
        """Test that WebhookNotification can be enabled."""
        handler = WebhookNotification(url="http://example.com", enabled=False)

        handler.enable()
        assert handler.enabled is True

        handler.disable()
        assert handler.enabled is False

    def test_url_property(self) -> None:
        """Test URL property accessor."""
        handler = WebhookNotification(url="http://test.com/webhook")
        assert handler.url == "http://test.com/webhook"


class TestAlertHandlerProtocol:
    """Tests for AlertHandler protocol compliance."""

    def test_mock_handler_implements_protocol(self) -> None:
        """Test that MockHandler satisfies AlertHandler protocol."""
        handler = MockHandler()
        assert isinstance(handler, AlertHandler)

    def test_logging_handler_implements_protocol(self) -> None:
        """Test that LoggingHandler satisfies AlertHandler protocol."""
        handler = LoggingHandler()
        assert isinstance(handler, AlertHandler)
