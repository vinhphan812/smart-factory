import { useEffect } from 'react';
import {
  useConnectionState,
  useOperationalMode,
  useFilteredEvents,
  useFilteredTelemetry,
  useActiveIncidents,
  useGatewayStore,
} from './store/gatewayStore';
import type { Severity } from './types/gateway';

/** Status badge component */
function StatusBadge({ connected }: { connected: boolean }) {
  return (
    <div
      className={`flex items-center space-x-2 px-3 py-1.5 rounded-full border ${
        connected
          ? 'text-green-400 bg-green-900/30 border-green-700'
          : 'text-yellow-400 bg-yellow-900/30 border-yellow-700'
      }`}
    >
      <span
        className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-green-400' : 'bg-yellow-400 animate-pulse'}`}
      />
      <span className="text-sm font-medium">
        {connected ? 'Gateway Connected' : 'Offline (Demo Mode)'}
      </span>
    </div>
  );
}

/** Time range selector */
function TimeRangeSelector() {
  const timeRange = useGatewayStore((state) => state.timeRange);
  const setTimeRange = useGatewayStore((state) => state.setTimeRange);

  const options: Array<{ value: typeof timeRange; label: string }> = [
    { value: '5m', label: '5m' },
    { value: '1h', label: '1h' },
    { value: '24h', label: '24h' },
  ];

  return (
    <div className="inline-flex rounded-md shadow-sm">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => setTimeRange(opt.value)}
          className={`px-3 py-1.5 text-xs font-medium border border-gray-700 transition ${
            timeRange === opt.value
              ? 'bg-blue-600 text-white'
              : 'bg-gray-900 text-gray-300 hover:bg-gray-800'
          } ${opt.value === '5m' ? 'rounded-l' : ''} ${opt.value === '24h' ? 'rounded-r' : ''}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

/** Event severity badge */
function SeverityBadge({ severity }: { severity: Severity }) {
  const styles: Record<Severity, string> = {
    INFO: 'bg-blue-900 text-blue-200',
    WARN: 'bg-yellow-900 text-yellow-200',
    ERROR: 'bg-orange-900 text-orange-200',
    CRITICAL: 'bg-red-900 text-red-200',
  };

  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${styles[severity]}`}>
      {severity}
    </span>
  );
}

/** Derive severity from event */
function deriveSeverity(event: { event_type: string; payload?: Record<string, unknown> }): Severity {
  if (event.event_type === 'status_offline') return 'WARN';
  if (event.event_type === 'command_ack' && event.payload?.status === 'error') return 'ERROR';
  return 'INFO';
}

