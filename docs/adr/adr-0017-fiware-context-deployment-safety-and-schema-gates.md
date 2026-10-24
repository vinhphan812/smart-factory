# ADR-0017: FIWARE Context Deployment Safety, Schema Validation and Supply-Chain Gates

**Status:** Proposed
**Date:** 2026-10-24
**Deciders:** AIBOT Smart Factory engineering team
**Related issues:** #204, #200, #160, #159, #202, #261

## Context

Maintainer Review Iteration #2 on PR #261 returned findings 4 and 5 as PARTIAL. The read-only FIWARE context facade in `iot-gateway/src/iot_gateway/context_query.py` has no authentication and no TLS configuration, so it cannot address a deployed Orion-LD behind a credentialed reverse proxy, and no test proves the stale-context and unverified-capability fail-closed behaviour over the real configuration path. The FIWARE JSON Schema layer is unvalidated: `contracts/fiware/schemas/validate_schemas.py` only parses JSON, `jsonschema` is not a dependency of any module, no CI workflow runs the validator, and the schema version table in `contracts/fiware/schemas/README.md` was not bumped when `robot.json` was added. The `edge-ai-robot` module has no pinned dependency set, and `.github/workflows/edge-ai-ci.yml` emits neither a dependency advisory assessment nor an SBOM.

Issue #204 is a read-only context mapping. The Yanshee SDK is not audited (Issues #159, #160), no deployed Orion-LD acceptance exists (Issue #202), and the broker exposure boundary is still open (Issue #200). This ADR therefore governs the deployed safety of the read path and the generation of release evidence, not robot operation.

## Decision

We will make the read-only context path safe to configure for a deployed broker without making it capable of authorizing anything, and we will turn the FIWARE schema layer and the `edge-ai-robot` dependency set into CI-enforced, auditable gates.

First, `ContextQueryConfig` gains explicit, fail-closed deployment fields: an optional bearer token read from `ORION_LD_TOKEN`, a boolean TLS requirement read from `ORION_LD_REQUIRE_TLS`, and a CA bundle path read from `ORION_LD_CA_BUNDLE`. A configuration that requires TLS but carries no CA bundle is rejected when it is built from the environment. The facade remains read-only: it still performs HTTP GET only, and a bearer token permits reads, never writes and never skill dispatch.

Second, the fail-closed guarantee becomes an executable end-to-end check. A new test drives `YansheeResponsePolicy` over a real `ContextQueryFacade` built from `ContextQueryConfig.from_env()` with a stubbed transport, and asserts that stale context, a missing observation timestamp, an unverified robot capability and an active emergency stop each produce the expected non-approval reason code. The module boundary that forbids `edge-ai-robot` from importing `iot_gateway` becomes an executable test rather than prose.

Third, the FIWARE schema layer is validated in the test path. `jsonschema` is added to the `iot-gateway` dev extras, `validate_schemas.py` grows an entity-validation mode, `iot-gateway/tests/test_orion_robot.py` gains a test that validates the produced `Robot` entity against `robot.json`, and `.github/workflows/edge-ai-ci.yml` gains a schema-validation job with `contracts/fiware/**` added to its path filter. The schema version table in `contracts/fiware/schemas/README.md` is bumped to record the `robot.json` addition.

Fourth, the supply-chain evidence for `edge-ai-robot` becomes reproducible. A pinned constraint file is added, `pip-audit` runs in CI to produce an advisory report, and a CycloneDX SBOM of the installed tree is generated and uploaded as a retained artifact. These steps are deliberately non-blocking in the same way as the repository's existing dashboard gate, and the recorded output is review material, not a claim of a clean audit.

Context remains evidence and never authority. Nothing in this ADR creates, widens or relaxes a robot actuation path. The Yanshee SDK remains unaudited, the default capability source remains `UnverifiedRobotCapabilitySource`, and no deployed-broker, HIL or physical-skill claim is made.

## Consequences

