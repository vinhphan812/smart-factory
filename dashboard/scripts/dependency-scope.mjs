/**
 * scripts/dependency-scope.mjs
 *
 * Shared dependency-scope analysis for the Smart Factory Operator Dashboard.
 *
 * Purpose
 * -------
 * `npm audit` reports advisory *packages*. It does not report whether an
 * advisory is reachable from the code that actually ships. This module resolves
 * every advisory to:
 *
 *   1. the concrete install path(s) from a declared dependency down to the
 *      vulnerable package (evidence, not assertion), and
 *   2. the scope of that path — `runtime` (reachable from `dependencies`) or
 *      `development/build` (reachable only from `devDependencies`).
 *
 * The classification is derived from the committed lockfile (`package-lock.json`),
 * not from npm's prose, so it is reproducible and reviewable.
 *
 * Scope vocabulary used across the release evidence:
 *   - `runtime`           : reachable through `dependencies`; ships in the bundle.
 *   - `development/build` : reachable only through `devDependencies`; test/build
 *                           toolchain; not present in the production bundle.
 *
 * Usage:
 *   import { analyseAdvisories } from './dependency-scope.mjs';
 *   const report = analyseAdvisories(auditJson, lockfileJson);
 */

import { execFileSync } from 'node:child_process';

// ---------------------------------------------------------------------------
// Lockfile model
// ---------------------------------------------------------------------------

/**
 * Build an index of every installed package in a lockfile v2/v3 file.
 *
 * @param {object} lock Parsed package-lock.json
 * @returns {Map<string, {name: string, version: string, dev: boolean, optional: boolean, peer: boolean, depth: number}>}
 */
export function indexLockfile(lock) {
  const packages = lock?.packages ?? {};
  const index = new Map();
  for (const [path, meta] of Object.entries(packages)) {
    if (!path) continue; // the root project entry
    const name = meta.name ?? path.split('node_modules/').pop();
    index.set(path, {
      name,
      version: meta.version,
      dev: Boolean(meta.dev),
      optional: Boolean(meta.optional),
      peer: Boolean(meta.peer),
      depth: path.split('node_modules/').length - 1,
    });
  }
  return index;
}

/**
 * Resolve a dependency name from a given lockfile node, walking up the
 * `node_modules` chain exactly as Node's resolution algorithm does: the
 * nearest nested `node_modules` wins, then each ancestor scope, then the root.
 *
 * @param {Map<string, object>} index Lockfile index
 * @param {string} fromPath Lockfile path of the requiring package ('' = root)
 * @param {string} depName Dependency name to resolve
 * @returns {string|null} Resolved lockfile path
 */
export function resolveFrom(index, fromPath, depName) {
  let base = fromPath;
  for (;;) {
    const candidate = base ? `${base}/node_modules/${depName}` : `node_modules/${depName}`;
    if (index.has(candidate)) return candidate;
    if (!base) return null;
    const cut = base.lastIndexOf('/node_modules/');
    base = cut === -1 ? '' : base.slice(0, cut);
  }
}

/**
 * Declared dependencies of a lockfile node.
 *
 * Regular and optional dependencies are hard edges. Peer dependencies are
 * included because npm 7+ materialises them into the tree, so a package that is
 * only ever a peer of a runtime package is still installed for the runtime.
 *
 * @param {object} lock Parsed package-lock.json
 * @param {string} path Lockfile path
 * @returns {Record<string, string>}
 */
export function declaredDependencies(lock, path) {
  const meta = lock?.packages?.[path];
  if (!meta) return {};
  return {
    ...(meta.dependencies ?? {}),
    ...(meta.optionalDependencies ?? {}),
    ...(meta.peerDependencies ?? {}),
  };
}

/**
 * Find every install path from a declared (direct) dependency down to a target
 * package, using breadth-first search over the resolved lockfile tree.
 *
 * @param {object} lock Parsed package-lock.json
 * @param {Map<string, object>} index Lockfile index
 * @param {string} targetPath Lockfile path of the vulnerable package
 * @param {number} [maxDepth]
 * @returns {Array<{chain: string[], isDev: boolean}>}
 */
export function findInstallPaths(lock, index, targetPath, maxDepth = 12) {
  const rootMeta = lock?.packages?.[''] ?? {};
  const runtimeDeps = rootMeta.dependencies ?? {};
  const devDeps = rootMeta.devDependencies ?? {};
  const optionalDeps = rootMeta.optionalDependencies ?? {};

  const roots = [];
  for (const depName of Object.keys({ ...runtimeDeps, ...devDeps, ...optionalDeps })) {
    const resolved = resolveFrom(index, '', depName);
    if (!resolved) continue;
    roots.push({
      name: depName,
      path: resolved,
      // A dependency that is only a devDependency is development/build scope.
      // A dependency listed in `dependencies` is runtime scope even if it also
      // appears in `devDependencies`.
      isDev: Boolean(devDeps[depName]) && !runtimeDeps[depName] && !optionalDeps[depName],
    });
  }

  const results = [];
  const queue = roots.map((r) => ({ path: r.path, chain: [r.name], isDev: r.isDev }));
  const seen = new Set();

  while (queue.length > 0) {
    const { path, chain, isDev } = queue.shift();
    if (chain.length > maxDepth) continue;
    if (path === targetPath) {
      results.push({ chain, isDev });
      continue;
    }
    const key = `${path}|${chain.length}`;
    if (seen.has(key)) continue;
    seen.add(key);
    for (const depName of Object.keys(declaredDependencies(lock, path))) {
      const resolved = resolveFrom(index, path, depName);
      if (!resolved) continue;
      queue.push({ path: resolved, chain: [...chain, depName], isDev });
    }
  }
  return results;
}

