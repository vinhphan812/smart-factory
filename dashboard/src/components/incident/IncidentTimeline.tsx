/**
 * IncidentTimeline - displays the audit trail of an incident
 */

import React from 'react';
import type { IncidentAuditEntry } from '../../contracts/gateway';

interface IncidentTimelineProps {
  auditTrail: IncidentAuditEntry[];
}

const ACTION_ICONS: Record<string, string> = {
  created: '🆕',
  acknowledged: '✅',
  resolved: '✓',
  note_added: '💬',
};

const ACTION_LABELS: Record<string, string> = {
  created: 'Incident Created',
  acknowledged: 'Acknowledged',
  resolved: 'Resolved',
  note_added: 'Note Added',
};

export function IncidentTimeline({ auditTrail }: IncidentTimelineProps) {
  if (!auditTrail || auditTrail.length === 0) {
    return (
      <div className="text-sm text-gray-500 text-center py-4">
        No audit trail available
      </div>
    );
  }

  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="relative">
      {/* Vertical line */}
      <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-700" />
      
      {/* Timeline entries */}
      <div className="space-y-4">
        {auditTrail.map((entry, index) => (
          <div key={entry.id || index} className="relative flex items-start gap-4">
            {/* Icon */}
            <div className="relative z-10 flex items-center justify-center w-8 h-8 rounded-full bg-gray-800 border-2 border-gray-600 text-sm">
              {ACTION_ICONS[entry.action] || '📋'}
            </div>

            {/* Content */}
            <div className="flex-1 bg-gray-800/50 p-3 rounded-lg border border-gray-700">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-200">
                  {ACTION_LABELS[entry.action] || entry.action}
                </span>
                <span className="text-xs text-gray-500 font-mono">
                  {formatTimestamp(entry.timestamp)}
                </span>
              </div>

              {/* Operator attribution */}
              {entry.operator_name && (
                <div className="text-xs text-gray-400 mb-1">
                  by <span className="text-gray-300">{entry.operator_name}</span>
                  {entry.operator_id && (
                    <span className="text-gray-500 ml-1">({entry.operator_id})</span>
                  )}
                </div>
              )}

              {/* Details */}
              {entry.details && (
                <div className="mt-2 p-2 bg-gray-900/50 rounded text-xs text-gray-400">
                  {entry.details}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default IncidentTimeline;
