// test_uart_adapter_source.cpp
//
// In the native PlatformIO test build, build_src_filter=-<*> excludes esp32/src/
// so uart_adapter.cpp is never compiled.  This translation unit provides the
// definitions that test_integration.cpp needs by including the production source
// directly (it's a single-file module with no Arduino dependencies beyond what
// the stub header covers).
//
// Note: include order matters.  Stub headers (Arduino.h) must come before
// any production headers that transitively include them.

#include "../stubs/Arduino.h"
#include "../src/uart_adapter.cpp"
