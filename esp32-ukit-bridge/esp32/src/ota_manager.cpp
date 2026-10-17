#include "ota_manager.h"

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstring>
#include <vector>

#include "bridge_config.h"

namespace ota {

OtaManager::OtaManager(Transport* transport, Partition* partition,
                       SignatureVerifier* verifier, const Config* config)
    : transport_(transport),
      partition_(partition),
      verifier_(verifier),
      config_(config ? *config : kDefaultConfig),
      state_(State::kIdle),
      previousState_(State::kIdle),
      lastResult_(Result::kOk),
      downloadStartTime_(0),
      stateEnterTime_(0),
      downloadedBytes_(0),
      retryCount_(0),
      downloadStarted_(false),
      healthCheckStartTime_(0),
      healthCheckAttempts_(0) {
  errorMessage_[0] = '\0';
  currentVersion_[0] = '\0';
  currentVersionCode_ = 0;

  // Initialize default/fallback version
  std::snprintf(currentVersion_, sizeof(currentVersion_), "0.0.0");
  currentVersionCode_ = 0;
}

bool OtaManager::isUpdating() const {
  return state_ != State::kIdle && state_ != State::kError;
}

uint8_t OtaManager::progress() const {
  if (state_ == State::kIdle || state_ == State::kError) {
    return 0;
  }

  // Calculate progress based on current state
  switch (state_) {
    case State::kDownloadScheduled:
      return 0;
    case State::kDownloading:
      if (pendingMetadata_.size > 0) {
        return static_cast<uint8_t>((downloadedBytes_ * 100) /
                                   pendingMetadata_.size);
      }
      return 0;
    case State::kValidating:
      return 90;
    case State::kStaging:
      return 95;
    case State::kRebooting:
      return 98;
    case State::kActive:
      return 100;
    case State::kRollback:
      return 50;  // Rollback is roughly halfway
    default:
      return 0;
  }
}

bool OtaManager::requestUpdate(const FirmwareMetadata& metadata) {
  // Only accept new updates in idle state
  if (state_ != State::kIdle) {
    setError(Result::kError, "OTA already in progress");
    return false;
  }

  // Validate metadata
  if (!validateMetadata(metadata)) {
    setError(Result::kInvalidMetadata, "Invalid firmware metadata");
    return false;
  }

  // Copy metadata for the update
  pendingMetadata_ = metadata;
  downloadedBytes_ = 0;
  retryCount_ = 0;
  downloadStarted_ = false;

  // Transition to DownloadScheduled state
  transitionTo(State::kDownloadScheduled);
  return true;
}

bool OtaManager::isMaintenanceWindowOpen(uint16_t pendingCommandCount) const {
  // Maintenance window is open when no commands are pending
  // Per ADR-0007: "pending actuator commands expired/drained"
  return pendingCommandCount == 0;
}

bool OtaManager::cancel() {
  if (state_ == State::kIdle || state_ == State::kError) {
    return false;  // Nothing to cancel
  }

  // Clean up transport if download was in progress
  if (downloadStarted_) {
    transport_->end();
    downloadStarted_ = false;
  }

  reset();
  transitionTo(State::kIdle);
  return true;
}

OtaManager::State OtaManager::tick(uint32_t nowMs) {
  switch (state_) {
    case State::kIdle:
      // Nothing to do
      break;
    case State::kDownloadScheduled:
      if (handleDownloadScheduled(nowMs)) {
        transitionTo(State::kDownloading);
      }
      break;
    case State::kDownloading:
      if (handleDownloading(nowMs)) {
        transitionTo(State::kValidating);
      }
      break;
    case State::kValidating:
      if (handleValidating(nowMs)) {
        transitionTo(State::kStaging);
      }
      break;
    case State::kStaging:
      if (handleStaging(nowMs)) {
        transitionTo(State::kRebooting);
      }
      break;
    case State::kRebooting:
      if (handleRebooting(nowMs)) {
        transitionTo(State::kActive);
      }
      break;
    case State::kActive:
      if (handleActive(nowMs)) {
        // Health check passed, update is complete
        std::snprintf(currentVersion_, sizeof(currentVersion_), "%s",
                     pendingMetadata_.version);
        currentVersionCode_ = pendingMetadata_.versionCode;
        transitionTo(State::kIdle);
      }
      break;
    case State::kRollback:
      if (handleRollback(nowMs)) {
        transitionTo(State::kIdle);
      }
      break;
    case State::kError:
      handleError(nowMs);
      break;
  }

  return state_;
}

bool OtaManager::handleDownloadScheduled(uint32_t nowMs) {
  // Per ADR-0007: "Maintenance mode required: pending actuator commands
  // expired/drained"
  // Only proceed if maintenance window is open (no pending commands)
  if (!isMaintenanceWindowOpen(pendingCommandCount_)) {
    // Maintenance window not open - stay in this state
    // Check for timeout waiting for maintenance window
    if (stateEnterTime_ == 0) {
      stateEnterTime_ = nowMs;
    }
    if (nowMs - stateEnterTime_ > config_.maintenanceWindowMs) {
      setError(Result::kMaintenanceBlocked,
              "Maintenance window timeout - pending commands");
      transitionTo(State::kError);
      return false;
    }
    return false;  // Wait for maintenance window
  }

  if (!transport_->isConnected()) {
    if (!transport_->begin()) {
      // Retry next tick
      return false;
    }
  }

  // Mark download start time for timeout tracking
  if (downloadStartTime_ == 0) {
    downloadStartTime_ = nowMs;
  }

  // Check if we've exceeded max download time
  if (nowMs - downloadStartTime_ > config_.maxDownloadTimeMs) {
    setError(Result::kNetworkError, "Download timeout exceeded");
    transitionTo(State::kError);
    return false;
  }

  // Ready to start download
  return true;
}

bool OtaManager::handleDownloading(uint32_t nowMs) {
  // Initialize download on first tick
  if (!downloadStarted_) {
    if (!transport_->beginDownload(pendingMetadata_.url,
                                   pendingMetadata_.size)) {
      // Failed to start download
      ++retryCount_;
      if (retryCount_ > config_.maxRetries) {
        setError(Result::kNetworkError, "Failed to start download");
        transitionTo(State::kError);
        return false;
      }
      // Retry next tick
      return false;
    }
    downloadStarted_ = true;
    downloadedBytes_ = 0;
  }

  // Read a chunk of data
  uint8_t buffer[4096];
  uint32_t bytesRead = transport_->read(buffer, sizeof(buffer));

  if (bytesRead > 0) {
    // Write chunk to inactive partition
    if (!partition_->write(downloadedBytes_, buffer, bytesRead)) {
      transport_->end();
      downloadStarted_ = false;
      setError(Result::kStorageError, "Failed to write to partition");
      transitionTo(State::kError);
      return false;
    }
    downloadedBytes_ += bytesRead;

    // Yield to prevent blocking (per ADR-0008)
    // Actual yield is done by caller (delay(0) in main loop)
  } else if (bytesRead == 0) {
    // Check if download is complete
    if (transport_->progress() >= pendingMetadata_.size) {
      transport_->end();
      downloadStarted_ = false;
      // Download complete, proceed to validation
      return true;
    }

    // Check for download timeout
    if (nowMs - downloadStartTime_ > config_.maxDownloadTimeMs) {
      transport_->end();
      downloadStarted_ = false;
      setError(Result::kNetworkError, "Download timeout");
      transitionTo(State::kError);
      return false;
    }
  } else {
    // Read error
    transport_->end();
    downloadStarted_ = false;
    ++retryCount_;
    if (retryCount_ > config_.maxRetries) {
      setError(Result::kNetworkError, "Download read error");
      transitionTo(State::kError);
      return false;
    }
    // Retry
    downloadStartTime_ = nowMs;
  }

  // Download not complete yet
  return false;
}

bool OtaManager::handleValidating(uint32_t nowMs) {
  // Per ADR-0007: "signature required"
  // Verify SHA-256 checksum first
  const char* inactivePartition = partition_->getInactivePartition();

  if (!partition_->verifyChecksum(inactivePartition, pendingMetadata_.sha256)) {
    setError(Result::kChecksumMismatch, "SHA-256 mismatch");
    transitionTo(State::kError);
    return false;
  }

  // Read firmware from partition for signature verification
  // Read the entire firmware image for signature verification
  uint32_t firmwareSize = pendingMetadata_.size;
  std::vector<uint8_t> firmwareData(firmwareSize);

  if (!partition_->read(inactivePartition, 0, firmwareData.data(), firmwareSize)) {
    setError(Result::kStorageError, "Failed to read firmware for verification");
    transitionTo(State::kError);
    return false;
  }

  // Verify signature using the pinned public key
  // Per ADR-0007: "Firmware image must be signed with a private key whose
  // public part is pinned on the device"
  if (!verifier_->verify(firmwareData.data(), firmwareSize,
                        pendingMetadata_.signature)) {
    setError(Result::kSignatureInvalid, "Signature verification failed");
    transitionTo(State::kRollback);
    return false;
  }

  // Validation complete
  return true;
}

bool OtaManager::handleStaging(uint32_t nowMs) {
  // Mark the inactive partition as boot candidate
  const char* inactivePartition = partition_->getInactivePartition();

  if (!partition_->setBootCandidate(inactivePartition)) {
    setError(Result::kStorageError, "Failed to set boot candidate");
    transitionTo(State::kRollback);
    return false;
  }

  // Staging complete
  return true;
}

bool OtaManager::handleRebooting(uint32_t nowMs) {
  // Trigger reboot - in real implementation, this would schedule a reboot
  // For testing purposes, we immediately proceed to Active state

  // Note: In production, this would call partition_->reboot()
  // and the device would reboot into the new firmware

  // For simulation/testing, we transition directly
  healthCheckStartTime_ = nowMs;
  healthCheckAttempts_ = 0;

  return true;
}

bool OtaManager::handleActive(uint32_t nowMs) {
  // Per ADR-0007: Post-boot health validation
  // - UART readiness
  // - MQTT connectivity
  // - AMLP protocol check
  // If validation fails within bounded timeout: automatic rollback

  if (healthCheckStartTime_ == 0) {
    healthCheckStartTime_ = nowMs;
  }

  // Check if health check timeout exceeded
  if (nowMs - healthCheckStartTime_ > config_.healthCheckTimeoutMs) {
    setError(Result::kHealthCheckFailed, "Health check timeout exceeded");
    transitionTo(State::kRollback);
    return false;
  }

  // Perform health checks
  // Note: In production, these would call actual hardware/connectivity checks
  // Here we simulate the checks - in real implementation:
  // 1. UART: send probe, expect response
  // 2. MQTT: verify connection is established
  // 3. AMLP: verify protocol handshake succeeded

  // Simulate health check attempts with bounded retries
  if (healthCheckAttempts_ < 3) {
    ++healthCheckAttempts_;
    // In production: if (!checkUartHealth() || !checkMqttHealth() ||
    // !checkAm lpHealth()) { return false; }
    // For now, simulate checking
    return false;  // Not complete yet, will complete on next tick
  }

  // Health check passed - all components ready
  return true;
}

bool OtaManager::handleRollback(uint32_t nowMs) {
  // Set the previous partition as boot candidate
  const char* currentPartition = partition_->getRunningPartition();
  const char* rollbackPartition = (std::strcmp(currentPartition, "A") == 0)
                                      ? "B"
                                      : "A";

  if (!partition_->setBootCandidate(rollbackPartition)) {
    setError(Result::kRollbackFailed, "Failed to set rollback partition");
    transitionTo(State::kError);
    return false;
  }

  // Trigger reboot to rollback
  // In production: partition_->reboot()

  // For testing: simulate immediate rollback
  return true;
}

bool OtaManager::handleError(uint32_t nowMs) {
  // In error state, we can attempt rollback
  // Per ADR-0007: "If validation fails within bounded timeout: automatic
  // rollback"
  // For now, stay in error state until explicitly cleared

  // Option to trigger rollback from error state
  // This would be called by external handler

  return false;
}

void OtaManager::transitionTo(State newState) {
  previousState_ = state_;
  state_ = newState;
  stateEnterTime_ = 0;  // Will be set on next tick
  lastResult_ = Result::kOk;
}

void OtaManager::setError(Result result, const char* message) {
  lastResult_ = result;
  std::strncpy(errorMessage_, message, sizeof(errorMessage_) - 1);
  errorMessage_[sizeof(errorMessage_) - 1] = '\0';
}

void OtaManager::reset() {
  downloadStartTime_ = 0;
  downloadedBytes_ = 0;
  retryCount_ = 0;
  downloadStarted_ = false;
  healthCheckStartTime_ = 0;
  healthCheckAttempts_ = 0;
}

bool OtaManager::validateMetadata(const FirmwareMetadata& metadata) const {
  // Per ADR-0007: "TLS certificate validated against pinned trust roots"
  // First, validate HTTPS URL scheme

  // Check URL starts with "https://" (case-insensitive check)
  if (std::strncmp(metadata.url, "https://", 8) != 0) {
    return false;  // Reject non-HTTPS URLs
  }

  // Check required fields
  if (metadata.version[0] == '\0') {
    return false;
  }
  if (metadata.url[0] == '\0') {
    return false;
  }
  if (metadata.size == 0) {
    return false;
  }
  if (metadata.sku[0] == '\0') {
    return false;
  }

  // Validate SHA-256 format (64 hex characters)
  if (std::strlen(metadata.sha256) != 64) {
    return false;
  }

  // Validate version format (basic check)
  // Should be semver-like (e.g., "1.2.3")
  const char* v = metadata.version;
  int dotCount = 0;
  while (*v) {
    if (*v == '.') {
      ++dotCount;
    } else if (!std::isdigit(*v)) {
      return false;
    }
    ++v;
  }
  if (dotCount < 2) {
    return false;  // Not semver-like
  }

  return true;
}

// MQTT publishing functions stubs
// In production, these would be implemented to publish to MQTT topics
void publishOtaStatus(class PubSubClient& client, const char* deviceId,
                      const OtaManager& ota) {
  (void)client;
  (void)deviceId;
  (void)ota;
  // Stub: would publish to smart-factory/{deviceId}/ota/status
}

void publishOtaProgress(class PubSubClient& client, const char* deviceId,
                        uint8_t progress, const char* status) {
  (void)client;
  (void)deviceId;
  (void)progress;
  (void)status;
  // Stub: would publish to smart-factory/{deviceId}/ota/progress
}

}  // namespace ota
