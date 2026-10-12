# Bridge Health Monitoring

This document describes the health monitoring, heartbeat, and reconnection behavior of the ESP32 MQTT bridge.

---

## 1. Heartbeat

The bridge periodically publishes a heartbeat message to advertise its presence and liveness.

| Property       | Value                                                      |
|----------------|------------------------------------------------------------|
| Topic          | `smart-factory/bridge/{id}/heartbeat`                      |
| QoS            | 0 (best effort)                                            |
| Retain         | No                                                         |
| Interval       | `HEARTBEAT_INTERVAL_MS` (default: 30 000 ms, 30 seconds)  |

### Payload

```json
{
  "online": true,
  "uptime_s": 12345,
  "rssi_dbm": -65,
  "free_heap_bytes": 40960,
  "queue_depth": 2,
  "last_tel_s": 5
}
```

| Field           | Type    | Description                                                     |
|-----------------|---------|-----------------------------------------------------------------|
| `online`        | bool    | Always `true` in a heartbeat; `false` only in the MQTT Last Will |
| `uptime_s`      | uint32  | Seconds since boot                                               |
| `rssi_dbm`      | int     | Current Wi-Fi RSSI in dBm (negative integer)                    |
| `free_heap_bytes` | uint32 | Available heap memory in bytes                                  |
| `queue_depth`   | uint16  | Number of commands currently pending in the queue               |
| `last_tel_s`   | uint32  | Seconds since the last `TEL` frame was received from uKit       |

> **TODO**: Full heartbeat implementation is pending. Currently `publishOnlineStatus()` sends a retained status JSON to `smart-factory/{id}/status`; the dedicated heartbeat topic and payload fields are not yet wired in `MqttBridge`.

---

## 2. Telemetry Health

### Expected Cadence

The uKit reference profile emits `TEL,STATE,...` frames at a fixed interval defined by the uKit firmware. The ESP32 bridge does not control this cadence. Typical expected interval is **1-10 seconds**.

### Stale Detection

A `TEL` frame is considered **stale** when the bridge has not received any `TEL` frame within `TELEMETRY_TIMEOUT_MS` (default: **60 000 ms, 60 seconds**).

Stale state is reflected in the heartbeat payload:

| State                          | `last_tel_s` in heartbeat              |
|--------------------------------|----------------------------------------|
| Normal (< timeout)             | Seconds since last `TEL`               |
| Stale (>= timeout, < 2x)       | Value >= `TELEMETRY_TIMEOUT_MS / 1000`; bridge marks `tel_stale: true` in status |
| Disconnected (>= 2x timeout)   | Bridge may publish a `telemetry_timeout` event to `smart-factory/bridge/{id}/event` |

> **TODO**: `checkTelemetryHealth()` is a stub. Full implementation must:
> - Track `lastTelReceivedMs_` in `MqttBridge` or a new `TelemetryMonitor` class.
> - Set `telStale_` flag when `nowMs - lastTelReceivedMs_ >= TELEMETRY_TIMEOUT_MS`.
> - Publish an event when `nowMs - lastTelReceivedMs_ >= 2 * TELEMETRY_TIMEOUT_MS`.

### Recovery

When a new `TEL` frame arrives after a stale period, `telStale_` is cleared and a `telemetry_recovered` event is optionally published.

---

## 3. Reconnection Behavior

### Wi-Fi Drop

The `WifiStateMachine` handles Wi-Fi disconnections.

| Scenario                        | Behavior                                                               |
|---------------------------------|-----------------------------------------------------------------------|
| Connected → disconnected        | Transitions to `State::Waiting`, schedules retry with exponential backoff |
| Backoff schedule                | `kWifiInitialRetryMs` (5 s) → doubling → `kWifiMaxRetryMs` (60 s)   |
| Reconnect attempt timeout        | `kWifiConnectTimeoutMs` (15 s) per attempt; if exceeded, retry again |
| Wi-Fi recovery                  | State returns to `Connected`, `retryDelayMs_` resets to initial value |
| Effect on MQTT                  | `MqttBridge::tick()` disconnects MQTT client when `networkReady == false` |

Backoff is capped at `kWifiMaxRetryMs`. The Wi-Fi state machine does not hold a persistent connection; `WiFi.setAutoReconnect(false)` is set so the application controls reconnection timing.

### MQTT Drop

`MqttBridge::tick()` monitors `client_.connected()`.

| Scenario                              | Behavior                                                          |
|---------------------------------------|-------------------------------------------------------------------|
| MQTT disconnected, network up         | If `due(nowMs, reconnectAtMs_)`, calls `connectOnce(nowMs)`       |
| `connectOnce` succeeds                | Resubscribes to `commandTopic_`, publishes `online` status        |
| `connectOnce` fails                   | Sets `reconnectAtMs_ = nowMs + kMqttRetryMs`; retries at next tick |
| MQTT Last Will published              | Broker sends retained `{"online":false,"reason":"mqtt_disconnect"}` to `statusTopic_` on any unexpected disconnect |

