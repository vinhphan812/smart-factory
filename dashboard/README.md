# Dashboard — Smart Factory

**Status: IMPLEMENTED** | Related issues: #148 #15 #39 #40

## Purpose

Role-specific operator display for telemetry charts, unified event timelines, and demo-only local acknowledgement. This version replaces the legacy single-file HTML dashboard with a React + TypeScript + Vite application.

**Note:** This PR delivers a **live telemetry fixture** (actual AMLP-normalized data via WebSocket) and a **demo-mode acknowledgement** (local, browser-memory only). No production acknowledgement with actor/timestamp audit, backend persistence, or server-side authentication exists yet.

## Migration (Issue #148)

The dashboard has been migrated from a single HTML file (`dashboard/src/index.html`) to a React + TypeScript + Vite application.

### What Changed

- **Technology:** React 18 + TypeScript + Vite (previously: vanilla JS + Tailwind CDN)
- **Architecture:** Component-based with typed contracts (previously: monolithic HTML)
- **Testing:** Vitest unit tests (previously: none)
- **Build:** Optimized production bundle (previously: CDN dependencies)

### Rollback

The legacy `dashboard/src/index.html` is preserved. If issues occur, revert to serving the HTML file directly.

## Features

- **Telemetry Views:** Time-range selector (5m, 1h, 24h), per-device telemetry charts, and metric aggregation (rate, average, peak)
- **Event Timeline:** Unified event stream filtered by severity (INFO, WARN, ERROR, CRITICAL), device, and trace ID
- **WebSocket Integration:** Real-time data from the IoT gateway with automatic reconnection
- **Demo Mode:** Works offline with simulated data
- **Incident Management:** Incident severities, automatic threshold escalation, and export to CSV/JSON

### Acknowledgement — Current Scope

Incident acknowledgement is **demo-only** and **local to the browser session**:

- **Live/production mode** — acknowledgement is disabled; the compliance label reads "Acknowledge: DISABLED (production mode)". No production auth, audit, or persistence exists.
- **Demo/simulation mode** — a local demonstration acknowledgement button is available, labelled "Acknowledge Incident (Demo)". It stores actor `demo-operator` and timestamp in browser memory only; there is no backend persistence, authentication, or export.
- **Planned (future):** Server-side acknowledgement with JWT auth, persistent audit log, and operator identity verification. This requires backend changes not yet implemented.

## Tech Stack

- React 18.3.1
- TypeScript
- Vite
- Chart.js 4.4.3
- React Router 6
- Vitest for testing

## Getting Started

### Prerequisites

- Node.js 18+
- npm

### Install

```bash
cd dashboard
npm install
```

### Development

```bash
npm run dev
```

Opens the dashboard at http://localhost:3000

### Build

```bash
npm run build
```

Builds for production to `dist/`

### Preview Production Build

```bash
npm run preview
```

### Test

```bash
npm run test
```

Runs unit tests with Vitest.

## Environment Variables

Copy `.env.example` to `.env`:

```
VITE_GATEWAY_WS_URL=ws://localhost:8000
VITE_GATEWAY_API_URL=http://localhost:8000
```

## Project Structure

```
dashboard/
├── src/
│   ├── app/              # App entry (main.tsx), root component (App.tsx)
│   ├── pages/           # Route pages (TelemetryPage, EventsPage)
│   ├── components/      # Shared UI (AppLayout, StatusBadge)
│   ├── features/        # Feature-specific (TelemetryChart)
│   ├── hooks/           # Custom hooks (useGatewayWs, useGatewayEvents)
│   ├── services/
│   │   ├── api/        # HTTP client for gateway REST endpoints
│   │   └── ws/         # WebSocket client (READ-ONLY)
│   ├── contracts/      # TypeScript types matching gateway API
│   ├── styles/         # Global CSS
│   └── tests/          # Unit tests
├── src-legacy/          # Original index.html (rollback fallback)
├── index.html
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## Local Development

Run the dashboard and connect to the gateway:

```bash
npm run dev
```

The page attempts connecting to the gateway WebSocket endpoint (defaulting to `ws://localhost:8000`, configurable via environment variables). When disconnected, it explicitly operates in **Simulation / Demo Mode** with demo fixtures. In live mode, it renders real canonical telemetry and restricts local demonstration acknowledgments.

## Security

The WebSocket client is **READ-ONLY**. It subscribes to telemetry but never initiates physical actuation. Browser never sends MQTT commands to devices.

## License

See repository root license.
