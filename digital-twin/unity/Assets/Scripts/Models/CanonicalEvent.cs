using System;
using System.Collections.Generic;
using UnityEngine;

namespace SmartFactory.DigitalTwin
{
    /// <summary>
    /// Canonical event types from gateway WebSocket.
    /// See: docs/twin/prefab-module-contracts.md Section 6
    /// </summary>
    public enum EventType
    {
        telemetry,
        command_ack,
        status_online,
        status_offline,
        heartbeat
    }

    /// <summary>
    /// Canonical event envelope from iot-gateway.
    /// See: docs/twin/prefab-module-contracts.md Section 6
    /// </summary>
    [Serializable]
    public class CanonicalEvent
    {
        public string event_id;
        public string device_id;
        public string event_type;
        public TelemetryPayload payload;
        public string mqtt_topic;
        public long mqtt_timestamp_ms;
        public string ingested_at;
        public int sequence;
    }

    [Serializable]
    public class TelemetryPayload
    {
        public string device_id;
        public long received_at_ms;
        public string[] values;
        public Dictionary<string, string> pairs;
    }

    /// <summary>
    /// Command acknowledgment from bridge.
    /// See: docs/twin/prefab-module-contracts.md Section 4.2
    /// </summary>
    [Serializable]
    public class CommandAck
    {
        public string request_id;
        public string status;
        public int status_code;
        public int? sequence;
        public string command;
        public int? attempts;
    }

    /// <summary>
    /// Device status payload.
    /// See: docs/twin/prefab-module-contracts.md Section 4.4
    /// </summary>
    [Serializable]
    public class DeviceStatus
    {
        public string status; // "online", "offline", "subscribe_failed", etc.
    }
}
