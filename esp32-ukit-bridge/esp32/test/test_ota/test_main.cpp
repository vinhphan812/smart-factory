#include <unity.h>

#include <cstring>

#include "ota_manager.h"
#include "mocks/ota_mocks.h"

namespace {

ota::FirmwareMetadata makeMetadata(const char* version = "1.0.0") {
  ota::FirmwareMetadata meta{};
  std::strncpy(meta.version, version, sizeof(meta.version) - 1);
  meta.versionCode = 100;
  std::strncpy(meta.sha256,
               "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
               sizeof(meta.sha256) - 1);
  std::strncpy(meta.signature, "valid", sizeof(meta.signature) - 1);
  std::strncpy(meta.releaseAuthority, "test-authority",
                sizeof(meta.releaseAuthority) - 1);
  std::strncpy(meta.url, "https://firmware.example.com/fw.bin",
               sizeof(meta.url) - 1);
  meta.size = 1024;
  std::strncpy(meta.sku, "ESP32-S3", sizeof(meta.sku) - 1);
  meta.timestamp = 1234567890;
  return meta;
}

void test_initial_state_is_idle() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  ota::OtaManager ota(&transport, &partition, &verifier);

  TEST_ASSERT_TRUE(ota.isIdle());
  TEST_ASSERT_EQUAL_INT(static_cast<int>(ota::State::kIdle),
                        static_cast<int>(ota.state()));
  TEST_ASSERT_EQUAL_STRING("0.0.0", ota.currentVersion());
}

void test_request_update_transitions_to_download_scheduled() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  ota::OtaManager ota(&transport, &partition, &verifier);
  ota::FirmwareMetadata meta = makeMetadata("1.0.0");

  bool result = ota.requestUpdate(meta);

  TEST_ASSERT_TRUE(result);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(ota::State::kDownloadScheduled),
                        static_cast<int>(ota.state()));
  TEST_ASSERT_FALSE(ota.isIdle());
}

void test_request_update_rejects_invalid_metadata() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  ota::OtaManager ota(&transport, &partition, &verifier);

  // Empty version should fail validation
  ota::FirmwareMetadata meta = makeMetadata();
  meta.version[0] = '\0';

  bool result = ota.requestUpdate(meta);

  TEST_ASSERT_FALSE(result);
  TEST_ASSERT_TRUE(ota.isIdle());
}

void test_request_update_rejects_when_already_updating() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  ota::OtaManager ota(&transport, &partition, &verifier);
  ota::FirmwareMetadata meta = makeMetadata("1.0.0");

  TEST_ASSERT_TRUE(ota.requestUpdate(meta));

  // Try another update while one is in progress
  ota::FirmwareMetadata meta2 = makeMetadata("1.0.1");
  bool result = ota.requestUpdate(meta2);

  TEST_ASSERT_FALSE(result);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(ota::State::kDownloadScheduled),
                        static_cast<int>(ota.state()));
}

void test_maintenance_window_open_when_no_pending_commands() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  ota::OtaManager ota(&transport, &partition, &verifier);

  TEST_ASSERT_TRUE(ota.isMaintenanceWindowOpen(0));
  TEST_ASSERT_FALSE(ota.isMaintenanceWindowOpen(1));
  TEST_ASSERT_FALSE(ota.isMaintenanceWindowOpen(5));
}

void test_cancel_resets_to_idle() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  ota::OtaManager ota(&transport, &partition, &verifier);
  ota::FirmwareMetadata meta = makeMetadata();

  TEST_ASSERT_TRUE(ota.requestUpdate(meta));
  TEST_ASSERT_FALSE(ota.isIdle());

  bool result = ota.cancel();

  TEST_ASSERT_TRUE(result);
  TEST_ASSERT_TRUE(ota.isIdle());
  TEST_ASSERT_EQUAL_INT(static_cast<int>(ota::State::kIdle),
                        static_cast<int>(ota.state()));
}

void test_cancel_when_idle_returns_false() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  ota::OtaManager ota(&transport, &partition, &verifier);

  TEST_ASSERT_FALSE(ota.cancel());
}

void test_progress_returns_0_when_idle() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  ota::OtaManager ota(&transport, &partition, &verifier);

  TEST_ASSERT_EQUAL_UINT8(0, ota.progress());
}

void test_progress_returns_expected_values_per_state() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  ota::OtaManager ota(&transport, &partition, &verifier);

  // Idle
  TEST_ASSERT_EQUAL_UINT8(0, ota.progress());

  // DownloadScheduled
  ota::FirmwareMetadata meta = makeMetadata();
  ota.requestUpdate(meta);
  TEST_ASSERT_EQUAL_UINT8(0, ota.progress());
}

