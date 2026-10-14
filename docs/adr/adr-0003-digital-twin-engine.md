# ADR-0003: Digital Twin Engine: Unreal vs Unity

**Status:** Proposed ⚠️ CONTRADICTION
**Date:** 2026-10-14
**Deciders:** Issue #11
**Related issues:** #11 #12 #33 #34 #35

## Context

The Smart Factory research proposal (2026) specifies **Unreal Engine 5** for the real-time 3D Digital Twin (S2). However, the repository has scattered references to **Unity** (earlier drafts, issue titles, some PRs). The authoritative source has not been formally locked.

This ADR records the current conflict and requires explicit resolution before the Twin module is implemented.

## Evidence of Decision Points

### For Unreal Engine (authoritative proposal)

- `docs/PROJECT_CONTEXT.md` Section S2: "an **Unreal Engine** 3D model"
- `docs/architecture/repository-layout.md` Section "Design note: Unreal Engine vs Unity": "The authoritative source is `docs/PROJECT_CONTEXT.md`, which references Unreal Engine"
- `digital-twin/README.md`: "Engine: **Unreal Engine**"
- `docs/architecture/overview.md`: "ADR-002: Unreal engine version, renderer/runtime, Git LFS and 3D asset policy"

### For Unity (reported in issues)

- Issue #11 title: references Unity (confirmed in issue tracker)
- Issue #33: "Model nine factory modules as reusable Unity prefabs"
- Repository layout doc note: "Earlier repository drafts mentioned Unity"
- PlatformIO native_test environment: Unity C++ test framework used for firmware (note: unrelated to 3D engine)

## Decision

**NOT YET RESOLVED.** The ADR is recorded as **Proposed** pending one of:

1. **Accept Unreal Engine 5+** — lock to the research proposal; update all docs; bootstrap `digital-twin/` with Unreal
2. **Switch to Unity** — requires documented rationale replacing the proposal; update `PROJECT_CONTEXT.md`; update all references
3. **Evaluate both** — define criteria (licensing, CI, team expertise, rendering requirements); decide empirically

Until resolved, `digital-twin/` bootstrap is blocked by Issue #11.

## Consequences

**If Unreal Engine is chosen:**
- Git LFS required for 3D assets (large binary files)
- Unreal build requires Windows + Visual Studio + significant disk space
- CI for Unreal requires dedicated runner or cloud VM (AzDo/AWS)
- Research proposal is authoritative — no institutional approval needed to change

**If Unity is chosen:**
- Unity is editor-agnostic (Windows/macOS/Linux)
- Unity Test Framework (EditMode/PlayMode) provides in-editor CI
- Existing ESP32 `native_test` PlatformIO environment uses "Unity" name but is unrelated (C++ unit test framework, not 3D engine)
- Requires updating `PROJECT_CONTEXT.md` with documented rationale and institutional approval

**If unresolved:**
- `digital-twin/` bootstrap is blocked
- ADR-002 reference in `docs/architecture/overview.md` is a placeholder

## Alternatives considered

| Option | License | CI complexity | Team expertise | Renderer quality |
|--------|---------|---------------|-----------------|-----------------|
| Unreal Engine 5 | Proprietary (royalty-free for < $1M revenue) | High (dedicated runner) | Unknown | Photorealistic |
| Unity 2022 LTS | Proprietary (per-seat or revenue-based) | Medium (Unity Test Framework) | Likely stronger in research context | High, flexible |
| Three.js/WebGL | MIT | Low (browser only) | Limited 3D fidelity | Good for telemetry viz |

## Required Action

Issue #11 must produce one of the three decisions above with documented rationale before this ADR advances to Accepted.

## Evidence

- `docs/PROJECT_CONTEXT.md` — authoritative source (currently Unreal)
- `docs/architecture/repository-layout.md` — Design note lines 36–38
- `digital-twin/README.md` — current status
- `docs/architecture/overview.md` — ADR-002 placeholder reference
- Issue #11: "Bootstrap Digital Twin"
