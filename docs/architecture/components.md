# Module boundaries and ownership

All items are subdirectories in a **modular monorepo**. A new repository is not required for each component.

| Module path | Purpose | Key responsibility | Issues |
|---|---|---|---|
| `esp32-ukit-bridge/` | Existing firmware/reference | MQTT JSON ↔ AMLP UART, parsing, retries, status | #4 #5 #28 #29 |
| `factory-control/` (planned) | Physical integration | nine device adapters, safe state machines, production orchestration | #9 #10 #22–#27 |
| `iot-gateway/` (planned) | Integration backbone | MQTT ingest, validation, normalized events and snapshots | #7 #8 #31 #32 |
| `contracts/` (planned) | System-level interface schemas | stable IDs, event versions, compatibility fixtures | #3 #30 |
| `digital-twin/` (planned) | Unreal Engine | actors, telemetry-to-state mapping, reconnect, replay | #11 #12 #33–#35 |
| `edge-ai-robot/` (planned) | MiniAlpha and Edge AI | detection, bounded robot skills, action guard | #13 #14 #36–#38 |
| `dashboard/` (planned) | Operator display | read-only telemetry, incidents, approved requests | #15 #39 #40 |
| `integration-tests/` (planned) | E2E quality | reproducible scenarios, HIL and reliability evidence | #16 #20 #42–#45 |
| `infrastructure/` (planned) | Environment | local deployment, credentials and recovery | #17 #41 #51 |

**Boundary rules:** module private code should not be accessed across directories; use versioned contracts. Do not copy/rewrite the canonical AMLP specification. Local controllers own motion safety and E-stop; AI/Twin/dashboard are not local safety controllers. Physical status must always be measured rather than inferred from a queued request or 3D animation.
