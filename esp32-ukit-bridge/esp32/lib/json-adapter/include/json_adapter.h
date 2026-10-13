#ifndef BRIDGE_JSON_ADAPTER_H_
#define BRIDGE_JSON_ADAPTER_H_

#include <cstdint>

namespace bridge {

// Pure C++ argument parser helpers — no Arduino, no ArduinoJson.
// These functions implement the canonical numeric-argument parsing rules used
// by the JSON adapter layer in mqtt_bridge.cpp.

// Returns true only if s is one or more ASCII decimal digits 0–9.
// Rejects: null, empty, leading/trailing whitespace, leading '+', hex prefix,
// or any embedded non-digit character. This enforces the canonical wire format.
bool isDigitOnly(const char* s);

// Pre-parse SET_OUTPUT arguments from raw string pointers.
// Fills out.channel, out.outputValue, out.channelParsed, out.valueParsed.
// Returns true if both channel (0..255) and value ("0" or "1") were parsed.
bool parseSetOutputArgs(const char* arg0, const char* arg1);

// Pre-parse CONVEYOR_START speed from a raw string pointer.
// Fills out.speedArg (1..100), out.speedParsed.
// Returns true if speed was parsed and within range.
bool parseConveyorStartArg(const char* arg0);

}  // namespace bridge

#endif  // BRIDGE_JSON_ADAPTER_H_
