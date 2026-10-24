/**
 * Gateway Store - Resilient State Management
 *
 * Zustand store for Smart Factory Gateway state with:
 * - Live event updates via WebSocket
 * - Stale data detection
 * - Connection state management
 * - Device registry
 * - Incident tracking
 */

import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type {
  CanonicalEvent,
  ConnectionState,
  DeviceInfo,
  HealthResponse,
  Incident,
  MetricsResponse,
  OperationalMode,
  Severity,
  TelemetryPoint,
  TimeRange,
} from '../types/gateway';
import { EventType } from '../types/gateway';
import { gatewayHttpClient } from '../api/gateway';
import { GatewayWebSocketClient } from '../api/websocket';

/** Time range to milliseconds mapping */
const TIME_RANGE_MS: Record<TimeRange, number> = {
  '5m': 5 * 60 * 1000,
  '1h': 60 * 60 * 1000,
  '24h': 24 * 60 * 60 * 1000,
};

/** Store state interface */
interface GatewayStore {
  // Connection state
  connectionState: ConnectionState;
  operationalMode: OperationalMode;
  isStale: boolean;
  lastUpdateTime: number;

  // Gateway data
  events: CanonicalEvent[];
  telemetryPoints: TelemetryPoint[];
  incidents: Incident[];
  devices: Map<string, DeviceInfo>;
  health: HealthResponse | null;
  metrics: MetricsResponse | null;

  // UI state
  selectedDevice: string;
  timeRange: TimeRange;
  severityFilter: Severity | '';

  // WebSocket client instance
  wsClient: GatewayWebSocketClient | null;

  // Actions
  setConnectionState: (state: ConnectionState) => void;
  setOperationalMode: (mode: OperationalMode) => void;
  setStale: (isStale: boolean) => void;
  setSelectedDevice: (deviceId: string) => void;
  setTimeRange: (range: TimeRange) => void;
  setSeverityFilter: (severity: Severity | '') => void;

  // Data actions
  addEvent: (event: CanonicalEvent) => void;
  loadSnapshot: (events: CanonicalEvent[], perDeviceLatest: Record<string, CanonicalEvent>) => void;
  acknowledgeIncident: (incidentId: string) => void;
  setHealth: (health: HealthResponse) => void;
  setMetrics: (metrics: MetricsResponse) => void;
  clearStaleData: () => void;

  // WebSocket lifecycle
  connectWebSocket: () => void;
  disconnectWebSocket: () => void;
  initializeFromGateway: () => Promise<void>;
}

/** Helper to derive severity from event */
function deriveSeverity(event: CanonicalEvent): Severity {
  if (event.event_type === EventType.STATUS_OFFLINE) return 'WARN';
  if (event.event_type === EventType.COMMAND_ACK) {
    const status = event.payload?.status as string | undefined;
    if (status === 'error') return 'ERROR';
  }
  return 'INFO';
}

/** Helper to determine if an event should create an incident */
function shouldCreateIncident(event: CanonicalEvent): boolean {
  const severity = deriveSeverity(event);
  return severity === 'ERROR' || severity === 'CRITICAL';
}

