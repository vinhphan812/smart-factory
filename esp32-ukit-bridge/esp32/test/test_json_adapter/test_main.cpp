#include <unity.h>

#include <cstddef>
#include <cstdint>
#include <cstring>

#include "json_adapter.h"

namespace {

// ---------------------------------------------------------------------------
// json_adapter tests — isDigitOnly, parseSetOutputArgs, parseConveyorStartArg
// ---------------------------------------------------------------------------

void test_isDigitOnly_accepts_plain_digits(void) {
  TEST_ASSERT_TRUE(bridge::isDigitOnly("0"));
  TEST_ASSERT_TRUE(bridge::isDigitOnly("1"));
  TEST_ASSERT_TRUE(bridge::isDigitOnly("60"));
  TEST_ASSERT_TRUE(bridge::isDigitOnly("100"));
  TEST_ASSERT_TRUE(bridge::isDigitOnly("255"));
}

void test_isDigitOnly_rejects_nullptr(void) {
  TEST_ASSERT_FALSE(bridge::isDigitOnly(nullptr));
}

void test_isDigitOnly_rejects_empty_string(void) {
  TEST_ASSERT_FALSE(bridge::isDigitOnly(""));
}

void test_isDigitOnly_rejects_whitespace_prefix(void) {
  TEST_ASSERT_FALSE(bridge::isDigitOnly(" 60"));
  TEST_ASSERT_FALSE(bridge::isDigitOnly("\t60"));
  TEST_ASSERT_FALSE(bridge::isDigitOnly("60 "));
}

void test_isDigitOnly_rejects_plus_prefix(void) {
  TEST_ASSERT_FALSE(bridge::isDigitOnly("+60"));
}

void test_isDigitOnly_rejects_hex_prefix(void) {
  TEST_ASSERT_FALSE(bridge::isDigitOnly("0xFF"));
}

void test_isDigitOnly_rejects_hex_lowercase(void) {
  TEST_ASSERT_FALSE(bridge::isDigitOnly("0xff"));
}

void test_isDigitOnly_rejects_negative(void) {
  TEST_ASSERT_FALSE(bridge::isDigitOnly("-1"));
  TEST_ASSERT_FALSE(bridge::isDigitOnly("-60"));
}

void test_isDigitOnly_rejects_float(void) {
  TEST_ASSERT_FALSE(bridge::isDigitOnly("60.5"));
  TEST_ASSERT_FALSE(bridge::isDigitOnly("60.0"));
}

void test_isDigitOnly_rejects_mixed(void) {
  TEST_ASSERT_FALSE(bridge::isDigitOnly("60abc"));
  TEST_ASSERT_FALSE(bridge::isDigitOnly("6a0"));
}

void test_parseSetOutputArgs_accepts_valid_channel_and_value(void) {
  TEST_ASSERT_TRUE(bridge::parseSetOutputArgs("0", "0"));
  TEST_ASSERT_TRUE(bridge::parseSetOutputArgs("0", "1"));
  TEST_ASSERT_TRUE(bridge::parseSetOutputArgs("1", "0"));
  TEST_ASSERT_TRUE(bridge::parseSetOutputArgs("1", "1"));
  TEST_ASSERT_TRUE(bridge::parseSetOutputArgs("255", "0"));
  TEST_ASSERT_TRUE(bridge::parseSetOutputArgs("255", "1"));
}

void test_parseSetOutputArgs_rejects_channel_out_of_range(void) {
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("256", "1"));
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("999", "0"));
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("9999", "1"));
}

void test_parseSetOutputArgs_rejects_invalid_value(void) {
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("5", "2"));
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("5", "10"));
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("5", "abc"));
}

void test_parseSetOutputArgs_rejects_trailing_garbage(void) {
  // These pass isDigitOnly so would reach strtoul; strtoul stops at non-digit.
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("60x", "1"));
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("5", "1x"));
}

void test_parseSetOutputArgs_rejects_non_decimal(void) {
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("+5", "1"));
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs(" 5", "1"));
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("0x10", "1"));
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("5", "+0"));
}

void test_parseSetOutputArgs_rejects_nullptr(void) {
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs(nullptr, "1"));
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs("1", nullptr));
  TEST_ASSERT_FALSE(bridge::parseSetOutputArgs(nullptr, nullptr));
}

void test_parseConveyorStartArg_accepts_valid_speed(void) {
  TEST_ASSERT_TRUE(bridge::parseConveyorStartArg("1"));
  TEST_ASSERT_TRUE(bridge::parseConveyorStartArg("50"));
  TEST_ASSERT_TRUE(bridge::parseConveyorStartArg("100"));
}

void test_parseConveyorStartArg_rejects_out_of_range(void) {
  TEST_ASSERT_FALSE(bridge::parseConveyorStartArg("0"));
  TEST_ASSERT_FALSE(bridge::parseConveyorStartArg("101"));
  TEST_ASSERT_FALSE(bridge::parseConveyorStartArg("999"));
}

void test_parseConveyorStartArg_rejects_non_decimal(void) {
  TEST_ASSERT_FALSE(bridge::parseConveyorStartArg("+50"));
  TEST_ASSERT_FALSE(bridge::parseConveyorStartArg("-50"));
  TEST_ASSERT_FALSE(bridge::parseConveyorStartArg(" 50"));
  TEST_ASSERT_FALSE(bridge::parseConveyorStartArg("50.0"));
  TEST_ASSERT_FALSE(bridge::parseConveyorStartArg("0x32"));
}

void test_parseConveyorStartArg_rejects_nullptr(void) {
  TEST_ASSERT_FALSE(bridge::parseConveyorStartArg(nullptr));
}

}  // namespace

void setUp() {}
void tearDown() {}

int main() {
  UNITY_BEGIN();
  // isDigitOnly
  RUN_TEST(test_isDigitOnly_accepts_plain_digits);
  RUN_TEST(test_isDigitOnly_rejects_nullptr);
  RUN_TEST(test_isDigitOnly_rejects_empty_string);
  RUN_TEST(test_isDigitOnly_rejects_whitespace_prefix);
  RUN_TEST(test_isDigitOnly_rejects_plus_prefix);
  RUN_TEST(test_isDigitOnly_rejects_hex_prefix);
  RUN_TEST(test_isDigitOnly_rejects_hex_lowercase);
  RUN_TEST(test_isDigitOnly_rejects_negative);
  RUN_TEST(test_isDigitOnly_rejects_float);
  RUN_TEST(test_isDigitOnly_rejects_mixed);
  // parseSetOutputArgs
  RUN_TEST(test_parseSetOutputArgs_accepts_valid_channel_and_value);
  RUN_TEST(test_parseSetOutputArgs_rejects_channel_out_of_range);
  RUN_TEST(test_parseSetOutputArgs_rejects_invalid_value);
  RUN_TEST(test_parseSetOutputArgs_rejects_trailing_garbage);
  RUN_TEST(test_parseSetOutputArgs_rejects_non_decimal);
  RUN_TEST(test_parseSetOutputArgs_rejects_nullptr);
  // parseConveyorStartArg
  RUN_TEST(test_parseConveyorStartArg_accepts_valid_speed);
  RUN_TEST(test_parseConveyorStartArg_rejects_out_of_range);
  RUN_TEST(test_parseConveyorStartArg_rejects_non_decimal);
  RUN_TEST(test_parseConveyorStartArg_rejects_nullptr);
  return UNITY_END();
}
