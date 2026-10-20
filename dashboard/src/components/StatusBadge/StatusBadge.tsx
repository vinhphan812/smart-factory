/**
 * StatusBadge component - displays connection status
 */

import type { ConnectionStatus } from '../../contracts/gateway';

interface StatusBadgeProps {
  status: ConnectionStatus;
  className?: string;
}

const statusConfig: Record<ConnectionStatus, { label: string; colorClass: string; dotClass: string }> = {
  connecting: {
    label: 'Connecting...',
    colorClass: 'text-yellow-400 bg-yellow-900/30 border-yellow-600',
    dotClass: 'bg-yellow-400 animate-pulse',
  },
  connected: {
    label: 'Connected',
    colorClass: 'text-green-400 bg-green-900/30 border-green-600',
    dotClass: 'bg-green-400',
  },
  disconnected: {
    label: 'Disconnected',
    colorClass: 'text-yellow-400 bg-yellow-900/30 border-yellow-600',
    dotClass: 'bg-yellow-400 animate-pulse',
  },
  error: {
    label: 'Error',
    colorClass: 'text-red-400 bg-red-900/30 border-red-600',
    dotClass: 'bg-red-400',
  },
};

export function StatusBadge({ status, className = '' }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <div
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm border ${config.colorClass} ${className}`}
      role="status"
      aria-live="polite"
    >
      <span className={`w-2.5 h-2.5 rounded-full ${config.dotClass}`} />
      <span className="font-medium">{config.label}</span>
    </div>
  );
}

export default StatusBadge;
