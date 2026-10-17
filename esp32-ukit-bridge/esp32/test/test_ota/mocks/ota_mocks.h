#pragma once

#include <cstring>
#include <vector>

#include "ota_manager.h"

/**
 * Mock transport for testing OTA downloads without network.
 */
class MockTransport final : public ota::Transport {
 public:
  MockTransport() : connected_(true), downloadStarted_(false), offset_(0) {}

  void setConnected(bool connected) { connected_ = connected; }

  void setDownloadData(const uint8_t* data, size_t size) {
    data_.assign(data, data + size);
    offset_ = 0;
  }

  void setDownloadFail(bool fail) { downloadFail_ = fail; }

  uint32_t readCount() const { return readCount_; }

  bool begin() override { return connected_; }

  bool isConnected() override { return connected_; }

  bool beginDownload(const char* url, uint32_t size) override {
    (void)url;
    (void)size;
    if (downloadFail_) {
      return false;
    }
    downloadStarted_ = true;
    offset_ = 0;
    return true;
  }

  uint32_t read(uint8_t* buffer, uint32_t size) override {
    if (!downloadStarted_ || offset_ >= data_.size()) {
      return 0;
    }
    ++readCount_;
    uint32_t toRead = size;
    if (offset_ + toRead > data_.size()) {
      toRead = static_cast<uint32_t>(data_.size() - offset_);
    }
    std::memcpy(buffer, data_.data() + offset_, toRead);
    offset_ += toRead;
    return toRead;
  }

  uint32_t progress() const override { return offset_; }

  void end() override { downloadStarted_ = false; }

 private:
  bool connected_;
  bool downloadStarted_;
  bool downloadFail_;
  std::vector<uint8_t> data_;
  uint32_t offset_;
  uint32_t readCount_;
};

/**
 * Mock partition for testing A/B slot management.
 */
class MockPartition final : public ota::Partition {
 public:
  MockPartition() : runningPartition_("A"), bootCandidate_("A") {}

  const char* getRunningPartition() const override { return runningPartition_; }

  const char* getInactivePartition() const override {
    return (std::strcmp(runningPartition_, "A") == 0) ? "B" : "A";
  }

  bool setBootCandidate(const char* partition) override {
    bootCandidate_[0] = partition[0];
    bootCandidate_[1] = '\0';
    return true;
  }

  bool write(uint32_t offset, const uint8_t* data, uint32_t size) override {
    if (offset + size > kFlashSize) {
      return false;
    }
    std::memcpy(flash_ + offset, data, size);
    written_ = true;
    return true;
  }

  bool read(const char* partition, uint32_t offset, uint8_t* buffer,
            uint32_t size) override {
    (void)partition;
    if (offset + size > kFlashSize) {
      return false;
    }
    std::memcpy(buffer, flash_ + offset, size);
    return true;
  }

  bool verifyChecksum(const char* partition,
                     const char* expectedSha256) override {
    (void)partition;
    // Simple mock: return true if expectedSha256 is "valid"
    // In real implementation, would compute SHA-256
    return std::strcmp(expectedSha256, "valid") == 0 ||
           std::strcmp(expectedSha256,
                      "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855") == 0;
  }

  void reboot() override { rebootRequested_ = true; }

  void setRunningPartition(const char* p) { 
    runningPartition_[0] = p[0];
    runningPartition_[1] = '\0';
  }

  bool rebootRequested() const { return rebootRequested_; }
  bool wasWritten() const { return written_; }

 private:
  static constexpr size_t kFlashSize = 2 * 1024 * 1024;  // 2MB mock flash
  char runningPartition_[2];
  char bootCandidate_[2];
  uint8_t flash_[kFlashSize];
  bool rebootRequested_;
  bool written_;
};

/**
 * Mock signature verifier for testing.
 */
class MockSignatureVerifier final : public ota::SignatureVerifier {
 public:
  MockSignatureVerifier() : shouldVerify_(true) {}

  void setShouldVerify(bool should) { shouldVerify_ = should; }

  bool verify(const uint8_t* data, uint32_t size,
              const char* signature) override {
    (void)data;
    (void)size;
    (void)signature;
    return shouldVerify_;
  }

 private:
  bool shouldVerify_;
};
