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

// ============ Auth & RBAC Types ============

/**
 * User roles for RBAC
 */
export type UserRole = 'operator' | 'supervisor' | 'admin';

/**
 * Permission scope for operations
 */
export type PermissionScope =
  | 'dashboard:view'
  | 'incidents:view'
  | 'incidents:acknowledge'
  | 'incidents:resolve'
  | 'safety-gate:status'
  | 'safety-gate:emergency-stop'
  | 'safety-gate:interlock'
  | 'safety-gate:override'
  | 'jobs:view'
  | 'jobs:create'
  | 'jobs:cancel'
  | 'materials:view'
  | 'admin:users'
  | 'admin:settings';

/**
 * Role-based permission mapping
 */
export const ROLE_PERMISSIONS: Record<UserRole, PermissionScope[]> = {
  operator: [
    'dashboard:view',
    'incidents:view',
    'incidents:acknowledge',
    'safety-gate:status',
    'jobs:view',
    'materials:view',
  ],
  supervisor: [
    'dashboard:view',
    'incidents:view',
    'incidents:acknowledge',
    'incidents:resolve',
    'safety-gate:status',
    'safety-gate:emergency-stop',
    'safety-gate:interlock',
    'safety-gate:override',
    'jobs:view',
    'jobs:create',
    'jobs:cancel',
    'materials:view',
  ],
  admin: [
    'dashboard:view',
    'incidents:view',
    'incidents:acknowledge',
    'incidents:resolve',
    'safety-gate:status',
    'safety-gate:emergency-stop',
    'safety-gate:interlock',
    'safety-gate:override',
    'jobs:view',
    'jobs:create',
    'jobs:cancel',
    'materials:view',
    'admin:users',
    'admin:settings',
  ],
};

/**
 * Auth tokens returned from login
 */
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;  // seconds
  token_type: 'Bearer';
}

/**
 * User info from auth
 */
export interface AuthUser {
  user_id: string;
  username: string;
  role: UserRole;
  display_name: string;
  permissions: PermissionScope[];
}

/**
 * Login credentials
 */
export interface LoginCredentials {
  username: string;
  password: string;
}

/**
 * Auth response with user and tokens
 */
export interface AuthResponse {
  user: AuthUser;
  tokens: AuthTokens;
}

/**
 * Refresh token request
 */
export interface RefreshTokenRequest {
  refresh_token: string;
}

// ============ Job & Material Lineage Types ============

/**
 * Job states in the production pipeline
 */
export type JobStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled';

/**
 * Material states
 */
export type MaterialStatus = 'pending' | 'processing' | 'completed' | 'rejected' | 'scrapped';

/**
 * Lineage event type for tracking state changes
 */
export type LineageEventType =
  | 'job_created'
  | 'job_started'
  | 'job_completed'
  | 'job_failed'
  | 'job_cancelled'
  | 'material_received'
  | 'material_processing'
  | 'material_completed'
  | 'material_rejected'
  | 'material_scraped'
  | 'material_transferred';

/**
 * Lineage event for tracking state changes with timestamp and module
 */
export interface LineageEvent {
  event_id: string;
  event_type: LineageEventType;
  job_id?: string;
  material_id?: string;
  batch_id?: string;
  module_id: string;
  from_state?: string;
  to_state?: string;
  timestamp: string;
  operator_id?: string;
  details?: Record<string, unknown>;
}

/**
 * Production job
 */
export interface ProductionJob {
  job_id: string;
  batch_id: string;
  product_type: string;
  quantity: number;
  status: JobStatus;
  priority: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
  failure_reason?: string;
  current_module?: string;
  lineage_events: LineageEvent[];
}

/**
 * Material in production
 */
export interface ProductionMaterial {
  material_id: string;
  batch_id: string;
  current_module: string;
  status: MaterialStatus;
  received_at: string;
  processed_at?: string;
  completed_at?: string;
  rejected_at?: string;
  rejection_reason?: string;
  properties?: Record<string, unknown>;
  lineage_events: LineageEvent[];
}

/**
 * Job with full lineage
 */
export interface ProductionJobWithLineage extends ProductionJob {
  materials: ProductionMaterial[];
}
