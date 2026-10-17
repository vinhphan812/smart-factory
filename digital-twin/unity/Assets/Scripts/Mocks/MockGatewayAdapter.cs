using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace SmartFactory.DigitalTwin.Mocks
{
    /// <summary>
    /// Mock gateway adapter for L2 simulation testing.
    /// Generates deterministic telemetry events without real hardware.
    /// See: docs/hardware-blocked-issues-audit.md - L2 simulator path
    /// </summary>
    public class MockGatewayAdapter : MonoBehaviour
    {
        [Header("Simulation Configuration")]
        public bool enableSimulation = true;
        public float telemetryInterval = 1.0f; // seconds
        public string conveyorDeviceId = "ukit-00000000";
        public string[] actuatorDeviceIds = new string[]
        {
            "ukit-AABBCC01", "ukit-AABBCC02", "ukit-AABBCC03", "ukit-AABBCC04",
            "ukit-AABBCC05", "ukit-AABBCC06", "ukit-AABBCC07", "ukit-AABBCC08"
        };

        // Event dispatchers (same as GatewayAdapter)
        public event Action<CanonicalEvent> OnTelemetry;
        public event Action<CanonicalEvent> OnCommandAck;
        public event Action<string, bool> OnConnectionStatus;

        // Simulation state
        private Coroutine _simulationCoroutine;
        private int _sequenceCounter = 0;
        private bool _conveyorRunning = false;
        private int _conveyorSpeed = 0;
        private bool[] _actuatorStates = new bool[8];

        private void Start()
        {
            if (enableSimulation)
            {
                _simulationCoroutine = StartCoroutine(SimulationLoop());
                
                // Simulate initial online status
                OnConnectionStatus?.Invoke(conveyorDeviceId, true);
                foreach (var id in actuatorDeviceIds)
                {
                    OnConnectionStatus?.Invoke(id, true);
                }
            }
        }

        private void OnDestroy()
        {
            if (_simulationCoroutine != null)
            {
                StopCoroutine(_simulationCoroutine);
            }
        }

        private IEnumerator SimulationLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(telemetryInterval);
                GenerateTelemetry();
            }
        }

        private void GenerateTelemetry()
        {
            // Generate conveyor telemetry
            GenerateConveyorTelemetry();
            
            // Generate actuator telemetry
            for (int i = 0; i < actuatorDeviceIds.Length; i++)
            {
                GenerateActuatorTelemetry(actuatorDeviceIds[i], i);
            }
        }

        private void GenerateConveyorTelemetry()
        {
            // Toggle conveyor state periodically for demo
            if (UnityEngine.Random.value > 0.7f)
            {
                _conveyorRunning = !_conveyorRunning;
                _conveyorSpeed = _conveyorRunning ? 60 : 0;
            }

            // Generate sensor values
            bool sensor1 = UnityEngine.Random.value > 0.5f;
            bool sensor2 = UnityEngine.Random.value > 0.5f;

            var payload = new TelemetryPayload
            {
                device_id = conveyorDeviceId,
                received_at_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                values = new string[] { "CONVEYOR", _conveyorRunning ? "RUNNING" : "IDLE", _conveyorSpeed.ToString() },
                pairs = new Dictionary<string, string>
                {
                    { "SENSOR1", sensor1 ? "1" : "0" },
                    { "SENSOR2", sensor2 ? "1" : "0" }
                }
            };

            var evt = new CanonicalEvent
            {
                event_id = Guid.NewGuid().ToString(),
                device_id = conveyorDeviceId,
                event_type = "telemetry",
                payload = payload,
                mqtt_topic = $"smart-factory/{conveyorDeviceId}/telemetry",
                mqtt_timestamp_ms = 0,
                ingested_at = DateTimeOffset.UtcNow.ToString("o"),
                sequence = _sequenceCounter++
            };

            OnTelemetry?.Invoke(evt);
        }

        private void GenerateActuatorTelemetry(string deviceId, int index)
        {
            // Randomly toggle actuator state
            if (UnityEngine.Random.value > 0.8f)
            {
                _actuatorStates[index] = !_actuatorStates[index];
            }

            string channel = $"CH{UnityEngine.Random.Range(1, 5)}";
            string value = _actuatorStates[index] ? "ON" : "OFF";

            // Generate sensor readings
            int pressure = UnityEngine.Random.Range(400, 600);
            int temp = UnityEngine.Random.Range(2000, 3000);

            var payload = new TelemetryPayload
            {
                device_id = deviceId,
                received_at_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                values = new string[] { "ACTUATOR", channel, value },
                pairs = new Dictionary<string, string>
                {
                    { "PRESSURE", pressure.ToString() },
                    { "TEMP", temp.ToString() }
                }
            };

            var evt = new CanonicalEvent
            {
                event_id = Guid.NewGuid().ToString(),
                device_id = deviceId,
                event_type = "telemetry",
                payload = payload,
                mqtt_topic = $"smart-factory/{deviceId}/telemetry",
                mqtt_timestamp_ms = 0,
                ingested_at = DateTimeOffset.UtcNow.ToString("o"),
                sequence = _sequenceCounter++
            };

            OnTelemetry?.Invoke(evt);
        }

        /// <summary>
        /// Simulate a command ACK response.
        /// </summary>
        public void SimulateCommandAck(string deviceId, string commandName, bool success)
        {
            var payload = new TelemetryPayload
            {
                device_id = deviceId,
                received_at_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                values = new string[] { commandName, success ? "OK" : "FAILED" }
            };

            var evt = new CanonicalEvent
            {
                event_id = Guid.NewGuid().ToString(),
                device_id = deviceId,
                event_type = "command_ack",
                payload = payload,
                mqtt_topic = $"smart-factory/{deviceId}/command/ack",
                mqtt_timestamp_ms = 0,
                ingested_at = DateTimeOffset.UtcNow.ToString("o"),
                sequence = _sequenceCounter++
            };

            OnCommandAck?.Invoke(evt);
        }

        /// <summary>
        /// Simulate device going offline.
        /// </summary>
        public void SimulateOffline(string deviceId)
        {
            OnConnectionStatus?.Invoke(deviceId, false);
        }

        /// <summary>
        /// Simulate device coming back online.
        /// </summary>
        public void SimulateOnline(string deviceId)
        {
            OnConnectionStatus?.Invoke(deviceId, true);
        }
    }
}
