# ADR-0013: FIWARE Orion-LD Context Architecture

**Status:** Proposed
**Date:** 2026-10-17
**Deciders:** AIBOT Smart Factory engineering team
**Related issues:** #195, #163, #166, #169, #196, #197, #198, #199, #200, #202, #205

## Context

The AIBOT Smart Factory system requires a context broker to materialise and expose the current state of the nine-module physical factory (Forklift, Dump Truck, Bracket, Packaging Machine, Conveyor Belt, Sorting Machine, Tower Crane, Parking Lot, Combine) for consumption by the Unity Digital Twin and React operations dashboard.

The existing Python IoT Gateway ingests telemetry over authenticated MQTT, normalises events, persists them to SQLite, and exposes HTTP REST, WebSocket and metrics endpoints. The gateway's event history is the authoritative record of what happened. A context broker can add a complementary role: a live, queryable view of the current entity state and relationships using NGSI-LD, with support for subscriptions that notify downstream consumers when state changes.

FIWARE Orion-LD implements NGSI-LD and exposes both NGSI-LD and NGSI-v2 APIs. It uses MongoDB as its backing store. The alternative FIWARE Orion implements only NGSI-v2. The two differ significantly: NGSI-LD uses a property/relationship graph model, URN-style entity IDs, a JSON-LD `@context`, and standardised timestamps (`observedAt`). NGSI-v2 uses a flat attribute model and string IDs. NGSI-LD is the future-facing API for linked-data scenarios. Upstream release 1.12.0 (January 2026, develop branch, 15 615 commits) is the latest tagged release. Orion-LD upstream recommends pinned container tags. MongoDB 4.2+ is supported, but the deployment should use a tested, supported MongoDB version with an active security lifecycle rather than copying an old tutorial's image tag.

The Gateway event store (SQLite, MQTT ingestion, REST/WS output) is authoritative for event history and device ingestion. Orion-LD holds only the latest context state and NGSI-LD subscriptions. The two stores serve different purposes and must not be conflated.

## Decision

We adopt **FIWARE Orion-LD as the NGSI-LD context broker** for the AIBOT Smart Factory. The architecture is as follows:

**Topology:**
```
PHYSICAL FIELD                  DATA & CONTROL              CONTEXT & APPLICATION
[uKit Explore V2.0 Mega]
  SDK: motor, servo, sensors
        ↕ AMLP TEL/CMD via safe UART (5V↔3.3V)
[ESP32-S3 bridge]
  identity + WiFi + MQTT + ESP32 OTA
        ↕ authenticated MQTT
[MQTT Broker] ⇄ [Gateway: MQTT ingress → normalize → SQLite event store]
                                     │
                 ┌───────────────────┼──────────────────────────────┐
                 │                   │                              │
        [Gateway REST/WS]  [post-commit ContextSink]        [Gateway Safety/
                 │                   │                       command service]
         Unity + React       NGSI-LD PATCH/UPSERT                   │
                                     │                              ▼
                           [Orion-LD Context Broker]     MQTT CMD→ESP32→Mega
                              │       │         │         (ACK ≠ observed done)
                          [MongoDB] [@context] [Subscriptions]
                              │                │
                      Context API       [Notification Relay]
                                               │
                                       Unity / React /
                                   incident context observer
                                       [Yanshee only via
                                      Gateway approved skills]
```

**Data flows and authority:**
| Flow | Wire interface | Scope of authority |
|------|---------------|-------------------|
| Measurement | UART AMLP TEL → MQTT smart-factory/{bridge_id}/telemetry | Raw physical measurement; source provenance in payload |
| Bridge health | MQTT status/heartbeat | Link health only — not motor operational proof |
| Persist | Gateway → SQLite | Append canonical source events |
| Materialise context | ContextSink → Orion-LD (internal HTTP NGSI-LD) | Update current entity properties after commit |
| Query context | Gateway facade / consumers → Orion-LD (NGSI-LD GET) | Read-only queries through access boundary |
| Subscriptions | Orion-LD → Relay → Unity/React | Versioned WebSocket/read contract; downstream read-only |
| Incident / robot | Gateway approved incident → Yanshee adapter | Policy-controlled; not context-write triggered |
| Physical command | React → Gateway → ESP32 → Mega | Explicitly authorised and locally interlocked |
| Recovery | SQLite → ContextSink → Orion-LD | Durable cursor / backfill to reconcile after outage |

