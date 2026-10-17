using System;
using UnityEngine;

namespace SmartFactory.DigitalTwin
{
    /// <summary>
    /// Station actuator prefab controller.
    /// Maps device telemetry to Unity GameObject transforms and materials.
    /// See: docs/twin/prefab-module-contracts.md Section 5
    /// </summary>
    public class ActuatorController : MonoBehaviour
    {
        [Header("Visual References")]
        public Renderer channel1Indicator;
        public Renderer channel2Indicator;
        public Renderer channel3Indicator;
        public Renderer channel4Indicator;
        public GameObject statusIndicator;

        [Header("Configuration")]
        public string deviceId;
        public Material onMaterial;
        public Material offMaterial;
        public Material faultMaterial;
        public Material staleMaterial;

        private Renderer[] _channelIndicators;
        private bool[] _channelStates = new bool[4];

        private void Start()
        {
            _channelIndicators = new Renderer[] { 
                channel1Indicator, channel2Indicator, channel3Indicator, channel4Indicator 
            };
            ResetChannels();
        }

        /// <summary>
        /// Update actuator state from DeviceManager.
        /// </summary>
        public void UpdateState(DeviceState state)
        {
            if (state == null) return;

            // Update channel indicators based on actuator channel/value
            if (!string.IsNullOrEmpty(state.actuator_channel) && !string.IsNullOrEmpty(state.actuator_value))
            {
                int channelIndex = GetChannelIndex(state.actuator_channel);
                if (channelIndex >= 0 && channelIndex < 4)
                {
                    _channelStates[channelIndex] = (state.actuator_value == "ON");
                    UpdateChannelIndicator(channelIndex, _channelStates[channelIndex]);
                }
            }

            // Update status indicator (offline/stale)
            if (statusIndicator != null)
            {
                long now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                bool isStale = state.IsStale(now, 60000);
                statusIndicator.SetActive(!state.is_online || isStale);
            }
        }

        private int GetChannelIndex(string channel)
        {
            return channel switch
            {
                "CH1" => 0,
                "CH2" => 1,
                "CH3" => 2,
                "CH4" => 3,
                _ => -1
            };
        }

        private void UpdateChannelIndicator(int index, bool isOn)
        {
            if (index < 0 || index >= _channelIndicators.Length) return;
            
            Renderer r = _channelIndicators[index];
            if (r != null)
            {
                r.material = isOn ? onMaterial : offMaterial;
            }
        }

        private void ResetChannels()
        {
            for (int i = 0; i < 4; i++)
            {
                _channelStates[i] = false;
                UpdateChannelIndicator(i, false);
            }
        }
    }
}
