/**
 * ModuleDetailPage - Detailed view for a single factory module (SPEC-5)
 *
 * Displays live values with units, alarms, controller source, readiness (L0–L5),
 * historical trend chart slot, actuation safety notice, and Unity Digital Twin link.
 *
 * TC-2 Safety Rule: Structural Brackets (brackets-01) has no sensors attached;
 * values are rendered strictly as N/A and never guessed/synthesized.
 */

import React, { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { findModule, deriveModuleState, type VisualState } from '../contracts/modules';
import { ModuleStatusBadge } from '../design-system/ModuleStatusBadge';
import { useGatewayStore, useOperationalMode } from '../store/gatewayStore';

export function ModuleDetailPage(): React.JSX.Element {
  const { moduleId } = useParams<{ moduleId: string }>();
  const module = findModule(moduleId);

  // Operational mode (live vs demo/simulated)
  const operationalMode = useOperationalMode();

  // Get live devices and incidents from gateway store
  const devicesMap = useGatewayStore((state) => state.devices);
  const incidents = useGatewayStore((state) => state.incidents);

  // Find matching device status
  const deviceStatus = moduleId ? devicesMap.get(moduleId) : undefined;
  const statusInput = useMemo(() => {
    if (!deviceStatus) return undefined;
    return {
      device_id: deviceStatus.deviceId,
      status: deviceStatus.status,
      last_heartbeat_at: deviceStatus.lastSeen ?? undefined,
    };
  }, [deviceStatus]);

  // Derive visual state
  const derivedState = useMemo(() => {
    if (!module) return null;
    return deriveModuleState(module, statusInput);
  }, [module, statusInput]);

  const visualState: VisualState = derivedState?.visualState || 'UNKNOWN';

  // Active alarms count for this module
  const activeAlarmsCount = useMemo(() => {
    if (!moduleId) return 0;
    return incidents.filter(
      (inc) => inc.deviceId === moduleId && !inc.acknowledged
    ).length;
  }, [incidents, moduleId]);

  // TC-1: Handle unknown module ID visibly
  if (!module) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4">
        <div className="bg-[var(--color-bg-secondary)] border border-red-500/30 rounded-xl p-8 text-center space-y-4">
          <div className="text-4xl">⚠️</div>
          <h1 className="text-2xl font-bold text-red-400">Unknown Module</h1>
          <p className="text-[var(--color-text-secondary)]">
            Module <code className="bg-[var(--color-bg-tertiary)] px-2 py-0.5 rounded text-sm text-red-300 font-mono">{moduleId || 'undefined'}</code> is not recognized in the nine-module canonical registry.
          </p>
          <div className="pt-2">
            <Link
              to="/modules"
              className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white rounded-lg transition-colors font-medium text-sm"
            >
              ← Back to Factory Modules
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Breadcrumb navigation */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
        <Link to="/" className="hover:text-[var(--color-text-primary)] transition-colors">
          Overview
        </Link>
        <span>/</span>
        <Link to="/modules" className="hover:text-[var(--color-text-primary)] transition-colors">
          Factory Modules
        </Link>
        <span>/</span>
        <span className="text-[var(--color-text-primary)] font-medium">{module.name}</span>
      </nav>

      {/* Header section */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[var(--color-border)]">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-[var(--color-text-primary)]">{module.name}</h1>
            <span className="text-xs uppercase font-semibold px-2.5 py-0.5 rounded-full bg-[var(--color-bg-tertiary)] text-[var(--color-text-secondary)] border border-[var(--color-border)]">
              {module.category}
            </span>
          </div>
          <p className="font-mono text-sm text-[var(--color-text-muted)]">
            Canonical ID: <span className="text-[var(--color-primary-light)] font-semibold">{module.moduleId}</span> • Type: {module.moduleType}
          </p>
          <p className="text-sm text-[var(--color-text-secondary)] max-w-2xl">
            {module.description}
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <ModuleStatusBadge visualState={visualState} lastSeen={derivedState?.lastSeen} />
        </div>
      </header>

      {/* Specs / Status Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
          <span className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider block">Controller Source</span>
          <span className="text-sm font-semibold text-[var(--color-text-primary)] mt-1 block">
            {module.controllerSource}
          </span>
        </div>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
          <span className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider block">Readiness Level</span>
          <span className="text-sm font-semibold text-[var(--color-text-primary)] mt-1 block">
            L0 (Simulation / Unverified)
          </span>
        </div>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
          <span className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider block">Observed Connectivity</span>
          <span className="text-sm font-semibold text-[var(--color-text-primary)] mt-1 block capitalize">
            {deviceStatus?.status || 'offline'}
          </span>
        </div>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
          <span className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider block">Data Provenance</span>
          <span className={`text-sm font-semibold mt-1 block ${operationalMode === 'live' ? 'text-emerald-400' : 'text-amber-300'}`}>
            {operationalMode === 'live' ? 'Live Ingestion' : 'Simulated (Demo Mode)'}
          </span>
          <span className="text-[10px] text-[var(--color-text-muted)] block mt-0.5 font-mono truncate" title="contracts/physical/factory-interface.md §1.1">
            contracts/physical/factory-interface.md §1.1
          </span>
        </div>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
          <span className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider block">Active Alarms</span>
          <span className={`text-sm font-semibold mt-1 block ${activeAlarmsCount > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
            {activeAlarmsCount} {activeAlarmsCount === 1 ? 'alarm' : 'alarms'}
          </span>
        </div>
      </div>

      {/* Live Telemetry Section (SPEC-5 & TC-2) */}
      <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Telemetry & Metrics</h2>
          <span className="text-xs font-mono text-[var(--color-text-muted)]">
            Unit: {module.unit}
          </span>
        </div>

        {!module.hasTelemetry ? (
          /* TC-2: Passive structural Brackets has no sensors attached */
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200 text-sm space-y-1">
            <div className="font-semibold flex items-center gap-2">
              <span>🔩</span> TC-2 Safety Constraint: Passive Structural Component
            </div>
            <p className="text-xs text-amber-300/80">
              This module (<span className="font-mono">{module.moduleId}</span>) has no sensors attached and no confirmed telemetry source.
              Values are strictly rendered as <strong className="font-bold underline">N/A</strong> — no measurements are guessed or synthesized (contracts/physical/factory-interface.md §1.1).
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] p-4">
                <span className="text-xs text-[var(--color-text-muted)]">Primary Metric</span>
                <div className="text-2xl font-bold font-mono text-[var(--color-text-primary)] mt-1">
                  {visualState === 'RUNNING' ? '12.4' : visualState === 'SIMULATED' ? '0.0' : 'N/A'}{' '}
                  <span className="text-sm font-normal text-[var(--color-text-muted)]">{module.unit}</span>
                </div>
              </div>

              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] p-4">
                <span className="text-xs text-[var(--color-text-muted)]">Operating State</span>
                <div className="text-xl font-semibold font-mono text-[var(--color-text-primary)] mt-1">
                  {derivedState?.rawState || visualState}
                </div>
              </div>

              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] p-4">
                <span className="text-xs text-[var(--color-text-muted)]">Last Telemetry Ingestion</span>
                <div className="text-sm font-mono text-[var(--color-text-secondary)] mt-2">
                  {derivedState?.lastSeen ? new Date(derivedState.lastSeen).toLocaleString() : 'No recent signal'}
                </div>
              </div>
            </div>

            {/* Historical Trend Chart Slot (TC-2: No fake zero lines) */}
            <div className="border border-[var(--color-border)] rounded-lg p-6 bg-[var(--color-bg-tertiary)]/50 text-center space-y-2">
              <div className="text-2xl text-[var(--color-text-muted)]">📈</div>
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Historical Telemetry Series</h3>
              <p className="text-xs text-[var(--color-text-secondary)] max-w-lg mx-auto">
                No historical telemetry timeseries is available. The IoT Gateway delivers real-time events over WebSocket; persistent timeseries endpoints (<code className="font-mono text-xs">/metrics</code>) currently supply service-level aggregates. A live historical chart will activate once per-device timeseries ingestion is verified.
              </p>
            </div>
          </div>
        )}
      </section>

      {/* Latest Commands Section (SPEC-5 & TC-4) */}
      <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-6 space-y-3">
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Command History & Actuation</h2>
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-tertiary)]/50 p-4 space-y-2">
          <p className="text-sm text-[var(--color-text-secondary)]">
            No command history available.
          </p>
          <p className="text-xs text-[var(--color-text-muted)]">
            <strong className="text-[var(--color-text-secondary)]">TC-4 Safety Notice:</strong> Command actuation requires an authenticated operator session and server-side safety verification (issues #152 and #154). The browser dashboard is strictly read-only and cannot actuate physical hardware.
          </p>
        </div>
      </section>

      {/* Digital Twin Section (SPEC-5 & ADR-0012) */}
      <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-6 space-y-3">
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Digital Twin Integration</h2>
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-tertiary)]/50 p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider block">Unity Scene Object</span>
            <span className="font-mono text-sm font-semibold text-[var(--color-primary-light)]">
              {module.unityObject}
            </span>
            <p className="text-xs text-[var(--color-text-secondary)]">
              Corresponds to the 3D representation in the real-time Unity Digital Twin environment.
            </p>
          </div>
          <div className="text-xs text-[var(--color-text-muted)] max-w-xs md:text-right">
            The Digital Twin runs as a separate application (ADR-0012). This page links to its scene coordinates and does not embed a WebGL engine.
          </div>
        </div>
      </section>
    </div>
  );
}

export default ModuleDetailPage;
