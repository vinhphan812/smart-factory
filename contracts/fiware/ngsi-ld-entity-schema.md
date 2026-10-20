# NGSI-LD Entity Schema — Smart Factory

**Owner:** Issue #197 (NGSI-LD entity graph + JSON-LD context)  
**Version:** 1.0.0  
**Status:** Draft — Ready for review  
**Context:** ADR-0014 (Orion-LD selected as context broker)

---

## Overview

This document defines the NGSI-LD entity schema for the AIBOT Smart Factory. It specifies entity types, properties, relationships, GeoJSON location support, JSON-LD `@context` mappings, and type registrations for Orion-LD.

NGSI-LD (Next Generation Service Interface — Linked Data) is the FIWARE context broker API that provides:
- JSON-LD based context data representation
- Entity temporal evolution
- Graph-based relationships between entities
- Subscription/notification capabilities

---

## Entity Type Inventory

| Entity Type | Description | Physical Mapping |
|-------------|-------------|-------------------|
| `Device` | Physical/controlled device (ESP32 bridge, MEGA controller) | ESP32 bridges, MEGA units |
| `Module` | Factory physical module (conveyor, crane, forklift, etc.) | 9 physical modules |
| `Job` | Production job/order being executed | Production orders |
| `Material` | Raw material or finished product | Materials in transit |
| `Operator` | Human operator authorized to issue commands | Human operators |
| `Alert` | System-generated alert condition | Alerts from anomaly detection |
| `Incident` | Incident record with root cause | Incident tracking |

---

## 1. Device Entity

Represents a controllable device in the factory (ESP32 bridge, MEGA controller, simulator).

### Properties

| Property | Type | Mandatory | Description |
|----------|------|-----------|-------------|
| `id` | URI | Yes | Full NGSI-LD entity ID (e.g., `urn:ngsi-ld:Device:bridge-001`) |
| `type` | String | Yes | Fixed: `Device` |
| `name` | String | Yes | Human-readable device name |
| `deviceType` | String | Yes | `esp32_bridge`, `mega_reference`, `simulator`, `iot_gateway` |
| `deviceId` | String | Yes | Registry device_id (e.g., `bridge-001`) |
| `firmwareVersion` | String | No | Semantic version or git hash |
| `capabilities` | Array[String] | Yes | List of supported commands/telemetry |
| `status` | String | Yes | `online`, `offline`, `maintenance`, `error` |
| `location` | GeoJSON Point | No | Physical location in factory |
| `owner` | Relationship | No | Links to `Operator` entity |
| `controlledBy` | Relationship | No | Links to parent `Module` entity |
| `lastSeen` | DateTime | No | Last heartbeat timestamp |
| `createdAt` | DateTime | Yes | Entity creation timestamp |
| `modifiedAt` | DateTime | No | Last modification timestamp |

### JSON-LD @context (Device)

```json
{
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-context.jsonld",
    {
      "sf": "https://smart-factory.example.com/ns/ont/factory#",
      "name": "https://schema.org/name",
      "deviceType": "sf:deviceType",
      "deviceId": "sf:deviceId",
      "firmwareVersion": "sf:firmwareVersion",
      "capabilities": {
        "@type": "https://schema.org/Array",
        "@container": "@set",
        "@id": "sf:capabilities"
      },
      "status": "sf:status",
      "location": "https://schema.org/location",
      "owner": {
        "@type": "@id",
        "@id": "sf:ownedBy"
      },
      "controlledBy": {
        "@type": "@id",
        "@id": "sf:controlledBy"
      },
      "lastSeen": "sf:lastSeen",
      "createdAt": "http://www.w3.org/ns/prov#generatedAtTime",
      "modifiedAt": "http://www.w3.org/ns/prov#invalidatedAtTime"
    }
  ]
}
```

### Example Entity

```json
{
  "id": "urn:ngsi-ld:Device:bridge-001",
  "type": "Device",
  "name": "ESP32 Bridge Unit 1",
  "deviceType": {
    "type": "Text",
    "value": "esp32_bridge"
  },
  "deviceId": {
    "type": "Text",
    "value": "bridge-001"
  },
  "firmwareVersion": {
    "type": "Text",
    "value": "v1.2.0"
  },
  "capabilities": {
    "type": "Array",
    "value": ["CONVEYOR_START", "CONVEYOR_STOP", "get_telemetry"]
  },
  "status": {
    "type": "Text",
    "value": "online"
  },
  "location": {
    "type": "GeoProperty",
    "value": {
      "type": "Point",
      "coordinates": [105.4456, 10.3732]
    }
  },
  "controlledBy": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Module:conveyor-a"
  },
  "lastSeen": {
    "type": "DateTime",
    "value": "2026-10-20T10:30:00Z"
  },
  "createdAt": {
    "type": "DateTime",
    "value": "2026-09-01T08:00:00Z"
  }
}
```

