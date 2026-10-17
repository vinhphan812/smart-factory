# Reproducible experiments and baseline methodology

This runbook defines how to compare the Smart Factory gateway, Digital Twin, safety gate and OTA workflows without treating a simulator or a queued message as proof of physical behavior. Every result is labelled by evidence level (L0-L5) from `testing-and-acceptance.md` and records what is implemented, simulated, blocked or hardware-validated.

## 1. Experiment taxonomy and evidence boundaries

| Type | Minimum setup | Primary claim | Required negative cases |
|---|---|---|---|
| Unit (L1) | Host tests with deterministic fixtures | parser, state machine or policy rule behaves for specified inputs | malformed, duplicate, stale and boundary input |
| Integration (L2) | Simulated UART/MQTT and mock device | module contracts, correlation and recovery work together | broker loss, retry, reorder, timeout |
| Simulation (L2) | Recorded or generated plant/device model | system behavior under controlled load and faults | injected loss, delay, clock skew and unsafe request |
| Bench (L3) | ESP32 and controller on a controlled bench | electrical/link interoperability and measured transport behavior | disconnect, reset, invalid command; operator/E-stop precheck |
| HIL (L4) | Actual moving subsystem with operator and E-stop | bounded physical actuation and local safety behavior | jam, sensor timeout, emergency stop, power/broker loss |
| E2E (L5) | Factory -> gateway -> Twin -> MiniAlpha with declared real/mock mix | end-to-end scenario trace and recovery | all applicable E01-E12 acceptance cases |

Offline simulator runs are the deterministic baseline. Online simulator runs use the deployed service path and broker timing. Hardware runs are a separate stratum, never pooled with simulation. If hardware is unavailable, report `BLOCKED` for hardware claims rather than `PASS`.

### Success and failure rules

Before collecting data, register the hypothesis, primary metric, comparison, exclusion rules and target evidence level. A run is `PASS` only when the pre-registered criterion and all safety/negative-case checks pass. A metric can be numerically successful while the experiment is `FAIL` if an unsafe action, lost audit record, unreproducible run or unapproved hardware condition occurs. `INCONCLUSIVE` means the setup or data quality prevents the planned comparison; it is not a pass.

## 2. Common protocol

1. Pin the repository commit, firmware image, schema version, configuration, simulator/model version, broker version, OS/toolchain and test data SHA-256.
2. Define the scenario seed, device IDs, clock source/time synchronization method, payload generator and fault schedule before the run.
3. Synchronize clocks where possible. Also record monotonic timestamps at each boundary; do not infer latency from wall-clock timestamps alone.
4. Execute a warm-up that is excluded from analysis, then collect the pre-registered number of repetitions. Do not change load, thresholds or filtering after observing outcomes.
5. Store raw events, commands, responses, faults and operator actions. Keep derived metrics as a separate immutable output with the script version that produced them.
6. Repeat the same protocol for each baseline and treatment. Randomize or counterbalance run order when thermal, queue or time effects could bias results.
7. Publish a manifest, aggregate table, confidence intervals and all exclusions. Retain enough raw data to replay the scenario and regenerate the aggregate.

### Run manifest (one JSON/YAML record per run)

Required fields: `run_id`, UTC start/end, commit SHA, branch, dataset/model SHA, schema versions, firmware/build ID, configuration hash, simulator or hardware ID, evidence level, scenario seed, repetition count, fault schedule, clock method, instrument versions, operator/E-stop checklist result, raw-data URI, analysis-script SHA and status (`PASS`, `FAIL`, `INCONCLUSIVE`, `BLOCKED`). Never store secrets or identifiable participant data.

### Retention and reproducibility

Keep raw event logs and command traces for the project retention period, plus the manifest and derived results permanently with the release/research record. A result is reproducible only if a clean checkout can resolve the recorded dependency versions, replay the seed/fault schedule and regenerate the reported values within the stated numerical tolerance. Large or sensitive data may be stored outside Git, but its immutable URI, access class and checksum must remain in the manifest.

## 3. Baselines and comparison method

Use at least these baselines where applicable:

- `B0-offline`: deterministic in-process simulator or fixture; establishes algorithmic behavior without network variance.
- `B1-online`: the same scenario through the deployed gateway/broker path with a mock device; estimates service/network overhead.
- `B2-hardware`: the same protocol on the approved bench or HIL setup; reported separately and only when the preflight passes.
- `B3-current`: the current implementation/configuration before a change. It is the paired comparator for a candidate treatment, not a claim that it is correct.

Keep payloads, scenario seeds, offered load, timeout policy and fault schedule identical across paired runs. Compare paired per-seed observations where possible; otherwise report independent-sample estimates and their assumptions. Report median and p95/p99 for skewed latency, loss/duplicate rates with counts and denominators, and bootstrap or distribution-appropriate 95% confidence intervals. For binary safety outcomes report the full confusion matrix (TP, FP, TN, FN), not accuracy alone. Any threshold must be approved before collection; this repository does not invent performance targets.

Default planning counts are starting points, not automatic proof of statistical power: 30 paired repetitions for latency/accuracy characterization, 100 independent trials for synchronization/fault-rate estimates, and 1,000+ command/update attempts for reliability proportions. A final sample size must be justified by the minimum practically important difference, alpha, desired power and expected variance/rate; increase it or label the result exploratory when those inputs are unknown. Report the calculation and seed.

