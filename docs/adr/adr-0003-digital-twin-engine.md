# ADR-0003: Use Unity for the Smart Factory Digital Twin

**Status:** Proposed — engineering technology selection recorded; formal ADR governance/acceptance review pending
**Date:** 2026-10-14
**Decision owner:** Smart Factory project leadership (engineering decision confirmed in project discussion)
**Related issues:** #11 #12 #33 #34 #35 #62 #79 #81
**Related PR:** #89

## Context

The original Smart Factory research proposal identified **Unreal Engine** for its three-dimensional Digital Twin. The project leadership subsequently selected **Unity as the CURRENT engineering implementation technology**; this decision is reflected in Issues #11, #12, #33–#35 and the closed documentation-alignment Issue #62.

Documentation on the master branch had not been updated consistently and continued to describe Unreal as authoritative, incorrectly treating Unity as merely a former draft. This divergence is a documentation defect, not an unresolved engineering engine choice. The signed/institutional research proposal remains a separate governance artifact and may require an approved amendment; no such approval is inferred here.

## Decision

**Use Unity** as the sole intended 3D runtime for the Smart Factory Digital Twin.

- Create the Unity project in `digital-twin/` according to Issue #11, recording the precise supported Unity editor/LTS release and target build platforms through that Issue (not guessing a release here).
- Build module representations with Unity GameObjects, prefabs and C# components; track `Assets/`, `Packages/`, `ProjectSettings/` and `*.meta`, and ignore generated `Library/`, `Temp/` etc.
- Integrate normalized gateway data via a contract-bound transport adapter, deterministic state reducer and Unity main-thread visualization; support stale/offline indication, reconnect snapshots, playback and EditMode/PlayMode tests.
- Do not implement Unreal Engine, Actors/Blueprints, Unreal plugin/toolchain or Unreal-only build requirements for the engineering Digital Twin.
- Retain a clear historical note wherever the original formal proposal calls for Unreal. Flag institutional proposal scope-change authorization as **PENDING/NOT VERIFIED** until documentation exists; do not silently modify signed research records.

**ADR lifecycle:** This records an explicitly chosen *engineering direction*. Its formal ADR status remains **Proposed**, pending review under governance #79/#80 and any required institutional approval. `Proposed` does **not** mean that Unity vs Unreal is still a technical open question, and does not claim Unity code exists.

## Decision drivers

- One supported 3D engine and one coherent repository/build/test workflow for agents.
- Consistency with current Unity implementation Issues and module ownership.
- Device-event visualization, deterministic replay, stale-state handling and integration testability.
- Source-control governance for scene assets/prefabs and reproducible editor versions.
- Research compliance must remain auditable when engineering technology changes.

## Alternatives considered

| Option | Assessment |
|---|---|
| Unity | **Selected** engineering runtime; C# components/prefabs and EditMode/PlayMode test support. |
| Unreal Engine | Original proposal technology; not the chosen implementation engine now. Institutional documentation may need amendment. |
| Three.js/WebGL | Alternative browser-based visualization, not selected as authoritative factory Digital Twin runtime. |
| Maintain both engines | Rejected for the baseline: duplicates implementation, testing and synchronization burden. |

No unsupported claims about exact licensing, renderer quality or team expertise are used as the decision's definitive rationale.

## Consequences

- Update `README.md`, `AGENTS.md`, `docs/PROJECT_CONTEXT.md`, architecture/roadmap/testing and module README to say **Unity**.
- All Twin Issues (#11/#12/#33/#34/#35), integration tests and device-registry mappings use Unity semantics.
- Historical research-proposal Unreal wording remains visible as a documented deviation, not an active implementation requirement.
- Unity's actual editor version, licenses, assets and CI constraints are verified through #11; do not claim an already bootstrapped scene until code/evidence exists.
- If the decision changes later, write a new superseding ADR; do not erase this record.

## Evidence

- Engineering tasks: #11, #12, #33, #34, #35 (Unity); #62 (documentation alignment).
- Source conflict identified in PR #89; implementation docs correction is tracked in a separate documentation PR.
- Formal proposal approval for switching Unreal to Unity is not verified.