/**
 * Classify a lockfile node as runtime or development/build scope.
 *
 * @param {object} lock
 * @param {Map<string, object>} index
 * @param {string} path
 * @returns {{version: string|undefined, scope: 'runtime'|'development/build'|'unresolved', runtime: Array, dev: Array}}
 */
export function classifyScope(lock, index, path) {
  const paths = findInstallPaths(lock, index, path);
  const runtime = paths.filter((p) => !p.isDev);
  const dev = paths.filter((p) => p.isDev);
  const info = index.get(path);
  return {
    version: info?.version,
    scope: runtime.length > 0 ? 'runtime' : dev.length > 0 ? 'development/build' : 'unresolved',
    runtime,
    dev,
  };
}

// ---------------------------------------------------------------------------
// Production dependency closure
// ---------------------------------------------------------------------------

/**
 * Spawn npm in a platform-portable way. On Windows `npm` is a `.cmd` shim that
 * cannot be exec'd directly, so the shell is used there.
 *
 * @param {string[]} args
 * @returns {string} stdout
 */
export function runNpm(args) {
  const isWindows = process.platform === 'win32';
  try {
    return execFileSync('npm', args, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
      shell: isWindows,
      maxBuffer: 128 * 1024 * 1024,
    });
  } catch (err) {
    // `npm ls` exits non-zero when the tree has peer-dependency warnings; the
    // tree is still printed on stdout in that case.
    if (err?.stdout) return err.stdout;
    throw err;
  }
}

/**
 * Names of every package in the production dependency closure (`npm ci
 * --omit=dev` semantics): the set of packages that can ship.
 *
 * `npm ls --omit=dev --all --json` reports the tree in two distinct kinds of
 * node, and they must not be conflated:
 *
 *   - *resolved* nodes (`resolved` is set) are physically installed packages;
 *   - *unresolved* nodes are either peer-shadow duplicates of an already
 *     listed package, or optional peers that were never installed (npm
 *     reports these with no version at all).
 *
 * Only resolved nodes are actually installed by `npm ci --omit=dev`, so only
 * resolved nodes belong to the production closure. Including unresolved nodes
 * would overstate the closure with packages that never ship.
 *
 * @returns {Set<string>|null} null when npm could not report the tree
 */
export function productionClosureNames() {
  const closure = productionClosure();
  return closure === null ? null : closure.names;
}

/**
 * The production dependency closure with the resolved version of each package.
 *
 * @returns {{names: Set<string>, versions: Map<string, string>, source: string}|null}
 *   null when npm could not report the tree
 */
export function productionClosure() {
  try {
    const parsed = JSON.parse(runNpm(['ls', '--omit=dev', '--all', '--json']));
    const names = new Set();
    const versions = new Map();
    const walk = (node) => {
      for (const [depName, dep] of Object.entries(node.dependencies ?? {})) {
        if (dep?.resolved && dep?.version && !versions.has(depName)) {
          versions.set(depName, dep.version);
          names.add(depName);
        }
        if (dep?.dependencies) walk(dep);
      }
    };
    walk(parsed);
    return { names, versions, source: 'npm ls --omit=dev --all --json (resolved nodes only)' };
  } catch {
    return null;
  }
}

/**
 * The production dependency closure derived from the committed lockfile alone:
 * every package npm did not flag as dev-only.
 *
 * This is an independent second opinion on the closure. It is computed without
 * invoking npm, so it stays reproducible on a machine with no installed tree.
 *
 * @param {object} lock Parsed package-lock.json
 * @returns {Map<string, string>} package name -> version
 */
export function lockfileProductionClosure(lock) {
  const packages = lock?.packages ?? {};
  const closure = new Map();
  for (const [nodePath, meta] of Object.entries(packages)) {
    if (!nodePath) continue; // the root project entry
    if (meta.dev) continue; // dev-only: test/build toolchain, never shipped
    const name = meta.name ?? nodePath.split('node_modules/').pop();
    if (!closure.has(name)) closure.set(name, meta.version);
  }
  return closure;
}

// ---------------------------------------------------------------------------
// Advisory analysis
// ---------------------------------------------------------------------------