Making it easier: a deployed Orion-LD behind a credentialed proxy becomes addressable, with an explicit configuration that fails closed rather than silently sending an unauthenticated plaintext request. Schema and producer drift becomes a CI failure instead of a review finding. The reviewer receives a pinned dependency set, an advisory report and an SBOM as immutable CI artifacts instead of a statement that the tree is acceptable.

Making it harder: an operator who sets `ORION_LD_REQUIRE_TLS` must also set `ORION_LD_CA_BUNDLE`, and an operator who points `ORION_LD_URL` at a non-loopback host must also set `ORION_LD_TOKEN`. The `edge-ai-robot` constraint file must be refreshed when a dependency is intentionally upgraded, and a stale constraint file makes CI install a different tree than local development. Schema validation adds `jsonschema` to the dev path, so it must never be promoted into a runtime dependency.

Risks introduced or mitigated: mitigated is the accidental deployment of the read path without credentials, which the fail-closed configuration now prevents. Introduced is a new configuration surface that can fail at startup where it previously worked with a plain default; this is the intended trade-off and the failure is loud and early.

Explicitly unchanged: the notification-only skill policy, the E-stop independence, the `UNKNOWN` and `UNVERIFIED` reporting of unmeasured robot fields, the ADR-0018 mapping decisions, and the read-only construction of the facade.

## Alternatives considered

**Alternative A — defer everything to the hardware and deployment issues.** Issue #160 owns the SDK audit, #202 owns the deployed Orion-LD harness and #200 owns broker exposure. We rejected this as the only option: it leaves the read path unable to address a credentialed broker at all, and leaves schema drift undetectable in CI, both of which are fixable now without any hardware. The parts that genuinely need hardware stay in those issues.

**Alternative B — add the schema validator and the advisory scan as blocking CI gates.** We rejected blocking advisory gates for the same reason the repository's dashboard gate uses non-blocking advisory steps: the current dependency tree carries transitive advisories in the test chain, and a blocking gate would fail the PR on a condition the reviewer has already accepted as recorded evidence rather than a hard error. The schema validator itself is blocking, because a malformed schema is unambiguously a defect; only the advisory scan and the SBOM are non-blocking.

**Alternative C — add `jsonschema` as a runtime dependency of `iot-gateway`.** We rejected this. Schema validation is a test-time and CI-time concern; shipping it in the gateway runtime would enlarge the production dependency surface for no runtime benefit. The validator lives in the dev extras and in CI.

**Alternative D — leave the fixture-based policy tests as the only proof of fail-closed behaviour.** We rejected this because the policy tests inject a `FakeContextReader` and never construct the facade from real configuration or real `ContextEntity` objects, so a defect in `from_env()`, in `ContextEntity.from_payload()` or in the freshness handling would not be caught by any test on the branch. The new end-to-end test closes that gap.

## Evidence

- `iot-gateway/src/iot_gateway/context_query.py` — the read-only facade, its `ContextQueryConfig.from_env()`, `ContextEntity.from_payload()` and `is_context_fresh()`.
- `edge-ai-robot/src/edge_ai_robot/context/__init__.py` — `YansheeResponsePolicy` and its `DecisionReason` codes.
- `iot-gateway/src/iot_gateway/adapters/orion_robot.py` — `UnverifiedRobotCapabilitySource` and `to_robot_entity()`.
- `contracts/fiware/schemas/robot.json` — the schema the new validation test asserts against.
- `contracts/fiware/schemas/README.md` — the schema version table this ADR bumps.
- `.github/workflows/edge-ai-ci.yml` — the workflow that gains the schema, advisory and SBOM jobs.
- `scripts/check_adrs.py` — the ADR lint and architecture-impact gate this ADR satisfies.
- Maintainer Review Iteration #2 on PR #261, 2026-10-24, findings 4 and 5.
- Issue #204 — FIWARE context mapping for Yanshee notifications, incident evidence and research API.
