/**
 * TelemetryChart component - displays device telemetry using Chart.js
 */

import React, { useRef, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ChartData,
  ChartOptions,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import type { DeviceId, TimeRange } from '../../../../contracts/gateway';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export interface TelemetryChartProps {
  deviceId: DeviceId;
  timeRange: TimeRange;
  data: Array<{ timestamp: string; value: number }>;
  isDemo?: boolean;
  className?: string;
}

export function TelemetryChart({
  deviceId,
  timeRange,
  data,
  isDemo = false,
  className = '',
}: TelemetryChartProps) {
  const chartRef = useRef<ChartJS<'line'>>(null);

  const chartData: ChartData<'line'> = {
    labels: data.map((d) => {
      const date = new Date(d.timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }),
    datasets: [
      {
        label: `${deviceId} Metric${isDemo ? ' (Demo)' : ''}`,
        data: data.map((d) => d.value),
        borderColor: '#60a5fa',
        backgroundColor: 'rgba(96, 165, 250, 0.1)',
        borderWidth: 2,
        tension: 0.3,
        fill: true,
        pointRadius: 3,
        pointHoverRadius: 5,
      },
    ],
  };

  const chartOptions: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: '#1f2937',
        titleColor: '#f3f4f6',
        bodyColor: '#d1d5db',
        borderColor: '#374151',
        borderWidth: 1,
        padding: 12,
        displayColors: false,
        callbacks: {
          label: (context) => `Value: ${(context.parsed.y ?? 0).toFixed(1)}`,
        },
      },
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(55, 65, 81, 0.5)',
        },
        ticks: {
          color: '#9ca3af',
          font: {
            size: 10,
          },
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 8,
        },
      },
      y: {
        grid: {
          color: 'rgba(55, 65, 81, 0.5)',
        },
        ticks: {
          color: '#9ca3af',
          font: {
            size: 10,
          },
        },
        beginAtZero: true,
      },
    },
  };

  // Update chart when data changes
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.update();
    }
  }, [data]);

  return (
    <div className={`bg-gray-800 p-5 rounded-xl border border-gray-700 ${className}`}>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold text-gray-200">Per-Device Telemetry & State Stream</h2>
        <span className="text-xs bg-gray-900 px-2 py-1 rounded text-blue-300">
          {deviceId} | {timeRange}
        </span>
      </div>
      <div className="h-72 relative">
        <Line ref={chartRef} data={chartData} options={chartOptions} />
      </div>
    </div>
  );
}

export default TelemetryChart;
