# Scripts — Smart Factory

**Status: PLANNED** | Related issues: #65

## Purpose

Repository-wide automation: smoke checks, structure validators, CI helpers and development convenience scripts.

## Available scripts (planned)

| Script | Purpose |
|---|---|
| `check-structure` | Verify module boundaries, detect cross-module imports without contracts, fail on untracked nested services |

## Module structure

```
scripts/
├── README.md            ← this file
└── check-structure.*   ← structure validator (Python or shell)
```

## Design note

`check-structure` must verify:
- No backend service lives under `esp32-ukit-bridge/`
- All implemented modules have a README
- All planned module directories have a README with `Status: PLANNED`
- No nested `.git` directories exist
- `contracts/` schemas are validated against actual wire format examples

This script is a **soft gate**: it documents structure expectations but does not replace code review.

## Readiness

**PLANNED.** Structure validator not yet implemented. Must be delivered before Issue #65 can be closed.
