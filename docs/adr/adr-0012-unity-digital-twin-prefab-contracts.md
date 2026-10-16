# ADR-0012: Unity Digital Twin Prefab Contracts

**Status:** Proposed
**Date:** 2026-10-16
**Deciders:** Issue #33
**Related issues:** #33 #34 #35

## Context

The Smart Factory project includes a planned Unity Digital Twin (S2) that must visualize and synchronize with the physical nine-module factory (S1). The iot-gateway provides a WebSocket stream and REST API exposing normalized canonical events. This ADR documents the contracts that Unity prefabs must implement to consume these events — the data schemas, state machine, and coordinate mapping — without creating actual Unity assets.

The repository contains:
- ESP32-uKit bridge with MQTT telemetry (`esp32-ukit-bridge/docs/mqtt-contract.md`)
- Python iot-gateway with event normalization (`iot-gateway/src/iot_gateway/`)
- JSON schemas for telemetry and device events (`contracts/v1/schemas/`)
- Nine factory modules defined in PROJECT_CONTEXT.md

## Decision

We define the following renderer-independent contracts for Unity consumption:

### 1. Nine Factory Modules

Each module is identified by its ESP32 bridge `device_id`. The current implementation treats each ESP32 as a single device; module-specific telemetry is embedded in the `values` array or `pairs` object.

| Module | Bridge Owner | Telemetry Topic | Command Interface | AMLP Envelope Shape |
|--------|--------------|-----------------|-------------------|---------------------|
| Forklift | ESP32-UKIT-01 | `smart-factory/ukit-*/telemetry` | CONVEYOR_START/STOP | `TEL,FORKLIFT,<state>,<speed>,SENSOR*=*` |
| Dump Truck | ESP32-UKIT-02 | `smart-factory/ukit-*/telemetry` | CONVEYOR_START/STOP | `TEL,DUMPTRUCK,<state>,<speed>,SENSOR*=*` |
| Bracket | ESP32-UKIT-03 | `smart-factory/ukit-*/telemetry` | CONVEYOR_START/STOP | `TEL,BRACKET,<state>,<speed>,SENSOR*=*` |
| Packaging Machine | ESP32-UKIT-04 | `smart-factory/ukit-*/telemetry` | CONVEYOR_START/STOP | `TEL,PACKAGING,<state>,<speed>,SENSOR*=*` |
| Conveyor Belt | ESP32-UKIT-05 | `smart-factory/ukit-*/telemetry` | CONVEYOR_START/STOP | `TEL,CONVEYOR,<state>,<speed>,SENSOR*=*` |
| Sorting Machine | ESP32-UKIT-06 | `smart-factory/ukit-*/telemetry` | CONVEYOR_START/STOP | `TEL,SORTING,<state>,<speed>,SENSOR*=*` |
| Tower Crane | ESP32-UKIT-07 | `smart-factory/ukit-*/telemetry` | CONVEYOR_START/STOP | `TEL,CRANE,<state>,<speed>,SENSOR*=*` |
| Parking Lot | ESP32-UKIT-08 | `smart-factory/ukit-*/telemetry` | CONVEYOR_START/STOP | `TEL,PARKING,<state>,<speed>,SENSOR*=*` |
| Combine/Integration | ESP32-UKIT-09 | `smart-factory/ukit-*/telemetry` | CONVEYOR_START/STOP | `TEL,COMBINE,<state>,<speed>,SENSOR*=*` |

**Limitation:** The current bridge firmware does not expose per-module device IDs. All nine modules report under a single `device_id` (e.g., `ukit-00000000`). The module type must be inferred from the first value in the `values` array (e.g., `CONVEYOR`, `FORKLIFT`).

### 2. Unity-Compatible Canonical Event Contract

Unity consumers must parse the gateway's canonical event envelope:

```json
{
  "event_id": "uuid-v4",
  "device_id": "ukit-00000000",
  "event_type": "telemetry",
  "timestamp": "2026-10-16T10:00:00Z",
  "received_at": "2026-10-16T10:00:00.123Z",
  "payload": {
    "device_id": "ukit-00000000",
    "received_at_ms": 123456,
    "values": ["CONVEYOR", "RUNNING", "60"],
    "pairs": { "SENSOR1": "1" }
  },
  "sequence": 42,
  "trace_id": "uuid-v4-optional"
}
```

**Unity-specific fields to extract:**

| Field | Source | Unity Mapping | Notes |
|-------|--------|---------------|-------|
| `device_id` | `payload.device_id` | `MonoBehaviour.name` | Prefab identifier |
| `module_type` | `payload.values[0]` | Enum: `ModuleType` | CONVEYOR, FORKLIFT, etc. |
| `state` | `payload.values[1]` | Enum: `ModuleState` | RUNNING, STOPPED, etc. |
| `speed` | `payload.values[2]` | `transform.position` / animation speed | Integer 0-255 |
| `sensors` | `payload.pairs` | ScriptableObject or dictionary | Key-value sensor readings |
| `timestamp` | Root level | `DateTime` field | UTC ISO8601 |
| `sequence` | Root level | `int` field | Ordering/deduplication |
| `received_at_ms` | `payload.received_at_ms` | `long` field | Monotonic timestamp |

### 3. Coordinate and State Mapping

