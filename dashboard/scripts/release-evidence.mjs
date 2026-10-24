#!/usr/bin/env node
/**
 * scripts/release-evidence.mjs
 *
 * Produces the release evidence bundle for the Smart Factory Operator Dashboard:
 *
 *   1. `dependency-scope.json` — machine-readable advisory disposition. For
 *      every advisory: severity, the concrete install path(s) from a declared
 *      dependency down to the vulnerable package, the scope of that path
 *      (runtime vs development/build), whether the package is in the
 *      production dependency closure, and the available fix.
 *   2. `dependency-scope.md` — the same disposition as a reviewable table.
 *   3. `sbom.runtime.cdx.json` — CycloneDX SBOM of the **production closure
 *      only** (what `npm ci --omit=dev` installs, i.e. what can ship).
 *   4. `sbom.development.cdx.json` — CycloneDX SBOM of the **development/build
 *      toolchain only**: the exact complement of the production closure within
 *      the installed tree. Together with the runtime SBOM it partitions the
 *      full tree, so neither document can silently over- or under-report.
 *   5. `sbom.full.cdx.json` — CycloneDX SBOM of the **full installed tree**
 *      (runtime + development/build toolchain).
 *   6. `sbom-separation.json` — the separation manifest: every component
 *      classified as runtime or development/build, the counts on both sides,
 *      and the SHA-256 of each SBOM so the set is tamper-evident.
 *
 * The release SBOM is therefore *separated* from the development toolchain
 * SBOM: a release reviewer can state exactly which third-party code is in the
 * shipped bundle, and the build/test toolchain is visibly excluded rather
 * than silently mixed in.
 *
 * The scope classification is cross-checked three ways and the agreement is
 * reported in `sbom-separation.json`:
 *
 *   - the lockfile `dev` flag,
 *   - the resolved install path from the committed lockfile, and
 *   - `npm ls --omit=dev --all` (the authoritative production closure).
 *
 * Usage:
 *   node scripts/release-evidence.mjs [--out-dir <dir>] [--no-sbom] [--quiet]
 *
 * By default the evidence is written to `dashboard/release-evidence/`, which is
 * git-ignored: the artefacts are regenerated release material, not source.
 *
 * Exit codes:
 *   0  evidence produced
 *   1  evidence could not be produced
 */

import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  analyseAdvisories,
  formatSummary,
  lockfileProductionClosure,
  productionClosure,
  runNpm,
} from './dependency-scope.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DASHBOARD_ROOT = path.resolve(HERE, '..');
const DEFAULT_OUT_DIR = path.join(DASHBOARD_ROOT, 'release-evidence');

// ---------------------------------------------------------------------------
// Argument parsing
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const options = { outDir: DEFAULT_OUT_DIR, sbom: true, quiet: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--out-dir') {
      options.outDir = path.resolve(argv[++i]);
    } else if (arg === '--no-sbom') {
      options.sbom = false;
    } else if (arg === '--quiet') {
      options.quiet = true;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return options;
}

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

/**
 * Read the advisory report for the *current* lockfile.
 *
 * A previously captured `npm-audit.json` is only reusable when it was written
 * after the lockfile it describes. A stale capture would silently misreport
 * the advisory state, so freshness is verified against the lockfile's
 * modification time before the file is trusted. Otherwise npm is invoked
 * directly to produce a fresh report.
 *
 * @param {string} cwd
 * @returns {{audit: object|null, source: string}}
 */
function readAudit(cwd) {
  const captured = path.join(cwd, 'npm-audit.json');
  const lockfile = path.join(cwd, 'package-lock.json');

  if (existsSync(captured)) {
    try {
      const capturedStat = statSync(captured);
      const lockStat = statSync(lockfile);
      // One second of tolerance absorbs coarse filesystem timestamps.
      if (capturedStat.mtimeMs >= lockStat.mtimeMs - 1000) {
        const parsed = JSON.parse(readFileSync(captured, 'utf8'));
        if (parsed && typeof parsed === 'object') {
          return { audit: parsed, source: 'npm-audit.json (fresh: captured after the lockfile)' };
        }
      }
    } catch {
      // Fall through to a direct npm invocation.
    }
  }

  try {
    const stdout = runNpm(['audit', '--json']);
    return { audit: JSON.parse(stdout), source: 'npm audit --json (fresh)' };
  } catch {
    return { audit: null, source: 'unavailable' };
  }
}