Exponential backoff for MQTT reconnect is not yet implemented; `kMqttRetryMs` (5 s) is used as a fixed interval. **TODO**: Add exponential backoff with `kMqttRetryMs` as initial and `kMqttBackoffMaxMs` as cap.

---

## 4. Recovery After Reconnect

### MQTT Reconnect Sequence

1. `connectOnce()` calls `client_.connect(..., statusTopic_, 1, true, kOfflinePayload)` — configures Last Will.
2. `client_.subscribe(commandTopic_, 1)` — restores command subscription.
3. `publishOnlineStatus()` — publishes `{"online":true,"protocol":"amlp/1","firmware":"0.1.0"}` to `statusTopic_` (retained).
4. Pending command queue is **not cleared** — in-flight commands that were sent before disconnect are still tracked in `BridgeCore` and will receive ACKs after reconnect. Commands that timed out during disconnect are handled by the normal retry logic.
5. No re-subscription to any other topics is required (bridge only subscribes to `commandTopic_`).

> **TODO**: Pending commands that exceeded `maxAttempts` during disconnect should be explicitly failed on reconnect. The current `BridgeCore` tick does not know the connection was lost; adding a "connection-up" callback to `MqttBridge` would allow it to scan for timed-out commands.

---

## 5. Diagnostics Counters

The bridge tracks the following counters for diagnostics and operational monitoring. These are currently **stubs**; they must be incremented by the relevant transport and protocol layers.

| Counter              | Description                                                        | Location to increment                          |
|----------------------|--------------------------------------------------------------------|------------------------------------------------|
| `tx_frames`          | AMLP frames sent to uKit over UART                                 | `UartAdapter::send()`                          |
| `rx_frames`          | AMLP frames received from uKit over UART                           | `UartAdapter::handleFrame()`                   |
| `crc_errors`         | Frames rejected due to CRC mismatch                                 | `amlp::Parser` (in `uart_adapter.cpp`)        |
| `parse_errors`       | Frames rejected due to syntax/format errors (no `@`, bad field)    | `amlp::Parser`                                 |
| `retries`            | Command retransmission attempts (same sequence number)              | `BridgeCore` retry logic                       |
| `queue_depth`        | Current number of pending commands in the queue                    | `BridgeCore::enqueue()` / `acknowledge()`     |
| `mqtt_publishes`     | MQTT packets published (commands/acks)                              | `MqttBridge::publishCompletion()`               |
| `mqtt_connects`      | Successful MQTT connect attempts                                    | `MqttBridge::connectOnce()` success branch     |
| `wifi_reconnects`    | Wi-Fi reconnection events (Connecting → Connected)                  | `WifiStateMachine` Connected transition        |
| `heartbeats_sent`    | Heartbeat messages published                                        | `publishHeartbeat()`                           |
| `telemetry_timeout_count` | Number of times telemetry became stale                         | `checkTelemetryHealth()`                       |

Counters are reset only on boot. They are included in the heartbeat payload as a cumulative snapshot.

> **TODO**: Implement a `DiagnosticsCounters` struct in `diagnostics.h`, expose it via `BridgeCore` or a standalone `Diagnostics` singleton, and increment counters at the identified locations.

---

## 6. MQTT Last Will and Testament

The bridge configures a Last Will message at connect time:

| Property     | Value                                                            |
|--------------|------------------------------------------------------------------|
| Topic        | `smart-factory/bridge/{id}/status` (same as status topic)         |
| QoS          | 1                                                                 |
| Retain       | Yes                                                               |
| Payload      | `{"online":false,"reason":"mqtt_disconnect"}`                   |

The Last Will fires when the ESP32's TCP connection to the broker is lost unexpectedly (crash, power loss, network partition). A clean `client_.disconnect()` call **does not** trigger the Last Will because `connectOnce()` first calls `client_.disconnect()` before the next connect attempt.

External monitors (SCADA, home automation) can subscribe to the status topic and receive the retained offline message immediately upon bridge disconnect.

> **Note**: The current firmware publishes a retained `online: true` status on every successful reconnect, which overwrites any previous Last Will payload. This is correct behavior — the retained offline message only persists if the bridge does not reconnect.

---

## Stub Implementation Notes

| Stub function            | Location                  | Status    |
|--------------------------|---------------------------|-----------|
| `publishHeartbeat()`     | `mqtt_bridge.cpp`         | TODO      |
| `checkTelemetryHealth()` | `mqtt_bridge.cpp`         | TODO      |
| `DiagnosticsCounters`    | `include/diagnostics.h`   | TODO      |
| `updateCounters()`       | `src/diagnostics.cpp`     | TODO      |
| MQTT backoff             | `mqtt_bridge.cpp`         | TODO      |
| Connection-up callback   | `mqtt_bridge.cpp`         | TODO      |
