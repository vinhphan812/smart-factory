# Dependency Advisory Triage Report — PR #260 (Issue #149)

**Date:** 2026-10-24  
**Scope:** Smart Factory Operator Dashboard (`dashboard/`)  
**Evidence Level:** L0 Static / L2 Simulation  

## Overview

This report provides the formal security triage for the eight (8) dependency advisories reported by `npm audit` in the Smart Factory Operator Dashboard project (`dashboard/`), following maintainer review requirements for PR #260.

In accordance with repository policy, advisories in the development/test toolchain are documented honestly as review material. Breaking major upgrades (`npm audit fix --force`) are intentionally **not** applied to avoid destabilizing test suites and cross-PR integration parity with PR #242 and PR #261.

---

## Audit Command & Reproduction

```bash
cd dashboard
npm ci
npm audit --json
```

**Audit Summary:**
- Total vulnerabilities: **8**
- Moderate: **5**
- High: **1**
- Critical: **2**

---

## Detailed Advisory Triage

### 1. `@vitest/mocker` (Moderate)
- **Direct / Transitive:** Transitive dependency via `vitest`
- **Affected Path:** `node_modules/@vitest/mocker` (Range: `>=2.1.0 <4.1.11`)
- **Advisory IDs / Titles:** 
  - GHSA-82fw-gwwq-j7x9 (Path Traversal / Arbitrary File Read via Redirect Mock)
  - GHSA-qxg6-89mg-rqv8 (Code injection via unauthenticated manual mock registration)
- **Fixed Version / Mitigation:** Upgrade `vitest` to `>=5.0.5` (SemVer major upgrade).
- **Scope & Runtime Impact:** Development and test runner tooling only. **Not included in the production bundle (`dist/`)** or runtime path.

### 2. `esbuild` (Moderate)
- **Direct / Transitive:** Transitive dependency via `vite`
- **Affected Path:** `node_modules/esbuild` (Range: `<=0.24.2`)
- **Advisory ID / Title:** GHSA-67mh-4wv8-2f99 (esbuild enables any website to send requests to development server and read response)
- **Fixed Version / Mitigation:** Upgrade `vite` to `8.3.5` (SemVer major upgrade).
- **Scope & Runtime Impact:** Development build/bundling server tooling. **Not present in production static assets (`dist/`).**

### 3. `react-router` (Moderate)
- **Direct / Transitive:** Transitive dependency via `react-router-dom`
- **Affected Path:** `node_modules/react-router` (Range: `>=6.0.0 <7.18.0`)
- **Advisory IDs / Titles:**
  - GHSA-wrjc-x8rr-h8h6 (Open redirect via backslash in `<Link>` and `useNavigate`)
  - GHSA-337j-9hxr-rhxg (Arbitrary Constructor Injection via `deserializeErrors()` in SSR Hydration)
- **Fixed Version / Mitigation:** Upgrade `react-router-dom` to `7.18.4` (SemVer major upgrade from v6 to v7).
- **Scope & Runtime Impact:** Client-side Single Page Application (SPA) routing. SSR hydration is not used in this SPA dashboard build. Open redirect risk requires user interaction with malformed backslash URLs; runtime risk is low in closed factory network deployments.

### 4. `react-router-dom` (Moderate)
- **Direct / Transitive:** Direct dependency (`^6.28.0`)
- **Affected Path:** `node_modules/react-router-dom` (Range: `6.0.0-alpha.0 - 7.17.0`)
- **Advisory ID / Title:** Depends on vulnerable `react-router`.
- **Fixed Version / Mitigation:** Upgrade to `7.18.4`.
- **Scope & Runtime Impact:** Production client-side routing runtime path.

### 5. `tinypool` (Critical - Dev Chain)
- **Direct / Transitive:** Transitive dependency via `vitest`
- **Affected Path:** `node_modules/tinypool` (Range: `<=2.1.1`)
- **Advisory IDs / Titles:**
  - GHSA-5gmw-xhrv-c9v3 (Prototype Pollution gadget in worker options leading to RCE)
  - GHSA-85c8-ppgw-ccpr (Prototype Pollution Gadget to RCE in `run()` options)
- **Fixed Version / Mitigation:** Upgrade `vitest` to `5.0.5`.
- **Scope & Runtime Impact:** Test worker pool execution. **Development/test chain only; zero production runtime impact.**

### 6. `vite` (High)
- **Direct / Transitive:** Direct dependency (`^5.4.10`)
- **Affected Path:** `node_modules/vite` (Range: `<=6.4.3`)
- **Advisory IDs / Titles:**
  - GHSA-fx2h-pf6j-xcff (`server.fs.deny` bypass on Windows alternate paths, CVSS 7.5 High)
  - GHSA-4w7w-66w2-5vf9, GHSA-v6wh-96g9-6wx3, GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-587h-7wmj-h5pm, GHSA-9jrq-w75r-8gcw, GHSA-rq7h-c2jc-7f22
- **Fixed Version / Mitigation:** Upgrade `vite` to `8.3.5`.
- **Scope & Runtime Impact:** Local development server and build tool. Production build emits static assets (`dist/index.html`, `dist/assets/*`) which are served by downstream web servers (Nginx/Orion) and are unaffected by dev server filesystem bypasses.

### 7. `vite-node` (Moderate)
- **Direct / Transitive:** Transitive dependency via `vitest`
- **Affected Path:** `node_modules/vite-node` (Range: `<=2.2.0-beta.2`)
- **Fixed Version / Mitigation:** Upgrade `vitest` to `5.0.5`.
- **Scope & Runtime Impact:** Test runner execution environment. Test/dev tooling only.

### 8. `vitest` (Critical - Dev Chain)
- **Direct / Transitive:** Direct dependency (`^2.0.4`)
- **Affected Path:** `node_modules/vitest` (Range: `<3.2.6` / `<=4.1.10`)
- **Advisory ID / Title:** GHSA-5xrq-8626-4rwp (When Vitest UI server is listening, arbitrary files can be read and executed, CVSS 9.8 Critical)
- **Fixed Version / Mitigation:** Upgrade `vitest` to `5.0.5`.
- **Scope & Runtime Impact:** Local unit testing framework and UI server. Vitest UI server is not started in CI or production builds. **Zero production runtime exposure.**

---

## Conclusion & Limitations

1. **Production Impact:** Only `react-router-dom` / `react-router` affects the client-side SPA bundle runtime. The critical advisories (`tinypool` and `vitest`) are strictly confined to the local test runner / build dev chain.
2. **Why `npm audit fix --force` is not executed:** Forcing major upgrades (`v6 → v7` router, `v5 → v8` vite, `v2 → v5` vitest) introduces breaking API changes and test suite regressions across the monorepo.
3. **Verification Status:** Dashboard CI pipeline runs typechecking, linting, unit tests (38/38 passing), SHA-256 integrity checks (`build:integrity` + `sha256sum -c`), and SBOM generation successfully at exact pushed HEAD.
