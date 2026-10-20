/**
 * ModuleCard component - Design System
 * 
 * Displays a factory module with status indicator, icon, and quick stats.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import type { FactoryModule } from './tokens';

type ModuleStatus = 'online' | 'offline' | 'warning' | 'error' | 'unknown';

interface ModuleCardProps {
  module: FactoryModule;
  className?: string;
  showStats?: boolean;
  stats?: {
    label: string;
    value: string | number;
    trend?: 'up' | 'down' | 'neutral';
  }[];
}

const statusConfig: Record<ModuleStatus, { color: string; bgColor: string; label: string }> = {
  online: {
    color: 'text-[var(--color-success)]',
    bgColor: 'bg-[var(--color-success-alpha)]',
    label: 'Online',
  },
  offline: {
    color: 'text-[var(--color-module-offline)]',
    bgColor: 'bg-gray-900/50',
    label: 'Offline',
  },
  warning: {
    color: 'text-[var(--color-warning)]',
    bgColor: 'bg-[var(--color-warning-alpha)]',
    label: 'Warning',
  },
  error: {
    color: 'text-[var(--color-error)]',
    bgColor: 'bg-[var(--color-error-alpha)]',
    label: 'Error',
  },
  unknown: {
    color: 'text-[var(--color-text-muted)]',
    bgColor: 'bg-gray-900/50',
    label: 'Unknown',
  },
};

export function ModuleCard({
  module,
  className = '',
  showStats = false,
  stats = [],
}: ModuleCardProps) {
  const status: ModuleStatus = module.status || 'unknown';

  return (
    <Link
      to={module.path}
      className={`
        group block p-4 rounded-xl
        bg-[var(--color-bg-secondary)] border border-[var(--color-border)]
        hover:border-[var(--color-border-light)]
        hover:shadow-lg hover:shadow-black/20
        transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 focus:ring-offset-[var(--color-bg-primary)]
        ${className}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[var(--color-bg-tertiary)] flex items-center justify-center text-xl">
            {module.icon}
          </div>
          <div>
            <h3 className="font-semibold text-[var(--color-text-primary)] group-hover:text-white transition-colors">
              {module.name}
            </h3>
            <p className="text-xs text-[var(--color-text-muted)]">
              {module.shortName}
            </p>
          </div>
        </div>
        <StatusIndicator status={status} />
      </div>

      {/* Description */}
      <p className="text-sm text-[var(--color-text-secondary)] mb-3">
        {module.description}
      </p>

      {/* Stats */}
      {showStats && stats.length > 0 && (
        <div className="grid grid-cols-2 gap-2 pt-3 border-t border-[var(--color-border)]">
          {stats.map((stat, index) => (
            <div key={index} className="text-center">
              <div className="text-lg font-bold text-[var(--color-text-primary)]">
                {stat.value}
              </div>
              <div className="text-xs text-[var(--color-text-muted)]">
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Category badge */}
      <div className="mt-3 flex items-center gap-2">
        <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-bg-tertiary)] text-[var(--color-text-muted)] capitalize">
          {module.category}
        </span>
      </div>
    </Link>
  );
}

interface StatusIndicatorProps {
  status: ModuleStatus;
  showLabel?: boolean;
  size?: 'sm' | 'md';
}

export function StatusIndicator({
  status,
  showLabel = false,
  size = 'sm',
}: StatusIndicatorProps) {
  const config = statusConfig[status];
  const dotSize = size === 'sm' ? 'w-2 h-2' : 'w-3 h-3';

  return (
    <div className={`flex items-center gap-1.5 ${config.bgColor} px-2 py-1 rounded-full`}>
      <span className={`${dotSize} rounded-full ${config.color} animate-pulse-slow`}
        style={{ backgroundColor: 'currentColor' }}
      />
      {showLabel && (
        <span className={`text-xs font-medium ${config.color}`}>
          {config.label}
        </span>
      )}
    </div>
  );
}

export default ModuleCard;
