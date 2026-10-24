# Dependency Advisory Triage & Disposition — PR #260 (Issue #149)

**Date:** 2026-10-24  
**Scope:** Smart Factory Operator Dashboard (`dashboard/`)  
**Evidence Level:** L0 Static / L1 Reproducible Execution / L2 Simulation  
**PR:** [#260](https://github.com/vinhphan812/smart-factory/pull/260) — branch `feat/issue-149-design-system-nav`  
**Status:** **All eight (8) original advisories remediated. Current audit: 0 vulnerabilities.**

## Overview

This document is the formal, closed disposition of the eight (8) dependency advisories reported by
`npm audit` in the Smart Factory Operator Dashboard (`dashboard/`), as required by Maintainer Review
Iteration #4 (comment `6378131836`).

The previous revision of this report documented the advisories but left them open, on the stated
ground that remediation would require breaking major upgrades. That reasoning has been **superseded
by evidence**: the required upgrades have been applied and fully validated, so the advisories are
closed rather than merely described.

Two things are recorded here, and the distinction matters:

1. **The original advisory disposition** — for each of the eight advisories, the concrete install
   path from a declared dependency down to the vulnerable package, the scope of that path
   (runtime vs development/build), whether the package was in the production dependency closure,
   and the fix that was applied. This is reproduced from the *pre-upgrade* lockfile and the
   *pre-upgrade* `npm audit` output using the same committed analyser
   (`dashboard/scripts/dependency-scope.mjs`) that produced the current evidence, so the paths
   below are computed, not asserted.
2. **The remediation and its verification** — the exact version changes, the separated release
   SBOM evidence, and the local validation output that was actually executed.

---

## 1. Audit Command & Reproduction

```bash
cd dashboard
npm ci                 # Node 22, npm ci from the committed lockfile
npm audit --json       # machine-readable advisory report
npm audit              # human-readable summary
```

**Pre-upgrade baseline (at reviewed HEAD `af5e47f5`):**

| Metric | Value |
| :--- | :--- |
| Total vulnerabilities | **8** |
| Critical | **2** |
| High | **1** |
| Moderate | **5** |
| Production closure packages | 16 |

**Post-remediation (current lockfile):**

| Metric | Value |
| :--- | :--- |
| Total vulnerabilities | **0** |
| Critical | 0 |
| High | 0 |
| Moderate | 0 |
| Production closure packages | 17 |

Actual output of `npm audit` at the remediated lockfile:

```text
found 0 vulnerabilities
```

---

## 2. Original Advisory Disposition (reproduced from the pre-upgrade lockfile)

Each path below is resolved by breadth-first search over the committed lockfile, walking the
`node_modules` chain exactly as Node's resolution algorithm does, including peer-dependency edges
(npm 7+ materialises peers into the installed tree, so a package that is only ever a peer of a
runtime package is still installed for the runtime).

**Scope vocabulary**

| Scope | Meaning |
| :--- | :--- |
| `runtime` | Reachable through `dependencies`; ships in the production bundle. |
| `development/build` | Reachable only through `devDependencies`; test/build toolchain; not present in the production bundle. |
| `production closure` | The set of packages `npm ci --omit=dev` actually installs — the authoritative "can this ship?" signal. |

### 2.1 `tinypool` — Critical (transitive, development/build)

| Field | Value |
| :--- | :--- |
| Installed version | `1.1.1` at `node_modules/tinypool` |
| Vulnerable range | `<=2.1.1` |
| Install path | `vitest -> tinypool` |
| Scope | `development/build` |
| In production closure | **No** |
| Runtime reachable | **No** |
| Advisories | GHSA-5gmw-xhrv-c9v3, GHSA-85c8-ppgw-ccpr (prototype pollution gadget → RCE in worker options) |
| Fix applied | Removed — `vitest@4.1.12` no longer depends on `tinypool` |

### 2.2 `vitest` — Critical (direct, development/build)

| Field | Value |
| :--- | :--- |
| Installed version | `2.1.9` at `node_modules/vitest` |
| Vulnerable range | `<=4.1.10` |
| Install path | `vitest` (direct `devDependency`) |
| Scope | `development/build` |
| In production closure | **No** |
| Runtime reachable | **No** |
| Advisory | GHSA-5xrq-8626-4rwp (Vitest UI server: arbitrary file read and execute, CVSS 9.8) |
| Fix applied | Upgraded `vitest` `^2.0.4` → `^4.1.12` |

### 2.3 `vite` — High (direct, development/build)

| Field | Value |
| :--- | :--- |
| Installed version | `5.4.21` at `node_modules/vite` |
| Vulnerable range | `<=6.4.3` |
| Install paths | `vite`; `@vitejs/plugin-react -> vite`; `vitest -> vite`; `vitest -> @vitest/mocker -> vite`; `vitest -> vite-node -> vite` |
| Scope | `development/build` |
| In production closure | **No** |
| Runtime reachable | **No** |
| Advisories | GHSA-fx2h-pf6j-xcff (`server.fs.deny` bypass on Windows alternate paths, CVSS 7.5); GHSA-587h-7wmj-h5pm; plus 6 moderate `launch-editor` / dev-server advisories |
| Fix applied | Upgraded `vite` `^5.4.10` → `^6.4.5` (above the vulnerable range, without the `v8` major that `npm audit fix --force` proposed) |

### 2.4 `react-router` — Moderate (transitive, **runtime**)

| Field | Value |
| :--- | :--- |
| Installed version | `6.30.6` at `node_modules/react-router` |
| Vulnerable range | `6.0.0 - 7.17.0` |
| Install path | `react-router-dom -> react-router` |
| Scope | **`runtime`** |
| In production closure | **Yes** |
| Runtime reachable | **Yes** |
| Advisories | GHSA-wrjc-x8rr-h8h6 (open redirect via backslash in `<Link>` / `useNavigate`); GHSA-337j-9hxr-rhxg (arbitrary constructor injection via `deserializeErrors()` in SSR hydration) |
| Fix applied | Upgraded `react-router-dom` `^6.28.0` → `^7.18.4`, which pulls `react-router` above the vulnerable range |

### 2.5 `react-router-dom` — Moderate (direct, **runtime**)

| Field | Value |
| :--- | :--- |
| Installed version | `6.30.6` at `node_modules/react-router-dom` |
| Vulnerable range | `6.0.0-alpha.0 - 7.17.0` |
| Install path | `react-router-dom` (direct `dependency`) |
| Scope | **`runtime`** |
| In production closure | **Yes** |
| Runtime reachable | **Yes** |
| Fix applied | Upgraded `react-router-dom` `^6.28.0` → `^7.18.4` |

> **This is the material finding.** Two of the eight advisories — `react-router` and
> `react-router-dom` — were genuinely reachable from the production bundle. They are the only two
> advisories in the original set that shipped to users. The previous revision of this report noted
> that "only `react-router-dom` / `react-router` affects the client-side SPA bundle runtime"; that
> observation is correct and is why the router upgrade was mandatory rather than optional.

### 2.6 `@vitest/mocker` — Moderate (transitive, development/build)

| Field | Value |
| :--- | :--- |
| Installed version | `2.1.9` at `node_modules/@vitest/mocker` |
| Vulnerable range | `<=4.1.11` |
| Install path | `vitest -> @vitest/mocker` |
| Scope | `development/build` |
| In production closure | **No** |
| Fix applied | Remediated by the `vitest` upgrade — `4.1.12` is present in the remediated tree, above the `<=4.1.11` vulnerable range |

### 2.7 `esbuild` — Moderate (transitive, development/build)

| Field | Value |
| :--- | :--- |
| Installed version | `0.21.5` at `node_modules/esbuild` |
| Vulnerable range | `<=0.24.2` |
| Install paths | `vite -> esbuild`; `@vitejs/plugin-react -> vite -> esbuild`; `vitest -> @vitest/mocker -> vite -> esbuild` |
| Scope | `development/build` |
| In production closure | **No** |
| Advisory | GHSA-67mh-4wv8-2f99 (dev server allows any website to send requests and read the response) |
| Fix applied | Removed from the vulnerable range by the `vite@6.4.5` upgrade |

### 2.8 `vite-node` — Moderate (transitive, development/build)

| Field | Value |
| :--- | :--- |
| Installed version | `2.1.9` at `node_modules/vite-node` |
| Vulnerable range | `<=2.2.0-beta.2` |
| Install path | `vitest -> vite-node` |
| Scope | `development/build` |
| In production closure | **No** |
| Fix applied | Removed — not present in the remediated tree |

### 2.9 Disposition summary

| Package | Severity | Scope | Runtime reachable | Closure | Disposition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `tinypool` | Critical | development/build | No | No | **Remediated** — removed |
| `vitest` | Critical | development/build | No | No | **Remediated** — `4.1.12` |
| `vite` | High | development/build | No | No | **Remediated** — `6.4.5` |
| `react-router` | Moderate | **runtime** | **Yes** | **Yes** | **Remediated** — `7.18.4` (via `react-router-dom`) |
| `react-router-dom` | Moderate | **runtime** | **Yes** | **Yes** | **Remediated** — `7.18.4` |
| `@vitest/mocker` | Moderate | development/build | No | No | **Remediated** — `4.1.12` |
| `esbuild` | Moderate | development/build | No | No | **Remediated** — above vulnerable range |
| `vite-node` | Moderate | development/build | No | No | **Remediated** — removed |

---

## 3. Remediation Applied

Only versions that are compatible and validated were adopted. The major versions that
`npm audit fix --force` proposed (`vitest@5`, `vite@8`) were **not** applied; the specific versions
below clear every advisory while preserving the existing API surface.

| Package | Before | After | Rationale |
| :--- | :--- | :--- | :--- |
| `vitest` | `^2.0.4` | `^4.1.12` | Clears the critical `vitest` and `@vitest/mocker` advisories; `tinypool` and `vite-node` are no longer in the tree. |
| `vite` | `^5.4.10` | `^6.4.5` | Above the `<=6.4.3` vulnerable range without the `v8` major. Also lifts `esbuild` out of the `<=0.24.2` range. |
| `@vitejs/plugin-react` | `^4.3.3` | `^4.6.0` | Peer-compatible with `vite@6`. |
| `react-router-dom` | `^6.28.0` | `^7.18.4` | The only remediation that clears the two **runtime-reachable** advisories. |

### 3.1 React Router v6 → v7 compatibility assessment

The router upgrade is the only one that crosses a major version, so it was assessed explicitly
rather than assumed:

- No v6-only API was found in use. The codebase was checked for `useOutlet`, `unstable_*`,
  `matchPath`, `generatePath`, `useMatch`, `useHref`, `useResolvedPath`, `useInRouterContext`,
  `useNavigationType`, `createSearchParams`, `RouterProvider`, `createMemoryRouter`,
  `createBrowserRouter`, `ServerRouter` and `StaticRouter` — **none** are used.
- `dashboard/src/app/routes.tsx` uses plain `<Route element>` path patterns, which are valid
  unchanged in v7.
- `react-router-dom@7.18.4` retains the `BrowserRouter` / `Routes` / `Route` / `Link` / `NavLink`
  / `useNavigate` surface the dashboard uses.
- The API change relevant to a v7 upgrade is the move to `react-router` (framework mode) packages
  for data APIs; this dashboard does not use those.

### 3.2 Time-bound remediation / owner decision

| Item | Decision |
| :--- | :--- |
| **Owner** | `@dev-frontend` (PR #260 author) for the dependency change; `@coordinator` for merge sequencing with PR #259. |
| **Remediation deadline** | **Completed 2026-10-24** — within this PR, ahead of the review deadline. |
| **Residual risk** | None outstanding at the advisory level: `npm audit` reports 0 vulnerabilities against the registry advisory database. |
| **Re-audit trigger** | Any future `npm ci` that changes `dashboard/package-lock.json` must re-run `npm run release:evidence`; the generator fails closed if the production closure and the lockfile disagree. |
| **Residual operational risk (not an advisory)** | The advisories are closed; the deployment-level gaps in §5 remain open and are *not* addressed by this change. |

---

## 4. Separated Release SBOM Evidence

Release evidence is generated by `dashboard/scripts/release-evidence.mjs` (`npm run release:evidence`).
It writes five artefacts to `dashboard/release-evidence/` (a git-ignored directory — these are
regenerated release material, not source):

| Artefact | Contents |
| :--- | :--- |
| `dependency-scope.json` | Machine-readable advisory disposition: severity, install paths, scope, production-closure membership, available fix. |
| `dependency-scope.md` | The same disposition as a reviewable table. |
| `sbom.runtime.cdx.json` | CycloneDX SBOM of the **production closure only** — what `npm ci --omit=dev` installs, i.e. what can ship. |
| `sbom.full.cdx.json` | CycloneDX SBOM of the **full installed tree** (runtime + development/build toolchain). |
| `sbom-separation.json` | Separation manifest: every component classified, counts on both sides, SHA-256 of each SBOM, and the closure agreement record. |

### 4.1 Why the runtime SBOM is derived rather than taken from `npm sbom --omit=dev`

`npm sbom --omit=dev` **silently omits packages that are genuinely installed**. Measured on this
project, it reported **9** components while `npm ci --omit=dev` physically installs **17** —
`react` and `react-dom` were missing from the runtime SBOM despite being present on disk and
reachable in the shipped bundle. The behaviour was reproduced on npm `10.9.9` **and** npm `12.0.2`,
so it is not a version-specific quirk.

An SBOM that under-reports the shipped dependency set is worse than no SBOM, because it is
reviewable evidence that looks authoritative. The generator therefore:

1. derives the production closure from the lockfile **and** cross-checks it against
   `npm ls --omit=dev --all --json`;
2. generates the **full** CycloneDX SBOM and filters it against that verified closure to produce
   the runtime SBOM;
3. **fails** (non-zero exit) if the two closure sources disagree on package set or versions, or if
   the classification cross-check reports any mismatch.

### 4.2 Separation result

| Metric | Value |
| :--- | :--- |
| Runtime (production closure) components | **17** |
| Development/build components | **260** |
| Full tree components | **277** |
| Closure agreement (npm `ls` vs lockfile) | consistent |
| Classification cross-check | consistent |

The runtime component set was independently confirmed against a physical `npm ci --omit=dev
--ignore-scripts` installation: **17** packages on disk, **17** in `npm ls --omit=dev`, **17** in
the lockfile closure, **17** in the runtime SBOM. `immer` (an unmet *optional* peer of `zustand`)
is correctly **excluded** — it is not in the lockfile and is not installed.

The 17 runtime packages are: `@kurkle/color`, `@types/prop-types`, `@types/react`, `chart.js`,
`cookie`, `csstype`, `js-tokens`, `loose-envify`, `react`, `react-chartjs-2`, `react-dom`,
`react-router`, `react-router-dom`, `scheduler`, `set-cookie-parser`, `use-sync-external-store`,
`zustand`.

### 4.3 Separation guarantees

- The runtime SBOM is matched on **name and version**, so a package present at two versions in the
  tree cannot leak the wrong version into the release SBOM.
- The CycloneDX `dependencies` graph is pruned so that every `dependsOn` edge resolves to a
  component present in the same document.
- Each SBOM's SHA-256 is recorded in `sbom-separation.json`, making the pair tamper-evident.

---

## 5. Verification Actually Executed

All commands below were run locally against the remediated tree. **Evidence level: L0 static
analysis + L1 reproducible execution + L2 simulation.** No L3/L4/L5 hardware or deployed
environment was exercised.

| Check | Command | Result |
| :--- | :--- | :--- |
| Deterministic install | `npm ci` | **PASS** |
| Advisory scan | `npm audit` | **PASS** — `found 0 vulnerabilities` |
| Dependency-path analysis | `node scripts/release-evidence.mjs` | **PASS** — 0 advisories, 17-package closure, closure agreement consistent |
| Release SBOM separation | (same generator) | **PASS** — 17 runtime / 260 dev-build / 277 total |
| TypeScript typecheck | `npm run typecheck` | **PASS** — exit 0 |
| ESLint | `npm run lint` | **PASS** — 0 errors, 11 pre-existing warnings (unchanged from baseline) |
| Unit tests | `npm run test` | **PASS** — 62/62 (38 pre-existing + 24 new) |
| Production build + integrity manifest | `npm run build:integrity` | **PASS** |
| Integrity manifest verification | `cd dist && sha256sum -c SHA256SUMS` | **PASS** — all files `OK` |
| ADR governance gate | `python scripts/check_adrs.py` | **PASS** — 16 ADRs validated |
| ADR linter test suite | `python -m pytest scripts/tests/test_check_adrs.py -q` | **PASS** — 6/6 |

### 5.1 Explicitly NOT verified

These remain **external acceptance gaps** and are *not* claimed as satisfied by this change:

- Deployed reverse-proxy behaviour: HTTPS/TLS termination, HSTS, certificate management.
- Deployed CORS policy and the CSP delivered as an HTTP **response header** at deploy time (the
  in-repo CSP is a `<meta http-equiv>` directive, which cannot carry build-time gateway origins).
- Hardware proof and physical mini-factory validation (L3/L4/L5).
- Live multi-container integration across the gateway, bridge and factory control services.

The unit CI results and build integrity above are **not** evidence of production deployment.

---

## 6. Cross-PR Reconciliation with PR #259

PR #259 is the canonical owner of the Dashboard CI gate. This change **does not** redesign the
workflow or any check name.

| File | Blob on #259 | Blob on #260 (this branch) | Relationship |
| :--- | :--- | :--- | :--- |
| `.github/workflows/dashboard-ci.yml` | `69ee4298` | `69ee4298` | **Byte-identical — unchanged** |
| `dashboard/scripts/build-integrity.mjs` | `5ea325ad` | `5ea325ad` | **Byte-identical — unchanged** |
| `dashboard/docs/RELEASE_ARTIFACTS.md` | `27601ff6` | `27601ff6` | **Byte-identical — unchanged** |
| `dashboard/sha256sum-verification.txt` | `024ffe02` | `024ffe02` | **Byte-identical — unchanged** |

The only shared file modified by this change is `dashboard/package.json` (and its lockfile), which
both PRs necessarily touch. The `release:evidence` script was added **at the end** of the `scripts`
block rather than adjacent to `build:integrity`, specifically so that the two PRs' insertions do
not land in the same hunk region. A merge test of this branch against PR #259 confirms
`dashboard/package.json` auto-merges cleanly, with both `build:integrity` and `release:evidence`
present in the merged result.

One pre-existing conflict remains between the two branches, in
`.github/workflows/adr-lint.yml`: the two branches contain differing text in the routing-truth-table
comment. This conflict exists between PR #259 and PR #260 **independently of this change** (it was
verified present at the pre-change baseline) and is outside the scope of this advisory remediation.
It is recorded here so the merge owner can resolve it deliberately rather than discover it.

---

## 7. Limitations

1. The advisory disposition is a **point-in-time** assessment against the npm registry advisory
   database as of 2026-10-24. A future advisory affecting any package in the runtime closure would
   require re-triage.
2. "0 vulnerabilities" means 0 advisories reported by `npm audit` for this lockfile. It is not a
   guarantee that the code is free of defects; it is a statement about the published advisory
   database.
3. The development/build toolchain remains 260 of the 277 installed components. Those packages are
   not in the shipped bundle, but they do execute on developer machines and in CI.
4. The deployment-level gaps listed in §5.1 are unchanged by this work and remain open.
