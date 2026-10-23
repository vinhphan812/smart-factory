# ADR-0016: FIWARE Context Mapping for Yanshee Notifications and Incident Evidence

**Status:** Proposed
**Date:** 2026-10-23
**Deciders:** AIBOT Smart Factory engineering team
**Related issues:** #204, #195, #196, #197, #198, #199, #200, #160, #178

## Context

Issue #204 asks for FIWARE factory context to be mapped onto Yanshee
notifications, incident evidence and a research API. ADR-0014 already selects
Orion-LD / NGSI-LD as the context broker and fixes the central invariants:
the Gateway event store stays authoritative for event history, Orion-LD holds
only the latest materialised context, and a context change never dispatches a
physical command.

Three gaps remain in the merged state (`origin/master` @ `3d7d7ca`):

1. **No robot entity.** The merged entity schema (`contracts/fiware/ngsi-ld-entity-schema.md`,
   Issue #197) defines `Device`, `Module`, `Job`, `Material`, `Operator`,
   `Alert` and `Incident`, but no `Robot` type. Issue #197 SPEC-1 explicitly
   says the Yanshee robot is to be typed separately as `Robot`, and that was
   never delivered. Without it, robot status, battery and supported actions
   have nowhere to live in context.
2. **No incident projection.** The Gateway owns incidents in
   `iot-gateway/src/iot_gateway/incidents.py`, but there is no projection of
   those incidents onto an NGSI-LD `Alert` entity. Issue #204 SPEC-2 requires
   the projection to carry `trace_id`, source event and operator state so a
   consumer can walk back to the originating Gateway event.
3. **No read-only consumer path.** Issue #198 merged an Orion-LD *writer*
   (`iot-gateway/src/iot_gateway/adapters/orion_ld.py`). There is no read-only
   facade, so a consumer that wants to look at context would have to be
   given write access to the broker — which would create exactly the
   "context write triggers actuation" path that ADR-0014 invariant 2 and
   ADR-0006 forbid.

A further constraint shapes the design: the UBTECH Yanshee SDK has **not** been
audited. Issue #159 (hardware/SDK/network audit) and Issue #160 (typed
adapter) are both open. Any robot status, battery level or supported-action
list that we publish today would therefore be invented, and
`docs/PROJECT_CONTEXT.md` §6 and `AGENTS.md` forbid fabricated figures.

## Decision

We will add a **read-only FIWARE context layer for robot and incident
evidence**, consisting of four versioned pieces:

1. **A `Robot` NGSI-LD entity** produced by
   `iot-gateway/src/iot_gateway/adapters/orion_robot.py`. The mapper takes a
   `RobotCapabilitySource` and emits `status`, `batteryLevel` and
   `supportedActions`. The source declares whether its reading is `verified`.
   **An unverified source yields `UNKNOWN` values plus
   `verificationStatus: UNVERIFIED`** — the mapper actively suppresses a
   concrete status and a concrete action list in that case. The default
   source is `UnverifiedRobotCapabilitySource`, which is what runs until
   Issue #160 delivers a real SDK adapter.

2. **An incident → `Alert` projection** produced by
   `iot-gateway/src/iot_gateway/adapters/orion_incident.py`. It maps a Gateway
   incident onto an NGSI-LD `Alert` carrying `traceId`, `sourceEventId`,
   `sourceSystem`, `incidentId`, `deviceId`, `dataQuality`, `operatorState`
   and the optional `relatedTo` / `relatedToSensor` relationships. The
   projection is a **read model**: it never mutates or replaces the Gateway
   incident store, and it is never the authorization truth.

3. **A read-only context query facade** at
   `iot-gateway/src/iot_gateway/context_query.py`. It exposes NGSI-LD `GET`
   queries only (`get_alert`, `get_alerts`, `get_robot`, `get_robots`,
   `get_entity`, `query_entities`). It has **no** upsert, delete, publish or
   command-forwarding method, and it never talks to MQTT or the bridge. The
   transport is a `ContextTransport` protocol so the read-only guarantee is
   auditable in one place and testable without a broker.

4. **A Yanshee response policy** at
   `edge-ai-robot/src/edge_ai_robot/context/__init__.py`. It consumes the
   facade through a structural `ContextReader` protocol (so
   `edge-ai-robot` does not import `iot-gateway`, honouring the ADR-0001
   boundary rule) and returns an explicit `APPROVED` / `DENIED` / `BLOCKED`
   decision with a machine-readable reason code.

The policy's rules, in evaluation order, are: unknown skill → `DENIED`;
physical-action skill or Yanshee physical topic → `BLOCKED`; missing or
mismatched Gateway approval → `DENIED`; missing alert → `DENIED`; stale or
untimestamped context → `DENIED`; non-actionable alert → `DENIED`; unverified
or missing robot capability → `DENIED`; skill absent from the robot's
verified `supportedActions` → `DENIED`; emergency stop active → `BLOCKED`.
Only a fully-satisfied evaluation yields `APPROVED`.

We further decide that the **notification dispatch path is unchanged**:
robot skills continue to be launched exclusively by the Gateway-approved
incident outbox (`iot-gateway/src/iot_gateway/alert_outbox.py`,
`enqueue_yanshee`). The FIWARE context layer never dispatches a skill; it
only ever *proposes* one, and the proposal requires an explicit Gateway
approval record.

Finally, we decide that **context is not an authorization surface**: no
property, relationship or alert status in Orion-LD may enable, authorise or
suppress a physical action, and the E-stop interlock remains entirely
independent of it.

## Consequences

**Positive:**