## 4. Experiment designs

### E-TA — Telemetry accuracy

- **Question:** Does normalization preserve the source event and produce the canonical telemetry representation without loss, duplication or unit corruption?
- **Inputs:** A versioned corpus of valid, malformed, duplicate, out-of-order, stale and boundary telemetry; known ground-truth fields and units; fixed seed.
- **Comparators:** B0 parser/fixture output, B1 gateway output, then B2 only if hardware is available.
- **Procedure:** Replay each corpus item at fixed rate and under injected delay/loss/reorder. Join output to ground truth by immutable event/correlation ID; count missing, duplicate, rejected and semantically incorrect fields.
- **Measures:** field-level exact/normalized match, event loss and duplicate rate, rejection reason completeness, timestamp skew and recovery after reconnect.
- **Pass/fail:** PASS requires all pre-registered invariants and no safety-critical corruption; FAIL on any unexplained loss, duplicate action, unit conversion error or missing audit record. Report per-class results, not only aggregate accuracy.

### E-CL — Command latency

- **Question:** What is the distribution from command creation to acknowledgement and, separately, verified device completion?
- **Inputs:** Fixed command mix, payload size, offered rate, timeout/retry policy, network profile and correlation IDs.
- **Comparators:** B0 direct/mock dispatch, B1 gateway/broker path, B2 bench/HIL path.
- **Procedure:** Timestamp creation, gateway receipt, publish, device receipt, acknowledgement and completion with monotonic clocks at each component. Run warm-up, then paired seeds at idle and declared loads; inject broker disconnect and device timeout in separate strata.
- **Measures:** end-to-end and segment p50/p95/p99, timeout/retry counts, duplicate execution count, acknowledgement-to-completion gap. ACK alone is not completion.
- **Pass/fail:** PASS requires the pre-registered latency criterion, zero unsafe duplicate execution and complete correlation; FAIL on missing timestamps, unexplained timeout, or physical actuation without valid authorization.

### E-TS — Twin synchronization fidelity

- **Question:** Does the Digital Twin converge to the authoritative device state and avoid rollback during delay, reorder and reconnect?
- **Inputs:** Recorded authoritative state trace with sequence/version, injected network delay/loss/reorder, reconnect and snapshot-resync events.
- **Comparators:** B0 direct event replay, B1 online gateway-to-Twin path, B2 integrated physical trace when available.
- **Procedure:** Replay identical traces by seed. Measure state at every event and at fixed sampling intervals; verify monotonic version handling, stale indicators and snapshot recovery. Analyze steady-state and fault windows separately.
- **Measures:** state mismatch duration, convergence/recovery time, rollback count, stale-indicator correctness, lost/duplicate events and final-state agreement.
- **Pass/fail:** PASS requires no forbidden rollback, correct stale/recovery classification and final convergence within the pre-registered criterion. Hardware absence makes B2 `BLOCKED`, not a simulated pass.

### E-SG — Safety-gate false positives and negatives

- **Question:** Does the safety policy reject every unsafe request while allowing every approved safe request under defined context?
- **Inputs:** A reviewed, labelled decision corpus including safe, unsafe, stale-context, unsupported-capability, permission, timeout and malformed requests. Labels are frozen before evaluation.
- **Comparators:** B0 reference policy oracle, B1 deployed gateway/policy path, B2 HIL only for actuation verification.
- **Procedure:** Evaluate blinded cases in randomized order. Record request, context version, policy decision, reason and whether any actuator command was emitted. Run adversarial and replay cases separately.
- **Measures:** TP/TN/FP/FN, precision/recall where meaningful, rejection reason coverage, unsafe-action count, audit completeness and decision latency.
- **Pass/fail:** Any false negative that permits unsafe actuation is a safety failure regardless of aggregate score. False positives are reported by class; acceptable rate must be approved before the run. A policy-only simulation cannot claim physical safety.

### E-OTA — OTA reliability

- **Question:** Does an authenticated update complete or recover safely across power, network and broker faults without booting an unverified image?
- **Inputs:** Signed versioned images, device inventory, update cohort, network conditions, fault injection point and rollback policy.
- **Comparators:** B0 local image verification/recovery fixture, B1 simulator/device emulator, B2 approved bench/HIL devices.
- **Procedure:** Verify manifest/signature before transfer. Execute staged update with declared interruption points (disconnect, reboot, power loss where safe). Record boot slot, image digest, health check, rollback and operator intervention. Never use production devices for fault injection.
- **Measures:** completion and recovery proportions with denominators, time-to-healthy, retries, rollback success, digest/signature failures, bricked/unreachable devices and audit completeness.
- **Pass/fail:** PASS requires every tested interruption to end in a verified old or new healthy image and no unsigned/unapproved boot. Any unrecovered device is FAIL and requires incident handling; unavailable hardware is BLOCKED.

## 5. Analysis and reporting checklist

For every experiment publish: protocol version; hypothesis and criterion; baseline/treatment definition; evidence level; environment and manifest; sample-size rationale; raw counts and exclusions; median/p95/p99 or confusion matrix as applicable; confidence interval and analysis method; plots/tables generated from versioned scripts; PASS/FAIL/INCONCLUSIVE/BLOCKED decision; limitations and next experiment. Link results to the relevant E01-E12 acceptance scenario and identify which claims remain simulated or hardware-blocked.
