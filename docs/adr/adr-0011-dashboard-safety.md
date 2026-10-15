# ADR-0011: Dashboard Safety, Telemetry Mode Separation, and XSS Hardening

**Status:** Proposed — awaiting architecture-lead sign-off
**Architecture Lead Approval:** Pending. This record is linked to PR [#100](https://github.com/vinhphan812/smart-factory/pull/100) for review and audit trail. Do not promote to "Accepted" until explicit sign-off is recorded below.
**Date:** 2026-10-15
**Deciders:** dev-frontend, reviewer
**Related issues:** #39

## Context

The Smart Factory Operator Dashboard (dashboard/src/index.html) had several safety and correctness issues identified during PR #100 review:

1. Default WebSocket endpoint pointed to simulator port 8765 instead of the real gateway default ws://localhost:8000.
2. No explicit distinction between live gateway-connected mode and demo/simulation mode; synthetic data could masquerade as live data.
3. Incident acknowledgement used browser `prompt()` for operator identity and was available in all modes.
4. DOM XSS: external canonical event fields (device_id, event_type, trace_id, incident title/notes) were interpolated directly into innerHTML template literals.
5. No automated validation covering these safety properties.

## Decision

We implement the following changes:

1. **Config-driven WS endpoint** — GATEWAY_WS_URL defaults to ws://localhost:8000 and is configurable via `window.SMART_FACTORY_WS_URL` or `?ws=ws://host:port` query parameter.

2. **Explicit mode separation** — OPERATIONAL_MODE variable: 'demo' (default) or 'live'. Mode badge shows LIVE (green) or DEMO/SIMULATION (yellow). Mode switches when WebSocket connects/disconnects. Demo mode seeds visible fixtures; live mode renders only canonical telemetry.

3. **Restricted acknowledgement** — acknowledgeIncident() guarded: only operates when OPERATIONAL_MODE === 'demo'. Fixed operator ID 'demo-operator'; no prompt(). Compliance label changes: "Acknowledge: DISABLED (production mode)" in live, "Acknowledge: Local Demo Only" in demo.

4. **DOM XSS hardening** — All external data rendered via safeText(node, value) using textContent; no template literals with external interpolation. Incident notes in live mode use static strings ('Gateway event type: ' + eventType) rather than JSON.stringify(payload).

5. **Gateway telemetry forwarding** — DEFAULT_TOPICS expanded to include smart-factory/+/telemetry and smart-factory/+/heartbeat. EventNormalizer handles these topics.

6. **Automated tests** — New pytest suite (test_dashboard_safety.py) covers: WS config, mode isolation, ack restrictions, XSS sanitization, telemetry acceptance, compliance labels.

## Consequences

- Dashboard now has clear visual distinction between live and demo modes.
- No false production acknowledgement claims; local demo is clearly labelled.
- XSS attack surface eliminated from event/incident rendering.
- Telemetry from the gateway is properly subscribed and forwarded.
- Test coverage validates safety invariants programmatically.

## Alternatives considered

- Option A — Keep the old static incidents and prompt()-based ack: rejected because it creates false production/audit claims.
- Option B — Server-side acknowledgement with JWT: rejected because it requires server-side persistence/audit that does not yet exist.
- Option C — Remove acknowledgement entirely: rejected because demo workflow testing requires a functional acknowledgement path.

## Evidence

- dashboard/src/index.html — full implementation
- dashboard/README.md — configuration documentation
- iot-gateway/src/iot_gateway/config.py — DEFAULT_TOPICS changes
- iot-gateway/tests/test_normalizer.py — telemetry/heartbeat normalizer tests
- iot-gateway/tests/test_dashboard_safety.py — safety test suite
