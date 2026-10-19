# Smart Factory Dashboard

**Status: IMPLEMENTED** | Related issues: #148 #15 #39 #40

A React + TypeScript + Vite application for the Smart Factory operator dashboard. Displays real-time telemetry charts, unified event timelines, and incident management.

## Features

- **Telemetry Views:** Time-range selector (5m, 1h, 24h), per-device telemetry charts, and metric aggregation (rate, average, peak)
- **Event Timeline:** Unified event stream filtered by severity (INFO, WARN, ERROR, CRITICAL), device, and trace ID
- **WebSocket Integration:** Real-time data from the IoT gateway with automatic reconnection
- **Demo Mode:** Works offline with simulated data

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
├── index.html
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## Security

The WebSocket client is **READ-ONLY**. It subscribes to telemetry but never initiates physical actuation. Browser never sends MQTT commands to devices.

## License

See repository root license.
