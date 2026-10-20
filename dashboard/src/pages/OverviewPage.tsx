/**
 * OverviewPage - Factory module overview with status cards
 */

import React, { useState } from 'react';
import { ModuleCard, factoryModules, type FactoryModule } from '../design-system';

type CategoryFilter = 'all' | FactoryModule['category'];

export function OverviewPage() {
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all');
  const [statusFilter, setStatusFilter] = useState<FactoryModule['status'] | 'all'>('all');

  // Filter modules based on selected filters
  const filteredModules = factoryModules.filter((module) => {
    if (categoryFilter !== 'all' && module.category !== categoryFilter) {
      return false;
    }
    if (statusFilter !== 'all' && module.status !== statusFilter) {
      return false;
    }
    return true;
  });

  // Calculate summary stats
  const stats = {
    total: factoryModules.length,
    online: factoryModules.filter((m) => m.status === 'online').length,
    offline: factoryModules.filter((m) => m.status === 'offline').length,
    warning: factoryModules.filter((m) => m.status === 'warning').length,
    error: factoryModules.filter((m) => m.status === 'error').length,
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">
            Factory Overview
          </h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Monitor all 9 factory modules in real-time
          </p>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard
          label="Total Modules"
          value={stats.total}
          icon="📦"
          colorClass="text-[var(--color-text-primary)]"
        />
        <StatCard
          label="Online"
          value={stats.online}
          icon="✅"
          colorClass="text-[var(--color-success)]"
        />
        <StatCard
          label="Offline"
          value={stats.offline}
          icon="⭕"
          colorClass="text-[var(--color-module-offline)]"
        />
        <StatCard
          label="Warning"
          value={stats.warning}
          icon="⚠️"
          colorClass="text-[var(--color-warning)]"
        />
        <StatCard
          label="Error"
          value={stats.error}
          icon="❌"
          colorClass="text-[var(--color-error)]"
        />
      </div>

      {/* Filters */}
      <div className="bg-[var(--color-bg-secondary)] p-4 rounded-xl border border-[var(--color-border)]">
        <div className="flex flex-wrap gap-4 items-center">
          {/* Category Filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="category-filter" className="text-sm font-medium text-[var(--color-text-secondary)]">
              Category:
            </label>
            <select
              id="category-filter"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value as CategoryFilter)}
              className="
                bg-[var(--color-bg-tertiary)] border border-[var(--color-border)]
                rounded-lg px-3 py-1.5 text-sm text-[var(--color-text-primary)]
                focus:outline-none focus:border-[var(--color-primary)]
              "
            >
              <option value="all">All Categories</option>
              <option value="production">Production</option>
              <option value="logistics">Logistics</option>
              <option value="control">Control</option>
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="status-filter" className="text-sm font-medium text-[var(--color-text-secondary)]">
              Status:
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as FactoryModule['status'] | 'all')}
              className="
                bg-[var(--color-bg-tertiary)] border border-[var(--color-border)]
                rounded-lg px-3 py-1.5 text-sm text-[var(--color-text-primary)]
                focus:outline-none focus:border-[var(--color-primary)]
              "
            >
              <option value="all">All Status</option>
              <option value="online">Online</option>
              <option value="offline">Offline</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </select>
          </div>

          {/* Active Filters Indicator */}
          {(categoryFilter !== 'all' || statusFilter !== 'all') && (
            <button
              onClick={() => {
                setCategoryFilter('all');
                setStatusFilter('all');
              }}
              className="
                text-sm text-[var(--color-primary)] hover:text-[var(--color-primary-light)]
                transition-colors
              "
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Module Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredModules.map((module) => (
          <ModuleCard
            key={module.id}
            module={module}
            showStats={true}
            stats={getModuleStats(module)}
          />
        ))}
      </div>

      {/* Empty State */}
      {filteredModules.length === 0 && (
        <div className="text-center py-12">
          <div className="text-4xl mb-4">🔍</div>
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">
            No modules found
          </h3>
          <p className="text-sm text-[var(--color-text-muted)]">
            Try adjusting your filters to see more modules.
          </p>
        </div>
      )}
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: number;
  icon: string;
  colorClass: string;
}

function StatCard({ label, value, icon, colorClass }: StatCardProps) {
  return (
    <div className="bg-[var(--color-bg-secondary)] p-4 rounded-xl border border-[var(--color-border)]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-[var(--color-text-muted)]">{label}</span>
        <span className="text-lg" role="img" aria-label={label}>
          {icon}
        </span>
      </div>
      <div className={`text-3xl font-bold ${colorClass}`}>{value}</div>
    </div>
  );
}

// Generate mock stats for each module type
function getModuleStats(module: FactoryModule): { label: string; value: string | number }[] {
  switch (module.id) {
    case 'conveyor':
      return [
        { label: 'Speed', value: '24 m/min' },
        { label: 'Items/hr', value: 180 },
      ];
    case 'robotic-arm':
      return [
        { label: 'Cycles', value: 142 },
        { label: 'Accuracy', value: '99.8%' },
      ];
    case 'cnc-mill':
      return [
        { label: 'Spindle', value: '12k RPM' },
        { label: 'Feed', value: '800 mm/m' },
      ];
    case 'quality-control':
      return [
        { label: 'Passed', value: 234 },
        { label: 'Failed', value: 3 },
      ];
    case 'storage':
      return [
        { label: 'Items', value: 1247 },
        { label: 'Capacity', value: '87%' },
      ];
    case 'packaging':
      return [
        { label: 'Packages', value: 89 },
        { label: 'Rate', value: '45/hr' },
      ];
    case 'sorting':
      return [
        { label: 'Sorted', value: 312 },
        { label: 'Grade A', value: '78%' },
      ];
    case 'agv':
      return [
        { label: 'Active', value: 3 },
        { label: 'Tasks', value: 12 },
      ];
    case 'control':
      return [
        { label: 'Nodes', value: 24 },
        { label: 'Uptime', value: '99.9%' },
      ];
    default:
      return [];
  }
}

export default OverviewPage;
