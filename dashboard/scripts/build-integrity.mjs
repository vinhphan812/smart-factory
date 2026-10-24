#!/usr/bin/env node
/**
 * scripts/build-integrity.mjs
 *
 * Generates a GNU-compatible `dist/SHA256SUMS` manifest for the production build.
 *
 * Review finding 5 (P1): the previous inline `npm run build:integrity` script used a
 * shell-escaped `\\n`, which risks emitting a literal backslash-n instead of a real
 * newline and therefore breaks `sha256sum -c SHA256SUMS`. This script writes real
 * newline-separated rows and is platform-independent (no shell escaping involved).
 *
 * Usage: node scripts/build-integrity.mjs
 */

import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const distDir = resolve(here, '..', 'dist');

/** Recursively collect every file under `dir`. */
function collectFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectFiles(full));
    } else if (entry.isFile()) {
      out.push(full);
    }
  }
  return out;
}

let files;
try {
  files = collectFiles(distDir);
} catch {
  console.error(`[build:integrity] dist directory not found: ${distDir}`);
  console.error('[build:integrity] run `npm run build` first.');
  process.exit(1);
}

if (files.length === 0) {
  console.error('[build:integrity] dist is empty; nothing to hash.');
  process.exit(1);
}

// Emit POSIX-style relative paths so the manifest is identical on Windows and Linux.
const rows = files
  .map((file) => {
    const digest = createHash('sha256').update(readFileSync(file)).digest('hex');
    const relPath = relative(distDir, file).split(sep).join('/');
    return `${digest}  ${relPath}`;
  })
  .sort((a, b) => a.slice(66).localeCompare(b.slice(66)));

// os.EOL guarantees `sha256sum -c` can parse the file on every platform.
const manifestPath = join(distDir, 'SHA256SUMS');
writeFileSync(manifestPath, `${rows.join('\n')}\n`, 'utf8');

console.log(`[build:integrity] hashed ${files.length} file(s)`);
console.log(`[build:integrity] wrote ${manifestPath}`);