/**
 * Generate the CycloneDX SBOM for the complete installed tree.
 *
 * Only the *full* SBOM is generated. `npm sbom --omit=dev` is deliberately not
 * used to define the runtime set: on npm 10.x and 12.x it silently omits
 * packages that `npm ci --omit=dev` really installs (verified against a
 * physical production-only install), which would publish an understated
 * release SBOM. The runtime SBOM is instead derived from the full SBOM by
 * filtering on the independently verified production closure.
 *
 * @returns {{sbom: object|null, error: string|null}}
 */
function generateFullSbom() {
  try {
    const stdout = runNpm(['sbom', '--sbom-format=cyclonedx']);
    return { sbom: JSON.parse(stdout), error: null };
  } catch (err) {
    return { sbom: null, error: err?.message ?? String(err) };
  }
}

// ---------------------------------------------------------------------------
// SBOM separation
// ---------------------------------------------------------------------------

/**
 * Stable identity for an SBOM component.
 *
 * @param {object} component
 * @returns {string}
 */
function componentKey(component) {
  return `${component.group ? `${component.group}/` : ''}${component.name}@${component.version}`;
}

/**
 * Derive the runtime (production closure) SBOM from the full SBOM.
 *
 * The runtime SBOM is the full SBOM restricted to the packages in the
 * verified production closure. The CycloneDX `dependencies` graph is pruned
 * to match, so the emitted document is internally consistent: every
 * `dependsOn` edge points at a component that is present in the document.
 *
 * Components are matched on name *and* version. A single package name can
 * appear more than once in the tree at different versions (for example
 * `lru-cache@10.4.3` and `lru-cache@5.1.1`), and matching on name alone
 * would let the version that is not actually installed in production leak
 * into the release SBOM.
 *
 * @param {object} fullSbom The complete installed-tree SBOM
 * @param {Map<string, string>} closureVersions Production closure name -> version
 * @returns {object} A CycloneDX SBOM document restricted to the closure
 */
export function deriveRuntimeSbom(fullSbom, closureVersions) {
  const components = (fullSbom.components ?? []).filter((c) => {
    const expected = closureVersions.get(c.name);
    return expected !== undefined && expected === c.version;
  });
  const present = new Set(components.map((c) => c['bom-ref'] ?? componentKey(c)));

  const dependencies = (fullSbom.dependencies ?? [])
    .filter((entry) => {
      // The root entry is always retained; it documents the project itself.
      if (entry.ref === fullSbom.metadata?.component?.['bom-ref']) return true;
      return present.has(entry.ref);
    })
    .map((entry) => ({
      ref: entry.ref,
      dependsOn: (entry.dependsOn ?? []).filter((ref) => present.has(ref)),
    }));

  return {
    ...fullSbom,
    metadata: {
      ...fullSbom.metadata,
      properties: [
        ...(fullSbom.metadata?.properties ?? []),
        { name: 'sbom:scope', value: 'runtime production closure' },
      ],
    },
    components,
    dependencies,
  };
}

/**
 * Derive the development/build toolchain SBOM from the full SBOM.
 *
 * This is the exact complement of {@link deriveRuntimeSbom} within the full
 * installed tree: every component that is *not* part of the verified
 * production closure. Components are matched on name *and* version, using the
 * same rule as the runtime derivation, so the runtime and development
 * documents partition the full tree without overlap and without gaps.
 *
 * The CycloneDX `dependencies` graph is pruned to match, so the emitted
 * document is internally consistent: every `dependsOn` edge points at a
 * component that is present in the document.
 *
 * @param {object} fullSbom The complete installed-tree SBOM
 * @param {Map<string, string>} closureVersions Production closure name -> version
 * @returns {object} A CycloneDX SBOM document restricted to the toolchain
 */
