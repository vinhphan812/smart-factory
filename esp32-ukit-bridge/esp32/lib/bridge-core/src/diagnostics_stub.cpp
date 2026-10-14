// Stub providing the strong definition of bridge::g_diagnostics for the
// native_test build, which does not compile diagnostics.cpp (depends on
// Arduino/WiFi/ArduinoJson). This file is only compiled in native_test via
// build_src_filter; for the ESP32 build diagnostics.cpp provides the symbol.
#include "diagnostics.h"

namespace bridge {
DiagnosticsCounters g_diagnostics;
}  // namespace bridge