---

## 2. Module Entity

Represents a physical factory module (conveyor, sorting machine, crane, forklift, etc.).

### Properties

| Property | Type | Mandatory | Description |
|----------|------|-----------|-------------|
| `id` | URI | Yes | Full NGSI-LD entity ID |
| `type` | String | Yes | Fixed: `Module` |
| `name` | String | Yes | Human-readable module name |
| `moduleType` | String | Yes | See module type enumeration |
| `description` | String | No | Module description |
| `status` | String | Yes | `idle`, `running`, `maintenance`, `error`, `emergency_stop` |
| `state` | String | No | Current operational state |
| `speed` | Integer | No | Current speed (0 when stopped) |
| `location` | GeoJSON Polygon/Point | Yes | Physical footprint/bounds |
| `zone` | String | No | Factory zone (e.g., "Assembly Line 1") |
| `line` | String | No | Production line identifier |
| `controlledBy` | Relationship | No | Links to `Device` that controls this module |
| `hasJob` | Relationship | No | Current `Job` being executed |
| `processes` | Relationship | No | `Material` entities currently being processed |
| `createdAt` | DateTime | Yes | Entity creation timestamp |
| `modifiedAt` | DateTime | No | Last modification timestamp |

### Module Type Enumeration

| Type | Description | Physical Module |
|------|-------------|-----------------|
| `conveyor` | Conveyor belt system | Conveyor Belt |
| `sorting` | Material sorting/routing | Sorting Machine |
| `crane` | Tower crane for lifting | Tower Crane |
| `forklift` | Material transport vehicle | Forklift |
| `dump_truck` | Material delivery vehicle | Dump Truck |
| `packaging` | Packaging machine | Packaging Machine |
| `bracket` | Mechanical structure | Bracket |
| `parking` | Storage/parking area | Parking Lot |
| `combine` | Integration/combine module | Combine Modules |

### JSON-LD @context (Module)

```json
{
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-context.jsonld",
    {
      "sf": "https://smart-factory.example.com/ns/ont/factory#",
      "name": "https://schema.org/name",
      "moduleType": "sf:moduleType",
      "description": "https://schema.org/description",
      "status": "sf:status",
      "state": "sf:state",
      "speed": "sf:speed",
      "location": "https://schema.org/location",
      "zone": "sf:zone",
      "line": "sf:line",
      "controlledBy": {
        "@type": "@id",
        "@id": "sf:controlledBy"
      },
      "hasJob": {
        "@type": "@id",
        "@id": "sf:hasJob"
      },
      "processes": {
        "@type": "@id",
        "@id": "sf:processes"
      },
      "createdAt": "http://www.w3.org/ns/prov#generatedAtTime",
      "modifiedAt": "http://www.w3.org/ns/prov#invalidatedAtTime"
    }
  ]
}
```

### Example Entity

```json
{
  "id": "urn:ngsi-ld:Module:conveyor-a",
  "type": "Module",
  "name": "Conveyor Belt A",
  "moduleType": {
    "type": "Text",
    "value": "conveyor"
  },
  "description": {
    "type": "Text",
    "value": "Primary conveyor belt for material transport"
  },
  "status": {
    "type": "Text",
    "value": "running"
  },
  "state": {
    "type": "Text",
    "value": "STATE_MOVING"
  },
  "speed": {
    "type": "Integer",
    "value": 120
  },
  "location": {
    "type": "GeoProperty",
    "value": {
      "type": "Polygon",
      "coordinates": [[
        [105.4455, 10.3731],
        [105.4458, 10.3731],
        [105.4458, 10.3733],
        [105.4455, 10.3733],
        [105.4455, 10.3731]
      ]]
    }
  },
  "zone": {
    "type": "Text",
    "value": "Assembly Line 1"
  },
  "line": {
    "type": "Text",
    "value": "Main Production Line"
  },
  "controlledBy": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Device:bridge-001"
  },
  "hasJob": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Job:job-001"
  },
  "createdAt": {
    "type": "DateTime",
    "value": "2026-09-01T08:00:00Z"
  },
  "modifiedAt": {
    "type": "DateTime",
    "value": "2026-10-20T10:30:00Z"
  }
}
```

---

## 3. Job Entity

Represents a production job or order being executed in the factory.

### Properties

