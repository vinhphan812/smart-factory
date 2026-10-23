# Smart Factory End-to-End Threat Model

**Version:** 1.0
**Date:** 2026-10-20
**Status:** Proposed
**Author:** dev-qa (Issue #179)
**Scope:** Wave 4-e2e-hil | Builds on: ADR-0006, ADR-0010, ADR-0013, ADR-0014

---

## Table of Contents

1. [System Overview and Service Boundaries](#1-system-overview-and-service-boundaries)
2. [Asset Inventory](#2-asset-inventory)
3. [STRIDE Threat Analysis](#3-stride-threat-analysis)
4. [Attack Surfaces](#4-attack-surfaces)
5. [Abuse Cases](#5-abuse-cases)
6. [Existing Controls and Gaps](#6-existing-controls-and-gaps)
7. [Risk Summary](#7-risk-summary)
8. [Threat Modelling Methodology](#8-threat-modelling-methodology)

---

## 1. System Overview and Service Boundaries

### 1.1 System Architecture

```
[Physical Factory / Actuators]
         ↕ UART AMLP (5V↔3.3V)
[ESP32-S3 Bridge]  ←── no TLS (PRODUCTION BLOCKED per bridge threat model)
         ↕ authenticated MQTT (plain, port 1883)
[MQTT Broker]
         ↕
[IoT Gateway]  ── REST (FastAPI/uvicorn) / WebSocket (websockets)
         │
         ├──[Dashboard: React]  (reads events, sends commands via REST)
         ├──[Digital Twin: Unity]  (WebSocket)
         ├──[Edge AI Robot: MiniAlpha]  (notification/skills via gateway incident policy)
         ├──[Context Broker: FIWARE Orion-LD]  (NGSI-LD PATCH/UPSERT via ContextSink)
         └──[Alert Webhooks]  (external HTTP POST)

[SQLite Event Store]  ← gateway persistence
```

### 1.2 Service Boundaries and Trust Levels

| # | Boundary | Direction | Trust Level | Transport |
|---|----------|-----------|-------------|-----------|
| 1 | Physical Actuators ↔ Mega | UART AMLP | Trusted (local bus) | Serial |
| 2 | Mega ↔ ESP32 Bridge | UART AMLP | Trusted | Serial |
| 3 | ESP32 Bridge ↔ MQTT Broker | MQTT | Untrusted network | Plain MQTT / future TLS |
| 4 | MQTT Broker ↔ IoT Gateway | MQTT | Untrusted network | Plain MQTT / future TLS |
| 5 | Gateway ↔ REST/WebSocket clients | HTTP/WS | Public-facing | TCP |
| 6 | Gateway ↔ FIWARE Orion-LD | HTTP | Internal network | TCP |
| 7 | Gateway ↔ Alert Webhooks | HTTPS | External network | TCP/TLS |
| 8 | Dashboard ↔ Gateway | REST | Within same trust boundary | HTTP |

### 1.3 Data Flows

| Flow | Source → Dest | Wire | Data Sensitivity |
|------|--------------|------|-----------------|
| Telemetry | Bridge → Broker → Gateway | MQTT | Integrity required |
| Commands | Dashboard → Broker → Bridge | MQTT | Integrity + Authorization |
| Context Upsert | Gateway → Orion-LD | HTTP NGSI-LD | Integrity |
| Real-time events | Gateway → Dashboard/Twin | WebSocket | Integrity |
| Alert notifications | Gateway → External webhook | HTTPS | Confidentiality + Integrity |
| Safety gate decisions | Gateway internal | In-process | Integrity |

---

## 2. Asset Inventory

### 2.1 Hardware Assets

| Asset | Confidentiality | Integrity | Availability |
|-------|---------------|-----------|-------------|
| ESP32-S3 Bridge | Low | **High** | **High** |
| Mega uKit Controller | Low | **High** | **High** |
| Actuators (conveyor, motors) | Low | **Critical** | **Critical** |
| MQTT Broker | Medium | **High** | **High** |
| IoT Gateway host | Medium | **High** | **High** |
| FIWARE Orion-LD host | Medium | **High** | Medium |
| MongoDB host | Medium | **High** | Medium |

### 2.2 Software / Credential Assets

| Asset | Type | Current State |
|-------|------|--------------|
| `SAFETY_OPERATOR_TOKEN` | Bearer token (env var) | Implemented; timing-safe comparison (`secrets.compare_digest`) |
| MQTT credentials (bridge) | Username/password | In `secrets.h`; plain MQTT (production blocked) |
| MQTT credentials (gateway) | Username/password | In env vars |
| WebSocket client connections | Ephemeral sessions | No auth; open to anyone on network |
| REST API (read) | `/events`, `/health`, `/snapshot`, `/metrics` | No auth |
| REST API (write) | Safety gate, incidents | Token-protected |
| ESP32 command allowlist | 5 tokens | Implemented in `CommandMapper::build()` |
| Orion-LD write credentials | Future: reverse proxy auth | Not yet configured |
| `SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS` | URL allowlist | Implemented; fail-closed |

---

## 3. STRIDE Threat Analysis

### 3.1 S — Spoofing

> Threat: An attacker impersonates a legitimate entity to gain unauthorized access.

| # | Threat | Service Boundary | Likelihood | Impact | Mitigations | Gap |
|---|--------|-----------------|-----------|--------|-------------|-----|
| S-1 | Rogue MQTT client authenticates to broker with stolen/guessed credentials | Boundary 3, 4 | Medium | **Critical** | Broker username/password; ACLs per ADR-0010 | No TLS — credentials transmitted in cleartext |
| S-2 | Attacker spoofs ESP32 bridge MAC/IP to inject telemetry | Boundary 3 | Low (requires LAN access) | High | MQTT broker validates client ID; device identity in topic | No TLS — packet injection possible |
| S-3 | WebSocket client connects without credentials, impersonating a dashboard | Boundary 5 | **High** | Medium | None currently — WebSocket accepts any connection | **No WebSocket authentication** |
| S-4 | Attacker calls REST safety-gate endpoints with stolen `SAFETY_OPERATOR_TOKEN` | Boundary 5 | Medium | **Critical** | Timing-safe comparison; 503 when token not configured | No token rotation mechanism; token in env var |
| S-5 | Rogue FIWARE subscriber registers a callback URL (SSRF) to Orion-LD subscription | Boundary 6 | Medium | High | Subscription endpoint validation; rate limits (per ADR-0014 F3) | Not yet implemented |

### 3.2 T — Tampering

> Threat: An attacker modifies data in transit or at rest without authorization.

| # | Threat | Service Boundary | Likelihood | Impact | Mitigations | Gap |
|---|--------|-----------------|-----------|--------|-------------|-----|
| T-1 | Telemetry poisoning: attacker modifies MQTT payload to inject false sensor readings | Boundary 3 | Medium | **Critical** | No MQTT integrity check (plaintext); ESP32 bridge validates field range; gateway normalizer discards malformed JSON | **No MQTT payload signing/TLS** |
| T-2 | Command injection: attacker publishes to `smart-factory/+/command/down` with malicious `command_name` | Boundary 3 | Medium | **Critical** | ESP32 command allowlist (5 tokens); broker ACL blocks unauthorized publish; MEGA hard limits | ADR-0010 ACL not yet verified as enforced |
| T-3 | Safety gate decision tampering: `evaluate()` verdict overridden via API or in-memory race | Boundary 5 | Low | **Critical** | Gate is in-process; no external mutation endpoint (only `set_emergency_stop`, `set_interlock`) | No cryptographic integrity on gate state |
| T-4 | WebSocket message injection: attacker sends crafted JSON to connected clients | Boundary 5 | Low | Medium | Gateway only sends server-initiated events; clients receive read-only data | No client authentication; no message signing |
| T-5 | Orion-LD context poisoning: Gateway ContextSink sends invalid NGSI-LD to corrupt entity state | Boundary 6 | Low | Medium | Validate payload schema before upsert; sequence + boot_id deduplication | Orion-LD write endpoint not yet behind reverse proxy auth |
| T-6 | SQLite event store tampering: attacker modifies database file directly | Gateway host | Low | Medium | File permissions; gateway is the sole writer | No write integrity check (checksum) on events |

### 3.3 R — Repudiation

> Threat: An entity denies having performed an action, and there is no proof to the contrary.

| # | Threat | Service Boundary | Likelihood | Impact | Mitigations | Gap |
|---|--------|-----------------|-----------|--------|-------------|-----|
| R-1 | Operator denies issuing emergency stop or override | Boundary 5 | Low | Medium | Every safety-gate decision is logged with timestamp, issuer type, and non-sensitive metadata (per ADR-0013) | Command arguments not logged (by design — protects secrets) |
| R-2 | Attacker denies publishing a malicious MQTT command (no broker-side audit) | Boundary 3 | Medium | Medium | ACK published with `request_id`; command logged in bridge | **No broker-side audit log documented** |
| R-3 | Dashboard operator denies sending a command | Boundary 5 | Low | Medium | REST API has no auth for commands (no token on dashboard→broker path) | Dashboard command path has no non-repudiation control |
| R-4 | FIWARE subscription delivery not confirmed | Boundary 6 | Medium | Low | Orion-LD subscription ACK; notification relay tracks delivery | No end-to-end delivery confirmation to Gateway |

### 3.4 I — Information Disclosure

> Threat: An attacker gains access to information they are not authorized to read.

| # | Threat | Service Boundary | Likelihood | Impact | Mitigations | Gap |
|---|--------|-----------------|-----------|--------|-------------|-----|
| I-1 | Raw webhook URLs with credentials leak in gateway logs | Boundary 7 | **High** (proven fix required) | Medium | `test_ssrf.py` tests: no raw URL/credentials in logs on reject | Fix already tested (`test_ssrf.py`); must verify in production |
| I-2 | Telemetry payload secrets (if any) disclosed in REST `/events` response | Boundary 5 | Low | Medium | No secrets in telemetry payloads (per design) | None |
| I-3 | Orion-LD `@context` document fetched from untrusted remote URL | Boundary 6 | Medium | Medium | ADR-0014: "static, versioned and locally controlled" | `@context` fetch not yet implemented; must not allow arbitrary remote |
| I-4 | ESP32 bridge credentials extracted from firmware binary dump | Boundary 3 | Low (requires physical access) | **Critical** | `secrets.h` excluded from git; ESP32 flash encryption recommended | **No flash encryption verified in current build** |
| I-5 | Safety gate audit log includes sensitive command arguments | Boundary 5 | Low | Medium | ADR-0013 explicitly excludes command arguments from audit log | None; design decision documented |

### 3.5 D — Denial of Service

> Threat: An attacker prevents legitimate users from accessing a service.

| # | Threat | Service Boundary | Likelihood | Impact | Mitigations | Gap |
|---|--------|-----------------|-----------|--------|-------------|-----|
| D-1 | MQTT telemetry flooding: attacker publishes high-volume messages to fill gateway write queue | Boundary 3, 4 | Medium | **High** | Bounded write queue (size=500); overflow drops events and increments `dropped` counter | No MQTT topic rate limiting at broker |
| D-2 | WebSocket client saturates outbound queue (64 events/client) | Boundary 5 | Medium | Medium | `MAX_QUEUE_PER_CLIENT = 64`; lagging clients disconnected | **No connection limit per IP or global client cap** |
| D-3 | Slowloris / HTTP connection exhaustion against REST API | Boundary 5 | Medium | Medium | uvicorn default timeouts | No explicit connection pool limit or timeout documented |
| D-4 | Orion-LD MongoDB overwhelmed by rapid ContextSink upserts | Boundary 6 | Medium | Medium | Bounded retry + quarantine on upsert failure | No rate limiter on ContextSink |
| D-5 | Safety gate `/safety-gate/audit-log` queried with very large `limit` (DoS) | Boundary 5 | Low | Low | `Query(..., ge=1, le=10000)` — FastAPI enforces max 10000 | None |
| D-6 | ESP32 bridge command queue flooded (8-slot queue) | Boundary 3 | Medium | Medium | `queue_full` status returned immediately; `kCommandQueueCapacity=8` | No broker-side rate limiting enforced |

### 3.6 E — Elevation of Privilege

> Threat: An attacker gains capabilities they are not authorized to have.

| # | Threat | Service Boundary | Likelihood | Impact | Mitigations | Gap |
|---|--------|-----------------|-----------|--------|-------------|-----|
| E-1 | Auth bypass: `SAFETY_OPERATOR_TOKEN` guessed via brute force | Boundary 5 | Low | **Critical** | `secrets.compare_digest` (timing-safe); 503 when token not set | **No rate limiting on auth-protected endpoints** |
| E-2 | Command topic ACL failure: authorized MQTT client publishes to a device it does not own | Boundary 3 | Medium | **Critical** | ADR-0010 ACL proposal: bridge credentials scoped per `{deviceId}` | **Broker ACL not yet verified as enforced** |
| E-3 | WebSocket unauthenticated client issues commands (if WebSocket used for commands) | Boundary 5 | **High** | **Critical** | WebSocket currently read-only; no command endpoint | Must not add command dispatch via WebSocket without auth |
| E-4 | FIWARE NGSI-LD injection: malicious `@context` or entity property overwrites system entities | Boundary 6 | Medium | **Critical** | Schema validation before upsert; entity ID stability enforced | Orion-LD write endpoint not yet behind reverse proxy |
| E-5 | ESP32 bridge firmware extracted, modified, and reflashed (no secure boot) | Boundary 2 | Low (requires physical) | **Critical** | JTAG fuse disable recommended; production checklist | **Secure boot not enabled** |
| E-6 | SSRF: Orion-LD subscription callback points to internal service (168.0.0.0/8, 10.0.0.0/8) | Boundary 6 | Medium | **Critical** | ADR-0014 F3: subscription endpoint validation; callback SSRF/rate limits | Not yet implemented |

---

## 4. Attack Surfaces

### 4.1 MQTT Bridge (ESP32 ↔ Broker)

| Surface | Vector | Severity | Control |
|---------|--------|----------|---------|
| MQTT command topic subscribe | Malformed JSON, unknown command, out-of-range args | **Critical** | ✅ Command allowlist, JSON schema validation, MEGA hard limits |
| MQTT telemetry topic publish | Poisoned readings, replayed frames | High | Partial: no TLS |
| UART AMLP egress | Truncated/malformed frames | High | ✅ CRC-16/CCITT-FALSE, inter-byte timeout 250ms |
| UART ACK ingress | Fake ACK frames | Medium | ✅ CRC validation, sequence correlation |
| Wi-Fi transport | Evil twin, credential theft | **Critical** | ⚠️ WPA2/WPA3 only; no TLS on MQTT |
| ESP32 programming interface | JTAG read of firmware/NVS | **Critical** | ⚠️ eFuse PROTECT_JTAG recommended but not verified |
| Command deduplication bypass | Replay within 16-entry FIFO window | Low | Partial: no minimum reuse window guarantee |

### 4.2 MQTT Broker

| Surface | Vector | Severity | Control |
|---------|--------|----------|---------|
| Client authentication | Credential brute force | **Critical** | ⚠️ Username/password implemented; no rate limiting documented |
| Topic ACL enforcement | Unauthorized cross-device publish/subscribe | **Critical** | ⚠️ Proposed in ADR-0010; not yet verified as enforced |
| TLS termination | None currently | **Critical** | ⚠️ No TLS on port 1883; port 8883 not yet configured |
| Client ID collision | Session hijacking | Medium | Unique client IDs required per ADR-0010 |

### 4.3 IoT Gateway REST API

| Surface | Vector | Severity | Control |
|---------|--------|----------|---------|
| `/safety-gate/*` endpoints | Token brute force, token theft | **Critical** | ✅ Timing-safe comparison; 503 when unconfigured |
| `/incidents/*` endpoints | Token brute force, token theft | **Critical** | ✅ Same token auth as safety gate |
| `/events`, `/snapshot` | Data enumeration, information disclosure | Medium | ⚠️ **No auth on read endpoints** |
| `/health`, `/metrics` | Service enumeration | Low | Open; low risk |
| Pydantic validation | Malformed payload causing crash/exception | Low | ✅ FastAPI/Pydantic validation enforced |

### 4.4 WebSocket Server

| Surface | Vector | Severity | Control |
|---------|--------|----------|---------|
| Connection acceptance | Any client on network connects | **High** | ⚠️ **No connection authentication** |
| Message broadcast | Injection via gateway-initiated events only | Low | ✅ Gateway is sole message source; clients receive read-only |
| Client queue saturation | Slow client fills 64-event queue | Medium | ✅ Lagging clients disconnected |
| Connection hijacking | No origin validation or subprotocol negotiation | Medium | ⚠️ No `Sec-WebSocket-Protocol` enforcement |
| Memory exhaustion | Many simultaneous slow clients | Medium | ⚠️ **No per-IP or global connection limit** |

### 4.5 FIWARE Orion-LD Context Broker

| Surface | Vector | Severity | Control |
|---------|--------|----------|---------|
| NGSI-LD PATCH/UPSERT | Malformed entity, injection | **Critical** | ⚠️ Write endpoint not behind reverse proxy; no auth verified |
| NGSI-LD `@context` fetch | SSRF via remote context URL | **Critical** | ⚠️ Not yet implemented; must be local only |
| Subscription callback registration | SSRF to private IP ranges | **Critical** | ⚠️ Not yet implemented |
| MongoDB credentials | Default/weak credentials | **Critical** | ⚠️ Not yet documented in deployment |
| Subscription rate limit | High-frequency notifications DoS | Medium | ⚠️ Not yet implemented |

### 4.6 Alert Webhooks

| Surface | Vector | Severity | Control |
|---------|--------|----------|---------|
| Webhook URL resolution | SSRF via `allowed_hosts` bypass | **Critical** | ✅ Fail-closed when unset; strict hostname match; `allow_redirects=False` |
| URL credential leakage | Credentials in URL path/query logged | Medium | ✅ Tested: no `://` or credentials in logs |
| Webhook response parsing | OOB, XXE from webhook response | Low | ⚠️ Current code does not parse response body |

### 4.7 Dashboard (React)

| Surface | Vector | Severity | Control |
|---------|--------|----------|---------|
| Browser XSS via WebSocket messages | Malicious event payload rendered in UI | Medium | ⚠️ React escapes by default; must verify no `dangerouslySetInnerHTML` |
| Browser session cookies | XSS-triggered authenticated requests | Medium | ✅ PR #242 uses `Secure`, `httpOnly`, `SameSite=Strict` access/refresh cookies; login response contains user data only and dashboard source stores no token material in `localStorage`/`sessionStorage`. ⚠️ Cookie authentication makes CSRF a remaining risk if cross-site cookie delivery/CORS or `SameSite` settings are relaxed; no end-to-end browser deployment verification is recorded. |
| Dashboard → Gateway REST calls | CSRF with browser cookies | Medium | ⚠️ `SameSite=Strict` reduces cross-site sends in PR #242, but no dedicated CSRF token or Origin/Referer validation is present in the inspected auth routes; production cookie/CORS deployment remains unverified. |
| Dashboard → MQTT commands | Command injection | **Critical** | Commands go through broker ACL + ESP32 validation; dashboard not privileged |

---

## 5. Abuse Cases

### 5.1 ABUSE-001: Command Injection via MQTT

**Threat:** Attacker publishes a malicious command to `smart-factory/{deviceId}/command/down` to execute an unauthorized actuator action.

**STRIDE:** T (Tampering), E (Elevation of Privilege)

**Preconditions:** Attacker has MQTT broker credentials or network access.

**Attack flow:**
1. Attacker authenticates to MQTT broker (S-1).
2. Attacker publishes `{"id": 999, "command_name": "RESET", "arguments": []}` to `smart-factory/victim-bridge/command/down`.
3. ESP32 bridge receives command; `CommandMapper` validates `command_name` is in allowlist; `RESET` is in allowlist.
4. Command forwarded to MEGA; MEGA executes RESET.

**Existing controls:**
- ✅ ESP32 command allowlist: only 5 tokens accepted (`CONVEYOR_START`, `CONVEYOR_STOP`, `RESET`, `PING`, `SET_OUTPUT`)
- ✅ Argument range validation: speed 1–100, channel 0–255, value `"0"` or `"1"`
- ✅ JSON structure validation: `deserializeJson` must succeed
- ✅ String length limit: max 64 bytes per field
- ✅ Allowed character filter: printable ASCII 0x21..0x7E; prohibited `,`, `*`, `@`, CR, LF
- ✅ Duplicate dedup: 16-entry FIFO cache; silently dropped
- ✅ Queue capacity: 8 entries max; `queue_full` returned immediately
- ✅ ADR-0010 broker ACL proposal: bridge credentials scoped per `{deviceId}`

**Gaps:**
- ⚠️ No TLS — credentials and payload in cleartext on LAN
- ⚠️ ADR-0010 broker ACL not yet verified as enforced
- ⚠️ No command signing or MAC

**Mitigation priority:** P1 — enforce broker ACL before production; P2 — add TLS

### 5.2 ABUSE-002: SSRF via Alert Webhook

**Threat:** Attacker tricks the gateway into making HTTP requests to internal services or external targets via the webhook URL resolution.

**STRIDE:** I (Information Disclosure), E (Elevation of Privilege), D (Denial of Service)

**Preconditions:** Alert is triggered; attacker can influence alert destination URL (if configurable).

**Attack flow (hostname allowlist bypass):**
1. Attacker sets `allowed_hosts` to `trusted.example.com`.
2. Attacker registers webhook URL `https://trusted.example.com` with DNS pointing to `169.254.169.254` (AWS metadata).
3. Gateway resolves `trusted.example.com`, gets IP `169.254.169.254`, sends alert payload.
4. AWS credentials or internal metadata leaked.

**Existing controls:**
- ✅ `WebhookNotification` fail-closed when `allowed_hosts` unset/empty
- ✅ Strict hostname match (not netloc); userinfo stripped via `parsed.hostname`
- ✅ Port stripped before comparison; subdomain not matched
- ✅ `allow_redirects=False` enforced
- ✅ Case-insensitive comparison
- ✅ No raw URL/credentials in logs (verified by `test_ssrf.py`)
- ✅ Per-instance `allowed_hosts` override takes precedence

**Gaps:**
- ⚠️ `SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS` env var can only be a comma-separated list (no CIDR notation)
- ⚠️ No DNS rebinding protection (TTL not checked)
- ⚠️ No `http://` scheme restriction (only `https://` should be allowed in production)

**Mitigation priority:** P1 — add DNS rebinding protection (check A record TTL or resolve immediately before use); P2 — restrict to `https://` only

### 5.3 ABUSE-003: Telemetry Poisoning

**Threat:** Attacker publishes false telemetry readings to corrupt sensor data, mislead AI inference, or trigger unintended safety gate decisions.

**STRIDE:** T (Tampering), I (Information Disclosure)

**Preconditions:** Attacker has MQTT credentials or LAN access to broker.

**Attack flow:**
1. Attacker publishes `{"event_type": "telemetry", "device_id": "conveyor-01", "payload": {"speed": 9999, "temperature": -273}}` to `smart-factory/bridge-001/telemetry`.
2. `EventNormalizer.normalize()` processes the message.
3. Event persisted to SQLite with malformed payload; `stale: false` set by default.
4. Downstream consumers (Twin, AI) receive corrupted state.

**Existing controls:**
- ✅ ESP32 bridge only publishes telemetry (attacker would need bridge credentials)
- ✅ `EventNormalizer.normalize()` discards messages that fail JSON deserialization
- ✅ Pydantic models in `models.py` enforce `EventType` enum
- ✅ ADR-0010: bridge credentials scoped per `{deviceId}` (prevents cross-device injection)

**Gaps:**
- ⚠️ No payload schema validation in `EventNormalizer` — arbitrary JSON accepted
- ⚠️ No telemetry signing or HMAC from bridge
- ⚠️ No timestamp validation in gateway normalizer (ESP32 monotonic millis vs UTC)
- ⚠️ `stale` flag is set based on latency calculation, not source attestation

**Mitigation priority:** P2 — add telemetry payload schema validation; P3 — add HMAC from bridge

### 5.4 ABUSE-004: Auth Bypass — Safety Gate

**Threat:** Attacker bypasses operator authentication on safety-gate endpoints to trigger emergency stop or interlock release.

**STRIDE:** E (Elevation of Privilege), S (Spoofing)

**Preconditions:** `SAFETY_OPERATOR_TOKEN` is configured; attacker does not know it.

**Attack flow (brute force):**
1. Attacker sends POST to `/safety-gate/emergency-stop` with random token values.
2. Without rate limiting, 1000 guesses could be tried per second.
3. Eventually correct token guessed.

**Existing controls:**
- ✅ Timing-safe comparison via `secrets.compare_digest` — prevents timing oracle
- ✅ 503 returned when `SAFETY_OPERATOR_TOKEN` not configured — no bypass
- ✅ `require_operator_token` shared dependency used on all safety/incident endpoints

**Gaps:**
- ⚠️ **No rate limiting on auth-protected endpoints** — brute force feasible
- ⚠️ No failed auth attempt lockout
- ⚠️ No audit log of failed auth attempts
- ⚠️ `SAFETY_OPERATOR_TOKEN` in env var — not in secrets manager

**Mitigation priority:** P1 — add rate limiting to auth-protected endpoints (e.g., 5 failed attempts → 60s backoff)

### 5.5 ABUSE-005: Denial of Service — Write Queue Exhaustion

**Threat:** Attacker floods the MQTT broker with telemetry messages to exhaust the gateway write queue, causing legitimate events to be dropped.

**STRIDE:** D (Denial of Service)

**Preconditions:** Attacker has MQTT credentials or LAN access to broker.

**Attack flow:**
1. Attacker publishes 501+ messages rapidly to `smart-factory/+/telemetry`.
2. Gateway `write_queue` (maxsize=500) fills up.
3. `_on_mqtt_message` calls `put_nowait` → `QueueFull` → event dropped, `dropped_count` incremented.
4. Legitimate events from the bridge are dropped.
5. `/health` shows `queue_dropped_count` incrementing; no alert currently fired.

**Existing controls:**
- ✅ Bounded queue (500 events)
- ✅ Lagging WebSocket clients disconnected (not a DoS vector)
- ✅ `dropped_count` exposed in `/health`
- ✅ Logging on drop: `logger.warning("Write queue full — event dropped")`

**Gaps:**
- ⚠️ **No MQTT topic-level rate limiting at broker**
- ⚠️ **No alert generated when queue drops events** — silent degradation
- ⚠️ No back-pressure signal to MQTT broker

**Mitigation priority:** P1 — add alert when `dropped_count` increases; P2 — add broker-side rate limiting

### 5.6 ABUSE-006: WebSocket Unauthorized Access

**Threat:** Attacker connects to the gateway WebSocket without credentials and receives all factory events in real time.

**STRIDE:** I (Information Disclosure), S (Spoofing)

**Preconditions:** Attacker has network access to gateway WebSocket port.

**Attack flow:**
1. Attacker connects to `ws://gateway:8000/`.
2. Gateway accepts connection; adds client to `_client_queues`.
3. All future events (telemetry, status, command ACKs) broadcast to attacker.
4. Attacker learns factory operational state, device IDs, command patterns.

**Existing controls:**
- ✅ WebSocket currently read-only (no command dispatch via WS)
- ✅ Client receives only broadcast events; cannot send to others

**Gaps:**
- ⚠️ **No WebSocket authentication or origin validation**
- ⚠️ **No connection limit per IP**
- ⚠️ No TLS on WebSocket (ws:// vs wss://)

**Mitigation priority:** P1 — add WebSocket auth token (query param or subprotocol); P2 — add connection limit

### 5.7 ABUSE-007: FIWARE Orion-LD SSRF / Context Injection

**Threat:** Attacker registers a malicious Orion-LD subscription callback or injects a hostile `@context` to pivot to internal services.

**STRIDE:** I (Information Disclosure), E (Elevation of Privilege), D (Denial of Service)

**Preconditions:** Attacker can reach Orion-LD API port (1026).

**Attack flow (subscription callback SSRF):**
1. Attacker calls `POST /ngsi-ld/v1/subscriptions` with `notification.endpoint.url` = `http://169.254.169.254/latest/meta-data/`.
2. Orion-LD delivers notification to internal AWS metadata endpoint.
3. IAM credentials exposed.

**Existing controls:**
- ⚠️ **No subscription endpoint validation currently implemented** (per ADR-0014 F3)
- ✅ ADR-0014 explicitly requires "subscription endpoint validation; callback SSRF/rate limits"

**Gaps:**
- ⚠️ Orion-LD write endpoint not behind reverse proxy auth
- ⚠️ MongoDB credentials not documented
- ⚠️ `@context` fetch restriction not implemented

**Mitigation priority:** P1 — deploy Orion-LD behind reverse proxy with auth; P1 — implement callback URL validation (block private IP ranges)

### 5.8 ABUSE-008: MQTT Replay Attack

**Threat:** Attacker captures valid MQTT command frames and replays them to execute duplicate commands within the dedup window.

**STRIDE:** T (Tampering), R (Repudiation)

**Preconditions:** Attacker captures MQTT traffic on LAN (no TLS).

**Attack flow:**
1. Attacker wiresharks `smart-factory/bridge/command/down` and captures `{"id": 42, "command_name": "CONVEYOR_START", "arguments": ["80"]}`.
2. Attacker replays this message to the broker.
3. ESP32 receives duplicate `id=42`; checks 16-entry dedup cache.
   - If cache is empty or `id=42` evicted → command re-executed.
   - If `id=42` still cached → silently dropped (no re-execution).
4. Conveyor starts again.

**Existing controls:**
- ✅ 16-entry FIFO dedup cache on bridge
- ✅ MEGA has 8-entry dedup cache
- ⚠️ No cryptographic command signing — replay possible with captured packet

**Gaps:**
- ⚠️ **No command signing or HMAC** — any captured packet replayable within window
- ⚠️ Dedup window is throughput-dependent; at high command rates window shrinks
- ⚠️ No per-command TTL enforcement in bridge firmware

**Mitigation priority:** P2 — add HMAC command signing; P2 — enforce TTL in bridge firmware

---

## 6. Existing Controls and Gaps

### 6.1 Control Status Summary

| Control | Status | Evidence |
|---------|--------|----------|
| ESP32 command allowlist (5 tokens) | ✅ Implemented | `CommandMapper::build()` |
| ESP32 argument range validation | ✅ Implemented | `CommandMapper::validSpeed()`, `validChannel()` |
| ESP32 fail-closed on auth (no empty creds) | ✅ Implemented | `connectOnce()` guard |
| ESP32 JSON structure validation | ✅ Implemented | `deserializeJson` |
| ESP32 AMLP CRC-16 | ✅ Implemented | `crc16_ccitt_false()` |
| ESP32 UART inter-byte timeout (250ms) | ✅ Implemented | AMLP parser |
| ESP32 deduplication (16-entry FIFO) | ✅ Implemented | `BridgeCore` `recent_[]` cache |
| ESP32 queue capacity (8) | ✅ Implemented | `kCommandQueueCapacity=8` |
| MEGA hard actuator limits | ✅ Implemented | MEGA uKit reference firmware |
| MQTT username/password auth | ✅ Implemented | `PubSubClient::connect()` |
| MQTT broker ACL proposal | ⚠️ Proposed | ADR-0010 |
| ESP32 fail-closed with empty MQTT credentials | ✅ Implemented | Anonymous connection prevented |
| ESP32 LWT (online/offline) | ✅ Implemented | `connectOnce()` |
| Gateway write queue bounded (500) | ✅ Implemented | `gateway.py` `QUEUE_SIZE=500` |
| Gateway queue overflow drop counter | ✅ Implemented | `dropped_count_ref` |
| WebSocket queue limit (64/client) | ✅ Implemented | `MAX_QUEUE_PER_CLIENT=64` |
| WebSocket lagging client disconnect | ✅ Implemented | `broadcast()` disconnect logic |
| REST endpoint rate limit (max 10000) | ✅ Implemented | FastAPI `Query(..., le=10000)` |
| Safety gate timing-safe token compare | ✅ Implemented | `secrets.compare_digest` |
| Safety gate fail-closed when token unset | ✅ Implemented | 503 on missing `SAFETY_OPERATOR_TOKEN` |
| Safety gate default-deny | ✅ Implemented | `SafetyGate.evaluate()` |
| Safety gate audit log (no args) | ✅ Implemented | ADR-0013 §Audit Trail |
| Webhook SSRF fail-closed (empty allowlist) | ✅ Implemented | L1: `test_security_abuse.py::TestSSRFWebhookNotification` (mocked HTTP via aioresponses) |
| Webhook strict hostname allowlist | ✅ Implemented | L1: `test_security_abuse.py::TestSSRFWebhookNotification` (mocked HTTP via aioresponses) |
| Webhook `allow_redirects=False` | ✅ Implemented | L1: `test_security_abuse.py::TestSSRFWebhookNotification` (mocked HTTP via aioresponses) |
| Webhook hostname normalization (strip userinfo/port) | ✅ Implemented | L1: `test_security_abuse.py::TestSSRFWebhookNotification` (mocked HTTP via aioresponses) |
| No raw URL/credentials in webhook logs | ✅ Implemented | L1: `test_security_abuse.py::TestSSRFWebhookNotification` (mocked HTTP via aioresponses) |
| Orion-LD write endpoint auth | ⚠️ Not yet implemented | ADR-0014 F3 |
| Orion-LD subscription callback SSRF protection | ⚠️ Not yet implemented | ADR-0014 F3 |
| Orion-LD `@context` local-only | ⚠️ Not yet implemented | ADR-0014 §Deployment |
| WebSocket authentication | ⚠️ **Not implemented** | **Gap** |
| MQTT TLS (port 8883) | ⚠️ **Not implemented** | `WiFiClient` used; `WiFiClientSecure` not wired |
| ESP32 TLS hostname verification | ⚠️ **Not implemented** | `setCACert()` not called |
| MQTT topic rate limiting | ⚠️ **Not implemented** | No broker-side rate limit |
| Auth endpoint rate limiting | ⚠️ **Not implemented** | **Gap** |
| WebSocket connection limit | ⚠️ **Not implemented** | **Gap** |
| Command HMAC signing | ⚠️ **Not implemented** | **Gap** |
| ESP32 secure boot / flash encryption | ⚠️ **Not verified** | Recommended in production checklist |
| Telemetry payload schema validation | ⚠️ **Not implemented** | Arbitrary JSON accepted |
| Dropped event alert | ⚠️ **Not implemented** | Silent degradation |
| Orion-LD MongoDB credentials | ⚠️ **Not documented** | ADR-0014 F3 |

---

## 7. Risk Summary

### 7.1 Risk Matrix

| Risk | Likelihood | Impact | Risk Score | Priority |
|------|-----------|--------|------------|---------|
| No TLS on MQTT (credentials + payload in cleartext) | Medium | **Critical** | **9** | **P1** |
| No WebSocket authentication (factory state disclosure) | **High** | Medium | **6** | **P1** |
| No auth endpoint rate limiting (token brute force) | Low | **Critical** | **6** | **P1** |
| Orion-LD write endpoint unauthenticated | Medium | **Critical** | **8** | **P1** |
| Orion-LD subscription callback SSRF | Medium | **Critical** | **8** | **P1** |
| No MQTT topic rate limiting (queue DoS) | Medium | High | **6** | **P1** |
| Telemetry poisoning (no payload validation) | Medium | **Critical** | **7** | **P2** |
| MQTT replay attack (no command signing) | Low | High | **4** | **P2** |
| ESP32 firmware extraction (no secure boot) | Low | **Critical** | **5** | **P2** |
| Command topic ACL not enforced | Medium | **Critical** | **8** | **P1** |
| Webhook DNS rebinding | Low | **Critical** | **5** | **P2** |
| No dropped event alerting (silent DoS) | Medium | Medium | **4** | **P2** |

### 7.2 Mitigations Roadmap

| Priority | Action | Threat(s) Addressed | Owner |
|----------|--------|---------------------|-------|
| **P1** | Enforce MQTT broker ACL (ADR-0010) | E-2, ABUSE-001 | Platform/Ops |
| **P1** | Add rate limiting to auth endpoints | E-1, ABUSE-004 | Gateway |
| **P1** | Add WebSocket authentication | S-3, ABUSE-006 | Gateway |
| **P1** | Wire ESP32 TLS (WiFiClientSecure) | S-1, S-2, T-1, ABUSE-001 | ESP32 firmware |
| **P1** | Deploy Orion-LD behind reverse proxy + auth | E-4, ABUSE-007 | Platform/Ops |
| **P1** | Implement Orion-LD subscription SSRF protection | ABUSE-007 | Platform/Ops |
| **P1** | Add dropped event alerting | D-1, ABUSE-005 | Gateway |
| **P2** | Add telemetry payload schema validation | T-1, ABUSE-003 | Gateway |
| **P2** | Add MQTT topic rate limiting | D-1, ABUSE-005 | Broker |
| **P2** | Add HMAC command signing | T-2, ABUSE-001, ABUSE-008 | ESP32 + Gateway |
| **P2** | Enable ESP32 secure boot + flash encryption | E-5 | ESP32 firmware |
| **P2** | Add Webhook DNS rebinding protection | ABUSE-002 | Gateway |
| **P3** | Add WebSocket connection limit per IP | D-2, ABUSE-006 | Gateway |
| **P3** | Document MongoDB credentials policy | E-4 | Platform/Ops |
| **P3** | Implement ESP32 TTL enforcement for commands | ABUSE-008 | ESP32 firmware |

---

## 8. Threat Modelling Methodology

### 8.1 Framework

This threat model uses **STRIDE** (Microsoft, 1999) applied per service boundary. STRIDE categorises threats into six classes:
- **S**poofing — impersonating another entity
- **T**ampering — modifying data or code
- **R**epudiation — denying having taken an action
- **I**nformation disclosure — exposing information to unauthorised parties
- **D**enial of service — denying or degrading service to legitimate users
- **E**levation of privilege — gaining capabilities without authorisation

### 8.2 Service Boundaries Modelled

1. **Boundary 1–2: Physical / UART (Mega ↔ ESP32)** — Low risk; physically bounded
2. **Boundary 3–4: MQTT (ESP32 ↔ Broker ↔ Gateway)** — High risk; network-exposed
3. **Boundary 5: Gateway REST/WebSocket** — Medium risk; public HTTP interface
4. **Boundary 6: FIWARE Orion-LD** — High risk; new service, not yet hardened
5. **Boundary 7: Alert Webhooks** — Medium risk; outbound HTTP

### 8.3 Evidence Levels

Threat model evidence follows the L0–L5 scale from `docs/experiment-baselines.md`:

| Level | Description |
|-------|-------------|
| L0 | Static analysis / design review only |
| L1 | Unit tests, static analysis (SAST), code review |
| L2 | Integration tests, simulation |
| L3 | Bench / isolated environment |
| L4 | Hardware-in-the-loop |
| L5 | Full integrated physical deployment |

### 8.4 Review Triggers

This threat model must be reviewed when:
- A new service boundary is introduced
- A new ADR is accepted that changes security posture
- A security incident or near-miss occurs
- A major version bump of MQTT broker, ESP32 firmware, or Orion-LD
- Quarterly (minimum)

---

*Document version 1.0 — Issue #179 | Aligns with ADR-0006 §Evidence, ADR-0013 §Integration Gap, ADR-0014 §Failure Behaviour, ADR-0010 §Consequences*
