using System;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using SmartFactory.DigitalTwin;

namespace SmartFactory.DigitalTwin.Tests
{
    /// <summary>
    /// EditMode tests for DeviceManager state reducer.
    /// </summary>
    public class DeviceManagerEditModeTests
    {
        private DeviceManager _deviceManager;

        [SetUp]
        public void Setup()
        {
            var go = new GameObject("DeviceManager");
            _deviceManager = go.AddComponent<DeviceManager>();
        }

        [TearDown]
        public void Teardown()
        {
            UnityEngine.Object.DestroyImmediate(_deviceManager.gameObject);
        }

        [Test]
        public void ProcessEvent_Telemetry_CreatesDeviceState()
        {
            // Arrange
            var evt = new CanonicalEvent
            {
                event_id = "test-001",
                device_id = "ukit-00000000",
                event_type = "telemetry",
                payload = new TelemetryPayload
                {
                    device_id = "ukit-00000000",
                    received_at_ms = 1000,
                    values = new string[] { "CONVEYOR", "RUNNING", "60" },
                    pairs = new Dictionary<string, string> { { "SENSOR1", "1" } }
                }
            };

            // Act
            _deviceManager.ProcessEvent(evt);
            var state = _deviceManager.GetState("ukit-00000000");

            // Assert
            Assert.AreEqual("ukit-00000000", state.device_id);
            Assert.IsTrue(state.is_online);
            Assert.AreEqual("RUNNING", state.conveyor_state);
            Assert.AreEqual(60, state.conveyor_speed);
            Assert.IsTrue(state.sensor1);
        }

        [Test]
        public void ProcessEvent_StatusOnline_SetsOnlineFlag()
        {
            // Arrange
            var evt = new CanonicalEvent
            {
                event_id = "test-002",
                device_id = "ukit-00000000",
                event_type = "status_online"
            };

            // Act
            _deviceManager.ProcessEvent(evt);
            var state = _deviceManager.GetState("ukit-00000000");

            // Assert
            Assert.IsTrue(state.is_online);
        }

        [Test]
        public void ProcessEvent_StatusOffline_SetsOfflineFlag()
        {
            // Arrange
            var onlineEvt = new CanonicalEvent
            {
                event_id = "test-003",
                device_id = "ukit-00000000",
                event_type = "status_online"
            };
            var offlineEvt = new CanonicalEvent
            {
                event_id = "test-004",
                device_id = "ukit-00000000",
                event_type = "status_offline"
            };

            // Act
            _deviceManager.ProcessEvent(onlineEvt);
            _deviceManager.ProcessEvent(offlineEvt);
            var state = _deviceManager.GetState("ukit-00000000");

            // Assert
            Assert.IsFalse(state.is_online);
        }

        [Test]
        public void IsStale_ReturnsTrue_WhenTimeoutExceeded()
        {
            // Arrange
            var evt = new CanonicalEvent
            {
                event_id = "test-005",
                device_id = "ukit-00000000",
                event_type = "telemetry",
                payload = new TelemetryPayload
                {
                    device_id = "ukit-00000000",
                    received_at_ms = 1000,
                    values = new string[] { "CONVEYOR", "IDLE", "0" }
                }
            };
            _deviceManager.ProcessEvent(evt);

            // Act - simulate time passing (in real usage, this would be > 60000ms)
            var state = _deviceManager.GetState("ukit-00000000");
            state.last_seen = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - 70000;

            // Assert
            Assert.IsTrue(_deviceManager.IsStale("ukit-00000000"));
        }

        [Test]
        public void ProcessEvent_ActuatorTelemetry_ParsesCorrectly()
        {
            // Arrange
            var evt = new CanonicalEvent
            {
                event_id = "test-006",
                device_id = "ukit-AABBCC01",
                event_type = "telemetry",
                payload = new TelemetryPayload
                {
                    device_id = "ukit-AABBCC01",
                    received_at_ms = 2000,
                    values = new string[] { "ACTUATOR", "CH2", "ON" },
                    pairs = new Dictionary<string, string> 
                    { 
                        { "PRESSURE", "512" },
                        { "TEMP", "2534" }
                    }
                }
            };

            // Act
            _deviceManager.ProcessEvent(evt);
            var state = _deviceManager.GetState("ukit-AABBCC01");

            // Assert
            Assert.AreEqual("CH2", state.actuator_channel);
            Assert.AreEqual("ON", state.actuator_value);
            Assert.AreEqual(512, state.pressure);
            Assert.AreEqual(2534, state.temperature);
        }
    }
}
