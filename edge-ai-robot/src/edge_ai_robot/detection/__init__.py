"""Anomaly detection pipeline for edge AI.

This module provides:
- Rule-based anomaly detection on factory events
- Deterministic alarm taxonomy
- Advisory output (human operators must approve responses)

For ML-based detection, see Issue #14.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import asyncio

import structlog

logger = structlog.get_logger(__name__)


class AlarmSeverity(str, Enum):
    """Alarm severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlarmCategory(str, Enum):
    """Alarm categories for classification."""
    CONNECTIVITY = "connectivity"      # Device offline, communication failure
    SENSOR_ANOMALY = "sensor_anomaly"  # Unexpected sensor readings
    SAFETY = "safety"                  # Safety-related events
    PERFORMANCE = "performance"        # Performance degradation
    UNKNOWN = "unknown"                # Unclassified


@dataclass
class Alarm:
    """Factory alarm event."""
    alarm_id: str
    category: AlarmCategory
    severity: AlarmSeverity
    device_id: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False


class AnomalyDetector:
    """Rule-based anomaly detector.

    This is a deterministic detector for L2 simulation.
    It generates alarms based on rule matching on incoming events.

    For ML-based detection, see Issue #14.
    """

    def __init__(self):
        self._alarms: dict[str, Alarm] = {}
        self._lock = asyncio.Lock()

    async def process_event(self, event: dict[str, Any]) -> list[Alarm]:
        """Process an event and generate alarms if anomalies detected.

        Args:
            event: Canonical event from gateway

        Returns:
            List of generated alarms (may be empty)
        """
        alarms = []
        device_id = event.get("device_id", "unknown")

        # Rule 1: Device offline detection
        if event.get("event_type") == "status_offline":
            alarm = await self._create_alarm(
                category=AlarmCategory.CONNECTIVITY,
                severity=AlarmSeverity.WARNING,
                device_id=device_id,
                message=f"Device {device_id} reported offline",
                metadata={"event": event},
            )
            alarms.append(alarm)

        # Rule 2: Stale telemetry detection
        if event.get("stale", False):
            alarm = await self._create_alarm(
                category=AlarmCategory.CONNECTIVITY,
                severity=AlarmSeverity.INFO,
                device_id=device_id,
                message=f"Telemetry from {device_id} is stale",
                metadata={"event": event},
            )
            alarms.append(alarm)

        # Rule 3: Command failure detection
        if event.get("event_type") == "command_ack":
            payload = event.get("payload", {})
            if payload.get("status") == "failed":
                alarm = await self._create_alarm(
                    category=AlarmCategory.PERFORMANCE,
                    severity=AlarmSeverity.WARNING,
                    device_id=device_id,
                    message=f"Command failed on {device_id}: {payload.get('error', 'unknown')}",
                    metadata={"event": event},
                )
                alarms.append(alarm)

        # Rule 4: Out-of-order event detection
        if event.get("out_of_order", False):
            alarm = await self._create_alarm(
                category=AlarmCategory.PERFORMANCE,
                severity=AlarmSeverity.INFO,
                device_id=device_id,
                message=f"Out-of-order event from {device_id}",
                metadata={"event": event},
            )
            alarms.append(alarm)

        # Rule 5: High latency detection (when timestamp is valid)
        latency_ms = event.get("latency_ms", -1)
        if latency_ms > 0 and latency_ms > 5000:  # > 5 seconds
            alarm = await self._create_alarm(
                category=AlarmCategory.PERFORMANCE,
                severity=AlarmSeverity.WARNING,
                device_id=device_id,
                message=f"High latency from {device_id}: {latency_ms}ms",
                metadata={"event": event, "latency_ms": latency_ms},
            )
            alarms.append(alarm)

        # Log generated alarms
        for alarm in alarms:
            logger.info(
                "alarm_generated",
                alarm_id=alarm.alarm_id,
                category=alarm.category.value,
                severity=alarm.severity.value,
                device_id=alarm.device_id,
            )

        return alarms

    async def _create_alarm(
        self,
        category: AlarmCategory,
        severity: AlarmSeverity,
        device_id: str,
        message: str,
        metadata: dict[str, Any],
    ) -> Alarm:
        """Create a new alarm."""
        import uuid

        alarm = Alarm(
            alarm_id=str(uuid.uuid4()),
            category=category,
            severity=severity,
            device_id=device_id,
            message=message,
            metadata=metadata,
        )

        async with self._lock:
            self._alarms[alarm.alarm_id] = alarm

        return alarm

    async def acknowledge_alarm(self, alarm_id: str) -> bool:
        """Acknowledge an alarm.

        Returns:
            True if alarm was acknowledged, False if not found
        """
        async with self._lock:
            if alarm_id in self._alarms:
                self._alarms[alarm_id].acknowledged = True
                logger.info("alarm_acknowledged", alarm_id=alarm_id)
                return True
            return False

    async def resolve_alarm(self, alarm_id: str) -> bool:
        """Resolve an alarm.

        Returns:
            True if alarm was resolved, False if not found
        """
        async with self._lock:
            if alarm_id in self._alarms:
                self._alarms[alarm_id].resolved = True
                logger.info("alarm_resolved", alarm_id=alarm_id)
                return True
            return False

    async def get_active_alarms(
        self,
        category: Optional[AlarmCategory] = None,
        severity: Optional[AlarmSeverity] = None,
    ) -> list[Alarm]:
        """Get active (unresolved) alarms, optionally filtered."""
        async with self._lock:
            alarms = [a for a in self._alarms.values() if not a.resolved]

            if category:
                alarms = [a for a in alarms if a.category == category]

            if severity:
                alarms = [a for a in alarms if a.severity == severity]

            return alarms

    async def get_alarm(self, alarm_id: str) -> Optional[Alarm]:
        """Get alarm by ID."""
        async with self._lock:
            return self._alarms.get(alarm_id)

    async def get_all_alarms(self) -> list[Alarm]:
        """Get all alarms (including resolved)."""
        async with self._lock:
            return list(self._alarms.values())