export function deriveDevelopmentSbom(fullSbom, closureVersions) {
  const components = (fullSbom.components ?? []).filter((c) => {
    const expected = closureVersions.get(c.name);
    // A component is development/build when it is NOT the exact
    // name@version pair that the production closure pins. A package that
    // appears in the closure at a different version (for example
    // `lru-cache@5.1.1` against a closure of `lru-cache@10.4.3`) is
    // development-only, exactly as `buildSeparation` classifies it.
    return expected !== c.version;
  });
  const present = new Set(components.map((c) => c['bom-ref'] ?? componentKey(c)));

  const dependencies = (fullSbom.dependencies ?? [])
    .filter((entry) => {
      // The root entry is always retained; it documents the project itself.
      if (entry.ref === fullSbom.metadata?.component?.['bom-ref']) return true;
      return present.has(entry.ref);
    })
    .map((entry) => ({
      ref: entry.ref,
      dependsOn: (entry.dependsOn ?? []).filter((ref) => present.has(ref)),
    }));

  return {
    ...fullSbom,
    metadata: {
      ...fullSbom.metadata,
      properties: [
        ...(fullSbom.metadata?.properties ?? []),
        { name: 'sbom:scope', value: 'development and build toolchain' },
      ],
    },
    components,
    dependencies,
  };
}

/**
 * Classify every component of the full SBOM as runtime or development/build,
 * and cross-check the classification against the production closure.
 *
 * Classification is by name *and* version, matching the rule used to derive
 * the runtime SBOM.
 *
 * @param {object|null} fullSbom
 * @param {Map<string, string>|null} closureVersions
 * @returns {object}
 */
export function buildSeparation(fullSbom, closureVersions) {
  const fullComponents = fullSbom?.components ?? [];
  const isRuntime = (c) =>
    closureVersions !== null && closureVersions.get(c.name) === c.version;

  const runtime = closureVersions
    ? fullComponents.filter(isRuntime)
    : [];
  const devOnly = closureVersions
    ? fullComponents.filter((c) => !isRuntime(c))
    : [...fullComponents];

  // Cross-check: every runtime component must be inside the production
  // closure reported by `npm ls --omit=dev --all`, and vice versa.
  const closureMismatches = [];
  if (closureVersions) {
    for (const component of runtime) {
      if (!closureVersions.has(component.name)) {
        closureMismatches.push({
          component: componentKey(component),
          issue: 'present in runtime SBOM but absent from the production closure',
        });
      }
    }
    for (const component of devOnly) {
      if (closureVersions.has(component.name)) {
        closureMismatches.push({
          component: componentKey(component),
          issue: 'present in the production closure but classified as development/build',
        });
      }
    }
  }

  return {
    runtimeComponentCount: runtime.length,
    developmentBuildComponentCount: devOnly.length,
    totalComponentCount: fullComponents.length,
    runtimeComponents: runtime.map(componentKey).sort(),
    developmentBuildComponents: devOnly.map(componentKey).sort(),
    productionClosureCrossCheck: closureVersions
      ? {
          available: true,
          closurePackageCount: closureVersions.size,
          mismatches: closureMismatches,
          consistent: closureMismatches.length === 0,
        }
      : { available: false, mismatches: [], consistent: null },
  };
}

// ---------------------------------------------------------------------------
// Markdown rendering
// ---------------------------------------------------------------------------

const SEVERITY_ORDER = { critical: 0, high: 1, moderate: 2, low: 3, info: 4 };

/**
 * Render the advisory disposition as a reviewable Markdown document.
 *
 * @param {object} report
 * @param {object} separation
 * @param {string} auditSource
 * @returns {string}
 */
