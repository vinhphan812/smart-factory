/**
 * ModuleStatusBadge component - Design System
 * 
 * Supports 6 visual states: UNKNOWN, STALE, OFFLINE, SIMULATED, RUNNING, FAULT
 * with explicit labels and optional timezone formatting.
 */

import React from 'react';
import type { VisualState } from '../contracts/modules';

export interface ModuleStatusBadgeProps {
  visualState: VisualState;
  lastSeen?: string | number;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

interface StatusConfigItem {
  label: string;
  color: string;
  bgColor: string;
  dotColor: string;
  pulse?: boolean;
}

const statusConfig: Record<VisualState, StatusConfigItem> = {
  UNKNOWN: {
    label: 'Unknown',
    color: 'text-[var(--color-text-muted, #9ca3af)]',
    bgColor: 'bg-gray-800/50 border-gray-700',
    dotColor: 'bg-gray-500',
  },
  STALE: {
    label: 'Stale',
    color: 'text-[var(--color-warning, #eab308)]',
    bgColor: 'bg-yellow-900/30 border-yellow-700/50',
    dotColor: 'bg-yellow-500',
    pulse: true,
  },
  OFFLINE: {
    label: 'Offline',
    color: 'text-[var(--color-module-offline, #6b7280)]',
    bgColor: 'bg-gray-900/60 border-gray-800',
    dotColor: 'bg-gray-600',
  },
  SIMULATED: {
    label: 'Simulated',
    color: 'text-[var(--color-primary-light, #7b87df)]',
    bgColor: 'bg-blue-900/30 border-blue-700/50',
    dotColor: 'bg-blue-500',
  },
  RUNNING: {
    label: 'Running',
    color: 'text-[var(--color-success, #22c55e)]',
    bgColor: 'bg-green-900/30 border-green-700/50',
    dotColor: 'bg-green-500',
    pulse: true,
  },
  FAULT: {
    label: 'Fault',
    color: 'text-[var(--color-error, #ef4444)]',
    bgColor: 'bg-red-900/30 border-red-700/50',
    dotColor: 'bg-red-500',
    pulse: true,
  },
};

export function ModuleStatusBadge({
  visualState,
  lastSeen,
  showLabel = true,
  size = 'sm',
  className = '',
}: ModuleStatusBadgeProps) {
  const config = statusConfig[visualState] || statusConfig.UNKNOWN;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs gap-1.5',
    md: 'px-2.5 py-1 text-sm gap-2',
    lg: 'px-3 py-1.5 text-base gap-2.5',
  }[size];

  const dotSizes = {
    sm: 'w-2 h-2',
    md: 'w-2.5 h-2.5',
    lg: 'w-3 h-3',
  }[size];

  // Format lastSeen with timezone if provided
  let formattedTime = '';
  if (lastSeen) {
    try {
      const date = typeof lastSeen === 'number' ? new Date(lastSeen) : new Date(lastSeen);
      if (!isNaN(date.getTime())) {
        formattedTime = date.toLocaleTimeString(undefined, {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          timeZoneName: 'short',
        });
      }
    } catch {
      formattedTime = String(lastSeen);
    }
  }

  return (
    <div
      className={`inline-flex items-center rounded-full border font-medium ${config.bgColor} ${config.color} ${sizeClasses} ${className}`}
      title={formattedTime ? `Last seen: ${formattedTime}` : config.label}
      role="status"
    >
      <span
        className={`${dotSizes} rounded-full ${config.dotColor} ${config.pulse ? 'animate-pulse' : ''}`}
      />
      {showLabel && <span>{config.label}</span>}
      {formattedTime && (
        <span className="text-[10px] opacity-75 font-mono ml-1 hidden sm:inline">
          ({formattedTime})
        </span>
      )}
    </div>
  );
}

export default ModuleStatusBadge;
