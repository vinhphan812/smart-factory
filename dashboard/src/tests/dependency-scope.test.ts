/**
 * Dependency scope analysis — unit tests.
 *
 * These cover the resolution rules that the release evidence depends on:
 * install-path reconstruction, runtime vs development/build classification,
 * and the runtime-reachability verdict that the advisory disposition reports.
 *
 * The release-evidence generator derives the runtime SBOM from the full SBOM
 * rather than trusting `npm sbom --omit=dev` (which silently omits packages
 * that `npm ci --omit=dev` really installs). The derivation rules are
 * exercised here so that regression is caught by the test suite rather than
 * by a reviewer.
 */

import { describe, expect, it } from 'vitest';

import {
  analyseAdvisories,
  classifyScope,
  findInstallPaths,
  indexLockfile,
  lockfileProductionClosure,
  resolveFrom,
} from '../../scripts/dependency-scope.mjs';
import {
  buildSeparation,
  deriveRuntimeSbom,
} from '../../scripts/release-evidence.mjs';
import type {
  SbomDocument,
  SeparationResult,
} from '../../scripts/release-evidence.mjs';

/**
 * A minimal lockfile v3 fixture:
 *
 *   runtime deps:  react, react-dom  -> react-dom -> scheduler
 *   dev deps:      vitest -> tinypool -> esbuild
 */
const LOCKFILE = {
  name: 'fixture',
  lockfileVersion: 3,
  packages: {
    '': {
      name: 'fixture',
      version: '1.0.0',
      dependencies: { react: '^18.3.1', 'react-dom': '^18.3.1' },
      devDependencies: { vitest: '^4.0.0' },
    },
    'node_modules/react': { version: '18.3.1' },
    'node_modules/react-dom': {
      version: '18.3.1',
      dependencies: { react: '^18.3.1', scheduler: '^0.23.2' },
    },
    'node_modules/scheduler': { version: '0.23.2' },
    'node_modules/vitest': { version: '4.1.12', dev: true, dependencies: { tinypool: '^2.1.1' } },
    'node_modules/tinypool': { version: '2.1.1', dev: true, dependencies: { esbuild: '^0.25.0' } },
    'node_modules/esbuild': { version: '0.25.0', dev: true },
  },
};

const INDEX = indexLockfile(LOCKFILE);

describe('resolveFrom', () => {
  it('resolves a root-level dependency from the project root', () => {
    expect(resolveFrom(INDEX, '', 'react')).toBe('node_modules/react');
  });

  it('resolves a nested dependency from its parent scope', () => {
    expect(resolveFrom(INDEX, 'node_modules/vitest', 'tinypool')).toBe('node_modules/tinypool');
  });

  it('returns null for a dependency that is not installed', () => {
    expect(resolveFrom(INDEX, '', 'not-installed')).toBeNull();
  });
});

describe('findInstallPaths', () => {
  it('reconstructs the runtime path to a runtime package', () => {
    const paths = findInstallPaths(LOCKFILE, INDEX, 'node_modules/scheduler');
    expect(paths).toHaveLength(1);
    expect(paths[0].chain).toEqual(['react-dom', 'scheduler']);
    expect(paths[0].isDev).toBe(false);
  });

  it('reconstructs a direct runtime dependency path', () => {
    const paths = findInstallPaths(LOCKFILE, INDEX, 'node_modules/react-dom');
    expect(paths).toHaveLength(1);
    expect(paths[0].chain).toEqual(['react-dom']);
    expect(paths[0].isDev).toBe(false);
  });

  it('reconstructs the development/build path to a dev-chain package', () => {
    const paths = findInstallPaths(LOCKFILE, INDEX, 'node_modules/esbuild');
    expect(paths).toHaveLength(1);
    expect(paths[0].chain).toEqual(['vitest', 'tinypool', 'esbuild']);
    expect(paths[0].isDev).toBe(true);
  });

  it('returns no path for a package that is not reachable', () => {
    expect(findInstallPaths(LOCKFILE, INDEX, 'node_modules/ghost')).toEqual([]);
  });
});

