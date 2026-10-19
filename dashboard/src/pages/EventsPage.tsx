/**
 * EventsPage - displays unified event timeline with filtering
 */

import React, { useState, useMemo } from 'react';
import { useGatewayEvents } from '../hooks/useGatewayEvents';
import { useGatewayWs } from '../hooks/useGatewayWs';
import type { Severity, DeviceId } from '../contracts/gateway';

const DEVICES: DeviceId[] = ['conveyor-01', 'robotic-arm-01', 'cnc-mill-01'];
const SEVERITIES: Severity[] = ['INFO', 'WARN', 'ERROR', 'CRITICAL'];

export function EventsPage() {
  const { status } = useGatewayWs();
  const [selectedDevice, setSelectedDevice] = useState<DeviceId | ''>('');
  const [selectedSeverity, setSelectedSeverity] = useState<Severity | ''>('');

  const events = useGatewayEvents({
    deviceId: selectedDevice || undefined,
    severity: selectedSeverity || undefined,
    limit: 100,
  });

  const getSeverityColor = (severity: Severity): string => {
    switch (severity) {
      case 'INFO':
        return 'bg-blue-900 text-blue-200';
      case 'WARN':
        return 'bg-yellow-900 text-yellow-200';
      case 'ERROR':
        return 'bg-orange-900 text-orange-200';
      case 'CRITICAL':
        return 'bg-red-900 text-red-200';
      default:
        return 'bg-gray-700 text-gray-300';
    }
  };

  const formatTimestamp = (timestamp: string): string => {
    try {
      return new Date(timestamp).toLocaleTimeString();
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-100">Unified Event Timeline</h1>
        <span className="text-sm text-gray-400">{events.length} events</span>
      </div>

      {/* Filters */}
      <div className="bg-gray-800 p-4 rounded-xl border border-gray-700 flex flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <label htmlFor="filter-device" className="text-sm font-medium text-gray-300">
            Device:
          </label>
          <select
            id="filter-device"
            value={selectedDevice}
            onChange={(e) => setSelectedDevice(e.target.value as DeviceId | '')}
            className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-[var(--color-primary)]"
          >
            <option value="">All Devices</option>
            {DEVICES.map((dev) => (
              <option key={dev} value={dev}>
                {dev}
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
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value as Severity | '')}
            className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-[var(--color-primary)]"
          >
            <option value="">All Severities</option>
            {SEVERITIES.map((sev) => (
              <option key={sev} value={sev}>
                {sev}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Event Timeline */}
      <div className="bg-gray-800 p-5 rounded-xl border border-gray-700">
        {events.length === 0 ? (
          <div className="text-sm text-gray-500 text-center py-8">
            {status === 'connected' ? 'No events matching filter.' : 'Waiting for gateway events...'}
          </div>
        ) : (
          <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
            {events.map((event, index) => (
              <div
                key={event.event_id || `event-${index}`}
                className="bg-gray-900 p-3 rounded-lg border border-gray-700 text-xs space-y-1"
              >
                <div className="flex justify-between items-center">
                  <span className="font-bold text-gray-200">{event.device_id}</span>
                  <span className={`px-2 py-0.5 rounded font-mono text-[10px] ${getSeverityColor(determineSeverity(event))}`}>
                    {determineSeverity(event)}
                  </span>
                </div>
                <div className="text-gray-400 flex justify-between">
                  <span>
                    Type: <strong className="text-gray-300">{event.event_type}</strong>
                  </span>
                  <span className="font-mono text-[10px] text-gray-500">
                    {formatTimestamp(event.ingested_at)}
                  </span>
                </div>
                {event.trace_id && (
                  <div className="text-gray-400 font-mono text-[10px] truncate">
                    Trace ID: {event.trace_id}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function determineSeverity(event: { event_type: string; payload?: { status?: string } }): Severity {
  if (event.event_type === 'status_offline') {
    return 'WARN';
  }
  if (event.event_type === 'command_ack') {
    if (event.payload?.status === 'error') {
      return 'ERROR';
    }
  }
  if (event.event_type === 'error') {
    return 'ERROR';
  }
  return 'INFO';
}

export default EventsPage;
