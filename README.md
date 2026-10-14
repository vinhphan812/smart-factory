# Smart Factory — AIBOT

**A 12-month research and engineering project** at AIBOT / Dong Nai Technology University (DNTU): a nine-module physical miniature factory, a **real-time Unity Digital Twin**, and an **AI Edge MiniAlpha Robot** for bounded monitoring and incident response.

This repository is a **modular monorepo**. GitHub Issues describe planned deliverables; they are not proof that the requested features or hardware are already implemented.

## Start here

- [Project context, objectives and readiness](docs/PROJECT_CONTEXT.md)
- [Documentation index](docs/README.md)
- [Architecture: current bridge vs future systems](docs/architecture/overview.md)
- [Contracts and event semantics](docs/contracts-and-data.md)
- [Testing and acceptance](docs/testing-and-acceptance.md)
- [12-month roadmap](docs/ROADMAP.md)
- [Instructions for AI coding agents](AGENTS.md)
- [Contribution and claiming issues](CONTRIBUTING.md)
- [Master backlog Issue #52](https://github.com/vinhphan812/smart-factory/issues/52)

## System components

| System | Research target | Current repository status |
|---|---|---|
| Physical factory | Forklift, Dump Truck, Bracket, Packaging, Conveyor, Sorting, Tower Crane, Parking Lot and integration | ESP32–UKIT communication bridge exists; full 9-module hardware proof pending |
| Digital Twin | Unity, 3D visualization synchronized with observed physical events | Planned; see Issues #11 #12 #33–#35 |
| AI Edge Robot | MiniAlpha alerts and validated, bounded on-site response | Planned; see Issues #13 #14 #36–#38 |
| Supporting services | Root `iot-gateway/` ingests MQTT and serves event API; other services and deployment | IoT Gateway software implemented; deployment/HIL evidence pending |

## Independent IoT Gateway (root module)

The Python MQTT gateway is in [`iot-gateway/`](iot-gateway/README.md), **not** inside the ESP32 firmware module. For a software-only check: `python -m pip install -e "./iot-gateway[dev]"` then `python -m pytest iot-gateway/tests/`. Hardware/MQTT end-to-end proof is separate.

## Existing bridge: what is actually present

The [ESP32–UKIT bridge](esp32-ukit-bridge/README.md) includes ESP32-S3 PlatformIO firmware, AMLP v1 UART framing, existing MQTT command/result/status behavior, Python tools, C99 portable UKIT reference code and automated tests. It **does not by itself prove integration with the vendor's real UKIT firmware or nine factory modules**.

Important: the [current MQTT contract](esp32-ukit-bridge/docs/mqtt-contract.md) documents `smart-factory/bridge/command`, `smart-factory/bridge/result`, and `smart-factory/bridge/status`; TEL→MQTT telemetry is not yet verified as implemented. Do not invent additional operational topic endpoints or assert live Twin synchronization.

### Software-only quickstart

```bash
cd esp32-ukit-bridge
python -m venv .venv
# Activate the environment for your shell
python -m pip install -e ".[test]"
python -m pytest tests/python
python -m amlp simulate --telemetry-interval 1
```

From the repository root with PlatformIO installed:

```bash
pio test -d esp32-ukit-bridge/ukit -e native
pio run -d esp32-ukit-bridge/esp32 -e esp32-s3
```

These build/simulation results must never be reported as hardware-in-the-loop acceptance.

## Safety and licensing

Physical motion requires local hardware interlocks, operator override and emergency stop independent of networking or AI. A queued/ACK response is not observed successful physical actuation. Check the project's licensing situation before reusing code or distributing vendor SDKs/3D assets; **no root project-wide license is asserted here**. Never commit secrets.

For detailed operating rules, see [AGENTS.md](AGENTS.md) and [safety/test policy](docs/testing-and-acceptance.md).