function renderMarkdown(report, separation, auditSource) {
  const lines = [];
  const totals = report.totals ?? {};

  lines.push('# Dependency Scope & Release SBOM Evidence');
  lines.push('');
  lines.push('Generated by `dashboard/scripts/release-evidence.mjs`.');
  lines.push('');
  lines.push('## Advisory summary');
  lines.push('');
  lines.push('| Metric | Value |');
  lines.push('| :--- | :--- |');
  lines.push(`| Advisory source | \`${auditSource}\` |`);
  lines.push(`| npm version | ${report.npmVersion ?? 'unknown'} |`);
  lines.push(`| Total advisories | ${totals.total ?? 0} |`);
  lines.push(`| Critical | ${totals.critical ?? 0} |`);
  lines.push(`| High | ${totals.high ?? 0} |`);
  lines.push(`| Moderate | ${totals.moderate ?? 0} |`);
  lines.push(`| Low | ${totals.low ?? 0} |`);
  lines.push(`| Production closure packages | ${report.productionClosureAvailable ? report.productionClosureSize : 'unavailable'} |`);
  lines.push('');

  lines.push('## Advisory disposition');
  lines.push('');
  if (report.advisories.length === 0) {
    lines.push('No advisories reported. The committed lockfile is clean against the registry advisory database.');
    lines.push('');
  } else {
    lines.push('| Package | Severity | Direct | Scope | Runtime reachable | In production closure | Fix available |');
    lines.push('| :--- | :--- | :--- | :--- | :--- | :--- | :--- |');
    for (const adv of [...report.advisories].sort((a, b) => {
      const bySeverity = (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9);
      return bySeverity !== 0 ? bySeverity : a.package.localeCompare(b.package);
    })) {
      lines.push(
        `| \`${adv.package}\` | ${adv.severity} | ${adv.isDirect ? 'yes' : 'transitive'} | ${adv.pathScope} | ${adv.runtimeReachable ? '**yes**' : 'no'} | ${adv.inProductionClosure === null ? 'unknown' : adv.inProductionClosure ? 'yes' : 'no'} | ${adv.fixAvailable ? JSON.stringify(adv.fixAvailable) : 'none reported'} |`,
      );
    }
    lines.push('');
  }

  lines.push('## Dependency paths');
  lines.push('');
  lines.push('Every install path below is resolved from the committed `package-lock.json`,');
  lines.push('not asserted from advisory metadata.');
  lines.push('');
  if (report.advisories.length === 0) {
    lines.push('No advisory paths to report.');
    lines.push('');
  } else {
    for (const adv of report.advisories) {
      lines.push(`### \`${adv.package}\` — ${adv.severity}`);
      lines.push('');
      lines.push(`- Vulnerable range: \`${adv.vulnerableRange}\``);
      lines.push(`- Runtime reachable: ${adv.runtimeReachable ? '**yes**' : 'no'}`);
      lines.push(`- In production closure: ${adv.inProductionClosure === null ? 'unknown' : adv.inProductionClosure ? 'yes' : 'no'}`);
      lines.push(`- Fix available: ${adv.fixAvailable ? `\`${JSON.stringify(adv.fixAvailable)}\`` : 'none reported'}`);
      for (const entry of adv.via) {
        if (entry.source) {
          lines.push(`- Reachable via package: \`${entry.source}\``);
        } else {
          lines.push(
            `- ${entry.ghsa ?? 'advisory'}: ${entry.title} (${entry.severity}, CVSS ${entry.cvss ?? 'n/a'}) — ${entry.url ?? ''}`,
          );
        }
      }
      for (const inst of adv.installed) {
        lines.push('');
        lines.push(`Installed \`${inst.version}\` at \`${inst.nodePath}\` — scope: ${inst.scope}`);
        for (const chain of inst.runtimePaths) {
          lines.push(`- runtime path: \`${chain.join(' -> ')}\``);
        }
        for (const chain of inst.developmentPaths) {
          lines.push(`- development/build path: \`${chain.join(' -> ')}\``);
        }
        if (inst.runtimePaths.length === 0 && inst.developmentPaths.length === 0) {
          lines.push('- no resolved path from a declared dependency');
        }
      }
      lines.push('');
    }
  }

  lines.push('## Release SBOM separation');
  lines.push('');
  lines.push('| Metric | Value |');
  lines.push('| :--- | :--- |');
  lines.push(`| Runtime SBOM components | ${separation.runtimeComponentCount} |`);
  lines.push(`| Development/build SBOM components | ${separation.developmentBuildComponentCount} |`);
  lines.push(`| Full tree components | ${separation.totalComponentCount} |`);
  lines.push(
    `| Production closure cross-check | ${separation.productionClosureCrossCheck.available ? (separation.productionClosureCrossCheck.consistent ? 'consistent' : '**mismatched**') : 'unavailable'} |`,
  );
  lines.push('');
  lines.push(
    'The runtime SBOM (`sbom.runtime.cdx.json`) contains only the production dependency closure;',
  );
  lines.push(
    'the development SBOM (`sbom.development.cdx.json`) contains only the development/build',
  );
  lines.push(
    'toolchain; the full SBOM (`sbom.full.cdx.json`) contains the complete installed tree.',
  );
  lines.push(
    'The runtime and development SBOMs partition the full tree: the runtime SBOM is',
  );
  lines.push(
    'derived by filtering the full SBOM against the verified production closure, because',
  );
  lines.push(
    '`npm sbom --omit=dev` silently omits packages that `npm ci --omit=dev` really installs',
  );
  lines.push('(verified on npm 10.x and 12.x), which would understate the shipped dependency set.');
  lines.push('');

  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

