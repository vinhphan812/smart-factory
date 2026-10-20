/**
 * Hook for managing telemetry chart data
 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import type { DeviceId, TimeRange, GatewayEvent, AppMode } from '../../../contracts/gateway';

export interface TelemetryDataPoint {
  timestamp: string;
  value: number;
}

interface UseTelemetryChartOptions {
  events: GatewayEvent[];
  deviceId: DeviceId;
  timeRange: TimeRange;
  mode: AppMode;
}

export function useTelemetryChart({
  events,
  deviceId,
  timeRange,
  mode,
}: UseTelemetryChartOptions) {
  const [selectedDevice, setSelectedDevice] = useState<DeviceId>(deviceId);
  const [selectedTimeRange, setSelectedTimeRange] = useState<TimeRange>(timeRange);

  // Update state when props change
  useEffect(() => {
    setSelectedDevice(deviceId);
  }, [deviceId]);

  useEffect(() => {
    setSelectedTimeRange(timeRange);
  }, [timeRange]);

  const data = useMemo((): TelemetryDataPoint[] => {
    if (mode === 'demo') {
      // Generate demo data
      return generateDemoData(selectedDevice, selectedTimeRange);
    }

    // Filter real events for the selected device
    const deviceEvents = events.filter(
      (ev) => ev.device_id === selectedDevice && ev.event_type === 'telemetry'
    );

    return deviceEvents.map((ev) => ({
      timestamp: ev.ingested_at,
      value: ev.payload?.value ?? 0,
    }));
  }, [events, selectedDevice, selectedTimeRange, mode]);

  const metrics = useMemo(() => {
    if (data.length === 0) {
      return { avg: 0, peak: 0, total: 0 };
    }

    const values = data.map((d) => d.value);
    const sum = values.reduce((acc, v) => acc + v, 0);
    const avg = sum / values.length;
    const peak = Math.max(...values);
    const total = values.length * 12; // Approximate total events

    return { avg, peak, total };
  }, [data]);

  const switchDevice = useCallback((deviceId: DeviceId) => {
    setSelectedDevice(deviceId);
  }, []);

  const changeTimeRange = useCallback((range: TimeRange) => {
    setSelectedTimeRange(range);
  }, []);

  return {
    data,
    metrics,
    selectedDevice,
    selectedTimeRange,
    switchDevice,
    changeTimeRange,
  };
}

/**
 * Generate demo telemetry data
 */
function generateDemoData(deviceId: DeviceId, timeRange: TimeRange): TelemetryDataPoint[] {
  const pointsCount = timeRange === '5m' ? 10 : timeRange === '1h' ? 30 : 60;
  const baseValue = deviceId === 'conveyor-01' ? 60 : deviceId === 'robotic-arm-01' ? 45 : 80;
  const data: TelemetryDataPoint[] = [];

  const intervalMs = timeRange === '5m' ? 30000 : 120000;

  for (let i = pointsCount; i >= 0; i--) {
    const timestamp = new Date(Date.now() - i * intervalMs).toISOString();
    const value = parseFloat(
      (baseValue + Math.sin(i + deviceId.length) * 10 + Math.random() * 5).toFixed(1)
    );
    data.push({ timestamp, value });
  }

  return data;
}

export default useTelemetryChart;