| Property | Type | Mandatory | Description |
|----------|------|-----------|-------------|
| `id` | URI | Yes | Full NGSI-LD entity ID |
| `type` | String | Yes | Fixed: `Job` |
| `name` | String | Yes | Job name/order ID |
| `jobType` | String | Yes | `production`, `maintenance`, `transport`, `sorting`, `packaging` |
| `status` | String | Yes | `pending`, `in_progress`, `completed`, `paused`, `cancelled`, `failed` |
| `priority` | Integer | No | Job priority (higher = more urgent) |
| `progress` | Integer | No | Progress percentage (0-100) |
| `quantity` | Integer | No | Target quantity to produce |
| `completedQuantity` | Integer | No | Items completed |
| `startedAt` | DateTime | No | Job start timestamp |
| `estimatedEndAt` | DateTime | No | Estimated completion timestamp |
| `completedAt` | DateTime | No | Actual completion timestamp |
| `createdBy` | Relationship | No | `Operator` who created the job |
| `assignedTo` | Relationship | No | `Module` or `Device` assigned |
| `usesMaterials` | Relationship | No | `Material` entities consumed |
| `produces` | Relationship | No | Output `Material` entities |
| `createdAt` | DateTime | Yes | Entity creation timestamp |
| `modifiedAt` | DateTime | No | Last modification timestamp |

### JSON-LD @context (Job)

```json
{
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-context.jsonld",
    {
      "sf": "https://smart-factory.example.com/ns/ont/factory#",
      "name": "https://schema.org/name",
      "jobType": "sf:jobType",
      "status": "sf:jobStatus",
      "priority": "sf:priority",
      "progress": "sf:progress",
      "quantity": "sf:quantity",
      "completedQuantity": "sf:completedQuantity",
      "startedAt": "sf:startedAt",
      "estimatedEndAt": "sf:estimatedEndAt",
      "completedAt": "sf:completedAt",
      "createdBy": {
        "@type": "@id",
        "@id": "sf:createdBy"
      },
      "assignedTo": {
        "@type": "@id",
        "@id": "sf:assignedTo"
      },
      "usesMaterials": {
        "@type": "@id",
        "@id": "sf:usesMaterials"
      },
      "produces": {
        "@type": "@id",
        "@id": "sf:produces"
      },
      "createdAt": "http://www.w3.org/ns/prov#generatedAtTime",
      "modifiedAt": "http://www.w3.org/ns/prov#invalidatedAtTime"
    }
  ]
}
```

### Example Entity

```json
{
  "id": "urn:ngsi-ld:Job:job-001",
  "type": "Job",
  "name": "Production Order #001",
  "jobType": {
    "type": "Text",
    "value": "production"
  },
  "status": {
    "type": "Text",
    "value": "in_progress"
  },
  "priority": {
    "type": "Integer",
    "value": 10
  },
  "progress": {
    "type": "Integer",
    "value": 45
  },
  "quantity": {
    "type": "Integer",
    "value": 100
  },
  "completedQuantity": {
    "type": "Integer",
    "value": 45
  },
  "startedAt": {
    "type": "DateTime",
    "value": "2026-10-20T08:00:00Z"
  },
  "estimatedEndAt": {
    "type": "DateTime",
    "value": "2026-10-20T12:00:00Z"
  },
  "createdBy": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Operator:op-001"
  },
  "assignedTo": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Module:conveyor-a"
  },
  "usesMaterials": {
    "type": "Relationship",
    "value": ["urn:ngsi-ld:Material:mat-001"]
  },
  "produces": {
    "type": "Relationship",
    "value": ["urn:ngsi-ld:Material:mat-002"]
  },
  "createdAt": {
    "type": "DateTime",
    "value": "2026-10-20T07:55:00Z"
  }
}
```

---

## 4. Material Entity

Represents raw material or finished product in the factory.

### Properties

| Property | Type | Mandatory | Description |
|----------|------|-----------|-------------|
| `id` | URI | Yes | Full NGSI-LD entity ID |
| `type` | String | Yes | Fixed: `Material` |
| `name` | String | Yes | Material name/identifier |
| `materialType` | String | Yes | `raw`, `work_in_progress`, `finished`, `packaged`, `waste` |
| `sku` | String | No | Stock keeping unit |
| `quantity` | Integer | Yes | Current quantity |
| `unit` | String | No | Unit of measure (e.g., `pcs`, `kg`, `box`) |
| `status` | String | Yes | `available`, `in_transit`, `processing`, `stored`, `consumed` |
| `location` | GeoJSON Point | No | Current location |
| `sourceModule` | Relationship | No | Origin `Module` |
| `destinationModule` | Relationship | No | Destination `Module` |
| `belongsToJob` | Relationship | No | Associated `Job` |
| `createdAt` | DateTime | Yes | Entity creation timestamp |
| `modifiedAt` | DateTime | No | Last modification timestamp |

### JSON-LD @context (Material)

