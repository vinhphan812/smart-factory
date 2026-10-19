/**
 * Unit tests for TelemetryChart component
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TelemetryChart } from '../features/telemetry/components/TelemetryChart';
import type { DeviceId, TimeRange } from '../contracts/gateway';

// Mock Chart.js to avoid canvas issues in tests
vi.mock('react-chartjs-2', () => ({
  Line: ({ data, options }: { data: unknown; options: unknown }) => (
    <div data-testid="chart" data-data={JSON.stringify(data)} data-options={JSON.stringify(options)}>
      Mock Chart
    </div>
  ),
}));

describe('TelemetryChart', () => {
  const mockData = [
    { timestamp: '2024-01-01T10:00:00Z', value: 50 },
    { timestamp: '2024-01-01T10:01:00Z', value: 55 },
    { timestamp: '2024-01-01T10:02:00Z', value: 52 },
    { timestamp: '2024-01-01T10:03:00Z', value: 58 },
    { timestamp: '2024-01-01T10:04:00Z', value: 60 },
  ];

  it('should render the chart component', () => {
    render(
      <TelemetryChart
        deviceId="conveyor-01"
        timeRange="5m"
        data={mockData}
      />
    );
    
    expect(screen.getByTestId('chart')).toBeInTheDocument();
  });

  it('should display device info in header', () => {
    render(
      <TelemetryChart
        deviceId="conveyor-01"
        timeRange="5m"
        data={mockData}
      />
    );
    
    expect(screen.getByText('conveyor-01 | 5m')).toBeInTheDocument();
  });

  it('should show demo indicator in chart label when in demo mode', () => {
    render(
      <TelemetryChart
        deviceId="conveyor-01"
        timeRange="5m"
        data={mockData}
        isDemo={true}
      />
    );
    
    // Demo indicator is in the chart data, not the header
    const chart = screen.getByTestId('chart');
    const chartData = JSON.parse(chart.getAttribute('data-data') || '{}');
    expect(chartData.datasets[0].label).toContain('(Demo)');
  });

  it('should render with custom className', () => {
    render(
      <TelemetryChart
        deviceId="conveyor-01"
        timeRange="5m"
        data={mockData}
        className="custom-class"
      />
    );
    
    const container = screen.getByTestId('chart').closest('.custom-class');
    expect(container).toBeInTheDocument();
  });

  it('should handle empty data', () => {
    render(
      <TelemetryChart
        deviceId="conveyor-01"
        timeRange="5m"
        data={[]}
      />
    );
    
    expect(screen.getByTestId('chart')).toBeInTheDocument();
  });
});
