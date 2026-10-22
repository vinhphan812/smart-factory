/**
 * Sidebar - Main navigation sidebar with 9-module overview (SPEC-2, SPEC-4)
 */

import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { MODULE_DEFINITIONS, type ModuleDefinition } from '../contracts/modules';

interface SidebarProps {
  className?: string;
  collapsed?: boolean;
  onToggle?: () => void;
}

// Navigation items for all 10 SPEC-2 routes (+ Events)
const mainNavItems: { path: string; label: string; icon: string; badge?: string }[] = [
  { path: '/', label: 'Overview', icon: '🏠' },
  { path: '/modules', label: 'Factory Modules', icon: '🏭' },
  { path: '/production', label: 'Production', icon: '📈' },
  { path: '/telemetry', label: 'Telemetry', icon: '📊' },
  { path: '/events', label: 'Events', icon: '📋' },
  { path: '/incidents', label: 'Incidents', icon: '🚨' },
  { path: '/commands', label: 'Commands', icon: '🎮', badge: 'Gated' },
  { path: '/devices', label: 'Devices', icon: '📱' },
  { path: '/health', label: 'System Health', icon: '💚' },
  { path: '/reports', label: 'Reports', icon: '📄' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
];

const moduleIcons: Record<string, string> = {
  'conveyor-01': '⚙️',
  'sorting-01': '🔀',
  'tower-crane-01': '🏗️',
  'parking-01': '🅿️',
  'forklift-01': '🚜',
  'dump-truck-01': '🚚',
  'packaging-01': '📦',
  'brackets-01': '🔩',
  'combine-01': '🎛️',
};

// Group canonical modules by category
const groupedModules = MODULE_DEFINITIONS.reduce((acc, module) => {
  const cat = module.category || 'production';
  if (!acc[cat]) {
    acc[cat] = [];
  }
  acc[cat].push(module);
  return acc;
}, {} as Record<string, ModuleDefinition[]>);

const categoryLabels: Record<string, string> = {
  production: 'Production',
  logistics: 'Logistics',
  control: 'Control',
};

const categoryIcons: Record<string, string> = {
  production: '🏭',
  logistics: '🚚',
  control: '🎛️',
};

export function Sidebar({ className = '', collapsed = false }: SidebarProps) {
  const [modulesExpanded, setModulesExpanded] = useState(true);

  return (
    <aside
      className={`
        h-full bg-[var(--color-bg-secondary)] border-r border-[var(--color-border)]
        flex flex-col overflow-hidden
        transition-all duration-300 ease-in-out
        ${collapsed ? 'w-16' : 'w-[280px]'}
        ${className}
      `}
    >
      {/* Main Navigation */}
      <nav className="p-3 border-b border-[var(--color-border)] overflow-y-auto max-h-[50%]" aria-label="Main navigation">
        <div className="space-y-0.5">
          {mainNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-[var(--color-primary)] text-white'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-white'
                }`
              }
            >
              <span className="text-base flex-shrink-0" aria-hidden="true">
                {item.icon}
              </span>
              {!collapsed && (
                <div className="flex items-center justify-between flex-1 min-w-0">
                  <span className="font-medium text-xs truncate">{item.label}</span>
                  {item.badge && (
                    <span className="text-[10px] uppercase font-semibold px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      {item.badge}
                    </span>
                  )}
                </div>
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Modules Section */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto">
          <div className="p-3">
            <button
              onClick={() => setModulesExpanded(!modulesExpanded)}
              className="w-full flex items-center justify-between px-2 py-1.5 text-xs font-semibold uppercase text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] transition-colors"
              aria-expanded={modulesExpanded}
            >
              <span>Nine Physical Modules</span>
              <svg
                className={`w-4 h-4 transition-transform ${modulesExpanded ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {modulesExpanded && (
              <div className="mt-1 space-y-3">
                {Object.entries(groupedModules).map(([category, modules]) => (
                  <div key={category}>
                    <div className="flex items-center gap-2 px-2 py-0.5 text-[11px] font-medium text-[var(--color-text-muted)]">
                      <span>{categoryIcons[category]}</span>
                      <span>{categoryLabels[category]}</span>
                    </div>
                    <div className="mt-0.5 space-y-0.5">
                      {modules.map((module) => (
                        <ModuleNavItem key={module.moduleId} module={module} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Footer */}
      {!collapsed && (
        <div className="p-3 border-t border-[var(--color-border)]">
          <div className="text-[11px] text-[var(--color-text-muted)] text-center">
            Smart Factory v0.1.0 • L0–L2
          </div>
        </div>
      )}
    </aside>
  );
}

interface ModuleNavItemProps {
  module: ModuleDefinition;
}

function ModuleNavItem({ module }: ModuleNavItemProps) {
  const icon = moduleIcons[module.moduleId] || '🏭';

  return (
    <NavLink
      to={`/modules/${module.moduleId}`}
      className={({ isActive }) =>
        `flex items-center gap-2 px-2.5 py-1.5 rounded-md transition-colors text-xs ${
          isActive
            ? 'bg-[var(--color-primary-alpha)] text-[var(--color-primary-light)] border-l-2 border-[var(--color-primary)]'
            : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-white'
        }`
      }
    >
      <span className="flex-shrink-0" aria-hidden="true">
        {icon}
      </span>
      <span className="flex-1 truncate">{module.name}</span>
      <span className="text-[10px] font-mono text-[var(--color-text-muted)]">{module.moduleId}</span>
    </NavLink>
  );
}

export default Sidebar;
