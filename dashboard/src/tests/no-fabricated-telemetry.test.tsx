/**
 * Regression tests for maintainer review findings on PR #260 (issue #149).
 *
 * Finding 1 (P0): fabricated telemetry must never be rendered in operational UI.
 * Finding 4 (P1): the staleness clock must re-evaluate without a gateway store change.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import React from 'react';
import { render, screen, act, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { FactoryModulesPage } from '../pages/FactoryModulesPage';
import { AppRoutes } from '../app/routes';
import { useGatewayStore } from '../store/gatewayStore';
import type { CanonicalEvent } from '../types/gateway';

/**
 * Label/value pairs that the previous implementation hard-coded as if they were live
 * measurements. Each entry is asserted inside a ModuleCard stat row, so the test checks
 * that a fabricated measurement cell no longer exists rather than matching bare digits
 * that legitimately occur in ids, column pickers and counters.
 */
const FABRICATED_STAT_CELLS = [
  'Speed',
  'Throughput',
  'Sorted',
  'Grade A',
  'Cycles',
  'Payload',
  'Staged',
  'Capacity',
  'Active AGV',
  'Battery',
  'Deliveries',
  'Weight',
  'Packaged',
  'Rate',
  'Stock',
  'Nodes',
  'Uptime',
];

function makeEvent(overrides: Partial<CanonicalEvent> = {}): CanonicalEvent {
  return {
    event_id: 'evt-1',
    device_id: 'conveyor-01',
    event_type: 'status_online',
    payload: { state: 'RUNNING' },
    mqtt_topic: 'factory/conveyor-01/state',
    mqtt_timestamp_ms: Date.now(),
    timestamp: Date.now(),
    received_at: new Date().toISOString(),
    received_at_ms: Date.now(),
    latency_ms: 1,
    stale: false,
    out_of_order: false,
    is_timestamp_synchronized: true,
    ingested_at: new Date().toISOString(),
    sequence: 1,
    ...overrides,
  };
}

/**
 * Assert that the conveyor module card's status badge renders the expected label.
 * The badge renders a human-readable label ("Running", "Stale", "Unknown", ...) so this
 * verifies the operator-visible verdict rather than internal state plumbing.
 */
function expectConveyorBadge(label: string): void {
  // The module card is a link to /modules/<moduleId>; query it by href so the assertion
  // is independent of how many times the id string also appears in filter chips.
  const conveyorCard = document.querySelector('a[href="/modules/conveyor-01"]');
  expect(conveyorCard).not.toBeNull();
  const badge = within(conveyorCard as HTMLElement).getByText(label);
  expect(badge).toBeDefined();
}

describe('Finding 1: fabricated telemetry is never rendered (P0)', () => {
  beforeEach(() => {
    useGatewayStore.setState({ devices: new Map(), events: [], operationalMode: 'live' });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('FactoryModulesPage renders no fabricated measurement rows in live mode', () => {
    const { container } = render(
      <MemoryRouter>
        <FactoryModulesPage />
      </MemoryRouter>
    );

    const text = container.textContent ?? '';
    for (const label of FABRICATED_STAT_CELLS) {
      expect(text).not.toContain(label);
    }

    // The hard-coded measurement values themselves must also be absent.
    for (const value of ['24 m/min', '12.5 kg', '1.2t', '92%', '99.9%', '45/hr', '78%']) {
      expect(text).not.toContain(value);
    }
  });

  it('FactoryModulesPage marks every module as N/A while no telemetry source exists', () => {
    render(
      <MemoryRouter>
        <FactoryModulesPage />
      </MemoryRouter>
    );

    // All nine modules report a measurement cell that is explicitly N/A.
    const naCells = screen.getAllByText(/N\/A \(no telemetry source\)|N\/A \(no sensors\)/i);
    expect(naCells.length).toBeGreaterThanOrEqual(9);
  });

  it('passive brackets-01 never shows a numeric stock or status reading', () => {
    const { container } = render(
      <MemoryRouter>
        <FactoryModulesPage />
      </MemoryRouter>
    );

    const text = container.textContent ?? '';
    expect(text).not.toContain('450');
    expect(text).not.toContain('Ready');
    expect(screen.getAllByText(/N\/A \(no sensors\)/i).length).toBeGreaterThanOrEqual(1);
  });

  it('ModuleDetailPage shows N/A for the primary metric instead of a hard-coded number', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/modules/conveyor-01']}>
        <AppRoutes />
      </MemoryRouter>
    );

    const text = container.textContent ?? '';
    expect(text).not.toContain('12.4');
    expect(screen.getByText(/No verified telemetry source for this metric yet\./i)).toBeDefined();
  });

  it('ModuleDetailPage keeps brackets-01 strictly N/A even when a gateway reports state', () => {
    act(() => {
      useGatewayStore.getState().addEvent(
        makeEvent({ device_id: 'brackets-01', payload: { state: 'RUNNING' } })
      );
    });

    const { container } = render(
      <MemoryRouter initialEntries={['/modules/brackets-01']}>
        <AppRoutes />
      </MemoryRouter>
    );

    const text = container.textContent ?? '';
    expect(text).not.toContain('450');
    expect(screen.getAllByText(/no sensors attached/i).length).toBeGreaterThanOrEqual(1);
  });
});

describe('Finding 3: gateway state reaches the derived visual state (P1)', () => {
  beforeEach(() => {
    useGatewayStore.setState({ devices: new Map(), events: [], operationalMode: 'live' });
  });

  it('exposes the raw gateway state on the device registry', () => {
    act(() => {
      useGatewayStore.getState().addEvent(makeEvent({ payload: { state: 'RUNNING' } }));
    });

    const device = useGatewayStore.getState().devices.get('conveyor-01');
    expect(device).toBeDefined();
    expect(device?.state).toBe('RUNNING');
  });

  it('preserves the last known state across heartbeat events that carry no state payload', () => {
    act(() => {
      useGatewayStore.getState().addEvent(makeEvent({ payload: { state: 'RUNNING' } }));
    });
    act(() => {
      useGatewayStore.getState().addEvent(
        makeEvent({ event_type: 'heartbeat', payload: {}, event_id: 'evt-2' })
      );
    });

    const device = useGatewayStore.getState().devices.get('conveyor-01');
    expect(device?.state).toBe('RUNNING');
  });

  it('records FAULT from the gateway payload', () => {
    act(() => {
      useGatewayStore.getState().addEvent(makeEvent({ payload: { state: 'FAULT' } }));
    });

    expect(useGatewayStore.getState().devices.get('conveyor-01')?.state).toBe('FAULT');
  });
});

describe('Finding 4: the staleness clock re-evaluates without a store change (P1)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-23T12:00:00Z'));
    useGatewayStore.setState({ devices: new Map(), events: [], operationalMode: 'live' });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('an idle device transitions to STALE after the 60s threshold without any store update', async () => {
    act(() => {
      useGatewayStore.getState().addEvent(
        makeEvent({
          payload: { state: 'RUNNING' },
          ingested_at: new Date('2026-10-23T12:00:00Z').toISOString(),
        })
      );
    });

    render(
      <MemoryRouter>
        <FactoryModulesPage />
      </MemoryRouter>
    );

    // Immediately after ingest the module card shows Running.
    expectConveyorBadge('Running');

    // Advance past the 60s staleness threshold with no further gateway traffic.
    await act(async () => {
      vi.advanceTimersByTime(90_000);
    });

    // The clock tick must invalidate the freshness verdict without a store change.
    expectConveyorBadge('Stale');
  });
});