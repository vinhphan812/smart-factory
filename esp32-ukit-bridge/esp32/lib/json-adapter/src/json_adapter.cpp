#include "json_adapter.h"

#include <cstdlib>
#include <cstring>

namespace bridge {

bool isDigitOnly(const char* s) {
  if (s == nullptr || *s == '\0') return false;
  const char* p = s;
  while (*p) {
    if (*p < '0' || *p > '9') return false;
    ++p;
  }
  return true;
}

bool parseSetOutputArgs(const char* arg0, const char* arg1) {
  if (arg0 == nullptr || arg1 == nullptr) return false;
  if (!isDigitOnly(arg0) || !isDigitOnly(arg1)) return false;

  char* endCh = nullptr;
  const unsigned long ch = std::strtoul(arg0, &endCh, 10);
  if (endCh == arg0 || *endCh != '\0' || ch > 255UL) return false;

  if (std::strcmp(arg1, "0") == 0) return true;
  if (std::strcmp(arg1, "1") == 0) return true;
  return false;
}

bool parseConveyorStartArg(const char* arg0) {
  if (arg0 == nullptr || !isDigitOnly(arg0)) return false;

  char* endSpd = nullptr;
  const long spd = std::strtol(arg0, &endSpd, 10);
  if (endSpd == arg0 || *endSpd != '\0') return false;
  return spd >= 1 && spd <= 100;
}

}  // namespace bridge