void test_tick_processes_download_scheduled_state() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  ota::OtaManager ota(&transport, &partition, &verifier);
  ota::FirmwareMetadata meta = makeMetadata();
  ota.requestUpdate(meta);

  // Tick should transition from DownloadScheduled to Downloading
  ota.tick(1000);

  TEST_ASSERT_EQUAL_INT(static_cast<int>(ota::State::kDownloading),
                        static_cast<int>(ota.state()));
}

void test_tick_completes_download_and_validates() {
  MockTransport transport;
  MockPartition partition;
  MockSignatureVerifier verifier;

  // Set up mock data for download
  uint8_t testData[256];
  std::memset(testData, 0x42, sizeof(testData));
  transport.setDownloadData(testData, sizeof(testData));

  ota::OtaManager ota(&transport, &partition, &verifier);
  ota::FirmwareMetadata meta = makeMetadata();
  meta.size = sizeof(testData);
  // Use "valid" checksum which the mock accepts
  std::strncpy(meta.sha256, "valid", sizeof(meta.sha256) - 1);
  ota.requestUpdate(meta);

  // Tick through the states
  while (ota.state() != ota::State::kIdle &&
         ota.state() != ota::State::kError) {
    ota.tick(ota.state() == ota::State::kDownloading ? 0 : 1000);
  }

  // Should complete successfully
  TEST_ASSERT_EQUAL_INT(static_cast<int>(ota::State::kIdle),
                        static_cast<int>(ota.state()));
  TEST_ASSERT_EQUAL_STRING("1.0.0", ota.currentVersion());
  TEST_ASSERT_TRUE(partition.wasWritten());
}

void test_partition_gets_inactive_partition() {
  MockPartition partition;

  TEST_ASSERT_EQUAL_STRING("A", partition.getRunningPartition());
  TEST_ASSERT_EQUAL_STRING("B", partition.getInactivePartition());

  partition.setRunningPartition("B");
  TEST_ASSERT_EQUAL_STRING("B", partition.getRunningPartition());
  TEST_ASSERT_EQUAL_STRING("A", partition.getInactivePartition());
}

void test_signature_verifier_mock() {
  MockSignatureVerifier verifier;

  uint8_t data[] = {0x01, 0x02, 0x03};

  // Default: verification succeeds
  TEST_ASSERT_TRUE(verifier.verify(data, sizeof(data), "signature"));

  // Can be configured to fail
  verifier.setShouldVerify(false);
  TEST_ASSERT_FALSE(verifier.verify(data, sizeof(data), "signature"));
}

void test_transport_mock() {
  MockTransport transport;

  // Default: connected
  TEST_ASSERT_TRUE(transport.isConnected());
  TEST_ASSERT_TRUE(transport.begin());

  // Can simulate disconnected
  transport.setConnected(false);
  TEST_ASSERT_FALSE(transport.isConnected());

  // Reset and test download
  transport.setConnected(true);
  uint8_t data[] = {0x01, 0x02, 0x03, 0x04, 0x05};
  transport.setDownloadData(data, sizeof(data));

  TEST_ASSERT_TRUE(transport.beginDownload("http://test.bin", sizeof(data)));

  uint8_t buffer[10] = {};
  uint32_t bytesRead = transport.read(buffer, 3);
  TEST_ASSERT_EQUAL_UINT32(3, bytesRead);
  TEST_ASSERT_EQUAL_UINT8(0x01, buffer[0]);
  TEST_ASSERT_EQUAL_UINT8(0x02, buffer[1]);
  TEST_ASSERT_EQUAL_UINT8(0x03, buffer[2]);

  bytesRead = transport.read(buffer, 3);
  TEST_ASSERT_EQUAL_UINT32(2, bytesRead);
  TEST_ASSERT_EQUAL_UINT8(0x04, buffer[0]);
  TEST_ASSERT_EQUAL_UINT8(0x05, buffer[1]);
}

}  // namespace

void setUp(void) {}

void tearDown(void) {}

int main() {
  UNITY_BEGIN();

  RUN_TEST(test_initial_state_is_idle);
  RUN_TEST(test_request_update_transitions_to_download_scheduled);
  RUN_TEST(test_request_update_rejects_invalid_metadata);
  RUN_TEST(test_request_update_rejects_when_already_updating);
  RUN_TEST(test_maintenance_window_open_when_no_pending_commands);
  RUN_TEST(test_cancel_resets_to_idle);
  RUN_TEST(test_cancel_when_idle_returns_false);
  RUN_TEST(test_progress_returns_0_when_idle);
  RUN_TEST(test_progress_returns_expected_values_per_state);
  RUN_TEST(test_tick_processes_download_scheduled_state);
  RUN_TEST(test_tick_completes_download_and_validates);
  RUN_TEST(test_partition_gets_inactive_partition);
  RUN_TEST(test_signature_verifier_mock);
  RUN_TEST(test_transport_mock);

  return UNITY_END();
}
