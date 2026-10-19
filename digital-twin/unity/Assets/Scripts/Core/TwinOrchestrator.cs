using System.Collections.Generic;
using UnityEngine;

namespace SmartFactory.DigitalTwin
{
    /// <summary>
    /// Main orchestrator for the Digital Twin.
    /// Coordinates GatewayAdapter, DeviceManager, and prefab controllers.
    /// </summary>
    public class TwinOrchestrator : MonoBehaviour
    {
        [Header("References")]
        public GatewayAdapter gatewayAdapter;
        public DeviceManager deviceManager;

        [Header("Prefabs")]
        public ConveyorController conveyorPrefab;
        public ActuatorController[] stationActuators = new ActuatorController[8];

        [Header("Configuration")]
        public string conveyorDeviceId = "ukit-00000000";

        // Active prefab instances
        private ConveyorController _conveyor;
        private Dictionary<string, ActuatorController> _actuatorMap = new Dictionary<string, ActuatorController>();

        private void Start()
        {
            // Wire up events
            if (gatewayAdapter != null)
            {
                gatewayAdapter.OnTelemetry += OnTelemetry;
                gatewayAdapter.OnCommandAck += OnCommandAck;
                gatewayAdapter.OnConnectionStatus += OnConnectionStatus;
            }

            // Initialize conveyor
            if (conveyorPrefab != null)
            {
                _conveyor = Instantiate(conveyorPrefab, transform);
                _conveyor.deviceId = conveyorDeviceId;
            }
        }

        private void OnDestroy()
        {
            if (gatewayAdapter != null)
            {
                gatewayAdapter.OnTelemetry -= OnTelemetry;
                gatewayAdapter.OnCommandAck -= OnCommandAck;
                gatewayAdapter.OnConnectionStatus -= OnConnectionStatus;
            }
        }

        private void Update()
        {
            // Update all prefabs with current state
            UpdatePrefabs();
        }

        private void OnTelemetry(CanonicalEvent evt)
        {
            deviceManager.ProcessEvent(evt);
        }

        private void OnCommandAck(CanonicalEvent evt)
        {
            deviceManager.ProcessEvent(evt);
            Debug.Log($"[TwinOrchestrator] Command ACK: {evt.payload?.values[0]} = {evt.payload?.values[1]}");
        }

        private void OnConnectionStatus(string deviceId, bool isOnline)
        {
            Debug.Log($"[TwinOrchestrator] Device {deviceId} is {(isOnline ? "online" : "offline")}");
        }

        private void UpdatePrefabs()
        {
            // Update conveyor
            if (_conveyor != null)
            {
                DeviceState state = deviceManager.GetState(_conveyor.deviceId);
                _conveyor.UpdateState(state);
            }

            // Update actuators
            foreach (var kvp in _actuatorMap)
            {
                DeviceState state = deviceManager.GetState(kvp.Key);
                kvp.Value.UpdateState(state);
            }
        }

        /// <summary>
        /// Register an actuator prefab for a device.
        /// </summary>
        public void RegisterActuator(string deviceId, ActuatorController actuator)
        {
            _actuatorMap[deviceId] = actuator;
        }
    }
}
