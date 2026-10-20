/**
 * IncidentsPage - incident list with filters
 */

import React, { useState } from 'react';
import { useIncidents } from '../../hooks/incidents';
import { IncidentCard } from '../../components/incident';
import type { Incident, IncidentStatus, IncidentSeverity, DeviceId } from '../../contracts/gateway';

const STATUS_OPTIONS: { value: IncidentStatus | ''; label: string }[] = [
  { value: '', label: 'All Status' },
  { value: 'open', label: 'Open' },
  { value: 'acknowledged', label: 'Acknowledged' },
  { value: 'resolved', label: 'Resolved' },
];

const SEVERITY_OPTIONS: { value: IncidentSeverity | ''; label: string }[] = [
  { value: '', label: 'All Severities' },
  { value: 'CRITICAL', label: 'Critical' },
  { value: 'WARNING', label: 'Warning' },
  { value: 'INFO', label: 'Info' },
];

const DEVICE_OPTIONS: { value: DeviceId | ''; label: string }[] = [
  { value: '', label: 'All Devices' },
  { value: 'conveyor-01', label: 'Conveyor 01' },
  { value: 'robotic-arm-01', label: 'Robotic Arm 01' },
  { value: 'cnc-mill-01', label: 'CNC Mill 01' },
];

export function IncidentsPage() {
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | ''>('');
  const [severityFilter, setSeverityFilter] = useState<IncidentSeverity | ''>('');
  const [deviceFilter, setDeviceFilter] = useState<DeviceId | ''>('');
  const [autoRefresh, setAutoRefresh] = useState(false);

  const { incidents, loading, error, refetch } = useIncidents({
    status: statusFilter || undefined,
    severity: severityFilter || undefined,
    deviceId: deviceFilter || undefined,
    autoRefresh,
    refreshInterval: 30000,
  });

  // Stats
  const openCount = incidents.filter((i) => i.status === 'open').length;
  const acknowledgedCount = incidents.filter((i) => i.status === 'acknowledged').length;
  const resolvedCount = incidents.filter((i) => i.status === 'resolved').length;
  const criticalCount = incidents.filter((i) => i.severity === 'CRITICAL' && i.status !== 'resolved').length;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Incident Management</h1>
          <p className="text-sm text-gray-400 mt-1">
            Track and manage factory incidents with full audit trail
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Live stats */}
          <div className="flex items-center gap-3 text-sm">
            {criticalCount > 0 && (
              <span className="px-2 py-1 bg-red-900/50 border border-red-700 rounded text-red-300">
                🔴 {criticalCount} Critical
              </span>
            )}
            <span className="px-2 py-1 bg-orange-900/50 border border-orange-700 rounded text-orange-300">
              🟠 {openCount} Open
            </span>
            <span className="px-2 py-1 bg-blue-900/50 border border-blue-700 rounded text-blue-300">
              🔵 {acknowledgedCount} Acknowledged
            </span>
            <span className="px-2 py-1 bg-green-900/50 border border-green-700 rounded text-green-300">
              ✓ {resolvedCount} Resolved
            </span>
          </div>

          {/* Refresh button */}
          <button
            onClick={() => refetch()}
            className="p-2 bg-gray-800 border border-gray-700 rounded-lg hover:border-gray-600 text-gray-400 hover:text-gray-200 transition-colors"
            title="Refresh"
          >
            🔄
          </button>

          {/* Auto-refresh toggle */}
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
            />
            <span>Auto-refresh</span>
          </label>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-gray-800 p-4 rounded-xl border border-gray-700 flex flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <label htmlFor="filter-status" className="text-sm font-medium text-gray-300">
            Status:
          </label>
          <select
            id="filter-status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as IncidentStatus | '')}
            className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-[var(--color-primary)]"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="filter-severity" className="text-sm font-medium text-gray-300">
            Severity:
          </label>
          <select
            id="filter-severity"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value as IncidentSeverity | '')}
            className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-[var(--color-primary)]"
          >
            {SEVERITY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="filter-device" className="text-sm font-medium text-gray-300">
            Device:
          </label>
          <select
            id="filter-device"
            value={deviceFilter}
            onChange={(e) => setDeviceFilter(e.target.value as DeviceId | '')}
            className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-[var(--color-primary)]"
          >
            {DEVICE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-sm text-red-300">
          <span className="font-medium">Error loading incidents:</span> {error}
          <button
            onClick={() => refetch()}
            className="ml-4 text-red-200 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Incident list */}
      <div className="bg-gray-800 p-5 rounded-xl border border-gray-700">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin text-3xl">⏳</div>
            <span className="ml-3 text-gray-400">Loading incidents...</span>
          </div>
        ) : incidents.length === 0 ? (
          <div className="text-sm text-gray-500 text-center py-12">
            {statusFilter || severityFilter || deviceFilter
              ? 'No incidents match the selected filters.'
              : 'No incidents recorded. The factory is running smoothly! 🎉'}
          </div>
        ) : (
          <div className="space-y-3">
            {incidents.map((incident) => (
              <IncidentCard key={incident.id} incident={incident} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default IncidentsPage;
