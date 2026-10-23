export type VisualState = 'UNKNOWN' | 'STALE' | 'OFFLINE' | 'SIMULATED' | 'RUNNING' | 'FAULT';

export interface ModuleDefinition {
  moduleId: string;
  name: string;
  role: string;
  moduleType: string;
  uiComponent: string;
  category?: 'production' | 'logistics' | 'control';
  description?: string;
  hasTelemetry?: boolean;
  controllerSource?: string;
  unityObject?: string;
  unit?: string;
}

export const MODULE_DEFINITIONS: ModuleDefinition[] = [
  {
    moduleId: 'conveyor-01',
    name: 'Conveyor',
    role: 'Material feed',
    moduleType: 'conveyor',
    uiComponent: 'ConveyorCard',
    category: 'logistics',
    description: 'Material transport and continuous feed conveyor system',
    hasTelemetry: true,
    controllerSource: 'ESP32-uKit (L0)',
    unityObject: 'Conveyor_01',
    unit: 'm/s',
  },
  {
    moduleId: 'sorting-01',
    name: 'Sorting',
    role: 'Classification/routing',
    moduleType: 'sorting',
    uiComponent: 'SortingCard',
    category: 'logistics',
    description: 'Optical classification and pneumatic routing station',
    hasTelemetry: true,
    controllerSource: 'ESP32-uKit (L0)',
    unityObject: 'Sorting_01',
    unit: 'items/min',
  },
  {
    moduleId: 'tower-crane-01',
    name: 'Tower Crane',
    role: 'Lift/place',
    moduleType: 'crane',
    uiComponent: 'CraneCard',
    category: 'production',
    description: 'Heavy payload lift and precision placement crane',
    hasTelemetry: true,
    controllerSource: 'MEGA-uKit (L0)',
    unityObject: 'TowerCrane_01',
    unit: 'deg',
  },
  {
    moduleId: 'parking-01',
    name: 'Parking',
    role: 'Vehicle staging',
    moduleType: 'parking',
    uiComponent: 'ParkingLotCard',
    category: 'logistics',
    description: 'Automated vehicle staging and bay allocation system',
    hasTelemetry: true,
    controllerSource: 'ESP32-uKit (L0)',
    unityObject: 'Parking_01',
    unit: 'slots',
  },
  {
    moduleId: 'forklift-01',
    name: 'Forklift',
    role: 'Pallet transport',
    moduleType: 'forklift',
    uiComponent: 'ForkliftCard',
    category: 'logistics',
    description: 'Autonomous guided forklift for pallet retrieval',
    hasTelemetry: true,
    controllerSource: 'ESP32-uKit (L0)',
    unityObject: 'Forklift_01',
    unit: 'm/s',
  },
  {
    moduleId: 'dump-truck-01',
    name: 'Dump Truck',
    role: 'Bulk-material delivery',
    moduleType: 'dump_truck',
    uiComponent: 'DumpTruckCard',
    category: 'logistics',
    description: 'Automated tipper truck for bulk raw material drop-off',
    hasTelemetry: true,
    controllerSource: 'ESP32-uKit (L0)',
    unityObject: 'DumpTruck_01',
    unit: 'kg',
  },
  {
    moduleId: 'packaging-01',
    name: 'Packaging',
    role: 'Package/seal',
    moduleType: 'packaging',
    uiComponent: 'PackagingCard',
    category: 'production',
    description: 'Automated carton packing and sealing cell',
    hasTelemetry: true,
    controllerSource: 'ESP32-uKit (L0)',
    unityObject: 'Packaging_01',
    unit: 'packs/min',
  },
  {
    moduleId: 'brackets-01',
    name: 'Brackets',
    role: 'Structural support',
    moduleType: 'bracket',
    uiComponent: 'BracketCard',
    category: 'production',
    description: 'Passive structural mounting bracket (no sensors attached)',
    hasTelemetry: false,
    controllerSource: 'N/A (Structural)',
    unityObject: 'Brackets_01',
    unit: 'N/A',
  },
  {
    moduleId: 'combine-01',
    name: 'Combine',
    role: 'Workflow coordinator',
    moduleType: 'combine',
    uiComponent: 'CombineCard',
    category: 'control',
    description: 'Master workflow coordinator and cell integration hub',
    hasTelemetry: true,
    controllerSource: 'ESP32-uKit (L0)',
    unityObject: 'Combine_01',
    unit: 'jobs/hr',
  },
];

export const MODULE_TYPES = MODULE_DEFINITIONS.map((m) => m.moduleType);
export const STALE_THRESHOLD_MS = 60000;

export function findModule(moduleId: string | undefined): ModuleDefinition | null {
  if (!moduleId) return null;
  return MODULE_DEFINITIONS.find((m) => m.moduleId === moduleId) || null;
}

export const allDeviceIds = MODULE_DEFINITIONS.map((m) => m.moduleId);

export interface DeviceStatusInput {
  device_id: string;
  status?: 'online' | 'offline' | string;
  state?: string;
  last_heartbeat_at?: string;
  timestamp?: string;
  stale?: boolean;
}

/**
 * Provenance of the data backing a derived state.
 * - 'live'      : gateway-reported telemetry/state
 * - 'simulated' : explicitly simulated or replay data
 */
