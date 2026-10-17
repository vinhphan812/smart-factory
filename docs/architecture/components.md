# Module boundaries and ownership

All items are subdirectories in a **modular monorepo**. A new repository is not required for each component.

| Module path | Purpose | Key responsibility | Issues |
|---|---|---|---|
| `esp32-ukit-bridge/` | Existing firmware/reference | MQTT JSON ↔ AMLP UART, parsing, retries, status | #4 #5 #28 #29 |
| `factory-control/` (planned) | Physical integration | nine device adapters, safe state machines, production orchestration | #9 #10 #22–#27 |
| `iot-gateway/` (implemented; migration under #65) | Integration backbone | MQTT ingest, validation, normalized events and snapshots | #7 #8 #31 #32 |
| `contracts/` (foundation work under #65) | System-level interface schemas | stable IDs, event versions, compatibility fixtures | #3 #30 |
| `digital-twin/` (planned) | Unity | prefabs/GameObjects, C# telemetry-to-state mapping, reconnect, replay | #11 #12 #33–#35 |
| `edge-ai-robot/` (planned) | UBTECH Yanshee and Edge AI | detection, bounded robot skills, action guard | #13 #14 #36–#38 |
| `dashboard/` (planned) | Operator display | read-only telemetry, incidents, approved requests | #15 #39 #40 |
| `integration-tests/` (planned) | E2E quality | reproducible scenarios, HIL and reliability evidence | #16 #20 #42–#45 |
| `infrastructure/` (planned) | Environment | local deployment, credentials and recovery | #17 #41 #51 |

**Boundary rules:** module private code should not be accessed across directories; use versioned contracts. Do not copy/rewrite the canonical AMLP specification. Local controllers own motion safety and E-stop; AI/Twin/dashboard are not local safety controllers. Physical status must always be measured rather than inferred from a queued request or 3D animation.


**Structure invariant:** Python IoT Gateway is a root sibling of the ESP32–uKit bridge, not a child directory. Bridge-local AMLP protocol remains owned by the bridge. Cross-module event, command and telemetry schemas belong in the root `contracts/` once validated against actual wire format; do not conflate existing bridge-local `contracts/v1/` with proven canonical cross-system contracts.