```json
{
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-context.jsonld",
    {
      "sf": "https://smart-factory.example.com/ns/ont/factory#",
      "name": "https://schema.org/name",
      "materialType": "sf:materialType",
      "sku": "sf:sku",
      "quantity": "sf:quantity",
      "unit": "sf:unit",
      "status": "sf:materialStatus",
      "location": "https://schema.org/location",
      "sourceModule": {
        "@type": "@id",
        "@id": "sf:sourceModule"
      },
      "destinationModule": {
        "@type": "@id",
        "@id": "sf:destinationModule"
      },
      "belongsToJob": {
        "@type": "@id",
        "@id": "sf:belongsToJob"
      },
      "createdAt": "http://www.w3.org/ns/prov#generatedAtTime",
      "modifiedAt": "http://www.w3.org/ns/prov#invalidatedAtTime"
    }
  ]
}
```

### Example Entity

```json
{
  "id": "urn:ngsi-ld:Material:mat-001",
  "type": "Material",
  "name": "Raw Component A",
  "materialType": {
    "type": "Text",
    "value": "raw"
  },
  "sku": {
    "type": "Text",
    "value": "RAW-CMP-A-001"
  },
  "quantity": {
    "type": "Integer",
    "value": 500
  },
  "unit": {
    "type": "Text",
    "value": "pcs"
  },
  "status": {
    "type": "Text",
    "value": "in_transit"
  },
  "location": {
    "type": "GeoProperty",
    "value": {
      "type": "Point",
      "coordinates": [105.4456, 10.3732]
    }
  },
  "sourceModule": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Module:parking-lot-1"
  },
  "destinationModule": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Module:conveyor-a"
  },
  "belongsToJob": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Job:job-001"
  },
  "createdAt": {
    "type": "DateTime",
    "value": "2026-10-20T08:00:00Z"
  }
}
```

---

## 5. Operator Entity

Represents a human operator authorized to issue commands to the factory.

### Properties

| Property | Type | Mandatory | Description |
|----------|------|-----------|-------------|
| `id` | URI | Yes | Full NGSI-LD entity ID |
| `type` | String | Yes | Fixed: `Operator` |
| `name` | String | Yes | Operator name |
| `employeeId` | String | Yes | Employee/operator ID |
| `role` | String | Yes | `operator`, `supervisor`, `maintenance`, `admin` |
| `authorizationLevel` | Integer | Yes | Authorization level (1-5) |
| `status` | String | Yes | `active`, `inactive`, `suspended` |
| `email` | String | No | Contact email |
| `phone` | String | No | Contact phone |
| `assignedZone` | String | No | Factory zone assignment |
| `certifications` | Array[String] | No | Safety certifications |
| `lastActiveAt` | DateTime | No | Last activity timestamp |
| `createdAt` | DateTime | Yes | Entity creation timestamp |
| `modifiedAt` | DateTime | No | Last modification timestamp |

### JSON-LD @context (Operator)

```json
{
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-context.jsonld",
    {
      "sf": "https://smart-factory.example.com/ns/ont/factory#",
      "name": "https://schema.org/name",
      "employeeId": "sf:employeeId",
      "role": "sf:operatorRole",
      "authorizationLevel": "sf:authorizationLevel",
      "status": "sf:operatorStatus",
      "email": "https://schema.org/email",
      "phone": "https://schema.org/telephone",
      "assignedZone": "sf:assignedZone",
      "certifications": {
        "@type": "https://schema.org/Array",
        "@container": "@set",
        "@id": "sf:certifications"
      },
      "lastActiveAt": "sf:lastActiveAt",
      "createdAt": "http://www.w3.org/ns/prov#generatedAtTime",
      "modifiedAt": "http://www.w3.org/ns/prov#invalidatedAtTime"
    }
  ]
}
```

### Example Entity

```json
{
  "id": "urn:ngsi-ld:Operator:op-001",
  "type": "Operator",
  "name": "Nguyen Van A",
  "employeeId": {
    "type": "Text",
    "value": "EMP-001"
  },
  "role": {
    "type": "Text",
    "value": "operator"
  },
  "authorizationLevel": {
    "type": "Integer",
    "value": 3
  },
  "status": {
    "type": "Text",
    "value": "active"
  },
  "email": {
    "type": "Text",
    "value": "nguyenvana@factory.local"
  },
  "assignedZone": {
    "type": "Text",
    "value": "Assembly Line 1"
  },
  "certifications": {
    "type": "Array",
    "value": ["safety-basic", "forklift-operation"]
  },
  "lastActiveAt": {
    "type": "DateTime",
    "value": "2026-10-20T10:30:00Z"
  },
  "createdAt": {
    "type": "DateTime",
    "value": "2026-09-01T08:00:00Z"
  }
}
```

---

## 6. Alert Entity

Represents a system-generated alert condition.

### Properties