export type StateProvenance = 'live' | 'simulated';

export interface DeriveOptions {
  /** Evaluation clock; defaults to Date.now(). */
  now?: number;
  /** Provenance of the underlying data; SIMULATED is only reachable when explicitly simulated. */
  provenance?: StateProvenance;
}

export interface DerivedModuleState {
  visualState: VisualState;
  lastSeen?: string;
  rawState?: string;
  provenance?: StateProvenance;
}

/** Maximum tolerated clock skew for an accepted heartbeat (ms). */
export const MAX_CLOCK_SKEW_MS = 5000;

/** Raw firmware/gateway states that indicate real motion or active production. */
const RUNNING_STATES = ['RUNNING', 'MOVING', 'ROUTING', 'DUMPING', 'SEALING', 'LIFTING', 'CHARGING'] as const;

/** Raw firmware/gateway states that indicate a fault or emergency stop. */
const FAULT_STATES = ['FAULT', 'ERROR', 'E_STOP', 'E_STOP_ACTIVE', 'OVERCURRENT', 'OVERTEMP'] as const;

/** Raw firmware/gateway states explicitly flagged as simulated by the gateway. */
const SIMULATED_STATES = ['SIMULATED', 'DEMO', 'MOCK', 'REPLAY', 'SYNTHETIC'] as const;

function parseTimestamp(value: string | undefined): number | null {
  if (!value) return null;
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? null : parsed;
}

/**
 * Derive the operator-visible state of a canonical module from gateway device status.
 *
 * Fail-closed rules (never fabricate a trustworthy-looking state):
 * - Unknown module, unknown device, or an absent/parsable-invalid heartbeat yields `UNKNOWN`.
 * - A heartbeat in the future beyond {@link MAX_CLOCK_SKEW_MS} is rejected as `UNKNOWN`.
 * - A heartbeat older than {@link STALE_THRESHOLD_MS} yields `STALE` and can never be `RUNNING`.
 * - A passive module without sensors yields `UNKNOWN` regardless of any reported state (TC-2).
 * - `SIMULATED` is only returned when provenance is explicitly simulated, or the gateway
 *   explicitly reports a simulated state. It is never a fallback for unclassified live data.
 */
export function deriveModuleState(
  moduleDef: ModuleDefinition | null | undefined,
  statuses: DeviceStatusInput | DeviceStatusInput[] | undefined,
  options: number | DeriveOptions = {}
): DerivedModuleState | null {
  if (!moduleDef) {
    return null;
  }

  const opts: DeriveOptions = typeof options === 'number' ? { now: options } : options;
  const now = opts.now ?? Date.now();
  const provenance: StateProvenance | undefined = opts.provenance;

  // TC-2: passive structural module (no sensors attached) never reports an operational state.
  if (moduleDef.moduleId === 'brackets-01' || moduleDef.hasTelemetry === false) {
    return { visualState: 'UNKNOWN', provenance };
  }

  const statusList = Array.isArray(statuses) ? statuses : statuses ? [statuses] : [];
  const deviceStatus = statusList.find((s) => s.device_id === moduleDef.moduleId);

  if (!deviceStatus) {
    return { visualState: 'UNKNOWN', provenance };
  }

  const rawState = deviceStatus.state;
  const lastSeen = deviceStatus.last_heartbeat_at || deviceStatus.timestamp;
  const lastSeenMs = parseTimestamp(lastSeen);

  // A gateway that explicitly reports a simulated state is trusted as such.
  if (rawState && SIMULATED_STATES.includes(rawState.toUpperCase() as (typeof SIMULATED_STATES)[number])) {
    return { visualState: 'SIMULATED', lastSeen, rawState, provenance: 'simulated' };
  }

  // Explicit offline status is reported as-is (the gateway is authoritative).
  if (deviceStatus.status === 'offline') {
    return { visualState: 'OFFLINE', lastSeen, rawState, provenance };
  }

  // Fail closed: without a parsable heartbeat we cannot assert freshness.
  if (lastSeenMs === null) {
    return { visualState: 'UNKNOWN', rawState, provenance };
  }

  // Reject impossible future timestamps beyond tolerated clock skew.
  if (lastSeenMs - now > MAX_CLOCK_SKEW_MS) {
    return { visualState: 'UNKNOWN', rawState, provenance };
  }

  const isStaleByClock = now - lastSeenMs > STALE_THRESHOLD_MS;
  if (deviceStatus.stale || isStaleByClock) {
    return { visualState: 'STALE', lastSeen, rawState, provenance };
  }

  // Fault states outrank motion states.
  if (rawState && FAULT_STATES.includes(rawState.toUpperCase() as (typeof FAULT_STATES)[number])) {
    return { visualState: 'FAULT', lastSeen, rawState, provenance };
  }

  if (rawState && RUNNING_STATES.includes(rawState.toUpperCase() as (typeof RUNNING_STATES)[number])) {
    return { visualState: 'RUNNING', lastSeen, rawState, provenance };
  }

  // SIMULATED requires explicit provenance; unclassified live data fails closed to UNKNOWN.
  if (provenance === 'simulated') {
    return { visualState: 'SIMULATED', lastSeen, rawState, provenance };
  }

  return { visualState: 'UNKNOWN', lastSeen, rawState, provenance };
}