**Central invariants (must be preserved):**
1. Gateway SQLite/event contract is authoritative for event history and device ingestion. Orion-LD holds only the latest context state and subscriptions — it is never the command authority.
2. Physical actuator command intent originates from the authorised Gateway API. A context Property or Relationship update never directly dispatches a command.
3. Device identity and capability registry (#169/#192) is authoritative. Entity IDs are stable. Source time and Gateway receive time must be distinguished, especially for ESP32 monotonic millis.
4. The ContextSink consumes post-persist canonical events (not raw MQTT) with durable checkpoint, idempotent upsert, bounded retry and quarantine. No parallel independent raw-MQTT ingestion writers by default.
5. React and Unity read FIWARE state through an authorised facade or notification relay with snapshot/reconnect logic. The existing Gateway direct REST/WS remains functional for current production and command lifecycle.
6. Yanshee observations and alerts may be represented as context entities, but triggering any robot skill is exclusive to the approved Gateway incident policy (#160/#168).
7. Docker/simulator tests demonstrate L1/L2 only. FIWARE fixture tests do not constitute safe physical actuation evidence.

**NGSI-LD entity graph (proposed stable URNs — final shape approved in #197):**
```
urn:ngsi-ld:Factory:aibot-01
  ├── containsModule → urn:ngsi-ld:Module:conveyor-01
  ├── containsModule → ... (nine-module catalogue items)
  └── containsController → urn:ngsi-ld:Controller:ukit-mega-01
Module:conveyor-01
  ├── partOf → Factory:aibot-01
  ├── controlledBy → Controller:ukit-mega-01
  ├── observedBy → Sensor:<verified_sensor_id> (ONLY IF HARDWARE CONFIRMED)
  ├── hasActuator → Actuator:<verified_actuator_id>
  └── representedBy → DigitalTwin:unity-factory-01
ProductionJob:<job_id> traverses Module:<id>
Alert:<alert_id> concerns Module:<id>
Robot:yanshee-01 reports health/capabilities after SDK verification
```
Nine-module catalogue: Forklift, Dump Truck, Bracket (structural unless instrumented), Packaging Machine, Conveyor Belt, Sorting Machine, Tower Crane, Parking Lot, Combine (orchestration). No synthetic control signals are allowed for Bracket.

**Example NGSI-LD entity (illustrative — needs schema review):**
```json
{
  "id": "urn:ngsi-ld:Module:conveyor-01",
  "type": "Module",
  "name": {"type": "Property", "value": "Conveyor Belt"},
  "operationalState": {
    "type": "Property",
    "value": "UNKNOWN",
    "observedAt": "2026-10-17T00:00:00Z"
  },
  "controlledBy": {
    "type": "Relationship",
    "object": "urn:ngsi-ld:Controller:ukit-mega-01"
  },
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"
  ]
}
```
**WARNING:** The `observedAt` timestamp above is a sample fixture value, not derived from live hardware. Replace with a real, validated timestamp at runtime. Use UNKNOWN until a hardware-confirmed measurement is available. Do not use placeholder timestamps as live data.

**Service boundary and deployment:**
All FIWARE infrastructure is **not yet created**. Recommended structure:
```
infrastructure/fiware/
  compose.fiware.yml        # pinned Orion-LD + supported MongoDB + @context HTTP
  contexts/v1/context.jsonld
  fixtures/v1/factory-entities.json
  scripts/smoke.sh
iot-gateway/src/iot_gateway/fiware/
  context_mapper.py
  context_sink.py
  context_reconciler.py
  settings.py
iot-gateway/tests/test_fiware_*.py
integration-tests/fiware/
  test_context_e2e.py
```
Use existing root network integration, separate lab profile, internal port 1026, protected MongoDB port and volume, pinned Docker images, health/readiness checks, and backup. The `@context` document should be static, versioned and locally controlled; no arbitrary untrusted remote context fetch. The Orion-LD write endpoint must not be placed on a public network without an identity-aware reverse proxy and role scopes (#200).

**Failure behaviour:**
1. Validate MQTT payload provenance, version and time domain; dedupe; persist canonical event in SQLite.
2. After database commit, enqueue a durable ContextSink record keyed by event_id, device_id, boot_id and sequence.
3. Upsert mapped NGSI-LD Properties/Relationships. Advance checkpoint only after confirmed Orion response.
4. If Orion/Mongo is unavailable, keep Gateway ingestion, read API and safety working. Retain outbox health visibility. Resume and reconcile from the authoritative log — avoid infinite cache/memory.
5. Prevent stale context revision overwriting newer state: compare boot identity + sequence and timestamp domains.
6. For Unity/React consumers: authorised snapshot and notifications, verify high-watermark, reconnect/resync on gap, show UNKNOWN/STALE when context is not freshly updated.
7. Context-based commands and autonomous actuation are **not enabled**. A context attribute value `RUNNING` is not proof of motor movement.

**Scope separation:**
- **IoT Agent JSON/MQTT (#203)** is optional. Its default device topic and provisioning format differ from the existing `smart-factory/{id}/...` scheme. Do not attach directly to duplicate Gateway ingestion/command ownership. POC only.
- **Temporal/history (#201)** is optional after measurement requirements. SQLite already retains canonical source events.
- **FIWARE security (#200)** must cover reverse proxy authentication, per-service rights, internal network, subscription endpoint validation, and callback SSRF/rate limits.
- **Integration tests (#202)** must cover Orion outage/restart, subscriber restart, invalid JSON-LD, ESP32 boot/clock resets, provenance, faulty commands, and correct reconciliation.

**Execution phases:**
- F0: architecture/ADR #195, master nine-flow #163, telemetry schema #166, registry #169.
- F1: broker #196 and entity graph #197.
- F2: Gateway sink #198, durable ingest #165, registry enrolment #192.
- F3: subscriber #199, security #200, Unity #176/#190, React #148/#150.
- F4: E2E #202, physical benches as separately authorised.
- F5: optional temporal #201, IoT Agent #203, Yanshee context #204.

**Initial verification level:** L2 simulator/lab. L3–L5 HIL requires existing #98/#173/#181 and hardware safety sign-off.

## Consequences

**Positive:**
- Gateway retains authoritative event history; Orion-LD adds a live, queryable, subscription-driven context layer without replacing either.
- NGSI-LD property/relationship graph maps naturally to the nine-module factory entity hierarchy.
- Subscription model enables reactive UI updates in Unity and React without polling.
- Observable FIWARE ecosystem (Orion-LD, Scorpio, Stellio) provides a path to multi-broker federation.
- Clear separation of concerns: ContextSink writes only after gateway commit; Orion never drives commands.

**Negative / risks:**
- Adds a new service dependency (Orion-LD + MongoDB) that must be operated, upgraded, secured and monitored.
- The `@context` vocabulary requires governance to avoid drift from FIWARE data models.
- Synchronisation lag between SQLite event commit and Orion-LD upsert can produce transient inconsistency windows; consumers must handle this (snapshot + UNKNOWN/STALE states).
- Orion-LD uptime affects the quality of the context view but must not affect the gateway's ability to ingest, store and command.
- IoT Agent (#203) could be mistaken for a replacement gateway; explicit scope separation is required.

**Neutral:**
- ADR does not commit implementation budget. Each subsequent phase requires its own issue, PR and (for architectural changes) additional ADR.
- ADR status is `Proposed` — no implementation PR may be merged against FIWARE architectural surface until architect review and evidence recording.

## Alternatives considered

**Alternative A — FIWARE Orion (NGSI-v2)**
NGSI-v2 is simpler and has wider existing deployment base. However, it uses a flat attribute model without relationships or JSON-LD `@context`, does not support the property-graph entity model we need for the nine-module factory hierarchy, and is being superseded by NGSI-LD in the FIWARE ecosystem. No ADR-triggering reason to prefer it over Orion-LD.

**Alternative B — Scorpio or Stellio NGSI-LD brokers**
Both support NGSI-LD. Scorpio is Java-based; Stellio is Kotlin/Spring Boot. Orion-LD (C++/MongoDB) is the most widely deployed and documented FIWARE broker, with a larger community and more tutorial coverage. Scorpio and Stellio remain viable for future multi-broker or Kubernetes-native scenarios, but Orion-LD is the appropriate initial choice for a lab/simulator environment.

**Alternative C — No context broker; extend Gateway REST/WS only**
The existing Gateway REST/WS API already exposes current state. A context broker adds NGSI-LD subscriptions, a formal entity model, and a standardised query language. The cost of adoption (new service, MongoDB, ContextSink development) is justified by the requirements for Unity/React reactive updates and a future-proof linked-data entity model. This ADR does not retroactively block continuing with the current gateway-only approach for command lifecycle.

## Evidence

- [FIWARE Orion-LD GitHub repository — active development (15 615 commits, latest release 1.12.0, January 2026)](https://github.com/FIWARE/context.Orion-LD)
- [FIWARE NGSI-LD Tutorials — Smart Farm walkthrough, Docker Compose examples, Postman collections](https://github.com/FIWARE/tutorials.NGSI-LD)
- [FIWARE Data Models NGSI-LD FAQ — official property graph model, @context guidance, entity examples](https://fiware.github.io/data-models/specs/ngsi-ld_faq.html)
