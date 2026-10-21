/**
 * HTTP client for the Smart Factory Gateway REST API
 *
 * SECURITY: Uses httpOnly cookies for token storage via credentials: 'include'.
 * This is more secure than localStorage as tokens are not accessible to JavaScript
 * and are automatically sent with requests (subject to same-origin policy).
 *
 * Residual limitations:
 * - Requires same-origin or properly configured CORS with credentials
 * - Cookies can be vulnerable to CSRF attacks (mitigated by SameSite=strict)
 * - Cannot be used with cross-origin API calls without proper CORS configuration
 */

import type {
  DeviceSnapshot,
  SystemHealth,
  TelemetryDataPoint,
  TimeRange,
  DeviceId,
  Incident,
  IncidentWithAudit,
  IncidentStatus,
  IncidentSeverity,
  LoginCredentials,
  AuthResponse,
  AuthTokens,
  AuthUser,
  RefreshTokenRequest,
  ProductionJob,
  ProductionMaterial,
  ProductionJobWithLineage,
  JobStatus,
  MaterialStatus,
} from '../../contracts/gateway';

const DEFAULT_API_URL = import.meta.env.VITE_GATEWAY_API_URL || 'http://localhost:8000';

class GatewayApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = DEFAULT_API_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Create fetch options with credentials: include for cookie-based auth
   */
  private _fetchOptions(additionalOptions: RequestInit = {}): RequestInit {
    return {
      credentials: 'include', // Send httpOnly cookies automatically
      ...additionalOptions,
    };
  }

  /**
   * Get device snapshots (current state of all devices)
   */
  async getSnapshots(): Promise<DeviceSnapshot[]> {
    const response = await fetch(`${this.baseUrl}/api/snapshot`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to fetch snapshots: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get system health status
   */
  async getHealth(): Promise<SystemHealth> {
    const response = await fetch(`${this.baseUrl}/api/health`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to fetch health: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get historical telemetry data for a device
   */
  async getMetrics(
    deviceId: DeviceId,
    timeRange: TimeRange,
    metric: string = 'value'
  ): Promise<TelemetryDataPoint[]> {
    const params = new URLSearchParams({
      device_id: deviceId,
      time_range: timeRange,
      metric,
    });

    const response = await fetch(`${this.baseUrl}/api/metrics?${params}`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to fetch metrics: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get events from the gateway
   */
  async getEvents(
    deviceId?: DeviceId,
    severity?: string,
    limit: number = 100
  ): Promise<import('../../contracts/gateway').GatewayEvent[]> {
    const params = new URLSearchParams({ limit: String(limit) });

    if (deviceId) {
      params.set('device_id', deviceId);
    }
    if (severity) {
      params.set('severity', severity);
    }

    const response = await fetch(`${this.baseUrl}/api/events?${params}`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to fetch events: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get all incidents with optional filters
   */
  async getIncidents(
    status?: IncidentStatus,
    severity?: IncidentSeverity,
    deviceId?: DeviceId,
    limit: number = 100
  ): Promise<Incident[]> {
    const params = new URLSearchParams({ limit: String(limit) });

    if (status) {
      params.set('status', status);
    }
    if (severity) {
      params.set('severity', severity);
    }
    if (deviceId) {
      params.set('device_id', deviceId);
    }

    const response = await fetch(`${this.baseUrl}/api/incidents?${params}`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to fetch incidents: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get a single incident by ID with full audit trail
   */
  async getIncident(incidentId: string): Promise<IncidentWithAudit> {
    const response = await fetch(`${this.baseUrl}/api/incidents/${incidentId}`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to fetch incident: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Acknowledge an incident
   */
  async acknowledgeIncident(
    incidentId: string,
    operatorToken: string,
    notes?: string
  ): Promise<Incident> {
    const response = await fetch(`${this.baseUrl}/api/incidents/${incidentId}/acknowledge`, this._fetchOptions({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Operator-Token': operatorToken,
      },
      body: JSON.stringify({ notes }),
    }));
    if (!response.ok) {
      throw new Error(`Failed to acknowledge incident: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Resolve an incident
   */
  async resolveIncident(
    incidentId: string,
    operatorToken: string,
    notes?: string
  ): Promise<Incident> {
    const response = await fetch(`${this.baseUrl}/api/incidents/${incidentId}/resolve`, this._fetchOptions({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Operator-Token': operatorToken,
      },
      body: JSON.stringify({ notes }),
    }));
    if (!response.ok) {
      throw new Error(`Failed to resolve incident: ${response.status}`);
    }
    return response.json();
  }

  // ============ Auth API Methods ============

  /**
   * Login with username and password
   * Note: Login sets httpOnly cookies via response, which are then sent automatically
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await fetch(`${this.baseUrl}/api/auth/login`, this._fetchOptions({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
    }));
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(error.detail || `Login failed: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Refresh access token using refresh token
   * Note: Uses cookies for authentication, refresh token from memory
   */
  async refreshToken(request: RefreshTokenRequest): Promise<AuthTokens> {
    const response = await fetch(`${this.baseUrl}/api/auth/refresh`, this._fetchOptions({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }));
    if (!response.ok) {
      throw new Error(`Token refresh failed: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Logout (invalidate refresh token)
   */
  async logout(refreshToken: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/auth/logout`, this._fetchOptions({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }));
    if (!response.ok) {
      throw new Error(`Logout failed: ${response.status}`);
    }
  }

  /**
   * Get current user info - uses cookie-based auth
   */
  async getCurrentUser(): Promise<AuthUser> {
    const response = await fetch(`${this.baseUrl}/api/auth/me`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to get user: ${response.status}`);
    }
    return response.json();
  }

  // ============ Job & Material API Methods ============

  /**
   * Get all production jobs with optional filters
   */
  async getJobs(
    status?: JobStatus,
    limit: number = 100
  ): Promise<ProductionJob[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (status) {
      params.set('status', status);
    }
    const response = await fetch(`${this.baseUrl}/api/jobs?${params}`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to fetch jobs: ${response.status}`);
    }
    const data = await response.json();
    return data.jobs || [];
  }

  /**
   * Get a single job by ID with full lineage
   */
  async getJob(jobId: string): Promise<ProductionJobWithLineage> {
    const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to fetch job: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Create a new production job
   */
  async createJob(
    job: Partial<ProductionJob>
  ): Promise<ProductionJob> {
    const response = await fetch(`${this.baseUrl}/api/jobs`, this._fetchOptions({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(job),
    }));
    if (!response.ok) {
      throw new Error(`Failed to create job: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Cancel a production job
   */
  async cancelJob(
    jobId: string
  ): Promise<ProductionJob> {
    const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}/cancel`, this._fetchOptions({
      method: 'POST',
    }));
    if (!response.ok) {
      throw new Error(`Failed to cancel job: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get all materials with optional filters
   */
  async getMaterials(
    status?: MaterialStatus,
    batchId?: string,
    limit: number = 100
  ): Promise<ProductionMaterial[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (status) {
      params.set('status', status);
    }
    if (batchId) {
      params.set('batch_id', batchId);
    }
    const response = await fetch(`${this.baseUrl}/api/materials?${params}`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to fetch materials: ${response.status}`);
    }
    const data = await response.json();
    return data.materials || [];
  }

  /**
   * Get a single material by ID with full lineage
   */
  async getMaterial(materialId: string): Promise<ProductionMaterial> {
    const response = await fetch(`${this.baseUrl}/api/materials/${materialId}`, this._fetchOptions());
    if (!response.ok) {
      throw new Error(`Failed to fetch material: ${response.status}`);
    }
    return response.json();
  }
}

export const gatewayApi = new GatewayApiClient();
export default GatewayApiClient;
