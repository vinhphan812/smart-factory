/**
 * OverviewPage - Factory module overview with status cards
 */

import React, { useState, useMemo } from 'react';
import { MODULE_DEFINITIONS, deriveModuleState, type VisualState } from '../contracts/modules';
import { ModuleCard } from '../design-system';
import { useGatewayStore } from '../store/gatewayStore';

type CategoryFilter = 'all' | 'production' | 'logistics' | 'control';
type StateFilter = 'all' | VisualState;

export function OverviewPage(): React.JSX.Element {
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StateFilter>('all');

  // Get live devices from gateway store
  const devicesMap = useGatewayStore((state) => state.devices);
  const statuses = useMemo(() => {
    return Array.from(devicesMap.values()).map((d) => ({
      device_id: d.deviceId,
      status: d.status,
      last_heartbeat_at: d.lastSeen ?? undefined,
    }));
  }, [devicesMap]);

  // Derive visual state for each canonical module
  const modulesWithState = useMemo(() => {
    return MODULE_DEFINITIONS.map((module) => {
      const derived = deriveModuleState(module, statuses);
      return {
        module,
        visualState: (derived?.visualState || 'UNKNOWN') as VisualState,
        lastSeen: derived?.lastSeen,
      };
    });
  }, [statuses]);

  // Filter modules based on selected filters
  const filteredModules = useMemo(() => {
    return modulesWithState.filter(({ module, visualState }) => {
      if (categoryFilter !== 'all' && module.category !== categoryFilter) {
        return false;
      }
      if (statusFilter !== 'all' && visualState !== statusFilter) {
        return false;
      }
      return true;
    });
  }, [modulesWithState, categoryFilter, statusFilter]);

  // Calculate summary stats across 6 visual states (SPEC-7)
  const stats = useMemo(() => {
    const counts = {
      total: MODULE_DEFINITIONS.length,
      running: 0,
      simulated: 0,
      stale: 0,
      offline: 0,
      fault: 0,
      unknown: 0,
    };
    for (const item of modulesWithState) {
      const s = item.visualState.toLowerCase() as keyof typeof counts;
      if (s in counts) {
        counts[s]++;
      }
    }
    return counts;
  }, [modulesWithState]);

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

      {/* Summary Stats - 6 canonical visual states (SPEC-7) */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <StatCard
          label="Running"
          value={stats.running}
          icon="🟢"
          colorClass="text-emerald-400"
        />
        <StatCard
          label="Simulated"
          value={stats.simulated}
          icon="🔵"
          colorClass="text-blue-400"
        />
        <StatCard
          label="Stale"
          value={stats.stale}
          icon="🟡"
          colorClass="text-amber-400"
        />
        <StatCard
          label="Offline"
          value={stats.offline}
          icon="⚪"
          colorClass="text-gray-400"
        />
        <StatCard
          label="Fault"
          value={stats.fault}
          icon="🔴"
          colorClass="text-red-400"
        />
        <StatCard
          label="Unknown / N/A"
          value={stats.unknown}
          icon="🟣"
          colorClass="text-purple-400"
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
              onChange={(e) => setStatusFilter(e.target.value as StateFilter)}
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
        {filteredModules.map(({ module, visualState, lastSeen }) => (
          <ModuleCard
            key={module.moduleId}
            module={module}
            visualState={visualState}
            lastSeen={lastSeen}
            showStats={true}
            stats={[
              { label: 'Role', value: module.role },
              { label: 'Unit', value: module.unit || 'N/A' },
            ]}
          />
        ))}
      </div>

      {/* Empty State */}
      {filteredModules.length === 0 && (
        <div className="text-center py-12">
          <div className="text-4xl mb-4">🔍</div>
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">
            No modules match the selected filter
          </h3>
          <p className="text-sm text-[var(--color-text-muted)]">
            Try adjusting your category or status filters.
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
    <div className="bg-[var(--color-bg-secondary)] p-3 rounded-xl border border-[var(--color-border)]">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-[var(--color-text-muted)] truncate">{label}</span>
        <span className="text-sm" role="img" aria-label={label}>
          {icon}
        </span>
      </div>
      <div className={`text-2xl font-bold ${colorClass}`}>{value}</div>
    </div>
  );
}

export default OverviewPage;
