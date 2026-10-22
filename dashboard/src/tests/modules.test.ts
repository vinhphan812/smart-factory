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

  it('correctly transitions between offline, fault, running, and simulated states', () => {
    const conveyor = MODULE_DEFINITIONS.find((m) => m.moduleId === 'conveyor-01')!;
    const now = Date.now();
    const freshTime = new Date(now - 1000).toISOString();

    // Offline status
    const offlineState = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'offline', last_heartbeat_at: freshTime }],
      now
    );
    expect(offlineState?.visualState).toBe('OFFLINE');

    // Fault state
    const faultState = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'FAULT', last_heartbeat_at: freshTime }],
      now
    );
    expect(faultState?.visualState).toBe('FAULT');

    // Running state
    const runningState = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'RUNNING', last_heartbeat_at: freshTime }],
      now
    );
    expect(runningState?.visualState).toBe('RUNNING');

    // Simulated state
    const simState = deriveModuleState(
      conveyor,
      [{ device_id: 'conveyor-01', status: 'online', state: 'IDLE', last_heartbeat_at: freshTime }],
      now
    );
    expect(simState?.visualState).toBe('SIMULATED');
  });

  it('contains expected module types and device IDs', () => {
    expect(MODULE_TYPES).toHaveLength(9);
    expect(allDeviceIds).toContain('conveyor-01');
    expect(allDeviceIds).toContain('combine-01');
    expect(STALE_THRESHOLD_MS).toBe(60000);
  });
});
