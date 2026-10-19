using System;
using UnityEngine;

namespace SmartFactory.DigitalTwin
{
    /// <summary>
    /// Conveyor prefab controller.
    /// Maps device telemetry to Unity GameObject transforms and materials.
    /// See: docs/twin/prefab-module-contracts.md Section 4
    /// </summary>
    public class ConveyorController : MonoBehaviour
    {
        [Header("Visual References")]
        public Transform beltTransform;
        public Renderer beltRenderer;
        public GameObject sensor1Indicator;
        public GameObject sensor2Indicator;
        public GameObject statusIndicator;

        [Header("Configuration")]
        public string deviceId = "ukit-00000000";
        public float defaultBeltSpeed = 1.0f;
        public Material runningMaterial;
        public Material idleMaterial;
        public Material faultMaterial;
        public Material staleMaterial;

        private Material _currentMaterial;
        private float _beltOffset;

        private void Start()
        {
            _currentMaterial = idleMaterial;
            UpdateVisuals("IDLE", 0);
        }

        /// <summary>
        /// Update conveyor state from DeviceManager.
        /// </summary>
        public void UpdateState(DeviceState state)
        {
            if (state == null) return;

            // Update belt animation
            UpdateVisuals(state.conveyor_state, state.conveyor_speed);

            // Update sensor indicators
            if (sensor1Indicator != null)
            {
                sensor1Indicator.SetActive(state.sensor1);
            }
            if (sensor2Indicator != null)
            {
                sensor2Indicator.SetActive(state.sensor2);
            }

            // Update status indicator (offline/stale)
            if (statusIndicator != null)
            {
                bool isStale = state.IsStale(DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(), 60000);
                statusIndicator.SetActive(!state.is_online || isStale);
            }
        }

        private void UpdateVisuals(string conveyorState, int speed)
        {
            // Animate belt
            if (beltRenderer != null && speed > 0)
            {
                _beltOffset += Time.deltaTime * speed * 0.1f;
                beltRenderer.material.mainTextureOffset = new Vector2(_beltOffset, 0);
            }

            // Update material based on state
            Material targetMaterial = conveyorState switch
            {
                "RUNNING" => runningMaterial,
                "FAULT" => faultMaterial,
                _ => idleMaterial
            };

            if (targetMaterial != null && targetMaterial != _currentMaterial)
            {
                _currentMaterial = targetMaterial;
                if (beltRenderer != null)
                {
                    beltRenderer.material = targetMaterial;
                }
            }
        }

        private void Update()
        {
            // Continuous belt animation when running
            // Note: In production, this should use the actual conveyor_speed from state
        }
    }
}
