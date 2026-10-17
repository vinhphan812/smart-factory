using System;
using System.Collections.Generic;
using UnityEngine;

namespace SmartFactory.DigitalTwin
{
    /// <summary>
    /// Deterministic state reducer for device state.
    /// Applies canonical events to produce new device states.
    /// See: ADR-0003 Section "deterministic state reducer"
    /// </summary>
    public class DeviceManager : MonoBehaviour
    {
        [Header("State Configuration")]
        [Tooltip("Telemetry staleness timeout in milliseconds")]
        public long stalenessTimeoutMs = 60000;

        // Device state storage
        private Dictionary<string, DeviceState> _deviceStates = new Dictionary<string, DeviceState>();
        
        // Event
        public event Action<DeviceState> OnStateChanged;

        /// <summary>
        /// Get current state for a device.
        /// </summary>
        public DeviceState GetState(string deviceId)
        {
            if (!_deviceStates.TryGetValue(deviceId, out DeviceState state))
            {
                state = new DeviceState { device_id = deviceId };
                _deviceStates[deviceId] = state;
            }
            return state;
        }

        /// <summary>
        /// Process incoming canonical event and update state.
        /// </summary>
        public void ProcessEvent(CanonicalEvent evt)
        {
            var state = GetState(evt.device_id);
            
            switch (evt.event_type)
            {
                case "telemetry":
                    ApplyTelemetry(state, evt.payload);
                    break;
                case "status_online":
                    state.is_online = true;
                    state.last_seen = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                    break;
                case "status_offline":
                    state.is_online = false;
                    break;
            }
            
            state.last_event_type = evt.event_type;
            state.last_event_time = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            
            OnStateChanged?.Invoke(state);
        }

        /// <summary>
        /// Apply telemetry payload to device state.
        /// See: docs/twin/prefab-module-contracts.md Section 4.3
        /// </summary>
        private void ApplyTelemetry(DeviceState state, TelemetryPayload payload)
        {
            if (payload == null) return;
            
            state.last_seen = payload.received_at_ms;
            state.is_online = true;
            state.raw_values = payload.values;
            state.raw_pairs = payload.pairs;

            // Parse conveyor telemetry
            if (payload.values != null && payload.values.Length >= 1)
            {
                string metricType = payload.values[0];
                
                if (metricType == "CONVEYOR" && payload.values.Length >= 3)
                {
                    // values[1] = state (RUNNING/IDLE/FAULT)
                    // values[2] = speed
                    state.conveyor_state = payload.values[1];
                    if (int.TryParse(payload.values[2], out int speed))
                    {
                        state.conveyor_speed = speed;
                    }
                }
                else if (metricType == "ACTUATOR" && payload.values.Length >= 3)
                {
                    // values[1] = channel/state
                    // values[2] = value
                    state.actuator_channel = payload.values[1];
                    state.actuator_value = payload.values[2];
                }
            }

            // Parse sensor pairs
            if (payload.pairs != null)
            {
                if (payload.pairs.TryGetValue("SENSOR1", out string s1))
                {
                    state.sensor1 = s1 == "1";
                }
                if (payload.pairs.TryGetValue("SENSOR2", out string s2))
                {
                    state.sensor2 = s2 == "1";
                }
                if (payload.pairs.TryGetValue("PRESSURE", out string pressure))
                {
                    if (int.TryParse(pressure, out int p))
                    {
                        state.pressure = p;
                    }
                }
                if (payload.pairs.TryGetValue("TEMP", out string temp))
                {
                    if (int.TryParse(temp, out int t))
                    {
                        state.temperature = t;
                    }
                }
            }
        }

        /// <summary>
        /// Check if telemetry for a device is stale.
        /// See: docs/twin/prefab-module-contracts.md Section 4.5
        /// </summary>
        public bool IsStale(string deviceId)
        {
            var state = GetState(deviceId);
            long now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            return (now - state.last_seen) > stalenessTimeoutMs;
        }

        /// <summary>
        /// Get all known device IDs.
        /// </summary>
        public IEnumerable<string> GetDeviceIds()
        {
            return _deviceStates.Keys;
        }

        /// <summary>
        /// Clear all device states (for testing).
        /// </summary>
        public void Clear()
        {
            _deviceStates.Clear();
        }
    }

    /// <summary>
    /// Runtime device state representation.
    /// </summary>
    [Serializable]
    public class DeviceState
    {
        public string device_id;
        public bool is_online;
        public long last_seen;
        public string last_event_type;
        public long last_event_time;
        
        // Raw payload
        public string[] raw_values;
        public Dictionary<string, string> raw_pairs;
        
        // Conveyor parsed
        public string conveyor_state; // "RUNNING", "IDLE", "FAULT"
        public int conveyor_speed;
        
        // Actuator parsed
        public string actuator_channel; // "CH1"-CH4"
        public string actuator_value; // "ON", "OFF", or sensor label
        
        // Sensors
        public bool sensor1;
        public bool sensor2;
        public int pressure;
        public int temperature;
        
        // Computed
        public bool IsStale(long now, long timeoutMs)
        {
            return (now - last_seen) > timeoutMs;
        }
    }
}
