# Merge-Order Plan — PR #260 and PR #259

**Date:** 2026-10-24
**Scope:** merge-order plan, combined-tree check verification and release-gate statement for
PR [#260](https://github.com/vinhphan812/smart-factory/pull/260) (`feat/issue-149-design-system-nav`)
and PR [#259](https://github.com/vinhphan812/smart-factory/pull/259)
(`smart-factory/t_7538eb48-ci-add-dashboard-ci-workflow-build-lint`).
**Trigger:** Maintainer Review Iteration #7, comment `6383072133`, findings F3, F4, F5 (all PARTIAL).
**Evidence level:** L0 static (git object / blob inspection, GitHub API) + L1 local `npm audit`
execution. **No production, browser or HIL evidence is claimed anywhere in this document.**

**Reviewed HEADs**

| PR | Branch | HEAD | Blob of `.github/workflows/dashboard-ci.yml` |
|---|---|---|---|
| #259 | `smart-factory/t_7538eb48-ci-add-dashboard-ci-workflow-build-lint` | `8332f01cd25f1a2ab2ddc4b5d3371803be4c6c12` | `69ee4298aa3f2ea6ad71e40ea3961014bed2bbfb` |
| #260 | `feat/issue-149-design-system-nav` | `0c422e867993fcf046b2c21db0283cdae4480f57` | `69ee4298aa3f2ea6ad71e40ea3961014bed2bbfb` |

Common merge base of both branches: `3d7d7ca5e8413566637a50e83c1e5fbe2722977f`.

**This document is documentation and verification only.** It does not merge, rebase, force-push or
close anything, and it does not create a second Dashboard CI workflow.

---

## 1. Actual file overlap between the two branches

Computed with `git diff --name-only <merge-base> <branch>` for each branch and intersected. The
merge base is identical for both branches (`3d7d7ca5`), so this is a true three-way overlap set.

| File | #259 | #260 | Combined-tree outcome |
|---|---|---|---|
| `.github/workflows/dashboard-ci.yml` | added | added | **Byte-identical** on both sides (blob `69ee4298aa3f2ea6ad71e40ea3961014bed2bbfb`). No add/add conflict, no duplicate workflow. |
| `.github/workflows/adr-lint.yml` | edited | edited | **Content conflict** — see §2.3. The only conflicted file in the merge. |
| `.github/workflows/bridge-ci.yml` | edited | untouched | Carried from #259 unchanged. |
| `.github/workflows/gateway-ci.yml` | edited | untouched | Carried from #259 unchanged. |
| `.github/workflows/factory-control-ci.yml` | edited | untouched | Carried from #259 unchanged. |
| `dashboard/package.json` | edited | edited | Auto-merges cleanly; result is byte-identical to #260's version (blob `56b2d9826b854480df616088f4826c28b0296be5`) in **both** merge orders. |
| `dashboard/package-lock.json` | untouched | edited | Result is #260's lockfile (blob `9efb1268d68ac1d97f0bbba4a6d3553e65d36938`) in **both** merge orders. |
| `dashboard/scripts/build-integrity.mjs` | added | edited | **Byte-identical** on both sides (blob `5ea325addbc8b6cb0e30df0283863a975ecda40c`). |
| `dashboard/sha256sum-verification.txt` | added | edited | **Byte-identical** on both sides (blob `024ffe02e1e6e6fefa595e6fd9c790b8bbb687fb`). |
| `dashboard/docs/RELEASE_ARTIFACTS.md` | added | edited | **Byte-identical** on both sides (blob `27601ff63ce09d3dd730f2c528994526acfd27fe`). |
| `docs/research/manifest.md` | edited | untouched | Carried from #259; records the Dashboard CI evidence. |

Note on `dashboard/package-lock.json`: **#259 does not modify the lockfile at all.** Its lockfile
blob (`cfac543e62540a4057890d42181017b6114cd700`) is byte-identical to the merge base's lockfile,
because #259's `dashboard/package.json` change adds only a `build:integrity` *script* entry and no
dependency. The advisory remediation exists **only** on #260.

Two independent merge-tree simulations were run (read-only; neither created a commit):

```
$ git merge-tree --write-tree origin/feat/issue-149-design-system-nav \
                                origin/smart-factory/t_7538eb48-ci-add-dashboard-ci-workflow-build-lint
75000ab5fcf743e6d76e07eb373a594a9a69c3a8
100644 993cc04405a792bbe8d32b6cb9df6c632a7ea74e 1   .github/workflows/adr-lint.yml
100644 bca7030603e6f19701e239d5f9bfa51908aa330e 2   .github/workflows/adr-lint.yml
100644 7275be2aca3c1771e1af7267f6185b4acd34b991 3   .github/workflows/adr-lint.yml
Auto-merging .github/workflows/adr-lint.yml
CONFLICT (content): Merge conflict in .github/workflows/adr-lint.yml
Auto-merging dashboard/package.json

$ git merge-tree --write-tree origin/smart-factory/t_7538eb48-ci-add-dashboard-ci-workflow-build-lint \
                                origin/feat/issue-149-design-system-nav
1b73592131795fefde672ef3d74c4c4a8ff1b01b
... CONFLICT (content): Merge conflict in .github/workflows/adr-lint.yml
Auto-merging dashboard/package.json
```

Resulting blob identity in the merged trees (both orders produce the same values):

```
merged dashboard-ci.yml      : 69ee4298aa3f2ea6ad71e40ea3961014bed2bbfb  (= both branches, unchanged)
merged dashboard/package.json: 56b2d9826b854480df616088f4826c28b0296be5  (= #260's version)
merged dashboard/package-lock.json : 9efb1268d68ac1d97f0bbba4a6d3553e65d36938 (= #260's lockfile)
merged build-integrity.mjs   : 5ea325addbc8b6cb0e30df0283863a975ecda40c  (= both branches)
merged RELEASE_ARTIFACTS.md  : 27601ff63ce09d3dd730f2c528994526acfd27fe  (= both branches)
```

**Conclusion from the merge simulation: the merge is content-neutral for the Dashboard gate itself.**
The order of the two merges does not change the final bytes of `dashboard-ci.yml`,
`package.json`, `package-lock.json`, `build-integrity.mjs` or `RELEASE_ARTIFACTS.md`. Only
`.github/workflows/adr-lint.yml` needs a human conflict resolution, and it conflicts in *both*
orders.

---

## 2. Merge order

### 2.1 Recommendation — merge #260 first, then #259

| Step | Action | Why |
|---|---|---|
| 1 | Merge PR **#260** into `master` | #260 carries the newer dependency baseline: `package-lock.json` blob `9efb1268…` with **0 advisories** (verified locally, §5), `react-router-dom ^7.18.4`, `vite ^6.4.5`, `vitest ^4.1.12`. It also already contains byte-identical copies of #259's `dashboard-ci.yml`, `build-integrity.mjs`, `sha256sum-verification.txt` and `RELEASE_ARTIFACTS.md`. |
| 2 | Merge PR **#259** into `master` | #259 then contributes no new workflow content — only the `adr-lint.yml` routing comment, the three sibling-workflow routing comments, `docs/research/manifest.md` and the `build:integrity` script entry (already present via #260). The canonical Dashboard CI blob is unchanged by this merge. |
| 3 | Refresh SBOM + `npm audit` on the **combined** `master` tree | §4. This is the "then SBOM and npm audit refreshed" step required by finding F3. |

**Why #260 first rather than #259 first.** The merge result is byte-identical in either order
(§1), so the choice is not about content conflicts. It is about the *intermediate* `master` state
that the gate itself observes:

- If **#259 lands first**, `master` gains the Dashboard CI gate while still carrying the
  un-remediated lockfile (`cfac543e…`, 8 advisories, §5). The gate's advisory step is
  deliberately non-blocking (`|| true`, §3), so that intermediate `master` run would be **green**
  while recording the vulnerable advisory state in its artifacts. The advisory refresh would then
  have to be repeated after #260 lands.
- If **#260 lands first**, `master` already carries the remediated lockfile *before* the gate is
  installed. The first `master` runs of the gate therefore record the remediated advisory state
  directly, and the refresh in §4 is performed exactly once, on the final tree.

If #259 must be merged first for another reason, the §4 command list is still mandatory afterwards,
and the intermediate `master` advisory evidence must be treated as superseded.

### 2.2 Expected final combined `.github/workflows/dashboard-ci.yml`

After the merge the file must be **byte-identical to its current content** — blob
`69ee4298aa3f2ea6ad71e40ea3961014bed2bbfb`, unchanged by the merge. It is the only Dashboard CI
workflow in the combined tree:

```
$ git ls-tree -r --name-only <merged-tree> .github/
.github/ISSUE_TEMPLATE/bug_report.md
.github/ISSUE_TEMPLATE/feature_request.md
.github/ISSUE_TEMPLATE/hardware_validation.md
.github/ISSUE_TEMPLATE/research_task.md
.github/pull_request_template.md
.github/workflows/adr-lint.yml
.github/workflows/bridge-ci.yml
.github/workflows/dashboard-ci.yml
.github/workflows/factory-control-ci.yml
.github/workflows/gateway-ci.yml
```

There is no second Dashboard workflow file, and the repository's registered workflow list contains
exactly one Dashboard CI entry:

```
$ gh api repos/vinhphan812/smart-factory/actions/workflows \
    --jq '.workflows[] | "\(.id)\t\(.name)\t\(.path)\t\(.state)"'
384253449   ADR Lint & Architecture Governance Gate   .github/workflows/adr-lint.yml          active
382237693   CI                                        .github/workflows/bridge-ci.yml         active
392572940   Dashboard CI                              .github/workflows/dashboard-ci.yml      active
392437488   E2E Simulation & Backup-Restore Drill    .github/workflows/e2e-simulation.yml     active
393785364   Edge AI Robot & Integration Tests        .github/workflows/edge-ai-ci.yml         active
387716582   Factory Control Tests                    .github/workflows/factory-control-ci.yml active
390262815   FIWARE Stack Smoke Test                  .github/workflows/fiware-smoke-test.yml active
382937338   IoT Gateway Tests                        .github/workflows/gateway-ci.yml         active
392407893   PR Review Verdict Publisher              .github/workflows/pr-review-verdict-publisher.yml active
```

**Canonical names that survive the merge (do not rename):**

| Identifier | Value | Owner |
|---|---|---|
| Workflow file path | `.github/workflows/dashboard-ci.yml` | #259 (issue #156) — stated in the file header, lines 9–14 |
| Workflow name | `Dashboard CI` | #259 |
| Job id | `dashboard-build-and-test` | #259 |
| Job (check) name — the check-run context a reviewer sees | `Dashboard Quality & Build Gate` | #259 |

The file header already records the canonical ownership explicitly:

```
# Canonical ownership:
#   This workflow file is the single canonical implementation of the Dashboard
#   quality gate for the repository. PR #259 (issue #156) owns the gate; PR
#   #260 (issue #149) carries a byte-identical copy of this file so the two
#   open branches do not shadow each other and merge without an add/add
#   conflict. Any change to the gate must be applied to both branches.
```

**Step-by-step expectation for the combined file** (13 steps, unchanged from the current blob):

| # | Step | Blocking? |
|---|---|---|
| 1 | `actions/checkout@v4` | n/a |
| 2 | `actions/setup-node@v4` (node 22, npm cache) | n/a |
| 3 | `npm ci` | **Blocking** |
| 4 | `npm audit --json` / `npm audit --audit-level=critical` | Non-blocking by design (`\|\| true`) — evidence only |
| 5 | `npm sbom --sbom-format=cyclonedx` | Non-blocking by design — evidence only |
| 6 | `npm run typecheck` | **Blocking** |
| 7 | `npm run lint` | **Blocking** |
| 8 | `npm run test` | **Blocking** |
| 9 | `npm run build:integrity` | **Blocking** |
| 10 | `cd dist && sha256sum -c SHA256SUMS \| tee ../sha256sum-verification.txt` | Intended blocking — **see §3.3, currently NOT reliably blocking** |
| 11 | `tar --sort=name --mtime='UTC 1970-01-01' …` + `sha256sum dashboard-dist.tar.gz` | **Blocking** |
| 12 | `actions/upload-artifact@v4` (`if-no-files-found: error`, 14-day retention) | **Blocking** |

### 2.3 The one conflict: `.github/workflows/adr-lint.yml`

Both branches edit the routing-truth-table comment block at the top of the file. The merge base
carries neither dashboard line. Base:

```
#   adr/**, docs/**, .github/workflows/**          → adr-lint.yml  (this file)
#   esp32-ukit-bridge/**                          → bridge-ci.yml
```

#259 adds:

```
#   dashboard/**                                  → dashboard-ci.yml
```

#260 adds:

```
#   dashboard/**, .github/workflows/dashboard-ci.yml → dashboard-ci.yml
```

Both additions are **comments only**; neither branch changes a trigger, a job or a step in
`adr-lint.yml`. The conflict is therefore cosmetic in effect but must still be resolved for the
merge to complete.

**Required resolution.** Adopt #260's routing line in `adr-lint.yml`, because it is the form that
matches the canonical `dashboard-ci.yml` header, which is byte-identical on both branches:

```
#   dashboard/**, .github/workflows/dashboard-ci.yml → dashboard-ci.yml
```

Retain #259's additional module-ownership line, which is non-conflicting and is already carried
into the merged tree by the auto-merge (it is informational and factually correct):

```
#   dashboard/                    : React + Vite operator dashboard (TypeScript)
```

**Consistency follow-up (required, non-blocking for the merge).** After the resolution, the three
sibling workflows that only #259 touched will still carry the shorter form
(`#   dashboard/**   → dashboard-ci.yml`) while `adr-lint.yml` carries the combined form. The
routing truth table is then not uniform across the workflow set. Either (a) align
`bridge-ci.yml`, `gateway-ci.yml` and `factory-control-ci.yml` to the combined wording in the same
follow-up commit, or (b) record explicitly that `adr-lint.yml` uses the extended wording on
purpose. The truth table is documentation only; it does not affect routing behaviour, because
`adr-lint.yml` triggers on `push`/`pull_request` without a `paths:` filter and runs
`yamllint .github/workflows/` plus `scripts/check_adrs.py` regardless of which path changed.

---

## 3. Non-skippable property of the combined check

### 3.1 The `continue-on-error:` / `if:` conditions — quoted from both branches

Both branches carry the identical blob `69ee4298…`, so every line quoted below is present verbatim
in the combined tree. Measured over the whole file on both branches:

```
$ git show <branch-259>:.github/workflows/dashboard-ci.yml | grep -c "continue-on-error"   -> 0
$ git show <branch-260>:.github/workflows/dashboard-ci.yml | grep -c "continue-on-error"   -> 0
$ git show <branch-259>:.github/workflows/dashboard-ci.yml | grep -cE "^\s+if:"             -> 0
$ git show <branch-260>:.github/workflows/dashboard-ci.yml | grep -cE "^\s+if:"             -> 0
```

There is **no** `continue-on-error:` and **no** step- or job-level `if:` anywhere in the file. The
only conditional expression of any kind is the upload-artifact input, which is a *fail-closed*
input:

```yaml
108	      - name: Upload build artifact and release evidence
109	        uses: actions/upload-artifact@v4
...
121	          if-no-files-found: error
```

The only two places where a failure is explicitly swallowed are the advisory-evidence commands,
which are documented as non-blocking in the file header:

```yaml
 72	      - name: Dependency advisory assessment (non-blocking evidence)
 73	        run: |
 74	          npm audit --json > npm-audit.json || true
 75	          npm audit --audit-level=critical > npm-audit-summary.txt 2>&1 || true
```

```yaml
 79	      - name: Generate SBOM for the installed dependency tree (non-blocking evidence)
 80	        run: |
 81	          npm sbom --sbom-format=cyclonedx > sbom.cdx.json 2>/dev/null \
 82	            || echo '{"note":"npm sbom unavailable in this npm version"}' > sbom.cdx.json
```

and this is the declared intent in the header:

```
# Supply-chain scope: the gate records (a) a dependency advisory assessment,
# (b) an SBOM of the installed dependency tree, and (c) a retained build
# artifact together with its SHA-256 digest. These steps are deliberately
# non-blocking because the current lockfile still carries transitive
# advisories in the vitest/tinypool dev chain, and `npm audit fix --force`
# would apply a breaking major upgrade. The recorded evidence is review
# material for release acceptance; it is not a claim of a clean audit.
```

**Verdict on step-level skip conditions: the quality gate steps cannot be skipped.** `npm ci`,
`npm run typecheck`, `npm run lint`, `npm run test`, `npm run build:integrity`, the `tar`
packaging step and the artifact upload all fail the job on error. No `if:` guard can turn a red
step green, and there is no `continue-on-error:` escape.

### 3.2 The check is not enforced as a required status check at the merge gate

This is the substantive part of finding F4 and it is **not** satisfied by the workflow file alone.

The repository's branch ruleset requires only one context:

```
$ gh api repos/vinhphan812/smart-factory/rulesets/25558417
{
  "conditions": {"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}},
  "enforcement": "active",
  "name": "smart-factory required checks",
  "rules": [{
    "parameters": {
      "do_not_enforce_on_create": false,
      "required_status_checks": [{"context": "ADR Lint & Impact Check", "integration_id": 15368}],
      "strict_required_status_checks_policy": false
    },
    "type": "required_status_checks"
  }]
}
```

`master` additionally has **no classic branch protection**:

```
$ gh api repos/vinhphan812/smart-factory/branches/master/protection
{"message": "Branch not protected", "status": "404"}
```

**So the Dashboard check (`Dashboard Quality & Build Gate`) is not a required status check and can
therefore be absent, pending or red without blocking a merge.** The gate is *non-skippable inside
the workflow* but *not enforced at the merge gate*.

**Required change (exactly):** add the Dashboard gate to the ruleset so the check context becomes
required:

```
PUT repos/vinhphan812/smart-factory/rulesets/25558417
{
  "rules": [{
    "type": "required_status_checks",
    "parameters": {
      "do_not_enforce_on_create": false,
      "strict_required_status_checks_policy": false,
      "required_status_checks": [
        {"context": "ADR Lint & Impact Check", "integration_id": 15368},
        {"context": "Dashboard Quality & Build Gate", "integration_id": 15368}
      ]
    }
  }]
}
```

`integration_id 15368` is the GitHub Actions integration already used by the existing ADR entry.

**Interaction with the `paths:` filter that must be handled in the same change.** The workflow
declares path filters on both triggers:

```yaml
 32	on:
 33	  push:
 34	    branches:
 35	      - master
 36	      - 'feat/**'
 37	      - 'fix/**'
 38	    paths:
 39	      - 'dashboard/**'
 40	      - '.github/workflows/dashboard-ci.yml'
 41	  pull_request:
 42	    branches:
 43	      - master
 44	    paths:
 45	      - 'dashboard/**'
 46	      - '.github/workflows/dashboard-ci.yml'
```

A pull request that touches neither `dashboard/**` nor `.github/workflows/dashboard-ci.yml`
produces **no check run at all** for `Dashboard Quality & Build Gate`. If the context is made
required while the `paths:` filter is kept, such PRs will wait for a check that never reports.
Two mutually exclusive options; the second is the safer one and is recommended:

- **Option A (recommended):** remove the `paths:` filter from the `pull_request` trigger (keep it on
  `push` if desired), so the gate always reports on every pull request against `master`.
- **Option B:** keep the `paths:` filter and do **not** make the context required — i.e. leave the
  gate as a non-required advisory signal. This is the current state and it does not satisfy F4.

### 3.3 The integrity-verification step is not reliably blocking (defect)

The combined file's manifest verification step is:

```yaml
 97	      - name: Verify per-file integrity manifest
 98	        run: |
 99	          cd dist
100	          sha256sum -c SHA256SUMS | tee ../sha256sum-verification.txt
```

GitHub Actions' default shell for `run:` on Linux is `bash -e {0}` — **`pipefail` is not enabled**
by default (measured: `grep -c pipefail` over the file returns `0` on both branches). With
`pipefail` off, the exit status of `sha256sum -c … | tee …` is the exit status of `tee`, which is
`0`. A SHA-256 mismatch is therefore *printed* in the log and copied into
`dashboard/sha256sum-verification.txt`, but it does **not** fail the step and does **not** fail the
check. `dashboard/docs/RELEASE_ARTIFACTS.md` currently describes this step as "a blocking
verification step; any mismatch fails the job" — that description does not hold for the current
pipeline.

**Required change (exactly):** enable `pipefail` before the pipeline in that step, e.g.

```yaml
 97	      - name: Verify per-file integrity manifest
 98	        run: |
 99	          set -o pipefail
100	          cd dist
101	          sha256sum -c SHA256SUMS | tee ../sha256sum-verification.txt
```

This change must be applied to **both** open branches (per the file's own canonical-ownership
note) and to the combined `master` tree, i.e. it is a follow-up commit, not part of this
documentation-only change.

### 3.4 Push-time trigger gap (observation, not blocking)

`dashboard-ci.yml` triggers on `push` to `master`, `feat/**` and `fix/**` only. It does **not**
include `smart-factory/**`, although `adr-lint.yml` does include `smart-factory/**`. Consequently a
push to a `smart-factory/**` branch does not run the Dashboard gate; only the `pull_request` event
against `master` does. This is directly visible in the run history of the two reviewed HEADs:

```
# #259 HEAD 8332f01 (branch smart-factory/t_7538eb48-...) — no Dashboard CI *push* run
39962434349  ADR Lint & Architecture Governance Gate  pull_request  completed  success
39962434326  CI                                       pull_request  completed  success
39962434308  Dashboard CI                             pull_request  completed  success
39962428767  ADR Lint & Architecture Governance Gate  push         completed  success

# #260 HEAD 0c422e8 (branch feat/issue-149-design-system-nav) — push run present, 'feat/**' matches
40078342840  ADR Lint & Architecture Governance Gate  pull_request  completed  success
40078342825  Dashboard CI                             pull_request  completed  success
40078342827  CI                                       pull_request  completed  success
40078340530  ADR Lint & Architecture Governance Gate  push         completed  success
40078340532  Dashboard CI                             push         completed  success
```

If push-time gate runs are wanted on the `smart-factory/**` branch namespace, add `- 'smart-factory/**'`
to the `push.branches` list. Recorded as an observation; it is not required for the merge.

### 3.5 Summary of the non-skippable verdict

| Question | Verdict | Evidence |
|---|---|---|
| Can a failing quality step be turned green inside the workflow? | **No** | 0 × `continue-on-error:`, 0 × `if:` (§3.1) |
| Can the advisory/SBOM evidence steps fail the job? | **No, by design** | `\|\| true` at lines 74–75; header lines 21–27 |
| Can the whole check be skipped/absent while merging to `master`? | **Yes** | ruleset `25558417` requires only `ADR Lint & Impact Check`; `master` has no classic branch protection (§3.2) |
| Can the check be absent on a PR? | **Yes** | `paths:` filters on both triggers (§3.2) |
| Can a SHA-256 mismatch fail the check? | **No, not today** | `sha256sum -c … \| tee …` without `pipefail` (§3.3) |

---

## 4. Post-merge refresh: ordered command list (SBOM + npm audit on the combined tree)

Run **after** both PRs are merged, on the combined `master` tree, in this order. The order matters:
`npm sbom` requires an installed tree and fails without `node_modules` (verified locally:
`npm error code ESBOMPROBLEMS … missing: chart.js@^4.4.3`), so `npm ci` must precede it.

**Who runs it:** the engineer performing the merge (owner of the merge operation), on the combined
`master` tree, immediately after both merges land and before the release decision is taken. The
push-triggered `Dashboard CI` run on `master` then regenerates the same artefacts for the merged
commit; the local run is what lets the reviewer see the advisory state before CI completes, and
what `npm run release:evidence` needs.

```bash
# 0. work on the combined tree
git checkout master
git pull --ff-only origin master
git rev-parse HEAD                      # record the exact combined-tree SHA in the evidence

cd dashboard

# 1. deterministic install from the committed (remediated) lockfile
npm ci

# 2. advisory state of the combined lockfile — record the exit code, it is 1 while advisories remain
npm audit --json > npm-audit.json;        echo "npm audit --json exit=$?"
npm audit --audit-level=critical > npm-audit-summary.txt 2>&1; echo "npm audit --audit-level=critical exit=$?"

# 3. SBOM of the combined installed tree (requires step 1)
npm sbom --sbom-format=cyclonedx > sbom.cdx.json; echo "npm sbom exit=$?"

# 4. full release-evidence bundle — present only after #260 lands
#    (package.json script "release:evidence" + scripts/release-evidence.mjs + scripts/dependency-scope.mjs)
npm run release:evidence
#    -> dashboard/release-evidence/{dependency-scope.json,dependency-scope.md,
#       sbom.runtime.cdx.json,sbom.full.cdx.json,sbom-separation.json}

# 5. production build + per-file integrity manifest
npm run build:integrity

# 6. manifest verification (see §3.3 — enable pipefail before trusting the exit code)
cd dist
set -o pipefail
sha256sum -c SHA256SUMS | tee ../sha256sum-verification.txt
cd ..
```

Then update the evidence documents on the combined tree to match the refreshed numbers:
`docs/research/manifest.md` (the Dashboard CI rows) and `dashboard/docs/RELEASE_ARTIFACTS.md`
(the advisory paragraph in §3 of that file, which currently describes the vitest/tinypool advisories
as still open).

Note: `npm-audit.json`, `npm-audit-summary.txt`, `sbom.cdx.json` and `release-evidence/` are
git-ignored by #260's `dashboard/.gitignore`, so they are regenerated release material and are
uploaded as workflow artefacts, not committed.

---

## 5. Current advisory state on this branch (#259) — independently re-derived

Executed locally in `dashboard/` on branch
`smart-factory/t_7538eb48-ci-add-dashboard-ci-workflow-build-lint` at HEAD
`8332f01cd25f1a2ab2ddc4b5d3371803be4c6c12`, Node `v26.12.1`, npm `12.0.2`:

```
$ cd dashboard && npm audit --json
{"auditReportVersion": 2, "vulnerabilities": { … }, "metadata": { … }}
# exit code 1

$ cd dashboard && npm audit
…
8 vulnerabilities (5 moderate, 1 high, 2 critical)

To address all issues (including breaking changes), run:
  npm audit fix --force
# exit code 1
```

Real counts from the `npm audit --json` `metadata` block:

```json
"vulnerabilities": {
  "info": 0,
  "low": 0,
  "moderate": 5,
  "high": 1,
  "critical": 2,
  "total": 8
}
```

Affected packages reported by `npm audit` on this branch, with severities:

| Package | Severity | Direct? | Advisory headline |
|---|---|---|---|
| `@vitest/mocker` | moderate | no | via `vitest` |
| `esbuild` | moderate | no | via `vite` |
| `vite` | high | **yes** | dev server / request handling advisories |
| `vite-node` | moderate | no | via `vitest` |
| `vitest` | critical | **yes** | via `tinypool` |
| `tinypool` | critical | no | Prototype Pollution gadget in worker options leads to Remote Code Execution (GHSA-5gmw-xhrv-c9v3); Prototype Pollution Gadget to RCE in `run()` options (GHSA-85c8-ppgw-ccpr) |
| `react-router` | moderate | no | Open redirect via backslash in `<Link>` and `useNavigate` (CVE-2025-68470 bypass, GHSA-wrjc-x8rr-h8h6); Arbitrary Constructor Injection via `deserializeErrors()` in React Router SSR Hydration (GHSA-337j-9hxr-rhxg) |
| `react-router-dom` | moderate | **yes** | depends on vulnerable `react-router` |

**Stated plainly, as required: the eight previously reported advisories are NOT resolved on this
branch's lockfile.** The real, locally re-derived count on #259's `dashboard/package-lock.json`
(blob `cfac543e62540a4057890d42181017b6114cd700`) is **8 vulnerabilities — 5 moderate, 1 high,
2 critical**, and `npm audit` exits `1`. #259 does not modify the lockfile at all, so this is the
merge base's advisory state, unchanged.

For contrast, the same command run against **#260's** `package.json` + `package-lock.json`
(blob `9efb1268d68ac1d97f0bbba4a6d3553e65d36938`) returns:

```json
"vulnerabilities": {
  "info": 0,
  "low": 0,
  "moderate": 0,
  "high": 0,
  "critical": 0,
  "total": 0
}
```

with `npm audit` exit code `0`.

The remediation therefore exists only on #260, which is the factual basis for the merge order in
§2.1 and for the refresh in §4. Until the combined tree is audited, the advisory state of the
merged result is **assumed**, not proven.

---

## 6. Release gate statement (finding F5)

**A green Dashboard CI build is NOT release approval.** It is a static-and-CI signal about a
source tree. It says nothing about the deployed artefact.

The following remain **externally open** and **cannot be certified by CI** on this repository. They
require a real browser session against a real deployment, a human operator, and the deployment
topology described in `dashboard/docs/RELEASE_ARTIFACTS.md`. No automated smoke exists for them and
none is claimed here.

Concrete checks a human must still perform before any release decision:

1. **Production-browser smoke.** Load the built dashboard in a real browser session against the
   production deployment (not `npm run dev`, not a static file open). Confirm the application
   boots, renders the module views, and that the console is free of uncaught errors and failed
   resource loads. CI runs `vite build` and unit tests only; it never opens the bundle in a browser.
2. **HTTPS gateway transport.** Confirm the dashboard reaches the gateway over **HTTPS** (and
   WSS where applicable) in production, with a valid certificate chain and the correct hostname.
   The committed CSP allows loopback origins only
   (`connect-src 'self' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*`),
   so a production gateway on another origin requires the deploy-time CSP header injection
   described in `RELEASE_ARTIFACTS.md` §1 and tracked in issue #156. Until that exists, the
   production transport is **not** demonstrated by anything in this repository.
3. **CSP header assertion.** Assert the **HTTP response header**
   `Content-Security-Policy` on the production response, with the production gateway origins
   substituted, and verify that no CSP violation is reported in the browser console. The committed
   policy is a `<meta http-equiv>` directive in `dashboard/index.html`, which cannot reference
   build-time environment values and is not a substitute for a response header.
4. **Cookie behaviour.** Verify session/auth cookies are set with the expected attributes
   (`Secure`, `HttpOnly`, `SameSite`, `Path`, `Domain`) and that they are honoured, rotated and
   cleared on logout over the real HTTPS origin.
5. **Auth session.** Log in with a real credential, confirm the session persists across a full page
   reload and a new tab, that an expired or revoked session is rejected, and that unauthorised
   routes and API calls are refused. No CI job authenticates against a live gateway.
6. **Role/permission behaviour.** Confirm that the operator roles enforced in the deployment match
   the intended RBAC for the nine-module factory view.
7. **Telemetry provenance.** Confirm that the values shown in production come from the real
   gateway/bridge feed and are not placeholder or simulated values. The repository's own
   no-fabricated-telemetry test is a source-level guard only.

None of items 1–7 has been performed, and this document does not claim any of them.

---

## 7. Rollback and reconciliation

### 7.1 If the combined tree ends up with two competing Dashboard checks

Because both branches carry a byte-identical `dashboard-ci.yml` (blob `69ee4298…`), a normal merge
cannot produce two Dashboard CI workflow files. Two competing checks would arise only from a
mistaken conflict resolution (for example restoring a divergent copy of the workflow under a second
name), or from an out-of-band branch carrying a second Dashboard workflow.

**Detection (run on the combined tree):**

```bash
# exactly one Dashboard CI workflow file must exist
git ls-tree -r --name-only origin/master .github/workflows/ | grep -i dashboard
# -> .github/workflows/dashboard-ci.yml   (must be exactly one line)

# and exactly one registered Dashboard CI workflow
gh api repos/vinhphan812/smart-factory/actions/workflows \
  --jq '.workflows[] | select(.path|test("dashboard")) | "\(.id)\t\(.name)\t\(.path)\t\(.state)"'
# -> 392572940  Dashboard CI  .github/workflows/dashboard-ci.yml  active   (exactly one row)

# and the canonical blob must still be the one below
git rev-parse origin/master:.github/workflows/dashboard-ci.yml
# -> 69ee4298aa3f2ea6ad71e40ea3961014bed2bbfb
```

**Reconciliation procedure (if more than one is found):**

1. Keep `.github/workflows/dashboard-ci.yml` as the single canonical workflow. #259 owns it; the
   canonical workflow name is `Dashboard CI` and the canonical job/check name is
   `Dashboard Quality & Build Gate`. Do not rename either.
2. Delete the redundant competing workflow file in a single follow-up commit on `master` (do not
   delete it on the PR branches — the delete would re-conflict on the next merge).
3. Re-verify with the three detection commands above; the blob must still be
   `69ee4298aa3f2ea6ad71e40ea3961014bed2bbfb` and the workflow list must show exactly one Dashboard
   row.
4. If the duplicate had already been made a required status check, remove the duplicated context
   from ruleset `25558417`, leaving one `Dashboard Quality & Build Gate` entry.
5. Re-run the gate on the repaired `master` and confirm exactly one
   `Dashboard Quality & Build Gate` check-run on the new HEAD:
   `gh api repos/vinhphan812/smart-factory/commits/<new-sha>/check-runs --jq '.check_runs[].name'`.

### 7.2 Merge rollback

If the merged `master` must be reverted, revert the merge commit(s) rather than force-pushing or
rebasing history:

```bash
git revert -m 1 <merge-commit-sha>      # in the order the merges were made
git push origin master
```

Do not reset or force-push `master`. Note that reverting #260 also restores the pre-remediation
lockfile (blob `cfac543e…`, 8 advisories) and must be accompanied by a re-run of the §4 refresh
commands so that the recorded advisory evidence matches the tree again.

### 7.3 If the `adr-lint.yml` conflict is resolved incorrectly

`adr-lint.yml` runs `yamllint .github/workflows/` and `python scripts/check_adrs.py`. An unresolved
conflict marker in that file makes the file invalid YAML, so the `ADR Lint & Impact Check` job
fails to start and the merge is blocked — the failure is loud, not silent. If a wrong resolution
gets through, re-open `adr-lint.yml` and set the routing line to the combined wording given in
§2.3.

---

## 8. Evidence index

All statements above are backed by one of the following, all reproducible:

| Claim | How it was obtained |
|---|---|
| File overlap set | `git diff --name-only 3d7d7ca5… <branch>` for each branch, intersected |
| Byte-identity of the six shared files | `git rev-parse <branch>:<path>` compared per file (blob SHAs in §1) |
| Merge conflict set and merged blobs | `git merge-tree --write-tree <A> <B>` in both orders (read-only; no commit created) |
| Workflow conditions | `git show <branch>:.github/workflows/dashboard-ci.yml`, quoted verbatim; `grep -c` for `continue-on-error`, `^\s+if:`, `pipefail` |
| Required-check enforcement | `gh api repos/…/rulesets/25558417`; `gh api repos/…/branches/master/protection` (404, not protected) |
| Workflow uniqueness | `gh api repos/…/actions/workflows`; `git ls-tree -r --name-only <merged-tree> .github/` |
| Exact-head CI URLs | `gh api repos/…/actions/runs?head_sha=…` for both reviewed HEADs (run IDs in §3.4) |
| Advisory counts on #259 | local `npm audit --json` and `npm audit` in `dashboard/` — real output quoted in §5, exit code 1 |
| Advisory counts on #260's lockfile | local `npm audit --json` against #260's `package.json` + `package-lock.json` — 0 total, exit code 0 |
| `npm sbom` requires an installed tree | local `npm sbom --sbom-format=cyclonedx` → `npm error code ESBOMPROBLEMS … missing: chart.js@^4.4.3` |

**Evidence ceiling:** L0 static (git object, blob and GitHub API inspection) plus L1 local
`npm audit` execution. **No production deployment, no browser session, no gateway, no hardware and
no HIL evidence is claimed.**
