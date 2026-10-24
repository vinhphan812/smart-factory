/**
 * Reference TypeScript binding for the Gateway northbound consumer fixture.
 *
 * Implements the projection rule defined in `contracts/gateway/fixtures/README.md` §3
 * against the recording in `contracts/gateway/fixtures/northbound-fixture.v1.json`.
 *
 * This is a REFERENCE ARTEFACT, not production code. The production React client lives in
 * `dashboard/src/api/websocket.ts` + `dashboard/src/api/gateway.ts`.
 *
 * Contract: contracts/gateway/northbound-fanout-contract.md §4 (SPEC-4).
 * Status: Specification. Evidence level: L0 (contract / static).
 */

/* ------------------------------------------------------------------ *
 * Wire types — mirror contracts/gateway/northbound-fanout.schema.json
 * ------------------------------------------------------------------ */

export type Connectivity = 'online' | 'offline' | 'unknown';
export type DataState = 'live' | 'stale' | 'uncertain' | 'unknown';
export type ClockDomain = 'utc' | 'device_monotonic' | 'unknown';
export type QualityStatus = 'good' | 'uncertain' | 'degraded' | 'invalid' | 'unknown';
export type EventType =
  | 'command_ack'
  | 'status_online'
  | 'status_offline'
  | 'telemetry'
  | 'heartbeat';

export interface Quality {
  status: QualityStatus;
  reason: string;
  stale: boolean;
  out_of_order: boolean;
  clock_domain: ClockDomain;
  latency_ms: number;
}

export interface CanonicalEvent {
  envelope_version?: string;
  event_id: string;
  device_id: string;
  module_id?: string | null;
  event_type: EventType;
  sequence: number;
  observed_at?: number | null;
  received_at: string;
  received_at_ms: number;
  boot_id?: string | null;
  units: Record<string, string>;
  quality: Quality;
  payload: Record<string, unknown>;
  mqtt_topic?: string;
  mqtt_timestamp_ms?: number;
  ingested_at?: string;
  stale?: boolean;
  out_of_order?: boolean;
  is_timestamp_synchronized?: boolean;
  latency_ms?: number;
  timestamp?: number;
}

export interface StreamFrame {
  envelope_version?: string;
  frame_type: 'event' | 'gap' | 'heartbeat';
  event?: CanonicalEvent;
  gap?: { from_sequence: number; to_sequence: number; reason: string };
  heartbeat?: { high_watermark: number; gateway_time: string };
}

export interface Snapshot {
  envelope_version?: string;
  cursor?: { high_watermark: number; last_sequence: number; since_sequence: number };
  high_watermark: number;
  snapshot_count: number;
  events: CanonicalEvent[];
  per_device_latest: Record<string, CanonicalEvent>;
  overflow?: boolean;
  overflow_limit?: number;
  resync_required?: boolean;
  oldest_retained_sequence?: number;
}

export interface Fixture {
  fixture_version: string;
  envelope_version: string;
  description: string;
  gateway: { service: string; version: string; http_port: number; ws_port: number };
  snapshot: Snapshot;
  frames: StreamFrame[];
  expected_state: {
    unity: ProjectedState;
    react: ProjectedState;
  };
}

/* ------------------------------------------------------------------ *
 * Projected state
 * ------------------------------------------------------------------ */

export interface ProjectedDeviceState {
  device_id: string;
  connectivity: Connectivity;
  data_state: DataState;
  last_event_type: string | null;
  last_sequence: number | null;
  last_event_id: string | null;
  boot_id: string | null;
  observed_at: number | null;
  received_at: string | null;
  clock_domain: ClockDomain;
  quality_status: QualityStatus;
  quality_reason: string;
  units: Record<string, string>;
  values: Record<string, string | number>;
  payload_state: string | null;
}

export interface ProjectedState {
  consumer: string;
  devices: Record<string, ProjectedDeviceState>;
  last_applied_sequence: number | null;
  resync_required: boolean;
  gap_detected: boolean;
  applied_event_ids: string[];
  dropped_duplicate_event_ids: string[];
}

/* ------------------------------------------------------------------ *
 * Projection rule (fixtures/README.md §3)
 * ------------------------------------------------------------------ */

interface Accumulator {
  device_id: string;
  connectivity: Connectivity;
  data_state: DataState;
  last_event_type: string | null;
  last_sequence: number | null;
  last_event_id: string | null;
  boot_id: string | null;
  observed_at: number | null;
  received_at: string | null;
  clock_domain: ClockDomain;
  quality_status: QualityStatus;
  quality_reason: string;
  units: Record<string, string>;
  values: Record<string, string | number>;
  payload_state: string | null;
  has_status: boolean;
  has_telemetry: boolean;
}

function newAccumulator(deviceId: string): Accumulator {
  return {
    device_id: deviceId,
    connectivity: 'unknown',
    data_state: 'unknown',
    last_event_type: null,
    last_sequence: null,
    last_event_id: null,
    boot_id: null,
    observed_at: null,
    received_at: null,
    clock_domain: 'unknown',
    quality_status: 'unknown',
    quality_reason: '',
    units: {},
    values: {},
    payload_state: null,
    has_status: false,
    has_telemetry: false,
  };
}

