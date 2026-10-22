/**
 * AppRoutes - Central route table for Smart Factory operator dashboard
 *
 * Implements SPEC-2 application navigation destinations:
 * - Overview (/)
 * - Factory Modules (/modules)
 * - Module Detail (/modules/:moduleId)
 * - Production (/production) [Reserved]
 * - Telemetry (/telemetry)
 * - Events (/events)
 * - Incidents (/incidents, /incidents/:incidentId)
 * - Commands (/commands) [Gated / Read-only]
 * - Devices (/devices) [Reserved]
 * - System Health (/health) [Reserved]
 * - Reports (/reports) [Reserved]
 * - Settings (/settings) [Reserved]
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { OverviewPage } from '../pages/OverviewPage';
import { FactoryModulesPage } from '../pages/FactoryModulesPage';
import { ModuleDetailPage } from '../pages/ModuleDetailPage';
import { TelemetryPage } from '../pages/TelemetryPage';
import { EventsPage } from '../pages/EventsPage';
import { IncidentsPage, IncidentDetailPage } from '../pages/incidents';

/**
 * Reserved placeholder view for planned routes with explicit safety/status notices
 */
const ReservedPage: React.FC<{
  title: string;
  icon: string;
  statusNote: string;
  safetyNotice?: string;
}> = ({ title, icon, statusNote, safetyNotice }) => (
  <div className="max-w-4xl mx-auto py-12 px-4 space-y-6">
    <div className="bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl p-8 space-y-4">
      <div className="text-4xl">{icon}</div>
      <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">{title}</h1>
      <p className="text-[var(--color-text-secondary)] text-sm leading-relaxed">
        {statusNote}
      </p>
      {safetyNotice && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-200">
          <strong className="text-amber-100 block mb-1">Safety Policy (TC-4):</strong>
          {safetyNotice}
        </div>
      )}
    </div>
  </div>
);

export function AppRoutes(): React.JSX.Element {
  return (
    <Routes>
      <Route path="/" element={<OverviewPage />} />
      <Route path="/modules" element={<FactoryModulesPage />} />
      <Route path="/modules/:moduleId" element={<ModuleDetailPage />} />
      <Route path="/telemetry" element={<TelemetryPage />} />
      <Route path="/events" element={<EventsPage />} />
      <Route path="/incidents" element={<IncidentsPage />} />
      <Route path="/incidents/:incidentId" element={<IncidentDetailPage />} />

      {/* SPEC-2 Reserved / Gated destinations */}
      <Route
        path="/production"
        element={
          <ReservedPage
            title="Production Analytics"
            icon="📈"
            statusNote="Production metrics, throughput tracking, and KPI targets are scheduled for implementation in issue #151."
          />
        }
      />
      <Route
        path="/commands"
        element={
          <ReservedPage
            title="Module Commands & Actuation"
            icon="🎮"
            statusNote="Hardware command dispatch requires an authenticated operator session and backend safety gates (issues #152 and #154)."
            safetyNotice="The browser operator dashboard is strictly read-only and has no actuation endpoints. Physical hardware actuation requires an authenticated operator session and backend safety gates (issues #152 and #154). Web clients cannot directly dispatch actuator or PLC commands."
          />
        }
      />
      <Route
        path="/devices"
        element={
          <ReservedPage
            title="Device Inventory"
            icon="📱"
            statusNote="Hardware provisioning, firmware flashing status, and device registry management are scheduled in issue #155."
          />
        }
      />
      <Route
        path="/health"
        element={
          <ReservedPage
            title="System Health & Infrastructure"
            icon="💚"
            statusNote="Gateway service health is continuously monitored at GET /health. A dedicated infrastructure health view is tracked in issue #156."
          />
        }
      />
      <Route
        path="/reports"
        element={
          <ReservedPage
            title="Automated Reports"
            icon="📄"
            statusNote="Shift reports, incident summaries, and compliance export workflows are planned for a subsequent dashboard wave."
          />
        }
      />
      <Route
        path="/settings"
        element={
          <ReservedPage
            title="Operator Settings"
            icon="⚙️"
            statusNote="User preferences, theme customization, and notification rules are planned for a subsequent dashboard wave."
          />
        }
      />

      {/* Catch-all redirect to overview */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default AppRoutes;
