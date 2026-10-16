"""Alert notification service for the Smart Factory IoT Gateway.

This module provides:
- Typed AlertEvent with severity, source, timestamp, message, recommended action,
  and acknowledgement state.
- AlertHandler protocol for pluggable notification handlers.
- AlertService that routes alerts by severity to registered handlers.
- CommandFeedback envelope for execution feedback.

Security notes:
- WebhookNotification enforces SSRF protections (HTTP(S) only, host allowlist).
- No secrets, tokens, or PII are written to logs; webhook URLs are masked.
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse
import uuid

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels, ordered by priority (critical first)."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertSource(str, Enum):
    """Alert source modules/devices."""

    CONVEYOR = "conveyor"
    ROBOT = "robot"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    SENSOR = "sensor"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class AlertStatus(str, Enum):
    """Alert acknowledgement status."""

    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass
class AlertEvent:
    """Typed alert event with all required fields.

    Attributes:
        alert_id: Unique identifier for this alert.
        severity: Alert severity (critical/warning/info).
        source: Source device/module that generated the alert.
        timestamp: ISO-formatted timestamp when the alert was generated.
        message: Human-readable alert message.
        recommended_action: Suggested action to resolve the alert.
        status: Current acknowledgement status.
        device_id: Specific device that triggered the alert (optional).
        metadata: Additional context-specific data.
    """

    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: AlertSeverity = AlertSeverity.INFO
    source: AlertSource = AlertSource.UNKNOWN
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    message: str = ""
    recommended_action: str = ""
    status: AlertStatus = AlertStatus.PENDING
    device_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "message": self.message,
            "recommended_action": self.recommended_action,
            "status": self.status.value,
            "device_id": self.device_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlertEvent:
        """Create AlertEvent from dictionary."""
        return cls(
            alert_id=data["alert_id"],
            severity=AlertSeverity(data["severity"]),
            source=AlertSource(data["source"]),
            timestamp=data["timestamp"],
            message=data["message"],
            recommended_action=data.get("recommended_action", ""),
            status=AlertStatus(data.get("status", "pending")),
            device_id=data.get("device_id"),
            metadata=data.get("metadata", {}),
        )

    def acknowledge(self) -> None:
        """Mark this alert as acknowledged."""
        self.status = AlertStatus.ACKNOWLEDGED

    def resolve(self) -> None:
        """Mark this alert as resolved."""
        self.status = AlertStatus.RESOLVED


@runtime_checkable
class AlertHandler(Protocol):
    """Protocol for alert notification handlers.

    Implement this protocol to create custom alert handlers (e.g., Webhook,
    Telegram, Email). Handlers are injected into AlertService and called
    based on alert severity.
    """

    async def handle(self, alert: AlertEvent) -> bool:
        """Handle an alert notification.

        Args:
            alert: The alert event to process.

        Returns:
            True if the handler processed the alert successfully,
            False otherwise.
        """
        ...


class AlertService:
    """Service that routes alerts to registered handlers based on severity.

    Supports:
    - Multiple handlers registered per severity level.
    - Minimum severity threshold filtering.
    - Handler injection for testing and flexibility.
    """

    def __init__(self, min_severity: AlertSeverity = AlertSeverity.INFO) -> None:
        """Initialize the alert service.

        Args:
            min_severity: Minimum severity level to process. Alerts below
                this threshold are ignored.
        """
        self._min_severity = min_severity
        self._handlers: dict[AlertSeverity, list[AlertHandler]] = {
            AlertSeverity.CRITICAL: [],
            AlertSeverity.WARNING: [],
            AlertSeverity.INFO: [],
        }
        # Track active alerts by ID for acknowledgement
        self._active_alerts: dict[str, AlertEvent] = {}

    def register_handler(
        self, handler: AlertHandler, severity: AlertSeverity | None = None
    ) -> None:
        """Register an alert handler.

        Args:
            handler: Handler to register (must implement AlertHandler protocol).
            severity: Specific severity to register for, or None to register
                for all severities.
        """
        if severity is not None:
            self._handlers[severity].append(handler)
            logger.info("Registered handler for severity: %s", severity.value)
        else:
            # Register for all severities
            for sev in AlertSeverity:
                self._handlers[sev].append(handler)
            logger.info("Registered handler for all severities")

    def _should_process(self, severity: AlertSeverity) -> bool:
        """Check if a severity should be processed based on minimum threshold."""
        # Severity priority: INFO=1, WARNING=2, CRITICAL=3
        severity_priority = {
            AlertSeverity.INFO: 1,
            AlertSeverity.WARNING: 2,
            AlertSeverity.CRITICAL: 3,
        }
        min_priority = severity_priority[self._min_severity]
        alert_priority = severity_priority[severity]
        return alert_priority >= min_priority

    async def publish(self, alert: AlertEvent) -> bool:
        """Publish an alert to registered handlers.

        Args:
            alert: The alert event to publish.

        Returns:
            True if the alert was processed (handlers called or no handlers needed),
            False if the alert was filtered by severity threshold.
        """
        # Store for acknowledgement tracking
        self._active_alerts[alert.alert_id] = alert

        # Check severity threshold
        if not self._should_process(alert.severity):
            logger.debug(
                "Alert %s ignored (severity %s below threshold %s)",
                alert.alert_id,
                alert.severity.value,
                self._min_severity.value,
            )
            return False  # Return False - alert was filtered by severity threshold

        # Get handlers for this severity only
        handlers_to_call = self._handlers[alert.severity]

        if not handlers_to_call:
            logger.debug(
                "No handlers registered for alert %s (severity: %s)",
                alert.alert_id,
                alert.severity.value,
            )
            return True  # Return True - alert was stored, just no handlers

        # Call all handlers for this severity
        results: list[bool] = []
        for handler in handlers_to_call:
            try:
                import inspect
                if inspect.iscoroutinefunction(handler.handle):
                    result = await handler.handle(alert)
                else:
                    # Sync handlers wrapped in async for consistency
                    result = await asyncio.to_thread(handler.handle, alert)
                results.append(result)
                if result:
                    logger.info(
                        "Alert %s handled by %s",
                        alert.alert_id,
                        type(handler).__name__,
                    )
            except Exception as exc:
                logger.exception(
                    "Handler %s failed to handle alert %s: %s",
                    type(handler).__name__,
                    alert.alert_id,
                    exc,
                )
                results.append(False)

        return any(results)

    async def acknowledge(self, alert_id: str) -> bool:
        """Acknowledge an alert by ID.

        Args:
            alert_id: The ID of the alert to acknowledge.

        Returns:
            True if the alert was found and acknowledged, False otherwise.
        """
        alert = self._active_alerts.get(alert_id)
        if alert is None:
            logger.warning("Attempted to acknowledge unknown alert: %s", alert_id)
            return False

        alert.acknowledge()
        logger.info("Alert %s acknowledged", alert_id)
        return True

    async def resolve(self, alert_id: str) -> bool:
        """Resolve an alert by ID.

        Args:
            alert_id: The ID of the alert to resolve.

        Returns:
            True if the alert was found and resolved, False otherwise.
        """
        alert = self._active_alerts.get(alert_id)
        if alert is None:
            logger.warning("Attempted to resolve unknown alert: %s", alert_id)
            return False

        alert.resolve()
        # Keep in dict for history, or remove if cleanup desired
        logger.info("Alert %s resolved", alert_id)
        return True

    def get_active_alerts(self) -> list[AlertEvent]:
        """Get all active (non-resolved) alerts."""
        return [
            alert
            for alert in self._active_alerts.values()
            if alert.status != AlertStatus.RESOLVED
        ]

    def get_alert(self, alert_id: str) -> AlertEvent | None:
        """Get an alert by ID."""
        return self._active_alerts.get(alert_id)


# --- Command Feedback ---

class CommandStatus(str, Enum):
    """Status of a command execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class CommandFeedback:
    """Typed envelope for command execution feedback.

    This is used to provide real-time feedback to clients about command
    execution status via WebSocket or API endpoints.
    """

    command_id: str
    device_id: str
    status: CommandStatus
    result: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "command_id": self.command_id,
            "device_id": self.device_id,
            "status": self.status.value,
            "result": self.result,
            "timestamp": self.timestamp,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommandFeedback:
        """Create CommandFeedback from dictionary."""
        return cls(
            command_id=data["command_id"],
            device_id=data["device_id"],
            status=CommandStatus(data["status"]),
            result=data.get("result", {}),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            error_message=data.get("error_message"),
        )


