# Smart Factory Security Abuse-Case Test Specifications

**Version:** 1.0
**Date:** 2026-10-20
**Status:** Proposed
**Author:** dev-qa (Issue #179)
**Related:** `docs/security/threat-model.md`, `iot-gateway/tests/test_security_abuse.py`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Test Naming Convention](#2-test-naming-convention)
3. [ABUSE-001: Command Injection via MQTT](#3-abuse-001-command-injection-via-mqtt)
4. [ABUSE-002: SSRF via Alert Webhook](#4-abuse-002-ssrf-via-alert-webhook)
5. [ABUSE-003: Telemetry Poisoning](#5-abuse-003-telemetry-poisoning)
6. [ABUSE-004: Auth Bypass — Safety Gate](#6-abuse-004-auth-bypass--safety-gate)
7. [ABUSE-005: DoS — Write Queue Exhaustion](#7-abuse-005-dos--write-queue-exhaustion)
8. [ABUSE-006: WebSocket Unauthorized Access](#8-abuse-006-websocket-unauthorized-access)
9. [ABUSE-007: FIWARE Orion-LD SSRF / Context Injection](#9-abuse-007-fiware-orion-ld-ssrf--context-injection)
10. [ABUSE-008: MQTT Replay Attack](#10-abuse-008-mqtt-replay-attack)
11. [Runbook: Running the Test Suite](#11-runbook-running-the-test-suite)

---

## 1. Overview

This document specifies **automation-ready test cases** for each abuse case identified in `threat-model.md`. Tests are documented at L1 (unit/integration) and target pytest for Python tests and Playwright for browser-based flows.

Each abuse case test specification follows this schema:

```
TEST-ID:  <abuse-case>-<N>
Title:    One-line description
Type:     [negative | positive | boundary | regression]
Preconditions: What must be true before the test runs
Automation:    pytest / Playwright / manual
Assertions:    What the test must verify
Pass criteria: Evidence that the system is secure
L0/L1:   Evidence level classification
```

Tests are categorised:
- **Negative**: attacker tries to exploit — system must reject/ignore
- **Positive**: legitimate user performs valid action — system must accept
- **Boundary**: edge cases, extreme values — system must handle gracefully
- **Regression**: verify a previously fixed vulnerability — system must not regress

---

## 2. Test Naming Convention

```
test_<abuse_case>_<attack_vector>_<expected_outcome>
```

Examples:
- `test_abuse001_mqtt_unknown_command_rejected`
- `test_abuse002_ssrf_private_ip_rejected`
- `test_abuse004_token_missing_returns_401`

---

## 3. ABUSE-001: Command Injection via MQTT

**Threat:** Attacker publishes a malicious command to `smart-factory/{deviceId}/command/down` to execute an unauthorized actuator action.

**Affected surface:** MQTT Bridge — `esp32-ukit-bridge/docs/threat-safety-model.md §2`
**Controls:** ESP32 command allowlist, argument range validation, broker ACL (ADR-0010)

### ABUSE-001-N1: Unknown command name rejected

```
TEST-ID:   ABUSE-001-N1
Title:     Unknown command name outside allowlist is rejected
Type:      negative
Severity:  Critical
Preconditions:
  - ESP32 bridge connected to MQTT broker
  - Telemetry capture active
Automation: pytest (mock MQTT broker)
Assertions:
  - Publish {"id": "test-001", "command_name": "FACTORY_RESET_ALL", "arguments": []}
  - ACK received within 5s with status != "ok"
  - ACK status is "unknown_command"
Pass criteria: ESP32 rejects unknown commands; status is "unknown_command"
L1: MQTT broker mock + asyncio test against EventNormalizer
```

### ABUSE-001-N2: Out-of-range speed argument rejected

```
TEST-ID:   ABUSE-001-N2
Title:     CONVEYOR_START with speed > 100 is rejected
Type:      negative / boundary
Severity:  Critical
Preconditions:
  - ESP32 bridge connected
Automation: pytest (mock MQTT broker)
Assertions:
  - Publish {"id": "test-002", "command_name": "CONVEYOR_START", "arguments": ["150"]}
  - ACK status is "invalid_argument"
  - Publish {"id": "test-003", "command_name": "CONVEYOR_START", "arguments": ["0"]}
  - ACK status is "invalid_argument"
Pass criteria: Speed outside 1–100 is rejected
L1: Unit test for CommandMapper::validSpeed()
```

### ABUSE-001-N3: SET_OUTPUT with invalid channel rejected

```
TEST-ID:   ABUSE-001-N3
Title:     SET_OUTPUT with channel > 255 is rejected
Type:      negative / boundary
Preconditions:
  - ESP32 bridge connected
Automation: pytest (mock MQTT broker)
Assertions:
  - Publish {"id": "test-004", "command_name": "SET_OUTPUT", "arguments": ["999", "1"]}
  - ACK status is "invalid_argument"
Pass criteria: Channel outside 0–255 is rejected
L1: Unit test for CommandMapper::validChannel()
```

### ABUSE-001-N4: SET_OUTPUT with invalid value rejected

```
TEST-ID:   ABUSE-001-N4
Title:     SET_OUTPUT with value not in {0,1} is rejected
Type:      negative
Preconditions:
  - ESP32 bridge connected
Automation: pytest
Assertions:
  - Publish {"id": "test-005", "command_name": "SET_OUTPUT", "arguments": ["5", "2"]}
  - ACK status is "invalid_argument"
Pass criteria: Value not "0" or "1" is rejected
L1: Unit test
```

### ABUSE-001-N5: Malformed JSON rejected

```
TEST-ID:   ABUSE-001-N5
Title:     Malformed JSON command is rejected
Type:      negative
Severity:  High
Preconditions: ESP32 bridge connected
Automation: pytest
Assertions:
  - Publish raw bytes: `{"id": "test-006", "command_name": ` (truncated)
  - Publish: `{not valid json at all}`
  - Neither results in an AMLP UART frame transmitted
Pass criteria: No UART frame sent for malformed JSON; ACK status = "invalid_argument"
L1: UART frame capture test
```

### ABUSE-001-N6: Command with prohibited characters rejected

```
TEST-ID:   ABUSE-001-N6
Title:     Command arguments with CR/LF are rejected
Type:      negative
Severity:  High
Preconditions: ESP32 bridge connected
Automation: pytest
Assertions:
  - Publish {"id": "test-007", "command_name": "CONVEYOR_START", "arguments": ["60\nCONVEYOR_STOP"]}
  - ACK status = "invalid_argument"
  - Publish {"id": "test-008", "command_name": "CONVEYOR_START", "arguments": ["60\rCONVEYOR_STOP"]}
  - ACK status = "invalid_argument"
Pass criteria: Arguments with CR or LF are rejected
L1: Unit test for allowed character filter
```

### ABUSE-001-N7: Duplicate command silently dropped

```
TEST-ID:   ABUSE-001-N7
Title:     Identical command within dedup window is silently dropped
Type:      negative / regression
Severity:  Medium
Preconditions: ESP32 bridge connected; command {"id": "dup-001", "command_name": "PING"} sent
Automation: pytest
Assertions:
  - Send {"id": "dup-001", "command_name": "PING"} again within 1s
  - No second ACK received
  - ESP32 serial log shows duplicate detected
Pass criteria: Duplicate silently dropped; no re-execution; no second ACK
L1: Unit test with 16-entry dedup cache
```

### ABUSE-001-N8: Cross-device command blocked by broker ACL

```
TEST-ID:   ABUSE-001-N8
Title:     Client cannot publish to a device's command topic it does not own
Type:      negative
Severity:  Critical
Preconditions: MQTT broker with ACLs configured per ADR-0010
Automation: pytest (two authenticated MQTT clients)
Assertions:
  - Client A (authenticated as "bridge-001") connects
  - Client A attempts to publish to "smart-factory/bridge-002/command/down"
  - Message is NOT delivered to bridge-002's subscription
  - Broker log shows ACL denial
Pass criteria: Broker ACL blocks cross-device command publish
L1: Integration test against real MQTT broker with ACL plugin
L3: Docker-compose test with Mosquitto ACLs
```

### ABUSE-001-N9: Queue-full status returned immediately

```
TEST-ID:   ABUSE-001-N9
Title:     Command published when queue is full returns "queue_full" immediately
Type:      boundary
Preconditions: ESP32 bridge with 8-slot queue at capacity
Automation: pytest
Assertions:
  - Send 8 commands (each with unique ID)
  - Send 9th command
  - 9th ACK has status "queue_full"
  - ACK received within 1s of send
Pass criteria: "queue_full" returned without waiting for queue drain
L1: Unit test
```

---

## 4. ABUSE-002: SSRF via Alert Webhook

**Threat:** Attacker tricks the gateway into making HTTP requests to internal/private network targets via the webhook URL resolution.

**Affected surface:** `iot-gateway/src/iot_gateway/alerts.py` — `WebhookNotification`
**Controls:** `test_ssrf.py` — strict hostname allowlist, fail-closed, `allow_redirects=False`

> **Note:** The SSRF fix is already implemented and tested in `test_ssrf.py`. The tests below document the full abuse-case coverage, including regression guards.

### ABUSE-002-N1: Off-allowlist hostname rejected

```
TEST-ID:   ABUSE-002-N1
Title:     Webhook URL with hostname not on allowlist is rejected
Type:      negative
Preconditions: SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS="trusted.example.com"
Automation: pytest
Assertions:
  - WebhookNotification with url="https://evil.attacker.com/hook"
  - handle() returns False; no HTTP request made
Pass criteria: Off-allowlist host rejected without making HTTP request
L1: Already covered: test_reject_off_allowlist_host
```

### ABUSE-002-N2: Fail-closed when allowlist is empty

```
TEST-ID:   ABUSE-002-N2
Title:     Webhook rejected when SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS is unset
Type:      negative / regression
Preconditions: SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS="" or not set
Automation: pytest
Assertions:
  - WebhookNotification(url="https://example.com/webhook")
  - handle() returns False
Pass criteria: Fail-closed; no HTTP request
L1: Already covered: test_fail_closed_when_allowlist_unset, test_fail_closed_when_allowlist_empty_string
```

### ABUSE-002-N3: Private IP ranges rejected (SSRF)

```
TEST-ID:   ABUSE-002-N3
Title:     Webhook URL resolving to RFC-1918 private IP is rejected
Type:      negative
Severity:  Critical
Preconditions: SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS="internal.factory.local"
Automation: pytest (mock DNS resolver)
Assertions:
  - allowed_hosts=["internal.factory.local"]
  - DNS resolution of internal.factory.local returns 10.0.0.5 (simulate)
  - handle() returns False
  - OR: URL is "https://169.254.169.254/latest/meta-data/" (AWS metadata)
  - handle() returns False
Pass criteria: Private IP ranges blocked; no HTTP request
L1: Manual verification + DNS mock test (implement)
```

### ABUSE-002-N4: DNS rebinding attack blocked

```
TEST-ID:   ABUSE-002-N4
Title:     DNS rebinding: hostname resolves to private IP at request time
Type:      negative
Severity:  High
Preconditions: SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS="trusted.example.com"
Automation: pytest (mock DNS with time-varying resolution)
Assertions:
  - Initial DNS resolution: trusted.example.com → 203.0.113.1 (allowed)
  - At HTTP request time: DNS resolution returns 10.0.0.1 (private)
  - handle() must NOT send to 10.0.0.1
Pass criteria: Either DNS resolved immediately and cached, or request goes to allowed IP only
L1: Implement DNS resolution + cache or resolve-once guard
```

### ABUSE-002-N5: Subdomain not accepted unless explicit

```
TEST-ID:   ABUSE-002-N5
Title:     Subdomain of allowlisted hostname is not accepted
Type:      negative / boundary
Preconditions: SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS="example.com"
Automation: pytest
Assertions:
  - URL "https://evil.example.com/hook" → handle() returns False
Pass criteria: Subdomain mismatch
L1: Already covered: test_subdomain_not_accepted
```

### ABUSE-002-N6: Userinfo and port stripped before comparison

```
TEST-ID:   ABUSE-002-N6
Title:     URL with userinfo or port bypasses allowlist check
Type:      negative / regression
Preconditions: SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS="example.com"
Automation: pytest
Assertions:
  - URL "https://user:secretpass@example.com/hook" → handle() returns True (after normalization)
  - URL "https://example.com:8443/hook" → handle() returns True (port stripped)
  - URL "https://EXAMPLE.COM/hook" → handle() returns True (case insensitive)
Pass criteria: Normalized hostname compared; userinfo/port stripped; case insensitive
L1: Already covered: test_normalize_strips_userinfo, test_normalize_strips_port, test_case_insensitive_match
```

### ABUSE-002-N7: No redirect follows (allow_redirects=False)

```
TEST-ID:   ABUSE-002-N7
Title:     HTTP redirect does not bypass allowlist
Type:      negative / regression
Preconditions: SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS="allowed.example.com"
Automation: pytest (mock aiohttp with redirect)
Assertions:
  - First request to allowed.example.com returns 301 → private IP
  - handle() must NOT follow redirect
Pass criteria: allow_redirects=False verified; no second request
L1: Already covered: test_allow_redirects_false
```

### ABUSE-002-N8: No credentials in logs

```
TEST-ID:   ABUSE-002-N8
Title:     Webhook URL with credentials does not leak in logs
Type:      negative / regression
Severity:  Medium
Preconditions: Any
Automation: pytest + log capture
Assertions:
  - URL "https://user:secretpass@example.com/hook" triggers rejection
  - No log record contains "://" or "secretpass" or "user:secretpass"
Pass criteria: Log scrubbed; no URL/credential disclosure
L1: Already covered: test_no_raw_url_in_logs_on_reject, test_no_credentials_in_logs_on_reject
```

### ABUSE-002-N9: Per-instance allowlist override takes precedence

```
TEST-ID:   ABUSE-002-N9
Title:     Per-instance allowed_hosts overrides module env var
Type:      positive
Preconditions: SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS="wrong.example.com"
Automation: pytest
Assertions:
  - WebhookNotification(url="https://correct.example.com/hook", allowed_hosts=["correct.example.com"])
  - handle() returns True
Pass criteria: Per-instance takes precedence
L1: Already covered: test_per_instance_allowed_hosts_takes_precedence
```

---

## 5. ABUSE-003: Telemetry Poisoning

**Threat:** Attacker publishes false telemetry readings to corrupt sensor data and mislead downstream consumers.

**Affected surface:** `iot-gateway/src/iot_gateway/event_normalizer.py`, `iot-gateway/src/iot_gateway/gateway.py`
**Controls:** ESP32 bridge credentials; `EventNormalizer.normalize()` discards malformed JSON

### ABUSE-003-N1: Malformed telemetry JSON discarded

```
TEST-ID:   ABUSE-003-N1
Title:     Non-deserializable MQTT telemetry message is discarded
Type:      negative
Severity:  High
Preconditions: Gateway running; subscribing to telemetry topic
Automation: pytest
Assertions:
  - Publish raw non-JSON bytes to "smart-factory/+/telemetry"
  - Event is NOT persisted to SQLite
  - No event broadcast to WebSocket clients
Pass criteria: normalize() returns None; no event queued
L1: Unit test for EventNormalizer.normalize()
```

### ABUSE-003-N2: Unknown event type discarded

```
TEST-ID:   ABUSE-003-N2
Title:     Telemetry with unknown event_type is discarded or tagged
Type:      negative
Preconditions: Gateway running
Automation: pytest
Assertions:
  - Publish {"device_id": "x", "event_type": "telemetry_xyz"} (unknown enum value)
  - normalize() raises ValueError OR returns None
Pass criteria: Unknown event type not persisted silently
L1: Unit test for EventNormalizer with invalid EventType
```

### ABUSE-003-N3: Telemetry with extreme/out-of-range sensor values handled

```
TEST-ID:   ABUSE-003-N3
Title:     Telemetry with impossible sensor values is persisted but flagged
Type:      negative
Preconditions: Gateway running
Automation: pytest
Assertions:
  - Publish {"device_id": "conveyor-01", "event_type": "telemetry",
      "payload": {"speed": 9999, "temperature": -1000}}
  - Event is persisted to SQLite (schema not enforced at normalizer level)
  - A future schema validator could flag this
Pass criteria: Normalizer does not crash; future payload schema validation recommended
L1: Integration test for normalizer resilience to extreme values
L2: Future: schema validation layer rejects out-of-range values
```

### ABUSE-003-N4: High-volume telemetry causes queue drop

```
TEST-ID:   ABUSE-003-N4
Title:     Rapid telemetry flooding causes queue overflow; counter incremented
Type:      negative / boundary
Severity:  High
Preconditions: Gateway running; write queue size = 500
Automation: pytest
Assertions:
  - Publish 600 MQTT telemetry messages rapidly
  - /health shows queue_dropped_count >= 100
  - No unhandled exception thrown
Pass criteria: Graceful degradation; counter visible; no crash
L1: Integration test for queue overflow
```

### ABUSE-003-N5: Stale telemetry flagging (ESP32 clock reset)

```
TEST-ID:   ABUSE-003-N5
Title:     Telemetry from ESP32 after clock reset is detected as stale
Type:      negative / regression
Preconditions: ESP32 telemetry with mqtt_timestamp_ms in uptime domain
Automation: pytest
Assertions:
  - Event has is_timestamp_synchronized=False
  - Latency computation is skipped (latency_ms = -1)
  - Gateway does not incorrectly flag as out-of-order
Pass criteria: Unsync'd timestamps handled without false positives
L1: Unit test for CanonicalEvent with is_timestamp_synchronized=False
```

---

## 6. ABUSE-004: Auth Bypass — Safety Gate

**Threat:** Attacker bypasses operator authentication on safety-gate endpoints via brute force or token theft.

**Affected surface:** `iot-gateway/src/iot_gateway/api.py` — `_require_operator_token`, `/safety-gate/*`
**Controls:** Timing-safe comparison; 503 when token unconfigured

### ABUSE-004-N1: Missing token returns 401

```
TEST-ID:   ABUSE-004-N1
Title:     Request without X-Operator-Token header returns 401
Type:      negative
Severity:  Critical
Preconditions: SAFETY_OPERATOR_TOKEN configured
Automation: pytest (FastAPI TestClient)
Assertions:
  - POST /safety-gate/emergency-stop without X-Operator-Token
  - Response status = 401
  - Response body does not include sensitive details
Pass criteria: 401 returned; no authentication bypass
L1: test_operator_token_required_for_emergency_stop (implement in test_security_abuse.py)
```

### ABUSE-004-N2: Invalid token returns 401

```
TEST-ID:   ABUSE-004-N2
Title:     Request with wrong token returns 401
Type:      negative
Severity:  Critical
Preconditions: SAFETY_OPERATOR_TOKEN="correct-token"
Automation: pytest (FastAPI TestClient)
Assertions:
  - POST /safety-gate/emergency-stop with X-Operator-Token="wrong-token"
  - Response status = 401
Pass criteria: 401 returned; timing-safe comparison prevents oracle
L1: test_operator_token_invalid_returns_401 (implement)
```

### ABUSE-004-N3: Token unconfigured returns 503

```
TEST-ID:   ABUSE-004-N3
Title:     When SAFETY_OPERATOR_TOKEN is unset, auth endpoints return 503
Type:      negative / regression
Severity:  High
Preconditions: SAFETY_OPERATOR_TOKEN not set (env var absent)
Automation: pytest (monkeypatch)
Assertions:
  - POST /safety-gate/emergency-stop
  - Response status = 503
  - Response body indicates auth not configured
Pass criteria: 503 returned; no bypass path
L1: test_operator_token_unset_returns_503 (implement)
```

### ABUSE-004-N4: Rate limit on auth endpoints

```
TEST-ID:   ABUSE-004-N4
Title:     Rapid auth attempts are rate-limited
Type:      negative
Severity:  Critical
Preconditions: SAFETY_OPERATOR_TOKEN="correct-token"; no rate limiter configured
Automation: pytest + Playwright (for HTTP-level observation)
Assertions:
  - Send 100 requests with wrong token within 1 second
  - After N requests (e.g., 5), subsequent requests return 429 Too Many Requests
  - Or: response time increases exponentially
Pass criteria: Brute force is impractical; rate limit enforced
L2: Integration test (rate limiter must be implemented first)
L0: Design requirement documented here; implement in future iteration
```

### ABUSE-004-N5: Safety gate status endpoint is unauthenticated (expected)

```
TEST-ID:   ABUSE-004-N5
Title:     GET /safety-gate/status is unauthenticated (by design)
Type:      positive / regression
Preconditions: Gateway running
Automation: pytest
Assertions:
  - GET /safety-gate/status returns 200 without token
  - Response includes only non-sensitive status fields
Pass criteria: Non-sensitive status accessible without auth; no device IDs or tokens leaked
L1: test_safety_gate_status_public (implement)
```

### ABUSE-004-N6: Incident acknowledge requires token

```
TEST-ID:   ABUSE-004-N6
Title:     POST /incidents/{id}/acknowledge requires operator token
Type:      negative
Severity:  High
Preconditions: SAFETY_OPERATOR_TOKEN configured
Automation: pytest (FastAPI TestClient)
Assertions:
  - POST /incidents/test-001/acknowledge without token → 401
  - POST /incidents/test-001/acknowledge with valid token → 200 or 404
Pass criteria: 401 without token
L1: test_incident_ack_requires_token (implement)
```

---

## 7. ABUSE-005: DoS — Write Queue Exhaustion

**Threat:** Attacker floods MQTT telemetry to exhaust the gateway write queue, causing legitimate events to be dropped.

**Affected surface:** `iot-gateway/src/iot_gateway/gateway.py` — `_on_mqtt_message`, `write_queue`
**Controls:** Bounded queue (500); `dropped_count_ref`

### ABUSE-005-N1: Queue overflow increments dropped counter

```
TEST-ID:   ABUSE-005-N1
Title:     Write queue overflow increments dropped_count; health endpoint reports it
Type:      negative / boundary
Severity:  High
Preconditions: Gateway running; write queue size = 500
Automation: pytest (async integration test)
Assertions:
  - Fill queue (501 messages); verify dropped_count >= 1
  - GET /health → queue_dropped_count >= 1
Pass criteria: Counter incremented; /health visible; no crash
L1: test_queue_overflow_increments_dropped_count (implement)
```

### ABUSE-005-N2: Alert fired when dropped_count increases

```
TEST-ID:   ABUSE-005-N2
Title:     Queue drop event triggers alert/incident
Type:      negative
Severity:  High
Preconditions: Alert system configured; queue overflow occurs
Automation: pytest (mock alert handler)
Assertions:
  - Simulate queue overflow (dropped_count increment)
  - Alert fired with severity >= WARNING
  - Incident created or logged
Pass criteria: Operations notified of queue drop
L2: Integration test; alert mechanism must be wired first
L0: Gap documented; implement in future iteration
```

### ABUSE-005-N3: Slow client disconnected (WebSocket)

```
TEST-ID:   ABUSE-005-N3
Title:     WebSocket client with full outbound queue is disconnected
Type:      negative / regression
Severity:  Medium
Preconditions: WebSocket server running; client with MAX_QUEUE_PER_CLIENT=64 events queued
Automation: pytest (asyncio)
Assertions:
  - Simulate client whose queue is full
  - Next broadcast() call raises QueueFull for that client
  - Client is disconnected (removed from _client_queues)
Pass criteria: Lagging client removed; fast clients not blocked
L1: Already covered: test_broadcast_disconnects_lagging_clients (test_api.py)
```

---

## 8. ABUSE-006: WebSocket Unauthorized Access

**Threat:** Attacker connects to WebSocket without credentials and receives all factory events.

**Affected surface:** `iot-gateway/src/iot_gateway/api.py` — `WebSocketServer`
**Controls:** WebSocket currently read-only; no auth

### ABUSE-006-N1: Anonymous WebSocket connection accepted (expected gap)

```
TEST-ID:   ABUSE-006-N1
Title:     Unauthenticated WebSocket connection is accepted (current behavior)
Type:      regression / negative
Severity:  High
Preconditions: WebSocket server running
Automation: pytest + manual verification
Assertions:
  - Any TCP client can connect to ws://gateway:8000
  - Client receives all broadcast events
  - No token required
Pass criteria: Current state documented; future: token required
L1: Manual test + automated connection test
L0: Gap documented; mitigation: add WebSocket subprotocol auth
```

### ABUSE-006-N2: WebSocket message origin validated (future)

```
TEST-ID:   ABUSE-006-N2
Title:     WebSocket server validates origin header
Type:      negative (future)
Preconditions: WebSocket server running with origin validation enabled
Automation: pytest
Assertions:
  - Client connects with Origin: https://evil.example.com
  - Connection rejected (or allowed with warning)
  - Client connects with Origin: https://dashboard.factory.local → allowed
Pass criteria: Cross-origin WebSocket hijacking prevented
L0: Future requirement; document; implement when dashboard ready
```

---

## 9. ABUSE-007: FIWARE Orion-LD SSRF / Context Injection

**Threat:** Attacker registers a malicious subscription callback or injects a hostile `@context` to pivot to internal services.

**Affected surface:** `iot-gateway/src/iot_gateway/adapters/orion_ld.py` (planned), FIWARE Orion-LD deployment
**Controls:** ADR-0014 F3 (not yet implemented)

### ABUSE-007-N1: Orion-LD subscription callback URL validation

```
TEST-ID:   ABUSE-007-N1
Title:     Orion-LD subscription callback URL must be validated against private IP ranges
Type:      negative
Severity:  Critical
Preconditions: Orion-LD subscription API accessible
Automation: pytest (mock Orion-LD or integration test)
Assertions:
  - POST /ngsi-ld/v1/subscriptions with notification.endpoint.url="http://10.0.0.5/api"
  - Request rejected with 400 or subscription not created
  - POST with notification.endpoint.url="http://169.254.169.254/latest/meta-data/"
  - Request rejected
Pass criteria: Private IP callback URLs rejected
L2: Integration test with live Orion-LD
L0: Not yet implemented per ADR-0014 F3; gap documented
```

### ABUSE-007-N2: Orion-LD write requires authentication

```
TEST-ID:   ABUSE-007-N2
Title:     Orion-LD NGSI-LD write endpoint requires authentication
Type:      negative
Severity:  Critical
Preconditions: Orion-LD deployment without reverse proxy auth
Automation: pytest
Assertions:
  - POST /ngsi-ld/v1/entities without Authorization header
  - Response is 401 or 403
  - POST /ngsi-ld/v1/entities with valid credentials
  - Response is 201
Pass criteria: Unauthenticated writes rejected
L2: Integration test
L0: Not yet implemented; gap documented
```

### ABUSE-007-N3: Context sink does not fetch remote @context

```
TEST-ID:   ABUSE-007-N3
Title:     ContextSink does not fetch @context from untrusted remote URLs
Type:      negative
Severity:  High
Preconditions: ContextSink implementation exists
Automation: pytest (mock HTTP client)
Assertions:
  - Entity includes @context pointing to https://attacker.com/context.jsonld
  - ContextSink does NOT fetch the remote context
  - Only local @context documents are used
Pass criteria: Remote @context not fetched; local context used
L1: Unit test for ContextSink (implement when ContextSink exists)
L0: Requirement documented in ADR-0014 §Deployment
```

---

## 10. ABUSE-008: MQTT Replay Attack

**Threat:** Attacker captures valid MQTT command frames and replays them within the dedup window to execute duplicate commands.

**Affected surface:** ESP32 bridge — `esp32-ukit-bridge/docs/threat-safety-model.md §2.4`
**Controls:** 16-entry FIFO dedup cache

### ABUSE-008-N1: Duplicate within dedup window silently dropped

```
TEST-ID:   ABUSE-008-N1
Title:     Command replayed within 16-entry FIFO dedup window is silently dropped
Type:      negative / regression
Severity:  Medium
Preconditions: ESP32 bridge running; command with id="replay-001" sent once
Automation: pytest (mock MQTT + bridge logic)
Assertions:
  - Same command {"id": "replay-001", "command_name": "PING"} sent again within 1s
  - No second ACK published
  - ESP32 log shows "duplicate detected"
Pass criteria: Replay silently dropped; no re-execution; no second ACK
L1: Unit test for deduplication cache
```

### ABUSE-008-N2: Dedup cache eviction allows replay (known limitation)

```
TEST-ID:   ABUSE-008-N2
Title:     After 16 unique commands, the first command ID can be replayed
Type:      negative / boundary (known limitation)
Severity:  Low
Preconditions: ESP32 bridge with 16 unique command IDs sent; cache evicted
Automation: pytest
Assertions:
  - Send 17 unique command IDs (1..17)
  - Command ID 1 is now evicted from cache
  - Re-send command ID 1
  - Command IS re-executed (no dedup protection for evicted IDs)
Pass criteria: Behavior documented; TTL enforcement recommended for future
L1: Unit test demonstrating eviction behavior
L0: Gap documented; HMAC signing recommended
```

---

## 11. Runbook: Running the Test Suite

### 11.1 Prerequisites

```bash
cd iot-gateway
pip install -e ".[dev]"
pip install pytest pytest-asyncio httpx websockets aioresponses
```

### 11.2 Run All Security Tests

```bash
# Run security abuse tests
pytest iot-gateway/tests/test_security_abuse.py -v

# Run existing SSRF regression tests
pytest iot-gateway/tests/test_ssrf.py -v

# Run full gateway test suite (regression check)
pytest iot-gateway/tests/ -v --ignore=iot-gateway/tests/test_fiware_*.py
```

### 11.3 Expected Results

| Test Group | Expected Pass | Notes |
|-----------|--------------|-------|
| `test_security_abuse.py` | All pass (see CI) | New security tests |
| `test_ssrf.py` | All pass | SSRF regression suite |
| `test_api.py` | All pass | REST + WebSocket tests |
| `test_safety_gate.py` | All pass | Safety gate decision tests |
| `test_normalizer.py` | All pass | Telemetry normalization tests |

### 11.4 Continuous Integration

Add to CI pipeline (`.github/workflows/security-tests.yml`):

```yaml
name: Security Abuse-Case Tests
on: [push, pull_request]
jobs:
  security-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install dependencies
        run: pip install -e iot-gateway/[dev] pytest pytest-asyncio
      - name: Run SSRF regression suite
        run: pytest iot-gateway/tests/test_ssrf.py -v
      - name: Run security abuse tests
        run: pytest iot-gateway/tests/test_security_abuse.py -v
      - name: Run full test suite
        run: pytest iot-gateway/tests/ -v --ignore=iot-gateway/tests/test_fiware_*.py
```

---

*Document version 1.0 — Issue #179 | Companion to `docs/security/threat-model.md`*