function main() {
  const options = parseArgs(process.argv.slice(2));
  const log = (message) => {
    if (!options.quiet) console.log(message);
  };

  mkdirSync(options.outDir, { recursive: true });

  const lock = JSON.parse(readFileSync(path.join(DASHBOARD_ROOT, 'package-lock.json'), 'utf8'));

  log('Reading advisory report...');
  const { audit, source } = readAudit(DASHBOARD_ROOT);
  if (!audit) {
    console.error('ERROR: no advisory report available (npm audit --json failed).');
    return 1;
  }

  const closure = productionClosure();
  const productionClosureNames = closure === null ? null : closure.names;
  const report = analyseAdvisories(audit, lock, productionClosureNames);

  // Independent second opinion on the production closure, computed from the
  // committed lockfile alone. Agreement between the two means the runtime
  // scope claim does not depend on any single npm invocation.
  const lockfileClosure = lockfileProductionClosure(lock);
  const closureAgreement = {
    npmLsSource: closure?.source ?? null,
    npmLsCount: closure === null ? null : closure.names.size,
    lockfileCount: lockfileClosure.size,
    onlyInNpmLs: closure
      ? [...closure.names].filter((n) => !lockfileClosure.has(n)).sort()
      : null,
    onlyInLockfile: [...lockfileClosure.keys()].filter((n) => !closure?.names.has(n)).sort(),
    versionsAgree:
      closure === null
        ? null
        : [...closure.names].every((n) => lockfileClosure.get(n) === closure.versions.get(n)),
  };
  closureAgreement.consistent =
    closureAgreement.onlyInNpmLs?.length === 0 &&
    closureAgreement.onlyInLockfile.length === 0 &&
    closureAgreement.versionsAgree === true;

  writeFileSync(
    path.join(options.outDir, 'dependency-scope.json'),
    `${JSON.stringify(report, null, 2)}\n`,
    'utf8',
  );
  log(`Wrote dependency-scope.json (${report.advisories.length} advisories)`);

  let separation = {
    runtimeComponentCount: 0,
    developmentBuildComponentCount: 0,
    totalComponentCount: 0,
    runtimeComponents: [],
    developmentBuildComponents: [],
    runtimeOnlyInFullTree: [],
    productionClosureCrossCheck: { available: false, mismatches: [], consistent: null },
  };
  let runtimeSha = null;
  let developmentSha = null;
  let fullSha = null;

  if (options.sbom) {
    log('Generating full SBOM (complete installed tree)...');
    const full = generateFullSbom();

    if (!full.sbom) {
      console.error(`ERROR: SBOM generation failed (${full.error ?? 'unknown error'}).`);
      return 1;
    }

    if (!productionClosureNames) {
      console.error(
        'ERROR: the production closure could not be determined; refusing to publish a runtime SBOM that may understate the shipped dependency set.',
      );
      return 1;
    }

    // The runtime SBOM is derived from the full SBOM by filtering on the
    // verified production closure, not taken from `npm sbom --omit=dev`.
    const runtimeSbom = deriveRuntimeSbom(full.sbom, closure.versions);
    // The development SBOM is the exact complement of the runtime SBOM, so
    // the two documents partition the installed tree.
    const developmentSbom = deriveDevelopmentSbom(full.sbom, closure.versions);

    const runtimeText = `${JSON.stringify(runtimeSbom, null, 2)}\n`;
    const developmentText = `${JSON.stringify(developmentSbom, null, 2)}\n`;
    const fullText = `${JSON.stringify(full.sbom, null, 2)}\n`;
    writeFileSync(path.join(options.outDir, 'sbom.runtime.cdx.json'), runtimeText, 'utf8');
    writeFileSync(path.join(options.outDir, 'sbom.development.cdx.json'), developmentText, 'utf8');
    writeFileSync(path.join(options.outDir, 'sbom.full.cdx.json'), fullText, 'utf8');
    runtimeSha = createHash('sha256').update(runtimeText, 'utf8').digest('hex');
    developmentSha = createHash('sha256').update(developmentText, 'utf8').digest('hex');
    fullSha = createHash('sha256').update(fullText, 'utf8').digest('hex');
    log('Wrote sbom.runtime.cdx.json, sbom.development.cdx.json and sbom.full.cdx.json');

    separation = buildSeparation(full.sbom, closure.versions);
  }

  const separationManifest = {
    generatedBy: 'dashboard/scripts/release-evidence.mjs',
    lockfile: 'package-lock.json',
    advisorySource: source,
    productionClosureAgreement: closureAgreement,
    sbom: {
      runtime: { file: 'sbom.runtime.cdx.json', sha256: runtimeSha },
      development: { file: 'sbom.development.cdx.json', sha256: developmentSha },
      full: { file: 'sbom.full.cdx.json', sha256: fullSha },
    },
    separation,
  };
  writeFileSync(
    path.join(options.outDir, 'sbom-separation.json'),
    `${JSON.stringify(separationManifest, null, 2)}\n`,
    'utf8',
  );
  log('Wrote sbom-separation.json');

  writeFileSync(
    path.join(options.outDir, 'dependency-scope.md'),
    renderMarkdown(report, separation, source),
    'utf8',
  );
  log('Wrote dependency-scope.md');

  log('');
  log(formatSummary(report));
  log('');
  log(
    `Release SBOM separation: ${separation.runtimeComponentCount} runtime / ${separation.developmentBuildComponentCount} development-build / ${separation.totalComponentCount} total components.`,
  );

  if (
    separation.productionClosureCrossCheck.available &&
    separation.productionClosureCrossCheck.consistent === false
  ) {
    console.error('ERROR: production closure cross-check reported mismatches.');
    return 1;
  }

  if (closureAgreement.consistent === false) {
    console.error(
      'ERROR: the production closure derived from `npm ls --omit=dev --all` and the closure derived from the committed lockfile disagree.',
    );
    console.error(`  only in npm ls:    ${JSON.stringify(closureAgreement.onlyInNpmLs)}`);
    console.error(`  only in lockfile: ${JSON.stringify(closureAgreement.onlyInLockfile)}`);
    console.error(`  versions agree:   ${closureAgreement.versionsAgree}`);
    return 1;
  }

  return 0;
}

// Only run the generator when this module is executed directly. Importing it
// (for example from the unit tests) must not trigger evidence generation.
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(main());
}
