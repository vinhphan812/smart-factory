# FIWARE Context Contract — Robot and Incident Evidence

**Owner:** Issue #204 (FIWARE context for Yanshee alerts, incident evidence, research API)
**Version:** 1.0.0
**Status:** Draft — Ready for review
**Context:** ADR-0014 (FIWARE/Orion-LD context architecture), ADR-0018 (FIWARE context mapping for Yanshee notifications and incident evidence), Issue #197 (entity schema)

---

## Overview

This contract specifies the NGSI-LD shapes used to expose **robot capability**
and **projected incident evidence** through the FIWARE context layer, and the
provenance rules every consumer must honour.

It extends `contracts/fiware/ngsi-ld-entity-schema.md` (Issue #197) with the
`Robot` type, which Issue #197 SPEC-1 required ("Yanshee separately typed as
`Robot`") but did not deliver.

**Authority statement (read before using anything in this document):**

> The FIWARE context layer is a **read model**. It is not the authorization
> truth, not the incident record of authority, and never a command path. A
> property or relationship update in Orion-LD can never enable, authorize or
> suppress a physical action. Robot skills are launched **only** by the
> Gateway-approved incident outbox (`iot-gateway/src/iot_gateway/alert_outbox.py`).

---

## 1. `Robot` entity

Represents the UBTECH Yanshee robot (Issue #158 supersedes MiniAlpha per
ADR-0013).

### Entity id

```
urn:ngsi-ld:Robot:<robot_id>
```

Example: `urn:ngsi-ld:Robot:yanshee-01`

### Properties

| Property | Type | Mandatory | Description |
|---|---|---|---|
| `id` | URI | Yes | Full NGSI-LD entity id. |
| `type` | String | Yes | Fixed: `Robot`. |
| `name` | Text | Yes | Human-readable robot name. |
| `robotId` | Text | Yes | Canonical robot id (e.g. `yanshee-01`). |
| `status` | Text | Yes | Robot status, or `UNKNOWN` when unverified. |
| `batteryLevel` | Number \| Text | Yes | Battery charge in percent, or `UNKNOWN` (Text). |
| `supportedActions` | Array[String] | Yes | Verified supported actions; empty when unverified. |
| `verificationStatus` | Text | Yes | `VERIFIED` or `UNVERIFIED`. |
| `verificationSource` | Text | Yes | Identifier of the source of the reading. |
| `dataQuality` | Text | Yes | `PHYSICAL`, `SIMULATED` or `UNKNOWN`. |
| `observedAt` | DateTime | No | Observation timestamp. **Omitted when unknown — never fabricated.** |
| `emergencyStop` | Boolean | No | E-stop state as observed by the robot source. Read-only for consumers. |
| `partOf` | Relationship | No | → `urn:ngsi-ld:Factory:<factory_id>`. |

### Rules

1. **R-1 — Unverified suppression.** When `verificationStatus` is `UNVERIFIED`,
   `status` **must** be `UNKNOWN`, `batteryLevel` **must** be `UNKNOWN` and
   `supportedActions` **must** be empty. An unverified source may not assert a
   concrete capability.

2. **R-2 — No fabricated timestamps.** `observedAt` is omitted when the source
   has no observation time. A placeholder timestamp is not acceptable.

3. **R-3 — Type stability of `batteryLevel`.** The attribute is `Number` when
   a verified battery reading exists and `Text` with value `UNKNOWN`
   otherwise. Consumers must branch on `verificationStatus`, not on the
   attribute type.

4. **R-4 — E-stop is informational.** `emergencyStop` reflects what the robot
   source reports. Consumers must never clear it, and the local hardwired
   E-stop remains the authority regardless of this value.

5. **R-5 — Current state.** The Yanshee SDK is unaudited (Issues #159/#160).
   Until that lands, the only permitted `verificationSource` value is
   `unverified-no-sdk-audit`.

### Example — unverified (the state today)

```json
{
  "id": "urn:ngsi-ld:Robot:yanshee-01",
  "type": "Robot",
  "name": { "type": "Text", "value": "UBTECH Yanshee" },
  "robotId": { "type": "Text", "value": "yanshee-01" },
  "status": { "type": "Text", "value": "UNKNOWN" },
  "batteryLevel": { "type": "Text", "value": "UNKNOWN" },
  "supportedActions": { "type": "Array", "value": [] },
  "verificationStatus": { "type": "Text", "value": "UNVERIFIED" },
  "verificationSource": { "type": "Text", "value": "unverified-no-sdk-audit" },
  "dataQuality": { "type": "Text", "value": "UNKNOWN" }
}
```

### Example — verified reading (only after Issue #160)

```json
{
  "id": "urn:ngsi-ld:Robot:yanshee-01",
  "type": "Robot",
  "name": { "type": "Text", "value": "UBTECH Yanshee" },
  "robotId": { "type": "Text", "value": "yanshee-01" },
  "status": { "type": "Text", "value": "idle" },
  "batteryLevel": { "type": "Number", "value": 91.0 },
  "supportedActions": { "type": "Array", "value": ["notify_operator"] },
  "verificationStatus": { "type": "Text", "value": "VERIFIED" },
  "verificationSource": { "type": "Text", "value": "yanshee-sdk@0.1.0" },
  "dataQuality": { "type": "Text", "value": "PHYSICAL" },
  "observedAt": { "type": "DateTime", "value": "2026-10-23T09:00:00Z" }
}
```

---

## 2. Incident → `Alert` projection

Projects a Gateway incident (`iot-gateway/src/iot_gateway/incidents.py`) onto
an NGSI-LD `Alert`.

### Entity id

```
urn:ngsi-ld:Alert:<incident_id>
```

Example: `urn:ngsi-ld:Alert:INC-001`

### Properties

| Property | Type | Mandatory | Description |
|---|---|---|---|
| `id` | URI | Yes | Full NGSI-LD entity id. |
| `type` | String | Yes | Fixed: `Alert`. |
| `name` | Text | Yes | Incident title. |
| `severity` | Text | Yes | `info` \| `warning` \| `critical`. |
| `category` | Text | Yes | `equipment` \| `safety` \| `quality` \| `performance` \| `anomaly`. |
| `description` | Text | Yes | Incident message. |
| `status` | Text | Yes | `active` \| `acknowledged` \| `resolved`. |
| `timestamp` | DateTime | Yes | Incident timestamp. |
| `createdAt` | DateTime | Yes | Incident timestamp. |
| `traceId` | Text | Yes | Trace id, or `UNKNOWN` when the incident has none. |
| `sourceEventId` | Text | Yes | Originating Gateway canonical event id, or `UNKNOWN`. |
| `sourceSystem` | Text | Yes | Always `iot-gateway`. |
| `incidentId` | Text | Yes | Gateway incident id. |
| `deviceId` | Text | Yes | Originating device id, or `UNKNOWN`. |
| `dataQuality` | Text | Yes | `PHYSICAL` \| `SIMULATED` \| `UNKNOWN`. |
| `operatorState` | Text | Yes | `unacknowledged` \| `acknowledged` \| `resolved`. |
| `recommendedAction` | Text | No | Suggested operator action. |
| `acknowledgedBy` / `acknowledgedAt` | Text / DateTime | No | Acknowledgement record. |
| `resolvedBy` / `resolvedAt` | Text / DateTime | No | Resolution record. |
| `relatedTo` | Relationship | No | → `urn:ngsi-ld:Module:<module_id>`. |
| `relatedToSensor` | Relationship | No | → `urn:ngsi-ld:Sensor:<sensor_id>`. |

### Rules

1. **R-6 — Provenance is mandatory.** `traceId`, `sourceEventId` and
   `sourceSystem` are always present. When the incident carries no trace id,
   the value is the literal `UNKNOWN` — never an empty string and never a
   generated id.

2. **R-7 — Read model.** The projection is a pure function of the stored
   incident. It does not mutate the incident store and does not replace it.
   The Gateway incident store remains the authoritative incident record.

3. **R-8 — Explicit category mapping only.** The Gateway `source` string maps
   to a category only on an unambiguous match (`safety`, `quality`,
   `performance`, `anomaly`); anything else falls back to `equipment`.

4. **R-9 — Relationship honesty.** `relatedTo` and `relatedToSensor` are
   emitted only when the module/sensor entity id is actually known. An
   absent relationship is not the same as a relationship to an unknown
   entity, and the keys are omitted rather than populated with placeholders.

### Example

```json
{
  "id": "urn:ngsi-ld:Alert:INC-ANOM-001",
  "type": "Alert",
  "name": { "type": "Text", "value": "Conveyor motor temperature anomaly" },
  "severity": { "type": "Text", "value": "critical" },
  "category": { "type": "Text", "value": "anomaly" },
  "description": { "type": "Text", "value": "Motor temperature 85.00 C exceeds threshold 75.00 C." },
  "status": { "type": "Text", "value": "active" },
  "timestamp": { "type": "DateTime", "value": "2026-10-23T09:00:00Z" },
  "createdAt": { "type": "DateTime", "value": "2026-10-23T09:00:00Z" },
  "traceId": { "type": "Text", "value": "trace-anom-001" },
  "sourceEventId": { "type": "Text", "value": "evt-anom-001" },
  "sourceSystem": { "type": "Text", "value": "iot-gateway" },
  "incidentId": { "type": "Text", "value": "INC-ANOM-001" },
  "deviceId": { "type": "Text", "value": "conveyor-01" },
  "dataQuality": { "type": "Text", "value": "SIMULATED" },
  "operatorState": { "type": "Text", "value": "unacknowledged" },
  "recommendedAction": { "type": "Text", "value": "Reduce load and inspect motor cooling" },
  "relatedTo": { "type": "Relationship", "object": "urn:ngsi-ld:Module:conveyor-01" },
  "relatedToSensor": { "type": "Relationship", "object": "urn:ngsi-ld:Sensor:conveyor-temp-01" }
}
```

---

## 3. Read-only query facade

`iot-gateway/src/iot_gateway/context_query.py` — `ContextQueryFacade`.

| Method | HTTP | Returns |
|---|---|---|
| `get_entity(entity_id)` | `GET /ngsi-ld/v1/entities/{id}` | `ContextEntity` or `None`. |
| `query_entities(entity_type, limit)` | `GET /ngsi-ld/v1/entities?type=…` | `list[ContextEntity]`. |
| `get_alerts(limit)` | same, `type=Alert` | `list[ContextEntity]`. |
| `get_alert(incident_id)` | `GET …/urn:ngsi-ld:Alert:{id}` | `ContextEntity` or `None`. |
| `get_robots(limit)` | same, `type=Robot` | `list[ContextEntity]`. |
| `get_robot(robot_id)` | `GET …/urn:ngsi-ld:Robot:{id}` | `ContextEntity` or `None`. |

### Rules

1. **R-10 — Read-only by construction.** The facade issues HTTP `GET` only.
   It has no upsert, delete, publish or command-forwarding method. The
   guarantee is structural, not a runtime check.

2. **R-11 — No actuation path.** The facade never talks to MQTT, the bridge
   or the Gateway command path.

3. **R-12 — Failure is absence, not an error state.** A broker error yields
   `None` / `[]`. A consumer must treat that as "no data" and must not
   substitute a default value.

4. **R-13 — Freshness is the consumer's job.** The facade returns what the
   broker holds. Callers must evaluate freshness (`is_context_fresh`) before
   acting on any value. Context that is stale or untimestamped **must not**
   authorize anything.

---

## 4. Yanshee response policy

`edge-ai-robot/src/edge_ai_robot/context/__init__.py` — `YansheeResponsePolicy`.

### Decision values

| Decision | Meaning |
|---|---|
| `APPROVED` | A notification may be proposed. |
| `DENIED` | Policy refused: not permitted, not supported, or context unusable. |
| `BLOCKED` | A safety boundary refused: physical skill, or E-stop active. |

### Reason codes

`OK`, `NO_GATEWAY_APPROVAL`, `CONTEXT_STALE`, `CONTEXT_INVALID`,
`UNSUPPORTED_SKILL`, `ROBOT_CAPABILITY_UNVERIFIED`, `ALERT_NOT_ACTIONABLE`,
`PHYSICAL_SKILL_BLOCKED`, `EMERGENCY_STOP_ACTIVE`, `UNKNOWN_SKILL`.

### Evaluation order

1. Unknown skill → `DENIED` / `UNKNOWN_SKILL`.
2. Physical-action skill, or a Yanshee physical topic (`yanshee/movement`,
   `yanshee/grabbing`, `yanshee/navigation`) → `BLOCKED` /
   `PHYSICAL_SKILL_BLOCKED`.
3. No Gateway approval, approval for a different incident, or approval for a
   different skill → `DENIED` / `NO_GATEWAY_APPROVAL` or `UNSUPPORTED_SKILL`.
4. No alert entity → `DENIED` / `CONTEXT_INVALID`.
5. Stale or untimestamped context → `DENIED` / `CONTEXT_STALE`.
6. Alert status not in `{active, acknowledged}` → `DENIED` /
   `ALERT_NOT_ACTIONABLE`.
7. Robot entity missing, or `verificationStatus != VERIFIED` → `DENIED` /
   `ROBOT_CAPABILITY_UNVERIFIED`.
8. Skill not in the robot's verified `supportedActions` → `DENIED` /
   `UNSUPPORTED_SKILL`.
9. Emergency stop active → `BLOCKED` / `EMERGENCY_STOP_ACTIVE`.
10. Otherwise → `APPROVED` / `OK`.

### Rules

1. **R-14 — Context alone never dispatches.** A Gateway approval record
   (`GatewayApproval`, produced by the incident outbox) is always required.
   An Orion-LD entity change by itself yields `DENIED`.

2. **R-15 — Notification-only.** Only `notification`-category skills may be
   proposed. Status-query and acknowledge skills change robot-side state and
   are out of scope for the context path.

3. **R-16 — Stale context cannot authorise.** Context older than the
   configured window (default 120 s), or with no timestamp, is refused.

4. **R-17 — The E-stop is independent.** The policy refuses while the E-stop
   is active and never clears it. The local hardwired E-stop remains the
   authority; the policy is not a path to it.

5. **R-18 — Explicit refusal.** Every refusal carries a reason code. An
   unsupported skill never yields success.

### Gateway skill topic mapping

| Gateway topic (`alert_outbox.YansheeSkill`) | Bounded skill id |
|---|---|
| `yanshee/speech` | `notify_operator` |
| `yanshee/emotion` | `broadcast_alert` |
| `yanshee/movement` | — permanently `BLOCKED` |
| `yanshee/grabbing` | — permanently `BLOCKED` |
| `yanshee/navigation` | — permanently `BLOCKED` |

---

## 5. Provenance chain

```
ESP32/uKit sensor
  → MQTT telemetry
    → Gateway canonical event (event_id, sequence, received_at)
      → Gateway incident (incident_id, audit trail)
        → NGSI-LD Alert (traceId, sourceEventId, sourceSystem)
          → read-only facade
            ├→ Unity subscriber
            ├→ React dashboard subscriber
            └→ Yanshee response policy (requires Gateway approval)
```

Every hop carries an identifier. A consumer that receives an `Alert` can
always resolve `sourceEventId` → Gateway canonical event and `traceId` →
the originating decision chain.

---

## 6. Compatibility

- This contract is additive to `contracts/fiware/ngsi-ld-entity-schema.md`
  (v1.0.0). No existing entity shape, property or relationship changes.
- `Alert` and `Robot` entity ids use the `urn:ngsi-ld:<Type>:<id>` pattern
  already established by Issue #197.
- The `Alert` projection reuses the `severity`, `category` and `status`
  enumerations from the Issue #197 `Alert` schema, so the existing
  `contracts/fiware/schemas/alert.json` remains applicable.
- The `Robot` type is new. It requires an Issue #197 follow-up to add
  `contracts/fiware/schemas/robot.json` and to register the type; that
  follow-up is tracked, not silently assumed.

---

## 7. Evidence levels

| Component | Level | Notes |
|---|---|---|
| Entity mapping (robot, incident) | L1 | Unit-tested. |
| Read-only facade | L1 | Unit-tested with a mocked transport. |
| Response policy | L1 | Unit-tested across the full decision matrix. |
| Controlled scenario (SPEC-4) | L2 | In-memory broker double, mock robot. |
| Real Orion-LD deployment | — | **Not verified here.** Requires the Issue #202 harness. |
| Real Yanshee SDK | — | **BLOCKED** on Issue #159/#160. |

No L3, L4 or L5 claim is made by this contract.
