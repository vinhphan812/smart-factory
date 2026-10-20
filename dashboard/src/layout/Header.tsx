/**
 * Header - Top header with breadcrumbs and status
 */

import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { StatusBadge } from '../components/StatusBadge';
import { useGatewayWs } from '../hooks/useGatewayWs';
import type { ConnectionStatus } from '../contracts/gateway';
import { Breadcrumbs, type BreadcrumbItem } from './Breadcrumbs';

interface HeaderProps {
  className?: string;
  title?: string;
  showBreadcrumbs?: boolean;
}

export function Header({
  className = '',
  title,
  showBreadcrumbs = true,
}: HeaderProps) {
  const { status } = useGatewayWs();
  const location = useLocation();

  // Generate breadcrumbs from current location
  const breadcrumbs: BreadcrumbItem[] = generateBreadcrumbs(location.pathname, title);

  return (
    <header
      className={`
        h-[var(--header-height)] bg-[var(--color-bg-secondary)] border-b border-[var(--color-border)]
        px-6 flex items-center justify-between
        ${className}
      `}
    >
      <div className="flex items-center gap-4">
        {/* Logo */}
        <Link
          to="/"
          className="flex items-center gap-3 hover:opacity-80 transition-opacity"
        >
          <div className="w-8 h-8 rounded-lg bg-[var(--color-primary)] flex items-center justify-center">
            <span className="text-lg">⚡</span>
          </div>
          <div>
            <span className="text-lg font-bold tracking-wide text-[var(--color-primary)]">
              SMART FACTORY
            </span>
            <span className="ml-2 text-xs uppercase bg-[var(--color-primary-alpha)] text-[var(--color-primary-light)] px-2 py-0.5 rounded font-semibold">
              Operator Dashboard
            </span>
          </div>
        </Link>

        {/* Breadcrumbs */}
        {showBreadcrumbs && breadcrumbs.length > 0 && (
          <div className="ml-4">
            <Breadcrumbs items={breadcrumbs} />
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* Current page title */}
        {title && (
          <h1 className="text-lg font-semibold text-[var(--color-text-primary)] hidden md:block">
            {title}
          </h1>
        )}

        {/* Status Badge */}
        <StatusBadge status={status as ConnectionStatus} />

        {/* Time display */}
        <TimeDisplay />
      </div>
    </header>
  );
}

// Generate breadcrumbs from pathname
function generateBreadcrumbs(pathname: string, title?: string): BreadcrumbItem[] {
  const breadcrumbs: BreadcrumbItem[] = [];

  if (pathname === '/' || pathname === '') {
    return breadcrumbs;
  }

  const segments = pathname.split('/').filter(Boolean);

  if (segments.length === 0) {
    return breadcrumbs;
  }

  // Dashboard / Overview
  breadcrumbs.push({
    label: 'Dashboard',
    path: '/',
  });

  // Add current page
  const currentLabel = title || formatSegment(segments[segments.length - 1]);
  breadcrumbs.push({
    label: currentLabel,
    path: pathname,
    isCurrent: true,
  });

  return breadcrumbs;
}

function formatSegment(segment: string): string {
  // Convert kebab-case to Title Case
  return segment
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

// Live time display
function TimeDisplay() {
  const [time, setTime] = React.useState(new Date());

  React.useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="hidden lg:flex items-center gap-2 text-sm text-[var(--color-text-muted)] font-mono">
      <svg
        className="w-4 h-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <span>{time.toLocaleTimeString()}</span>
    </div>
  );
}

export default Header;
