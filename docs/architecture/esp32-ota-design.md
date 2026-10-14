# Secure ESP32-S3 OTA Architecture, Partition Layout, and Release Contract

**Issue:** #72
**Status:** Design Review / Architecture Specification
**Assignee:** dev-architect
**Prerequisite:** #56 Audit (uKit Explore / Arduino Mega & ESP32 bridge separation, verified via recovery PRs #83/#84 on master)

---

## 1. Executive Summary and Scope

This document defines the secure Over-The-Air (OTA) firmware update architecture for ESP32-S3 bridge nodes within the Smart Factory (AIBOT) architecture. It establishes the partition layout, cryptographic trust verification model, anti-replay mechanism, non-blocking asynchronous OTA management seam (`OtaManager`), state lifecycle, error code taxonomy, and release contract.

### In Scope
- Non-blocking event-driven `OtaManager` seam separating transport/download from flashing and verification.
- Cryptographic verification architecture (distinguishing TLS transport integrity from ECDSA firmware signature authenticity and SHA-256 binary integrity).
- Versioned release manifest schema (`ota-manifest.json`) supporting anti-replay and staged rollouts.
- A/B (OTA_0 / OTA_1) flash partition table specification with explicit sizing assumptions for 8MB and 16MB flash chips, guarded by #56 hardware verification gates.
- Post-boot health check, automatic rollback protocol, and fallback safety states.
- Release artifact contracts and measurable thresholds for future agentic automation / dedicated worker tasks (#73 client implementation, #74 release pipeline).

### Out of Scope (Exclusions)
- Implementation of the OTA client runner (#73).
- CI/CD release pipeline automation scripts (#74).
- Production private signing keys or hardcoded production credentials.
- Vendor proprietary code redistribution (uKit SDK remains isolated to Arduino Mega).
- Hardware flashing or HIL execution claims without physical bench sign-off.

---

## 2. System Architecture & Event-Driven `OtaManager` Seam

To prevent blocking the core MQTT event loop, telemetry emission, and UART AMLP bridge commands during firmware download and flash writes, OTA operations are managed via a non-blocking, state-machine-driven `OtaManager` component.

```mermaid
flowchart TD
    subgraph MQTT / Cloud
        Broker[MQTT Broker] -->|OTA Trigger / Manifest| Sub[MQTT Subscription Handler]
    end

    subgraph ESP32-S3 Bridge
        Sub -->|Enqueue Request| Q[Async OTA Queue]
        Q --> OM[OtaManager State Machine]

        OM -->|1. Fetch Chunk (HTTPS)| Down[Download Worker]
        Down -->|Stream chunks| Crypto[Cryptographic Verifier]
        Crypto -->|2. Verify Signature & SHA256| Flash[ESP Partition Writer]

        Flash -->|3. Write inactive OTA slot| Slot[OTA_0 / OTA_1 Partition]
        Slot -->|4. Set boot partition| Boot[esp_ota_set_boot_partition]

        Boot -->|5. Reboot trigger| Reboot[System Restart]
    end

    subgraph Post-Boot
        Reboot --> Health[Health Check & Smoke Test]
        Health -- Success --> Confirm[esp_ota_mark_app_valid_cancel_rollback]
        Health -- Failure --> Rollback[Automatic Rollback to Previous Slot]
    end
```

### Key Design Principles
1. **Non-Blocking Execution:** File downloads occur in chunks via HTTPS using ESP-IDF HTTP client callbacks (`esp_http_client`). The MQTT loop and UART parser run concurrently without interruption.
2. **Asynchronous State Tracking:** OTA progress is emitted periodically via MQTT status topics (`smart-factory/bridge/ota/status`) without starving main telemetry.
3. **Fail-Closed Safety:** Any signature verification failure, download timeout, power interruption, or post-boot health check failure aborts the update and triggers an automatic rollback or safe idle state.

---

## 3. Cryptographic Trust Model & Verification Seam

Security and authenticity are strictly separated from simple transport integrity:

| Check Layer | Mechanism | Purpose | Failure Consequence |
|---|---|---|---|
| **Transport Integrity** | TLS 1.3 / HTTPS (Mutual Auth or pinned CA) | Protects transit against tampering and eavesdropping | Connection abort / download failure |
| **Binary Integrity** | SHA-256 Hash Check | Verifies exact byte-for-byte transmission match | Rejection before writing to flash |
| **Firmware Authenticity** | ECDSA (secp256r1) Signature over SHA-256 | Verifies firmware binary was signed by authorized private release key | Immediate rejection; slot marked invalid |
| **Anti-Replay** | Monotonically increasing version / build number | Prevents rolling back to vulnerable older firmware versions | Rejection of downgrade manifest |

### Verification Flow
1. Device receives `ota-manifest.json` containing version, minimum hardware revision, SHA-256 checksum, signature, and firmware URL.
2. `OtaManager` verifies manifest signature using the device's compiled-in public key (or secure NVS-stored public key anchor).
3. As chunks are downloaded, incremental SHA-256 is computed.
4. Final binary SHA-256 and ECDSA signature are verified against the manifest prior to calling `esp_ota_set_boot_partition`.

---

## 4. Versioned Release Manifest Schema (`ota-manifest.json`)

All OTA updates are governed by a strictly validated JSON schema.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ESP32OTAManifest",
  "type": "object",
  "required": [
    "schema_version",
    "firmware_name",
    "version",
    "min_hardware_revision",
    "target_chip",
    "image_size",
    "sha256",
    "signature",
    "url"
  ],
  "properties": {
    "schema_version": { "type": "string", "enum": ["v1"] },
    "firmware_name": { "type": "string", "example": "esp32-ukit-bridge" },
    "version": { "type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+(-[a-zA-Z0-9.]+)?$" },
    "min_hardware_revision": { "type": "string", "example": "v1.2" },
    "target_chip": { "type": "string", "enum": ["esp32s3"] },
    "image_size": { "type": "integer", "minimum": 1024, "maximum": 4194304 },
    "sha256": { "type": "string", "pattern": "^[a-fA-F0-9]{64}$" },
    "signature": { "type": "string", "description": "Base64 encoded ECDSA secp256r1 signature" },
    "url": { "type": "string", "format": "uri" },
    "rollback_permitted": { "type": "boolean", "default": true }
  },
  "additionalProperties": false
}
```

---

## 5. Partition Layout & Hardware Sizing Assumptions (#56 Gate)

In accordance with architectural constraint #56, actual board flash capacity and bootloader configuration must be physically verified before committing to hardcoded partition sizes.

### Conditional Partition Table Templates

#### Template A: 8MB Flash (Standard Development / Small Deployment)
```ini
# Name,   Type, SubType, Offset,  Size, Flags
nvs,      data, nvs,     ,        0x4000,
otadata,  data, ota,     ,        0x2000,
phy_init, data, phy,     ,        0x1000,
factory,  app,  factory, ,        1M,
ota_0,    app,  ota_0,   ,        2560K,
ota_1,    app,  ota_1,   ,        2560K,
storage,  data, spiffs,  ,        1536K,
```

#### Template B: 16MB Flash (Production / Staged Multi-Model Deployment)
```ini
# Name,   Type, SubType, Offset,  Size, Flags
nvs,      data, nvs,     ,        0x4000,
otadata,  data, ota,     ,        0x2000,
phy_init, data, phy,     ,        0x1000,
ota_0,    app,  ota_0,   ,        4M,
ota_1,    app,  ota_1,   ,        4M,
storage,  data, spiffs,  ,        6M,
```

### Hardware Verification Gates (`#56` Dependency)
- **Gate 1:** Flash chip size must be read via `esptool.py flash_id` or ESP-IDF `esp_flash_get_size()` during initial bench bring-up.
- **Gate 2:** Bootloader configuration (Secure Boot V2 and Flash Encryption enabled/disabled) must be explicitly recorded.
- **Gate 3:** If flash size is unverified or less than 8MB, automated OTA is **BLOCKED** and firmware updates must fall back to wired serial flashing.

---

## 6. Lifecycle, State Machine, and Error Code Taxonomy

### State Machine Transitions
`IDLE` -> `MANIFEST_CHECK` -> `DOWNLOADING` -> `VERIFYING` -> `WRITING` -> `PENDING_REBOOT` -> `HEALTH_CHECK` -> (`COMMITTED` | `ROLLBACK`)

| State | Description | Transition Triggers |
|---|---|---|
| `IDLE` | Waiting for MQTT OTA trigger | Incoming valid MQTT command |
| `MANIFEST_CHECK` | Verifying signature, schema, anti-replay | Valid manifest JSON received |
| `DOWNLOADING` | HTTP chunk streaming | Manifest verified successfully |
| `VERIFYING` | Computing final SHA-256 and ECDSA signature | Download complete (`EOF`) |
| `WRITING` | Flashing inactive OTA slot via `esp_ota_write` | Signature valid |
| `PENDING_REBOOT` | Setting boot partition and scheduling restart | Write successful (`esp_ota_set_boot_partition`) |
| `HEALTH_CHECK` | Post-boot validation smoke test | Device rebooted into new image |
| `COMMITTED` | Marking app valid (`esp_ota_mark_app_valid`) | Health check passed (>60s stable operation) |
| `ROLLBACK` | Reverting boot partition to prior slot | Health check failed or panic detected |

### Error Code Taxonomy

| Error Code | Category | Meaning | Recovery Action |
|---|---|---|---|
| `OTA_ERR_001` | Network | TLS handshake or HTTP download timeout | Retry with exponential backoff (max 3 attempts) |
| `OTA_ERR_002` | Schema | Manifest JSON validation failed | Abort; log error; remain on current firmware |
| `OTA_ERR_003` | Cryptography | ECDSA signature verification failed | Abort; discard image; log security alert |
| `OTA_ERR_004` | Integrity | SHA-256 checksum mismatch | Abort; discard image; request re-download |
| `OTA_ERR_005` | Flash | `esp_ota_begin` or `esp_ota_write` failed (out of space / bad sector) | Abort; mark partition invalid; fallback to safe idle |
| `OTA_ERR_006` | Rollback | Post-boot health check failed | Automatic reboot into previous valid OTA slot |

---

## 7. Post-Boot Health Check, Confirmation, and Rollback

### The Rollback Protocol (ESP-IDF Native OTA)
1. When the ESP32-S3 boots into a newly flashed OTA image for the first time, ESP-IDF marks the running app as `ESP_OTA_IMG_PENDING_VERIFY`.
2. The firmware initializes subsystems (Wi-Fi, MQTT broker connection, UART AMLP bridge loop, device registry).
3. A watchdog timer and stability counter monitor health for **60 seconds**:
   - If MQTT connects successfully and at least one valid heartbeat/telemetry frame is processed without a kernel panic or watchdog reset, the firmware invokes `esp_ota_mark_app_valid_cancel_rollback()`.
   - If a crash, watchdog timeout, or unrecoverable error occurs within 60 seconds, the ESP-IDF bootloader automatically reverts the active boot partition to the previous stable slot (`OTA_0` ↔ `OTA_1`) on the next reboot.

---

## 8. Release Artifacts and Measurable Thresholds for Downstream Tasks

### Deliverables for Task #73 (Client Implementation)
- C++ OTA client module (`OtaManager` class) in `esp32-ukit-bridge/esp32/src/ota_manager.cpp`.
- Integration into MQTT command dispatcher for topic `smart-factory/bridge/ota/trigger`.
- Unit and integration tests covering manifest parsing, signature validation failure, and state transitions.

### Deliverables for Task #74 (Release Pipeline)
- GitHub Actions workflow (`.github/workflows/esp32-ota-release.yml`) for automated firmware compilation, signing, and artifact packaging.
- Release registry JSON generator.

### Measurable Thresholds
- OTA download & flash verification duration: < 45 seconds for a 2.5MB firmware image over a stable 2.4GHz Wi-Fi link.
- Rollback execution time: < 3 seconds on boot failure detection.
- Zero regression on existing MQTT-to-AMLP bridge telemetry latency (p95 < 50ms).

---

## 9. Hardware & Security Blockers
- **Physical Flash Inspection (#56 Gate):** Final partition sector mapping must be confirmed on target hardware before production flashing.
- **Key Management:** Private ECDSA signing keys must reside in a secure offline vault; only the public verification key is compiled into the firmware binary.
