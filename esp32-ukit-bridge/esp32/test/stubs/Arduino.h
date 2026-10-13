// Minimal Arduino.h stub for native unit tests.
// Defines only the types and macros used by esp32 firmware sources.

#pragma once

#include <cstdint>

// HardwareSerial is never instantiated in tests — feedBytes() bypasses serial.
// Declared in the global namespace to match ESP-IDF header layout.
class HardwareSerial {
 public:
  explicit HardwareSerial(int) {}
  void begin(uint32_t, int, int, int) const {}  // const to allow const instances
  int available() const { return 0; }
  int read() { return -1; }
  size_t write(const uint8_t*, size_t) { return 0; }
};

// Serial config mode (passed to begin but unused in native tests).
constexpr int SERIAL_8N1 = 0;
