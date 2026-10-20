/**
 * AppLayout component - main application layout with sidebar and header
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import { StatusBadge } from '../StatusBadge';
import { useGatewayWs } from '../../hooks/useGatewayWs';
import type { ConnectionStatus } from '../../contracts/gateway';

interface AppLayoutProps {
  children: React.ReactNode;
}

const navItems = [
  { path: '/telemetry', label: 'Telemetry', icon: '📊' },
  { path: '/events', label: 'Events', icon: '📋' },
  { path: '/incidents', label: 'Incidents', icon: '🚨' },
];

export function AppLayout({ children }: AppLayoutProps) {
  const { status } = useGatewayWs();

  return (
    <div className="min-h-screen flex flex-col bg-gray-900 text-gray-100">
      {/* Skip to content link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:bg-[var(--color-primary)] focus:text-white focus:px-4 focus:py-2 focus:rounded focus:outline-none focus:ring-2 focus:ring-white"
      >
        Skip to content
      </a>

      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold tracking-wider text-[var(--color-primary)]">⚡ SMART FACTORY</span>
          <span className="text-xs uppercase bg-[var(--color-primary)]/20 text-[var(--color-primary-light)] px-2.5 py-1 rounded font-semibold">
            Operator Dashboard
          </span>
        </div>
        <div className="flex items-center gap-4">
          <StatusBadge status={status as ConnectionStatus} />
        </div>
      </header>

      <div className="flex-1 flex">
        {/* Sidebar */}
        <aside className="w-56 bg-gray-800 border-r border-gray-700 p-4">
          <nav className="space-y-2" aria-label="Dashboard navigation">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                tabIndex={0}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] ${
                    isActive
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                  }`
                }
              >
                <span className="text-lg" aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </aside>

        {/* Main Content */}
        <main id="main-content" className="flex-1 p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

export default AppLayout;
