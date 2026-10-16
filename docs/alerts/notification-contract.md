# Alert Notification Contract

## Overview

This document describes the alert notification system for the Smart Factory IoT Gateway. The system provides typed alert events with configurable handlers for routing notifications based on severity.

**Note:** Physical notifications (buzzer, LED) are **NOT** in scope for this implementation. Hardware HIL is blocked per issue #98.

## Alert Taxonomy

### Severity Levels

| Level | Value | Description | Example |
|-------|-------|-------------|---------|
| `critical` | `critical` | Immediate attention required | Conveyor belt jam, temperature exceed safe threshold |
| `warning` | `warning` | Attention needed soon | Elevated temperature, slow conveyor speed |
| `info` | `info` | Informational | Status changes, routine telemetry |

### Alert Sources

| Source | Value | Description |
|--------|-------|-------------|
| Conveyor | `conveyor` | Conveyor belt system |
| Robot | `robot` | Robotic arm / robot |
| Temperature | `temperature` | Temperature sensor |
| Humidity | `humidity` | Humidity sensor |
| Sensor | `sensor` | Generic sensor |
| System | `system` | Gateway/system events |
| Unknown | `unknown` | Unclassified source |

### Alert Status

| Status | Value | Description |
|--------|-------|-------------|
| Pending | `pending` | Alert triggered, not yet acknowledged |
| Acknowledged | `acknowledged` | Alert has been acknowledged by an operator |
| Resolved | `acknowledged` | Alert condition has been resolved |

## AlertEvent Schema

```json
{
  "alert_id": "uuid-string",
  "severity": "critical|warning|info",
  "source": "conveyor|robot|temperature|humidity|sensor|system|unknown",
  "timestamp": "ISO-8601 timestamp",
  "message": "Human-readable alert message",
  "recommended_action": "Suggested action to resolve the alert",
  "status": "pending|acknowledged|resolved",
  "device_id": "device-identifier or null",
  "metadata": {
    "key": "value"
  }
}
```

### Required Fields

- `alert_id`: Unique identifier (UUID)
- `severity`: Alert severity level
- `source`: Alert source module
- `timestamp`: ISO-8601 formatted timestamp
- `message`: Human-readable message
- `status`: Current acknowledgement state

### Optional Fields

- `recommended_action`: Suggested action to resolve
- `device_id`: Specific device that triggered the alert
- `metadata`: Additional context-specific data

## Handler Contract

### AlertHandler Protocol

Handlers must implement the `AlertHandler` protocol:

```python
class AlertHandler(Protocol):
    async def handle(self, alert: AlertEvent) -> bool:
        """Handle an alert notification.

        Returns True if handled successfully, False otherwise.
        """
        ...
```

### Handler Registration

Handlers are registered with the `AlertService`:

```python
# Register for specific severity
service.register_handler(handler, severity=AlertSeverity.CRITICAL)

# Register for all severities
service.register_handler(handler, severity=None)
```

### Built-in Handlers

#### LoggingHandler

Logs alerts at appropriate levels based on severity.

```python
handler = LoggingHandler(min_severity=AlertSeverity.INFO)
```

#### WebhookNotification

POSTs alerts to a configurable webhook URL.

```python
handler = WebhookNotification(
    url="https://example.com/webhook",
    timeout=10.0,
    enabled=True,
)
```

Configuration via environment variables:

- `ALERT_WEBHOOK_URL`: Webhook URL for notifications

## Alert Routing

The `AlertService` routes alerts based on:

1. **Severity threshold**: Minimum severity level to process (configurable)
2. **Handler registration**: Handlers can be registered for specific severities or all

When an alert is published:
1. Check if severity meets minimum threshold
2. Collect all handlers registered for that severity and higher
3. Call each handler in order
4. Return `true` if at least one handler succeeds

## Command Feedback

### CommandFeedback Schema

```json
{
  "command_id": "uuid-or-command-id",
  "device_id": "device-identifier",
  "status": "pending|in_progress|success|failed|timeout",
  "result": {},
  "timestamp": "ISO-8601 timestamp",
  "error_message": "Error details if failed"
}
```

### Required Fields

- `command_id`: The command identifier (matches incoming command)
- `device_id`: Target device identifier
- `status`: Execution status

### Optional Fields

- `result`: Command result payload
- `error_message`: Error details if status is "failed"
- `timestamp`: ISO-8601 formatted timestamp

## WebSocket/API Endpoints

### Alert Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/alerts` | List active alerts |
| `GET` | `/alerts/{alert_id}` | Get specific alert |
| `POST` | `/alerts/{alert_id}/acknowledge` | Acknowledge an alert |
| `POST` | `/alerts/{alert_id}/resolve` | Resolve an alert |

### Command Feedback Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `WS` | `/ws` | WebSocket for real-time command feedback |
| `GET` | `/commands/{command_id}/feedback` | Get command feedback by ID |

## Telemetry Integration

Alerts are generated from incoming MQTT telemetry topics:

- `smart-factory/{deviceId}/telemetry` - Telemetry data
- `smart-factory/{deviceId}/command/ack` - Command acknowledgements
- `smart-factory/{deviceId}/status` - Device status changes

Example telemetry that triggers alerts:

```json
// High temperature alert
{
  "device_id": "ukit-00000000",
  "received_at_ms": 123456,
  "values": ["TEMP", "8500"],
  "pairs": {}
}

// Conveyor stopped
{
  "device_id": "ukit-00000000",
  "received_at_ms": 123456,
  "values": ["CONVEYOR", "STOPPED"],
  "pairs": {}
}
```

## Not In Scope

The following are explicitly **NOT** in scope for this implementation:

- **Physical notifications**: Buzzer, LED, or any hardware-based alerts (blocked per #98)
- **Email notifications**: Not implemented in initial release
- **SMS/Push notifications**: Not implemented in initial release
- **Alert aggregation**: Single alerts, no batching
- **Alert history persistence**: In-memory only (can be extended to SQLite)

## Testing

Unit tests are provided in `iot-gateway/tests/test_alerts.py` covering:

- Alert creation and serialization
- Severity-based routing
- Handler registration and invocation
- Acknowledgement and resolution
- Minimum severity threshold filtering
