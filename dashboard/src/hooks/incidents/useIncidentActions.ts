/**
 * Hook for incident acknowledge/resolve actions
 */

import { useState, useCallback } from 'react';
import { gatewayApi } from '../../services/api/client';
import type { Incident } from '../../contracts/gateway';

interface UseIncidentActionsResult {
  actionInProgress: boolean;
  actionError: string | null;
  acknowledge: (incidentId: string, operatorToken: string, notes?: string) => Promise<Incident | null>;
  resolve: (incidentId: string, operatorToken: string, notes?: string) => Promise<Incident | null>;
  clearError: () => void;
}

export function useIncidentActions(): UseIncidentActionsResult {
  const [actionInProgress, setActionInProgress] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const acknowledge = useCallback(
    async (incidentId: string, operatorToken: string, notes?: string): Promise<Incident | null> => {
      setActionInProgress(true);
      setActionError(null);

      try {
        const result = await gatewayApi.acknowledgeIncident(incidentId, operatorToken, notes);
        return result;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to acknowledge incident';
        setActionError(message);
        return null;
      } finally {
        setActionInProgress(false);
      }
    },
    []
  );

  const resolve = useCallback(
    async (incidentId: string, operatorToken: string, notes?: string): Promise<Incident | null> => {
      setActionInProgress(true);
      setActionError(null);

      try {
        const result = await gatewayApi.resolveIncident(incidentId, operatorToken, notes);
        return result;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to resolve incident';
        setActionError(message);
        return null;
      } finally {
        setActionInProgress(false);
      }
    },
    []
  );

  const clearError = useCallback(() => {
    setActionError(null);
  }, []);

  return {
    actionInProgress,
    actionError,
    acknowledge,
    resolve,
    clearError,
  };
}

export default useIncidentActions;
