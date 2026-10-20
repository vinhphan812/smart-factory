"""Mock MQTT publisher — simulates 3 virtual Smart Factory devices.

Publishes telemetry, status (online), command/ack, and heartbeat events
on the canonical topic tree every N seconds (default 2 s).

Usage (standalone, outside Docker):
    python mock_mqtt_publisher.py --broker localhost --port 1883

Environment variables (Docker):
    MQTT_BROKER           (default: localhost)
    MQTT_PORT              (default: 1883)
    MQTT_USERNAME          (default: None)
    MQTT_PASSWORD          (default: None)
    PUBLISH_INTERVAL_S    (default: 2)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mock-publisher")


# ── Devices ──────────────────────────────────────────────────────────────────

DEVICES = [
    {
        "device_id": "mock-conveyor-a",
        "type": "conveyor",
        "module_index": 0,
        "telemetry": {"speed_rpm": 120, "load_kg": 2.5, "running": True},
    },
    {
        "device_id": "mock-robot-arm-b",
        "type": "robot_arm",
        "module_index": 2,
        "telemetry": {"angle_deg": 45.0, "torque_nm": 1.2, "gripper_open": True},
    },
    {
        "device_id": "mock-inspection-c",
        "type": "inspection",
        "module_index": 4,
        "telemetry": {"pass_count": 0, "fail_count": 0, "throughput_pph": 300},
    },
]


# ── Payload builders ─────────────────────────────────────────────────────────

def build_telemetry(device: dict[str, Any]) -> dict[str, Any]:
    return {
        "device_id": device["device_id"],
        "device_type": device["type"],
        "module_index": device["module_index"],
        "telemetry": {**device["telemetry"], "timestamp": datetime.now(timezone.utc).isoformat()},
    }


def build_status(device: dict[str, Any], online: bool = True) -> dict[str, Any]:
    return {
        "device_id": device["device_id"],
        "online": online,
        "ts": int(time.time() * 1000),
    }


def build_heartbeat(device: dict[str, Any]) -> dict[str, Any]:
    return {
        "device_id": device["device_id"],
        "uptime_ms": int(time.time() * 1000),
        "firmware_version": "mock-v1.0.0",
    }


def build_command_ack(device: dict[str, Any]) -> dict[str, Any]:
    return {
        "device_id": device["device_id"],
        "command_id": str(uuid.uuid4()),
        "status": "completed",
        "result": "ok",
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Publisher ─────────────────────────────────────────────────────────────────

class MockPublisher:
    def __init__(
        self,
        broker: str,
        port: int,
        username: str | None,
        password: str | None,
        interval: float,
    ):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.interval = interval
        self._client: mqtt.Client | None = None
        self._seq = 0

    def _on_connect(self, client: mqtt.Client, userdata: object, flags: dict, rc: int) -> None:
        if rc == 0:
            log.info("Connected to MQTT broker at %s:%d", self.broker, self.port)
        else:
            log.error("Connection failed (rc=%d) — check broker and credentials", rc)
            sys.exit(1)

    def _on_disconnect(self, client: mqtt.Client, userdata: object, rc: int) -> None:
        log.warning("Disconnected (rc=%d) — reconnecting in 5 s", rc)
        time.sleep(5)
        try:
            client.reconnect()
        except Exception as exc:
            log.error("Reconnect failed: %s", exc)

    def connect(self) -> None:
        client_id = f"mock-publisher-{uuid.uuid4().hex[:8]}"
        self._client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        if self.username and self.password:
            self._client.username_pw_set(self.username, self.password)

        self._client.connect(self.broker, self.port, keepalive=60)
        self._client.loop_start()

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self._client is None:
            return
        msg = json.dumps(payload)
        result = self._client.publish(topic, msg, qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            log.warning("Publish to %s failed: %s", topic, result)

    def _tick(self) -> None:
        self._seq += 1
        now = datetime.now(timezone.utc).isoformat()

        for device in DEVICES:
            did = device["device_id"]

            # 1. Telemetry
            telemetry = build_telemetry(device)
            telemetry["_seq"] = self._seq
            self._publish(f"smart-factory/{did}/telemetry", telemetry)

            # 2. Status (online)
            status = build_status(device, online=True)
            self._publish(f"smart-factory/{did}/status", status)

            # 3. Heartbeat (every 3rd tick)
            if self._seq % 3 == 0:
                self._publish(f"smart-factory/{did}/heartbeat", build_heartbeat(device))

            # 4. Command ACK (mock-inspection-c only, every 5th tick)
            if did == "mock-inspection-c" and self._seq % 5 == 0:
                ack = build_command_ack(device)
                ack["_seq"] = self._seq
                self._publish(f"smart-factory/{did}/command/ack", ack)

        log.info(
            "Tick %d — published %d telemetry + %d status events",
            self._seq,
            len(DEVICES),
            len(DEVICES),
        )

    def run(self) -> None:
        log.info(
            "Starting mock publisher — broker=%s:%s interval=%.1fs",
            self.broker, self.port, self.interval,
        )
        self.connect()

        # Publish immediately, then every interval seconds
        self._tick()
        while True:
            time.sleep(self.interval)
            self._tick()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Mock MQTT device publisher for E2E simulation.")
    parser.add_argument("--broker", default=os.environ.get("MQTT_BROKER", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.environ.get("MQTT_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("MQTT_PASSWORD"))
    parser.add_argument(
        "--interval", type=float,
        default=float(os.environ.get("PUBLISH_INTERVAL_S", "2")),
    )
    args = parser.parse_args()

    publisher = MockPublisher(
        broker=args.broker,
        port=args.port,
        username=args.username or None,
        password=args.password or None,
        interval=args.interval,
    )
    publisher.run()


if __name__ == "__main__":
    main()