| Property | Type | Mandatory | Description |
|----------|------|-----------|-------------|
| `id` | URI | Yes | Full NGSI-LD entity ID |
| `type` | String | Yes | Fixed: `Alert` |
| `name` | String | Yes | Alert name/identifier |
| `severity` | String | Yes | `info`, `warning`, `critical`, `emergency` |
| `category` | String | Yes | `equipment`, `safety`, `quality`, `performance`, `anomaly` |
| `description` | String | Yes | Alert description |
| `status` | String | Yes | `active`, `acknowledged`, `resolved` |
| `triggeredBy` | Relationship | No | Entity that triggered the alert |
| `acknowledgedBy` | Relationship | No | `Operator` who acknowledged |
| `acknowledgedAt` | DateTime | No | Acknowledgment timestamp |
| `resolvedBy` | Relationship | No | `Operator` who resolved |
| `resolvedAt` | DateTime | No | Resolution timestamp |
| `resolution` | String | No | Resolution notes |
| `timestamp` | DateTime | Yes | Alert generation timestamp |
| `createdAt` | DateTime | Yes | Entity creation timestamp |

### JSON-LD @context (Alert)

```json
{
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-context.jsonld",
    {
      "sf": "https://smart-factory.example.com/ns/ont/factory#",
      "name": "https://schema.org/name",
      "severity": "sf:alertSeverity",
      "category": "sf:alertCategory",
      "description": "https://schema.org/description",
      "status": "sf:alertStatus",
      "triggeredBy": {
        "@type": "@id",
        "@id": "sf:triggeredBy"
      },
      "acknowledgedBy": {
        "@type": "@id",
        "@id": "sf:acknowledgedBy"
      },
      "acknowledgedAt": "sf:acknowledgedAt",
      "resolvedBy": {
        "@type": "@id",
        "@id": "sf:resolvedBy"
      },
      "resolvedAt": "sf:resolvedAt",
      "resolution": "sf:resolution",
      "timestamp": "http://www.w3.org/ns/prov#generatedAtTime",
      "createdAt": "http://www.w3.org/ns/prov#generatedAtTime"
    }
  ]
}
```

### Example Entity

```json
{
  "id": "urn:ngsi-ld:Alert:alert-001",
  "type": "Alert",
  "name": "Conveyor Speed Anomaly",
  "severity": {
    "type": "Text",
    "value": "warning"
  },
  "category": {
    "type": "Text",
    "value": "anomaly"
  },
  "description": {
    "type": "Text",
    "value": "Conveyor A speed deviation >15% from setpoint"
  },
  "status": {
    "type": "Text",
    "value": "active"
  },
  "triggeredBy": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Module:conveyor-a"
  },
  "timestamp": {
    "type": "DateTime",
    "value": "2026-10-20T10:35:00Z"
  },
  "createdAt": {
    "type": "DateTime",
    "value": "2026-10-20T10:35:00Z"
  }
}
```

---

## 7. Incident Entity

Represents a recorded incident with root cause analysis.

### Properties

| Property | Type | Mandatory | Description |
|----------|------|-----------|-------------|
| `id` | URI | Yes | Full NGSI-LD entity ID |
| `type` | String | Yes | Fixed: `Incident` |
| `name` | String | Yes | Incident name/identifier |
| `incidentType` | String | Yes | `safety`, `equipment_failure`, `quality`, `production_delay`, `security` |
| `severity` | String | Yes | `low`, `medium`, `high`, `critical` |
| `description` | String | Yes | Incident description |
| `status` | String | Yes | `open`, `investigating`, `mitigated`, `closed` |
| `timeline` | Array[Object] | No | Incident timeline events |
| `rootCause` | String | No | Root cause analysis |
| `impactedEntities` | Relationship | No | Entities affected |
| `reportedBy` | Relationship | No | `Operator` who reported |
| `assignedTo` | Relationship | No | `Operator` responsible for resolution |
| `resolvedAt` | DateTime | No | Resolution timestamp |
| `occurredAt` | DateTime | Yes | Incident occurrence timestamp |
| `createdAt` | DateTime | Yes | Entity creation timestamp |
| `modifiedAt` | DateTime | No | Last modification timestamp |

### JSON-LD @context (Incident)

```json
{
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-context.jsonld",
    {
      "sf": "https://smart-factory.example.com/ns/ont/factory#",
      "name": "https://schema.org/name",
      "incidentType": "sf:incidentType",
      "severity": "sf:incidentSeverity",
      "description": "https://schema.org/description",
      "status": "sf:incidentStatus",
      "timeline": "sf:timeline",
      "rootCause": "sf:rootCause",
      "impactedEntities": {
        "@type": "@id",
        "@id": "sf:impactedEntities"
      },
      "reportedBy": {
        "@type": "@id",
        "@id": "sf:reportedBy"
      },
      "assignedTo": {
        "@type": "@id",
        "@id": "sf:assignedTo"
      },
      "resolvedAt": "sf:resolvedAt",
      "occurredAt": "sf:occurredAt",
      "createdAt": "http://www.w3.org/ns/prov#generatedAtTime",
      "modifiedAt": "http://www.w3.org/ns/prov#invalidatedAtTime"
    }
  ]
}
```

