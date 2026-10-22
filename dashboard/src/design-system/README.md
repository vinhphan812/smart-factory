# Smart Factory Design System

Accessible component library and token specification for the Smart Factory operator console (Issue #149).

## Dependency Choice Rationale (SPEC-1)

The dashboard design system relies on **Tailwind CSS utility classes** combined with **CSS Custom Properties (CSS variables)** declared in `tokens.css` and strongly typed constants in `tokens.ts`.

### Why No Heavy External Component Library?
1. **Lightweight & Embedded Ready:** Heavy UI component libraries (MUI, Ant Design, Chakra) introduce hundreds of megabytes of transitive dependencies, client runtime overhead, and complex CSS reset behaviors that conflict with high-performance real-time factory dashboards.
2. **Deterministic Contrast & Accessibility (WCAG 2.2 AA):** All color tokens and text contrast pairings (e.g. `--color-text-primary` on `--color-bg-secondary` yielding > 13:1 contrast) are completely under repo ownership and cannot be broken by third-party library theme updates.
3. **No Decorative Role Impersonation:** In adherence to SPEC-1 and ADR-0011, UI controls never provide cosmetic "role switchers" or fake elevation toggles; permissions and actuation are strictly gated server-side.

## Token Palette

- **Primary:** Linear Lavender `#5E6AD2`, Hover `#4E5AC0`, Active `#434EB0`
- **Backgrounds:** Industrial Dark Canvas `#111827`, Secondary Surface `#1F2937`, Tertiary Surface `#374151`
- **Text:** Primary Text `#F3F4F6`, Secondary Text `#9CA3AF`, Muted `#6B7280`
- **Border:** `#374151`, Light `#4B5563`
- **Status Indicators (SPEC-7):**
  - `RUNNING`: Green `#10B981` / `#065F46`
  - `SIMULATED`: Blue `#3B82F6` / `#1E40AF`
  - `STALE`: Yellow `#F59E0B` / `#78350F`
  - `OFFLINE`: Gray `#6B7280` / `#374151`
  - `FAULT`: Red `#EF4444` / `#7F1D1D`
  - `UNKNOWN`: Purple/Muted `#8B5CF6` / `#4C1D95`

## Core Components

### 1. `ModuleStatusBadge` (SPEC-7)
Renders one of the six canonical visual states with a distinct color dot, border, background tint, explicit textual label, and localized timestamp.
```tsx
import { ModuleStatusBadge } from '../design-system';

<ModuleStatusBadge state="RUNNING" timestamp="2026-10-22T10:00:00Z" />
```

### 2. `ModuleCard` (SPEC-3, SPEC-6)
Card component representing one of the nine physical factory modules with favorites toggle, density modes (`compact`, `normal`, `spacious`), and status indicator.
```tsx
import { ModuleCard } from '../design-system';

<ModuleCard
  module={moduleDefinition}
  visualState="RUNNING"
  isFavorite={false}
  onToggleFavorite={(id) => handleToggle(id)}
/>
```

### 3. `Button` & `Card`
Base accessible buttons and layout container primitives with keyboard focus rings.
