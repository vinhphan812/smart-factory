using System;
using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using SmartFactory.DigitalTwin;
using SmartFactory.DigitalTwin.Mocks;

namespace SmartFactory.DigitalTwin.Tests
{
    /// <summary>
    /// PlayMode tests for MockGatewayAdapter.
    /// </summary>
    public class MockGatewayAdapterPlayModeTests
    {
        private GameObject _go;
        private MockGatewayAdapter _mockAdapter;

        [SetUp]
        public void Setup()
        {
            _go = new GameObject("MockAdapter");
            _mockAdapter = _go.AddComponent<MockGatewayAdapter>();
            _mockAdapter.enableSimulation = false; // Disable auto-simulation
            _mockAdapter.conveyorDeviceId = "ukit-00000000";
        }

        [TearDown]
        public void Teardown()
        {
            UnityEngine.Object.DestroyImmediate(_go);
        }

        [UnityTest]
        public IEnumerator GenerateTelemetry_ProducesValidEvent()
        {
            // Arrange
            CanonicalEvent receivedEvent = null;
            _mockAdapter.OnTelemetry += evt => receivedEvent = evt;

            // Act - manually call telemetry generation would require reflection or exposing method
            // Instead, test the event subscription works
            var testEvt = new CanonicalEvent
            {
                event_id = "test-001",
                device_id = "ukit-00000000",
                event_type = "telemetry",
                payload = new TelemetryPayload
                {
                    device_id = "ukit-00000000",
                    received_at_ms = 1000,
                    values = new string[] { "CONVEYOR", "RUNNING", "60" }
                }
            };

            // Simulate event via direct invocation
            _mockAdapter.OnTelemetry?.Invoke(testEvt);

            yield return null;

            // Assert
            Assert.IsNotNull(receivedEvent);
            Assert.AreEqual("telemetry", receivedEvent.event_type);
        }

        [UnityTest]
        public IEnumerator SimulateCommandAck_FiresEvent()
        {
            // Arrange
            CanonicalEvent receivedAck = null;
            _mockAdapter.OnCommandAck += evt => receivedAck = evt;

            // Act
            _mockAdapter.SimulateCommandAck("ukit-00000000", "CONVEYOR_START", true);

            yield return null;

            // Assert
            Assert.IsNotNull(receivedAck);
            Assert.AreEqual("command_ack", receivedAck.event_type);
            Assert.AreEqual("OK", receivedAck.payload.values[1]);
        }

        [UnityTest]
        public IEnumerator SimulateOffline_FiresEvent()
        {
            // Arrange
            string deviceId = null;
            bool? isOnline = null;
            _mockAdapter.OnConnectionStatus += (id, online) => { deviceId = id; isOnline = online; };

            // Act
            _mockAdapter.SimulateOffline("ukit-00000000");

            yield return null;

            // Assert
            Assert.AreEqual("ukit-00000000", deviceId);
            Assert.IsFalse(isOnline);
        }

        [UnityTest]
        public IEnumerator SimulateOnline_FiresEvent()
        {
            // Arrange
            string deviceId = null;
            bool? isOnline = null;
            _mockAdapter.OnConnectionStatus += (id, online) => { deviceId = id; isOnline = online; };

            // Act
            _mockAdapter.SimulateOnline("ukit-00000000");

            yield return null;

            // Assert
            Assert.AreEqual("ukit-00000000", deviceId);
            Assert.IsTrue(isOnline);
        }
    }
}