/** §3.5 — derive the measurement map from `payload.structured`. */
function deriveValues(payload: Record<string, unknown>): {
  values: Record<string, string | number>;
  payload_state: string | null;
} {
  const structured = payload['structured'];
  if (structured === undefined || structured === null || typeof structured !== 'object') {
    return { values: {}, payload_state: null };
  }
  const s = structured as Record<string, unknown>;
  const values: Record<string, string | number> = {};

  const state = s['state'];
  if (typeof state === 'string') {
    values['state'] = state;
  }
  const speed = s['speed'];
  if (typeof speed === 'number' || typeof speed === 'string') {
    values['speed'] = speed;
  }
  const sensors = s['sensors'];
  if (sensors !== undefined && sensors !== null && typeof sensors === 'object') {
    const sensorMap = sensors as Record<string, unknown>;
    const temperature = sensorMap['temperature_centi_c'];
    if (typeof temperature === 'number' || typeof temperature === 'string') {
      values['temperature'] = temperature;
    }
    const humidity = sensorMap['humidity_centi_percent'];
    if (typeof humidity === 'number' || typeof humidity === 'string') {
      values['humidity'] = humidity;
    }
  }
  return { values, payload_state: typeof state === 'string' ? state : null };
}

/** §3.4 — data freshness from the latest applied telemetry event. */
function dataStateFor(event: CanonicalEvent): DataState {
  const quality = event.quality;
  if (quality.status === 'uncertain') {
    return 'uncertain';
  }
  if (quality.status === 'degraded' || quality.stale === true) {
    return 'stale';
  }
  if (quality.status === 'good' && quality.stale !== true) {
    return 'live';
  }
  return 'unknown';
}

function applyEvent(acc: Accumulator, event: CanonicalEvent): void {
  acc.last_event_type = event.event_type;
  acc.last_sequence = event.sequence;
  acc.last_event_id = event.event_id;
  acc.boot_id = event.boot_id ?? null;
  acc.received_at = event.received_at;

  if (event.event_type === 'status_online' || event.event_type === 'status_offline') {
    acc.has_status = true;
    acc.connectivity = event.event_type === 'status_online' ? 'online' : 'offline';
    return;
  }

  if (event.event_type === 'telemetry') {
    acc.has_telemetry = true;
    acc.observed_at = event.observed_at ?? null;
    acc.clock_domain = event.quality.clock_domain;
    acc.quality_status = event.quality.status;
    acc.quality_reason = event.quality.reason ?? '';
    acc.units = { ...event.units };
    const derived = deriveValues(event.payload);
    acc.values = derived.values;
    acc.payload_state = derived.payload_state;
    acc.data_state = dataStateFor(event);
  }
}

/**
 * Project a fixture onto the consumer state.
 *
 * Purely functional — no I/O, no wall-clock reads, no randomness.
 */
export function projectFixture(fixture: Fixture, consumer: string): ProjectedState {
  // §3.1 — collect candidates: snapshot events first, then stream event frames.
  const candidates: CanonicalEvent[] = [
    ...fixture.snapshot.events,
    ...fixture.frames.filter((f) => f.frame_type === 'event').map((f) => f.event as CanonicalEvent),
  ];

  // §3.2 — deduplicate by event_id, first occurrence wins.
  const seen = new Set<string>();
  const droppedDuplicateEventIds: string[] = [];
  const unique: CanonicalEvent[] = [];
  for (const event of candidates) {
    if (seen.has(event.event_id)) {
      droppedDuplicateEventIds.push(event.event_id);
      continue;
    }
    seen.add(event.event_id);
    unique.push(event);
  }

  // §3.3 — order by sequence, stable.
  unique.sort((a, b) => a.sequence - b.sequence);

  // §3.4/§3.5 — project per device.
  const accumulators = new Map<string, Accumulator>();
  const appliedEventIds: string[] = [];
  let lastAppliedSequence: number | null = null;

  for (const event of unique) {
    let acc = accumulators.get(event.device_id);
    if (acc === undefined) {
      acc = newAccumulator(event.device_id);
      accumulators.set(event.device_id, acc);
    }
    applyEvent(acc, event);
    appliedEventIds.push(event.event_id);
    lastAppliedSequence = event.sequence;
  }

  // §3.6 — gap / resync.
  let gapDetected = false;
  let resyncRequired = fixture.snapshot.resync_required === true;
  for (const frame of fixture.frames) {
    if (frame.frame_type === 'gap') {
      gapDetected = true;
      resyncRequired = true;
    }
  }

  const devices: Record<string, ProjectedDeviceState> = {};
  for (const [deviceId, acc] of [...accumulators.entries()].sort((a, b) =>
    a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0,
  )) {
    devices[deviceId] = {
      device_id: acc.device_id,
      connectivity: acc.connectivity,
      data_state: acc.data_state,
      last_event_type: acc.last_event_type,
      last_sequence: acc.last_sequence,
      last_event_id: acc.last_event_id,
      boot_id: acc.boot_id,
      observed_at: acc.observed_at,
      received_at: acc.received_at,
      clock_domain: acc.clock_domain,
      quality_status: acc.quality_status,
      quality_reason: acc.quality_reason,
      units: acc.units,
      values: acc.values,
      payload_state: acc.payload_state,
    };
  }

  return {
    consumer,
    devices,
    last_applied_sequence: lastAppliedSequence,
    resync_required: resyncRequired,
    gap_detected: gapDetected,
    applied_event_ids: appliedEventIds,
    dropped_duplicate_event_ids: droppedDuplicateEventIds,
  };
}
