/**
 * Hook for fetching and managing incidents list
 */

import { useState, useEffect, useCallback } from 'react';
import { gatewayApi } from '../../services/api/client';
import type { Incident, IncidentStatus, IncidentSeverity, DeviceId } from '../../contracts/gateway';

interface UseIncidentsOptions {
  status?: IncidentStatus;
  severity?: IncidentSeverity;
  deviceId?: DeviceId;
  limit?: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseIncidentsResult {
  incidents: Incident[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useIncidents(options: UseIncidentsOptions = {}): UseIncidentsResult {
  const {
    status,
    severity,
    deviceId,
    limit = 100,
    autoRefresh = false,
    refreshInterval = 30000,
  } = options;

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchIncidents = useCallback(async () => {
    try {
      setError(null);
      const data = await gatewayApi.getIncidents(status, severity, deviceId, limit);
      setIncidents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch incidents');
    } finally {
      setLoading(false);
    }
  }, [status, severity, deviceId, limit]);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(fetchIncidents, refreshInterval);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchIncidents]);

  return {
    incidents,
    loading,
    error,
    refetch: fetchIncidents,
  };
}

export default useIncidents;
