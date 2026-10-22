# Dashboard QA Screenshots & Visual Evidence (SPEC-8, TC-6)

All QA captures in this documentation repository demonstrate the dashboard operating in **offline simulation mode (L0 static / L2 simulation)** without physical hardware attached.

## Evidence Matrix

| View | Breakpoint | Target Purpose | Status & Ingestion State |
|---|---|---|---|
| Overview | 1440px | 9-module aggregate status summary | Gateway Offline / Mock UNKNOWN (L0) |
| Factory Modules | 1440px | Grid with state filters & search | Gateway Offline / Mock UNKNOWN (L0) |
| Factory Modules | 768px | Tablet responsive 2-column layout | Verified (360/768/1440px responsive) |
| Factory Modules | 360px | Mobile single-column collapse | No horizontal scroll / overflow (TC-3) |
| Module Detail | 1440px | Detail view with telemetry safeguard | `brackets-01` renders N/A (TC-2) |

## Hardware Readiness Notice

- **Hardware Status:** No physical hardware connected in these captures.
- **Evidence Level:** L0 Static / L2 Simulation only.
- In accordance with `contracts/physical/factory-interface.md` §1.1, `brackets-01` is structurally passive without sensors; values are rendered as **N/A** rather than fabricated numbers.
