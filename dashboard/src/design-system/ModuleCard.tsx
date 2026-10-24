/**
 * ModuleCard component - Design System
 * 
 * Displays a factory module with status badge, icon, favorites toggle, and quick stats.
 * Supports compact/normal/spacious density modes.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { ModuleStatusBadge } from './ModuleStatusBadge';
import type { VisualState, ModuleDefinition } from '../contracts/modules';

export interface ModuleCardProps {
  module: ModuleDefinition & {
    icon?: string;
    description?: string;
    category?: string;
    shortName?: string;
  };
  visualState: VisualState;
  lastSeen?: string;
  isFavorite?: boolean;
  onToggleFavorite?: (moduleId: string) => void;
  className?: string;
  showStats?: boolean;
  stats?: { label: string; value: string | number }[];
  density?: 'compact' | 'normal' | 'spacious';
}

// Default metadata for the 9 canonical modules
const MODULE_METADATA: Record<string, { icon: string; description: string; category: string; shortName: string }> = {
  'conveyor-01': { icon: '⚙️', description: 'Material feed conveyor transport', category: 'logistics', shortName: 'Conveyor' },
  'sorting-01': { icon: '🔀', description: 'Classification and routing station', category: 'logistics', shortName: 'Sorting' },
  'tower-crane-01': { icon: '🏗️', description: 'Lift and place mechanical crane', category: 'production', shortName: 'Crane' },
  'parking-01': { icon: '🅿️', description: 'Vehicle staging and parking area', category: 'logistics', shortName: 'Parking' },
  'forklift-01': { icon: '🚜', description: 'Pallet transport forklift AGV', category: 'logistics', shortName: 'Forklift' },
  'dump-truck-01': { icon: '🚚', description: 'Bulk-material delivery dump truck', category: 'logistics', shortName: 'Dump Truck' },
  'packaging-01': { icon: '📦', description: 'Package and seal production station', category: 'production', shortName: 'Packaging' },
  'brackets-01': { icon: '🔩', description: 'Structural support and bracket feed', category: 'production', shortName: 'Brackets' },
  'combine-01': { icon: '🎛️', description: 'Workflow coordinator and PLC hub', category: 'control', shortName: 'Combine' },
};

export function ModuleCard({
  module,
  visualState,
  lastSeen,
  isFavorite = false,
  onToggleFavorite,
  className = '',
  showStats = true,
  stats = [],
  density = 'normal',
}: ModuleCardProps) {
  const meta = MODULE_METADATA[module.moduleId] || {
    icon: '🏭',
    description: module.role || 'Factory module unit',
    category: 'production',
    shortName: module.name,
  };

  const densityPadding = {
    compact: 'p-3',
    normal: 'p-4',
    spacious: 'p-6',
  }[density];

  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (onToggleFavorite) {
      onToggleFavorite(module.moduleId);
    }
  };

  return (
    <Link
      to={`/modules/${module.moduleId}`}
      className={`
        group relative block rounded-xl
        bg-[var(--color-bg-secondary)] border border-[var(--color-border)]
        hover:border-[var(--color-border-light)]
        hover:shadow-xl hover:shadow-black/30
        transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 focus:ring-offset-[var(--color-bg-primary)]
        ${densityPadding}
        ${className}
      `}
    >
      {/* Top action bar: Favorite toggle + Status badge */}
      <div className="flex items-start justify-between mb-3 gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-[var(--color-bg-tertiary)] flex items-center justify-center text-xl flex-shrink-0">
            {meta.icon}
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-[var(--color-text-primary)] group-hover:text-white transition-colors truncate">
              {module.name}
            </h3>
            <p className="text-xs text-[var(--color-text-muted)] font-mono truncate">
              {module.moduleId} • {meta.shortName}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            type="button"
            onClick={handleFavoriteClick}
            className={`p-1.5 rounded-full transition-colors ${
              isFavorite
                ? 'text-yellow-400 bg-yellow-900/30'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)]'
            }`}
            title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
            aria-label="Toggle favorite"
          >
            <svg className="w-4 h-4" fill={isFavorite ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.690h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.690l1.519-4.674z" />
            </svg>
          </button>
          <ModuleStatusBadge visualState={visualState} lastSeen={lastSeen} size="sm" />
        </div>
      </div>

      {/* Description / Role */}
      <p className="text-sm text-[var(--color-text-secondary)] mb-3 line-clamp-2">
        {meta.description} ({module.role})
      </p>

      {/* Stats */}
      {showStats && stats.length > 0 && (
        <div className="grid grid-cols-2 gap-2 pt-3 border-t border-[var(--color-border)]">
          {stats.map((stat, index) => (
            <div key={index} className="text-center bg-[var(--color-bg-tertiary)]/50 p-2 rounded-lg">
              <div className="text-sm font-bold text-[var(--color-text-primary)] font-mono">
                {stat.value}
              </div>
              <div className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Footer Category Badge */}
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="px-2 py-0.5 rounded-full bg-[var(--color-bg-tertiary)] text-[var(--color-text-muted)] capitalize font-medium">
          {meta.category}
        </span>
        <span className="text-[var(--color-primary-light)] font-medium group-hover:underline">
          View Details →
        </span>
      </div>
    </Link>
  );
}

export default ModuleCard;
