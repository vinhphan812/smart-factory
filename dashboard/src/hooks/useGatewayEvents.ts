/**
 * Hook for accessing gateway events with filtering
 */

import { useMemo } from 'react';
import { useGatewayWs } from './useGatewayWs';
import type { GatewayEvent, Severity, DeviceId } from '../contracts/gateway';

interface UseGatewayEventsOptions {
  deviceId?: DeviceId;
  severity?: Severity;
  eventType?: string;
  limit?: number;
}

export function useGatewayEvents(options: UseGatewayEventsOptions = {}): GatewayEvent[] {
  const { events } = useGatewayWs();
  
  const { deviceId, severity, eventType, limit = 100 } = options;

  const filteredEvents = useMemo(() => {
    let filtered = events;

    if (deviceId) {
      filtered = filtered.filter((ev) => ev.device_id === deviceId);
    }

    if (severity) {
      filtered = filtered.filter((ev) => {
        // Determine severity from event (for now, map event_type to severity)
        const evSeverity = determineSeverity(ev);
        return evSeverity === severity;
      });
    }

    if (eventType) {
      filtered = filtered.filter((ev) => ev.event_type === eventType);
    }

    // Apply limit
    return filtered.slice(0, limit);
  }, [events, deviceId, severity, eventType, limit]);

  return filteredEvents;
}

/**
 * Determine severity from a gateway event
 */
function determineSeverity(event: GatewayEvent): Severity {
  if (event.event_type === 'status_offline') {
    return 'WARN';
  }
  
  if (event.event_type === 'command_ack') {
    const status = event.payload?.status;
    if (status === 'error') {
      return 'ERROR';
    }
  }
  
  if (event.event_type === 'error') {
    return 'ERROR';
  }
  
  return 'INFO';
}

export default useGatewayEvents;