describe('classifyScope', () => {
  it('classifies a runtime-reachable package as runtime scope', () => {
    const detail = classifyScope(LOCKFILE, INDEX, 'node_modules/scheduler');
    expect(detail.scope).toBe('runtime');
    expect(detail.dev).toHaveLength(0);
  });

  it('classifies a dev-chain-only package as development/build scope', () => {
    const detail = classifyScope(LOCKFILE, INDEX, 'node_modules/tinypool');
    expect(detail.scope).toBe('development/build');
    expect(detail.runtime).toHaveLength(0);
  });
});

describe('analyseAdvisories', () => {
  const audit = {
    metadata: { npm_version: '10.0.0', vulnerabilities: { total: 2, critical: 1, high: 1 } },
    vulnerabilities: {
      tinypool: {
        name: 'tinypool',
        severity: 'critical',
        isDirect: false,
        range: '<=2.1.1',
        via: [{ title: 'Prototype pollution', severity: 'critical', range: '<=2.1.1', url: 'https://example.invalid' }],
      },
      react: {
        name: 'react',
        severity: 'high',
        isDirect: true,
        range: '<18.3.2',
        via: [{ title: 'Open redirect', severity: 'high', range: '<18.3.2', url: 'https://example.invalid' }],
      },
    },
  };

  it('marks a dev-chain advisory as not runtime reachable', () => {
    const report = analyseAdvisories(audit, LOCKFILE, new Set(['react', 'react-dom', 'scheduler']));
    const tinypool = report.advisories.find((a) => a.package === 'tinypool');
    expect(tinypool).toBeDefined();
    expect(tinypool?.runtimeReachable).toBe(false);
    expect(tinypool?.developmentOnly).toBe(true);
    expect(tinypool?.pathScope).toBe('development/build');
    expect(tinypool?.installed[0]?.developmentPaths[0]).toEqual(['vitest', 'tinypool']);
  });

  it('marks a runtime advisory as runtime reachable', () => {
    const report = analyseAdvisories(audit, LOCKFILE, new Set(['react', 'react-dom', 'scheduler']));
    const react = report.advisories.find((a) => a.package === 'react');
    expect(react).toBeDefined();
    expect(react?.runtimeReachable).toBe(true);
    expect(react?.inProductionClosure).toBe(true);
  });

  it('sorts advisories by severity, most severe first', () => {
    const report = analyseAdvisories(audit, LOCKFILE, new Set(['react']));
    expect(report.advisories.map((a) => a.severity)).toEqual(['critical', 'high']);
  });

  it('reports an empty advisory list for a clean audit', () => {
    const report = analyseAdvisories(
      { metadata: { vulnerabilities: { total: 0 } }, vulnerabilities: {} },
      LOCKFILE,
      new Set(['react']),
    );
    expect(report.advisories).toEqual([]);
    expect(report.totals?.total).toBe(0);
  });
});

describe('lockfileProductionClosure', () => {
  it('includes runtime packages and excludes dev-only packages', () => {
    const closure = lockfileProductionClosure(LOCKFILE);
    expect([...closure.keys()].sort()).toEqual([
      'react',
      'react-dom',
      'scheduler',
    ]);
  });

  it('records the resolved version of each production package', () => {
    const closure = lockfileProductionClosure(LOCKFILE);
    expect(closure.get('react')).toBe('18.3.1');
    expect(closure.get('scheduler')).toBe('0.23.2');
  });

  it('excludes the root project entry', () => {
    const closure = lockfileProductionClosure(LOCKFILE);
    expect(closure.has('fixture')).toBe(false);
  });
});

