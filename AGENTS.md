# AIBOT Smart Factory — Instructions for coding agents

Read in order: `docs/PROJECT_CONTEXT.md`, `docs/architecture/repository-layout.md`, `docs/architecture/overview.md`, `docs/contracts-and-data.md`, the affected module README/source/tests and GitHub Issue, then `docs/testing-and-acceptance.md`.

## Fixed context
- Research system = **nine-module physical mini-factory + Unreal Engine real-time Digital Twin + MiniAlpha Edge AI Robot**. Not a retail twin and not a generic chatbot demo.
- Modular monorepo: do not split repos, create nested `.git`, or duplicate bridge implementation without an approved architecture decision.
- **Root module ownership (P0 #65):** `esp32-ukit-bridge/` is only the ESP32 ↔ MEGA-uKit firmware, AMLP and bridge-local tests/contracts. Independent backend services such as `iot-gateway/` MUST be siblings at repository root. Never nest services under `esp32-ukit-bridge/`. Cross-system schemas belong to root `contracts/`, subject to compatibility audit; AMLP stays in the bridge.
- Existing bridge is source of truth for its wire/JSON interface; AMLP v1 at `esp32-ukit-bridge/shared/protocol-spec/AMLP-v1.md`, MQTT contract at `esp32-ukit-bridge/docs/mqtt-contract.md`.
- UKIT endpoint is portable C99 reference, not vendor firmware/hardware proof. Simulator/native build does not imply HIL PASS. The bridge's MQTT telemetry support must be verified, not presumed.
- Never turn a target/Issue into an implemented claim. Mark status as **implemented**, **simulated**, **planned**, **blocked**, or **verified hardware** with evidence.
- AI/Twin/dashboard cannot bypass device-local interlocks, operator override, physical E-stop, fresh context checks, permissions or actuator limits.
- Do not treat queued or ACK as verified physical completion.
- No secrets, identifiable participant data or proprietary SDK/3D assets in the public repository.

## Work policy
1. Check Issue, dependency and current PR; claim an unassigned task with plan, ETA, tests. `/claim` is a manual convention, not an installed bot.
2. Change only scoped files, use versioned interfaces, preserve AMLP compatibility.
3. Provide positive/negative, duplicate/stale, offline/recovery and safety tests as applicable.
4. Label evidence L0 static / L1 unit / L2 simulation / L3 bench / L4 HIL / L5 integrated.
5. In PR state purpose, files, commands/results, assumptions, compatibility, risks and blockers. Do not claim achievements or invent numerical results.