# --- Concrete Handlers ---


class WebhookNotification:
    """Alert handler that POSTs alerts to a configured webhook URL.

    Security (SSRF protections):
        - Rejects non-HTTP(S) URL schemes.
        - Validates host against SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS allowlist
          (comma-separated, optional). If set, only listed hosts are permitted.
        - Applies a configurable timeout (default 5 s); no retry by default.

    Args:
        url: The webhook endpoint URL (must be https:// or http://).
        timeout: Request timeout in seconds (default: 5.0).
        enabled: Whether the handler is active (default: True).
        allowed_hosts: Optional explicit host allowlist (overrides env var).
    """

    def __init__(
        self,
        url: str,
        timeout: float = 5.0,
        enabled: bool = True,
        allowed_hosts: list[str] | None = None,
    ) -> None:
        """Initialize the webhook handler.

        Args:
            url: The webhook URL to POST alerts to.
            timeout: Request timeout in seconds (default 5.0).
            enabled: Whether to actually send notifications.
            allowed_hosts: Optional host allowlist; defaults to env var
                SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS.
        """
        self._url = url
        self._timeout = timeout
        self._enabled = enabled
        self._allowed_hosts = allowed_hosts

    # ------------------------------------------------------------------
    # SSRF helpers
    # ------------------------------------------------------------------

    def _get_allowed_hosts(self) -> list[str]:
        """Return host allowlist from instance, env var, or empty."""
        if self._allowed_hosts is not None:
            return self._allowed_hosts
        raw = os.environ.get("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "")
        return [h.strip() for h in raw.split(",") if h.strip()]

    def _validate_url(self, url: str) -> bool:
        """Return True if the URL passes SSRF checks, False otherwise.

        Security invariants
        -------------------
        - FAIL-CLOSED: when SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS is unset/empty,
          no host is permitted, all webhooks are rejected.
        - Hostname normalised via parsed.hostname (strips userinfo and port).
        - Comparison is case-insensitive.
        - Raw URLs are never logged in error branches.
        """
        try:
            parsed = urlparse(url)
        except Exception:
            logger.warning("WebhookNotification: failed to parse webhook URL")
            return False

        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            logger.warning(
                "WebhookNotification: rejected non-HTTP(S) scheme %r",
                scheme,
            )
            return False

        hostname = parsed.hostname
        if not hostname:
            logger.warning("WebhookNotification: URL has no host")
            return False

        allowed = self._get_allowed_hosts()
        # FAIL-CLOSED: empty allowlist means "not configured" → reject everything.
        if not allowed or hostname.lower() not in {h.lower() for h in allowed}:
            logger.warning(
                "WebhookNotification: host %r not on SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS",
                hostname,
            )
            return False

        return True

    def _mask_url(self, url: str) -> str:
        """Return a masked version of the URL safe for logging (no credentials)."""
        try:
            parsed = urlparse(url)
            if not parsed.netloc and not parsed.scheme and not parsed.path:
                return "***"
            # netloc includes port if present: user:pass@host:port
            # Redact userinfo before logging.
            if parsed.username or parsed.password:
                masked = parsed._replace(netloc=f"***:***@{parsed.hostname or ''}"
                    + (f":{parsed.port}" if parsed.port else ""))
                return masked.geturl()
            return url
        except Exception:
            return "***"

    # ------------------------------------------------------------------
    # AlertHandler interface
    # ------------------------------------------------------------------

    async def handle(self, alert: AlertEvent) -> bool:
        """Send alert notification via webhook POST.

        Args:
            alert: The alert event to send.

        Returns:
            True if the POST was successful, False otherwise.
        """
        if not self._enabled:
            logger.debug("WebhookNotification: disabled, skipping")
            return True

        if not self._validate_url(self._url):
            logger.warning(
                "WebhookNotification: rejected unsafe URL, alert %s not sent",
                alert.alert_id,
            )
            return False

        import aiohttp

        payload = alert.to_dict()
        payload["handler"] = "webhook"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                    allow_redirects=False,  # disable — default True allows SSRF via redirect
                ) as response:
                    if response.status < 400:
                        logger.info(
                            "WebhookNotification: sent alert %s",
                            alert.alert_id,
                        )
                        return True
                    else:
                        logger.warning(
                            "WebhookNotification: webhook returned %s for alert %s",
                            response.status,
                            alert.alert_id,
                        )
                        return False
        except Exception as exc:
            logger.exception(
                "WebhookNotification: failed to send alert %s to %s: %s",
                alert.alert_id,
                self._mask_url(self._url),
                exc,
            )
            return False

    @property
    def url(self) -> str:
        """Get the configured webhook URL."""
        return self._url

    @property
    def enabled(self) -> bool:
        """Check if the handler is enabled."""
        return self._enabled

    def disable(self) -> None:
        """Disable this handler."""
        self._enabled = False

    def enable(self) -> None:
        """Enable this handler."""
        self._enabled = True


class LoggingHandler:
    """Simple alert handler that logs alerts (useful for development)."""

    def __init__(self, min_severity: AlertSeverity = AlertSeverity.INFO) -> None:
        """Initialize the logging handler.

        Args:
            min_severity: Minimum severity to log.
        """
        self._min_severity = min_severity

    async def handle(self, alert: AlertEvent) -> bool:
        """Log the alert at appropriate level based on severity.

        Args:
            alert: The alert event to log.

        Returns:
            Always returns True (logging is always successful).
        """
        severity_order = [AlertSeverity.INFO, AlertSeverity.WARNING, AlertSeverity.CRITICAL]
        if severity_order.index(alert.severity) < severity_order.index(self._min_severity):
            return True

        log_method = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.CRITICAL: logger.critical,
        }[alert.severity]

        log_method(
            "ALERT [%s] %s | Source: %s | Device: %s | Message: %s | Action: %s",
            alert.severity.value.upper(),
            alert.alert_id,
            alert.source.value,
            alert.device_id or "N/A",
            alert.message,
            alert.recommended_action,
        )
        return True
