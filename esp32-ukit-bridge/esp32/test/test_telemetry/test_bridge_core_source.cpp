// test_bridge_core_source.cpp
//
// bridge_core.cpp is needed by integration tests (UartAdapter uses BridgeCore&
// as a poll() parameter).  It has no Arduino dependencies so it can be compiled
// directly in the test build alongside the production source.

#include "../lib/bridge-core/src/bridge_core.cpp"