### Example Entity

```json
{
  "id": "urn:ngsi-ld:Incident:inc-001",
  "type": "Incident",
  "name": "Conveyor Motor Overheat",
  "incidentType": {
    "type": "Text",
    "value": "equipment_failure"
  },
  "severity": {
    "type": "Text",
    "value": "high"
  },
  "description": {
    "type": "Text",
    "value": "Conveyor A motor temperature exceeded 80°C threshold"
  },
  "status": {
    "type": "Text",
    "value": "mitigated"
  },
  "timeline": {
    "type": "Array",
    "value": [
      {
        "timestamp": "2026-10-20T09:00:00Z",
        "event": "Alert triggered",
        "source": "urn:ngsi-ld:Alert:alert-001"
      },
      {
        "timestamp": "2026-10-20T09:15:00Z",
        "event": "Operator acknowledged",
        "source": "urn:ngsi-ld:Operator:op-001"
      },
      {
        "timestamp": "2026-10-20T10:00:00Z",
        "event": "Motor cooled and inspected",
        "source": "urn:ngsi-ld:Operator:op-002"
      }
    ]
  },
  "rootCause": {
    "type": "Text",
    "value": "Insufficient ventilation due to dust accumulation"
  },
  "impactedEntities": {
    "type": "Relationship",
    "value": ["urn:ngsi-ld:Module:conveyor-a"]
  },
  "reportedBy": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Operator:op-001"
  },
  "assignedTo": {
    "type": "Relationship",
    "value": "urn:ngsi-ld:Operator:op-002"
  },
  "occurredAt": {
    "type": "DateTime",
    "value": "2026-10-20T09:00:00Z"
  },
  "createdAt": {
    "type": "DateTime",
    "value": "2026-10-20T09:00:00Z"
  },
  "modifiedAt": {
    "type": "DateTime",
    "value": "2026-10-20T10:00:00Z"
  }
}
```

---

## Entity Relationships

### Relationship Diagram

```
Operator
    │
    ├── createdBy ──► Job
    │
    ├── acknowledgedBy ──► Alert
    │
    ├── reportedBy ──► Incident
    │
    └── assignedTo ──► Incident / Job
```

```
Module
    │
    ├── controlledBy ──► Device
    │
    ├── hasJob ──► Job
    │
    └── processes ──► Material
```

```
Job
    │
    ├── createdBy ──► Operator
    │
    ├── assignedTo ──► Module / Device
    │
    ├── usesMaterials ──► Material
    │
    └── produces ──► Material
```

```
Material
    │
    ├── sourceModule ──► Module
    │
    ├── destinationModule ──► Module
    │
    └── belongsToJob ──► Job
```

```
Alert
    │
    └── triggeredBy ──► (Device / Module / Material)
```

```
Incident
    │
    ├── impactedEntities ──► (Device / Module / Material)
    │
    ├── reportedBy ──► Operator
    │
    └── assignedTo ──► Operator
```

### Relationship Summary Table

| Source Entity | Relationship | Target Entity | Cardinality |
|---------------|--------------|---------------|-------------|
| Device | `controlledBy` | Module | N:1 |
| Module | `controlledBy` | Device | N:1 |
| Module | `hasJob` | Job | N:1 |
| Module | `processes` | Material | N:M |
| Job | `createdBy` | Operator | N:1 |
| Job | `assignedTo` | Module / Device | N:1 |
| Job | `usesMaterials` | Material | N:M |
| Job | `produces` | Material | N:M |
| Material | `sourceModule` | Module | N:1 |
| Material | `destinationModule` | Module | N:1 |
| Material | `belongsToJob` | Job | N:1 |
| Alert | `triggeredBy` | Device / Module / Material | N:1 |
| Alert | `acknowledgedBy` | Operator | N:1 |
| Alert | `resolvedBy` | Operator | N:1 |
| Incident | `reportedBy` | Operator | N:1 |
| Incident | `assignedTo` | Operator | N:1 |
| Incident | `impactedEntities` | Device / Module / Material | N:M |
| Device | `owner` | Operator | N:1 |

---

## NGSI-LD Type Registration

### Registration Payload (Orion-LD)

