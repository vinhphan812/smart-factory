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
  const [deviceId, setDeviceId] = useState<DeviceId>('conveyor-01');
  const [timeRange, setTimeRange] = useState<TimeRange>('5m');
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
      {/* Controls / Time Range Selector */}
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
    </div>
  );
}

export default TelemetryPage;
