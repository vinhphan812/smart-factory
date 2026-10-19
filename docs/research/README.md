# Research Evidence Archive

**Owner:** Issue #47
**Branch:** `smart-factory/t_74cb2b44-47-research-evidence-archive-and-reprodu`
**Created:** 2026-10-17
**Parent document:** `docs/hardware-blocked-issues-audit.md` §47

---

## Purpose

This archive collects and pins every verifiable artifact produced by the Smart Factory project so that:

1. Any reviewer can reproduce the evidence for L0-L2 claims without hardware.
2. Future experiment runs can cite a stable baseline and a known dependency graph.
3. Hardware-blocked claims (L3/L4/L5) are clearly labelled with their unblock path.
4. The final scientific report (#48) can cite immutable, versioned evidence.

**Rule:** Nothing enters this archive without evidence. No assertion about software behavior enters without a linked test result. No claim about hardware enters without a gate label (`BLOCKED-L3`, `BLOCKED-L4`, `BLOCKED-L5`).

---

## Archive structure

```
docs/research/
  README.md                    ← this file
  manifest.md                  ← master evidence manifest with SHA-256 pins
  reproducibility-package.md    ← dependency pins, environment, test vectors
  evidence/
    bridge-amlp-l2-evidence.md  ← L2 protocol evidence from esp32-ukit-bridge
    gateway-l2-evidence.md       ← L2 gateway evidence from iot-gateway
    adr-evidence.md              ← ADR status and prerequisite gate audit
    hardware-blocked-audit.md    ← copy of hardware-blocked-issues-audit.md (this version pinned)
    contracts-l0-evidence.md     ← L0 contract schema audit
```

---

## Evidence levels

| Level | Environment | What it proves |
|-------|-------------|----------------|
| L0 | static/schema | Shape, review, lint |
| L1 | Python/C99/C++ host unit | Local algorithms and parsers |
| L2 | simulated UART/MQTT, mock device | Software protocol and application behavior |
| L3 | ESP32 + real controller (bench) | Verified electrical and link interoperability |
| L4 | Actual moving subsystem, operator, E-stop | Physical safety and actuation |
| L5 | Integrated factory → gateway → Twin → MiniAlpha | Stated E2E scenarios with declared mock/real mix |

See `docs/testing-and-acceptance.md` for the full definition.

---

## How to cite this archive

In a report or PR, cite a specific artifact like:

```
Evidence: docs/research/evidence/bridge-amlp-l2-evidence.md
Archive version: smart-factory/t_74cb2b44-47-research-evidence-archive-and-reprodu
Git SHA: <commit SHA of this branch>
Date: 2026-10-17
```

For reproducibility, always pin:
- Repository commit SHA
- Evidence archive version tag
- Evidence level
- Test command and its exit code

---

## Updating this archive

When new evidence is produced (e.g. a new L2 test run, an ADR accepted, a hardware test completed):

1. Add the new evidence file under `docs/research/evidence/`.
2. Update `docs/research/manifest.md` with the new SHA-256 pins.
3. Open a PR with `[skip-adr]` if the change is only evidence (no architecture change).
4. Record the update in the `CHANGELOG` section of `manifest.md`.

Do NOT overwrite evidence files already cited in a published report. Add new files with a versioned name (e.g. `gateway-l2-evidence-v2.md`) and update the manifest.
