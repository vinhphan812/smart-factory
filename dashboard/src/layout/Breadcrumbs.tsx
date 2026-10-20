/**
 * Breadcrumbs - Navigation breadcrumb component
 */

import React from 'react';
import { Link } from 'react-router-dom';

export interface BreadcrumbItem {
  label: string;
  path: string;
  isCurrent?: boolean;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  className?: string;
  separator?: React.ReactNode;
}

const defaultSeparator = (
  <svg
    className="w-4 h-4 text-[var(--color-text-muted)]"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M9 5l7 7-7 7"
    />
  </svg>
);

export function Breadcrumbs({
  items,
  className = '',
  separator = defaultSeparator,
}: BreadcrumbsProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <nav
      aria-label="Breadcrumb"
      className={`flex items-center gap-1 text-sm ${className}`}
    >
      <ol className="flex items-center gap-1">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          const isFirst = index === 0;

          return (
            <li key={item.path} className="flex items-center gap-1">
              {!isFirst && (
                <span className="text-[var(--color-text-muted)] mx-1">
                  {separator}
                </span>
              )}
              {item.isCurrent || isLast ? (
                <span
                  className={`
                    font-medium
                    ${isFirst ? 'text-[var(--color-text-secondary)]' : 'text-[var(--color-text-primary)]'}
                  `}
                  aria-current={item.isCurrent ? 'page' : undefined}
                >
                  {item.label}
                </span>
              ) : (
                <Link
                  to={item.path}
                  className="
                    text-[var(--color-text-muted)]
                    hover:text-[var(--color-text-secondary)]
                    transition-colors
                  "
                >
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default Breadcrumbs;
