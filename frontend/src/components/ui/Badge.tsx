/**
 * InsiEDR Contextual Status Badge
 * ===============================
 *
 * Architectural Role:
 *   Standardized color-coded visual chip indicating risk severity, endpoint online/offline
 *   presence, telemetry collector daemon identities, or neutral metadata.
 */

import React from 'react';
import type { RiskLevel } from '../../types/telemetry';

export interface BadgeProps {
  level?: RiskLevel | string;
  children?: React.ReactNode;
  variant?: 'risk' | 'status' | 'neutral' | 'collector';
  className?: string;
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  level,
  children,
  variant = 'risk',
  className = '',
  size = 'md',
}) => {
  const norm = (level || '').toUpperCase();
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  if (variant === 'status') {
    const isOnline = norm === 'ACTIVE' || norm === 'ONLINE' || norm === 'SUCCESS' || norm === 'READY';
    return (
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-md border ${
          isOnline
            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
            : 'bg-slate-50 text-slate-600 border-slate-200'
        } ${sizeClasses} ${className}`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-emerald-500' : 'bg-slate-400'}`}
        />
        {children || (isOnline ? 'Online' : 'Offline')}
      </span>
    );
  }

  if (variant === 'collector') {
    return (
      <span
        className={`inline-flex items-center font-mono font-medium rounded border bg-slate-100 text-slate-700 border-slate-200 ${sizeClasses} ${className}`}
      >
        {children || level}
      </span>
    );
  }

  if (variant === 'neutral') {
    return (
      <span
        className={`inline-flex items-center font-medium rounded-md border bg-slate-50 text-slate-600 border-slate-200 ${sizeClasses} ${className}`}
      >
        {children || level}
      </span>
    );
  }

  // Risk badges
  let colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (norm === 'CRITICAL') {
    colorClasses = 'bg-rose-50 text-rose-700 border-rose-200 font-semibold';
  } else if (norm === 'HIGH') {
    colorClasses = 'bg-orange-50 text-orange-700 border-orange-200 font-semibold';
  } else if (norm === 'MEDIUM') {
    colorClasses = 'bg-amber-50 text-amber-800 border-amber-200 font-medium';
  }

  return (
    <span
      className={`inline-flex items-center tracking-wide font-sans rounded-md border ${colorClasses} ${sizeClasses} ${className}`}
    >
      {children || norm}
    </span>
  );
};