```json
{
  "id": "urn:ngsi-ld:TypeRegistration:smart-factory-types",
  "type": "ContextRegistration",
  "information": [
    {
      "entities": [
        {
          "idPattern": "urn:ngsi-ld:Device:.*",
          "type": "Device"
        },
        {
          "idPattern": "urn:ngsi-ld:Module:.*",
          "type": "Module"
        },
        {
          "idPattern": "urn:ngsi-ld:Job:.*",
          "type": "Job"
        },
        {
          "idPattern": "urn:ngsi-ld:Material:.*",
          "type": "Material"
        },
        {
          "idPattern": "urn:ngsi-ld:Operator:.*",
          "type": "Operator"
        },
        {
          "idPattern": "urn:ngsi-ld:Alert:.*",
          "type": "Alert"
        },
        {
          "idPattern": "urn:ngsi-ld:Incident:.*",
          "type": "Incident"
        }
      ],
      "provides": [
        {
          "id": "urn:ngsi-ld:ContextSource:smart-factory",
          "type": "ContextSource",
          "endpoint": "http://iot-gateway:8080/ngsi-ld/v1"
        }
      ]
    }
  ]
}
```

### JSON-LD Context Document

Create a dedicated context document at `https://smart-factory.example.com/ngsi-context.jsonld`:

```json
{
  "@context": {
    "ngsi-ld": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-context.jsonld",
    "sf": "https://smart-factory.example.com/ns/ont/factory#",
    "schema.org": "https://schema.org/",
    "prov": "http://www.w3.org/ns/prov#",

    "Device": "sf:Device",
    "Module": "sf:Module",
    "Job": "sf:Job",
    "Material": "sf:Material",
    "Operator": "sf:Operator",
    "Alert": "sf:Alert",
    "Incident": "sf:Incident",

    "deviceType": "sf:deviceType",
    "deviceId": "sf:deviceId",
    "firmwareVersion": "sf:firmwareVersion",
    "capabilities": "sf:capabilities",
    "moduleType": "sf:moduleType",
    "zone": "sf:zone",
    "line": "sf:line",
    "jobType": "sf:jobType",
    "priority": "sf:priority",
    "progress": "sf:progress",
    "materialType": "sf:materialType",
    "sku": "sf:sku",
    "quantity": "sf:quantity",
    "unit": "sf:unit",
    "employeeId": "sf:employeeId",
    "operatorRole": "sf:operatorRole",
    "authorizationLevel": "sf:authorizationLevel",
    "assignedZone": "sf:assignedZone",
    "certifications": "sf:certifications",
    "alertSeverity": "sf:alertSeverity",
    "alertCategory": "sf:alertCategory",
    "incidentType": "sf:incidentType",
    "incidentSeverity": "sf:incidentSeverity",
    "timeline": "sf:timeline",
    "rootCause": "sf:rootCause",

    "ownedBy": {
      "@type": "@id",
      "@id": "sf:ownedBy"
    },
    "controlledBy": {
      "@type": "@id",
      "@id": "sf:controlledBy"
    },
    "hasJob": {
      "@type": "@id",
      "@id": "sf:hasJob"
    },
    "processes": {
      "@type": "@id",
      "@id": "sf:processes"
    },
    "createdBy": {
      "@type": "@id",
      "@id": "sf:createdBy"
    },
    "assignedTo": {
      "@type": "@id",
      "@id": "sf:assignedTo"
    },
    "usesMaterials": {
      "@type": "@id",
      "@id": "sf:usesMaterials"
    },
    "produces": {
      "@type": "@id",
      "@id": "sf:produces"
    },
    "sourceModule": {
      "@type": "@id",
      "@id": "sf:sourceModule"
    },
    "destinationModule": {
      "@type": "@id",
      "@id": "sf:destinationModule"
    },
    "belongsToJob": {
      "@type": "@id",
      "@id": "sf:belongsToJob"
    },
    "triggeredBy": {
      "@type": "@id",
      "@id": "sf:triggeredBy"
    },
    "acknowledgedBy": {
      "@type": "@id",
      "@id": "sf:acknowledgedBy"
    },
    "resolvedBy": {
      "@type": "@id",
      "@id": "sf:resolvedBy"
    },
    "impactedEntities": {
      "@type": "@id",
      "@id": "sf:impactedEntities"
    },
    "reportedBy": {
      "@type": "@id",
      "@id": "sf:reportedBy"
    }
  }
}
```

---

## JSON Schema Validation

