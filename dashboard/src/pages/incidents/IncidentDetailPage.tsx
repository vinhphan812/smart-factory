/**
 * IncidentDetailPage - single incident view with audit trail
 */

import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useIncidentDetail, useIncidentActions } from '../../hooks/incidents';
import { IncidentTimeline, AcknowledgeButton } from '../../components/incident';

export function IncidentDetailPage() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const navigate = useNavigate();
  const [operatorToken, setOperatorToken] = useState('');

  const { incident, loading, error, refetch } = useIncidentDetail(incidentId || null, {
    autoRefresh: true,
    refreshInterval: 15000,
  });

  const { acknowledge, resolve, actionInProgress, actionError } = useIncidentActions();

  const getSeverityColor = (severity: string): string => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-red-900/60 border-red-600 text-red-200';
      case 'WARNING':
        return 'bg-yellow-900/60 border-yellow-600 text-yellow-200';
      case 'INFO':
        return 'bg-blue-900/60 border-blue-600 text-blue-200';
      default:
        return 'bg-gray-800 border-gray-600 text-gray-300';
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'open':
        return 'bg-orange-900/60 border-orange-600 text-orange-200';
      case 'acknowledged':
        return 'bg-blue-900/60 border-blue-600 text-blue-200';
      case 'resolved':
        return 'bg-green-900/60 border-green-600 text-green-200';
      default:
        return 'bg-gray-800 border-gray-600 text-gray-300';
    }
  };

  const formatTimestamp = (timestamp: string): string => {
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  };

  const handleAcknowledge = async (id: string, notes?: string): Promise<boolean> => {
    if (!operatorToken) {
      alert('Please enter your operator token first');
      return false;
    }
    const result = await acknowledge(id, operatorToken, notes);
    if (result) {
      refetch();
      return true;
    }
    return false;
  };

  const handleResolve = async (id: string, notes?: string): Promise<boolean> => {
    if (!operatorToken) {
      alert('Please enter your operator token first');
      return false;
    }
    const result = await resolve(id, operatorToken, notes);
    if (result) {
      refetch();
      return true;
    }
    return false;
  };

  if (!incidentId) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-300">
          Invalid incident ID
        </div>
        <Link to="/incidents" className="text-blue-400 hover:underline mt-4 inline-block">
          ← Back to Incidents
        </Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin text-3xl">⏳</div>
        <span className="ml-3 text-gray-400">Loading incident details...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-300">
          <span className="font-medium">Error loading incident:</span> {error}
        </div>
        <button
          onClick={() => refetch()}
          className="mt-4 text-blue-400 hover:underline"
        >
          Retry
        </button>
        <Link to="/incidents" className="block mt-4 text-blue-400 hover:underline">
          ← Back to Incidents
        </Link>
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 text-gray-400">
          Incident not found
        </div>
        <Link to="/incidents" className="text-blue-400 hover:underline mt-4 inline-block">
          ← Back to Incidents
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/incidents')}
            className="p-2 bg-gray-800 border border-gray-700 rounded-lg hover:border-gray-600 text-gray-400 hover:text-gray-200 transition-colors"
            title="Back to list"
          >
            ←
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-100">Incident Details</h1>
            <p className="text-sm text-gray-500 font-mono">{incident.id}</p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => refetch()}
            className="p-2 bg-gray-800 border border-gray-700 rounded-lg hover:border-gray-600 text-gray-400 hover:text-gray-200 transition-colors"
            title="Refresh"
          >
            🔄
          </button>
        </div>
      </div>

      {/* Operator token input */}
      <div className="bg-gray-800 p-4 rounded-xl border border-gray-700">
        <label htmlFor="operator-token" className="block text-sm font-medium text-gray-300 mb-2">
          Operator Token (for acknowledge/resolve actions)
        </label>
        <input
          type="password"
          id="operator-token"
          value={operatorToken}
          onChange={(e) => setOperatorToken(e.target.value)}
          placeholder="Enter operator token"
          className="w-full max-w-md bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-[var(--color-primary)]"
        />
      </div>

      {/* Action error */}
      {actionError && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-sm text-red-300">
          {actionError}
        </div>
      )}

      {/* Incident header info */}
      <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-gray-100 mb-2">{incident.title}</h2>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className={`px-2 py-0.5 rounded text-xs font-mono uppercase border ${getSeverityColor(incident.severity)}`}>
                {incident.severity}
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-mono uppercase border ${getStatusColor(incident.status)}`}>
                {incident.status}
              </span>
              <span className="text-gray-400">
                📱 {incident.device_id}
              </span>
            </div>
          </div>

          {/* Action button */}
          <AcknowledgeButton
            incidentId={incident.id}
            currentStatus={incident.status}
            disabled={actionInProgress || !operatorToken}
            onAcknowledge={handleAcknowledge}
            onResolve={handleResolve}
          />
        </div>

        {/* Message */}
        {incident.message && (
          <div className="mb-4">
            <h3 className="text-sm font-medium text-gray-400 mb-1">Description</h3>
            <p className="text-gray-300">{incident.message}</p>
          </div>
        )}

        {/* Details grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-700">
          <div>
            <span className="text-xs text-gray-500 block mb-1">Created</span>
            <span className="text-sm text-gray-300">{formatTimestamp(incident.timestamp)}</span>
          </div>
          {incident.acknowledged_by && (
            <div>
              <span className="text-xs text-gray-500 block mb-1">Acknowledged By</span>
              <span className="text-sm text-gray-300">
                {incident.acknowledged_by}
                {incident.acknowledged_at && (
                  <span className="text-gray-500 ml-1">
                    ({formatTimestamp(incident.acknowledged_at)})
                  </span>
                )}
              </span>
            </div>
          )}
          {incident.resolved_by && (
            <div>
              <span className="text-xs text-gray-500 block mb-1">Resolved By</span>
              <span className="text-sm text-gray-300">
                {incident.resolved_by}
                {incident.resolved_at && (
                  <span className="text-gray-500 ml-1">
                    ({formatTimestamp(incident.resolved_at)})
                  </span>
                )}
              </span>
            </div>
          )}
          {incident.source && (
            <div>
              <span className="text-xs text-gray-500 block mb-1">Source</span>
              <span className="text-sm text-gray-300">{incident.source}</span>
            </div>
          )}
        </div>

        {/* Recommended action */}
        {incident.recommended_action && (
          <div className="mt-4 p-3 bg-blue-900/20 border border-blue-800 rounded-lg">
            <h3 className="text-sm font-medium text-blue-300 mb-1">Recommended Action</h3>
            <p className="text-sm text-blue-200">{incident.recommended_action}</p>
          </div>
        )}

        {/* Notes */}
        {incident.notes && (
          <div className="mt-4 p-3 bg-gray-900/50 border border-gray-700 rounded-lg">
            <h3 className="text-sm font-medium text-gray-400 mb-1">Notes</h3>
            <p className="text-sm text-gray-300 whitespace-pre-wrap">{incident.notes}</p>
          </div>
        )}
      </div>

      {/* Audit Trail */}
      <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
        <h2 className="text-lg font-semibold text-gray-100 mb-4 flex items-center gap-2">
          <span>📋</span>
          <span>Audit Trail</span>
        </h2>
        <IncidentTimeline auditTrail={incident.audit_trail} />
      </div>
    </div>
  );
}

export default IncidentDetailPage;
