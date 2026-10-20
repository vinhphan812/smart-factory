/**
 * HTTP client for the Smart Factory Gateway REST API
 */

import type { DeviceSnapshot, SystemHealth, TelemetryDataPoint, TimeRange, DeviceId } from '../../contracts/gateway';

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
}

export const gatewayApi = new GatewayApiClient();
export default GatewayApiClient;
