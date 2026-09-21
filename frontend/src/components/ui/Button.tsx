/**
 * InsiEDR Interactive Action Button
 * =================================
 *
 * Architectural Role:
 *   Theme-consistent interactive button supporting primary, secondary, danger,
 *   and ghost styling variants with accessible keyboard focus rings, loading spinner
 *   states, and inline SVG iconography.
 */

import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'secondary',
  size = 'md',
  icon,
  isLoading = false,
  className = '',
  disabled,
  ...props
}) => {
  const sizeClasses = {
    sm: 'px-2.5 py-1.5 text-xs font-medium gap-1.5 rounded-md',
    md: 'px-3.5 py-2 text-sm font-medium gap-2 rounded-md',
    lg: 'px-4 py-2.5 text-base font-medium gap-2.5 rounded-lg',
  }[size];

  const variantClasses = {
    primary:
      'bg-slate-900 text-white hover:bg-slate-800 border border-slate-900 shadow-xs focus:ring-2 focus:ring-slate-900 focus:ring-offset-1',
    secondary:
      'bg-white text-slate-700 hover:bg-slate-50 border border-slate-200 shadow-xs hover:border-slate-300 focus:ring-2 focus:ring-slate-400 focus:ring-offset-1',
    danger:
      'bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 focus:ring-2 focus:ring-rose-400 focus:ring-offset-1',
    ghost:
      'bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-transparent',
  }[variant];

  return (
    <button
      className={`inline-flex items-center justify-center transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed select-none outline-none ${sizeClasses} ${variantClasses} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        icon
      )}
      {children}
    </button>
  );
};
