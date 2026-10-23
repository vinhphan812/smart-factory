/**
 * FactoryModulesPage - Comprehensive 9-module factory monitoring page
 * 
 * Supports search input, state filter tabs, favorites toggle & filter,
 * column density controls, and 360/768/1440px responsive CSS grid.
 */

import React, { useState, useMemo, useEffect } from 'react';
import { MODULE_DEFINITIONS, deriveModuleState, findModule, type VisualState } from '../contracts/modules';
import { ModuleCard } from '../design-system';
import { useGatewayStore, useOperationalMode } from '../store/gatewayStore';

type StateFilter = 'ALL' | VisualState;
type DensityMode = 'compact' | 'normal' | 'spacious';
type ColumnDensity = 2 | 3 | 4;

export function FactoryModulesPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [stateFilter, setStateFilter] = useState<StateFilter>('ALL');
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [favorites, setFavorites] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('smart_factory_module_favorites');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [density, setDensity] = useState<DensityMode>('normal');
  const [columnCols, setColumnCols] = useState<ColumnDensity>(3);

  // Track current time for stale detection — re-evaluates on every tick so an idle
  // device can never appear fresh indefinitely (review finding 4).
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(timer);
  }, []);

  // Operational mode (live vs demo/simulated)
  const operationalMode = useOperationalMode();

  // Get live devices from gateway store
  const devicesMap = useGatewayStore((state) => state.devices);
  const statuses = useMemo(() => {
    return Array.from(devicesMap.values()).map((d) => ({
      device_id: d.deviceId,
      status: d.status,
      state: d.state,
      last_heartbeat_at: d.lastSeen ?? undefined,
    }));
  }, [devicesMap]);

  // Toggle favorite
  const handleToggleFavorite = (moduleId: string) => {
    setFavorites((prev) => {
      const next = prev.includes(moduleId)
        ? prev.filter((id) => id !== moduleId)
        : [...prev, moduleId];
      try {
        localStorage.setItem('smart_factory_module_favorites', JSON.stringify(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };

  // Compute states for all modules.
  // `now` is a dependency so the staleness verdict re-evaluates on every clock tick
  // even when the gateway store has not changed (review finding 4).
  const moduleStates = useMemo(() => {
    return MODULE_DEFINITIONS.map((mod) => {
      const derived = deriveModuleState(mod, statuses, {
        now,
        provenance: operationalMode === 'live' ? 'live' : 'simulated',
      });
      return {
        module: mod,
        visualState: (derived?.visualState || 'UNKNOWN') as VisualState,
        lastSeen: derived?.lastSeen,
      };
    });
  }, [statuses, now, operationalMode]);

  // Filter modules
  const filteredModules = useMemo(() => {
    return moduleStates.filter(({ module, visualState }) => {
      // Search query filter (name, id, role, moduleType)
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = module.name.toLowerCase().includes(q);
        const matchesId = module.moduleId.toLowerCase().includes(q);
        const matchesRole = module.role.toLowerCase().includes(q);
        const matchesType = module.moduleType.toLowerCase().includes(q);
        if (!matchesName && !matchesId && !matchesRole && !matchesType) {
          return false;
        }
      }

      // State filter
      if (stateFilter !== 'ALL' && visualState !== stateFilter) {
        return false;
      }

      // Favorites filter
      if (favoritesOnly && !favorites.includes(module.moduleId)) {
        return false;
      }

      return true;
    });
  }, [moduleStates, searchQuery, stateFilter, favoritesOnly, favorites]);

  // Summary counts across all 9 modules
  const counts = useMemo(() => {
    const res = {
      ALL: MODULE_DEFINITIONS.length,
      RUNNING: 0,
      SIMULATED: 0,
      FAULT: 0,
      STALE: 0,
      OFFLINE: 0,
      UNKNOWN: 0,
    };
    for (const { visualState } of moduleStates) {
      if (res[visualState] !== undefined) {
        res[visualState]++;
      }
    }
    return res;
  }, [moduleStates]);

  /**
   * Per-module stat rows.
   *
   * Review finding 1 (P0): hard-coded sample measurements (24 m/min, 92% battery,
   * Stock 450 ...) were rendered as if they were real monitoring values. The dashboard
   * has no verified per-device telemetry source yet, so every numeric cell must be N/A
   * until the gateway supplies a measurement. Only sourced, non-numeric facts are shown.
   */
  const getStats = (moduleId: string) => {
    const definition = findModule(moduleId);
    const hasTelemetry = definition?.hasTelemetry !== false;
    return [
      { label: 'Controller source', value: definition?.controllerSource ?? 'N/A' },
      { label: 'Measurement', value: hasTelemetry ? 'N/A (no telemetry source)' : 'N/A (no sensors)' },
    ];
  };

  // Grid column class mapper
  const gridColumnClass = {
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4',
  }[columnCols];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">
              Factory Modules Matrix
            </h1>
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${
                operationalMode === 'live'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${operationalMode === 'live' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              {operationalMode === 'live' ? 'LIVE GATEWAY (L2 Telemetry)' : 'OFFLINE SIMULATION / DEMO (L0/L2 Mock)'}
            </span>
          </div>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Real-time monitoring and control of all 9 physical mini-factory modules
          </p>
        </div>

        {/* Density & Column Controls */}
        <div className="flex flex-wrap items-center gap-3 bg-[var(--color-bg-secondary)] p-2 rounded-xl border border-[var(--color-border)]">
          <div className="flex items-center gap-1 text-xs text-[var(--color-text-secondary)]">
            <span className="font-medium mr-1">Density:</span>
            {(['compact', 'normal', 'spacious'] as DensityMode[]).map((d) => (
              <button
                key={d}
                onClick={() => setDensity(d)}
                className={`px-2 py-1 rounded capitalize transition-colors ${
                  density === d
                    ? 'bg-[var(--color-primary)] text-white font-medium'
                    : 'hover:bg-[var(--color-bg-tertiary)] text-[var(--color-text-muted)]'
                }`}
              >
                {d}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-[var(--color-border)] hidden sm:block" />

          <div className="flex items-center gap-1 text-xs text-[var(--color-text-secondary)]">
            <span className="font-medium mr-1">Columns:</span>
            {([2, 3, 4] as ColumnDensity[]).map((c) => (
              <button
                key={c}
                onClick={() => setColumnCols(c)}
                className={`w-7 h-7 rounded flex items-center justify-center transition-colors ${
                  columnCols === c
                    ? 'bg-[var(--color-primary)] text-white font-bold'
                    : 'bg-[var(--color-bg-tertiary)] hover:bg-[var(--color-border)] text-[var(--color-text-primary)]'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-[var(--color-bg-secondary)] p-4 rounded-xl border border-[var(--color-border)] space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Search Input */}
          <div className="relative flex-1 max-w-md">
            <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-[var(--color-text-muted)]">
              🔍
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, ID, role, or type..."
              className="w-full pl-10 pr-4 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-primary)] transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-xs text-[var(--color-text-muted)] hover:text-white"
              >
                Clear
              </button>
            )}
          </div>

          {/* Favorites Toggle Filter */}
          <button
            onClick={() => setFavoritesOnly(!favoritesOnly)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors border ${
              favoritesOnly
                ? 'bg-yellow-900/40 border-yellow-600 text-yellow-300'
                : 'bg-[var(--color-bg-tertiary)] border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-white'
            }`}
          >
            <span className={favoritesOnly ? 'text-yellow-400' : 'text-[var(--color-text-muted)]'}>⭐</span>
            Favorites ({favorites.length})
          </button>
        </div>

        {/* State Filter Tabs */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[var(--color-border)]">
          <span className="text-xs font-semibold uppercase text-[var(--color-text-muted)] mr-2">
            State Filter:
          </span>
          {(['ALL', 'RUNNING', 'SIMULATED', 'FAULT', 'STALE', 'OFFLINE', 'UNKNOWN'] as StateFilter[]).map((state) => {
            const count = counts[state as keyof typeof counts];
            const isActive = stateFilter === state;
            return (
              <button
                key={state}
                onClick={() => setStateFilter(state)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                  isActive
                    ? 'bg-[var(--color-primary)] text-white shadow-md'
                    : 'bg-[var(--color-bg-tertiary)] text-[var(--color-text-secondary)] hover:bg-[var(--color-border)] hover:text-white'
                }`}
              >
                <span>{state}</span>
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${isActive ? 'bg-white/20 text-white' : 'bg-black/30 text-[var(--color-text-muted)]'}`}>
                  {count}
                </span>
              </button>
            );
          })}

          {(stateFilter !== 'ALL' || searchQuery || favoritesOnly) && (
            <button
              onClick={() => {
                setStateFilter('ALL');
                setSearchQuery('');
                setFavoritesOnly(false);
              }}
              className="ml-auto text-xs text-[var(--color-primary)] hover:text-[var(--color-primary-light)] font-medium transition-colors"
            >
              Reset all filters
            </button>
          )}
        </div>
      </div>

      {/* Modules Grid (Responsive 360/768/1440px) */}
      <div className={`grid ${gridColumnClass} gap-4`}>
        {filteredModules.map(({ module, visualState, lastSeen }) => (
          <ModuleCard
            key={module.moduleId}
            module={module}
            visualState={visualState}
            lastSeen={lastSeen}
            isFavorite={favorites.includes(module.moduleId)}
            onToggleFavorite={handleToggleFavorite}
            showStats={density !== 'compact'}
            stats={getStats(module.moduleId)}
            density={density}
          />
        ))}
      </div>

      {/* Empty State */}
      {filteredModules.length === 0 && (
        <div className="text-center py-16 bg-[var(--color-bg-secondary)] rounded-2xl border border-[var(--color-border)]">
          <div className="text-4xl mb-3">🔍</div>
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-1">
            No matching modules found
          </h3>
          <p className="text-sm text-[var(--color-text-muted)] max-w-md mx-auto mb-4">
            No modules match your current search query or filter criteria. Try adjusting your filters or clearing search.
          </p>
          <button
            onClick={() => {
              setStateFilter('ALL');
              setSearchQuery('');
              setFavoritesOnly(false);
            }}
            className="px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:bg-[var(--color-primary-dark)] transition-colors"
          >
            Clear Filters
          </button>
        </div>
      )}
    </div>
  );
}

export default FactoryModulesPage;
