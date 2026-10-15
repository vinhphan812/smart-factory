# Dashboard — Smart Factory

**Status: IMPLEMENTED (Operator UI & Telemetry Fixture)** | Related issues: #15 #39 #40

## Purpose

Role-specific operator display for telemetry charts, unified event timelines, and demo-only local acknowledgement. No heartbeat topic is contracted by the ESP32 bridge firmware; this PR adds the subscription but it requires a separate accepted ADR before it is authorized as supported E2E.

**Note:** This PR delivers a **live telemetry fixture** (actual AMLP-normalized data via WebSocket) and a **demo-mode acknowledgement** (local, browser-memory only). No production acknowledgement with actor/timestamp audit, backend persistence, or server-side authentication exists yet.

## Features

- **Telemetry Views:** Time-range selector (5m, 1h, 24h), per-device telemetry charts, and metric aggregation (rate, average, peak).
- **Event Timeline:** Unified event stream filtered by severity (INFO, WARN, ERROR, CRITICAL), device, and trace ID.
- **Incident Management:** Incident severities, automatic threshold escalation, and export to CSV/JSON.

### Acknowledgement — Current Scope

Incident acknowledgement is **demo-only** and **local to the browser session**:

- **Live/production mode** — acknowledgement is disabled; the compliance label reads "Acknowledge: DISABLED (production mode)". No production auth, audit, or persistence exists.
- **Demo/simulation mode** — a local demonstration acknowledgement button is available, labelled "Acknowledge Incident (Demo)". It stores actor `demo-operator` and timestamp in browser memory only; there is no backend persistence, authentication, or export.
- **Planned (future):** Server-side acknowledgement with JWT auth, persistent audit log, and operator identity verification. This requires backend changes not yet implemented.

## Module structure

```
dashboard/
├── README.md            ← this file
├── src/
│   └── index.html       ← single-page operator dashboard (Tailwind + Chart.js)
└── tests/
```

## Local development

Run the dashboard and connect to the gateway:

```bash
python -m http.server 8080 --directory dashboard/src
```

Open `http://localhost:8080`. The page attempts connecting to the gateway WebSocket endpoint (defaulting to `ws://localhost:8000`, configurable via `window.SMART_FACTORY_WS_URL` or `?ws=ws://host:port` query parameter). When disconnected, it explicitly operates in **Simulation / Demo Mode** with demo fixtures. In live mode, it renders real canonical telemetry and restricts local demonstration acknowledgments.
