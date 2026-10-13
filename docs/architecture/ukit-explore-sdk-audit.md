# Issue #56 Audit Report: uKit Explore v1/v2 SDK, Arduino Mega Pinout, Dependencies, and Licensing

**Status:** Completed L0/L1 Architectural Audit & Evidence Review (Physical HIL and Vendor Redistribution: **BLOCKED** pending bench signoff and licensing clearance).
**Owner Task:** Kanban `t_6784d6e7` / GitHub Issue [#56](https://github.com/vinhphan812/smart-factory/issues/56).
**Target Branch:** `docs/issue-56-ukit-explore-sdk-audit` (derived from `origin/master`).

---

## 1. Executive Summary

This audit report evaluates the uKit Explore v1/v2 software development kit (SDK), Arduino Mega 2560 microcontroller target assumptions, transitive library dependencies, licensing posture, and electrical/hardware integration prerequisites for the AIBOT Smart Factory project. 

In accordance with system design principles and `docs/architecture/ukit-mega-sdk-integration.md`, the C99 portable reference (`esp32-ukit-bridge/ukit/`) remains isolated from Arduino firmware. This audit establishes the baseline evidence required before proceeding to downstream firmware targets (#57), AMLP transport ports (#58), bounded driver functions (#59), and hardware-in-the-loop (HIL) integration (#60).

---

## 2. Official Source Material & Version Evidence

The audit examined official upstream vendor resources cited in project specifications:
1. **UBTECH GitBook Documentation:**
   - [Getting the SDK](https://ubtechedu.gitbook.io/ukit-explore/ukit-explore-quick-start/get-sdk): Instructs installation via Arduino IDE library ZIP and selection of Arduino Mega / Mega 2560 board profile.
   - [Library & V1/V2 Support Guide](https://ubtechedu.gitbook.io/ukit-explore/standard/ukit-explore-library-file): Identifies the primary controller as Arduino Mega 2560, details header variations between v1 and v2 controller revisions, and mandates explicit calls to `Initialization()`.
2. **Official Vendor Code Repository:**
   - [GitHub: UBTEDU/uKitExplore-library](https://github.com/UBTEDU/uKitExplore-library):
     - **Declared Version:** `library.properties` specifies version `1.2.28-1`.
     - **Transitive Dependencies:** Pins `ArduinoJson (=6.19.5)` and `IRremote (=3.9.0)`.
     - **Licensing Posture:** The repository does not visibly contain an explicit root `LICENSE` file. Consequently, vendor code redistribution, vendoring into public repositories, or binary distribution requires formal project legal clearance or clean-room abstraction wrapper design. **Classification:** Pending explicit license review or wrapper isolation.

---

## 3. Arduino Mega Target & V1/V2 Board Architecture

### 3.1 Microcontroller Specifications
- **MCU:** ATmega2560 (8-bit AVR RISC architecture)
- **Clock Speed:** 16 MHz
- **Memory:** 256 KB Flash (8 KB used by bootloader), 8 KB SRAM, 4 KB EEPROM.
- **Implication:** Constrained memory footprint requires careful static allocation and prevents running heavy JSON parsing libraries concurrently with complex application logic unless strictly bounded.

### 3.2 Board Revisions (v1 vs v2)
- **v1 Controllers:** Utilize legacy pin headers (`uKitExplore.h`), distinct port mappings for DC motors, servos, and analog/digital sensors.
- **v2 Controllers:** Introduce updated header layouts (`uKitExplore2.h`), expanded sensor multiplexing, and revised power distribution.
- **Requirement:** Firmware abstraction must conditionally include headers based on board revision compile flags (`-DUBTECH_UKIT_V1` vs `-DUBTECH_UKIT_V2`).

### 3.3 Initialization & Serial Communication
- The vendor library mandates `Initialization()` during `setup()`.
- **Serial Conflict Warning:** The vendor library initializes hardware serial interfaces (`Serial`, `Serial1`, etc.) for internal sensor/servo bus communication. Debug logging directly over the primary UART bus will corrupt framing. A dedicated, isolated serial channel or software serial must be established for AMLP transport.

---

## 4. SDK / API Compatibility & Protocol Boundaries

### 4.1 Architectural Separation
- **ESP32-S3 Bridge (`esp32-ukit-bridge/esp32/`):** Handles Wi-Fi MQTT JSON commands and bridges them via AMLP v1 binary framing over UART.
- **C99 Portable Reference (`esp32-ukit-bridge/ukit/`):** Pure C99 protocol reference parser, checksum verification, and state machine. Remains decoupled from Arduino SDK.
- **Arduino Mega Firmware Target (`esp32-ukit-bridge/ukit/mega/` — Proposed #57):** The sole domain permitted to include the vendor C++ library (`uKitExplore.h`).

### 4.2 Dependency Version Conflict Prevention
- The ESP32 firmware stack utilizes modern ArduinoJson (v7.x).
- Upstream uKit Explore library strictly pins `ArduinoJson (=6.19.5)`.
- **Constraint:** Attempting to compile the ESP32 bridge with uKit library dependencies would introduce a version collision. Strict build isolation (separate PlatformIO projects) is mandatory.

---

## 5. Electrical, Hardware & Safety Prerequisites (Explicitly BLOCKED)

Physical hardware integration and HIL testing are **BLOCKED** absent verified empirical evidence:
1. **Logic Level Voltage Mismatch:** Arduino Mega operates at **5V TTL** logic levels, whereas ESP32-S3 operates at **3.3V LVTTL**. Direct connection risks damaging ESP32 RX/TX pins. A robust bidirectional logic level shifter and shared common ground are mandatory.
2. **Power Supply & Current Limits:** Servo motors and actuators draw high peak currents. Power rails must be isolated between logic controllers (Mega/ESP32) and actuator motor power supplies to prevent brownouts and voltage spikes.
3. **Physical Availability & Revision Verification:** Actual physical boards, sensors, and modular components in the AIBOT lab must be inspected with a multimeter to verify pinout voltages and port assignments.
4. **Emergency Stop (E-Stop):** Hardware-level physical E-stop interrupting motor power is required prior to any automated physical actuation. Software signals alone are insufficient.

---

## 6. Next Steps & Unblocks for Downstream Tasks

- **Issue #57 (Separate Firmware Target):** Create isolated PlatformIO project structure under `esp32-ukit-bridge/ukit/mega/` targeting `megaatmega2560`, pin version 1.2.28-1 of vendor library and ArduinoJson 6.19.5.
- **Issue #58 (AMLP Transport Port):** Implement non-blocking AMLP v1 frame reception on Arduino Mega serial port, integrating CRC-16/CCITT-FALSE validation and ACK generation without blocking main loop execution.
- **Issue #59 (Bounded Driver Functions):** Wrap vendor functions (`setMotorTurn`, `setServoAngle`, etc.) with parameter bounds checking, local watchdog timers, and safe default states on timeout.
- **Issue #60 (CI, Evidence & HIL):** Establish CI compilation checks (without flashing unverified hardware) and conduct supervised L3/L4 bench tests with verified level shifting and physical E-stop.
- **Issue #72:** System integration coordination.
