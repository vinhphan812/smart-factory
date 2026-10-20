/**
 * Hook for fetching a single incident with audit trail
 */

import { useState, useEffect, useCallback } from 'react';
import { gatewayApi } from '../../services/api/client';
import type { IncidentWithAudit } from '../../contracts/gateway';

interface UseIncidentDetailOptions {
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseIncidentDetailResult {
  incident: IncidentWithAudit | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useIncidentDetail(
  incidentId: string | null,
  options: UseIncidentDetailOptions = {}
): UseIncidentDetailResult {
  const { autoRefresh = false, refreshInterval = 15000 } = options;

  const [incident, setIncident] = useState<IncidentWithAudit | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchIncident = useCallback(async () => {
    if (!incidentId) {
      setIncident(null);
      setLoading(false);
      return;
    }

    try {
      setError(null);
      const data = await gatewayApi.getIncident(incidentId);
      setIncident(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch incident');
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    fetchIncident();
  }, [fetchIncident]);

  // Auto-refresh for live updates
  useEffect(() => {
    if (!autoRefresh || !incidentId) return;
    
    const interval = setInterval(fetchIncident, refreshInterval);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, incidentId, fetchIncident]);

  return {
    incident,
    loading,
    error,
    refetch: fetchIncident,
  };
}

export default useIncidentDetail;
