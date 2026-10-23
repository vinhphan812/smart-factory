# Production Release Artifacts & Integrity Manifest

## Overview

This document specifies the production build integrity, Content Security Policy (CSP) enforcement, and SHA-256 artifact provenance for the Smart Factory Operator Dashboard (`dashboard/`).

## 1. Content Security Policy (CSP)

The production dashboard declares a Content Security Policy via a `<meta http-equiv>` directive
in `dashboard/index.html`:

```html
<meta
  http-equiv="Content-Security-Policy"
  content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*; object-src 'none'; base-uri 'self'; frame-ancestors 'none';"
/>
```

### Policy Directives Rationale

| Directive | Value | Purpose |
| :--- | :--- | :--- |
| `default-src` | `'self'` | Disallows loading resources from third-party domains by default. |
| `script-src` | `'self'` | Strictly prohibits external or inline script execution, mitigating Cross-Site Scripting (XSS). |
| `style-src` | `'self' 'unsafe-inline'` | Permits local styles and necessary framework runtime inline styling (e.g., Tailwind CSS / dynamic UI density). |
| `img-src` | `'self' data:` | Allows local image assets and inline SVG / data URIs for UI icons. |
| `connect-src` | `'self'` + loopback origins | Allows same-origin requests plus `localhost` / `127.0.0.1` over HTTP and WS, which covers the local development gateway. Arbitrary internet destinations are **not** permitted. |
| `font-src` | `'self'` | Enforces locally packaged fonts only; no external font CDNs. |
| `object-src` | `'none'` | Completely disables browser plugins (Flash, Java, ActiveX) to prevent legacy execution vectors. |
| `base-uri` | `'self'` | Restricts document base URL to prevent unauthorized base tag hijacking. |
| `frame-ancestors` | `'none'` | Prevents the dashboard from being embedded in a foreign page (clickjacking). |

### Honest Scope Statement

An earlier revision used `connect-src 'self' ws: wss: http: https:`, which is **not** an endpoint
restriction: the `http:` / `https:` / `ws:` / `wss:` schemes permit connections to *any* host on
those schemes, so the policy did not constrain where data could be sent. The tightened policy
above removes those wildcard schemes.

What this CSP does **not** do:

- It does not pin the dashboard to one specific remote gateway host. A static HTML `meta` CSP
  cannot reference build-time environment values, so a deployment that must talk to a remote
  gateway needs one of:
  - a reverse proxy that serves the gateway under the dashboard's own origin (recommended — keeps
    `connect-src 'self'` sufficient), or
  - the CSP delivered as an **HTTP response header** generated at deploy time with the approved
    gateway origins substituted in.

Deployment-time CSP header injection, HTTPS/WSS enforcement and reverse-proxy topology are
tracked in issue #156. Until that exists, this repository's policy intentionally allows loopback
only, so an operator cannot silently exfiltrate telemetry to an unintended host from the shipped
build.

## 2. Release Artifact Integrity (`SHA256SUMS`)

Production distribution builds must be verifiable and tamper-evident.

### Build Process

`npm run build:integrity` performs two steps:

1. Executes `tsc && vite build` to compile TypeScript and generate the production bundle into `dashboard/dist/`.
2. Runs `node scripts/build-integrity.mjs`, which computes SHA-256 hashes for every file under
   `dashboard/dist/` and writes `dashboard/dist/SHA256SUMS`.

The hashing step lives in a standalone ES module rather than an inline `node -e` expression
because a shell-escaped `\\n` inside an npm script can emit a literal backslash-n instead of a
real newline, which silently breaks `sha256sum -c`. The script also emits POSIX-style relative
paths (`assets/index-xxx.js`) so the manifest is byte-identical on Windows and Linux.

The manifest is standard GNU `sha256sum` format:

```text
<sha256_hash>  <relative_path>
```

### Verification Procedure

```bash
# Generate production bundle and SHA-256 manifest
npm run build:integrity

# Verify integrity manifest against emitted dist files
cd dist
sha256sum -c SHA256SUMS   # every line must report OK
```

## 3. CI Pipeline & Immutable Artifact Upload

The GitHub Actions workflow `.github/workflows/dashboard-ci.yml` is the single canonical
implementation of the Dashboard quality gate (owned by PR #259 / issue #156 and carried
byte-identically by PR #260 so the two open branches merge without an add/add conflict).

Current gate sequence:

1. `npm ci` — deterministic install from the committed lockfile (Node.js 22).
2. Dependency advisory assessment — `npm audit --json` and a critical-severity summary, recorded
   as **non-blocking** evidence. The lockfile still carries transitive advisories in the
   `vitest` / `tinypool` dev chain; `npm audit fix --force` would apply a breaking major upgrade,
   so the recorded output is review material, not a claim of a clean audit.
3. CycloneDX SBOM generation — non-blocking evidence.
4. `npm run typecheck`, `npm run lint`, `npm run test`.
5. `npm run build` — production Vite bundle.
6. Deterministic packaging — a reproducible `tar` archive (`dashboard-dist.tar.gz`) plus its
   SHA-256 digest (`dashboard-dist.tar.gz.sha256`).
7. `actions/upload-artifact@v4` uploads `dashboard-dist-${{ github.sha }}` containing the archive,
   its digest, the audit reports and the SBOM, with a 14-day retention.

**Note on `build:integrity`:** the per-file `dist/SHA256SUMS` manifest is produced by
`npm run build:integrity` locally. The CI gate packages the `dist` tree into a tarball and
digests the tarball instead, because the tarball is the artifact that is actually released and
transported. Both integrity mechanisms are recorded; the authoritative digest for a given CI run
is `dashboard-dist.tar.gz.sha256`.

## 4. Acceptance & Verification Boundary

In adherence to `AGENTS.md` and repository verification standards:
- **Evidence Level**: L0 Static / L2 Simulation.
- **Scope**: Frontend code quality, Vite production build, CSP compliance, component rendering, and simulated telemetry state transitions.
- **Physical Boundary**: This dashboard artifact operates against simulated telemetry or local bridge WebSocket feeds. It does **not** constitute L3/L4/L5 hardware acceptance or physical mini-factory validation. Live end-to-end integration across multi-container orchestration is scoped to Issue #156.
