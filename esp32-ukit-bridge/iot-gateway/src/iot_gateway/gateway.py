"""Main gateway orchestration — wires MQTT, store, and API together."""

import asyncio
import logging
from typing import Any

from .config import DEFAULT_TOPICS, GatewayConfig
from .event_normalizer import EventNormalizer
from .event_store import EventStore
from .mqtt_client import MqttSubscriber
from .api import WebSocketServer, create_http_app

logger = logging.getLogger(__name__)


class Gateway:
    """MQTT ingestion gateway.

    Wires:
    - MqttSubscriber → EventNormalizer → write queue → EventStore (SQLite)
    - EventStore → WebSocketServer (broadcast)
    - EventStore → FastAPI HTTP (REST)

    Uses a bounded asyncio.Queue to decouple MQTT message arrival from SQLite
    writes, preventing thundering-herd lock contention when many messages arrive
    simultaneously.
    """

    # Number of concurrent SQLite write workers
    NUM_WRITERS = 2
    QUEUE_SIZE = 500

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config
        self._store = EventStore(config.database_url, config.max_events)
        self._normalizer = EventNormalizer()
        self._ws = WebSocketServer(config.ws_host, config.ws_port)
        self._app = create_http_app(self._store)
        self._mqtt: MqttSubscriber | None = None
        self._runner: Any | None = None
        self._write_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self.QUEUE_SIZE
        )
        self._shutdown_event = asyncio.Event()
        self._writers_done: list[asyncio.Task[None]] = []
        # Saved so the MQTT thread callback can schedule async work safely.
        # Set in start(); the callback always accesses it after start().
        self._loop: asyncio.AbstractEventLoop

    async def _write_worker(self, worker_id: int, stop_event: asyncio.Event) -> None:
        """Worker that drains the write queue and persists events to SQLite.

        Uses wait_for(timeouts=0.5) so stop_event is checked periodically without
        blocking the event loop when the queue is empty.
        """
        while not stop_event.is_set():
            try:
                event_dict = await asyncio.wait_for(
                    self._write_queue.get(), timeout=0.5
                )
            except asyncio.TimeoutError:
                continue
            if event_dict is None:
                self._write_queue.task_done()
                continue
            try:
                await self._store.insert_dict(event_dict)
                await self._ws.broadcast(event_dict)
            except Exception as exc:
                logger.exception("Write worker %d failed to persist event: %s", worker_id, exc)
            finally:
                self._write_queue.task_done()

        # Drain ALL remaining queue items before exiting — no early exit.
        while True:
            try:
                event_dict = self._write_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if event_dict is None:
                self._write_queue.task_done()
                continue
            try:
                await self._store.insert_dict(event_dict)
                await self._ws.broadcast(event_dict)
            except Exception as exc:
                logger.exception("Write worker %d flush error: %s", worker_id, exc)
            finally:
                self._write_queue.task_done()

    async def _on_mqtt_message(self, topic: str, payload: bytes) -> None:
        """Normalize MQTT message and enqueue for async persistence."""
        event = self._normalizer.normalize(topic, payload)
        if event is None:
            return

        event_dict = event.to_dict()
        try:
            self._write_queue.put_nowait(event_dict)
        except asyncio.QueueFull:
            logger.warning(
                "Write queue full — event dropped (type=%s device=%s)",
                event.event_type.value,
                event.device_id,
            )
        else:
            logger.debug(
                "Event queued: type=%s device=%s id=%s",
                event.event_type.value,
                event.device_id,
                event.event_id,
            )

    def _mqtt_callback(self, topic: str, payload: bytes) -> None:
        """Called from Paho's internal thread.

        Paho's MQTT loop runs on its own thread, not the asyncio event loop.
        Calling asyncio.create_task() directly here raises RuntimeError because
        there is no running event loop on that thread.

        Schedule the async handler with call_soon_threadsafe so the event loop
        processes it on its next tick. _loop is always set by start().
        """
        self._loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self._on_mqtt_message(topic, payload))
        )

    async def start(self) -> None:
        """Start all gateway components."""
        # Save event loop reference before starting any async work.
        # _mqtt_callback runs on Paho's thread, not the asyncio thread.
        self._loop = asyncio.get_running_loop()

        await self._store.init()
        logger.info("Starting IoT Gateway...")

        # Start WebSocket server first so it's ready before MQTT messages arrive
        await self._ws.start()

        # Start write workers before MQTT so they are ready
        self._stop_events = [
            asyncio.Event() for _ in range(self.NUM_WRITERS)
        ]
        self._writers_done = [
            asyncio.create_task(self._write_worker(i, stop))
            for i, stop in enumerate(self._stop_events)
        ]

        # MQTT subscriber runs in a background thread
        self._mqtt = MqttSubscriber(
            broker=self._config.mqtt_broker,
            port=self._config.mqtt_port,
            username=self._config.mqtt_username,
            password=self._config.mqtt_password,
            topics=DEFAULT_TOPICS,
            on_message=self._mqtt_callback,
        )
        self._mqtt.start()

        # WebSocket + HTTP server
        try:
            from uvicorn import Config, Server

            config = Config(
                app=self._app,
                host=self._config.ws_host,
                port=self._config.ws_port,
                log_level="warning",
            )
            self._runner = Server(config)
            await self._runner.serve()
        except ImportError:
            logger.warning("uvicorn not installed — HTTP/WebSocket server disabled")

    async def shutdown(self) -> None:
        """Graceful shutdown: stop workers, drain queue, close connections."""
        logger.info("Shutting down gateway...")
        if self._mqtt:
            self._mqtt.stop()

        # Signal all workers to stop and wait for them to flush remaining queue items
        for stop in self._stop_events:
            stop.set()
        await asyncio.gather(*self._writers_done, return_exceptions=True)

        await self._ws.shutdown()
        await self._store.close()
        self._shutdown_event.set()