/** Event timeline item */
function EventItem({ event }: { event: { event_id: string; device_id: string; event_type: string; ingested_at: string; payload?: Record<string, unknown> } }) {
  const severity = deriveSeverity(event);

  return (
    <div className="bg-gray-900 p-3 rounded-lg border border-gray-700 text-xs space-y-1">
      <div className="flex justify-between items-center">
        <span className="font-bold text-gray-200">{event.device_id}</span>
        <SeverityBadge severity={severity} />
      </div>
      <div className="flex justify-between text-gray-400">
        <span>
          Type: <strong className="text-gray-300">{event.event_type}</strong>
        </span>
        <span className="text-gray-500 text-[10px]">
          {new Date(event.ingested_at).toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}

/** Incident card */
function IncidentCard({
  incident,
  onAck,
  canAck,
}: {
  incident: { id: string; severity: Severity; deviceId: string; title: string; acknowledged: boolean; ackBy: string | null; ackAt: string | null };
  onAck: () => void;
  canAck: boolean;
}) {
  const severityColors: Record<Severity, string> = {
    INFO: 'bg-blue-900 text-blue-200',
    WARN: 'bg-yellow-900 text-yellow-200',
    ERROR: 'bg-orange-900 text-orange-200',
    CRITICAL: 'bg-red-900 text-red-200',
  };

  return (
    <div
      className={`bg-gray-900 p-4 rounded-lg border space-y-2 ${
        incident.acknowledged ? 'border-gray-700 opacity-75' : 'border-red-600'
      }`}
    >
      <div className="flex justify-between items-start">
        <div>
          <span className="font-mono text-xs text-gray-400">{incident.id}</span>
          <h4 className="font-bold text-sm text-gray-100">{incident.title}</h4>
        </div>
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${severityColors[incident.severity]}`}>
          {incident.severity}
        </span>
      </div>
      <div className="text-xs text-gray-400">
        Device: <strong className="text-gray-300">{incident.deviceId}</strong>
      </div>
      <div className="pt-2 border-t border-gray-800">
        {incident.acknowledged ? (
          <div className="text-green-400 font-mono text-[10px]">
            ✓ Acknowledged by {incident.ackBy} at{' '}
            {incident.ackAt && new Date(incident.ackAt).toLocaleTimeString()}
          </div>
        ) : canAck ? (
          <button
            onClick={onAck}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white px-3 py-1 rounded font-medium transition text-sm"
          >
            Acknowledge Incident
          </button>
        ) : (
          <div className="text-gray-500 font-mono text-[10px] text-center">
            Ack disabled in production mode
          </div>
        )}
      </div>
    </div>
  );
}

/** Telemetry chart placeholder */
function TelemetryChart() {
  const telemetry = useFilteredTelemetry();

  return (
    <div className="bg-gray-800 p-5 rounded-xl border border-gray-700">
      <h2 className="text-lg font-semibold text-gray-200 mb-4">Telemetry Stream</h2>
      <div className="h-48 flex items-end justify-around gap-1">
        {telemetry.slice(0, 20).map((point, i) => (
          <div
            key={i}
            className="bg-blue-500/70 hover:bg-blue-400 transition rounded-t"
            style={{ height: `${Math.min(100, (point.value / 100) * 100)}%`, width: '12px' }}
            title={`${point.value} @ ${new Date(point.timestamp).toLocaleTimeString()}`}
          />
        ))}
      </div>
      {telemetry.length === 0 && (
        <div className="h-48 flex items-center justify-center text-gray-500">
          No telemetry data available
        </div>
      )}
    </div>
  );
}

/** Main App component */
function App() {
  const connectionState = useConnectionState();
  const operationalMode = useOperationalMode();
  const events = useFilteredEvents();
  const incidents = useActiveIncidents();
  const initializeFromGateway = useGatewayStore((state) => state.initializeFromGateway);
  const acknowledgeIncident = useGatewayStore((state) => state.acknowledgeIncident);
  const selectedDevice = useGatewayStore((state) => state.selectedDevice);
  const setSelectedDevice = useGatewayStore((state) => state.setSelectedDevice);

  // Initialize connection on mount
  useEffect(() => {
    if (operationalMode === 'demo') {
      initializeFromGateway();
    }
  }, [initializeFromGateway, operationalMode]);

  const isConnected = connectionState === 'connected';
  const canAck = operationalMode === 'demo';

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <span className="text-2xl font-bold tracking-wider text-blue-400">⚡ SMART FACTORY</span>
            <span className="text-xs uppercase bg-blue-900 text-blue-200 px-2.5 py-1 rounded font-semibold">
              Operator Dashboard
            </span>
            {operationalMode === 'demo' && (
              <span className="text-xs uppercase bg-yellow-900 text-yellow-200 px-2.5 py-1 rounded font-semibold">
                DEMO
              </span>
            )}
          </div>
          <StatusBadge connected={isConnected} />
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left/Center column */}
        <section className="lg:col-span-2 space-y-6">
          {/* Controls */}
          <div className="bg-gray-800 p-4 rounded-xl border border-gray-700 flex flex-wrap justify-between items-center gap-4">
            <div className="flex items-center space-x-2">
              <label htmlFor="device-select" className="text-sm font-medium text-gray-300">
                Device:
              </label>
              <select
                id="device-select"
                value={selectedDevice}
                onChange={(e) => setSelectedDevice(e.target.value)}
                className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
              >
                <option value="conveyor-01">conveyor-01</option>
                <option value="robotic-arm-01">robotic-arm-01</option>
                <option value="cnc-mill-01">cnc-mill-01</option>
              </select>
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gray-300">Time Range:</span>
              <TimeRangeSelector />
            </div>
          </div>

          {/* Telemetry chart */}
          <TelemetryChart />

          {/* Event timeline */}
          <div className="bg-gray-800 p-5 rounded-xl border border-gray-700">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-gray-200">Event Timeline</h2>
              <span className="text-sm text-gray-400">{events.length} events</span>
            </div>
            <div className="space-y-3 max-h-64 overflow-y-auto pr-2">
              {events.length === 0 ? (
                <div className="text-sm text-gray-500 text-center py-4">
                  {operationalMode === 'demo'
                    ? 'Waiting for demo data...'
                    : 'Waiting for gateway events...'}
                </div>
              ) : (
                events.slice(0, 50).map((event) => (
                  <EventItem key={event.event_id} event={event} />
                ))
              )}
            </div>
          </div>
        </section>

        {/* Right column - Incidents */}
        <section className="space-y-6">
          <div className="bg-gray-800 p-5 rounded-xl border border-gray-700">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-gray-200">Active Incidents</h2>
              <span className="bg-red-900 text-red-200 text-xs px-2 py-0.5 rounded-full font-bold">
                {incidents.length} Active
              </span>
            </div>
            <div className="space-y-4 max-h-[550px] overflow-y-auto pr-2">
              {incidents.length === 0 ? (
                <div className="bg-gray-900 p-4 rounded-lg border border-gray-700 text-center text-gray-500 text-sm">
                  No active incidents. System healthy.
                </div>
              ) : (
                incidents.map((incident) => (
                  <IncidentCard
                    key={incident.id}
                    incident={incident}
                    onAck={() => acknowledgeIncident(incident.id)}
                    canAck={canAck}
                  />
                ))
              )}
            </div>
          </div>

          {/* System info */}
          <div className="bg-gray-800 p-5 rounded-xl border border-gray-700 space-y-3">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
              System Info
            </h3>
            <div className="text-xs text-gray-400 space-y-1 font-mono">
              <div>Mode: {operationalMode.toUpperCase()}</div>
              <div>Connection: {connectionState}</div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
