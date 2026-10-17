#pragma once

#include <cstdint>
#include <cstring>

namespace ota {

/**
 * OTA state machine states per ADR-0008.
 * Each state represents a phase in the OTA update lifecycle.
 */
enum class State {
  kIdle,                 ///< No OTA in progress, ready to accept new updates
  kDownloadScheduled,    ///< OTA requested, waiting for maintenance window
  kDownloading,          ///< Actively downloading firmware from server
  kValidating,           ///< Verifying signature and SHA-256 checksum
  kStaging,              ///< Writing validated image to inactive partition
  kRebooting,            ///< Rebooting to apply new firmware
  kActive,               ///< New firmware running, monitoring for health
  kRollback,             ///< Rolling back to previous firmware
  kError                 ///< Error state, requires manual intervention
};

/**
 * Result codes for OTA operations.
 */
enum class Result {
  kOk,                  ///< Operation succeeded
  kPending,             ///< Operation in progress (non-blocking)
  kError,               ///< Generic error
  kInvalidMetadata,     ///< Firmware metadata invalid
  kSignatureInvalid,    ///< Signature verification failed
  kChecksumMismatch,    ///< SHA-256 mismatch
  kNetworkError,        ///< Network connectivity issue
  kStorageError,        ///< Flash storage error
  kMaintenanceBlocked,  ///< Maintenance mode not available
  kHealthCheckFailed,   ///< Post-boot health validation failed
  kRollbackFailed       ///< Rollback procedure failed
};

/**
 * Firmware metadata received via MQTT update announcement.
 * Per ADR-0007: includes version, SHA-256, signature, release authority.
 */
struct FirmwareMetadata {
  char version[16];           ///< Semantic version string (e.g., "1.2.3")
  uint32_t versionCode;       ///< Numeric version for comparison
  char sha256[65];            ///< SHA-256 hash as hex string (64 chars + null)
  char signature[256];        ///< RSA/ECDSA signature (hex encoded)
  char releaseAuthority[64];  ///< Identity of signing authority
  char url[256];              ///< HTTPS firmware download URL
  uint32_t size;              ///< Firmware image size in bytes
  char sku[32];               ///< Hardware SKU identifier
  uint32_t timestamp;         ///< Release timestamp (Unix epoch)
};

/**
 * Configuration for OTA operations.
 */
struct Config {
  uint32_t downloadChunkSize;      ///< Bytes per tick() chunk (default: 4096)
  uint32_t maxDownloadTimeMs;      ///< Max total download time
  uint32_t validationTimeoutMs;    ///< Max signature/checksum validation time
  uint32_t healthCheckTimeoutMs;   ///< Post-boot health check timeout
  uint32_t rollbackTimeoutMs;      ///< Rollback procedure timeout
  uint32_t maintenanceWindowMs;   ///< Min maintenance window duration
  uint16_t maxRetries;             ///< Max retry attempts for downloads
};

/**
 * Default OTA configuration.
 */
constexpr Config kDefaultConfig = {
    .downloadChunkSize = 4096,
    .maxDownloadTimeMs = 300000,        // 5 minutes
    .validationTimeoutMs = 30000,       // 30 seconds
    .healthCheckTimeoutMs = 60000,      // 60 seconds
    .rollbackTimeoutMs = 120000,        // 2 minutes
    .maintenanceWindowMs = 5000,        // 5 seconds minimum
    .maxRetries = 3
};

/**
 * Transport interface for firmware downloads.
 * Abstracts HTTP/HTTPS to allow testing with mock implementations.
 */
class Transport {
 public:
  virtual ~Transport() = default;

  /**
   * Initialize the transport (e.g., connect Wi-Fi).
   * @return true if ready for downloads
   */
  virtual bool begin() = 0;

  /**
   * Check if network is available.
   * @return true if network is connected
   */
  virtual bool isConnected() = 0;

  /**
   * Start a firmware download.
   * @param url HTTPS URL to download from
   * @param size Expected file size in bytes
   * @return true if connection established
   */
  virtual bool beginDownload(const char* url, uint32_t size) = 0;

  /**
   * Read a chunk of data from the download.
   * @param buffer Buffer to store data
   * @param size Maximum bytes to read
   * @return Actual bytes read, 0 on EOF or error
   */
  virtual uint32_t read(uint8_t* buffer, uint32_t size) = 0;

  /**
   * Get download progress.
   * @return Number of bytes downloaded so far
   */
  virtual uint32_t progress() const = 0;

  /**
   * End current download and cleanup.
   */
  virtual void end() = 0;
};

/**
 * Partition interface for A/B slot management.
 * Abstracts flash partition operations for testing.
 */
class Partition {
 public:
  virtual ~Partition() = default;

  /**
   * Get the currently running partition label.
   * @return "A" or "B"
   */
  virtual const char* getRunningPartition() const = 0;

  /**
   * Get the inactive partition (target for OTA).
   * @return "A" or "B"
   */
  virtual const char* getInactivePartition() const = 0;

  /**
   * Mark a partition as the boot candidate.
   * @param partition "A" or "B"
   * @return true on success
   */
  virtual bool setBootCandidate(const char* partition) = 0;

  /**
   * Write data to the inactive partition at offset.
   * @param offset Byte offset from partition start
   * @param data Data to write
   * @param size Bytes to write
   * @return true on success
   */
  virtual bool write(uint32_t offset, const uint8_t* data, uint32_t size) = 0;

