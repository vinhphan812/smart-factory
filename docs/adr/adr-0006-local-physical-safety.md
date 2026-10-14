# ADR-0006: Local Physical Command Safety

**Status:** Proposed
**Date:** 2026-10-14
**Deciders:** Issue #5
**Related issues:** #5 #9 #10

## Context

The Smart Factory controls physical actuators: conveyor belts, motors, cranes, sorting mechanisms. A malfunctioning command (wrong speed, wrong direction, simultaneous conflicting commands) can cause physical damage or safety hazards. AI/Twin/dashboard operators must not be able to bypass physical safety limits.

The system spans multiple trust boundaries: dashboard operators → MQTT broker → ESP32 bridge → UART → Mega → motors/sensors. Without enforcement, any MQTT client can publish to the command topic and actuate physical devices.

## Decision

Physical safety is enforced **at the local controller level**, not at the cloud/AI/twin layer.

**Layer 1 — MQTT broker ACL (per Issue #41):**
- Only authenticated service accounts may publish to `smart-factory/{deviceId}/command/down`
- Read-only clients cannot issue commands
- ACLs prevent unauthorized broker access

**Layer 2 — ESP32 bridge command validation (per Issue #5):**
- Command name, channel range, value range validated before UART dispatch
- Malformed JSON → immediate NAK (no UART traffic)
- Unknown command → NAK, no action
- Duplicate command ID → silently deduped (no re-execution)
- Rate limiting and anti-replay via command ID window

**Layer 3 — Mega local safety (per Issue #9/10):**
- Motion limits, speed bounds, sensor interlocks enforced in Mega firmware
- E-stop signal is a hardware-level interrupt, not a software flag
- Bridge cannot override Mega's safety decisions

**Layer 4 — AI/Twin fail-closed (per Issue #13):**
- AI robot actions require explicit operator approval
- Twin is read-only — cannot issue actuator commands
- Dashboard sends commands through the same MQTT contract as all other clients (no bypass)

**AI action guard:**
- AI may generate a suggested action, but the action is held in "proposed" state until an operator explicitly approves it
- The approval gate is a separate MQTT publish from an operator-authenticated session
- Physical execution follows the normal command contract (no special AI shortcut)

## Consequences

**Easier:**
- Each layer is independently auditable
- Safety enforcement does not depend on MQTT, AI, or Twin availability
- Hardware-level E-stop works even if all software systems fail

**Harder:**
- Debugging requires access to physical system or emulator
- Safety rules must be synchronized between bridge validation and Mega enforcement
- "Safe state" definition (what happens on disconnect) must be explicit per device

## Alternatives considered

**Option A: Centralized safety enforcement in bridge**
- Bridge holds all safety rules and rejects any command outside bounds
- Rejected: Mega is the authoritative source of physical state; bridge does not have sensor feedback loop

**Option B: Safety only at MQTT ACL layer**
- Rejected: MQTT ACL prevents unauthorized access but does not prevent authorized-but-unsafe commands

**Option C: AI directly controls actuators with ML safety model**
- Rejected: Research context requires human operator approval; ML safety model cannot be validated as a safety-critical system without extensive HIL testing

## Evidence

- `docs/architecture/repository-layout.md` Boundary rule 5: "Local controllers own motion limits and E-stop; AI/Twin/dashboard cannot bypass these"
- `docs/architecture/components.md` Boundary rule: "Physical status must always be measured rather than inferred"
- Issue #5: "Harden bridge command authorization and device fail-safe policy"
- Issue #9, #10: Factory control device adapters (planned)
- Issue #13: AI action guard
- `esp32-ukit-bridge/docs/threat-safety-model.md` — threat model (to be updated with this ADR)
