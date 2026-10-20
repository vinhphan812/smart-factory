/**
 * Button component - Design System
 */

import React, { HTMLAttributes } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends HTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  disabled?: boolean;
  fullWidth?: boolean;
  type?: 'button' | 'submit' | 'reset';
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: `
    bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-dark)]
    focus:ring-[var(--color-primary)] border-transparent
  `,
  secondary: `
    bg-[var(--color-bg-tertiary)] text-[var(--color-text-primary)]
    hover:bg-[var(--color-border)] border-[var(--color-border)]
    focus:ring-[var(--color-primary)] border
  `,
  ghost: `
    bg-transparent text-[var(--color-text-secondary)]
    hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]
    focus:ring-[var(--color-primary)] border-transparent
  `,
  danger: `
    bg-[var(--color-error)] text-white hover:bg-[var(--color-error-dark)]
    focus:ring-[var(--color-error)] border-transparent
  `,
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm gap-1.5',
  md: 'px-4 py-2 text-base gap-2',
  lg: 'px-6 py-3 text-lg gap-2.5',
};

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className = '',
  disabled,
  fullWidth = false,
  ...props
}: ButtonProps) {
  const isDisabled = disabled || isLoading;

  return (
    <button
      className={`
        inline-flex items-center justify-center font-medium rounded-lg
        transition-all duration-200 ease-in-out
        focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[var(--color-bg-primary)]
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variantStyles[variant]}
        ${sizeStyles[size]}
        ${className}
        ${fullWidth ? 'w-full' : ''}
      `}
      disabled={isDisabled}
      {...props}
    >
      {isLoading ? (
        <>
          <svg
            className="animate-spin h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <span>Loading...</span>
        </>
      ) : (
        <>
          {leftIcon && <span className="flex-shrink-0">{leftIcon}</span>}
          {children}
          {rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
        </>
      )}
    </button>
  );
}

export default Button;