  /**
   * Read data from a partition.
   * @param partition "A" or "B"
   * @param offset Byte offset from partition start
   * @param buffer Buffer to store data
   * @param size Bytes to read
   * @return true on success
   */
  virtual bool read(const char* partition, uint32_t offset, uint8_t* buffer,
                    uint32_t size) = 0;

  /**
   * Verify written data matches expected SHA-256.
   * @param partition "A" or "B"
   * @param expectedSha256 Expected SHA-256 as hex string
   * @return true if checksum matches
   */
  virtual bool verifyChecksum(const char* partition,
                             const char* expectedSha256) = 0;

  /**
   * Trigger a reboot to apply the new firmware.
   */
  virtual void reboot() = 0;
};

/**
 * Signature verifier interface.
 * Abstracts cryptographic verification for testing.
 */
class SignatureVerifier {
 public:
  virtual ~SignatureVerifier() = default;

  /**
   * Verify firmware signature against pinned public key.
   * @param data Firmware image data
   * @param size Data size in bytes
   * @param signature Signature to verify (hex encoded)
   * @return true if signature is valid
   */
  virtual bool verify(const uint8_t* data, uint32_t size,
                     const char* signature) = 0;
};

/**
 * Event-driven OTA manager.
 * Per ADR-0008: runs on main loop thread, tick() processes one chunk.
 * Thread-safe for concurrent calls from main loop.
 */
class OtaManager {
 public:
  /**
   * Construct OTA manager with dependencies.
   * @param transport Network transport for downloads
   * @param partition A/B partition manager
   * @param verifier Signature verification implementation
   * @param config OTA configuration (uses default if nullptr)
   */
  explicit OtaManager(Transport* transport, Partition* partition,
                      SignatureVerifier* verifier,
                      const Config* config = nullptr);

  /**
   * Check if OTA is idle and ready for new updates.
   * @return true if in kIdle state
   */
  bool isIdle() const { return state_ == State::kIdle; }

  /**
   * Check if an OTA update is in progress.
   * @return true if not in kIdle or kError state
   */
  bool isUpdating() const;

  /**
   * Get current OTA state.
   * @return Current state enum
   */
  State state() const { return state_; }

  /**
   * Get last operation result.
   * @return Last Result code
   */
  Result lastResult() const { return lastResult_; }

  /**
   * Get last error message.
   * @return Error description string
   */
  const char* errorMessage() const { return errorMessage_; }

  /**
   * Get current firmware version running.
   * @return Version string
   */
  const char* currentVersion() const { return currentVersion_; }

  /**
   * Get download progress percentage (0-100).
   * @return Progress value
   */
  uint8_t progress() const;

  /**
   * Request an OTA update with metadata from MQTT.
   * Only accepted if in kIdle state and maintenance window available.
   * @param metadata Firmware metadata from update announcement
   * @return true if update request accepted
   */
  bool requestUpdate(const FirmwareMetadata& metadata);

  /**
   * Check if maintenance mode is available (no pending commands).
   * Called by main loop to gate OTA during active operations.
   * @param pendingCommandCount Number of commands in flight
   * @return true if maintenance window is open
   */
  bool isMaintenanceWindowOpen(uint16_t pendingCommandCount) const;

  /**
   * Cancel any in-progress OTA update.
   * @return true if cancelled successfully
   */
  bool cancel();

  /**
   * Process one tick of the OTA state machine.
   * Non-blocking: processes at most one chunk per call.
   * @param nowMs Current system time in milliseconds
   * @return Current state (for logging/status)
   */
  State tick(uint32_t nowMs);

 private:
  // State handlers (each processes one step, returns true if complete)
  bool handleDownloadScheduled(uint32_t nowMs);
  bool handleDownloading(uint32_t nowMs);
  bool handleValidating(uint32_t nowMs);
  bool handleStaging(uint32_t nowMs);
  bool handleRebooting(uint32_t nowMs);
  bool handleActive(uint32_t nowMs);
  bool handleRollback(uint32_t nowMs);
  bool handleError(uint32_t nowMs);

  // Helper methods
  void transitionTo(State newState);
  void setError(Result result, const char* message);
  void reset();
  bool validateMetadata(const FirmwareMetadata& metadata) const;

  // Dependencies (owned by caller)
  Transport* const transport_;
  Partition* const partition_;
  SignatureVerifier* const verifier_;

  // Configuration
  const Config config_;

  // State machine state
  State state_;
  State previousState_;  // For rollback tracking
  Result lastResult_;
  char errorMessage_[64];

  // Current update metadata
  FirmwareMetadata pendingMetadata_;
  uint32_t downloadStartTime_;
  uint32_t stateEnterTime_;

  // Download state
  uint32_t downloadedBytes_;
  uint8_t retryCount_;
  bool downloadStarted_;

  // Health tracking
  uint32_t healthCheckStartTime_;
  uint8_t healthCheckAttempts_;

  // Current firmware version (persisted or compiled-in)
  char currentVersion_[16];
  uint32_t currentVersionCode_;
};

/**
 * Publish OTA status to MQTT.
 * Called by main loop to report OTA progress.
 */
void publishOtaStatus(class PubSubClient& client, const char* deviceId,
                      const OtaManager& ota);

/**
 * Publish OTA progress event.
 * Called during download to report progress.
 */
void publishOtaProgress(class PubSubClient& client, const char* deviceId,
                        uint8_t progress, const char* status);

}  // namespace ota
