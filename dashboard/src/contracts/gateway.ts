/**
 * TypeScript types for the Smart Factory Gateway API
 * These types mirror the AMLP canonical envelope and gateway REST endpoints
 */

// Severity levels for events and incidents
export type Severity = 'INFO' | 'WARN' | 'ERROR' | 'CRITICAL';

// Device identifiers
export type DeviceId = 'conveyor-01' | 'robotic-arm-01' | 'cnc-mill-01' | string;

// Event types from the gateway
export type EventType = 'telemetry' | 'status_online' | 'status_offline' | 'command_ack' | 'error' | string;

/**
 * Canonical envelope from the gateway WebSocket
 * Matches ADR-0005 Canonical Envelope format
 */
export interface GatewayEvent {
  event_id?: string;
  device_id: DeviceId;
  event_type: EventType;
  trace_id?: string;
  ingested_at: string;
  payload: GatewayPayload;
}

/**
 * Payload contained in gateway events
 */
export interface GatewayPayload {
  value?: number;
  status?: 'ok' | 'error' | string;
  temperature?: number;
  rpm?: number;
  position?: number;
  [key: string]: unknown;
}

/**
 * Snapshot of current device states (from /api/snapshot endpoint)
 */
export interface DeviceSnapshot {
  device_id: DeviceId;
  state: 'online' | 'offline' | 'error';
  last_seen: string;
  metrics: {
    temperature?: number;
    rpm?: number;
    position?: number;
    [key: string]: unknown;
  };
}

/**
 * System health status (from /api/health endpoint)
 */
export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  services: {
    mqtt: boolean;
    websocket: boolean;
    storage: boolean;
  };
}

/**
 * Historical telemetry data point (from /api/metrics endpoint)
 */
export interface TelemetryDataPoint {
  timestamp: string;
  device_id: DeviceId;
  value: number;
  metric: string;
}

/**
 * Incident for tracking errors and critical events
 */
export interface Incident {
  id: string;
  severity: Severity;
  device_id: DeviceId;
  title: string;
  timestamp: string;
  acknowledged: boolean;
  ack_by?: string;
  ack_at?: string;
  notes?: string;
}

/**
 * WebSocket connection status
 */
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

/**
 * Gateway configuration
 */
export interface GatewayConfig {
  wsUrl: string;
  apiUrl: string;
  reconnectInterval: number;
  maxReconnectAttempts: number;
}

/**
 * Time range options for telemetry queries
 */
export type TimeRange = '5m' | '1h' | '24h';

/**
 * Application mode
 */
export type AppMode = 'live' | 'demo';
