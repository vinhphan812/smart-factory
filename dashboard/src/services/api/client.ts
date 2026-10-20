/**
 * HTTP client for the Smart Factory Gateway REST API
 */

import type { DeviceSnapshot, SystemHealth, TelemetryDataPoint, TimeRange, DeviceId, Incident, IncidentWithAudit, IncidentStatus, IncidentSeverity } from '../../contracts/gateway';

const DEFAULT_API_URL = import.meta.env.VITE_GATEWAY_API_URL || 'http://localhost:8000';

class GatewayApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = DEFAULT_API_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Get device snapshots (current state of all devices)
   */
  async getSnapshots(): Promise<DeviceSnapshot[]> {
    const response = await fetch(`${this.baseUrl}/api/snapshot`);
    if (!response.ok) {
      throw new Error(`Failed to fetch snapshots: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get system health status
   */
  async getHealth(): Promise<SystemHealth> {
    const response = await fetch(`${this.baseUrl}/api/health`);
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
    
    const response = await fetch(`${this.baseUrl}/api/metrics?${params}`);
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
    
    const response = await fetch(`${this.baseUrl}/api/events?${params}`);
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
    
    const response = await fetch(`${this.baseUrl}/api/incidents?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch incidents: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get a single incident by ID with full audit trail
   */
  async getIncident(incidentId: string): Promise<IncidentWithAudit> {
    const response = await fetch(`${this.baseUrl}/api/incidents/${incidentId}`);
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
    const response = await fetch(`${this.baseUrl}/api/incidents/${incidentId}/acknowledge`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Operator-Token': operatorToken,
      },
      body: JSON.stringify({ notes }),
    });
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
    const response = await fetch(`${this.baseUrl}/api/incidents/${incidentId}/resolve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Operator-Token': operatorToken,
      },
      body: JSON.stringify({ notes }),
    });
    if (!response.ok) {
      throw new Error(`Failed to resolve incident: ${response.status}`);
    }
    return response.json();
  }
}

export const gatewayApi = new GatewayApiClient();
export default GatewayApiClient;
