#!/usr/bin/env node
/**
 * scripts/release-evidence-archive.mjs
 *
 * Produces the *archived* release-evidence set for one exact commit.
 *
 * The advisory triage and the SBOM separation are **not** re-implemented
 * here: they are produced by `scripts/release-evidence.mjs`, which this
 * script invokes as a child process and whose outputs are collected into the
 * archive verbatim. This script only adds what the triage cannot provide:
 *
 *   1. the raw `npm audit --json` output for the production dependency tree
 *      (`npm audit --json --omit=dev`) and for the full tree, captured
 *      byte-for-byte together with npm's exit code;
 *   2. the production (runtime closure) SBOM and the development/build SBOM
 *      produced by the generator;
 *   3. a SHA256 manifest (`MANIFEST.json`) listing every produced artefact
 *      with its filename, SHA256 digest and byte size, plus a GNU-compatible
 *      `SHA256SUMS` for convenience;
 *   4. the exact commit SHA the artefacts were produced from, recorded
 *      inside the artefact set itself (`COMMIT` and `METADATA.json`);
 *   5. a `README.md` that documents a one-line command a reviewer can run to
 *      re-verify the manifest without trusting any report text;
 *   6. the manifest verification itself, and an advisory gate that fails on
 *      any high or critical advisory.
 *
 * Usage:
 *   node scripts/release-evidence-archive.mjs                     # produce + verify
 *   node scripts/release-evidence-archive.mjs --verify            # verify an existing set
 *   node scripts/release-evidence-archive.mjs --gate              # audit gate only
 *
 * Options:
 *   --out-dir <dir>   Directory the archive is written to.
 *                      Default: dashboard/release-evidence-archive/
 *   --commit <sha>    Commit SHA recorded in the archive. Defaults to the
 *                      SHA of the checked-out tree (`git rev-parse HEAD`).
 *
 * Exit codes:
 *   0  archive produced and verified / verification passed / gate passed
 *   1  the archive could not be produced, could not be verified, or the
 *      advisory gate reported a high or critical vulnerability
 */

import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DASHBOARD_ROOT = path.resolve(HERE, '..');
const DEFAULT_OUT_DIR = path.join(DASHBOARD_ROOT, 'release-evidence-archive');
const GENERATOR = path.join(HERE, 'release-evidence.mjs');

/** Files written by this script; they are never part of the manifest itself. */
const MANIFEST_FILE = 'MANIFEST.json';
const SUMS_FILE = 'SHA256SUMS';

/** Severity levels that fail the advisory gate. */
export const BLOCKING_SEVERITIES = ['high', 'critical'];

// ---------------------------------------------------------------------------
// Argument parsing
// ---------------------------------------------------------------------------

/**
 * @param {string[]} argv
 * @returns {{outDir: string, commit: string|null, mode: 'produce'|'verify'|'gate'}}
 */
function parseArgs(argv) {
  const options = { outDir: DEFAULT_OUT_DIR, commit: null, mode: 'produce' };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--out-dir') {
      options.outDir = path.resolve(argv[++i]);
    } else if (arg === '--commit') {
      options.commit = argv[++i];
    } else if (arg === '--verify') {
      options.mode = 'verify';
    } else if (arg === '--gate') {
      options.mode = 'gate';
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return options;
}

// ---------------------------------------------------------------------------
// Process helpers
// ---------------------------------------------------------------------------

/**
 * Run npm and capture stdout plus the exit code.
 *
 * `npm audit` exits non-zero when it finds advisories, but it still prints a
 * complete JSON report on stdout. That report is the evidence, so the exit
 * code is recorded rather than treated as a failure of the capture.
 *
 * @param {string[]} args
 * @param {string} cwd
 * @returns {{stdout: string, status: number}}
 */
export function runNpmCapture(args, cwd) {
  const isWindows = process.platform === 'win32';
  try {
    const stdout = execFileSync('npm', args, {
      cwd,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: isWindows,
      maxBuffer: 256 * 1024 * 1024,
    });
    return { stdout, status: 0 };
  } catch (err) {
    const stdout = typeof err?.stdout === 'string' ? err.stdout : '';
    const status = typeof err?.status === 'number' ? err.status : 1;
    return { stdout, status };
  }
}