**Current state (as of 2026-10-16):**

| Unity Property | Source Field | Gap |
|----------------|--------------|-----|
| `transform.position` | None | **No explicit X/Y/Z coordinates in telemetry** |
| `transform.rotation` | None | **No rotation data** |
| `animation.speed` | `payload.values[2]` (speed) | Available as integer |
| Custom state enum | `payload.values[1]` (state) | Available but no formal enum |
| Sensor dictionary | `payload.pairs` | Available as key-value |

**Identified gaps:**
1. **No position fields**: The current telemetry schema does not include X/Y/Z coordinates. Unity must either:
   - Use static scene placement (prefab coordinates are fixed)
   - Infer position from a separate position telemetry stream (not yet defined)
   - Add coordinate fields to a future telemetry schema extension

2. **No module type enum**: Module type is inferred from string values in `payload.values[0]`. A future schema should add an explicit `module_type` enum.

3. **No explicit staleness flag**: The bridge documentation mentions 60-second timeout for staleness detection, but this is not exposed in the event envelope. Unity must implement staleness detection by tracking `received_at_ms` timestamps.

### 4. Scene Object Contract

Unity prefabs must implement the following contract to consume gateway events:

```csharp
// Required: ModuleType enum (extend as needed)
public enum ModuleType {
    Unknown = 0,
    Forklift = 1,
    DumpTruck = 2,
    Bracket = 3,
    Packaging = 4,
    Conveyor = 5,
    Sorting = 6,
    TowerCrane = 7,
    Parking = 8,
    Combine = 9
}

// Required: ModuleState enum
public enum ModuleState {
    Unknown = 0,
    Running = 1,
    Stopped = 2,
    Error = 3,
    Offline = 4
}

// Required: MonoBehaviour interface
public interface IFactoryModuleReceiver {
    string DeviceId { get; }
    ModuleType ModuleType { get; }
    ModuleState State { get; set; }
    int Speed { get; set; }
    Dictionary<string, string> Sensors { get; set; }
    DateTime LastUpdate { get; set; }
    bool IsStale { get; }
}

// Required: Prefab must implement IFactoryModuleReceiver
public class ConveyorModule : MonoBehaviour, IFactoryModuleReceiver {
    public string DeviceId { get; private set; }
    public ModuleType ModuleType => ModuleType.Conveyor;
    public ModuleState State { get; set; }
    public int Speed { get; set; }
    public Dictionary<string, string> Sensors { get; set; }
    public DateTime LastUpdate { get; set; }

    // Stale detection: mark stale if no update for 60 seconds
    public bool IsStale => (DateTime.UtcNow - LastUpdate).TotalSeconds > 60;

    public void OnCanonicalEvent(CanonicalEvent evt) { /* parse payload */ }
}
```

**WebSocket consumption pattern:**
```csharp
// Unity WebSocket client connects to: ws://<gateway-host>:8765/
// Receives JSON CanonicalEvent objects
// Must handle: reconnection, message ordering, staleness
```

**REST API snapshot:**
```csharp
// GET http://<gateway-host>:8000/events?device_id=ukit-*&limit=100
// Returns: { "events": [...], "count": N }
```

### 5. ADR Reference

This ADR follows the format defined in `adr-TEMPLATE.md` and builds upon:
- ADR-0002: Bridge MQTT-AMLP Contract
- ADR-0005: Gateway Canonical Event Envelope

## Consequences

**Easier:**
- Unity developers have a clear contract to implement
- WebSocket and REST API are already functional
- Telemetry schema provides backward compatibility

**Harder:**
- No explicit coordinates — Unity must use static positioning or await schema extension
- No explicit module type — requires string parsing from telemetry values
- Staleness must be client-side calculated (60s timeout not in schema)

**Limitations to communicate:**
1. Unity prefabs cannot be dynamically positioned without schema changes
2. Module type is implicit, not explicit in the event envelope
3. Physical positions must be hardcoded in Unity scene or inferred from separate sensors

## Alternatives considered

**Option A: Wait for explicit coordinate fields**
- Defer Unity implementation until telemetry schema adds explicit X/Y/Z fields
- Rejected: blocks current Unity development; static positioning is acceptable for initial demo

**Option B: Add coordinates to schema now**
- Extend `telemetry.schema.json` with `position_x`, `position_y`, `position_z`
- Rejected: hardware does not currently provide position data; schema would be aspirational without sensor evidence

**Option C: Document current gaps (chosen)**
- Implement Unity contract with current schema
- Document gaps explicitly
- Plan future schema extensions as separate issues

## Evidence

- `esp32-ukit-bridge/docs/mqtt-contract.md` — current MQTT topics, AMLP envelope, telemetry format
- `iot-gateway/src/iot_gateway/models.py` — `CanonicalEvent` dataclass definition
- `iot-gateway/src/iot_gateway/event_normalizer.py` — event normalization logic
- `contracts/v1/schemas/telemetry.schema.json` — telemetry JSON schema (no coordinates)
- `contracts/v1/schemas/device-event.schema.json` — canonical event envelope schema
- `docs/PROJECT_CONTEXT.md` — nine factory module definitions
- Issue #33: Unity prefab contracts for nine factory modules
- Issue #34: Unity time synchronization and stale/offline recovery
