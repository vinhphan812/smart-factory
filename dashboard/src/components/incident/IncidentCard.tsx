/**
 * IncidentCard - displays a single incident summary
 */

import React from 'react';
import { Link } from 'react-router-dom';
import type { Incident } from '../../contracts/gateway';

interface IncidentCardProps {
  incident: Incident;
  showDevice?: boolean;
}

export function IncidentCard({ incident, showDevice = true }: IncidentCardProps) {
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
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
      return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return timestamp;
    }
  };

  return (
    <Link
      to={`/incidents/${incident.id}`}
      className="block bg-gray-800/50 p-4 rounded-lg border border-gray-700 hover:border-[var(--color-primary)] transition-colors hover:bg-gray-800"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Title */}
          <h3 className="text-sm font-semibold text-gray-100 truncate mb-1">
            {incident.title}
          </h3>
          
          {/* Message preview */}
          {incident.message && (
            <p className="text-xs text-gray-400 line-clamp-2 mb-2">
              {incident.message}
            </p>
          )}

          {/* Meta info */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
            {showDevice && (
              <span className="flex items-center gap-1">
                <span>📱</span>
                <span>{incident.device_id}</span>
              </span>
            )}
            <span className="flex items-center gap-1">
              <span>🕐</span>
              <span>{formatTimestamp(incident.timestamp)}</span>
            </span>
          </div>
        </div>

        {/* Badges */}
        <div className="flex flex-col items-end gap-2 shrink-0">
          <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${getSeverityColor(incident.severity)}`}>
            {incident.severity}
          </span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${getStatusColor(incident.status)}`}>
            {incident.status}
          </span>
        </div>
      </div>

      {/* Attribution if acknowledged/resolved */}
      {(incident.acknowledged_by || incident.resolved_by) && (
        <div className="mt-2 pt-2 border-t border-gray-700 text-xs text-gray-500 flex items-center gap-2">
          {incident.acknowledged_by && (
            <span>✅ Acknowledged by {incident.acknowledged_by}</span>
          )}
          {incident.resolved_by && (
            <span>✓ Resolved by {incident.resolved_by}</span>
          )}
        </div>
      )}
    </Link>
  );
}

export default IncidentCard;
