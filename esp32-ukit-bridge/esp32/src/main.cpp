#include <Arduino.h>
#include <PubSubClient.h>
#include <WiFi.h>

#include <cstdio>

#include "bridge_core.h"
#include "mqtt_bridge.h"
#include "uart_adapter.h"
#include "wifi_state_machine.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

namespace {

bridge::BridgeCore bridgeCore({1000, 3});
HardwareSerial deviceSerial(1);
UartAdapter uart(deviceSerial);
WifiStateMachine wifi(BRIDGE_WIFI_SSID, BRIDGE_WIFI_PASSWORD);
WiFiClient networkClient;
PubSubClient mqttClient(networkClient);
char mqttClientId[32]{};
MqttBridge* mqttBridge = nullptr;

void makeClientId() {
  const uint64_t chipId = ESP.getEfuseMac();
  std::snprintf(mqttClientId, sizeof(mqttClientId), "ukit-%08lx",
                static_cast<unsigned long>(chipId & 0xFFFFFFFFULL));
}

}  // namespace

void setup() {
  Serial.begin(115200);
  uart.begin();
  makeClientId();

  static MqttBridge mqtt(mqttClient, bridgeCore, BRIDGE_MQTT_HOST,
                         BRIDGE_MQTT_PORT, BRIDGE_MQTT_USERNAME,
                         BRIDGE_MQTT_PASSWORD, mqttClientId);
  mqttBridge = &mqtt;

  // Register MQTT bridge as the telemetry consumer so that AMLP TEL frames
  // received from MEGA are published to the MQTT telemetry topic.
  uart.setTelemetryHandler(mqttBridge);

  const uint32_t now = millis();
  wifi.begin(now);
  mqttBridge->begin();
}

void loop() {
  const uint32_t now = millis();
  wifi.tick(now);
  uart.poll(now, bridgeCore);
  bridgeCore.tick(now, uart);
  mqttBridge->tick(now, wifi.connected());
  yield();
}
