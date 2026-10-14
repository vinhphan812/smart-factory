# ADR-0008: Event-driven OtaManager (No Dedicated FreeRTOS Task)

**Status:** Proposed
**Date:** 2026-10-14
**Deciders:** Issue #73
**Related issues:** #72 #73

## Context

The ESP32 bridge runs on FreeRTOS with tasks for Wi-Fi management, MQTT loop, UART polling, and command bridging. Adding an OTA download task would compete for CPU time and could starve the critical control loop if it blocks or uses excessive memory.

A naive approach — create a dedicated FreeRTOS task for OTA — risks priority inversion: if the OTA task has lower priority than the Wi-Fi/MQTT tasks, downloads stall. If it has higher priority, control commands are delayed.

## Decision

The OTA subsystem is implemented as an **event-driven OtaManager state machine** driven by short `tick()` calls from the existing bridge `loop()`:

```
loop() {
  wifi.tick();
  uart.poll();
  bridgeCore.tick();
  mqttBridge.tick();
  otaManager.tick();   // ← short non-blocking step
}
```

**Properties:**
- OtaManager runs on the main loop thread (not a separate FreeRTOS task)
- Each `tick()` call processes at most one chunk of work (non-blocking)
- State machine: Idle → DownloadScheduled → Downloading → Validating → Staging → Rebooting → Active
- Wi-Fi, UART, and MQTT processing continue uninterrupted during download
- Memory budget is fixed: bounded download buffer, no dynamic allocation during staging

**Anti-starvation measures:**
- OTA download uses cooperative yielding (call `delay(0)` or `vTaskDelay(1)` between chunks)
- Progress events published to MQTT for monitoring
- If Wi-Fi disconnects, download pauses and resumes on reconnect (not a new task)
- If UART/MQTT health degrades, OTA can be aborted before staging (safety gate)

**Future optional improvement (not implemented yet):**
- A dedicated FreeRTOS OTA task could be added if Issue #74 demonstrates CPU starvation
- The current design uses a `Transport` interface so the task option is a future swap, not a redesign

## Consequences

**Easier:**
- No priority management between OTA and control tasks
- Simpler debugging (single-threaded call stack)
- State machine is independently unit-testable without FreeRTOS mocks

**Harder:**
- OTA download speed is limited by how quickly `tick()` yields
- Large firmware images take longer to download (no parallel download + control)
- Requires careful yield management to avoid blocking UART/MQTT

## Alternatives considered

**Option A: Dedicated FreeRTOS OTA task (high priority)**
- Pro: fastest possible download
- Con: must pin to core, manage priority vs Wi-Fi/MQTT tasks, harder to test
- Rejected: premature optimization; no evidence of starvation from #74 measurements

**Option B: Dedicated FreeRTOS OTA task (low priority)**
- Pro: never starves critical tasks
- Con: download may be unacceptably slow; task management overhead
- Rejected: same as above

**Option C: ESP-IDF OTA with dedicated partition and callbacks**
- Uses ESP-IDF's built-in OTA system
- Rejected: requires replacing Arduino framework with ESP-IDF; out of scope for current platform choice

## Evidence

- Issue #73 Implementation decision LOCKED: "OtaManager as independently unit-testable event-driven state machine"
- Issue #73 Implementation decision LOCKED: "Do **not** create dedicated FreeRTOS OTA tasks, pin tasks to cores or replace Arduino with ESP-IDF"
- Issue #74: "Build OTA release pipeline, staged rollout and real ESP32-S3 recovery test matrix" — will produce measurements that could justify adding a dedicated task
