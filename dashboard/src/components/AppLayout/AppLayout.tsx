/**
 * AppLayout component - main application layout with sidebar and header
 *
 * Single-shell reconciliation of #149 (design-system Header/Sidebar with
 * 9-module navigation) and #153 (AppLayout wrapper, StatusBadge, incident
 * routes): AppLayout owns the page frame and delegates the header and the
 * sidebar to the design-system components, so the two features never render
 * competing headers/sidebars.
 */

import React from 'react';
import { Header } from '../../layout/Header';
import { Sidebar } from '../../layout/Sidebar';

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col bg-[var(--color-bg-primary)] text-[var(--color-text-primary)]">
      {/* Skip to content link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:bg-[var(--color-primary)] focus:text-white focus:px-4 focus:py-2 focus:rounded focus:outline-none focus:ring-2 focus:ring-white"
      >
        Skip to content
      </a>

      {/* Header (design system: breadcrumbs + connection status + clock) */}
      <Header />

      <div className="flex-1 flex">
        {/* Sidebar (design system: main routes + 9-module navigation) */}
        <Sidebar />

        {/* Main Content */}
        <main id="main-content" className="flex-1 p-6 overflow-auto" role="main">
          {children}
        </main>
      </div>
    </div>
  );
}

export default AppLayout;
