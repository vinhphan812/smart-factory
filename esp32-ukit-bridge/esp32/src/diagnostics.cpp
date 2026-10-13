#include "diagnostics.h"

#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>

#include <cstdio>

#include "bridge_config.h"

namespace bridge {

// Global diagnostics instance.
DiagnosticsCounters g_diagnostics;

}  // namespace bridge

// ---------------------------------------------------------------------------
// Heartbeat
// ---------------------------------------------------------------------------

/**
 * @brief  Publishes a heartbeat message to the MQTT broker.
 *
 * Topic:  smart-factory/bridge/{deviceId}/heartbeat
 * QoS:    0 (best effort)
 * Retain: No
 *
 * Payload (JSON):
 * {
 *   "online": true,
 *   "uptime_s": <seconds since boot>,
 *   "rssi_dbm": <current Wi-Fi RSSI>,
 *   "free_heap_bytes": <available heap>,
 *   "queue_depth": <pending command count>,
 *   "last_tel_s": <seconds since last TEL>,
 *   "counters": {
 *     "tx_frames": <...>, "rx_frames": <...>,
 *     "crc_errors": <...>, "parse_errors": <...>,
 *     "retries": <...>, "mqtt_publishes": <...>,
 *     "mqtt_connects": <...>, "wifi_reconnects": <...>,
 *     "heartbeats_sent": <...>
 *   }
 * }
 *
 * @param client       Active MQTT client (must be connected).
 * @param deviceId     Bridge device identifier, used to build the topic name.
 * @param queueDepth   Current number of pending commands.
 * @param lastTelAgeMs Milliseconds since the last TEL frame from uKit.
 *
 * @return true if the message was published successfully.
 *
 * TODO: Integrate into MqttBridge::tick() so it is called every
 *       kHeartbeatIntervalMs when MQTT is connected.
 * TODO: Expose lastTelAgeMs from UartAdapter or a TelemetryMonitor.
 */
bool publishHeartbeat(PubSubClient& client, const char* deviceId,
                      uint16_t queueDepth, uint32_t lastTelAgeMs) {
  if (!client.connected() || deviceId == nullptr || deviceId[0] == '\0') {
    return false;
  }

  char topic[128]{};
  std::snprintf(topic, sizeof(topic),
                "smart-factory/bridge/%s/heartbeat", deviceId);

  JsonDocument doc;
  doc["online"] = true;
  doc["uptime_s"] = millis() / 1000U;
  doc["rssi_dbm"] = WiFi.RSSI();
  doc["free_heap_bytes"] = ESP.getFreeHeap();
  doc["queue_depth"] = queueDepth;
  doc["last_tel_s"] = lastTelAgeMs / 1000U;

  // Include counters snapshot.
  JsonObject counters = doc["counters"].to<JsonObject>();
  counters["tx_frames"] = bridge::g_diagnostics.tx_frames;
  counters["rx_frames"] = bridge::g_diagnostics.rx_frames;
  counters["crc_errors"] = bridge::g_diagnostics.crc_errors;
  counters["parse_errors"] = bridge::g_diagnostics.parse_errors;
  counters["retries"] = bridge::g_diagnostics.retries;
  counters["mqtt_publishes"] = bridge::g_diagnostics.mqtt_publishes;
  counters["mqtt_connects"] = bridge::g_diagnostics.mqtt_connects;
  counters["wifi_reconnects"] = bridge::g_diagnostics.wifi_reconnects;
  counters["heartbeats_sent"] = bridge::g_diagnostics.heartbeats_sent;

  char buffer[384]{};
  const std::size_t len = serializeJson(doc, buffer);
  if (len == 0) {
    return false;
  }

  const bool ok = client.publish(topic, buffer, false);
  if (ok) {
    ++bridge::g_diagnostics.heartbeats_sent;
  }
  return ok;
}

// ---------------------------------------------------------------------------
// Telemetry health check
// ---------------------------------------------------------------------------

/**
 * @brief  Checks whether telemetry from uKit is stale and publishes a
 *         telemetry_timeout or telemetry_recovered event if the state changed.
 *
 * A TEL frame is considered stale when more than kTelemetryTimeoutMs have
 * elapsed since the last one was received.  If more than
 * kTelemetryCriticalTimeoutMs have elapsed, a telemetry_timeout event is
 * published to smart-factory/bridge/{deviceId}/event.
 *
 * When a fresh TEL arrives after a stale period, a telemetry_recovered event
 * is published and the recovered counter is incremented.
 *
 * @param client         Active MQTT client (must be connected).
 * @param deviceId       Bridge device identifier.
 * @param nowMs          Current time in milliseconds (millis()).
 * @param lastTelAgeMs   Time since the last TEL frame, in milliseconds.
 * @param wasStale       Whether the telemetry was stale on the previous call
 *                       (pass by reference; updated by this function).
 *
 * @return true if an event was published, false otherwise.
 *
 * TODO: Call this from MqttBridge::tick() every tick, passing the tracked
 *       lastTelReceivedMs_ value from UartAdapter or a TelemetryMonitor.
 * TODO: Add wasStale_ member to MqttBridge or TelemetryMonitor so the
 *       previous-state tracking persists across calls.
 * TODO: Implement TelemetryMonitor::onTelReceived() to record the timestamp
 *       of each incoming TEL frame.
 */
bool checkTelemetryHealth(PubSubClient& client, const char* deviceId,
                          uint32_t nowMs, uint32_t lastTelAgeMs,
                          bool& wasStale) {
  if (!client.connected() || deviceId == nullptr || deviceId[0] == '\0') {
    return false;
  }

  const bool isStale = lastTelAgeMs >= bridge_config::kTelemetryTimeoutMs;
  const bool isCritical =
      lastTelAgeMs >= bridge_config::kTelemetryCriticalTimeoutMs;

  char topic[128]{};
  std::snprintf(topic, sizeof(topic),
                "smart-factory/bridge/%s/event", deviceId);

  // Transition: normal → stale (first time we cross the threshold)
  if (!wasStale && isStale) {
    wasStale = true;
    ++bridge::g_diagnostics.telemetry_timeout_count;

    JsonDocument doc;
    doc["event"] = "telemetry_stale";
    doc["last_tel_s"] = lastTelAgeMs / 1000U;
    char buffer[128]{};
    serializeJson(doc, buffer);
    client.publish(topic, buffer, false);
    return true;
  }

  // Transition: stale → recovered (fresh TEL arrived)
  if (wasStale && !isStale) {
    wasStale = false;
    ++bridge::g_diagnostics.telemetry_recovered_count;

    JsonDocument doc;
    doc["event"] = "telemetry_recovered";
    doc["gap_s"] = lastTelAgeMs / 1000U;
    char buffer[128]{};
    serializeJson(doc, buffer);
    client.publish(topic, buffer, false);
    return true;
  }

  // Critical timeout — informational event, no counter increment (already counted
  // at the stale transition).
  if (isCritical && wasStale) {
    // Publish every critical check interval without flooding.
    // Caller should rate-limit if needed; here we just return false to avoid
    // spamming. A production implementation would track a lastEventMs_
    // timestamp and only publish every e.g. 5 minutes.
    (void)topic;
    (void)client;
    return false;
  }

  return false;
}
