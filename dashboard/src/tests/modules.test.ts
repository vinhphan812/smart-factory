import { describe, it, expect } from 'vitest';
import {
  MODULE_DEFINITIONS,
  MODULE_TYPES,
  STALE_THRESHOLD_MS,
  deriveModuleState,
  findModule,
  allDeviceIds,
} from '../contracts/modules';

describe('nine-module registry (TC-1 & TC-2)', () => {
  it('contains exactly nine canonical modules (TC-1)', () => {
    expect(MODULE_DEFINITIONS).toHaveLength(9);
    const ids = MODULE_DEFINITIONS.map((m) => m.moduleId);
    expect(new Set(ids).size).toBe(9);
  });

  it('verifies each module ID appears exactly once with no duplicates (TC-1)', () => {
    const seen = new Set<string>();
    for (const mod of MODULE_DEFINITIONS) {
      expect(seen.has(mod.moduleId)).toBe(false);
      seen.add(mod.moduleId);
    }
    expect(seen.size).toBe(9);
  });

  it('returns null for unknown module ID (TC-1)', () => {
    expect(findModule('unknown-device')).toBeNull();
    expect(findModule('')).toBeNull();
    expect(findModule(undefined)).toBeNull();
    expect(deriveModuleState(null, [])).toBeNull();
  });

  it('reports OFFLINE when the gateway explicitly reports the device offline', () => {
    const conveyor = MODULE_DEFINITIONS.find((m) => m.moduleId === 'conveyor-01')!;
    const now = Date.now();
    const freshTime = new Date(now - 1000).toISOString();

    const offlineState = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'offline', last_heartbeat_at: freshTime }],
      { now, provenance: 'live' }
    );
    expect(offlineState?.visualState).toBe('OFFLINE');
  });

  it('never reports RUNNING for brackets-01 (TC-2)', () => {
    const bracket = MODULE_DEFINITIONS.find((m) => m.moduleId === 'brackets-01')!;
    expect(bracket).toBeDefined();
    expect(bracket.hasTelemetry).toBe(false);

    const state = deriveModuleState(
      bracket,
      [{ device_id: 'brackets-01', status: 'online', state: 'RUNNING', last_heartbeat_at: new Date().toISOString() }],
      Date.now()
    );
    expect(state).not.toBeNull();
    expect(state!.visualState).not.toBe('RUNNING');
    expect(state!.visualState).toBe('UNKNOWN');
  });

  it('never reports RUNNING when the heartbeat is stale (TC-2)', () => {
    const conveyor = MODULE_DEFINITIONS.find((m) => m.moduleId === 'conveyor-01')!;
    const now = Date.now();
    const staleTime = new Date(now - STALE_THRESHOLD_MS - 5000).toISOString();

    const state = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'RUNNING', last_heartbeat_at: staleTime }],
      now
    );
    expect(state).not.toBeNull();
    expect(state!.visualState).toBe('STALE');
    expect(state!.visualState).not.toBe('RUNNING');
  });

  it('derives RUNNING and FAULT from a real gateway-reported state (review finding 3)', () => {
    const conveyor = MODULE_DEFINITIONS.find((m) => m.moduleId === 'conveyor-01')!;
    const now = Date.now();
    const freshTime = new Date(now - 1000).toISOString();

    const runningState = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'RUNNING', last_heartbeat_at: freshTime }],
      { now, provenance: 'live' }
    );
    expect(runningState?.visualState).toBe('RUNNING');
    expect(runningState?.rawState).toBe('RUNNING');

    const faultState = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'FAULT', last_heartbeat_at: freshTime }],
      { now, provenance: 'live' }
    );
    expect(faultState?.visualState).toBe('FAULT');

    const estopState = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'E_STOP', last_heartbeat_at: freshTime }],
      { now, provenance: 'live' }
    );
    expect(estopState?.visualState).toBe('FAULT');
  });

  it('fails closed to UNKNOWN for live data without a parsable heartbeat (review finding 2)', () => {
    const conveyor = MODULE_DEFINITIONS.find((m) => m.moduleId === 'conveyor-01')!;
    const now = Date.now();

    // No timestamp at all
    const noTimestamp = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'RUNNING' }],
      { now, provenance: 'live' }
    );
    expect(noTimestamp?.visualState).toBe('UNKNOWN');
    expect(noTimestamp?.visualState).not.toBe('SIMULATED');

    // Unparsable timestamp
    const badTimestamp = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'RUNNING', last_heartbeat_at: 'not-a-timestamp' }],
      { now, provenance: 'live' }
    );
    expect(badTimestamp?.visualState).toBe('UNKNOWN');

    // Empty timestamp string
    const emptyTimestamp = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'RUNNING', last_heartbeat_at: '' }],
      { now, provenance: 'live' }
    );
    expect(emptyTimestamp?.visualState).toBe('UNKNOWN');
  });

  it('rejects future timestamps beyond the tolerated clock skew (review finding 2)', () => {
    const conveyor = MODULE_DEFINITIONS.find((m) => m.moduleId === 'conveyor-01')!;
    const now = Date.now();

    // Far future -> rejected
    const farFuture = new Date(now + 60 * 60 * 1000).toISOString();
    const rejected = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'RUNNING', last_heartbeat_at: farFuture }],
      { now, provenance: 'live' }
    );
    expect(rejected?.visualState).toBe('UNKNOWN');

    // Small skew within tolerance -> accepted
    const smallSkew = new Date(now + 1000).toISOString();
    const accepted = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'RUNNING', last_heartbeat_at: smallSkew }],
      { now, provenance: 'live' }
    );
    expect(accepted?.visualState).toBe('RUNNING');
  });

  it('only reports SIMULATED when provenance or the gateway state says so (review finding 2)', () => {
    const conveyor = MODULE_DEFINITIONS.find((m) => m.moduleId === 'conveyor-01')!;
    const now = Date.now();
    const freshTime = new Date(now - 1000).toISOString();

    // Live provenance with an unclassified state must NOT become SIMULATED
    const liveIdle = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'IDLE', last_heartbeat_at: freshTime }],
      { now, provenance: 'live' }
    );
    expect(liveIdle?.visualState).toBe('UNKNOWN');

    // No provenance at all also fails closed
    const noProvenance = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'IDLE', last_heartbeat_at: freshTime }],
      { now }
    );
    expect(noProvenance?.visualState).toBe('UNKNOWN');

    // Explicit simulated provenance -> SIMULATED
    const simulated = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'IDLE', last_heartbeat_at: freshTime }],
      { now, provenance: 'simulated' }
    );
    expect(simulated?.visualState).toBe('SIMULATED');
    expect(simulated?.provenance).toBe('simulated');

    // Gateway explicitly flags the state as simulated
    const gatewayFlagged = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'SIMULATED', last_heartbeat_at: freshTime }],
      { now, provenance: 'live' }
    );
    expect(gatewayFlagged?.visualState).toBe('SIMULATED');
    expect(gatewayFlagged?.provenance).toBe('simulated');
  });

  it('contains expected module types and device IDs', () => {
    expect(MODULE_TYPES).toHaveLength(9);
    expect(allDeviceIds).toContain('conveyor-01');
    expect(allDeviceIds).toContain('combine-01');
    expect(STALE_THRESHOLD_MS).toBe(60000);
  });
});
