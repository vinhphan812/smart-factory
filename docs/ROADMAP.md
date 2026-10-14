# Roadmap — 12-month proposal and GitHub backlog

Source: the research proposal describes five scientific work packages (architecture, physical integration, data synchronization, Digital Twin, AI Edge Robot). Months below are **relative proposals**, not authorized calendar deadlines.

| Stage | Relative month | Deliverable/evidence | Key issues |
|---|---|---|---|
| A. Foundation | 1–2 | architecture/context, contracts, CI, procurement/SDK readiness | #1–#6 #9 #19 #52 |
| B. Device and data simulation | 2–4 | stable AMLP path, simulated production, gateway, registry | #7 #10 #22–#32 |
| C. 3D and robot adapters | 4–7 | Unity scene, synchronization, robot capability mock, dashboard | #11–#15 #33–#40 |
| D. Physical integration | 5–9 | staged HIL, local safety and approved device behavior | #4 #5 #9 #20 #42 |
| E. E2E experiments | 8–11 | recorded tests, fault injection, latency and response results | #16 #43–#47 |
| F. Education/handover | 11–12 | scientific report, lab guide, demonstration and recovery docs | #18 #48–#51 |

## Priority
P0 = integration/safety blocker. P1 = core feature. P2 = quality, evidence, training and handover. Title tags reflect priority even when GitHub label automation has not been configured.

## Tracking and claiming
[Master Issue #52](https://github.com/vinhphan812/smart-factory/issues/52) indexes the entire backlog. Verify dependencies, owner/claim and linked PR before starting; do not duplicate work already done. Comment `/claim` with plan and ETA and request manual assignment. Mark hardware/SDK dependency `BLOCKED: reason`. PR should link issue, tests and evidence before closing.

A closed software Issue is not proof of hardware integration; test levels and real-device evidence are separate.