/** Helper to create incident from event */
function createIncident(event: CanonicalEvent): Incident {
  return {
    id: `INC-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
    severity: deriveSeverity(event),
    deviceId: event.device_id,
    title: `Event: ${event.event_type}`,
    timestamp: event.ingested_at,
    acknowledged: false,
    ackBy: null,
    ackAt: null,
    notes: `Gateway event type: ${event.event_type}`,
  };
}

/** Helper to extract telemetry point from event */
function extractTelemetryPoint(event: CanonicalEvent): TelemetryPoint | null {
  if (event.event_type !== EventType.TELEMETRY) return null;

  const value = event.payload?.value as number | undefined;
  if (typeof value !== 'number') return null;

  return {
    timestamp: event.ingested_at,
    deviceId: event.device_id,
    value,
    sequence: event.sequence,
  };
}

/**
 * Extract the latest raw firmware/gateway state for a device from the canonical event payload.
 * The canonical envelope keeps module state in `payload.state`; `status` is used as a fallback
 * because some gateway builds publish the state under that key instead.
 */
function extractDeviceState(event: CanonicalEvent): string | undefined {
  const candidate = event.payload?.state ?? event.payload?.status;
  if (typeof candidate === 'string' && candidate.trim().length > 0) {
    return candidate.trim();
  }
  return undefined;
}

/** Create the store */
export const useGatewayStore = create<GatewayStore>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    connectionState: 'disconnected',
    operationalMode: 'demo',
    isStale: false,
    lastUpdateTime: Date.now(),

    events: [],
    telemetryPoints: [],
    incidents: [],
    devices: new Map(),
    health: null,
    metrics: null,

    selectedDevice: 'conveyor-01',
    timeRange: '5m',
    severityFilter: '',

    wsClient: null,

    // Connection actions
    setConnectionState: (state) => set({ connectionState: state }),
    setOperationalMode: (mode) => set({ operationalMode: mode }),
    setStale: (isStale) => set({ isStale }),
    setSelectedDevice: (deviceId) => set({ selectedDevice: deviceId }),
    setTimeRange: (range) => set({ timeRange: range }),
    setSeverityFilter: (severity) => set({ severityFilter: severity }),

    // Data actions
    addEvent: (event) => {
      set((state) => {
        const newEvents = [event, ...state.events].slice(0, 500); // Keep last 500 events

        // Extract telemetry point if applicable
        const telemetryPoint = extractTelemetryPoint(event);
        const newTelemetryPoints = telemetryPoint
          ? [telemetryPoint, ...state.telemetryPoints].slice(0, 1000)
          : state.telemetryPoints;

        // Create incident if needed
        const newIncidents = shouldCreateIncident(event)
          ? [createIncident(event), ...state.incidents].slice(0, 100)
          : state.incidents;

        // Update device registry
                const newDevices = new Map(state.devices);
                const previousDevice = state.devices.get(event.device_id);
                newDevices.set(event.device_id, {
                  deviceId: event.device_id,
                  displayName: event.device_id,
                  type: 'unknown',
                  status: event.event_type === EventType.STATUS_OFFLINE ? 'offline' : 'online',
                  lastSeen: event.ingested_at,
                  // Preserve the last known raw state when an event carries no state payload
                  // (e.g. pure heartbeat or metric event) so RUNNING/FAULT is not silently lost.
                  state: extractDeviceState(event) ?? previousDevice?.state,
                });

        return {
          events: newEvents,
          telemetryPoints: newTelemetryPoints,
          incidents: newIncidents,
          devices: newDevices,
          lastUpdateTime: Date.now(),
          isStale: false,
        };
      });
    },

    loadSnapshot: (events, perDeviceLatest) => {
      set((state) => {
        // Extract all telemetry points from snapshot
        const telemetryPoints: TelemetryPoint[] = [];
        const devices = new Map(state.devices);

        for (const event of events) {
          const point = extractTelemetryPoint(event);
          if (point) {
            telemetryPoints.push(point);
          }

          // Update device status
                    const latestForDevice = perDeviceLatest[event.device_id];
                    if (latestForDevice) {
                      const previousDevice = devices.get(event.device_id);
                      devices.set(event.device_id, {
                        deviceId: event.device_id,
                        displayName: event.device_id,
                        type: 'unknown',
                        status: latestForDevice.event_type === EventType.STATUS_OFFLINE ? 'offline' : 'online',
                        lastSeen: latestForDevice.ingested_at,
                        state: extractDeviceState(latestForDevice) ?? extractDeviceState(event) ?? previousDevice?.state,
                      });
                    }
        }

        return {
          events: events.slice(0, 500),
          telemetryPoints: telemetryPoints.slice(0, 1000),
          devices,
          lastUpdateTime: Date.now(),
        };
      });
    },

    acknowledgeIncident: (incidentId) => {
      set((state) => ({
        incidents: state.incidents.map((inc) =>
          inc.id === incidentId
            ? {
                ...inc,
                acknowledged: true,
                ackBy: 'operator',
                ackAt: new Date().toISOString(),
              }
            : inc
        ),
      }));
    },

    setHealth: (health) => set({ health }),
    setMetrics: (metrics) => set({ metrics }),

    clearStaleData: () => {
      set({ isStale: false });
    },

    // WebSocket lifecycle
    connectWebSocket: () => {
      const { wsClient } = get();

      if (wsClient?.isConnected()) {
        return;
      }

      const client = new GatewayWebSocketClient();
      set({ wsClient: client });

      client.connect({
        onEvent: (event) => {
          get().addEvent(event);
        },
        onConnectionStateChange: (state) => {
          set({ connectionState: state });

          if (state === 'connected') {
            set({ operationalMode: 'live', isStale: false });
          } else if (state === 'disconnected') {
            set({ operationalMode: 'demo' });
          }
        },
        onError: (error) => {
          console.error('WebSocket error:', error);
        },
        onStaleData: () => {
          set({ isStale: true });
        },
      });
    },

    disconnectWebSocket: () => {
      const { wsClient } = get();
      if (wsClient) {
        wsClient.disconnect();
        set({ wsClient: null });
      }
    },

    initializeFromGateway: async () => {
      try {
        // Fetch health
        const health = await gatewayHttpClient.getHealth();
        set({ health });

        // Fetch metrics
        const metrics = await gatewayHttpClient.getMetrics(health.queue_dropped_count);
        set({ metrics });

        // Fetch initial snapshot
        const snapshot = await gatewayHttpClient.getSnapshot(0, 1000);

        // Load events into store
        get().loadSnapshot(snapshot.events, snapshot.per_device_latest);

        // Connect WebSocket for live updates
        get().connectWebSocket();
      } catch (error) {
        console.error('Failed to initialize from gateway:', error);
        // Fall back to demo mode
        set({ operationalMode: 'demo' });
      }
    },
  }))
);

/** Selector hooks for common state slices */
export const useConnectionState = () => useGatewayStore((state) => state.connectionState);
export const useOperationalMode = () => useGatewayStore((state) => state.operationalMode);
export const useIsStale = () => useGatewayStore((state) => state.isStale);
export const useSelectedDevice = () => useGatewayStore((state) => state.selectedDevice);
export const useTimeRange = () => useGatewayStore((state) => state.timeRange);

/** Selector for filtered events */
export const useFilteredEvents = () =>
  useGatewayStore((state) => {
    const { events, selectedDevice, severityFilter, timeRange } = state;
    const cutoff = Date.now() - TIME_RANGE_MS[timeRange];

    return events.filter((event) => {
      // Time filter
      const eventTime = new Date(event.ingested_at).getTime();
      if (eventTime < cutoff) return false;

      // Device filter
      if (selectedDevice && event.device_id !== selectedDevice) return false;

      // Severity filter
      if (severityFilter) {
        const severity = deriveSeverity(event);
        if (severity !== severityFilter) return false;
      }

      return true;
    });
  });

/** Selector for filtered telemetry points */
export const useFilteredTelemetry = () =>
  useGatewayStore((state) => {
    const { telemetryPoints, selectedDevice, timeRange } = state;
    const cutoff = Date.now() - TIME_RANGE_MS[timeRange];

    return telemetryPoints.filter((point) => {
      const pointTime = new Date(point.timestamp).getTime();
      if (pointTime < cutoff) return false;
      if (selectedDevice && point.deviceId !== selectedDevice) return false;
      return true;
    });
  });

/** Selector for active (unacknowledged) incidents */
export const useActiveIncidents = () =>
  useGatewayStore((state) => state.incidents.filter((inc) => !inc.acknowledged));

/** Selector for devices list */
export const useDevices = () =>
  useGatewayStore((state) => Array.from(state.devices.values()));
