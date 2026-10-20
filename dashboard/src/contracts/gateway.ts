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
 * Incident status lifecycle
 */
export type IncidentStatus = 'open' | 'acknowledged' | 'resolved';

/**
 * Incident severity levels (matching AlertSeverity from backend)
 */
export type IncidentSeverity = 'INFO' | 'WARNING' | 'CRITICAL';

/**
 * Audit trail entry for incident state changes
 */
export interface IncidentAuditEntry {
  id: string;
  incident_id: string;
  action: 'created' | 'acknowledged' | 'resolved' | 'note_added';
  operator_id?: string;
  operator_name?: string;
  timestamp: string;
  details?: string;
}

/**
 * Incident for tracking errors and critical events
 */
export interface Incident {
  id: string;
  severity: IncidentSeverity;
  device_id: DeviceId;
  title: string;
  message: string;
  timestamp: string;
  status: IncidentStatus;
  acknowledged_by?: string;
  acknowledged_at?: string;
  resolved_by?: string;
  resolved_at?: string;
  notes?: string;
  source?: string;
  recommended_action?: string;
}

/**
 * Extended incident with audit trail
 */
export interface IncidentWithAudit extends Incident {
  audit_trail: IncidentAuditEntry[];
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
 *
 * - 'live': Connected to real gateway, showing actual telemetry
 * - 'demo': Disconnected, showing simulated demo data
 * - 'simulated': Manually triggered simulation mode (future)
 * - 'replay': Historical event replay mode (future)
 */
export type AppMode = 'live' | 'demo' | 'simulated' | 'replay';
