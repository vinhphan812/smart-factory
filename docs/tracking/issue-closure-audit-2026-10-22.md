# Smart Factory — Issue Closure Audit (2026-10-22)

**Auditor:** dev-architect (Kanban `t_353718a4`)  
**Audited ref:** `origin/master` at [`3d7d7ca5e8413566637a50e83c1e5fbe2722977f`](https://github.com/vinhphan812/smart-factory/commit/3d7d7ca5e8413566637a50e83c1e5fbe2722977f)  
**Snapshot date:** 2026-10-22 — this document is a **dated point-in-time snapshot**, not a live status feed.  
**Scope:** Re-derive closure evidence for open Issues #152, #174, #179, #167, #182, #186, and #180. A merged commit, open PR, closed-unmerged PR, and document are distinct evidence states.

> **Snapshot freshness rule.** Every open/closed/merged status recorded below was true on
> **2026-10-22** only. Issue and PR states change; **re-query live GitHub state before any
> future closure action** and before relying on any "still open" claim in this document.
> A later re-check is recorded in [Live status re-verification (2026-10-24)](#live-status-re-verification-2026-10-24).

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

| Issue | Verdict | Named gap / blocker |
|---|---|---|
| #152 | **KEEP OPEN** | PR #242 is open/unmerged. |
| #174 | **KEEP OPEN** | L0 docs only; no versioned executable controller schema, fixture library, or negative tests. |
| #179 | **KEEP OPEN** | Missing required fixtures/tests; dependencies #152 and #167 are open. |
| #167 | **KEEP OPEN** | PR #242 is open/unmerged; master lacks gateway auth module and authenticated WS. |
| #182 | **KEEP OPEN** | PR #244 is open/unmerged. |
| #186 | **KEEP OPEN** | PR #244 is open/unmerged. |
| #180 | **KEEP OPEN** | PR #244 is open/unmerged; `integration-tests/` is PLANNED only. |

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

Live issue/PR state (re-run before any closure action) — see
[Live status re-verification (2026-10-24)](#live-status-re-verification-2026-10-24).

Documentation validation:

```text
$ python scripts/check_adrs.py
$ python -m pytest scripts/tests/test_check_adrs.py -q
```

---

## #174 — Physical capability matrix, typed I/O, controller contracts

**Merged evidence:** PR #256 merge [`961298b642599c71bcdbff1b0879b2f3bda2e9bb`](https://github.com/vinhphan812/smart-factory/commit/961298b642599c71bcdbff1b0879b2f3bda2e9bb) changes exactly one file, [`contracts/physical/capability-matrix.md`](https://github.com/vinhphan812/smart-factory/blob/961298b642599c71bcdbff1b0879b2f3bda2e9bb/contracts/physical/capability-matrix.md) (797 lines). The file labels itself **L0 design contract** (`:3`) and says controller/channel allocation and electrical validation are **BLOCKED-L3** (`:33`). Line references below are to that immutable SHA, not to a moving branch.

**Verdict: KEEP OPEN — named gap: executable physical-controller capability contract and fixture implementation.** As of 2026-10-22, no open PR changed `contracts/physical/`, Mega/uKit firmware, registry capability mapping, or Unity prefabs.

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

## #167 — Gateway HTTP/WebSocket auth and scoped permissions

**Verdict: KEEP OPEN — blocker: unmerged PR #242.** As of 2026-10-22, master had no `auth.py`; reads are directly exposed at `iot-gateway/src/iot_gateway/api.py:203-339`, while selected writes use only `SAFETY_OPERATOR_TOKEN` (`:26-52,354-455`). The threat model records WS auth absent (`threat-model.md:512`) and no auth-endpoint rate limit (`:534`); anonymous WS is documented as an expected/future gap (`abuse-case-tests.md:652-675`). Re-audit #242 after merge.

## #182 — Reproducible deployment topology, health, DR

**Verdict: KEEP OPEN — blocker: unmerged PR #244.** As of 2026-10-22, master had MQTT/MQTT-TLS compose and separate FIWARE compose only; no `docker-compose.full.yml`, no `LOCAL_SIM`/`LAB_HIL`/`PRODUCTION_READONLY` profiles, no deployment smoke script, and no gateway backup/restore implementation. Run actual #244 compose/smoke/DR evidence only after merge.

## #186 — Executable migrations and backup/restore

**Verdict: KEEP OPEN — blocker: unmerged PR #244.** As of 2026-10-22, `EventStore._migrate_schema()` (`iot-gateway/src/iot_gateway/event_store.py:126-179`) added a fixed timing-column list but master had neither a schema-version table nor executable backup/restore. `iot-gateway/migrations/001_add_timing_columns.md` is informational. Intended `schema_version.py`, `backup_restore.py`, and migration tests exist only in #244.

## #180 — Full-stack simulation and multi-service E2E

**Verdict: KEEP OPEN — blocker: unmerged PR #244.** As of 2026-10-22, `integration-tests/README.md:1-27` labelled the harness **PLANNED**; the directory had no scenarios, fixtures, harness, reports, or CI job. The intended `e2e/simulation/` and `e2e-simulation.yml` exist only in #244.

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

## Closure Comment Actions

No issue is fully met, so **no GitHub issue is closed**. Comment each issue with its blocker: #152/#167 → #242; #174 → L0-only gap plus #173/#98; #179 → #245 L1 suite passes but gaps and #152/#167 remain; #182/#186/#180 → #244. No physical/HIL/integrated-factory success is claimed.

## Explicit Limitations (non-closable by this audit)

The evidence gathered here is L0 (design/static) and L1 (host unit). It **does not** and
**cannot** establish any of the following, regardless of how green the CI run was:

| Capability | Why this audit cannot close it | Required evidence level |
|---|---|---|
| Physical E-stop / safety interlock | No physical actuation or operator override was exercised; L0 matrix rules and mocked tests are design intent only. | L3 bench / L4 HIL |
| OTA signature validation | `api.py` stores an optional SHA-256 only; no signature is verified or rejected by any test. | L1 executable test + L3 signed-image test |
| MQTT ACL / TLS | Broker authorisation and transport security were not exercised; ADR-0010 is `Status: Proposed` and states it "does not claim that a broker ACL, TLS listener, or client configuration is already implemented". | L2 simulation against a real broker + L3 TLS test |
| Yanshee SDK / HIL capability | Issue #179 SPEC-5 requires a denial fixture for an unsupported Yanshee skill; the merged `iot-gateway/tests/test_security_abuse.py` contains no Yanshee or skill node (`grep -i "yanshee\|skill"` returns nothing), and no vendor SDK call was executed. | L4 HIL on Yanshee hardware |
| Authenticated WebSocket | WS auth is recorded as unimplemented in the threat model; anonymous access is a documented gap. | L1 server test + L3 session test |
| Deployment / DR / migration | `docker-compose.full.yml`, backup/restore and schema versioning exist only in unmerged PR #244. | L2/L3 run on the deployment topology |

Green CI, merged Markdown and this audit are **not** deployment or hardware acceptance
evidence. Any future closure action must (a) re-query live issue/PR state, and (b) supply
evidence at the level named in the table above.

---

*Signed-off-by: Vinh Phan <vinhphan812@gmail.com>*
