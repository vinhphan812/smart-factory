# FIWARE / Yanshee Context — Acceptance Boundary

**Owner:** Issue #204 (PR #261)
**Version:** 1.0.0
**Date:** 2026-10-24
**Context:** ADR-0014, ADR-0018, ADR-0017

---

## What is proven in this PR (L1 / L2)

- The read-only FIWARE context facade performs HTTP `GET` only; it has no
  write, upsert, delete or command method.
- The facade can be configured for a credentialed, TLS-protected Orion-LD
  deployment, and refuses a partially-specified secure configuration at
  startup instead of silently downgrading to an unauthenticated plaintext
  read.
- The Yanshee response policy denies on missing Gateway approval, on stale or
  missing observation timestamps, on a non-actionable alert, on a robot entity
  whose `verificationStatus` is not `VERIFIED`, on a skill the robot does not
  report as supported, and on any skill outside the NOTIFICATION category.
  Physical skill topics and an active emergency stop are refused outright.
- These denials are proven over the real `ContextQueryFacade` and the real
  `ContextEntity` parsing path, not only over a fake reader.
- The default robot capability source is `UnverifiedRobotCapabilitySource`:
  every measured field is `UNKNOWN`, `supportedActions` is empty and
  `verificationStatus` is `UNVERIFIED`. No fabricated battery level or status
  is emitted.
- The produced `Robot` entity validates against `contracts/fiware/schemas/robot.json`
  with `jsonschema`.
- `edge-ai-robot` installs from a pinned constraint set; CI records a
  dependency advisory report and a CycloneDX SBOM as retained artifacts.
- The `edge-ai-robot` package is checked by an executable test to contain no
  import of `iot_gateway`.

## What is NOT proven here

| Area | Status | Owner |
|---|---|---|
| Real Yanshee SDK / hardware read | **Not verified.** `verificationSource` remains `unverified-no-sdk-audit`. | Issue #160 |
| Physical skill execution | **Not verified.** Only notification-class skills are proposable, and only through the Gateway-approved incident outbox. | Issue #160, #164 |
| Deployed Orion-LD acceptance | **Not verified.** The configuration now supports a credentialed, TLS-protected broker, but no deployed broker was exercised by this PR. | Issue #202 |
| Broker exposure / ACL / TLS termination | **Open.** The read path is read-only, but broker exposure is not closed by this PR. | Issue #200 |
| Physical hardware / HIL | **Not verified.** No hardware was involved. | Issue #193 |

## Deliberate non-claims

- The existence of entities and relationships in a context broker is **not**
  evidence of reasoning, inference or understanding.
- A green CI run is evidence that the recorded checks passed at the recorded
  commit — it is not deployment acceptance.
- The advisory report and the SBOM are **review material**. They record what
  the dependency tree contains; they do not assert that the tree is free of
  advisories.

## Evidence locations

- CI runs: the PR's `Edge AI Robot & Integration Tests`, `IoT Gateway Tests`,
  `ADR Lint & Architecture Governance Gate` and `CI` workflows.
- Supply-chain artifacts: the `edge-ai-supply-chain-<sha>` artifact uploaded
  by `.github/workflows/edge-ai-ci.yml`.
- Schema evidence: the `FIWARE schema validation` job.
