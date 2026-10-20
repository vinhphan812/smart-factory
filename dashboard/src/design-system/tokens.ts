/**
 * Design System Tokens
 * 
 * This file exports design tokens as TypeScript constants for use in components.
 * The actual CSS custom properties are defined in tokens.css.
 * 
 * Factory aesthetic: Industrial, clean, with high contrast for operator visibility.
 */

// Color palette - Industrial dark theme
export const colors = {
  // Primary - Linear lavender #5E6AD2 (industrial accent)
  primary: '#5E6AD2',
  primaryDark: '#4a55a8',
  primaryLight: '#7b87df',
  
  // Status colors
  success: '#22c55e',
  successDark: '#16a34a',
  warning: '#eab308',
  warningDark: '#ca8a04',
  error: '#ef4444',
  errorDark: '#dc2626',
  critical: '#dc2626',
  
  // Background colors
  bgPrimary: '#111827',
  bgSecondary: '#1f2937',
  bgTertiary: '#374151',
  bgElevated: '#1f2937',
  
  // Text colors
  textPrimary: '#f3f4f6',
  textSecondary: '#d1d5db',
  textMuted: '#9ca3af',
  textInverse: '#111827',
  
  // Border colors
  border: '#374151',
  borderLight: '#4b5563',
  borderFocus: '#5E6AD2',
  
  // Module status colors (for factory modules)
  moduleOnline: '#22c55e',
  moduleOffline: '#6b7280',
  moduleWarning: '#eab308',
  moduleError: '#ef4444',
} as const;

// Spacing scale (matches 4px base grid)
export const spacing = {
  xs: '0.25rem',   // 4px
  sm: '0.5rem',    // 8px
  md: '1rem',      // 16px
  lg: '1.5rem',    // 24px
  xl: '2rem',      // 32px
  xxl: '3rem',     // 48px
} as const;

// Typography scale
export const typography = {
  fontSans: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  fontMono: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
  
  // Font sizes
  textXs: '0.75rem',    // 12px
  textSm: '0.875rem',   // 14px
  textBase: '1rem',     // 16px
  textLg: '1.125rem',   // 18px
  textXl: '1.25rem',    // 20px
  text2xl: '1.5rem',    // 24px
  text3xl: '1.875rem',  // 30px
  text4xl: '2.25rem',   // 36px
  
  // Font weights
  fontLight: 300,
  fontNormal: 400,
  fontMedium: 500,
  fontSemibold: 600,
  fontBold: 700,
} as const;

// Border radius
export const radius = {
  sm: '0.25rem',   // 4px
  md: '0.5rem',    // 8px
  lg: '0.75rem',   // 12px
  xl: '1rem',      // 16px
  full: '9999px',  // Pill shape
} as const;

// Shadows
export const shadows = {
  sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
  lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  xl: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
} as const;

// Transitions
export const transitions = {
  fast: '150ms ease-in-out',
  normal: '200ms ease-in-out',
  slow: '300ms ease-in-out',
} as const;

// Breakpoints (for reference)
export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const;

// Z-index scale
export const zIndex = {
  base: 0,
  dropdown: 100,
  sticky: 200,
  modal: 300,
  tooltip: 400,
  toast: 500,
} as const;

// Factory module definitions
export interface FactoryModule {
  id: string;
  name: string;
  shortName: string;
  description: string;
  icon: string;
  path: string;
  category: 'production' | 'logistics' | 'control';
  status?: 'online' | 'offline' | 'warning' | 'error';
}

export const factoryModules: FactoryModule[] = [
  {
    id: 'conveyor',
    name: 'Conveyor System',
    shortName: 'Conveyor',
    description: 'Material transport and sorting',
    icon: '⚙️',
    path: '/modules/conveyor',
    category: 'logistics',
    status: 'online',
  },
  {
    id: 'robotic-arm',
    name: 'Robotic Arm',
    shortName: 'Robot',
    description: 'Pick and place operations',
    icon: '🦾',
    path: '/modules/robotic-arm',
    category: 'production',
    status: 'online',
  },
  {
    id: 'cnc-mill',
    name: 'CNC Mill',
    shortName: 'CNC',
    description: 'Precision machining',
    icon: '🔩',
    path: '/modules/cnc-mill',
    category: 'production',
    status: 'online',
  },
  {
    id: 'quality-control',
    name: 'Quality Control',
    shortName: 'QC',
    description: 'Visual inspection and testing',
    icon: '🔍',
    path: '/modules/quality-control',
    category: 'production',
    status: 'online',
  },
  {
    id: 'storage',
    name: 'Storage Module',
    shortName: 'Storage',
    description: 'Raw materials and finished goods',
    icon: '📦',
    path: '/modules/storage',
    category: 'logistics',
    status: 'online',
  },
  {
    id: 'packaging',
    name: 'Packaging Station',
    shortName: 'Packaging',
    description: 'Product packaging and labeling',
    icon: '📫',
    path: '/modules/packaging',
    category: 'production',
    status: 'online',
  },
  {
    id: 'sorting',
    name: 'Sorting Module',
    shortName: 'Sorting',
    description: 'Product sorting by grade',
    icon: '🔀',
    path: '/modules/sorting',
    category: 'logistics',
    status: 'online',
  },
  {
    id: 'agv',
    name: 'AGV Transport',
    shortName: 'AGV',
    description: 'Automated guided vehicles',
    icon: '🚚',
    path: '/modules/agv',
    category: 'logistics',
    status: 'online',
  },
  {
    id: 'control',
    name: 'Central Control',
    shortName: 'Control',
    description: 'PLC and system coordination',
    icon: '🎛️',
    path: '/modules/control',
    category: 'control',
    status: 'online',
  },
];

// CSS variable mappings for runtime use
export const cssVariables = {
  colorPrimary: 'var(--color-primary)',
  colorPrimaryDark: 'var(--color-primary-dark)',
  colorPrimaryLight: 'var(--color-primary-light)',
  colorSuccess: 'var(--color-success)',
  colorWarning: 'var(--color-warning)',
  colorError: 'var(--color-error)',
  colorCritical: 'var(--color-critical)',
  colorBgPrimary: 'var(--color-bg-primary)',
  colorBgSecondary: 'var(--color-bg-secondary)',
  colorBgTertiary: 'var(--color-bg-tertiary)',
  colorTextPrimary: 'var(--color-text-primary)',
  colorTextSecondary: 'var(--color-text-secondary)',
  colorTextMuted: 'var(--color-text-muted)',
  colorBorder: 'var(--color-border)',
  colorBorderLight: 'var(--color-border-light)',
  spacingXs: 'var(--spacing-xs)',
  spacingSm: 'var(--spacing-sm)',
  spacingMd: 'var(--spacing-md)',
  spacingLg: 'var(--spacing-lg)',
  spacingXl: 'var(--spacing-xl)',
  radiusSm: 'var(--radius-sm)',
  radiusMd: 'var(--radius-md)',
  radiusLg: 'var(--radius-lg)',
  radiusXl: 'var(--radius-xl)',
  shadowSm: 'var(--shadow-sm)',
  shadowMd: 'var(--shadow-md)',
  shadowLg: 'var(--shadow-lg)',
} as const;