### Device JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://smart-factory.example.com/schemas/device.json",
  "title": "Device",
  "type": "object",
  "required": ["id", "type", "name", "deviceType", "deviceId", "capabilities", "status", "createdAt"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^urn:ngsi-ld:Device:.*$"
    },
    "type": {
      "const": "Device"
    },
    "name": {
      "type": "string"
    },
    "deviceType": {
      "type": "string",
      "enum": ["esp32_bridge", "mega_reference", "simulator", "iot_gateway"]
    },
    "deviceId": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9_-]{0,62}[a-z0-9]$"
    },
    "firmwareVersion": {
      "type": "string"
    },
    "capabilities": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "status": {
      "type": "string",
      "enum": ["online", "offline", "maintenance", "error"]
    },
    "location": {
      "$ref": "https://smart-factory.example.com/schemas/geojson.json#/definitions/Point"
    },
    "owner": {
      "$ref": "#/definitions/relationship"
    },
    "controlledBy": {
      "$ref": "#/definitions/relationship"
    },
    "lastSeen": {
      "type": "string",
      "format": "date-time"
    },
    "createdAt": {
      "type": "string",
      "format": "date-time"
    },
    "modifiedAt": {
      "type": "string",
      "format": "date-time"
    }
  },
  "definitions": {
    "relationship": {
      "type": "object",
      "properties": {
        "type": { "const": "Relationship" },
        "value": { "type": "string" }
      },
      "required": ["type", "value"]
    }
  }
}
```

### Additional Schemas

For brevity, the following JSON Schemas follow the same pattern and should be created:
- `module.json` — Module entity validation
- `job.json` — Job entity validation  
- `material.json` — Material entity validation
- `operator.json` — Operator entity validation
- `alert.json` — Alert entity validation
- `incident.json` — Incident entity validation
- `geojson.json` — GeoJSON Point/Polygon definitions

---

## Integration Notes

### IoT Gateway → Orion-LD Flow

```
MQTT Broker ──► IoT Gateway ──► Orion-LD ──► Subscribers
                   │              │
                   │              └──► Temporal queries
                   │
                   └──► Normalize & enrich
```

### Entity Upsert Example (IoT Gateway → Orion-LD)

```bash
# Create or update a Module entity
curl -X POST 'http://localhost:1026/ngsi-ld/v1/entities/' \
  -H 'Content-Type: application/ld+json' \
  -H 'Link: <https://smart-factory.example.com/ngsi-context.jsonld>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"' \
  -d '{
    "id": "urn:ngsi-ld:Module:conveyor-a",
    "type": "Module",
    "name": { "type": "Text", "value": "Conveyor Belt A" },
    "moduleType": { "type": "Text", "value": "conveyor" },
    "status": { "type": "Text", "value": "running" },
    "location": {
      "type": "GeoProperty",
      "value": { "type": "Point", "coordinates": [105.4456, 10.3732] }
    }
  }'
```

### Subscription Example

```bash
# Subscribe to all Module status changes
curl -X POST 'http://localhost:1026/ngsi-ld/v1/subscriptions/' \
  -H 'Content-Type: application/ld+json' \
  -d '{
    "type": "Subscription",
    "entities": [{ "type": "Module" }],
    "watchedAttributes": ["status"],
    "notification": {
      "endpoint": {
        "uri": "http://iot-gateway:8080/notifications",
        "accept": "application/json"
      }
    }
  }'
```

---

## Acceptance Criteria Checklist

- [x] Entity schema defined for all 7 entity types
- [x] JSON-LD @context mappings for all entity types
- [x] Relationships defined between entities
- [x] GeoJSON location support for Device and Module entities
- [x] NGSI-LD type registration for Orion-LD
- [x] JSON Schema validation files referenced
- [x] Physical factory modules mapped to Module entity types

## Physical Module Mapping

| Physical Module | moduleType | Entity ID Example |
|----------------|------------|-------------------|
| Forklift | `forklift` | `urn:ngsi-ld:Module:forklift-1` |
| Dump Truck | `dump_truck` | `urn:ngsi-ld:Module:dump-truck-1` |
| Bracket | `bracket` | `urn:ngsi-ld:Module:bracket-1` |
| Packaging Machine | `packaging` | `urn:ngsi-ld:Module:packaging-1` |
| Conveyor Belt | `conveyor` | `urn:ngsi-ld:Module:conveyor-a` |
| Sorting Machine | `sorting` | `urn:ngsi-ld:Module:sorting-1` |
| Tower Crane | `crane` | `urn:ngsi-ld:Module:crane-1` |
| Parking Lot | `parking` | `urn:ngsi-ld:Module:parking-lot-1` |
| Combine Modules | `combine` | `urn:ngsi-ld:Module:combine-1` |

---

## References

- [NGSI-LD Specification](https://forge.etsi.org/rep/IoT/传感网络Specifications/blob/master/ngsi-ld.md)
- [Orion-LD Documentation](https://fiware-orion-ld.readthedocs.io/)
- [JSON-LD Contexts](https://json-ld.org/)
- [FIWARE Data Models](https://fiware.github.io/data-models/)
- [ADR-0014](./adr-0014-orion-ld-selection.md) — Orion-LD Selection (to be created)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-10-20 | Initial draft for Smart Factory NGSI-LD entity schema |