/**
 * Analyse an `npm audit --json` report against a committed lockfile.
 *
 * @param {object} audit Parsed npm audit JSON report
 * @param {object} lock Parsed package-lock.json
 * @param {Set<string>|null} [productionClosure]
 * @returns {object} Machine-readable advisory analysis
 */
export function analyseAdvisories(audit, lock, productionClosure = productionClosureNames()) {
  const index = indexLockfile(lock);

  const advisories = [];
  for (const [name, vuln] of Object.entries(audit?.vulnerabilities ?? {})) {
    const via = (vuln.via ?? []).map((entry) =>
      typeof entry === 'string'
        ? { source: entry }
        : {
            title: entry.title,
            severity: entry.severity,
            vulnerableRange: entry.range,
            url: entry.url,
            ghsa: entry.ghsaId ?? entry.cve ?? null,
            cwe: entry.cwe ?? null,
            cvss: entry.cvss?.score ?? null,
          },
    );

    const installed = [...index.entries()]
      .filter(([, info]) => info.name === name)
      .map(([nodePath]) => {
        const detail = classifyScope(lock, index, nodePath);
        return {
          nodePath,
          version: detail.version,
          scope: detail.scope,
          runtimePaths: detail.runtime.map((p) => p.chain),
          developmentPaths: detail.dev.map((p) => p.chain),
        };
      });

    // The production closure is the authoritative "can this ship?" signal: it
    // is what `npm ci --omit=dev` actually installs. Path analysis is the
    // explanatory evidence. A package is runtime-reachable when either signal
    // says so.
    const inProductionClosure = productionClosure === null ? null : productionClosure.has(name);
    const pathSaysRuntime = installed.some((i) => i.scope === 'runtime');

    advisories.push({
      package: name,
      severity: vuln.severity,
      isDirect: Boolean(vuln.isDirect),
      vulnerableRange: vuln.range,
      fixAvailable: vuln.fixAvailable ?? null,
      via,
      installed,
      pathScope: pathSaysRuntime
        ? 'runtime'
        : installed.length > 0 && installed.every((i) => i.scope === 'development/build')
          ? 'development/build'
          : 'unresolved',
      inProductionClosure,
      runtimeReachable: pathSaysRuntime || inProductionClosure === true,
      developmentOnly: !pathSaysRuntime && inProductionClosure === false,
    });
  }

  const severityRank = { critical: 0, high: 1, moderate: 2, low: 3, info: 4 };
  advisories.sort((a, b) => {
    const bySeverity = (severityRank[a.severity] ?? 9) - (severityRank[b.severity] ?? 9);
    return bySeverity !== 0 ? bySeverity : a.package.localeCompare(b.package);
  });

  return {
    generatedFrom: 'npm audit --json',
    lockfile: 'package-lock.json',
    npmVersion: audit?.metadata?.npm_version ?? null,
    totals: audit?.metadata?.vulnerabilities ?? null,
    productionClosureAvailable: productionClosure !== null,
    productionClosureSize: productionClosure === null ? null : productionClosure.size,
    advisories,
  };
}

/**
 * Render a short, human-readable summary of an analysis report.
 *
 * @param {object} report Result of {@link analyseAdvisories}
 * @returns {string}
 */
export function formatSummary(report) {
  const lines = [];
  const totals = report.totals ?? {};
  lines.push(
    `Advisories: ${totals.total ?? 0} (critical ${totals.critical ?? 0}, high ${totals.high ?? 0}, moderate ${totals.moderate ?? 0}, low ${totals.low ?? 0})`,
  );
  lines.push(
    `Production closure (npm ls --omit=dev): ${report.productionClosureAvailable ? `${report.productionClosureSize} packages` : 'unavailable'}`,
  );
  for (const adv of report.advisories) {
    lines.push('');
    lines.push(`${adv.package} — ${adv.severity} (direct: ${adv.isDirect ? 'yes' : 'no'})`);
    lines.push(`  vulnerable range: ${adv.vulnerableRange}`);
    lines.push(`  runtime reachable: ${adv.runtimeReachable ? 'YES' : 'no'}`);
    lines.push(`  in production closure: ${adv.inProductionClosure === null ? 'unknown' : adv.inProductionClosure ? 'yes' : 'no'}`);
    lines.push(`  fix available: ${JSON.stringify(adv.fixAvailable)}`);
    for (const inst of adv.installed) {
      lines.push(`  installed ${inst.version} @ ${inst.nodePath} — scope ${inst.scope}`);
      for (const p of inst.runtimePaths) lines.push(`    runtime path: ${p.join(' -> ')}`);
      for (const p of inst.developmentPaths) lines.push(`    dev path:     ${p.join(' -> ')}`);
    }
    for (const entry of adv.via) {
      if (entry.source) lines.push(`  via package: ${entry.source}`);
      else lines.push(`  via: ${entry.ghsa ?? ''} ${entry.title} (${entry.severity}, cvss ${entry.cvss}) ${entry.url ?? ''}`);
    }
  }
  return lines.join('\n');
}
