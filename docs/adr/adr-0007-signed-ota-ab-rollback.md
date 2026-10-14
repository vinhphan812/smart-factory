# ADR-0007: Signed HTTPS OTA with A/B Rollback

**Status:** Proposed
**Date:** 2026-10-14
**Deciders:** Issue #72 #73 #74
**Related issues:** #72 #73 #74

## Context

The ESP32-S3 bridge firmware must be updatable in the field without physical access to the device. OTA (Over-The-Air) updates introduce security risks: an attacker could flash malicious firmware that disables safety interlocks, exfiltrates credentials, or enables unauthorized physical actuation.

The system must also handle update failures gracefully: a failed update should not brick the device.

## Decision

Firmware updates use **signed HTTPS with A/B partition rollback**:

**Partition layout:**
- Two firmware slots (A and B) of equal size
- One slot is always bootable (last known good)
- New firmware is downloaded into the inactive slot
- Bootloader selects the active slot on every boot

**Verification chain:**
1. MQTT announces update availability with metadata: firmware version, SHA-256, signature, release authority
2. Bridge validates: version > current, hardware SKU matches, signature valid, SHA-256 matches
3. SHA-256 alone is insufficient — **signature required** (public-key cryptography)
4. TLS certificate validated against pinned trust roots (not just any HTTPS server)

**Safety gate:**
- Maintenance mode required: pending actuator commands expired/drained
- Post-boot health validation: UART readiness, MQTT connectivity, AMLP protocol check
- If validation fails within bounded timeout: automatic rollback to previous slot
- If rollback fails: explicit recovery procedure documented; no silent brick

**Authorization:**
- MQTT may only announce/coordinate updates; actual download authorization is separate
- Rate limiting, request IDs, and anti-replay on OTA control channel
- Release authority credentials not stored on device (use JWT or signed manifest)

**Non-negotiable properties:**
- Firmware image must be signed with a private key whose public part is pinned on the device
- A rollback to a previous image is always possible
- The bootloader, not the application, selects which slot to boot

## Consequences

**Easier:**
- Field updates without physical access
- Compromised signing key can be rotated (new key, re-sign old images or enforce deadline)
- Rollback prevents update-induced bricking

**Harder:**
- Partition layout reduces usable flash (50% per slot)
- Signing infrastructure required (CA, key management, certificate rotation)
- Release pipeline must sign artifacts before publishing (cannot be done in CI without secret injection)
- Bootloader modification required (platform-specific)

## Alternatives considered

**Option A: Unauthenticated HTTP download**
- Rejected: no integrity verification, trivially MITMed

**Option B: SHA-256 checksum only (no signature)**
- Rejected: checksum verifies integrity but does not authenticate origin; attacker can replace both image and checksum

**Option C: Vendor OTA service (e.g., Espressif OTA)**
- Rejected: requires vendor cloud account and infrastructure; not independently auditable; may conflict with institutional data policies

**Option D: Delta updates (incremental diff)**
- Reduces download size
- Deferred: adds complexity (delta generation, integrity of delta, storage for base image); full-image A/B is the minimum viable approach

## Evidence

- Issue #72: "Specify secure ESP32-S3 OTA architecture, partition layout and release contract"
- Issue #73: "Implement authenticated HTTPS OTA client, maintenance gating and rollback on ESP32 bridge"
- Issue #74: "Build OTA release pipeline, staged rollout and real ESP32-S3 recovery test matrix"
- `esp32-ukit-bridge/docs/bridge-health.md` — health monitoring (OTA depends on this)
- OTA decision locked in Issue #73 Implementation decision: "OtaManager as event-driven state machine, no dedicated FreeRTOS OTA task" (see ADR-0008)
