/**
 * Gateway API TypeScript Types
 *
 * Type definitions matching the Smart Factory IoT Gateway API.
 * Aligned with:
 * - contracts/v1/schemas/*.schema.json
 * - iot-gateway/src/iot_gateway/models.py (CanonicalEvent)
 * - iot-gateway/src/iot_gateway/api.py (HTTP endpoints)
 */

/** Event types from the gateway canonical event envelope */
export const EventType = {
  COMMAND_ACK: 'command_ack',
  STATUS_ONLINE: 'status_online',
  STATUS_OFFLINE: 'status_offline',
  TELEMETRY: 'telemetry',
  HEARTBEAT: 'heartbeat',
} as const;

export type EventType = typeof EventType[keyof typeof EventType];

/** Severity levels for events and incidents */
export type Severity = 'INFO' | 'WARN' | 'ERROR' | 'CRITICAL';

/** Canonical event envelope from the gateway */
export interface CanonicalEvent {
  event_id: string;
  device_id: string;
  event_type: EventType | string;
  payload: Record<string, unknown>;
  mqtt_topic: string;
  mqtt_timestamp_ms: number;
  /** Canonical timestamp alias */
  timestamp: number;
  received_at: string;
  received_at_ms: number;
  latency_ms: number;
  stale: boolean;
  out_of_order: boolean;
  is_timestamp_synchronized: boolean;
  ingested_at: string;
  sequence: number;
}

/** Event with derived severity (for UI consumption) */
export interface TypedEvent extends CanonicalEvent {
  severity: Severity;
}

/** Query parameters for /events endpoint */
export interface EventQueryParams {
  device_id?: string;
  event_type?: string;
  limit?: number;
}

/** Response from /events endpoint */
export interface EventsResponse {
  events: CanonicalEvent[];
  count: number;
}

/** Response from /events/{event_id} endpoint */
export interface SingleEventResponse extends CanonicalEvent {}

/** Response from /snapshot endpoint */
export interface SnapshotResponse {
  high_watermark: number;
  snapshot_count: number;
  events: CanonicalEvent[];
  per_device_latest: Record<string, CanonicalEvent>;
  overflow: boolean;
  overflow_limit: number;
}

/** Response from /health endpoint */
export interface HealthResponse {
  status: 'ok' | 'error';
  event_count: number;
  high_watermark: number;
  queue_dropped_count: number;
}

/** Latency histogram bucket from /metrics endpoint */
export interface LatencyBucket {
  count: number;
  min: number;
  max: number;
  avg: number;
  p50: number;
  p95: number;
  p99: number;
}

/** Response from /metrics endpoint */
export interface MetricsResponse {
  latency_ms: {
    conveyor_01?: LatencyBucket;
    robotic_arm_01?: LatencyBucket;
    cnc_mill_01?: LatencyBucket;
    [device_id: string]: LatencyBucket | undefined;
  };
  jitter_ms: Record<string, number>;
  stale_event_count: number;
  out_of_order_event_count: number;
  unsynchronized_event_count: number;
  last_event_ms: Record<string, number>;
  queue_dropped_count: number;
}

/** Incident representation for UI */
export interface Incident {
  id: string;
  severity: Severity;
  deviceId: string;
  title: string;
  timestamp: string;
  acknowledged: boolean;
  ackBy: string | null;
  ackAt: string | null;
  notes?: string;
}

/** Telemetry data point for charts */
export interface TelemetryPoint {
  timestamp: string;
  deviceId: string;
  value: number;
  sequence: number;
}

/** Time range options */
export type TimeRange = '5m' | '1h' | '24h';

/** WebSocket connection states */
export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error';

/** Operational modes */
export type OperationalMode = 'live' | 'demo';

/** Device info for registry */
export interface DeviceInfo {
  deviceId: string;
  displayName: string;
  type: 'conveyor' | 'robotic-arm' | 'cnc-mill' | 'unknown';
  status: 'online' | 'offline' | 'unknown';
  lastSeen: string | null;
  /**
   * Latest raw gateway/firmware state for this device (e.g. RUNNING, IDLE, FAULT, E_STOP).
   * Required by the module state derivation so RUNNING/FAULT can be derived from live data
   * instead of falling back to a fabricated state.
   */
  state?: string;
}

/** Gateway configuration from environment */
export interface GatewayConfig {
  httpUrl: string;
  wsUrl: string;
}
