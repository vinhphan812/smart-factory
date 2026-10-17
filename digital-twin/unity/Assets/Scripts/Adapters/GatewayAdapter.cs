using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Text.Json;
using UnityEngine;
using WebSocketSharp;

namespace SmartFactory.DigitalTwin
{
    /// <summary>
    /// Gateway transport adapter for WebSocket and REST connectivity.
    /// Handles connection lifecycle, reconnection, and message dispatch.
    /// See: docs/twin/prefab-module-contracts.md Section 7
    /// </summary>
    public class GatewayAdapter : MonoBehaviour
    {
        [Header("Gateway Configuration")]
        [Tooltip("WebSocket URL (e.g., ws://localhost:8000)")]
        public string wsUrl = "ws://localhost:8000";

        [Tooltip("REST API base URL (e.g., http://localhost:8000)")]
        public string restBaseUrl = "http://localhost:8000";

        [Tooltip("Reconnection delay in seconds")]
        public float reconnectDelay = 2.0f;

        [Tooltip("Maximum reconnection attempts (0 = unlimited)")]
        public int maxReconnectAttempts = 10;

        [Tooltip("Telemetry staleness timeout in milliseconds")]
        public long telemetryTimeoutMs = 60000;

        // Event dispatchers
        public event Action<CanonicalEvent> OnTelemetry;
        public event Action<CanonicalEvent> OnCommandAck;
        public event Action<string, bool> OnConnectionStatus; // deviceId, isOnline

        private WebSocket _ws;
        private bool _isConnected;
        private int _reconnectAttempts;
        private ConcurrentQueue<CanonicalEvent> _eventQueue = new ConcurrentQueue<CanonicalEvent>();
        
        // Staleness tracking
        private ConcurrentDictionary<string, long> _lastTelemetryTime = new ConcurrentDictionary<string, long>();
        private Coroutine _stalenessCoroutine;

        private void Start()
        {
            Connect();
            _stalenessCoroutine = StartCoroutine(StalenessCheckLoop());
        }

        private void OnDestroy()
        {
            Disconnect();
            if (_stalenessCoroutine != null)
            {
                StopCoroutine(_stalenessCoroutine);
            }
        }

        /// <summary>
        /// Establish WebSocket connection to gateway.
        /// </summary>
        public void Connect()
        {
            if (_isConnected) return;

            _ws = new WebSocket(wsUrl);
            _ws.OnOpen += OnWsOpen;
            _ws.OnMessage += OnWsMessage;
            _ws.OnError += OnWsError;
            _ws.OnClose += OnWsClose;
            _ws.Connect();
        }

        /// <summary>
        /// Close WebSocket connection.
        /// </summary>
        public void Disconnect()
        {
            if (_ws != null)
            {
                _ws.OnOpen -= OnWsOpen;
                _ws.OnMessage -= OnWsMessage;
                _ws.OnError -= OnWsError;
                _ws.OnClose -= OnWsClose;
                _ws.Close();
                _ws = null;
            }
            _isConnected = false;
        }

        /// <summary>
        /// Request a scene snapshot via REST API.
        /// See: docs/twin/prefab-module-contracts.md Section 7
        /// </summary>
        public async void RequestSnapshot(int limit = 100)
        {
            // TODO: Implement REST snapshot request when gateway supports it
            // GET /events?event_type=telemetry&limit={limit}
            Debug.Log($"[GatewayAdapter] Snapshot request not yet implemented (GET {restBaseUrl}/events?limit={limit})");
        }

        private void OnWsOpen(object sender, EventArgs e)
        {
            _isConnected = true;
            _reconnectAttempts = 0;
            Debug.Log("[GatewayAdapter] WebSocket connected");
        }

        private void OnWsMessage(object sender, MessageEventArgs e)
        {
            try
            {
                var evt = JsonSerializer.Deserialize<CanonicalEvent>(e.Data);
                if (evt != null)
                {
                    _eventQueue.Enqueue(evt);
                    
                    // Update last telemetry time for staleness tracking
                    if (evt.event_type == "telemetry" && evt.payload != null)
                    {
                        _lastTelemetryTime[evt.device_id] = evt.payload.received_at_ms;
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.LogError($"[GatewayAdapter] Failed to parse message: {ex.Message}");
            }
        }

        private void OnWsError(object sender, ErrorEventArgs e)
        {
            Debug.LogError($"[GatewayAdapter] WebSocket error: {e.Message}");
        }

        private void OnWsClose(object sender, CloseEventArgs e)
        {
            _isConnected = false;
            Debug.Log($"[GatewayAdapter] WebSocket closed: {e.Reason}");
            AttemptReconnect();
        }

        private void AttemptReconnect()
        {
            if (maxReconnectAttempts > 0 && _reconnectAttempts >= maxReconnectAttempts)
            {
                Debug.LogError($"[GatewayAdapter] Max reconnection attempts reached");
                return;
            }

            _reconnectAttempts++;
            Debug.Log($"[GatewayAdapter] Attempting reconnect ({_reconnectAttempts})...");
            Invoke(nameof(Connect), reconnectDelay);
        }

        private void Update()
        {
            // Process queued events on main thread
            while (_eventQueue.TryDequeue(out CanonicalEvent evt))
            {
                DispatchEvent(evt);
            }
        }

        private void DispatchEvent(CanonicalEvent evt)
        {
            switch (evt.event_type)
            {
                case "telemetry":
                    OnTelemetry?.Invoke(evt);
                    break;
                case "command_ack":
                    OnCommandAck?.Invoke(evt);
                    break;
                case "status_online":
                    OnConnectionStatus?.Invoke(evt.device_id, true);
                    break;
                case "status_offline":
                    OnConnectionStatus?.Invoke(evt.device_id, false);
                    break;
                default:
                    Debug.LogWarning($"[GatewayAdapter] Unknown event type: {evt.event_type}");
                    break;
            }
        }

        /// <summary>
        /// Coroutine to check for stale telemetry.
        /// See: docs/twin/prefab-module-contracts.md Section 4.5
        /// </summary>
        private System.Collections.IEnumerator StalenessCheckLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(1.0f);
                
                long now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                
                foreach (var kvp in _lastTelemetryTime)
                {
                    if (now - kvp.Value > telemetryTimeoutMs)
                    {
                        // Signal staleness - handled by DeviceManager
                        Debug.Log($"[GatewayAdapter] Telemetry stale for device: {kvp.Key}");
                    }
                }
            }
        }

        /// <summary>
        /// Check if connected to gateway.
        /// </summary>
        public bool IsConnected => _isConnected;
    }
}
