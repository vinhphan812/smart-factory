# Smart Factory — Issue Closure Audit (2026-10-22)

**Auditor:** dev-architect (Kanban `t_353718a4`)  
**Audited ref:** `origin/master` at [`3d7d7ca5e8413566637a50e83c1e5fbe2722977f`](https://github.com/vinhphan812/smart-factory/commit/3d7d7ca5e8413566637a50e83c1e5fbe2722977f)  
**Snapshot date:** 2026-10-22 — this document is a **dated point-in-time snapshot**, not a live status feed.  
**Scope:** Re-derive closure evidence for open Issues #152, #174, #179, #167, #182, #186, and #180. A merged commit, open PR, closed-unmerged PR, and document are distinct evidence states.
**Closure outcome:** **no issue is closed by this audit.** All seven audited issues remain **OPEN**, because no closure evidence for any specific issue is independently verifiable in the repository at the anchors recorded below. This document is documentation-only and closes nothing on its own.

> **Snapshot freshness rule.** Every open/closed/merged status recorded below was true on
> **2026-10-22** only. Issue and PR states change; **re-query live GitHub state before any
> future closure action** and before relying on any "still open" claim in this document.
> A later re-check is recorded in [Live status re-verification (2026-10-24)](#live-status-re-verification-2026-10-24).
>
> This rule is formalised in the sections below:
> [Evidence Lifetime and Requery Rule](#evidence-lifetime-and-requery-rule) (when this
> audit must be re-run and which commit SHA and CI run URL each observation is anchored to),
> [Release Boundary Classification](#release-boundary-classification) (which class of
> evidence may close an issue and which may not),
> [Snapshot Staleness and Branch Movement](#snapshot-staleness-and-branch-movement) (which
> open PR heads have moved since the snapshot, and the SHA-scoped validity rule),
> [Revalidation Procedure](#revalidation-procedure) (the exact commands a reviewer runs to
> re-verify a specific issue's closure, and when each must be run), and
> [Non-Negotiable Limitations of L0/L1/L2 Evidence](#non-negotiable-limitations-of-l0l1l2-evidence)
> (what the evidence gathered here can never certify).

## Method

1. Ran `git fetch origin --prune`; inspected `origin/master`, not a feature branch.
2. Confirmed #245 merge [`bcc8848`](https://github.com/vinhphan812/smart-factory/commit/bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20) and #256 merge [`961298b`](https://github.com/vinhphan812/smart-factory/commit/961298b642599c71bcdbff1b0879b2f3bda2e9bb) are ancestors of `origin/master`; confirmed #242 and #244 remain open and unmerged.
3. Read each issue checklist and inspected merged source/test evidence.
4. Executed the required security suite in a detached checkout of `origin/master`.

Commands used for the live checks are recorded in the re-verification section so the
queries themselves are reproducible.

Evidence levels follow `docs/testing-and-acceptance.md:6-11`: L0 design/static, L1 host unit, L2 simulation, L3 bench, L4 HIL, L5 integrated physical deployment.

**Immutable Evidence & Provenance:**
- **CI Run URL:** [GitHub Actions Run #39717529906](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906) (Jobs [119623125386 (Python 3.12)](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906/job/119623125386) and [119623125531 (Python 3.11)](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906/job/119623125531)) on runner `ubuntu-24.04`, anchored to head SHA `bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20`.
- **Exact Verification Command:** `cd iot-gateway && python -m pytest tests/test_security_abuse.py -v` — exercises the 69-node abuse suite named in the #179 checklist (the CI run additionally exercises the whole `iot-gateway/tests/` tree: 316 items in the test step, 407 in the coverage step).
- **Explicit Scope Limitations:** This audit is a dated snapshot (2026-10-22); live issue/PR status must be re-evaluated before any future closure action. Furthermore, documentation and L0/L1 unit test evidence **do not prove** physical E-stop, OTA signature validation, MQTT ACL/TLS or Yanshee SDK/HIL capability.

## Executive Verdict

**Close no issues.** #179 has a merged, passing L1 regression suite, but mandatory coverage is incomplete and explicit dependencies #152/#167 are open. #174 is useful L0 design evidence but explicitly does not meet an executable/hardware DoD. The other five rely on open, unmerged PRs.

| Issue | Verdict | Evidence class | Named gap / blocker |
|---|---|---|---|
| #152 | **KEEP OPEN** | Class A (repository-verifiable) | PR #242 is open/unmerged. |
| #174 | **KEEP OPEN** | Class A (repository-verifiable) + Class B gate outstanding | L0 docs only; no versioned executable controller schema, fixture library, or negative tests. |
| #179 | **KEEP OPEN** | Class A (repository-verifiable) + Class B gates outstanding | Missing required fixtures/tests; dependencies #152 and #167 are open. |
| #167 | **KEEP OPEN** | Class A (repository-verifiable) + Class B gate outstanding | PR #242 is open/unmerged; master lacks gateway auth module and authenticated WS. |
| #182 | **KEEP OPEN** | Class A (repository-verifiable) + Class B gate outstanding | PR #244 is open/unmerged. |
| #186 | **KEEP OPEN** | Class A (repository-verifiable) + Class B gate outstanding | PR #244 is open/unmerged. |
| #180 | **KEEP OPEN** | Class A (repository-verifiable) + Class B gate outstanding | PR #244 is open/unmerged; `integration-tests/` is PLANNED only. |

**Evidence class** is defined in
[Release Boundary Classification](#release-boundary-classification): **Class A** is
repository-verifiable evidence (merged commit, source, test, CI run) and is the only class
that can close an issue; **Class B** is an external release gate (deployed HTTPS/CORS/CSP,
HSTS, certificate management, hardware proof, live multi-container integration) and can
never close an issue. The "Class B gate outstanding" entries above record that the
corresponding external gate is *also* unmet — they do not weaken the Class A verdict.

**Reference anchors.** File-and-line citations in this document resolve against immutable
commits, not branches:

| Artefact | Immutable base URL |
|---|---|
| `docs/security/threat-model.md`, `docs/security/abuse-case-tests.md`, `iot-gateway/tests/test_security_abuse.py` | `https://github.com/vinhphan812/smart-factory/blob/bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20/` |
| `contracts/physical/capability-matrix.md` | `https://github.com/vinhphan812/smart-factory/blob/961298b642599c71bcdbff1b0879b2f3bda2e9bb/` |
| Audited master tree | `https://github.com/vinhphan812/smart-factory/tree/3d7d7ca5e8413566637a50e83c1e5fbe2722977f/` |

### How to re-verify this document

Every measurement below is re-checkable with these commands.

Immutable CI run and job metadata:

```text
$ gh api repos/vinhphan812/smart-factory/actions/runs/39717529906 --jq '{id,head_sha,head_branch,status,conclusion,html_url,created_at,path}'
$ gh api repos/vinhphan812/smart-factory/actions/runs/39717529906/jobs --jq '.jobs[] | {id,name,conclusion,html_url}'
```

Raw job logs (count suite nodes, read the verbatim result lines):

```text
$ gh api repos/vinhphan812/smart-factory/actions/jobs/119623125531/logs > job-119623125531.log
$ gh api repos/vinhphan812/smart-factory/actions/jobs/119623125386/logs > job-119623125386.log
$ grep -c "test_security_abuse.py::" job-119623125531.log   # 69
$ grep -E "passed" job-119623125531.log                     # verbatim result lines
```

Local re-execution (host environment, non-permanent output):

```text
$ cd iot-gateway && python -m pytest tests/test_security_abuse.py -q
```

Live issue/PR state — the exact queries required by the
[Evidence Lifetime and Requery Rule](#evidence-lifetime-and-requery-rule), to be re-run
**immediately before any closure claim** and after any merge into `master`:

```text
$ git fetch origin --prune
$ git rev-parse origin/master
$ for i in 152 174 179 167 182 186 180; do gh api repos/vinhphan812/smart-factory/issues/$i --jq '"#\(.number) \(.state) updated=\(.updated_at) closed=\(.closed_at // "-")"'; done
$ for p in 242 244 245 256; do gh api repos/vinhphan812/smart-factory/pulls/$p --jq '"PR#\(.number) state=\(.state) merged=\(.merged) mergedAt=\(.merged_at // "-") head=\(.head.sha) updated=\(.updated_at)"'; done
$ gh api "repos/vinhphan812/smart-factory/actions/runs?head_sha=$(git rev-parse origin/master)" --jq '.workflow_runs[] | "\(.id) \(.name) \(.status)/\(.conclusion) \(.html_url)"'
```

Recorded outputs of these queries are in
[Live status re-verification](#live-status-re-verification-2026-10-24).

Documentation validation:

```text
$ python scripts/check_adrs.py
$ python -m pytest scripts/tests/test_check_adrs.py -q
```

## Evidence Lifetime and Requery Rule

**This audit is a point-in-time observation, not a standing claim.** Every verdict,
status, count and file-line citation above was derived from a specific immutable commit
SHA and, where a test result is cited, a specific CI run URL. Those anchors are the
*only* thing that gives the findings their validity; the prose has none on its own. A
finding in this document must never be restated, quoted or cited as a current fact
without the anchor that produced it and without its observation date.

### What each observation is anchored to

| Observation | Commit SHA | CI run URL | Observed |
|---|---|---|---|
| Audited `origin/master` tree | `3d7d7ca5e8413566637a50e83c1e5fbe2722977f` | [ADR Lint run 39717602691](https://github.com/vinhphan812/smart-factory/actions/runs/39717602691) (`success`) | 2026-10-22 |
| #179 threat model, abuse-case doc, `iot-gateway/tests/test_security_abuse.py` | `bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20` | [IoT Gateway Tests run 39717529906](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906) (`success`); [ADR Lint run 39717529878](https://github.com/vinhphan812/smart-factory/actions/runs/39717529878) (`success`) | 2026-10-22 |
| #174 physical capability matrix (`contracts/physical/capability-matrix.md`) | `961298b642599c71bcdbff1b0879b2f3bda2e9bb` | [ADR Lint run 39717572941](https://github.com/vinhphan812/smart-factory/actions/runs/39717572941) (`success`) | 2026-10-22 |
| Local host re-execution of the #179 abuse suite | branch tree `b5982bd306b07a41a47c1c005684a162054b3c3a` | n/a — local, non-permanent (see permanence limitation above) | 2026-10-24 |

An observation is valid **only** for the SHA and CI run it was made against. If either
the audited tree or the referenced PR head moves, the observation is stale and must be
re-taken, not extrapolated.

### When this audit MUST be requeried

The audit is invalidated by any of the following events. On each one, re-run the queries
in [How to re-verify this document](#how-to-re-verify-this-document) and the live
issue/PR queries in
[Live status re-verification](#live-status-re-verification-2026-10-24), and record the
new result and its date here.

1. **Immediately before any issue-closure claim is made.** This is mandatory and
   unconditional: the closure decision must be based on a requery taken at that moment,
   not on the 2026-10-22 snapshot and not on this document's own conclusion.
2. **After any merge into `master`.** A merge changes `origin/master`, invalidating the
   audited tree SHA `3d7d7ca` and every file-line citation resolved against it, and may
   also close the very gap that kept an issue open.
3. **After any merge, force-push or new commit on PR #242, #244, #258, #259, #260, #261
   or #262.** Their head SHAs are the blocker state recorded above and in
   [Snapshot Staleness and Branch Movement](#snapshot-staleness-and-branch-movement); a
   changed head invalidates the recorded head SHA and the KEEP OPEN reasoning that
   rests on it.
4. **When a referenced CI run is re-run, superseded or deleted.** The run URL anchors the
   result; a newer run does not retroactively validate the old one, and a deleted run
   removes the evidence entirely.
5. **On any new deployment, hardware session or release**, because that changes the
   Class B release-gate posture recorded below.

This rule is not satisfied by the audit's own timestamps alone. The rule is: **no
closure action without a fresh, dated, anchored requery.**

### Prohibited conversions

The following conversions are invalid and are not made anywhere in this document:

- A dated observation ("on 2026-10-22, master had no `auth.py`") must not be restated
  as a standing claim ("master has no `auth.py`").
- A green CI run must not be generalised to "the suite passes" without its head SHA.
- A KEEP OPEN verdict must not be flipped to closed because the audit itself is old, or
  because a blocking PR has moved — only a fresh requery against merged repository
  evidence may change a verdict.
- Class B (external release gate) evidence must not be recorded as closure evidence for
  any issue; see the next section.

---

## Snapshot Staleness and Branch Movement

This audit is anchored to a **single point in time**: `origin/master` at
[`3d7d7ca5e8413566637a50e83c1e5fbe2722977f`](https://github.com/vinhphan812/smart-factory/commit/3d7d7ca5e8413566637a50e83c1e5fbe2722977f),
observed on **2026-10-22**. That anchor is not renegotiable and is not re-based by this
document: the snapshot remains a dated observation of that tree.

What *has* moved is the set of **open PR branch heads** that the snapshot's verdicts refer
to as blockers. The table below records the real, live head SHAs of the open PRs as
queried from the GitHub API on **2026-10-24T11:26:49Z** (see the exact query in
[Revalidation Procedure](#revalidation-procedure)):

| PR | Branch | Head SHA recorded in this document | Live head SHA observed 2026-10-24T11:26:49Z | Movement |
|---|---|---|---|---|
| #242 | `feat/issue-152-dashboard-auth-lineage-v2` | `986f00279e615f1717cb9e2f4d07f8760452d917` | `c0a7a20ec3cf221334173a9200beacef80e666d5` | **Moved** (last commit `c0a7a20e`, 2026-10-24T10:36:25Z) |
| #244 | `feat/issue-182-deployment-e2e` | `614ed31f2844bc910061ec9e665d27186d865d3e` | `614ed31f2844bc910061ec9e665d27186d865d3e` | **Moved since the 2026-10-22 snapshot** (`6ebd8cc4c5d5e5b55148e65363847e90c3a3c700` → `51ccf4f3593836e87cac0279dd8f3bba14b3f8a6` → `614ed31f`); unchanged between the two 2026-10-24 requeries |
| #258 | `docs/issue-closure-audit-2026-10-22` | `f7f085e8155adc12f2ab637392b2d535e2a1c262` | `f7f085e8155adc12f2ab637392b2d535e2a1c262` | This branch carries this document; it moves with every push to it, so its own head is by definition transient |
| #259 | `smart-factory/t_7538eb48-ci-add-dashboard-ci-workflow-build-lint` | not previously recorded | `8332f01cd25f1a2ab2ddc4b5d3371803be4c6c12` | First anchored here (last commit 2026-10-23T13:34:47Z) |
| #260 | `feat/issue-149-design-system-nav` | not previously recorded | `0c422e867993fcf046b2c21db0283cdae4480f57` | First anchored here (last commit 2026-10-24T08:30:11Z) |
| #261 | `feat/issue-204-fiware-yanshee-context` | not previously recorded | `b9c1b46aca883648cec1197c6ae2a0ca1e508492` | First anchored here (last commit 2026-10-24T10:48:45Z) |
| #262 | `docs/adr-0015-date-correction` | not previously recorded | `e438ae5f58ef0beddd4d1725d4b82b3f1a1235ea` | First anchored here (last commit 2026-10-24T02:58:41Z) |

The head SHAs above were fetched live with `gh pr view <n> --json headRefOid` and
cross-checked against `gh api repos/vinhphan812/smart-factory/pulls/<n>`. They are
recorded as they stood at that timestamp and are **themselves subject to the same
staleness rule** as everything else in this document.

### SHA-scoped validity rule (non-negotiable)

1. **Every closure verdict in this document is VALID ONLY against the specific SHA it
   names.** A verdict that says "PR #244 is open/unmerged" is a statement about the
   repository *at the SHA named for that PR and at `origin/master` at
   `3d7d7ca5e8413566637a50e83c1e5fbe2722977f`* — nothing else.
2. **Any branch movement invalidates the affected verdict until it is re-verified.** The
   moment a cited PR head, the audited master tree, or a cited CI run changes, the
   observation is stale. It must be re-taken by re-running the commands in
   [Revalidation Procedure](#revalidation-procedure) — never extrapolated, never
   inherited from the older value.
3. **Re-verification is required on the ACTUAL closure date.** A closure claim must be
   backed by a requery taken at the moment the claim is made, not by this document's
   verdicts and not by the timestamps in this document.
4. **Re-verification is required AGAIN after merge, against the merged master SHA.** A
   merge changes `origin/master`, invalidating the audited tree SHA and every
   file-and-line citation resolved against it. The post-merge re-verification must be
   anchored to the **merged master commit SHA**, not to the PR head that was merged.
5. **Staleness never converts into closure.** A moved branch, a new commit or a newer CI
   run does not by itself satisfy any checklist item. Only fresh, dated, anchored
   **Class A** evidence can change a verdict, and no Class B evidence can close anything
   (see [Release Boundary Classification](#release-boundary-classification)).

### Effect of the movement recorded above on this audit's verdicts

As observed on 2026-10-24T11:26:49Z, all seven audited issues are still `open`, both
blocking PRs (#242, #244) are still **unmerged**, and `origin/master` is still
`3d7d7ca5e8413566637a50e83c1e5fbe2722977f`. The KEEP OPEN verdicts therefore still hold
**at that timestamp**, and the movement of the PR heads has not changed them — because
each verdict rests on *merged* repository state and on the *absence* of merged artefacts
in `origin/master`, not on the content of an unmerged branch head.

This must not be read as permanence. As soon as any of the seven PR heads above moves
again, the corresponding observation is stale and must be re-verified under the rule in
the preceding subsection.

---

## Revalidation Procedure

A reviewer who wants to re-verify the closure state of **one specific issue** runs the
following, in order. The procedure is per-issue: substitute the issue number in step 2
and its blocking PR number in step 3. Every step is anchored to a SHA or a permanent
CI URL, and each step has a defined point in time at which it must be run.

### Step 1 — Fix the reference point (run at the moment of any closure claim)

```text
$ git fetch origin --prune
$ git rev-parse origin/master
3d7d7ca5e8413566637a50e83c1e5fbe2722977f
```

The SHA printed above is the one observed at the third requery (2026-10-24T11:26:49Z);
record the SHA your own run prints. It is the anchor for every subsequent observation. If
it differs from `3d7d7ca5e8413566637a50e83c1e5fbe2722977f`, the snapshot's
file-and-line citations are stale and must be re-derived against the new master tree.

### Step 2 — Re-query the issue's own live state (run at the moment of any closure claim)

```text
$ gh api repos/vinhphan812/smart-factory/issues/<ISSUE> --jq '"#\(.number) \(.state) updated=\(.updated_at) closed=\(.closed_at // "-")"'
#179 open updated=2026-10-20T13:01:46Z closed=-
```

The line above is the observed output for issue #179 at the third requery. `<ISSUE>` is
the issue number under review. The issue's `state` and `updated_at` must be captured with
the timestamp of the query; a verdict quoted without that timestamp is not valid
evidence.

### Step 3 — Re-query the blocking PR's live head and merge state (run at the moment of any closure claim)

```text
$ gh api repos/vinhphan812/smart-factory/pulls/<PR> --jq '"PR#\(.number) state=\(.state) merged=\(.merged) mergedAt=\(.merged_at // "-") head=\(.head.sha) updated=\(.updated_at)"'
PR#244 state=open merged=false mergedAt=- head=614ed31f2844bc910061ec9e665d27186d865d3e updated=2026-10-24T10:26:03Z
$ gh pr view <PR> --repo vinhphan812/smart-factory --json number,state,mergedAt,headRefOid
{"headRefOid":"614ed31f2844bc910061ec9e665d27186d865d3e","mergedAt":null,"number":244,"state":"OPEN"}
```

`<PR>` is the blocking pull request for that issue: #242 for #152 and #167, and #244 for
issues #182, #186 and #180. The already-merged PRs are #245 for #179 and #256 for #174.
Compare the returned `head` with the SHA recorded in this document. If they differ, the
observation is stale and the checklist row for that issue must be re-derived.

### Step 4 — Confirm the CI evidence for the exact SHA under review (run before citing any CI run)

Filter by the **exact head SHA**, never by branch name:

```text
$ gh api "repos/vinhphan812/smart-factory/actions/runs?head_sha=<SHA>" --jq '.workflow_runs[] | "\(.id) \(.name) \(.event) \(.status)/\(.conclusion) \(.html_url)"'
39717529878 ADR Lint & Architecture Governance Gate push completed/success https://github.com/vinhphan812/smart-factory/actions/runs/39717529878
39717529906 IoT Gateway Tests push completed/success https://github.com/vinhphan812/smart-factory/actions/runs/39717529906
```

The two lines above are the observed output for `<SHA>` =
`bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20` (the #179 merge).

The permanent CI anchors already recorded in this document, and which must be cited by
run ID and job ID rather than by branch:

| Artefact | Permanent CI run | Permanent job(s) | Head SHA |
|---|---|---|---|
| #179 abuse suite (IoT Gateway Tests) | [run 39717529906](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906) | [119623125531 (Python 3.11)](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906/job/119623125531), [119623125386 (Python 3.12)](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906/job/119623125386) | `bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20` |
| Audited master tree (ADR Lint) | [run 39717602691](https://github.com/vinhphan812/smart-factory/actions/runs/39717602691) | — | `3d7d7ca5e8413566637a50e83c1e5fbe2722977f` |
| #179 security artefacts (ADR Lint) | [run 39717529878](https://github.com/vinhphan812/smart-factory/actions/runs/39717529878) | — | `bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20` |
| #174 capability matrix (ADR Lint) | [run 39717572941](https://github.com/vinhphan812/smart-factory/actions/runs/39717572941) | — | `961298b642599c71bcdbff1b0879b2f3bda2e9bb` |

Job logs remain permanently addressable and may be re-counted independently:

```text
$ gh api repos/vinhphan812/smart-factory/actions/jobs/119623125531/logs > job-119623125531.log
$ gh api repos/vinhphan812/smart-factory/actions/jobs/119623125386/logs > job-119623125386.log
$ grep -c "test_security_abuse.py::" job-119623125531.log
69
$ grep -E "passed" job-119623125386.log | tail -2
2026-10-22T03:34:22.6685335Z ======================= 316 passed, 1 warning in 10.37s ========================
2026-10-22T03:34:43.3543353Z ======================= 407 passed, 1 warning in 19.13s ========================
```

The counts above are the observed output when the job logs were re-fetched on
2026-10-24.

### Step 5 — Re-run the local documentation and ADR gates (run before the review verdict)

```text
$ python scripts/check_adrs.py
✅ ADR Lint / Governance Gate PASSED (15 ADRs validated successfully).
$ python -m pytest scripts/tests/test_check_adrs.py -q
......                                                                   [100%]
6 passed in 0.27s
```

The output above is what the local gates produced on this branch on 2026-10-24.

### Step 6 — Re-run the procedure AGAIN after merge (mandatory)

When the blocking PR merges, repeat steps 1–5 **against the merged master commit SHA**
(not against the PR head) and record the new anchors, the new requery timestamp and the
resulting verdict in this document's
[Live status re-verification](#live-status-re-verification-2026-10-24) section.

### Point-in-time summary

| Step | Point in time at which it must be run |
|---|---|
| 1 — reference point | Immediately before any closure claim, and again after any merge into `master` |
| 2 — issue state | Immediately before any closure claim (the **actual** closure date, not a proxy date) |
| 3 — PR head / merge state | Immediately before any closure claim, and again after the PR moves |
| 4 — CI runs for the exact SHA | Before citing any CI result, and after any new commit on the cited SHA |
| 5 — local lint gates | Before the review verdict is recorded |
| 6 — post-merge re-verification | After the merge, anchored to the merged master SHA |

No closure action is permitted on the strength of this document alone. The requery
timestamp, the SHA and the CI run URL are the evidence; this document is only the record
of how to obtain them.

---

## #174 — Physical capability matrix, typed I/O, controller contracts

**Merged evidence:** PR #256 merge [`961298b642599c71bcdbff1b0879b2f3bda2e9bb`](https://github.com/vinhphan812/smart-factory/commit/961298b642599c71bcdbff1b0879b2f3bda2e9bb) changes exactly one file, [`contracts/physical/capability-matrix.md`](https://github.com/vinhphan812/smart-factory/blob/961298b642599c71bcdbff1b0879b2f3bda2e9bb/contracts/physical/capability-matrix.md) (797 lines). The file labels itself **L0 design contract** (`:3`) and says controller/channel allocation and electrical validation are **BLOCKED-L3** (`:33`). Line references below are to that immutable SHA, not to a moving branch.

**Verdict: KEEP OPEN — named gap: executable physical-controller capability contract and fixture implementation.** As of 2026-10-22, no open PR changed `contracts/physical/`, Mega/uKit firmware, registry capability mapping, or Unity prefabs.

**Evidence class:** Class A (repository-verifiable) is the only class that can close this issue, and it is incomplete — the merged artefact is a single L0 Markdown contract. A separate Class B gate (physical hardware proof: measured pinout, tolerance validation, physical E-stop and interlock actuation) remains outstanding and, in any case, cannot close this issue.

| Checklist item | Status | Merged-master evidence | Conclusion |
|---|---|---|---|
| SPEC-1 — identity, controller, counts, modes, pin provenance, safety envelope | **PARTIAL** | Nine logical module sections `capability-matrix.md:37-740`; logical types `:20-33`; constraints, e.g. Conveyor `:103-111`. | Logical identity/I/O/safety exists; no controller board, measured counts/modes, or pin provenance. |
| SPEC-2 — distinguish physical modules from Brackets/Combine | **MET (L0)** | Brackets has no independent actuator/state machine (`:604`); Combine no independent motor/servo/E-stop circuit (`:671`). | Required distinction is explicit. |
| SPEC-3 — typed signals, units/ranges, transitions, fault/watchdog/interlock ownership | **PARTIAL** | Types `:20-33`; per-module schemas/reject codes `:41-735`; `UNKNOWN` invariant `:757-764`; interlock summary `:786-797`. | L0 logical contract exists; channels are unverified and types remain TBD (Parking `:290,351`; Packaging `:534`); no implemented versioned schema. |
| SPEC-4 — canonical command → Mega SDK adapter with hardware-version constraints | **NOT MET** | Generic planned interface only, `factory-interface.md:41-55`; no Mega/uKit/SDK/version mapping. | No adapter mapping is merged. |
| SPEC-5 — simulator fixture library for listed normal/fault conditions | **NOT MET** | Generic simulator `factory-control/src/simulator.py:1-260`; no fixture library under physical contracts, factory-control, or integration-tests. | No all-nine-module fixture library. |
| SPEC-6 — registry #169 and Unity prefab #68, including UNKNOWN/SIMULATED | **PARTIAL** | `UNKNOWN` designed (`capability-matrix.md:735,764,794`); no `SIMULATED`, registry, Unity, prefab, or #169 reference. | No registry/prefab integration. |
| TC-1 — all nine mapped without invented sensors/drives | **PARTIAL (L0)** | Nine sections `:37-740`; unresolved types/counts `:290,534,750`. | Presence is documented; measured proof is absent. |
| TC-2 — mismatch rejected before actuator | **NOT MET** | Planned reject tables, e.g. `:52-59`; no matrix-driven test. | No executable controller admission test. |
| TC-3 — expected states reproducibly reached for every module | **NOT MET** | `integration-tests/README.md:1-27` says PLANNED. | No all-nine-module simulator matrix. |
| TC-4 — measured pinout/tolerances before HIL | **NOT MET** | Explicit BLOCKED-L3 (`:33`). | Required evidence absent. |
| TC-5 — power-loss/safety-stop controlled per module | **NOT MET** | L0 rules, e.g. `:107-111`; no executable recovery suite. | Written design is not test evidence. |
| DoD — paths, schemas/config, fixtures, versioned evidence, negative tests | **NOT MET** | #256 is one Markdown file; `contracts/v1/schemas/` has no physical-controller schema. | Issue forbids closure on docs alone. |

**Blast radius:** HIGH. Future work touches controller adapters, bridge schema compatibility, registry, Unity mapping, simulator, and local interlocks. Required evidence: versioned schema; command admission; duplicate/stale/offline/power-loss fixtures; L2 run hashes; separately labelled L3/L4 proof.

---

## #179 — Threat model and safety abuse-case regression suite

**Merged evidence:** PR #245 merge [`bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20`](https://github.com/vinhphan812/smart-factory/commit/bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20) adds `docs/security/threat-model.md`, `docs/security/abuse-case-tests.md`, and `iot-gateway/tests/test_security_abuse.py`. Source links below resolve against that immutable SHA.

### Required execution evidence (L1)

**Immutable CI anchor (authoritative).** GitHub Actions run
[#39717529906](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906)
— workflow *IoT Gateway Tests* (`.github/workflows/gateway-ci.yml`), event `push` to `master`,
**head SHA `bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20`** (the #245 merge commit),
created `2026-10-22T03:33:53Z`, conclusion `success`.
Both matrix jobs are permanently addressable:

| Job | Immutable URL | Interpreter | Result line (verbatim from job log) |
|---|---|---|---|
| `pytest (Python 3.11)` | [119623125531](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906/job/119623125531) | Python 3.11.17, pytest 9.1.1, pluggy 1.7.0 | `316 passed, 1 warning in 7.97s` (test step); `407 passed, 1 warning in 16.77s` (coverage step) |
| `pytest (Python 3.12)` | [119623125386](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906/job/119623125386) | Python 3.12.15, pytest 9.1.1, pluggy 1.7.0 | `316 passed, 1 warning in 10.37s` (test step); `407 passed, 1 warning in 19.13s` (coverage step) |

Runner: `ubuntu-24.04` (GitHub-hosted). The two step counts differ because
`.github/workflows/gateway-ci.yml:43-49` (test step) excludes
`test_gateway.py`, `test_ssrf.py`, `test_time_sync.py` and `test_orion_ld.py`,
whereas the coverage step at `:51-55` does not — the logs show
`collected 316 items` for the test step and `collected 407 items` for the coverage
step, with an identical coverage total of `2653  568  79%` in both jobs.

`iot-gateway/tests/test_security_abuse.py` contributes exactly **69** test nodes to the
run — countable in either job log (69 lines matching `test_security_abuse.py::`).

**Local host run (secondary, non-permanent).** Executed in a detached checkout of
`origin/master` (`3d7d7ca`) on 2026-10-22:

```text
$ cd iot-gateway && python -m pytest tests/test_security_abuse.py -v
====================== 69 passed, 73 warnings in 13.51s =======================
```

> **Permanence limitation:** this local console excerpt is copied text, not a retained
> artefact — it has no permalink and its exact warning count is environment-dependent.
> It is corroboration only. The permanent, independently re-checkable record is the CI
> run URL above, which is anchored to an immutable SHA.

**Independent re-verification (2026-10-24).** Re-executed on this branch's tree:

```text
$ cd iot-gateway && python -m pytest tests/test_security_abuse.py -q
69 passed in 6.50s
```

Environment: Windows 11 host, Python 3.14.9, pytest 9.1.1, `iot-gateway` editable install.
Two runs on the same tree returned `69 passed` (6.50s and 5.40s). The node count (69)
matches the CI run; the differing wall-clock and warning count reflect the different
interpreter/dependency set, not a behavioural difference.

**Verdict: KEEP OPEN — named gaps: OTA-signature, Yanshee-skill, authenticated-WS/ACL, replay-to-actuation, and restart-fail-closed tests; dependencies #152/#167 remain open.** Dependencies block closure: the threat model calls WebSocket auth unimplemented (`threat-model.md:512`) and dashboard session evidence belongs to unmerged #242.

**Evidence class:** the merged `test_security_abuse.py` suite and CI run
[#39717529906](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906) are
**Class A (repository-verifiable)** evidence, and they are the only class that can close
this issue — but they cover only part of the checklist, so the verdict stays KEEP OPEN.
The remaining checklist items are Class A gaps (missing repository test nodes), while the
deployed-broker ACL/TLS, signed-OTA-image and Yanshee-hardware items are **Class B
release gates**; no Class B evidence exists for them, and even if it did, it could not
close this issue.

| Checklist item | Status | Merged-master evidence / test mapping | Conclusion |
|---|---|---|---|
| SPEC-1 — boundaries across browser/auth/ACL/OTA/UART/Mega/Unity/Yanshee | **PARTIAL** | Boundaries `threat-model.md:24-70`; React/Unity/MiniAlpha `:35-41`; no OTA or Yanshee term. | Major boundaries modelled; required OTA/Yanshee coverage missing. |
| SPEC-2 — injection/replay/spoof/stale/OTA/webhook/actuation threats | **PARTIAL** | STRIDE `:104-179`; abuse cases `:254-475`; risk matrix `:526-545`. | Injection/spoof/webhook/staleness covered; OTA downgrade absent; replay is a known limitation. |
| SPEC-3 — human/device/service roles, least-privilege ACL, rotation matrix | **NOT MET** | One operator token `:90-100`; no Viewer/Operator/Supervisor/Admin matrix; no rotation `:113`; broker ACL proposed `:492`. | Required role/ACL/rotation matrix absent. |
| SPEC-4 — local E-stop, safe startup, fail-closed auth, audit separate from AI | **PARTIAL** | Safety gate `:343-370`; local safety intent `factory-interface.md:343-350`. | Token failure is fail-closed; no safe-startup or end-to-end separation proof. |
| SPEC-5 — API/WS/MQTT/UART/OTA/Yanshee denial fixtures | **PARTIAL** | 69 #245 nodes; bridge CRC/duplicate tests separately at `esp32-ukit-bridge/tests/python/test_protocol.py:14-68`, `test_simulator.py:19-27`; no OTA/Yanshee node. | API/MQTT/token/queue fixtures exist; OTA manifest/Yanshee/WS-auth fixtures absent. |
| SPEC-6 — risk acceptance and staged sim vs authorized physical gate | **PARTIAL** | Risk roadmap `:526-565`; evidence levels `:587-597`. | Risks/levels published, but no accepted risk decision or executable stage gate. |
| TC-1 — Viewer cannot bypass policy by raw API or broker | **NOT MET** | Closest: `TestOperatorTokenAuth::test_missing_token_returns_401`; `TestPrivilegeEscalation::test_incident_ack_without_token_rejected`; `...::test_operator_override_without_token_rejected`. | Token denial is tested; no Viewer role or MQTT ACL test. |
| TC-2 — replay/stale context cannot trigger actuation | **NOT MET** | `TestTelemetryAnomalyInjection::test_stale_event_flagged`; `...::test_out_of_order_events_detected`; dedup eviction replay is known limitation (`abuse-case-tests.md:777-790`). | Stale marking is not replay-to-actuation prevention. |
| TC-3 — invalid OTA signature never accepted | **NOT MET** | No suite node; `api.py:698-718` stores optional SHA-256 only (`firmware_sha256` at `:700` and `:717`; the string `signature` does not occur in that file); ADR-0007 requires a signature ([`adr-0007-signed-ota-ab-rollback.md:16-27`](https://github.com/vinhphan812/smart-factory/blob/bcc8848bf2ff65aaa4e69b7d8d0c705cd73edd20/docs/adr/adr-0007-signed-ota-ab-rollback.md#L16-L27)). | Missing signature-rejection implementation/test. Open #248/#74 carry OTA work. |
| TC-4 — disconnection/restart fail closed | **NOT MET** | Closest: bounded WebSocket queue nodes `TestDoSRateLimiting::test_broadcast_queue_full_drops_lagging_clients` and `TestDoSResourceExhaustion::test_websocket_max_queue_per_client_enforced`. | Bounded resources do not prove restart/interlock fail-closed behavior. |
| TC-5 — abuse tests run in CI without hardware | **MET (L1)** | 69-node output above; CI run [#39717529906](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906) (jobs [119623125531](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906/job/119623125531), [119623125386](https://github.com/vinhphan812/smart-factory/actions/runs/39717529906/job/119623125386)); suite header says external services are mocked (`test_security_abuse.py:1-20`). | Verified L1 CI suite, no hardware claim. |
| DoD — sources, fixtures, commands/logs, CI and acceptance | **PARTIAL** | Sources and CI evidence exist; checklist coverage is incomplete. | Cannot close. |

### Explicit TC-to-node cross-reference

| TC | Specific node IDs | Result |
|---|---|---|
| TC-1 | `TestOperatorTokenAuth::test_missing_token_returns_401`; `TestPrivilegeEscalation::test_incident_ack_without_token_rejected`; `...::test_operator_override_without_token_rejected` | Partial only. |
| TC-2 | `TestTelemetryAnomalyInjection::test_stale_event_flagged`; `...::test_out_of_order_events_detected` | Partial only. |
| TC-3 | *No test node exists.* | Not met. |
| TC-4 | `TestDoSRateLimiting::test_broadcast_queue_full_drops_lagging_clients`; `TestDoSResourceExhaustion::test_websocket_max_queue_per_client_enforced` | Partial only. |
| TC-5 | All 69 `tests/test_security_abuse.py` nodes | Met at L1. |

---

## #152 — Dashboard authenticated session, RBAC, lineage

**Verdict: KEEP OPEN — blocker: unmerged PR #242.** `gh pr view 242` reported `state: OPEN`, `mergedAt: null` as of 2026-10-22. See [Live status re-verification (2026-10-24)](#live-status-re-verification-2026-10-24) for a later check.

Master evidence (line references resolve against the audited master SHA `3d7d7ca`): `dashboard/README.md:39` says acknowledgement is browser-memory demo with no backend persistence/authentication; `dashboard/src/services/api/client.ts:20-152` makes unauthenticated fetches; current master has no `iot-gateway/src/iot_gateway/auth.py`. Do not guess a post-merge residual gap: re-audit #242 only after it merges.

**Evidence class:** **Class A (repository-verifiable)** — the blocker is the absence of merged
auth/RBAC/lineage source and tests in the repository, and only Class A evidence can close
this issue once PR #242 merges and its artefacts are independently verifiable in the
repository. The separate Class B release gate (deployed HTTPS, CORS and CSP headers, HSTS
and certificate management on the served dashboard) is outstanding, is not observable from
this repository, and cannot close this issue.

## #167 — Gateway HTTP/WebSocket auth and scoped permissions

**Verdict: KEEP OPEN — blocker: unmerged PR #242.** As of 2026-10-22, master had no `auth.py`; reads are directly exposed at `iot-gateway/src/iot_gateway/api.py:203-339`, while selected writes use only `SAFETY_OPERATOR_TOKEN` (`:26-52,354-455`). The threat model records WS auth absent (`threat-model.md:512`) and no auth-endpoint rate limit (`:534`); anonymous WS is documented as an expected/future gap (`abuse-case-tests.md:652-675`). Re-audit #242 after merge.

**Evidence class:** **Class A (repository-verifiable)** — closure requires merged gateway
auth source and tests in the repository, independently verifiable after PR #242 merges.
The separate Class B release gate (deployed TLS termination, deployed broker ACL, HSTS
and certificate management on the live endpoint) is outstanding, is not observable from
this repository, and cannot close this issue.

## #182 — Reproducible deployment topology, health, DR

**Verdict: KEEP OPEN — blocker: unmerged PR #244.** As of 2026-10-22, master had MQTT/MQTT-TLS compose and separate FIWARE compose only; no `docker-compose.full.yml`, no `LOCAL_SIM`/`LAB_HIL`/`PRODUCTION_READONLY` profiles, no deployment smoke script, and no gateway backup/restore implementation. Run actual #244 compose/smoke/DR evidence only after merge.

**Evidence class:** **Class A (repository-verifiable)** — closure requires the merged
deployment topology, profile definitions, smoke script and DR artefacts in the repository
after PR #244 merges. The separate Class B release gate (live multi-container integration
and DR rehearsal on a deployed environment) is outstanding, is not observable from this
repository, and cannot close this issue.

## #186 — Executable migrations and backup/restore

**Verdict: KEEP OPEN — blocker: unmerged PR #244.** As of 2026-10-22, `EventStore._migrate_schema()` (`iot-gateway/src/iot_gateway/event_store.py:126-179`) added a fixed timing-column list but master had neither a schema-version table nor executable backup/restore. `iot-gateway/migrations/001_add_timing_columns.md` is informational. Intended `schema_version.py`, `backup_restore.py`, and migration tests exist only in #244.

**Evidence class:** **Class A (repository-verifiable)** — closure requires the merged
schema-version table, executable backup/restore code and migration tests in the repository
after PR #244 merges. The separate Class B release gate (restore rehearsal against a live
deployed database, with deployed backup retention in force) is outstanding, is not
observable from this repository, and cannot close this issue.

## #180 — Full-stack simulation and multi-service E2E

**Verdict: KEEP OPEN — blocker: unmerged PR #244.** As of 2026-10-22, `integration-tests/README.md:1-27` labelled the harness **PLANNED**; the directory had no scenarios, fixtures, harness, reports, or CI job. The intended `e2e/simulation/` and `e2e-simulation.yml` exist only in #244.

**Evidence class:** **Class A (repository-verifiable)** — closure requires the merged E2E
harness, scenarios, fixtures and CI job in the repository after PR #244 merges. The
separate Class B release gate (live multi-container integration run, with the deployed
CORS/CSP and HSTS posture actually observed) is outstanding, is not observable from this
repository, and cannot close this issue.

## Tracked Gap Recommendation

#174 exposes a real gap not implemented by #242/#244: turning the L0 matrix into versioned executable schema, capability admission validation, all-module fixture library, registry binding, and Unity mapping. Existing #57/#58/#59/#68/#98 cover parts, but no open PR implements the integrated matrix-to-runtime contract.

**Recommended issue title (do not create automatically):**

> `[P1][PHYSICAL] Implement versioned nine-module capability schema, controller admission tests, and simulator fixture library from #174 matrix`

Acceptance should require schema compatibility review, registry/Unity mapping, normal/jam/missing-sensor/limit/E-stop/offline/calibration-expiry fixtures, TC-2/TC-3/TC-5 negative tests, L2 run hashes, and separately labelled L3/L4 evidence.

## Live status re-verification (2026-10-24)

Re-queried live GitHub state to test whether the 2026-10-22 snapshot is still accurate.
This re-check **does not close any issue**; it only records that the snapshot's verdicts
still hold at this timestamp. Future readers must repeat the same queries.

```text
$ for i in 152 174 179 167 182 186 180; do gh api repos/vinhphan812/smart-factory/issues/$i --jq '"#\(.number) \(.state) updated=\(.updated_at) closed=\(.closed_at // "-")"'; done
$ for p in 242 244 245 256; do gh api repos/vinhphan812/smart-factory/pulls/$p --jq '"PR#\(.number) state=\(.state) merged=\(.merged) mergedAt=\(.merged_at // "-") head=\(.head.sha) updated=\(.updated_at)"'; done
```

Observed at 2026-10-24 (UTC):

| Issue | State | Last updated |
|---|---|---|
| #152 | `open` | 2026-10-20 |
| #174 | `open` | 2026-10-20 |
| #179 | `open` | 2026-10-20 |
| #167 | `open` | 2026-10-20 |
| #182 | `open` | 2026-10-20 |
| #186 | `open` | 2026-10-20 |
| #180 | `open` | 2026-10-20 |

| PR | State | Head SHA | Merged at |
|---|---|---|---|
| #242 | `open`, not merged | `986f00279e615f1717cb9e2f4d07f8760452d917` | — |
| #244 | `open`, not merged | `6ebd8cc4c5d5e5b55148e65363847e90c3a3c700` | — |
| #245 | `closed`, merged | `bea5a59d16e3fa69e1101ecf7af167db4e84ea3a` | 2026-10-22T03:33:51Z |
| #256 | `closed`, merged | `8526805d7a77055888752810e7a19569a0f1d9df` | 2026-10-22T03:34:20Z |

**Conclusion:** no status changed in a way that affects any verdict. All seven issues
remain `open`; the two blocking PRs (#242, #244) remain unmerged, so the KEEP OPEN
verdicts and their named gaps stand unchanged as at 2026-10-24.

### Second requery — 2026-10-24 07:33:31 UTC (14:33:31 GMT+0700)

A second requery was executed while preparing the evidence-lifetime and release-boundary
sections of this document, to demonstrate the requery rule in practice rather than
assert it.

```text
$ date -u
Sat, Oct 24, 2026  7:33:31 AM
$ for i in 152 174 179 167 182 186 180; do gh api repos/vinhphan812/smart-factory/issues/$i --jq '"#\(.number) \(.state) updated=\(.updated_at) closed=\(.closed_at // "-")"'; done
#152 open updated=2026-10-20T13:01:38Z closed=-
#174 open updated=2026-10-20T13:02:50Z closed=-
#179 open updated=2026-10-20T13:01:46Z closed=-
#167 open updated=2026-10-20T13:01:30Z closed=-
#182 open updated=2026-10-20T13:01:51Z closed=-
#186 open updated=2026-10-20T13:02:40Z closed=-
#180 open updated=2026-10-20T13:02:47Z closed=-
$ for p in 242 244 245 256; do gh api repos/vinhphan812/smart-factory/pulls/$p --jq '"PR#\(.number) state=\(.state) merged=\(.merged) mergedAt=\(.merged_at // "-") head=\(.head.sha) updated=\(.updated_at)"'; done
PR#242 state=open merged=false mergedAt=- head=986f00279e615f1717cb9e2f4d07f8760452d917 updated=2026-10-24T06:57:55Z
PR#244 state=open merged=false mergedAt=- head=614ed31f2844bc910061ec9e665d27186d865d3e updated=2026-10-24T07:15:04Z
PR#245 state=closed merged=true mergedAt=2026-10-22T03:33:51Z head=bea5a59d16e3fa69e1101ecf7af167db4e84ea3a updated=2026-10-22T03:33:51Z
PR#256 state=closed merged=true mergedAt=2026-10-22T03:34:20Z head=8526805d7a77055888752810e7a19569a0f1d9df updated=2026-10-22T03:34:20Z
```

**What changed between the two 2026-10-24 requeries:** PR #244's head SHA moved from
`6ebd8cc4c5d5e5b55148e65363847e90c3a3c700` to
`614ed31f2844bc910061ec9e665d27186d865d3e` (updated `2026-10-24T07:15:04Z`), and PR #242
was touched at `2026-10-24T06:57:55Z`. All seven issues remain `open`; both blocking PRs
remain **unmerged**; #245 and #256 remain merged at the same commits.

**This is exactly why the requery rule exists.** The earlier head SHA recorded for #244
is now stale, and the KEEP OPEN verdict for #182, #186 and #180 is nevertheless
unchanged — because it rests on *merged* repository state, not on the PR head. A verdict
that had been anchored to the PR head alone would have needed re-derivation; a verdict
anchored to `origin/master` did not. The recorded head SHA for #244 is therefore
superseded by `614ed31f2844bc910061ec9e665d27186d865d3e`, and no claim in this document
depends on the superseded value.

**Conclusion of this requery:** all seven issues remain `open`; no issue is closed by
this document.

### Third requery — 2026-10-24 11:26:49 UTC (18:26:49 GMT+0700)

Executed while preparing the
[Snapshot Staleness and Branch Movement](#snapshot-staleness-and-branch-movement) and
[Revalidation Procedure](#revalidation-procedure) sections, so that the moved PR heads
are recorded with their live SHA rather than asserted.

```text
$ date -u
Sat, Oct 24, 2026 11:26:49 AM
$ for i in 152 174 179 167 182 186 180; do gh api repos/vinhphan812/smart-factory/issues/$i --jq '"#\(.number) \(.state) updated=\(.updated_at) closed=\(.closed_at // "-")"'; done
#152 open updated=2026-10-20T13:01:38Z closed=-
#174 open updated=2026-10-20T13:02:50Z closed=-
#179 open updated=2026-10-20T13:01:46Z closed=-
#167 open updated=2026-10-20T13:01:30Z closed=-
#182 open updated=2026-10-20T13:01:51Z closed=-
#186 open updated=2026-10-20T13:02:40Z closed=-
#180 open updated=2026-10-20T13:02:47Z closed=-
$ for p in 242 244 245 256 258 259 260 261 262; do gh api repos/vinhphan812/smart-factory/pulls/$p --jq '"PR#\(.number) state=\(.state) merged=\(.merged) mergedAt=\(.merged_at // "-") head=\(.head.sha) updated=\(.updated_at)"'; done
PR#242 state=open merged=false mergedAt=- head=c0a7a20ec3cf221334173a9200beacef80e666d5 updated=2026-10-24T10:36:36Z
PR#244 state=open merged=false mergedAt=- head=614ed31f2844bc910061ec9e665d27186d865d3e updated=2026-10-24T10:26:03Z
PR#245 state=closed merged=true mergedAt=2026-10-22T03:33:51Z head=bea5a59d16e3fa69e1101ecf7af167db4e84ea3a updated=2026-10-22T03:33:51Z
PR#256 state=closed merged=true mergedAt=2026-10-22T03:34:20Z head=8526805d7a77055888752810e7a19569a0f1d9df updated=2026-10-22T03:34:20Z
PR#258 state=open merged=false mergedAt=- head=f7f085e8155adc12f2ab637392b2d535e2a1c262 updated=2026-10-24T10:24:33Z
PR#259 state=open merged=false mergedAt=- head=8332f01cd25f1a2ab2ddc4b5d3371803be4c6c12 updated=2026-10-24T10:24:28Z
PR#260 state=open merged=false mergedAt=- head=0c422e867993fcf046b2c21db0283cdae4480f57 updated=2026-10-24T10:24:22Z
PR#261 state=open merged=false mergedAt=- head=b9c1b46aca883648cec1197c6ae2a0ca1e508492 updated=2026-10-24T10:52:17Z
PR#262 state=open merged=false mergedAt=- head=e438ae5f58ef0beddd4d1725d4b82b3f1a1235ea updated=2026-10-24T10:24:02Z
$ git rev-parse origin/master
3d7d7ca5e8413566637a50e83c1e5fbe2722977f
```

**What changed since the second requery:** PR #242's head SHA moved again, from
`986f00279e615f1717cb9e2f4d07f8760452d917` to
`c0a7a20ec3cf221334173a9200beacef80e666d5` (last commit authored 2026-10-24T10:36:25Z).
PR #244's head is unchanged at `614ed31f2844bc910061ec9e665d27186d865d3e`. The
remaining open PRs (#258, #259, #260, #261, #262) are anchored for the first time in
the staleness table above. `origin/master` is **still** `3d7d7ca5e8413566637a50e83c1e5fbe2722977f`,
so the audited tree and its file-and-line citations are not yet stale — but every
verdict that names a PR head is anchored only to that head, and #242's head has now moved
twice within a single day.

**Conclusion of this requery:** all seven audited issues remain `open`; #242 and #244
remain **unmerged**; no issue is closed by this document.

## ADR Allocation Consistency

The ADR allocation in force is recorded here so that this audit cannot be read as
renumbering or superseding any ADR. This document introduces **no** ADR and renumbers
**no** ADR; the mapping below is a restatement of the allocation already agreed, not a
new decision.

| PR | ADR(s) allocated | Note |
|---|---|---|
| #260 | ADR-0016 | `docs/adr/adr-0016-dashboard-module-registry.md` in the PR branch |
| #261 | ADR-0017 and ADR-0018 | `adr-0017-fiware-context-deployment-safety-and-schema-gates.md`, `adr-0018-fiware-yanshee-context-mapping.md` in the PR branch |
| #242 | ADR-0019 (renumber pending) | The PR branch currently carries `adr-0016-lineage-persistence-deduplication-and-concurrency.md`; the number collides with #260's ADR-0016 and is pending renumber to ADR-0019. |

All three PRs remain **unmerged**, so none of ADR-0016, ADR-0017, ADR-0018 or ADR-0019
exists in `origin/master`; the merged ADR index still ends at ADR-0015. None of these
ADRs is therefore repository-verifiable closure evidence for any issue audited here, and
the renumbering of #242's ADR is left to the ADR owner and is out of scope for this
documentation-only PR.

## Closure Comment Actions

No issue is fully met, so **no GitHub issue is closed**. Comment each issue with its blocker: #152/#167 → #242; #174 → L0-only gap plus #173/#98; #179 → #245 L1 suite passes but gaps and #152/#167 remain; #182/#186/#180 → #244. No physical/HIL/integrated-factory success is claimed.

Each such comment must state, for its issue, the **Class A** gap that remains, note that
the **Class B** release gate is still open, and carry the requery timestamp of the
moment the comment was written. A comment that quotes this document's verdict must also
carry the observation date it was taken on, per the
[Evidence Lifetime and Requery Rule](#evidence-lifetime-and-requery-rule).

## Release Boundary Classification

Closure evidence and release evidence are different things. This audit separates them
explicitly so that a repository observation is never mistaken for a release acceptance.

### Class A — repository-verifiable closure evidence

Evidence that can be checked inside this repository at a named commit SHA: a merged
commit on `origin/master`, source or test files in that tree, an executable test result,
or an immutable CI run URL anchored to a head SHA.

**Class A is the only class that can close an issue.** Closure requires Class A evidence
*for that specific issue* — the merged artefact, and the test or run that demonstrates it,
must both be independently verifiable in the repository.

### Class B — external release gates

Evidence that lives outside the repository, in a deployed environment or on physical
hardware:

- deployed HTTPS termination, CORS and CSP header configuration;
- HSTS and certificate management (issuance, renewal, expiry) on the live endpoint;
- hardware proof — physical E-stop, safety interlock actuation, measured pinouts,
  on-device broker/OTA behaviour, Yanshee robot capability;
- live multi-container integration — the deployed compose topology running the full
  service set, and a DR/restore rehearsal against a live system.

**Class B evidence can never close an issue, on its own or in combination.** It is
recorded here as an outstanding release gate, never as closure evidence. Class B gates
are outside the scope of a documentation-only PR and cannot be satisfied by any document,
test suite or CI run in this repository.

### Per-issue classification

Each audited issue states which class its evidence belongs to, and which class is still
outstanding.

| Issue | Class A evidence held (repository-verifiable) | Class A gap blocking closure | Class B release gate (outstanding, cannot close the issue) |
|---|---|---|---|
| #152 | None — no merged auth/RBAC/lineage source in `origin/master` | PR #242 unmerged | Deployed HTTPS, CORS/CSP, HSTS and certificate management on the served dashboard |
| #174 | `contracts/physical/capability-matrix.md` at `961298b` (L0 design contract only) | No versioned executable schema, fixture library or negative tests | Hardware proof: measured pinout/tolerance, physical E-stop and interlock actuation |
| #179 | `iot-gateway/tests/test_security_abuse.py` at `bcc8848`, CI run #39717529906 (L1, 69 nodes) | Missing OTA-signature, Yanshee, authenticated-WS/ACL, replay-to-actuation and restart-fail-closed nodes; dependencies #152/#167 open | Deployed broker ACL/TLS, signed-OTA image validation, Yanshee HIL capability |
| #167 | None — no `auth.py` in `origin/master` | PR #242 unmerged | Deployed TLS termination and deployed broker ACL, HSTS and certificate management |
| #182 | None — no `docker-compose.full.yml` or smoke/DR implementation in `origin/master` | PR #244 unmerged | Live multi-container integration and DR rehearsal on the deployed topology |
| #186 | `EventStore._migrate_schema()` timing columns only; migration note is informational | PR #244 unmerged — no schema-version table, no executable backup/restore | Restore rehearsal against a live deployed database with deployed retention in force |
| #180 | `integration-tests/README.md` states PLANNED | PR #244 unmerged — no scenarios, fixtures, harness or CI job | Live multi-container integration run with deployed CORS/CSP and HSTS posture observed |

**Governing rule.** An issue may be marked closed only on Class A evidence for that
issue. Class B evidence is never a substitute for it, and no issue in this audit is
marked closed on the basis of the external class — no Class B evidence exists for any of
them in any case.

## Explicit Limitations (non-closable by this audit)

The evidence gathered here is L0 (design/static) and L1 (host unit). It **does not** and
**cannot** establish any of the following, regardless of how green the CI run was. Every
row below is a **Class B external release gate** under the
[Release Boundary Classification](#release-boundary-classification) section — none of them
is closure evidence for any issue:

| Capability | Why this audit cannot close it | Required evidence level |
|---|---|---|
| Physical E-stop / safety interlock | No physical actuation or operator override was exercised; L0 matrix rules and mocked tests are design intent only. | L3 bench / L4 HIL |
| OTA signature validation | `api.py` stores an optional SHA-256 only; no signature is verified or rejected by any test. | L1 executable test + L3 signed-image test |
| MQTT ACL / TLS | Broker authorisation and transport security were not exercised; ADR-0010 is `Status: Proposed` and states it "does not claim that a broker ACL, TLS listener, or client configuration is already implemented". | L2 simulation against a real broker + L3 TLS test |
| Yanshee SDK / HIL capability | Issue #179 SPEC-5 requires a denial fixture for an unsupported Yanshee skill; the merged `iot-gateway/tests/test_security_abuse.py` contains no Yanshee or skill node (`grep -i "yanshee\|skill"` returns nothing), and no vendor SDK call was executed. | L4 HIL on Yanshee hardware |
| Authenticated WebSocket | WS auth is recorded as unimplemented in the threat model; anonymous access is a documented gap. | L1 server test + L3 session test |
| Deployment / DR / migration | `docker-compose.full.yml`, backup/restore and schema versioning exist only in unmerged PR #244. | L2/L3 run on the deployment topology |

Green CI, merged Markdown and this audit are **not** deployment or hardware acceptance
evidence. Any future closure action must (a) re-query live issue/PR state, (b) supply
**Class A** evidence at the level named in the table above, and (c) treat every Class B
release gate as still open regardless of what Class A evidence shows. Under the
[Evidence Lifetime and Requery Rule](#evidence-lifetime-and-requery-rule), the re-query
must be taken **immediately before** the closure claim is made, and this document's own
verdicts are not a substitute for it.

---

## Non-Negotiable Limitations of L0/L1/L2 Evidence

This section is **binding and non-negotiable**. It is stated separately, and in full, so
that it cannot be lost in a summary, a paraphrase, or a quotation of only the verdict
tables above.

The evidence gathered by this audit is **L0 (design/static) and L1 (host unit)**, plus
**L2 (simulation)** in the cases where a simulator exists. Green CI, merged Markdown,
L0 contracts and L1 test nodes **cannot certify** any of the capabilities listed below.
Each item requires **external and/or physical evidence** at the level stated. **No
closure action may treat any item below as satisfied by this document, by this
repository, or by any CI run.**

| # | Capability that L0/L1/L2 evidence CANNOT certify | Why this audit cannot certify it | External / physical evidence required | Level needed |
|---|---|---|---|---|
| L-1 | **Physical E-stop function** (actual operator press → actuator stop) | No physical actuation was performed. The capability matrix is an L0 design contract that itself marks electrical validation `BLOCKED-L3`; the abuse suite mocks external services. | A physical E-stop press on the real module with the actuator observed to stop, plus interlock actuation and operator-override evidence, recorded against a hardware session | **L3 bench, L4 HIL for the in-line safety loop, and L5 integrated for the full operator-to-actuator chain** |
| L-2 | **OTA signature verification** (a tampered/unsigned image must be rejected) | `api.py` records an optional SHA-256 only; no signature is verified or rejected by any test node. ADR-0007 requires a signature that no merged code enforces. | A signed-image install on real hardware plus a negative test showing an invalid-signature image is rejected before flash, on the device | **L1 executable negative test (repository), plus L3 signed-image test on device** |
| L-3 | **OTA A/B rollback** (a failed update must roll back to the previous slot) | ADR-0007 (`docs/adr/adr-0007-signed-ota-ab-rollback.md`) is `Status: Proposed`; the A/B slot layout it specifies is not implemented in `origin/master` (no slot state machine, no slot switch, no failure-injection test — the OTA control plane records a status string only, `ota_control.py:178`), and no device was booted or interrupted mid-update. | Interrupted-update and bricked-slot scenarios on real hardware with observed automatic rollback to the previous bootable slot | **L3 bench, and L4 HIL for field recovery** |
| L-4 | **Broker TLS/ACL enforcement at runtime** (authorisation actually denied by the broker) | Broker authorisation and transport security were never exercised against a running broker; ADR-0010 is `Status: Proposed` and explicitly disclaims any implemented broker ACL, TLS listener or client configuration. The CI suite mocks the broker. | A real broker with TLS termination and per-role ACLs, showing a Viewer denial and an authorised Operator path, with certificates and configuration captured from the deployed endpoint | **L2 simulation against a real broker, plus L3 TLS/ACL test on the deployed broker** |
| L-5 | **Yanshee SDK capability behaviour** (what the SDK actually does on Yanshee hardware) | The merged `iot-gateway/tests/test_security_abuse.py` contains no Yanshee or skill node (`grep -i "yanshee\|skill"` returns nothing), and no vendor SDK call was executed anywhere in this audit. | The Yanshee robot on hardware, with the SDK's real capability surface exercised and the unsupported-skill denial fixture observed, against the vendor SDK version in use | **L4 HIL on Yanshee hardware** |
| L-6 | **Real browser / gateway session acceptance** (an authenticated, authorised user session end to end) | The threat model records WebSocket auth as unimplemented and anonymous WS access as a documented gap; the dashboard client makes unauthenticated fetches and the acknowledgement path is browser-memory demo only. No browser or live gateway session was driven by this audit. | An authenticated browser session against a deployed gateway and dashboard, with token lifecycle, RBAC enforcement, CSP/CORS/HSTS headers and WebSocket authorisation observed | **L1 server test, plus L3 deployed session test** |

**Governing rules for this section.**

1. **None of L-1 … L-6 is closure evidence for any issue.** Each is an outstanding
   **Class B external release gate** under
   [Release Boundary Classification](#release-boundary-classification). Even a completed
   physical or deployment session would not by itself close any issue audited here; the
   corresponding **Class A** repository evidence is required as well.
2. **The required level is a floor, not a target.** "L1 executable test" for L-2 and L-6
   means a repository test that does not exist today; until it exists, the capability is
   uncertified at every level.
3. **A CI run cannot substitute for the physical level.** No GitHub Actions runner, no
   mocked broker, no simulator and no unit test can produce L3, L4 or L5 evidence.
4. **This document asserts none of L-1 … L-6.** Nothing in this audit may be cited as
   proof of physical E-stop function, OTA signature verification, OTA A/B rollback,
   runtime broker TLS/ACL enforcement, Yanshee SDK capability behaviour, or browser /
   gateway session acceptance. The evidence ceiling of this audit is **L0 static /
   documentation only**.

---

*Signed-off-by: Vinh Phan <vinhphan812@gmail.com>*
