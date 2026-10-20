/**
 * Sidebar - Main navigation sidebar with 9-module overview
 */

import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { factoryModules, type FactoryModule } from '../design-system/tokens';

interface SidebarProps {
  className?: string;
  collapsed?: boolean;
  onToggle?: () => void;
}

// Navigation items for main routes
const mainNavItems = [
  { path: '/', label: 'Overview', icon: '🏠' },
  { path: '/telemetry', label: 'Telemetry', icon: '📊' },
  { path: '/events', label: 'Events', icon: '📋' },
];

// Group modules by category
const groupedModules = factoryModules.reduce((acc, module) => {
  if (!acc[module.category]) {
    acc[module.category] = [];
  }
  acc[module.category].push(module);
  return acc;
}, {} as Record<string, FactoryModule[]>);

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
      <nav className="p-4 border-b border-[var(--color-border)]" aria-label="Main navigation">
        <div className="space-y-1">
          {mainNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-[var(--color-primary)] text-white'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-white'
                }`
              }
            >
              <span className="text-lg flex-shrink-0" aria-hidden="true">
                {item.icon}
              </span>
              {!collapsed && (
                <span className="font-medium text-sm">{item.label}</span>
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Modules Section */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto">
          <div className="p-4">
            <button
              onClick={() => setModulesExpanded(!modulesExpanded)}
              className="w-full flex items-center justify-between px-2 py-2 text-xs font-semibold uppercase text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] transition-colors"
              aria-expanded={modulesExpanded}
            >
              <span>Factory Modules</span>
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
              <div className="mt-2 space-y-4">
                {Object.entries(groupedModules).map(([category, modules]) => (
                  <div key={category}>
                    <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-[var(--color-text-muted)]">
                      <span>{categoryIcons[category]}</span>
                      <span>{categoryLabels[category]}</span>
                    </div>
                    <div className="mt-1 space-y-0.5">
                      {modules.map((module) => (
                        <ModuleNavItem key={module.id} module={module} />
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
        <div className="p-4 border-t border-[var(--color-border)]">
          <div className="text-xs text-[var(--color-text-muted)] text-center">
            Smart Factory v0.1.0
          </div>
        </div>
      )}
    </aside>
  );
}

interface ModuleNavItemProps {
  module: FactoryModule;
}

function ModuleNavItem({ module }: ModuleNavItemProps) {
  const statusColors: Record<string, string> = {
    online: 'bg-[var(--color-success)]',
    offline: 'bg-[var(--color-module-offline)]',
    warning: 'bg-[var(--color-warning)]',
    error: 'bg-[var(--color-error)]',
  };
  const statusColor = statusColors[module.status || 'unknown'] || 'bg-gray-500';

  return (
    <NavLink
      to={module.path}
      className={({ isActive }) =>
        `flex items-center gap-2 px-3 py-2 rounded-md transition-colors text-sm ${
          isActive
            ? 'bg-[var(--color-primary-alpha)] text-[var(--color-primary-light)] border-l-2 border-[var(--color-primary)]'
            : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-white'
        }`
      }
    >
      <span className="flex-shrink-0" aria-hidden="true">
        {module.icon}
      </span>
      <span className="flex-1 truncate">{module.shortName}</span>
      <span className={`w-1.5 h-1.5 rounded-full ${statusColor} flex-shrink-0`} />
    </NavLink>
  );
}

export default Sidebar;
