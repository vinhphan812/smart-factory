"""Async MQTT subscriber for the gateway."""

import asyncio
import logging
from typing import Callable

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MqttSubscriber:
    """Async MQTT subscriber using paho-mqtt with threading + asyncio bridge.

    Uses the threaded interface of paho-mqtt to handle MQTT callbacks in
    a background thread, then signals the asyncio event loop via a queue.
    """

    def __init__(
        self,
        broker: str,
        port: int,
        username: str | None,
        password: str | None,
        topics: list[str],
        on_message: Callable[[str, bytes], None],
    ) -> None:
        self._broker = broker
        self._port = port
        self._username = username
        self._password = password
        self._topics = topics
        self._on_message = on_message
        self._client: mqtt.Client | None = None
        self._loop_thread: asyncio.AbstractEventLoop | None = None
        self._running = False

    def _on_mqtt_message(
        self, _client: mqtt.Client, _userdata: object, msg: mqtt.MQTTMessage
    ) -> None:
        try:
            self._on_message(msg.topic, msg.payload)
        except Exception as exc:
            logger.exception("Error in MQTT message handler: %s", exc)

    def _on_connect(
        self, _client: mqtt.Client, _userdata: object, flags: dict, rc: int
    ) -> None:
        if rc == 0:
            logger.info("Connected to MQTT broker %s:%d", self._broker, self._port)
            for topic in self._topics:
                self._client.subscribe(topic, qos=1)
                logger.info("Subscribed to: %s", topic)
        else:
            logger.error("MQTT connection failed with code %d", rc)

    def _on_disconnect(
        self, _client: mqtt.Client, _userdata: object, rc: int
    ) -> None:
        if rc != 0:
            logger.warning("Unexpected MQTT disconnect (rc=%d). Will retry.", rc)

    def start(self) -> None:
        client_id = f"iot-gateway-{id(self)}"
        self._client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        if self._username:
            self._client.username_pw_set(self._username, self._password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_mqtt_message

        self._client.connect(self._broker, self._port, keepalive=60)
        self._client.loop_start()
        self._running = True
        logger.info("MQTT subscriber started (broker=%s:%d)", self._broker, self._port)

    def stop(self) -> None:
        if self._client and self._running:
            self._client.loop_stop()
            self._client.disconnect()
            self._running = False
            logger.info("MQTT subscriber stopped")
