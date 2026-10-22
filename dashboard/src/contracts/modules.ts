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

export interface DerivedModuleState {
  visualState: VisualState;
  lastSeen?: string;
  rawState?: string;
}

export function deriveModuleState(
  moduleDef: ModuleDefinition | null | undefined,
  statuses: DeviceStatusInput | DeviceStatusInput[] | undefined,
  now: number = Date.now()
): DerivedModuleState | null {
  if (!moduleDef) {
    return null;
  }

  // TC-2: brackets-01 never reports RUNNING
  if (moduleDef.moduleId === 'brackets-01') {
    return { visualState: 'UNKNOWN' };
  }

  const statusList = Array.isArray(statuses) ? statuses : statuses ? [statuses] : [];
  const deviceStatus = statusList.find((s) => s.device_id === moduleDef.moduleId);

  if (!deviceStatus) {
    return { visualState: 'UNKNOWN' };
  }

  if (deviceStatus.status === 'offline') {
    return { visualState: 'OFFLINE', lastSeen: deviceStatus.last_heartbeat_at || deviceStatus.timestamp };
  }

  if (deviceStatus.stale) {
    return { visualState: 'STALE', lastSeen: deviceStatus.last_heartbeat_at || deviceStatus.timestamp };
  }

  if (deviceStatus.last_heartbeat_at || deviceStatus.timestamp) {
    const timeStr = deviceStatus.last_heartbeat_at || deviceStatus.timestamp!;
    const time = new Date(timeStr).getTime();
    if (!isNaN(time) && now - time > STALE_THRESHOLD_MS) {
      return { visualState: 'STALE', lastSeen: timeStr };
    }
  }

  const rawState = deviceStatus.state;
  if (rawState === 'RUNNING' || rawState === 'MOVING' || rawState === 'ROUTING' || rawState === 'DUMPING' || rawState === 'SEALING') {
    return { visualState: 'RUNNING', rawState };
  }

  if (rawState === 'FAULT' || rawState === 'ERROR' || rawState === 'E_STOP') {
    return { visualState: 'FAULT', rawState };
  }

  return { visualState: 'SIMULATED', rawState: rawState || 'IDLE' };
}