/**
 * The SHA of the checked-out tree, used as the default commit binding.
 *
 * @param {string} cwd
 * @returns {string|null}
 */
export function gitHead(cwd) {
  try {
    return execFileSync('git', ['rev-parse', 'HEAD'], {
      cwd,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Manifest primitives
// ---------------------------------------------------------------------------

/**
 * @param {string} file
 * @returns {string} lowercase hex SHA256 digest of the file
 */
export function sha256File(file) {
  return createHash('sha256').update(readFileSync(file)).digest('hex');
}

/**
 * Every file under `dir`, as POSIX-style relative paths, sorted.
 *
 * @param {string} dir
 * @param {string} [prefix]
 * @returns {string[]}
 */
export function collectFiles(dir, prefix = '') {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectFiles(full, rel));
    } else if (entry.isFile()) {
      out.push(rel);
    }
  }
  return out.sort();
}

/**
 * Build the SHA256 manifest for the files in `outDir`.
 *
 * Every listed artefact carries its filename, its SHA256 digest and its byte
 * size, so a reviewer can check integrity *and* completeness (a truncated
 * file changes its size as well as its digest).
 *
 * @param {string} outDir
 * @param {string} commit
 * @returns {{schema: string, commit: string, generatedAt: string, generator: string, artifactCount: number, artifacts: {file: string, sha256: string, bytes: number}[]}}
 */
export function buildManifest(outDir, commit) {
  const files = collectFiles(outDir).filter(
    (f) => f !== MANIFEST_FILE && f !== SUMS_FILE,
  );
  const artifacts = files.map((file) => {
    const full = path.join(outDir, file);
    return {
      file,
      sha256: sha256File(full),
      bytes: statSync(full).size,
    };
  });
  return {
    schema: 'smart-factory/release-evidence-manifest/v1',
    commit,
    generatedAt: new Date().toISOString(),
    generator: 'dashboard/scripts/release-evidence-archive.mjs',
    artifactCount: artifacts.length,
    artifacts,
  };
}

/**
 * Write the SHA256 manifest into the archive directory.
 *
 * The manifest cannot list itself, so it is written after the artefact list
 * has been computed and it is excluded from `buildManifest`'s own scan.
 *
 * @param {string} outDir
 * @param {string} commit
 * @returns {{schema: string, commit: string, generatedAt: string, generator: string, artifactCount: number, artifacts: {file: string, sha256: string, bytes: number}[]}}
 */
export function writeManifest(outDir, commit) {
  const manifest = buildManifest(outDir, commit);
  writeFileSync(
    path.join(outDir, MANIFEST_FILE),
    `${JSON.stringify(manifest, null, 2)}\n`,
    'utf8',
  );
  writeSums(outDir, manifest.artifacts);
  return manifest;
}

/**
 * Create a temporary directory populated with the given files.
 *
 * The dashboard package deliberately does not depend on `@types/node`, so the
 * Node built-ins are used here, inside the plain ES module, and the typed
 * surface is declared in `release-evidence-archive.d.mts`. The test suite
 * therefore never has to import `node:fs` from TypeScript.
 *
 * @param {Record<string, string>} files Relative filename -> file contents
 * @returns {string} The absolute path of the created directory
 */
export function createTempArchive(files) {
  const dir = mkdtempSync(path.join(tmpdir(), 'release-evidence-'));
  for (const [name, contents] of Object.entries(files)) {
    const target = path.join(dir, name);
    mkdirSync(path.dirname(target), { recursive: true });
    writeFileSync(target, contents, 'utf8');
  }
  return dir;
}

/**
 * Remove a directory created by `createTempArchive`.
 *
 * @param {string} dir
 * @returns {void}
 */
export function cleanupTempArchive(dir) {
  rmSync(dir, { recursive: true, force: true });
}

/**
 * Write (or overwrite) one file inside an archive directory.
 *
 * @param {string} dir
 * @param {string} name Relative filename inside the archive
 * @param {string} contents
 * @returns {void}
 */
export function writeArchiveFile(dir, name, contents) {
  const target = path.join(dir, name);
  mkdirSync(path.dirname(target), { recursive: true });
  writeFileSync(target, contents, 'utf8');
}

/**
 * Delete one file inside an archive directory.
 *
 * @param {string} dir
 * @param {string} name Relative filename inside the archive
 * @returns {void}
 */
export function removeArchiveFile(dir, name) {
  rmSync(path.join(dir, name), { force: true });
}

/**
 * Verify an archive against its manifest.
 *
 * Three classes of defect are detected: a listed artefact whose digest or
 * byte size does not match, a listed artefact that is missing, and an
 * artefact present in the archive but absent from the manifest.
 *
 * @param {string} outDir
 * @returns {{ok: boolean, checked: number, mismatches: {file: string, issue: string}[]}}
 */
export function verifyManifest(outDir) {
  const manifestPath = path.join(outDir, MANIFEST_FILE);
  if (!existsSync(manifestPath)) {
    return {
      ok: false,
      checked: 0,
      mismatches: [{ file: MANIFEST_FILE, issue: 'manifest is missing' }],
    };
  }

  let manifest;
  try {
    manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  } catch (err) {
    return {
      ok: false,
      checked: 0,
      mismatches: [{ file: MANIFEST_FILE, issue: `manifest is not valid JSON: ${err.message}` }],
    };
  }

  const mismatches = [];
  const listed = new Set();

  for (const artefact of manifest.artifacts ?? []) {
    listed.add(artefact.file);
    const full = path.join(outDir, artefact.file);
    if (!existsSync(full)) {
      mismatches.push({ file: artefact.file, issue: 'listed artefact is missing' });
      continue;
    }
    const size = statSync(full).size;
    if (size !== artefact.bytes) {
      mismatches.push({
        file: artefact.file,
        issue: `byte size mismatch: manifest ${artefact.bytes}, on disk ${size}`,
      });
      continue;
    }
    const digest = sha256File(full);
    if (digest !== artefact.sha256) {
      mismatches.push({
        file: artefact.file,
        issue: `SHA256 mismatch: manifest ${artefact.sha256}, on disk ${digest}`,
      });
    }
  }

  for (const file of collectFiles(outDir)) {
    if (file === MANIFEST_FILE || file === SUMS_FILE) continue;
    if (!listed.has(file)) {
      mismatches.push({ file, issue: 'artefact is present but not listed in the manifest' });
    }
  }

  return { ok: mismatches.length === 0, checked: listed.size, mismatches };
}

// ---------------------------------------------------------------------------
// Advisory gate
// ---------------------------------------------------------------------------

/**
 * Extract the advisories at or above the blocking severities.
 *
 * @param {object} audit Parsed `npm audit --json` report
 * @param {string[]} severities
 * @returns {{name: string, severity: string, isDirect: boolean, range: string|null}[]}
 */
export function blockingAdvisories(audit, severities = BLOCKING_SEVERITIES) {
  const out = [];
  for (const [name, entry] of Object.entries(audit?.vulnerabilities ?? {})) {
    if (!severities.includes(entry?.severity)) continue;
    out.push({
      name: entry?.name ?? name,
      severity: entry.severity,
      isDirect: Boolean(entry?.isDirect),
      range: entry?.range ?? null,
    });
  }
  return out.sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * Write the GNU-compatible digest list for the same file set as the manifest.
 *
 * @param {string} outDir
 * @param {{file: string, sha256: string}[]} artifacts
 */
export function writeSums(outDir, artifacts) {
  const rows = artifacts
    .map((a) => `${a.sha256}  ${a.file}`)
    .sort((a, b) => a.slice(66).localeCompare(b.slice(66)));
  writeFileSync(path.join(outDir, SUMS_FILE), `${rows.join('\n')}\n`, 'utf8');
}

// ---------------------------------------------------------------------------
// Archive production
// ---------------------------------------------------------------------------

/**
 * The one-line verification command documented in the archive README.
 *
 * It re-reads `MANIFEST.json` and recomputes both the SHA256 digest and the
 * byte size of every listed artefact. It depends on nothing but Node and the
 * archive directory, so a reviewer needs no repository checkout and no trust
 * in any report text.
 */
export const VERIFY_COMMAND =
  "node -e \"const fs=require('fs'),c=require('crypto'),m=JSON.parse(fs.readFileSync('MANIFEST.json','utf8'));let bad=0;for(const a of m.artifacts){const b=fs.readFileSync(a.file);if(c.createHash('sha256').update(b).digest('hex')!==a.sha256||b.length!==a.bytes){console.error('MISMATCH '+a.file);bad++}}if(bad)process.exit(1);console.log('OK: '+m.artifacts.length+' artefacts verified against MANIFEST.json (commit '+m.commit+')')\"";

/**
 * @param {object} meta
 * @returns {string}
 */
function renderReadme(meta) {
  return `# Archived release evidence

This directory is the archived, SHA-bound release evidence for **one exact
commit**. It is produced by \`dashboard/scripts/release-evidence-archive.mjs\`
and uploaded as a retained CI artefact.

| Field | Value |
| :--- | :--- |
| Commit | \`${meta.commit}\` |
| Checkout HEAD | \`${meta.checkoutHead ?? 'n/a'}\` |
| Workflow run | ${meta.runUrl ? `[${meta.runId}](${meta.runUrl})` : `\`${meta.runId ?? 'n/a'}\``} |
| Repository | \`${meta.repository ?? 'n/a'}\` |
| Ref | \`${meta.ref ?? 'n/a'}\` |
| Node / npm | ${meta.nodeVersion} / ${meta.npmVersion} |
| Generated at | ${meta.generatedAt} |

## Contents

| File | Description |
| :--- | :--- |
| \`COMMIT\` | The exact commit SHA these artefacts were produced from. |
| \`METADATA.json\` | Provenance: commit, run, tool versions, npm audit exit codes. |
| \`npm-audit.production.json\` | Raw \`npm audit --json --omit=dev\` output for the production dependency tree. |
| \`npm-audit.full.json\` | Raw \`npm audit --json\` output for the full installed tree. |
| \`sbom.runtime.cdx.json\` | Production SBOM: the runtime closure (ships in the bundle). |
| \`sbom.development.cdx.json\` | Development/build SBOM: the complement of the runtime closure. |
| \`sbom.full.cdx.json\` | CycloneDX SBOM of the complete installed tree. |
| \`sbom-separation.json\` | Generator's separation manifest, with per-SBOM digests. |
| \`dependency-scope.json\` | Machine-readable advisory disposition. |
| \`dependency-scope.md\` | Human-readable advisory disposition. |
| \`MANIFEST.json\` | SHA256 manifest: filename, SHA256 and byte size of every artefact above. |
| \`SHA256SUMS\` | GNU-compatible digest list for \`sha256sum -c SHA256SUMS\`. |

## Verifying this archive

Run this **one line** inside this directory. It re-reads \`MANIFEST.json\` and
recomputes the SHA256 digest and the byte size of every listed artefact. It
needs nothing but Node and this directory, so it does not trust any report
text:

\`\`\`
${VERIFY_COMMAND}
\`\`\`

\`MANIFEST.json\` and \`SHA256SUMS\` cannot list themselves, so they are not
self-verifying. The SHA256 of \`MANIFEST.json\` is published in the CI run log
and in the pull request body; compare it with:

\`\`\`
sha256sum MANIFEST.json
\`\`\`

A digest-only cross-check is also available:

\`\`\`
sha256sum -c SHA256SUMS
\`\`\`

## Advisory gate

The CI job that produces this archive fails when either audit report contains
a **high** or **critical** advisory. The gate is not skippable and is not
\`continue-on-error\`.

## Retention

GitHub Actions artefact retention for this repository is capped at
**${meta.retentionDays} days**. The archive is therefore *not* an immutable,
permanently retained record: it expires. The digest of \`MANIFEST.json\` and
the commit SHA are also stated in the pull request body so that the claim
remains checkable after the artefact itself has expired.
`;
}

/**
 * Produce the whole archive.
 *
 * @param {{outDir: string, commit: string|null}} options
 * @returns {number} exit code
 */
function produce(options) {
  const outDir = options.outDir;

  // A stale archive must never be silently mixed with fresh artefacts.
  rmSync(outDir, { recursive: true, force: true });
  mkdirSync(outDir, { recursive: true });

  const checkoutHead = gitHead(DASHBOARD_ROOT);
  const commit = options.commit ?? checkoutHead;
  if (!commit) {
    console.error(
      'ERROR: no commit SHA available; pass --commit <sha> or run inside a git checkout.',
    );
    return 1;
  }
  // The archive must be bound to the tree it was actually built from. If the
  // caller states a commit that is not the checked-out HEAD, the evidence
  // would claim a provenance it does not have, so refuse to produce it.
  if (checkoutHead && commit !== checkoutHead) {
    console.error(
      `ERROR: the stated commit ${commit} does not match the checked-out HEAD ${checkoutHead}.`,
    );
    return 1;
  }
  console.log(`[release-evidence-archive] commit ${commit}`);

  // --- 1. raw audit reports -------------------------------------------------
  const prodAudit = runNpmCapture(['audit', '--json', '--omit=dev'], DASHBOARD_ROOT);
  if (!prodAudit.stdout.trim()) {
    console.error('ERROR: `npm audit --json --omit=dev` produced no output.');
    return 1;
  }
  writeFileSync(path.join(outDir, 'npm-audit.production.json'), prodAudit.stdout, 'utf8');
  console.log(
    `[release-evidence-archive] npm-audit.production.json written (npm exit ${prodAudit.status})`,
  );

  const fullAudit = runNpmCapture(['audit', '--json'], DASHBOARD_ROOT);
  if (!fullAudit.stdout.trim()) {
    console.error('ERROR: `npm audit --json` produced no output.');
    return 1;
  }
  writeFileSync(path.join(outDir, 'npm-audit.full.json'), fullAudit.stdout, 'utf8');
  console.log(
    `[release-evidence-archive] npm-audit.full.json written (npm exit ${fullAudit.status})`,
  );

  // Hand the generator the very same bytes so the advisory disposition and
  // the archived raw report cannot disagree. The generator prefers a captured
  // `npm-audit.json` over a fresh invocation, and the file is git-ignored.
  writeFileSync(path.join(DASHBOARD_ROOT, 'npm-audit.json'), fullAudit.stdout, 'utf8');

  // --- 2. SBOMs and advisory disposition, from the existing generator -------
  try {
    execFileSync(process.execPath, [GENERATOR, '--out-dir', outDir], {
      cwd: DASHBOARD_ROOT,
      stdio: 'inherit',
    });
  } catch {
    console.error('ERROR: dashboard/scripts/release-evidence.mjs failed.');
    return 1;
  }
  for (const required of [
    'sbom.runtime.cdx.json',
    'sbom.development.cdx.json',
    'sbom.full.cdx.json',
    'sbom-separation.json',
    'dependency-scope.json',
    'dependency-scope.md',
  ]) {
    if (!existsSync(path.join(outDir, required))) {
      console.error(`ERROR: the generator did not produce ${required}.`);
      return 1;
    }
  }

  // --- 3. commit binding and provenance -------------------------------------
  writeFileSync(path.join(outDir, 'COMMIT'), `${commit}\n`, 'utf8');

  let npmVersion = 'unknown';
  try {
    npmVersion = execFileSync('npm', ['--version'], {
      cwd: DASHBOARD_ROOT,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
      shell: process.platform === 'win32',
    }).trim();
  } catch {
    /* keep the placeholder */
  }

  const metadata = {
    schema: 'smart-factory/release-evidence-metadata/v1',
    commit,
    checkoutHead,
    generatedAt: new Date().toISOString(),
    repository: process.env.GITHUB_REPOSITORY ?? null,
    ref: process.env.GITHUB_REF ?? null,
    sha: process.env.GITHUB_SHA ?? null,
    runId: process.env.GITHUB_RUN_ID ?? null,
    runUrl:
      process.env.GITHUB_RUN_ID && process.env.GITHUB_REPOSITORY
        ? `https://github.com/${process.env.GITHUB_REPOSITORY}/actions/runs/${process.env.GITHUB_RUN_ID}`
        : null,
    nodeVersion: process.version,
    npmVersion,
    npmAuditExitCode: { production: prodAudit.status, full: fullAudit.status },
  };
  writeFileSync(
    path.join(outDir, 'METADATA.json'),
    `${JSON.stringify(metadata, null, 2)}\n`,
    'utf8',
  );

  writeFileSync(
    path.join(outDir, 'README.md'),
    renderReadme({
      ...metadata,
      retentionDays: process.env.RELEASE_EVIDENCE_RETENTION_DAYS ?? '90',
    }),
    'utf8',
  );

  // --- 4. manifest ----------------------------------------------------------
  const manifest = writeManifest(outDir, commit);
  console.log(
    `[release-evidence-archive] ${MANIFEST_FILE} lists ${manifest.artifactCount} artefact(s)`,
  );

  // --- 5. verify ------------------------------------------------------------
  const verification = verifyManifest(outDir);
  if (!verification.ok) {
    console.error('ERROR: the SHA256 manifest did not verify against the archive.');
    for (const m of verification.mismatches) {
      console.error(`  ${m.file}: ${m.issue}`);
    }
    return 1;
  }
  console.log(
    `[release-evidence-archive] manifest verified: ${verification.checked} artefact(s) OK`,
  );
  console.log(
    `[release-evidence-archive] MANIFEST.json sha256 ${sha256File(path.join(outDir, MANIFEST_FILE))}`,
  );

  return 0;
}

// ---------------------------------------------------------------------------
// Gate
// ---------------------------------------------------------------------------

/**
 * Fail on any high or critical advisory in the archived audit reports.
 *
 * @param {string} outDir
 * @returns {number} exit code
 */
function gate(outDir) {
  const reports = [
    ['npm-audit.production.json', 'production dependency tree'],
    ['npm-audit.full.json', 'full installed tree'],
  ];
  let blocking = 0;

  for (const [file, scope] of reports) {
    const full = path.join(outDir, file);
    if (!existsSync(full)) {
      console.error(`ERROR: ${file} is missing from ${outDir}; the archive is incomplete.`);
      return 1;
    }
    let audit;
    try {
      audit = JSON.parse(readFileSync(full, 'utf8'));
    } catch (err) {
      console.error(`ERROR: ${file} is not valid JSON: ${err.message}`);
      return 1;
    }
    const found = blockingAdvisories(audit);
    const counts = audit?.metadata?.vulnerabilities ?? {};
    console.log(
      `[release-evidence-archive] ${scope}: total=${counts.total ?? 'unknown'} high=${counts.high ?? 0} critical=${counts.critical ?? 0}`,
    );
    for (const advisory of found) {
      console.error(
        `  BLOCKING ${advisory.severity.toUpperCase()}: ${advisory.name}${advisory.range ? ` (${advisory.range})` : ''}`,
      );
      blocking += 1;
    }
  }

  if (blocking > 0) {
    console.error(
      `ERROR: ${blocking} high/critical advisory/advisories found; the release evidence gate failed.`,
    );
    return 1;
  }
  console.log('[release-evidence-archive] advisory gate passed: no high or critical advisories.');
  return 0;
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (err) {
    console.error(`ERROR: ${err.message}`);
    return 1;
  }

  if (options.mode === 'verify') {
    const verification = verifyManifest(options.outDir);
    if (!verification.ok) {
      console.error(`ERROR: manifest verification failed for ${options.outDir}`);
      for (const m of verification.mismatches) {
        console.error(`  ${m.file}: ${m.issue}`);
      }
      return 1;
    }
    console.log(
      `[release-evidence-archive] manifest verified: ${verification.checked} artefact(s) OK`,
    );
    return 0;
  }

  if (options.mode === 'gate') {
    return gate(options.outDir);
  }

  const produced = produce(options);
  if (produced !== 0) return produced;
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(main());
}
