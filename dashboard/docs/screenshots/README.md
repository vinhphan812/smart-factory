# Dashboard QA Screenshots & Visual Evidence (SPEC-8, TC-6)

All QA captures in this documentation repository demonstrate the dashboard operating in **offline simulation mode (L0 static / L2 simulation)** without physical hardware attached.

## Viewport Artifacts

| Artifact | Viewport | Target Purpose | File Size | SHA-256 Checksum |
|---|---|---|---|---|
| `overview-1440.png` | 1440 × 900 px | Overview page with 9-module aggregate summary | 36.4 KB | `a88af2f462ab58407a945708c6d537db5ccfb87258d3aec044a5aea3a74f0d5d` |
| `modules-1440.png` | 1440 × 900 px | Factory Modules responsive desktop grid (3–4 cols) | 16.2 KB | `3ea76ee09b634dfc8bfc82425da1ee019611f1dd0e156d0cd553aef589f335a7` |
| `modules-768.png` | 768 × 1024 px | Factory Modules tablet layout (2 cols) | 17.7 KB | `706b0b1446aaa95e494b966443b83a0366346ca6ddfff1aafd6d99270726d03f` |
| `modules-360.png` | 360 × 800 px | Factory Modules mobile collapse (single col, no horizontal overflow) | 14.9 KB | `883eb3d3e2387bd6ef1131a88c802cc416eba1fad199199bec6886dba40e132a` |
| `module-detail-1440.png` | 1440 × 900 px | Module Detail view (`brackets-01`) showing N/A telemetry safeguards | 16.2 KB | `b623080692dc893860ddaf807ce8ddf8f0e64a9dbcd9237c08d0c698f664120a` |

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
