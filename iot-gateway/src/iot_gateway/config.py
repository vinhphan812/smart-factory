"""Gateway configuration from environment variables."""

from dataclasses import dataclass
import os


@dataclass
class GatewayConfig:
    mqtt_broker: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    database_url: str
    ws_host: str
    ws_port: int
    ws_http_port: int
    max_events: int
    mqtt_ca_cert: str | None = None

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        ws_port = int(os.environ.get("WS_PORT", "8000"))
        return cls(
            mqtt_broker=os.environ.get("MQTT_BROKER", "localhost"),
            mqtt_port=int(os.environ.get("MQTT_PORT", "1883")),
            mqtt_username=os.environ.get("MQTT_USERNAME") or None,
            mqtt_password=os.environ.get("MQTT_PASSWORD") or None,
            database_url=os.environ.get(
                "DATABASE_URL", "sqlite+aiosqlite:///gateway.db"
            ),
            ws_host=os.environ.get("WS_HOST", "0.0.0.0"),
            ws_port=ws_port,
            ws_http_port=int(os.environ.get("WS_HTTP_PORT", str(ws_port + 1))),
            max_events=int(os.environ.get("MAX_EVENTS", "10000")),
            mqtt_ca_cert=os.environ.get("MQTT_CA_CERT") or None,
        )


DEFAULT_TOPICS = [
    "smart-factory/+/command/ack",
    "smart-factory/+/status",
    "smart-factory/+/telemetry",
    "smart-factory/+/heartbeat",
]
