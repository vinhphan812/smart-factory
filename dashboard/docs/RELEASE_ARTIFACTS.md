# Production Release Artifacts & Integrity Manifest

## Overview

This document specifies the production build integrity, Content Security Policy (CSP) enforcement, and SHA-256 artifact provenance for the Smart Factory Operator Dashboard (`dashboard/`).

## 1. Content Security Policy (CSP)

The production dashboard enforces a strict Content Security Policy defined via a `<meta>` directive in `dashboard/index.html`:

```html
<meta
  http-equiv="Content-Security-Policy"
  content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss: http: https:; font-src 'self'; object-src 'none'; base-uri 'self';"
/>
```

### Policy Directives Rationale

| Directive | Value | Purpose |
| :--- | :--- | :--- |
| `default-src` | `'self'` | Disallows loading resources from third-party domains by default. |
| `script-src` | `'self'` | Strictly prohibits external or inline script execution, mitigating Cross-Site Scripting (XSS). |
| `style-src` | `'self' 'unsafe-inline'` | Permits local styles and necessary framework runtime inline styling (e.g., Tailwind CSS / dynamic UI density). |
| `img-src` | `'self' data:` | Allows local image assets and inline SVG / data URIs for UI icons. |
| `connect-src` | `'self' ws: wss: http: https:` | Restricts REST and WebSocket telemetry endpoints to self origin and operator-configured IoT gateways. |
| `font-src` | `'self'` | Enforces locally packaged fonts only; no external font CDNs. |
| `object-src` | `'none'` | Completely disables browser plugins (Flash, Java, ActiveX) to prevent legacy execution vectors. |
| `base-uri` | `'self'` | Restricts document base URL to prevent unauthorized base tag hijacking. |

## 2. Release Artifact Integrity (`SHA256SUMS`)

Production distribution builds must be verifiable and tamper-evident. The dashboard provides an integrity script in `package.json`:

```bash
npm run build:integrity
```

### Build Process
1. Executes `tsc && vite build` to compile TypeScript and generate the production bundle into `dashboard/dist/`.
2. Computes SHA-256 cryptographic hashes for all distribution artifacts recursively (JavaScript chunks, CSS, HTML, SVG assets).
3. Emits `dashboard/dist/SHA256SUMS` in the standard GNU `sha256sum` format:
   ```text
   <sha256_hash>  <relative_path>
   ```

### Verification Procedure

To verify production bundle integrity locally or in staging:

```bash
# Generate production bundle and SHA-256 manifest
npm run build:integrity

# Verify integrity manifest against emitted dist files (Linux / Git Bash)
cd dist
sha256sum -c SHA256SUMS
```

All files must report `OK`.

## 3. CI Pipeline & Immutable Artifact Upload

The GitHub Actions workflow `.github/workflows/dashboard-ci.yml` runs `npm run build:integrity` and archives `dashboard/dist` as an immutable release artifact using `actions/upload-artifact@v4`:

- **Artifact Name**: `dashboard-production-dist`
- **Path**: `dashboard/dist`
- **Retention**: GitHub Actions default retention policy
- **Integrity Guarantee**: Each CI run publishes verified bundle files alongside the `SHA256SUMS` manifest matching the exact commit SHA.

## 4. Acceptance & Verification Boundary

In adherence to `AGENTS.md` and repository verification standards:
- **Evidence Level**: L0 Static / L2 Simulation.
- **Scope**: Frontend code quality, Vite production build, CSP compliance, component rendering, and simulated telemetry state transitions.
- **Physical Boundary**: This dashboard artifact operates against simulated telemetry or local bridge WebSocket feeds. It does **not** constitute L3/L4/L5 hardware acceptance or physical mini-factory validation. Live end-to-end integration across multi-container orchestration is scoped to Issue #156.
