# ADR-0015: Frontend Migration to React + TypeScript + Vite

**Date:** 2024-10-19
**Status:** Proposed
**Related Issues:** #148

## Context

The Smart Factory dashboard currently exists as a single HTML file (`dashboard/src/index.html`) with embedded vanilla JavaScript and Tailwind CSS via CDN. This approach has served well for rapid prototyping but now needs to scale for:

1. **Type safety** — Contract types between gateway API and frontend are not enforced
2. **Component reuse** — UI patterns duplicated across the single page
3. **Testability** — No unit tests possible with vanilla JS + CDN
4. **Maintainability** — No build-time linting or bundling optimization

## Decision

Migrate the dashboard to **React 18 + TypeScript + Vite** with the following architecture:

### Technology Stack
- **React** 18.3.1 — UI framework
- **TypeScript** — Type safety for gateway contracts
- **Vite** — Fast dev server and optimized production build
- **Chart.js** 4.4.3 — Telemetry visualization (preserved from current implementation)
- **React Router** — Client-side routing for Telemetry and Events pages
- **Vitest** 2.0.4 — Unit testing framework

### Application Architecture
```
dashboard/src/
├── app/             # App entry (main.tsx), root component (App.tsx), providers
├── pages/           # Route pages (TelemetryPage, EventsPage)
├── components/      # Shared UI (AppLayout, StatusBadge)
├── features/        # Feature-specific (TelemetryChart)
├── hooks/           # Custom hooks (useGatewayWs, useGatewayEvents)
├── services/
│   ├── api/        # HTTP client for gateway REST endpoints
│   └── ws/         # WebSocket client (READ-ONLY, no MQTT publish)
├── contracts/      # TypeScript types matching gateway API
├── styles/         # Global CSS with CSS variables
└── tests/          # Unit tests
```

### Security Constraint
The WebSocket client in `services/ws/client.ts` is **READ-ONLY**. It subscribes to telemetry but never initiates physical actuation. A comment explicitly states:
> "SECURITY: READ-ONLY. No MQTT publish. Browser never initiates physical actuation."

## Consequences

- **Positive:**
  - Type safety between gateway API contracts and frontend
  - Component-based architecture enables reuse
  - Unit tests can verify business logic
  - Vite provides fast HMR and optimized builds

- **Negative:**
  - Initial migration effort (~24 files)
  - Team must know React + TypeScript
  - Build step required (not just open HTML file)

## Alternatives Considered

1. **Keep vanilla JS** — Rejected: no type safety, poor testability
2. **Next.js** — Rejected: overkill for SPA with 2 pages
3. **Svelte** — Rejected: team experience with React

## Evidence

- TypeScript compiles without errors (`npm run build` passes)
- All 12 unit tests pass (`npm run test`)
- Production build succeeds with bundled assets (no CDN runtime dependencies)
- Legacy `dashboard/src/index.html` preserved as rollback fallback
- WebSocket client verified READ-ONLY with security comment

### Acceptance Criteria Met

| Criterion | Evidence |
|-----------|----------|
| Type safety | TypeScript strict mode enabled, all types defined |
| Testability | 12 vitest tests passing |
| Build | `npm run build` produces optimized bundle |
| Security | No MQTT publish methods, read-only client |
| Rollback | Legacy HTML preserved at `dashboard/src/index.html` |

## Rollback

If the React migration encounters critical issues:

1. **Preserved Legacy**: The original `dashboard/src/index.html` with vanilla JS remains available at the same path. Simply revert to serving the HTML file directly.
2. **No Database Changes**: Migration only affects the frontend build process.
3. **Fast Rollback**: Reverting the build step to serve static HTML is a 5-minute change in the web server configuration.

## Implementation Notes

- Preserve current UI styling (Tailwind classes)
- Maintain demo/simulation mode for offline development
- WebSocket reconnection with exponential backoff
- Error boundary for graceful failure handling