describe('deriveRuntimeSbom', () => {
  const FULL_SBOM: SbomDocument = {
    metadata: { component: { 'bom-ref': 'pkg:dashboard/fixture@0.0.0' } },
    components: [
      { name: 'react', version: '18.3.1', 'bom-ref': 'pkg:npm/react@18.3.1' },
      { name: 'react-dom', version: '18.3.1', 'bom-ref': 'pkg:npm/react-dom@18.3.1' },
      { name: 'vite', version: '5.4.0', 'bom-ref': 'pkg:npm/vite@5.4.0' },
      { name: 'vite', version: '6.4.5', 'bom-ref': 'pkg:npm/vite@6.4.5' },
    ],
    dependencies: [
      {
        ref: 'pkg:dashboard/fixture@0.0.0',
        dependsOn: ['pkg:npm/react@18.3.1', 'pkg:npm/vite@6.4.5'],
      },
      { ref: 'pkg:npm/react@18.3.1', dependsOn: [] },
      { ref: 'pkg:npm/vite@6.4.5', dependsOn: [] },
      { ref: 'pkg:npm/vite@5.4.0', dependsOn: [] },
    ],
  };

  const CLOSURE = new Map([
    ['react', '18.3.1'],
    ['react-dom', '18.3.1'],
  ]);

  it('keeps only the components in the production closure', () => {
    const runtime = deriveRuntimeSbom(FULL_SBOM, CLOSURE) as SbomDocument;
    expect(runtime.components.map((c) => c.name).sort()).toEqual(['react', 'react-dom']);
  });

  it('matches on version as well as name', () => {
    // `vite` appears twice; the closure pins 6.4.5, so 5.4.0 must not leak in.
    const closure = new Map([...CLOSURE, ['vite', '6.4.5']]);
    const runtime = deriveRuntimeSbom(FULL_SBOM, closure) as SbomDocument;
    const vite = runtime.components.filter((c) => c.name === 'vite');
    expect(vite).toHaveLength(1);
    expect(vite[0].version).toBe('6.4.5');
  });

  it('prunes dependency edges so every dependsOn target is present', () => {
    const runtime = deriveRuntimeSbom(FULL_SBOM, CLOSURE) as SbomDocument;
    const present = new Set(runtime.components.map((c) => c['bom-ref']));
    for (const entry of runtime.dependencies) {
      for (const target of entry.dependsOn ?? []) {
        expect(present.has(target)).toBe(true);
      }
    }
  });

  it('retains the root component entry', () => {
    const runtime = deriveRuntimeSbom(FULL_SBOM, CLOSURE) as SbomDocument;
    const refs = runtime.dependencies.map((d) => d.ref);
    expect(refs).toContain('pkg:dashboard/fixture@0.0.0');
  });

  it('records the runtime scope as an SBOM property', () => {
    const runtime = deriveRuntimeSbom(FULL_SBOM, CLOSURE) as SbomDocument;
    const props = runtime.metadata.properties ?? [];
    expect(props.some((p) => p.name === 'sbom:scope')).toBe(true);
  });
});

describe('buildSeparation', () => {
  const FULL_SBOM: SbomDocument = {
    metadata: { component: { 'bom-ref': 'pkg:dashboard/fixture@0.0.0' } },
    components: [
      { name: 'react', version: '18.3.1' },
      { name: 'react-dom', version: '18.3.1' },
      { name: 'vite', version: '5.4.0' },
      { name: 'vite', version: '6.4.5' },
    ],
    dependencies: [],
  };

  it('separates runtime from development/build components', () => {
    const separation = buildSeparation(
      FULL_SBOM,
      new Map([
        ['react', '18.3.1'],
        ['react-dom', '18.3.1'],
      ]),
    ) as SeparationResult;
    expect(separation.runtimeComponentCount).toBe(2);
    expect(separation.developmentBuildComponentCount).toBe(2);
    expect(separation.totalComponentCount).toBe(4);
  });

  it('reports a consistent cross-check when classification matches the closure', () => {
    const separation = buildSeparation(
      FULL_SBOM,
      new Map([
        ['react', '18.3.1'],
        ['react-dom', '18.3.1'],
      ]),
    ) as SeparationResult;
    expect(separation.productionClosureCrossCheck.consistent).toBe(true);
    expect(separation.productionClosureCrossCheck.mismatches).toEqual([]);
  });

  it('flags a mismatch when a closure package is classified as development', () => {
    const separation = buildSeparation(
      FULL_SBOM,
      new Map([
        ['react', '18.3.1'],
        ['react-dom', '18.3.1'],
        ['vite', '6.4.5'],
      ]),
    ) as SeparationResult;
    expect(separation.productionClosureCrossCheck.consistent).toBe(false);
    expect(separation.productionClosureCrossCheck.mismatches.length).toBeGreaterThan(0);
  });
});