- Robot capability and incident evidence become readable by Unity, the React
  dashboard, the robot policy and research reports through one versioned
  NGSI-LD shape, with a single provenance chain back to the Gateway event.
- The "no verified SDK" state is represented honestly. A consumer can tell
  `UNKNOWN` from a measurement, and `SIMULATED` from `PHYSICAL`, so the
  TC-5 requirement is satisfiable at the data level rather than in prose.
- Because the facade has no write method, the class of bug where a context
  change triggers actuation cannot be introduced by adding a consumer. The
  read-only property is enforced by the absence of an API, not by a runtime
  check.
- The `ContextReader` protocol keeps `edge-ai-robot` free of a cross-module
  import, so the ADR-0001 module boundary rule holds without a new contract
  negotiation.

**Negative / risks:**

- This adds a second representation of incidents (Gateway store plus NGSI-LD
  projection). Divergence is possible if the projection is not refreshed.
  Mitigated by making the projection a pure function of the stored incident
  and by keeping the Gateway store authoritative.
- The `Robot` entity ships permanently `UNVERIFIED` until Issue #160 lands.
  Consumers that require a verified robot reading will receive `DENIED`
  decisions until then. This is the intended fail-closed behaviour, not a
  defect.
- The response policy duplicates a small amount of skill-name knowledge
  (the `YANSHEE_SKILL_MAP` from Gateway topics onto bounded skill ids).
  If the Gateway topic scheme changes, both sides must be updated. The map is
  kept small and in one place for that reason.
- Orion-LD availability still affects the quality of the context view but
  never affects the gateway's ability to ingest, store or command.

**Neutral:**

- This ADR does not approve the FIWARE surface itself; that remains ADR-0014
  (`Proposed`). It records only the robot/incident context projection, the
  read-only facade and the response-policy shape.
- The relationship between this decision and Issue #199 (NGSI-LD
  subscriptions and the notification relay to Unity/React) is intentionally
  left open. Issue #199 owns the relay; this ADR owns the read model and the
  policy. Issue #200 owns the broker's auth boundary and tenancy; the
  facade here is loopback/internal until that lands.

## Alternatives considered

**Alternative A — let the Orion-LD writer carry robot and incident entities too**

The existing `OrionLdAdapter` from Issue #198 already writes NGSI-LD
entities. Extending it to emit `Robot` and projected `Alert` entities would
have avoided a second mapping module. It was rejected because that adapter
maps *canonical events*, not incidents or robot capability, and because
extending the write path would have put incident projection and robot
capability behind the same opt-in writer flag as telemetry — making the
"context write" surface larger at exactly the point where ADR-0014 wants it
smaller. The separate mapping modules also let the incident projection be
sourced from the incident store rather than from MQTT.

**Alternative B — expose the Orion-LD broker directly to consumers**

Consumers (Unity, React, the robot) could query Orion-LD themselves over
HTTP. This was rejected: it would require exposing an unauthenticated broker
endpoint (Issue #200 is still open), it would give browser and robot code
write-capable HTTP access to the broker, and it would place the
read-only boundary in each consumer instead of in one reviewed place.

**Alternative C — have the robot policy read the Gateway incident store directly**

The robot could consume incidents over the existing gateway REST/WebSocket
path and never involve FIWARE at all. This was rejected because Issue #204
exists precisely to evaluate the FIWARE context layer as a supporting
surface for the research demo, and because the incident projection also has
to serve the dashboard, Unity and the research reports. The Gateway incident
store remains the source of truth; the FIWARE path is an additional
materialised view, not a replacement.

**Alternative D — publish robot capability values now and mark them "simulated"**

Rather than shipping `UNKNOWN`, the mapper could emit a representative
battery level and action list labelled `dataQuality: SIMULATED`. It was
rejected because a simulated battery level in a context that downstream
policy code reads as a capability list is exactly the kind of value that
later gets mistaken for a measurement. `UNKNOWN` plus `UNVERIFIED` cannot be
confused with a reading.

## Evidence

- `docs/adr/adr-0014-fiware-orion-ld-context.md` — FIWARE/Orion-LD context
  architecture, central invariants 1, 2 and 6.
- `docs/adr/adr-0006-local-physical-safety.md` — local physical safety and
  the fail-closed AI guard.
- `docs/adr/adr-0001-modular-monorepo.md` — module boundary rule that keeps
  `edge-ai-robot` from importing `iot-gateway`.
- `contracts/fiware/ngsi-ld-entity-schema.md` — merged entity schema
  (Issue #197); notes that the Yanshee robot is typed separately as `Robot`.
- `iot-gateway/src/iot_gateway/adapters/orion_ld.py` — the merged Issue #198
  write path this ADR deliberately does not extend.
- `iot-gateway/src/iot_gateway/alert_outbox.py` — the Gateway-approved
  incident outbox that remains the sole notification dispatch path.
- `iot-gateway/src/iot_gateway/incidents.py` — the authoritative incident
  record the projection reads.
- `iot-gateway/src/iot_gateway/adapters/orion_robot.py`,
  `iot-gateway/src/iot_gateway/adapters/orion_incident.py`,
  `iot-gateway/src/iot_gateway/context_query.py`,
  `edge-ai-robot/src/edge_ai_robot/context/__init__.py` — the implementation.
- `integration-tests/fiware/test_fiware_yanshee_scenario.py` — L2 controlled
  scenario with transport and provenance trace (SPEC-4, TC-1..TC-5).
- Issue #204 — FIWARE context mapping for Yanshee notifications, incident
  evidence and research API.
