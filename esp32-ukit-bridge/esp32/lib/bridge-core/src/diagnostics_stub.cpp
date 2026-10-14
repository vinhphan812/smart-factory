// Strong definition of bridge::g_diagnostics for the native_test build.
// diagnostics.cpp cannot be compiled here (requires Arduino/WiFi/ArduinoJson).
#include "diagnostics.h"

namespace bridge {

DiagnosticsCounters g_diagnostics;

}  // namespace bridge
