/**
 * Typed HTTP Client for Smart Factory IoT Gateway
 *
 * Provides full type coverage for all Gateway REST endpoints.
 * Endpoint definitions from iot-gateway/src/iot_gateway/api.py
 */

import type {
  EventsResponse,
  EventQueryParams,
  HealthResponse,
  MetricsResponse,
  SnapshotResponse,
  SingleEventResponse,
} from '../types/gateway';

// Default gateway URL - can be overridden via environment
const DEFAULT_HTTP_URL = import.meta.env.VITE_GATEWAY_HTTP_URL || 'http://localhost:8000';

/** Custom error class for API errors */
export class GatewayApiError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly endpoint: string
  ) {
    super(message);
    this.name = 'GatewayApiError';
  }
}

/**
 * Base fetch options with timeout support
 */
interface FetchOptions extends RequestInit {
  timeout?: number;
}

/**
 * Execute fetch with timeout
 */
async function fetchWithTimeout(
  url: string,
  options: FetchOptions = {}
): Promise<Response> {
  const { timeout = 10000, ...fetchOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Typed HTTP client for the Smart Factory IoT Gateway API
 */
export class GatewayHttpClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = DEFAULT_HTTP_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // Remove trailing slash
  }

  /**
   * Health check endpoint - GET /health
   */
  async getHealth(): Promise<HealthResponse> {
    const response = await fetchWithTimeout(`${this.baseUrl}/health`);

    if (!response.ok) {
      throw new GatewayApiError(
        `Health check failed: ${response.statusText}`,
        response.status,
        '/health'
      );
    }

    return response.json() as Promise<HealthResponse>;
  }

  /**
   * List events with optional filtering - GET /events
   */
  async listEvents(params: EventQueryParams = {}): Promise<EventsResponse> {
    const searchParams = new URLSearchParams();

    if (params.device_id) {
      searchParams.set('device_id', params.device_id);
    }
    if (params.event_type) {
      searchParams.set('event_type', params.event_type);
    }
    if (params.limit !== undefined) {
      searchParams.set('limit', String(params.limit));
    }

    const url = `${this.baseUrl}/events${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetchWithTimeout(url);

    if (!response.ok) {
      throw new GatewayApiError(
        `Failed to list events: ${response.statusText}`,
        response.status,
        '/events'
      );
    }

    return response.json() as Promise<EventsResponse>;
  }

  /**
   * Get single event by ID - GET /events/{event_id}
   */
  async getEvent(eventId: string): Promise<SingleEventResponse> {
    const response = await fetchWithTimeout(`${this.baseUrl}/events/${encodeURIComponent(eventId)}`);

    if (!response.ok) {
      if (response.status === 404) {
        throw new GatewayApiError(
          `Event not found: ${eventId}`,
          response.status,
          `/events/${eventId}`
        );
      }
      throw new GatewayApiError(
        `Failed to get event: ${response.statusText}`,
        response.status,
        `/events/${eventId}`
      );
    }

    return response.json() as Promise<SingleEventResponse>;
  }

  /**
   * Get scene snapshot - GET /snapshot
   *
   * For initial load or resync after disconnect.
   * Use since_sequence=0 for full snapshot, or last known sequence for incremental.
   */
  async getSnapshot(
    sinceSequence: number = 0,
    limit: number = 1000
  ): Promise<SnapshotResponse> {
    const searchParams = new URLSearchParams({
      since_sequence: String(sinceSequence),
      limit: String(limit),
    });

    const response = await fetchWithTimeout(
      `${this.baseUrl}/snapshot?${searchParams}`
    );

    if (!response.ok) {
      throw new GatewayApiError(
        `Failed to get snapshot: ${response.statusText}`,
        response.status,
        '/snapshot'
      );
    }

    return response.json() as Promise<SnapshotResponse>;
  }

  /**
   * Get time/metrics data - GET /metrics
   */
  async getMetrics(queueDroppedCount: number = 0): Promise<MetricsResponse> {
    const searchParams = new URLSearchParams({
      queue_dropped_count: String(queueDroppedCount),
    });

    const response = await fetchWithTimeout(
      `${this.baseUrl}/metrics?${searchParams}`
    );

    if (!response.ok) {
      throw new GatewayApiError(
        `Failed to get metrics: ${response.statusText}`,
        response.status,
        '/metrics'
      );
    }

    return response.json() as Promise<MetricsResponse>;
  }

  /**
   * Get root info - GET /
   */
  async getRootInfo(): Promise<{ service: string; version: string; docs: string }> {
    const response = await fetchWithTimeout(`${this.baseUrl}/`);

    if (!response.ok) {
      throw new GatewayApiError(
        `Failed to get root info: ${response.statusText}`,
        response.status,
        '/'
      );
    }

    return response.json() as Promise<{ service: string; version: string; docs: string }>;
  }
}

// Singleton instance for convenience
export const gatewayHttpClient = new GatewayHttpClient();

// Re-export types for consumers
export type { EventQueryParams };
