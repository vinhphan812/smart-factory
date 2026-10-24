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

**This document is report text, and report text is not a permanent clearance.** The triage table
in §2 is a **point-in-time observation** of the npm advisory database as of **2026-10-24** for the
lockfile at the reviewed head; it must be **re-derived at each release** and must never be carried
forward as a standing approval (§7.1). The **durable, SHA-bound** evidence is the archived CI
artefact set described in **§5.3**: for the exact commit being built, the canonical Dashboard CI
workflow produces the raw production and full `npm audit` JSON, the production and development
SBOMs, a `COMMIT` file and a SHA256 manifest, and uploads them as a retained artefact. That
artefact set — not this prose — is what a reviewer re-verifies, with a single documented command.

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
--ignore-scripts` installation of this exact `package.json` + `package-lock.json` pair: **17**
packages on disk, **17** in `npm ls --omit=dev`, **17** in the lockfile closure, **17** in the
runtime SBOM. `immer` (an unmet *optional* peer of `zustand`) is correctly **excluded** — it is
not in the lockfile and is not installed.

A note on the closure count: the pre-remediation closure was **16** packages and the
post-remediation closure is **17**. The net change is entirely within the router dependency tree,
and no new *direct* production dependency was added — `dependencies` still declares exactly the
same six packages. `react-router-dom@6` brought in `@remix-run/router` (16 total);
`react-router-dom@7` drops `@remix-run/router` and adds `cookie` and `set-cookie-parser`
(17 total). The closure was confirmed by physically installing it, not inferred from the lockfile
alone.

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

### 5.0.1 CI verification evidence

The remediation commit `f823cff613079eb2638232549f64c15374d9b0cd` is the commit that carries the
dependency changes, the new tooling and the tests; it is the immutable reference point for the
evidence below. The gate was verified on that exact head:

| Workflow | Event | Result | URL |
| :--- | :--- | :--- | :--- |
| Dashboard CI (`Dashboard Quality & Build Gate`) | pull_request | **success** | https://github.com/vinhphan812/smart-factory/actions/runs/40065045028 |
| Dashboard CI (`Dashboard Quality & Build Gate`) | push | **success** | https://github.com/vinhphan812/smart-factory/actions/runs/40065042065 |
| ADR Lint & Architecture Governance Gate | pull_request | **success** | https://github.com/vinhphan812/smart-factory/actions/runs/40065045019 |
| ADR Lint & Architecture Governance Gate | push | **success** | https://github.com/vinhphan812/smart-factory/actions/runs/40065042062 |
| CI | pull_request | **success** | https://github.com/vinhphan812/smart-factory/actions/runs/40065045033 |

The PR head carries two further **documentation-only** commits on top of `f823cff` (`d309039` and
`d48280c`), which re-run the identical gate without changing any dependency, workflow or build
integrity input. §5.2 records the independently re-verified runs at the reviewed head itself.

The artefacts produced by the exact-head Dashboard CI run were downloaded and inspected:

- `npm-audit-summary.txt` → `found 0 vulnerabilities`; `npm-audit.json` → `total: 0`. The CI scanner
  independently confirms the local `npm audit` result.
- `sha256sum-verification.txt` → all three built files `OK`.
- `dashboard-dist.tar.gz.sha256` → digest verified with `sha256sum -c` → `OK`.
- The CI build artefact's per-file `SHA256SUMS` is **byte-identical** to the locally built
  manifest (`index-Bher25rv.css`, `index-mj-AmJLy.js`, `index.html`), so the build is reproducible
  across the Linux CI runner and the local Windows workstation.
- The CI SBOM contains **280** component entries over **278** distinct package versions, against the
  local full-tree SBOM's **277** entries over **277** distinct versions. The two trees must be
  compared *by distinct version*, because npm 10.9.9 (CI) emits one `components` entry per
  **install path** while npm 12.0.2 (local) collapses same-version duplicates: `eslint-visitor-keys@5.0.1`
  appears three times in the CI SBOM (the `eslint/`, `espree/` and `@typescript-eslint/visitor-keys/`
  nested paths) and once locally, and `eslint-visitor-keys@3.4.3` once in each. At the distinct-version
  level the delta is exactly the four platform-specific **optional** build-toolchain binaries that CI
  adds — `@esbuild/linux-x64`, `@napi-rs/lzma-linux-x64-gnu`, `@rollup/rollup-linux-x64-gnu` and
  `@rollup/rollup-linux-x64-musl` — against the three Windows counterparts the local tree carries
  instead (`@esbuild/win32-x64`, `@rollup/rollup-win32-x64-gnu`, `@rollup/rollup-win32-x64-msvc`).
  Every component in that delta carries CycloneDX `scope: optional` and
  `cdx:npm:package:development: true`, so the delta is confined to the development/build side
  and does not touch the 17-package production closure. No package differs in version, and no
  non-optional package differs in presence between the two trees.
- The CycloneDX `scope` field is **not** comparable across the two trees: npm 10.9.9 labels 266 of
  the CI SBOM's 280 entries `optional`, whereas npm 12.0.2 labels only 6 of the local tree's 277
  entries `optional` (and marks the same `eslint-visitor-keys` versions `required` rather than
  `optional`). Scope labels must therefore not be used to reconcile the two SBOMs; the
  `cdx:npm:package:development` flag and the `name@version` set are the comparable signals. Using
  the `development` flag, the CI tree's **17** non-development components are exactly the **17**
  components of the derived runtime SBOM — an empty symmetric difference — so the runtime partition
  is confirmed independently from the CI artefact itself, not only from the local tree.
- Note the canonical Dashboard CI workflow records the **full-tree** SBOM (`sbom.cdx.json`); the
  separated runtime/full pair and the closure cross-check are produced by
  `npm run release:evidence` (`dashboard/scripts/release-evidence.mjs`), which this change adds.
  The workflow file itself is unchanged and byte-identical to PR #259.

### 5.1 Explicitly NOT verified

These remain **external acceptance gaps** and are *not* claimed as satisfied by this change:

- Deployed reverse-proxy behaviour: HTTPS/TLS termination, HSTS, certificate management.
- Deployed CORS policy and the CSP delivered as an HTTP **response header** at deploy time (the
  in-repo CSP is a `<meta http-equiv>` directive, which cannot carry build-time gateway origins).
- Hardware proof and physical mini-factory validation (L3/L4/L5).
- Live multi-container integration across the gateway, bridge and factory control services.

The unit CI results and build integrity above are **not** evidence of production deployment.

The four gaps above are tracked as open in this repository's own issue tracker (issue #156, OPEN) and
are recorded here as external acceptance gaps. No text in this PR body, in this document, or in the
Dashboard CI workflow claims production deployment from unit CI; the workflow's evidence steps are
explicitly non-blocking advisory/SBOM material, and the PR body's Hardware Status section states
"Dashboard frontend only — no physical hardware connected. Evidence level: L0 Static / L2 Simulation."

### 5.2 Independent re-verification at the reviewed head

The advisory and release-evidence claims in §1, §4 and §5.0.1 were **re-derived independently** at the
reviewed head `d48280cddd116097e29898b3d5838a8548abdc7a` from a fresh checkout of
`origin/feat/issue-149-design-system-nav`, using the committed lockfile and the exact-head CI build
artefacts — not from the author's local machine. The re-derivation reproduced every published figure
and additionally corrected one SBOM counting basis (see §5.0.1).

| Check | Command | Independently observed result |
| :--- | :--- | :--- |
| Deterministic install | `npm ci` | 279 packages added, 280 audited, `found 0 vulnerabilities` |
| Advisory scan (raw JSON) | `npm audit --json` | `"vulnerabilities": {}`; `total: 0` (info/low/moderate/high/critical all 0) |
| Pre-upgrade baseline | `npm audit --json` on the `af5e47f` lockfile | 8 advisories — 2 critical, 1 high, 5 moderate — matching §1 |
| Pre-upgrade dependency-path analysis | `dependency-scope.mjs` `classifyScope` over the `af5e47f` lockfile | `react-router` and `react-router-dom` runtime-reachable; `tinypool`, `vitest`, `vite`, `@vitest/mocker`, `esbuild`, `vite-node` development/build only — matching §2 |
| Release SBOM separation | `npm run release:evidence` | 0 advisories, 17-package production closure, closure agreement consistent; 17 runtime / 260 development-build / 277 total |
| Runtime closure (physical) | `npm ci --omit=dev --ignore-scripts` into a clean directory | **17** packages on disk, matching the runtime SBOM's 17 `name@version` entries exactly (empty set difference) |
| Pre-upgrade closure (physical) | `npm ci --omit=dev --ignore-scripts` on the `af5e47f` lockfile | **16** packages, confirming the 16 → 17 closure change in §4.2 |
| `npm sbom --omit=dev` under-reporting | `npm sbom --omit=dev --sbom-format=cyclonedx` on npm **12.0.2** and npm **10.9.9** | **9** components on both versions; `react` and `react-dom` absent — confirming §4.1 on both npm versions |
| Unit tests | `npm run test` | 62 passed across 6 files (24 in `dependency-scope.test.ts`) |
| Typecheck / lint | `npm run typecheck` / `npm run lint` | exit 0 / 0 errors, 11 warnings — matching §5 |
| Production build + integrity | `npm run build:integrity`; `cd dist && sha256sum -c SHA256SUMS` | 3 files hashed; all three `OK` |
| Build reproducibility | `diff` of local `dist/SHA256SUMS` against the CI artefact's | byte-identical |
| ADR governance gate | `python scripts/check_adrs.py`; `python -m pytest scripts/tests/test_check_adrs.py -q` | 16 ADRs validated; 6 passed |

The exact-head CI runs at `d48280c` were also confirmed **SUCCESS** independently of the `f823cff`
anchor cited above:

| Workflow | Job | Event | Result | URL |
| :--- | :--- | :--- | :--- | :--- |
| ADR Lint & Architecture Governance Gate | `ADR Lint & Impact Check` | pull_request | **success** | https://github.com/vinhphan812/smart-factory/actions/runs/40065612440 |
| ADR Lint & Architecture Governance Gate | `ADR Lint & Impact Check` | push | **success** | https://github.com/vinhphan812/smart-factory/actions/runs/40065608458 |
| Dashboard CI | `Dashboard Quality & Build Gate` | pull_request | **success** | https://github.com/vinhphan812/smart-factory/actions/runs/40065612514 |
| Dashboard CI | `Dashboard Quality & Build Gate` | push | **success** | https://github.com/vinhphan812/smart-factory/actions/runs/40065608435 |
| CI | (repository CI) | pull_request | **success** | https://github.com/vinhphan812/smart-factory/actions/runs/40065612428 |

The exact-head Dashboard CI artefact (`dashboard-dist-0c64d024fea7adacf626d8be13eb8d925624d413`,
downloaded from run `40065612514`) was inspected directly: `npm-audit-summary.txt` reads
`found 0 vulnerabilities`; `npm-audit.json` reports `"total": 0` with an empty `vulnerabilities`
object and an identical `metadata.dependencies` block to the locally reproduced audit
(`prod: 18, dev: 312, optional: 53, peer: 8, total: 329`); `sha256sum-verification.txt` reports all
three built files `OK`; and `dashboard-dist.tar.gz.sha256` matches the recomputed digest of the
downloaded tarball (`8d99f2ca00817eb8850bb177ee6e610d88bf94444b39a34d48e5e7bdf22b6a40`).

**Evidence level of this re-verification: L0 static + L1 reproducible execution + L2 simulation.**
No L3/L4/L5 hardware, deployed-environment or HIL evidence is claimed or produced.

### 5.3 Archived, SHA-bound release evidence (artefact set, not report text)

Everything above is *report text*. Report text is a claim; it is not evidence that survives the
author's machine, the CI runner and the report itself being gone. To make the release claim
**provable from an immutable artefact**, the canonical Dashboard CI workflow now produces an
archived evidence set for the **exact commit being built** and uploads it as a retained CI
artefact.

The archive is produced by `dashboard/scripts/release-evidence-archive.mjs`, which drives the
**existing** generator (`dashboard/scripts/release-evidence.mjs`) rather than re-implementing the
advisory triage or the SBOM generation. The archive contains:

| File | What it is |
| :--- | :--- |
| `COMMIT` | The exact commit SHA the artefacts were produced from. |
| `METADATA.json` | Provenance: commit, workflow run, repository, ref, tool versions, npm audit exit codes. |
| `npm-audit.production.json` | Raw `npm audit --json --omit=dev` output for the production dependency tree. |
| `npm-audit.full.json` | Raw `npm audit --json` output for the full installed tree. |
| `sbom.runtime.cdx.json` | Production SBOM (the runtime closure that ships in the bundle). |
| `sbom.development.cdx.json` | Development/build SBOM (the complement of the runtime closure). |
| `sbom.full.cdx.json` | CycloneDX SBOM of the complete installed tree. |
| `sbom-separation.json` | The generator's separation manifest, with per-SBOM digests. |
| `dependency-scope.json` / `dependency-scope.md` | The advisory disposition, machine- and human-readable. |
| `MANIFEST.json` | SHA256 manifest: filename, SHA256 and byte size of every artefact above. |
| `SHA256SUMS` | GNU-compatible digest list for `sha256sum -c SHA256SUMS`. |

The development SBOM was added by this change: `release-evidence.mjs` previously derived only the
runtime SBOM, so the "development" scope existed in the separation report but had no SBOM of its
own. `deriveDevelopmentSbom()` now derives it as the **complement** of the production closure, using
the same name-and-version matching rule as the runtime derivation, and prunes the CycloneDX
dependency graph so every `dependsOn` edge points at a retained component. On the reviewed tree the
partition is exact: **17 runtime + 260 development/build = 277 total**, with an empty overlap and
no dangling dependency edges.

#### Verifying the archive without trusting the report

`MANIFEST.json` lists the filename, SHA256 digest **and** byte size of every artefact. A reviewer
re-verifies the whole set with one line, run inside the downloaded artefact directory:

```
node -e "const fs=require('fs'),c=require('crypto'),m=JSON.parse(fs.readFileSync('MANIFEST.json','utf8'));let bad=0;for(const a of m.artifacts){const b=fs.readFileSync(a.file);if(c.createHash('sha256').update(b).digest('hex')!==a.sha256||b.length!==a.bytes){console.error('MISMATCH '+a.file);bad++}}if(bad)process.exit(1);console.log('OK: '+m.artifacts.length+' artefacts verified against MANIFEST.json (commit '+m.commit+')')"
```

The command is also embedded in the archive's own `README.md`, so the check travels with the
artefact rather than living only in this document. The SHA256 **of `MANIFEST.json` itself** is
printed in the CI run log and stated in the pull request body; `MANIFEST.json` cannot list itself,
so its digest is the trust anchor and must be compared out of band.

#### The gate is blocking

The `release-evidence` job **fails** the workflow when either archived audit report contains a
**high** or **critical** advisory, and when the SHA256 manifest cannot be produced or verified.
The job is not conditional, not skippable and not `continue-on-error`. The four failure modes were
exercised directly (see §5.4).

#### Retention — stated plainly

GitHub Actions artefact retention for this repository is capped at **90 days**
(`maximum_allowed_days: 90`), and the workflow sets `retention-days: 90` explicitly. **This does
not satisfy an immutable-evidence requirement.** The archive *expires*; it is a 90-day retained
artefact, not a permanent record. The digest of `MANIFEST.json` and the commit SHA are also stated
in the pull request body so that the claim remains checkable after the artefact has expired, but a
reviewer must record that **longer-lived, immutable retention is a residual gap** that GitHub
Actions cannot close. If the release process requires evidence that outlives 90 days, it needs a
retention mechanism outside GitHub Actions — for example a release-attached checksum file, a
signed tag annotation, or an external evidence store.

### 5.4 Failure modes of the archived-evidence gate, exercised

The gate was exercised against real inputs rather than asserted:

| Scenario | Command | Observed result |
| :--- | :--- | :--- |
| Clean tree | `node scripts/release-evidence-archive.mjs --out-dir release-evidence-archive` | exit **0** — 11 artefacts listed, manifest verified |
| One-line re-verification | the `node -e` command above, in the archive directory | exit **0** — `OK: 11 artefacts verified against MANIFEST.json` |
| Tampered artefact | appended one byte to `sbom.runtime.cdx.json`, then re-verified | exit **1** — `MISMATCH sbom.runtime.cdx.json` |
| Tampered manifest | rewrote one digest inside `MANIFEST.json`, then re-verified | exit **1** — `COMMIT: SHA256 mismatch` |
| Missing artefact | deleted `sbom.runtime.cdx.json`, then re-verified | exit **1** — `sbom.runtime.cdx.json: listed artefact is missing` |
| Critical advisory | injected a critical `lodash` advisory into `npm-audit.production.json`, then ran `--gate` | exit **1** — `BLOCKING CRITICAL: lodash (<4.17.21)`; `the release evidence gate failed` |

---

## 6. Cross-PR Reconciliation with PR #259

PR #259 is the canonical owner of the Dashboard CI gate. This change **does not** redesign the
workflow or any check name, and it does **not** create a second Dashboard CI workflow.

| File | Blob on #259 | Blob on #260 (this branch) | Relationship |
| :--- | :--- | :--- | :--- |
| `.github/workflows/dashboard-ci.yml` | `69ee4298` | modified by this change | **Extended** — see below |
| `dashboard/scripts/build-integrity.mjs` | `5ea325ad` | `5ea325ad` | **Byte-identical — unchanged** |
| `dashboard/docs/RELEASE_ARTIFACTS.md` | `27601ff6` | `27601ff6` | **Byte-identical — unchanged** |
| `dashboard/sha256sum-verification.txt` | `024ffe02` | `024ffe02` | **Byte-identical — unchanged** |

### 6.1 The canonical workflow and check names remain #259's

The canonical workflow file is `.github/workflows/dashboard-ci.yml` and the canonical check name is
**`Dashboard Quality & Build Gate`**. Both remain owned by PR #259. This change adds a **separate
job** inside that same workflow file:

| Job | Check name | Owner |
| :--- | :--- | :--- |
| `dashboard-quality` | `Dashboard Quality & Build Gate` | **PR #259** (unchanged) |
| `release-evidence` | `Release Evidence (Archived, SHA-Bound)` | PR #260 (new) |

The two jobs do not compete: they run in parallel, they have different check names, and neither
modifies the other. The canonical gate's steps, its `if:` conditions and its artefact uploads are
untouched. There is exactly **one** Dashboard CI workflow file in the repository; this change adds
no second one.

### 6.2 The add/add conflict this creates, and how to resolve it

`origin/master` does **not** contain `.github/workflows/dashboard-ci.yml`. Both PR #259 and PR #260
*add* that file, so merging the two branches produces a Git **add/add conflict** on it whenever
their contents differ — which they now do, because this change adds the `release-evidence` job.

This is a known, deliberate consequence of the card's instruction to extend the existing workflow
file rather than create a competing one. It is recorded here so the merge owner can resolve it
deliberately instead of discovering it. The resolution is mechanical: keep the **superset** — the
`dashboard-quality` job from PR #259 **plus** the `release-evidence` job from PR #260 — and
confirm that the canonical `Dashboard Quality & Build Gate` job body is byte-identical to
PR #259's. Equivalently, the same `release-evidence` job can be applied to PR #259's branch
before merging, which makes the two blobs identical again and the conflict disappears.

The only file that **both** this change and PR #259 modify is `dashboard/package.json`; it is the
one file both PRs necessarily touch. (This change also modifies `dashboard/package-lock.json`,
`dashboard/.gitignore` and adds new files under `dashboard/scripts/` and `dashboard/src/tests/`,
none of which PR #259 touches — so none of them can conflict.) The `release:evidence` script was
added **at the end** of the `scripts` block rather than adjacent to `build:integrity`, specifically
so that the two PRs' insertions do not land in the same hunk region. A merge test of this branch
against PR #259 confirms `dashboard/package.json` auto-merges cleanly, with both `build:integrity`
and `release:evidence` present in the merged result, and confirms that the merged tree retains
`build-integrity.mjs` at blob `5ea325ad`.

One pre-existing conflict remains between the two branches, in
`.github/workflows/adr-lint.yml`: the two branches contain differing text in the routing-truth-table
comment. This conflict exists between PR #259 and PR #260 **independently of this change** (it was
verified present at the pre-change baseline) and is outside the scope of this advisory remediation.
It is recorded here so the merge owner can resolve it deliberately rather than discover it.

---

## 7. Limitations

1. **The triage table in this document is a point-in-time observation, never a permanent
   clearance.** §2 and §3 describe the advisories as reported by `npm audit` against the npm
   registry advisory database **as of 2026-10-24**, for the lockfile at the reviewed head. It must
   be **re-derived at each release**, from the lockfile actually being released, against the
   advisory database as it stands at that moment. A future advisory affecting any package in the
   runtime closure — or the emergence of a new advisory against a package that was clean today —
   invalidates this table. Nothing in this document authorises shipping a later release on the
   strength of a clean table from 2026-10-24. The blocking `release-evidence` CI job exists to
   make that re-derivation automatic and non-skippable (§5.3), and the archived artefact set is
   the per-release record of what was actually observed.
2. "0 vulnerabilities" means 0 advisories reported by `npm audit` for this lockfile. It is not a
   guarantee that the code is free of defects; it is a statement about the published advisory
   database.
3. The development/build toolchain remains 260 of the 277 installed components. Those packages are
   not in the shipped bundle, but they do execute on developer machines and in CI.
4. **The archived evidence is retained for 90 days, not indefinitely** (§5.3). GitHub Actions
   cannot provide immutable long-lived artefact retention for this repository, so the archive is
   a bounded-retention artefact and the `MANIFEST.json` digest recorded in the pull request body
   is the durable anchor. This is a residual gap, not a satisfied requirement.
5. The deployment-level gaps listed in §5.1 are unchanged by this work and remain open.
