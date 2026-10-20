/**
 * TelemetryPage - displays device telemetry charts and metrics
 */

import React, { useState, useEffect } from 'react';
import { TelemetryChart } from '../features/telemetry/components/TelemetryChart';
import { useTelemetryChart } from '../features/telemetry/hooks/useTelemetryChart';
import { useGatewayWs } from '../hooks/useGatewayWs';
import type { DeviceId, TimeRange, AppMode } from '../contracts/gateway';

const DEVICES: DeviceId[] = ['conveyor-01', 'robotic-arm-01', 'cnc-mill-01'];
const TIME_RANGES: TimeRange[] = ['5m', '1h', '24h'];

export function TelemetryPage() {
  const { events, status } = useGatewayWs();
  const [deviceId, _setDeviceId] = useState<DeviceId>('conveyor-01');
  const [timeRange, _setTimeRange] = useState<TimeRange>('5m');
  const [mode, setMode] = useState<AppMode>('demo');

  // Set mode based on connection status
  useEffect(() => {
    if (status === 'connected') {
      setMode('live');
    } else {
      setMode('demo');
    }
  }, [status]);

  const { data, metrics, switchDevice, changeTimeRange } = useTelemetryChart({
    events,
    deviceId,
    timeRange,
    mode,
  });

  const handleDeviceChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    switchDevice(e.target.value as DeviceId);
  };

  const handleTimeRangeChange = (range: TimeRange) => {
    changeTimeRange(range);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Loading state */}
      {status === 'connecting' && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-pulse text-yellow-400 text-sm">Connecting to gateway...</div>
        </div>
      )}

      {/* Offline state */}
      {(status === 'disconnected' || status === 'error') && (
        <div className="flex items-center gap-2 text-sm text-yellow-400 bg-yellow-900/20 border border-yellow-700 rounded-lg px-4 py-2">
          <span>📡</span>
          <span>Gateway offline — showing demo data. Start iot-gateway to see live telemetry.</span>
        </div>
      )}

      {/* Mode indicator */}
      {status !== 'connecting' && (
        <div className="flex items-center gap-2">
          {mode === 'live' && (
            <span className="text-xs bg-green-900/30 text-green-400 px-2 py-1 rounded border border-green-700 font-medium">LIVE</span>
          )}
          {mode === 'demo' && (
            <span className="text-xs bg-yellow-900/30 text-yellow-400 px-2 py-1 rounded border border-yellow-700 font-medium">DEMO</span>
          )}
          {mode === 'simulated' && (
            <span className="text-xs bg-blue-900/30 text-blue-400 px-2 py-1 rounded border border-blue-700 font-medium">SIMULATED</span>
          )}
          {mode === 'replay' && (
            <span className="text-xs bg-purple-900/30 text-purple-400 px-2 py-1 rounded border border-purple-700 font-medium">REPLAY</span>
          )}
          {/* Source timestamp for live mode */}
          {mode === 'live' && events[0]?.ingested_at && (
            <span className="text-xs text-gray-500 font-mono ml-2">
              Latest: {new Date(events[0].ingested_at).toLocaleTimeString()}
            </span>
          )}
        </div>
      )}

      {/* Controls / Time Range Selector */}
      {status !== 'connecting' && (
        <>
          <div className="bg-gray-800 p-4 rounded-xl border border-gray-700 flex flex-wrap justify-between items-center gap-4">
            <div className="flex items-center gap-2">
              <label htmlFor="device-select" className="text-sm font-medium text-gray-300">
                Device:
              </label>
              <select
                id="device-select"
                value={deviceId}
                onChange={handleDeviceChange}
                className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-[var(--color-primary)]"
              >
                {DEVICES.map((dev) => (
                  <option key={dev} value={dev}>
                    {dev}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-300">Time Range:</span>
              <div className="inline-flex rounded-md shadow-sm" role="group">
                {TIME_RANGES.map((range) => (
                  <button
                    key={range}
                    onClick={() => handleTimeRangeChange(range)}
                    className={`px-3 py-1.5 text-xs font-medium rounded transition ${
                      timeRange === range
                        ? 'bg-[var(--color-primary)] text-white'
                        : 'bg-gray-900 text-gray-300 border border-gray-700 hover:bg-gray-700'
                    } ${range === '5m' ? 'rounded-l' : ''} ${range === '24h' ? 'rounded-r' : ''}`}
                  >
                    {range}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Metrics Summary Cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-800 p-4 rounded-xl border border-gray-700">
              <div className="text-xs text-gray-400 font-medium uppercase">Average Rate</div>
              <div className="text-2xl font-bold text-blue-400 mt-1">{metrics.avg.toFixed(1)}</div>
              <div className="text-xs text-gray-500 mt-1">units / min</div>
            </div>
            <div className="bg-gray-800 p-4 rounded-xl border border-gray-700">
              <div className="text-xs text-gray-400 font-medium uppercase">Peak Value</div>
              <div className="text-2xl font-bold text-green-400 mt-1">{metrics.peak.toFixed(1)}</div>
              <div className="text-xs text-gray-500 mt-1">max observed</div>
            </div>
            <div className="bg-gray-800 p-4 rounded-xl border border-gray-700">
              <div className="text-xs text-gray-400 font-medium uppercase">Total Events</div>
              <div className="text-2xl font-bold text-purple-400 mt-1">{metrics.total}</div>
              <div className="text-xs text-gray-500 mt-1">in selected window</div>
            </div>
          </div>

          {/* Telemetry Chart */}
          <TelemetryChart
            deviceId={deviceId}
            timeRange={timeRange}
            data={data}
            isDemo={mode === 'demo'}
          />
        </>
      )}
    </div>
  );
}

export default TelemetryPage;
