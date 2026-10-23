/**
 * Responsive & Accessibility UX Tests (SPEC-2, TC-1, TC-2, TC-4)
 */

import { describe, it, expect, afterEach } from 'vitest';
import React from 'react';
import { render, screen, within, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from '../layout/Sidebar';
import { AppRoutes } from '../app/routes';
import { FactoryModulesPage } from '../pages/FactoryModulesPage';
import { useGatewayStore } from '../store/gatewayStore';

describe('Accessibility & Responsive UX Contracts (TC-1, TC-2, TC-4)', () => {
  afterEach(() => {
    act(() => {
      useGatewayStore.getState().setOperationalMode('demo');
    });
  });
  it('renders main navigation landmark and all 10 SPEC-2 destinations in Sidebar', () => {
    render(
      <MemoryRouter>
        <Sidebar collapsed={false} />
      </MemoryRouter>
    );

    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    expect(nav).toBeDefined();

    const links = [
      'Overview',
      'Factory Modules',
      'Production',
      'Telemetry',
      'Events',
      'Incidents',
      'Commands',
      'Devices',
      'System Health',
      'Reports',
      'Settings',
    ];
    for (const text of links) {
      expect(within(nav).getByText(text)).toBeDefined();
    }
  });

  it('renders unknown module error boundary visibly (TC-1)', () => {
    render(
      <MemoryRouter initialEntries={['/modules/non-existent-device']}>
        <AppRoutes />
      </MemoryRouter>
    );
    expect(screen.getByText(/unknown module/i)).toBeDefined();
    expect(screen.getByText(/non-existent-device/i)).toBeDefined();
  });

  it('renders N/A for passive structural Brackets module (TC-2)', () => {
    render(
      <MemoryRouter initialEntries={['/modules/brackets-01']}>
        <AppRoutes />
      </MemoryRouter>
    );
    expect(screen.getByText(/passive structural component/i)).toBeDefined();
    const sensorNotices = screen.getAllByText(/no sensors attached/i);
    expect(sensorNotices.length).toBeGreaterThan(0);
    expect(screen.getByText('N/A (Structural)')).toBeDefined();
  });

  it('renders gated safety notice for Commands route (TC-4)', () => {
    render(
      <MemoryRouter initialEntries={['/commands']}>
        <AppRoutes />
      </MemoryRouter>
    );
    expect(screen.getByText(/module commands & actuation/i)).toBeDefined();
    expect(
      screen.getByText(/browser operator dashboard is strictly read-only and has no actuation endpoints/i)
    ).toBeDefined();
    const safetyGateMentions = screen.getAllByText(/backend safety gates/i);
    expect(safetyGateMentions.length).toBeGreaterThan(0);
  });

  it('switches gateway live/offline mode transition (Finding 4)', () => {
    act(() => {
      useGatewayStore.getState().setOperationalMode('demo');
    });

    render(
      <MemoryRouter>
        <FactoryModulesPage />
      </MemoryRouter>
    );

    expect(screen.getByText('OFFLINE SIMULATION / DEMO (L0/L2 Mock)')).toBeDefined();

    act(() => {
      useGatewayStore.getState().setOperationalMode('live');
    });

    expect(screen.getByText('LIVE GATEWAY (L2 Telemetry)')).toBeDefined();

    act(() => {
      useGatewayStore.getState().setOperationalMode('demo');
    });

    expect(screen.getByText('OFFLINE SIMULATION / DEMO (L0/L2 Mock)')).toBeDefined();
  });

  it('verifies reserved /commands route non-actuation and TC-4 safety policy (Finding 4)', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/commands']}>
        <AppRoutes />
      </MemoryRouter>
    );

    // Assert that there are no buttons or submit elements that can actuate hardware
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    const actionableElements = container.querySelectorAll(
      'button, input[type="submit"], input[type="button"], form'
    );
    expect(actionableElements.length).toBe(0);

    // Assert that the TC-4 safety policy notice is present and mentions that the browser operator dashboard is strictly read-only
    expect(screen.getByText(/Safety Policy \(TC-4\):/i)).toBeDefined();
    expect(
      screen.getByText(/browser operator dashboard is strictly read-only/i)
    ).toBeDefined();
  });
});
