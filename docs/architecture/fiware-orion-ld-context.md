# FIWARE Orion-LD Context Architecture for Smart Factory
**Status: DESIGN PROPOSAL — not deployed; ADR approval required (#195).**
**Scope:** AIBOT Smart Factory 9-module physical factory, ESP32–uKit Explore V2.0/Mega, Python IoT Gateway, Unity Digital Twin, React operations dashboard and UBTECH Yanshee. Maintains the S1/S2/S3 architecture and adds FIWARE as supporting context infrastructure, not a new physical or AI principal subsystem.
**Audit baseline:** 2026-10-17 master. No FIWARE implementation present. Existing Gateway has MQTT four-topic subscription, normalized events, SQLite, HTTP /events /snapshot /metrics, standalone WebSocket. See #163–#170.

## 1. Architecture decision under review
Prefer **Orion-LD implementing NGSI-LD**, with property/relationship graph, observedAt and linked-data @context. Alternative original FIWARE Orion implements NGSI-v2; compare in #195 against tested deployment/runtime/API support, maturity and institutional requirements. Do not declare ADR Accepted until approved. Orion-LD upstream recommends pinned container tags, not latest; observed upstream release 1.12.0 (January 2026), compatibility and Docker artifacts must be verified at implementation. Supports MongoDB 4.2+ per upstream docs, but choose tested supported MongoDB major/security lifecycle rather than blindly copying tutorial's old mongo:4.2 example.

**Central invariants:**
1. Gateway SQLite/event contract is authoritative **event history and device ingestion**. Orion-LD holds materialized latest **context state** and NGSI-LD subscriptions, not motor command authority or a substitute for event store.
2. Physical actuator command intent originates from authorized Gateway API; server policy and device-local Mega E-stop/watchdog still gate execution. A context Relationship/Property update never directly dispatches a command.
3. Device identity and capability registry (#169/#192) is authoritative; entity IDs are stable mappings. Source time and Gateway receive time must be distinguished, especially ESP32 monotonic millis.
4. ContextSink consumes **post-persist canonical** Gateway events with durable checkpoint/outbox, idempotent updates, retry and quarantine; no parallel independent raw-MQTT ingestion writers by default.
5. React/Unity read FIWARE state through authorized facade/notification relay with snapshot/reconnect logic. Existing Gateway direct REST/WS stays functional for current production/command lifecycle.
6. Yanshee observations and alerts may be represented as context. Triggering any robot skill is exclusive to approved Gateway incident policy (#160/#168), not Orion subscription alone.
7. No false L3/L4/L5 hardware status: FIWARE fixture or Docker tests demonstrate L1/L2, not safe physical actuation.

## 2. System topology
```text
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

## 3. Source roles and transport matrix
| Flow | Origin / Destination | Wire interface | Scope of authority |
|---|---|---|---|
| Measurement | Mega→ESP32→Gateway | UART AMLP TEL → MQTT smart-factory/{bridge_id}/telemetry | raw physical measurement with source provenance |
| Bridge health | ESP32→Gateway | MQTT status/heartbeat | link health (not motor operational proof) |
| Persist | Gateway→SQLite | local transaction + sequence | append canonical source events |
| Materialize context | ContextSink→Orion-LD | internal authenticated HTTP NGSI-LD | update current entity properties |
| Query context | Gateway facade/read consumers→Orion-LD | NGSI-LD GET via access boundary | query entities and relationships |
| Subscriptions | Orion-LD→Relay→Unity/React | NGSI-LD notification → versioned WS/read contract | downstream read-only context change |
| Incident/robot | Gateway approved incident→Yanshee adapter | typed bounded skill and feedback | policy-controlled, not context-write triggered |
| Physical command | React operator→Gateway→ESP32→Mega | auth HTTP intent → ACL MQTT CMD → AMLP | explicitly authorized and locally interlocked |
| Recovery | SQLite→ContextSink→Orion | durable cursor/backfill | reconcile current context after broker outage |

## 4. NGSI-LD entity graph
Propose stable URI-escaped IDs (final shape approved in #197):
```
urn:ngsi-ld:Factory:aibot-01
  ├── containsModule → urn:ngsi-ld:Module:conveyor-01
  ├── containsModule → ... nine module catalogue items ...
  └── containsController → urn:ngsi-ld:Controller:ukit-mega-01
Module:conveyor-01
  ├── partOf → Factory:aibot-01
  ├── controlledBy → Controller:ukit-mega-01
  ├── observedBy → Sensor:<verified_sensor_id> (ONLY IF HARDWARE CONFIRMED)
  ├── hasActuator → Actuator:<verified_actuator_id>
  └── representedBy → DigitalTwin:unity-factory-01
ProductionJob:<job_id> traverses Module:<id> with stage status and trace metadata
Alert:<alert_id> concerns Module:<id> with source event, severity, provenance
Robot:yanshee-01 reports health/capabilities after actual SDK verification
```
Nine module catalogue: Forklift, Dump Truck, Bracket (structural unless instrumented), Packaging Machine, Conveyor Belt, Sorting Machine, Tower Crane, Parking Lot and Combine Modules (orchestration). No synthetic control signals allowed for Bracket.

## 5. Minimal NGSI-LD fixture (illustrative, needs schema review)
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
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "https://context.example.invalid/smart-factory/v1/context.jsonld"
  ]
}
```
**WARNING:** Placeholder observedAt above is a *sample fixture timestamp*, never derived from ESP32 millis. Replace example.invalid with approved local context server and tested expandible vocab document. Do not copy as live data. Use explicit time uncertainty/data quality when the upstream clock is unsynchronized. Modules get UNKNOWN until actually measured.

## 6. Service boundary and deployment
Recommended structure (all **not yet created**):
```text
infrastructure/fiware/
  compose.fiware.yml        # pinned Orion-LD + compatible MongoDB + @context HTTP
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
docs/architecture/fiware-orion-ld-context.md
```
Use existing root network integration, separate lab profile, internal port 1026, protected MongoDB port and volume, pinned Docker images, health/readiness, backup. FIWARE @context should be static, versioned and locally controlled; no arbitrary untrusted remote context fetch.

**Avoid putting open Orion write endpoint on public network.** Broker is a data store/API, not a turnkey auth proxy. Use a tested identity-aware reverse proxy and role scopes (#200). Validate FIWARE service headers only if supported by chosen version. Signed requests and command authority remain in Gateway.

## 7. Failure behavior, synchronization and replay
1. Receive MQTT payload; validate provenance/identity/version/time domain; dedupe; persist canonical event in Gateway SQLite.
2. After database commit, enqueue durable ContextSink record/cursor keyed by event_id, device_id, boot_id and sequence.
3. Upsert mapped NGSI-LD Properties/Relationships. Only advance checkpoint after confirmed Orion update and validated response.
4. If Orion/Mongo unavailable, keep Gateway ingestion, read API and safety working; bounded retry/backoff and explicit outbox/backlog health. Resume and reconcile from authoritative log; avoid infinite cache/memory.
5. If out-of-order per-device event arrives, retain event log but prevent stale context revision overwriting newer state. Compare boot identity + validated sequence and actual timestamp domains.
6. For Unity/React consumers: use authorized snapshot and notifications, verify high-watermark/cursor, reconnect/resync on gap, show UNKNOWN/STALE when latest context is no longer physically fresh.
7. Context-based commands and autonomous actuation are **not enabled**. A context attribute value `RUNNING` is not proof of motor movement, particularly for a mock.

## 8. Scope separation: IoT Agent, temporal, FIWARE security
- **IoT Agent JSON/MQTT (#203) is optional**. Its default device topic and provisioning format differ from existing `smart-factory/{id}/...`; do not attach directly and duplicate Gateway ingestion/command ownership. POC only.
- **Temporal/history (#201) optional** after measurement requirements; SQLite already retains canonical source events. Compare Orion temporal representations and other connectors with real NGSI-LD compatibility before adding databases.
- **FIWARE security (#200)** must cover reverse proxy authentication, per-service rights, internal network, subscription endpoint validation and callback SSRF/rate limits.
- **Integration (#202)** must test Orion outage/restart, subscriber restart, invalid JSON-LD, boot/clock resets, provenance, faulty commands and correct reconciliation.
- **Deployment maturity:** initial target L2 simulator/lab; L3–L5 HIL requires existing #98/#173/#181 and hardware safety signoff.

## 9. Execution order & links
- F0 architecture/ADR #195, master nine-flow #163, telemetry schema #166, registry #169.
- F1 broker #196 and entity graph #197.
- F2 Gateway sink #198, durable ingest #165 and registry enrollment #192.
- F3 subscriber #199 and security #200, Unity #176/#190, React #148/#150.
- F4 E2E #202 and #180, physical benches as separately authorized.
- F5 optional historical #201, IoT Agent #203, Yanshee context #204.
- Epic: #205; program Epic #188.

## Official references
- https://github.com/FIWARE/context.Orion-LD
- https://github.com/FIWARE/tutorials.NGSI-LD
- https://fiware.github.io/data-models/specs/ngsi-ld_faq.html
