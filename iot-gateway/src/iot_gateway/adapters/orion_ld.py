"""Orion-LD NGSI-LD context adapter for the gateway.

This adapter translates gateway canonical events into NGSI-LD entities
and persists them to an Orion-LD context broker using the NGSI-LD v1.3.1 API.

Key features:
- Event to NGSI-LD entity mapping
- Reliable upsert (idempotent create-or-update)
- Batch processing for performance
- Dead-letter queue for failed entities
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import aiohttp

from ..models import CanonicalEvent, EventType

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    """NGSI-LD entity types for Smart Factory devices."""

    DEVICE = "Device"
    CONVEYOR = "Conveyor"
    SENSOR = "Sensor"
    COMMAND = "Command"
    TELEMETRY = "Telemetry"
    STATUS = "Status"


@dataclass
class OrionLdConfig:
    """Configuration for Orion-LD connection."""

    base_url: str = "http://localhost:1026"
    context: str = "https://schema.lab.fiware.org/ns/unknown"
    batch_size: int = 100
    batch_timeout_seconds: float = 5.0
    dead_letter_path: str = "/tmp/orion-ld-dead-letter"
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0

    @classmethod
    def from_env(cls) -> "OrionLdConfig":
        return cls(
            base_url=os.environ.get("ORION_LD_URL", "http://localhost:1026"),
            context=os.environ.get(
                "ORION_LD_CONTEXT",
                "https://schema.lab.fiware.org/ns/unknown",
            ),
            batch_size=int(os.environ.get("ORION_LD_BATCH_SIZE", "100")),
            batch_timeout_seconds=float(
                os.environ.get("ORION_LD_BATCH_TIMEOUT", "5.0")
            ),
            dead_letter_path=os.environ.get(
                "ORION_LD_DEAD_LETTER_PATH", "/tmp/orion-ld-dead-letter"
            ),
            retry_attempts=int(os.environ.get("ORION_LD_RETRY_ATTEMPTS", "3")),
            retry_delay_seconds=float(
                os.environ.get("ORION_LD_RETRY_DELAY", "1.0")
            ),
        )


@dataclass
class DeadLetterEntry:
    """Entry for the dead-letter queue."""

    event: CanonicalEvent
    ngsi_ld_entity: dict[str, Any]
    error: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    attempts: int = 1

    def to_dict(self) -> dict:
        return {
            "event": self.event.to_dict(),
            "ngsi_ld_entity": self.ngsi_ld_entity,
            "error": self.error,
            "timestamp": self.timestamp,
            "attempts": self.attempts,
        }


class OrionLdClient:
    """NGSI-LD v1.3.1 API client for Orion-LD."""

    def __init__(self, config: OrionLdConfig) -> None:
        self._config = config
        self._session: aiohttp.ClientSession | None = None
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Link": f'<{config.context}>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"',
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def upsert_batch(
        self, entities: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Upsert a batch of entities using NGSI-LD upsert API.

        Returns:
            Tuple of (successful_entities, failed_entities)
        """
        if not entities:
            return [], []

        url = f"{self._config.base_url}/ngsi-ld/v1/entityOperations/upsert"
        payload = {"entities": entities}

        session = await self._get_session()
        try:
            async with session.post(url, json=payload) as response:
                if response.status in (200, 201):
                    logger.debug(
                        f"Successfully upserted {len(entities)} entities"
                    )
                    return entities, []
                elif response.status == 207:
                    # Partial success - parse response to identify failures
                    result = await response.json()
                    return self._parse_partial_success(entities, result)
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Orion-LD upsert failed: {response.status} - {error_text}"
                    )
                    # All entities failed
                    return [], entities
        except aiohttp.ClientError as e:
            logger.error(f"Orion-LD connection error: {e}")
            return [], entities

    def _parse_partial_success(
        self,
        entities: list[dict[str, Any]],
        result: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Parse partial success response from Orion-LD."""
        successful = []
        failed = []

        # The response format is typically:
        # {"entities": [{"id": "...", "error": {...}}]}
        result_entities = result.get("entities", [])

        # Create a lookup for success/failure
        success_ids = set()
        failed_by_id = {}

        for res_entity in result_entities:
            entity_id = res_entity.get("id")
            if "error" in res_entity:
                failed_by_id[entity_id] = res_entity
            else:
                success_ids.add(entity_id)

        # Categorize input entities
        for entity in entities:
            entity_id = entity.get("id")
            if entity_id in success_ids:
                successful.append(entity)
            else:
                failed.append(entity)

        return successful, failed


class EventToEntityMapper:
    """Maps gateway canonical events to NGSI-LD entities."""

    # Map event types to NGSI-LD entity types
    EVENT_TYPE_TO_ENTITY_TYPE: dict[EventType, EntityType] = {
        EventType.COMMAND_ACK: EntityType.COMMAND,
        EventType.STATUS_ONLINE: EntityType.STATUS,
        EventType.STATUS_OFFLINE: EntityType.STATUS,
        EventType.TELEMETRY: EntityType.TELEMETRY,
        EventType.HEARTBEAT: EntityType.DEVICE,
    }

    def map_event(self, event: CanonicalEvent) -> dict[str, Any] | None:
        """Map a canonical event to an NGSI-LD entity.

        Returns None if the event cannot be mapped.
        """
        entity_type = self.EVENT_TYPE_TO_ENTITY_TYPE.get(event.event_type)
        if entity_type is None:
            logger.warning(
                f"Unknown event type: {event.event_type}, skipping"
            )
            return None

        entity_id = self._build_entity_id(event)
        if entity_id is None:
            logger.warning(f"Cannot build entity ID for event: {event.event_id}")
            return None

        entity = {
            "id": entity_id,
            "type": entity_type.value,
            "dateModified": {
                "@type": "DateTime",
                "@value": event.received_at or datetime.now(timezone.utc).isoformat(),
            },
        }

        # Add event-specific attributes
        self._add_attributes(entity, event)

        return entity

    def _build_entity_id(self, event: CanonicalEvent) -> str | None:
        """Build the NGSI-LD entity ID from the event."""
        if not event.device_id:
            return None

        # Entity IDs follow the pattern: urn:ngsi-ld:<type>:<device-id>
        entity_type = self.EVENT_TYPE_TO_ENTITY_TYPE.get(event.event_type)
        if entity_type is None:
            return None

        # Use a sanitized device_id (replace special chars)
        sanitized_id = event.device_id.replace("/", "-").replace(":", "-")
        return f"urn:ngsi-ld:{entity_type.value}:{sanitized_id}"

    def _add_attributes(
        self, entity: dict[str, Any], event: CanonicalEvent
    ) -> None:
        """Add event-specific attributes to the entity."""
        # Add core attributes
        entity["deviceId"] = {
            "type": "Property",
            "value": event.device_id,
        }

        entity["eventId"] = {
            "type": "Property",
            "value": str(event.event_id),
        }

        # Add timestamp
        timestamp = event.event_timestamp_ms or event.mqtt_timestamp_ms
        if timestamp:
            # Convert epoch ms to ISO datetime
            try:
                dt = datetime.fromtimestamp(
                    timestamp / 1000, tz=timezone.utc
                ).isoformat()
            except (ValueError, OSError):
                dt = datetime.now(timezone.utc).isoformat()
            entity["timestamp"] = {
                "type": "Property",
                "value": {"@type": "DateTime", "@value": dt},
            }

        # Add event-type-specific attributes
        if event.event_type == EventType.COMMAND_ACK:
            self._add_command_attributes(entity, event)
        elif event.event_type in (EventType.STATUS_ONLINE, EventType.STATUS_OFFLINE):
            self._add_status_attributes(entity, event)
        elif event.event_type == EventType.TELEMETRY:
            self._add_telemetry_attributes(entity, event)
        elif event.event_type == EventType.HEARTBEAT:
            self._add_heartbeat_attributes(entity, event)

    def _add_command_attributes(
        self, entity: dict[str, Any], event: CanonicalEvent
    ) -> None:
        """Add command-specific attributes."""
        payload = event.payload or {}

        entity["commandId"] = {
            "type": "Property",
            "value": payload.get("id", ""),
        }

        entity["status"] = {
            "type": "Property",
            "value": payload.get("status", ""),
        }

        if "attempts" in payload:
            entity["attempts"] = {
                "type": "Property",
                "value": payload["attempts"],
            }

    def _add_status_attributes(
        self, entity: dict[str, Any], event: CanonicalEvent
    ) -> None:
        """Add status-specific attributes."""
        payload = event.payload or {}

        entity["status"] = {
            "type": "Property",
            "value": "online"
            if event.event_type == EventType.STATUS_ONLINE
            else "offline",
        }

        if "reason" in payload:
            entity["reason"] = {
                "type": "Property",
                "value": payload["reason"],
            }

    def _add_telemetry_attributes(
        self, entity: dict[str, Any], event: CanonicalEvent
    ) -> None:
        """Add telemetry-specific attributes."""
        payload = event.payload or {}

        # Map known telemetry fields
        if "state" in payload:
            entity["state"] = {
                "type": "Property",
                "value": payload["state"],
            }

        if "speed" in payload:
            entity["speed"] = {
                "type": "Property",
                "value": payload["speed"],
            }

        if "sensors" in payload:
            sensors = payload["sensors"]
            if "temperature_centi_c" in sensors:
                entity["temperature"] = {
                    "type": "Property",
                    "value": sensors["temperature_centi_c"] / 100,
                }
            if "humidity_centi_percent" in sensors:
                entity["humidity"] = {
                    "type": "Property",
                    "value": sensors["humidity_centi_percent"] / 100,
                }

        if "uptime" in payload:
            entity["uptime"] = {
                "type": "Property",
                "value": payload["uptime"],
            }

    def _add_heartbeat_attributes(
        self, entity: dict[str, Any], event: CanonicalEvent
    ) -> None:
        """Add heartbeat-specific attributes."""
        payload = event.payload or {}

        entity["lastSeen"] = {
            "type": "Property",
            "value": {
                "@type": "DateTime",
                "@value": event.received_at
                or datetime.now(timezone.utc).isoformat(),
            },
        }

        if "version" in payload:
            entity["firmwareVersion"] = {
                "type": "Property",
                "value": payload["version"],
            }


class DeadLetterQueue:
    """Dead-letter queue for failed entity upserts."""

    def __init__(self, config: OrionLdConfig) -> None:
        self._config = config
        self._queue: asyncio.Queue[DeadLetterEntry] = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def add(
        self,
        event: CanonicalEvent,
        ngsi_ld_entity: dict[str, Any],
        error: str,
    ) -> None:
        """Add a failed entity to the dead-letter queue."""
        entry = DeadLetterEntry(
            event=event, ngsi_ld_entity=ngsi_ld_entity, error=error
        )
        await self._queue.put(entry)
        logger.warning(f"Added to dead-letter queue: {error}")

    async def retry_batch(
        self, client: OrionLdClient, max_attempts: int = 3
    ) -> tuple[int, int]:
        """Retry all entries in the dead-letter queue.

        Returns:
            Tuple of (successful_count, failed_count)
        """
        entries = []
        while not self._queue.empty():
            try:
                entry = self._queue.get_nowait()
                entries.append(entry)
            except asyncio.QueueEmpty:
                break

        if not entries:
            return 0, 0

        successful = 0
        failed = 0

        for entry in entries:
            if entry.attempts >= max_attempts:
                logger.error(
                    f"Max retry attempts reached for entity: {entry.ngsi_ld_entity.get('id')}"
                )
                failed += 1
                continue

            # Retry the upsert
            entry.attempts += 1
            try:
                _, failed_entities = await client.upsert_batch(
                    [entry.ngsi_ld_entity]
                )
                if not failed_entities:
                    successful += 1
                    logger.info(
                        f"Successfully retried entity: {entry.ngsi_ld_entity.get('id')}"
                    )
                else:
                    # Re-queue for another retry
                    await self._queue.put(entry)
            except Exception as e:
                logger.exception(f"Error retrying entity: {e}")
                await self._queue.put(entry)

        return successful, failed

    def size(self) -> int:
        """Return the current size of the dead-letter queue."""
        return self._queue.qsize()


class OrionLdAdapter:
    """Main adapter for publishing gateway events to Orion-LD.

    This adapter:
    1. Maps canonical events to NGSI-LD entities
    2. Batches entities for efficient upsert
    3. Handles errors with dead-letter queue
    """

    def __init__(self, config: OrionLdConfig | None = None) -> None:
        self._config = config or OrionLdConfig.from_env()
        self._client = OrionLdClient(self._config)
        self._mapper = EventToEntityMapper()
        self._dlq = DeadLetterQueue(self._config)
        self._batch: list[tuple[CanonicalEvent, dict[str, Any]]] = []
        self._batch_lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the adapter."""
        self._running = True
        # Start the periodic flush task
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("Orion-LD adapter started")

    async def stop(self) -> None:
        """Stop the adapter and flush remaining batch."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        # Final flush
        await self._flush_batch()
        await self._client.close()
        logger.info("Orion-LD adapter stopped")

    async def publish_event(self, event: CanonicalEvent) -> None:
        """Publish a canonical event to Orion-LD (batched)."""
        # Map event to NGSI-LD entity
        entity = self._mapper.map_event(event)
        if entity is None:
            logger.debug(f"Skipping event with no entity mapping: {event.event_id}")
            return

        # Add to batch
        async with self._batch_lock:
            self._batch.append((event, entity))
            if len(self._batch) >= self._config.batch_size:
                await self._flush_batch()

    async def _periodic_flush(self) -> None:
        """Periodically flush the batch."""
        while self._running:
            try:
                await asyncio.sleep(self._config.batch_timeout_seconds)
                async with self._batch_lock:
                    if self._batch:
                        await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in periodic flush: {e}")

    async def _flush_batch(self) -> None:
        """Flush the current batch to Orion-LD."""
        if not self._batch:
            return

        batch_to_flush = self._batch
        self._batch = []

        entities = [entity for _, entity in batch_to_flush]

        # Retry logic for batch upsert
        for attempt in range(self._config.retry_attempts):
            successful, failed = await self._client.upsert_batch(entities)

            if not failed:
                logger.info(f"Successfully upserted {len(successful)} entities")
                return

            # Handle failures - add to dead-letter queue
            logger.warning(
                f"Batch upsert had {len(failed)} failures (attempt {attempt + 1})"
            )

            # Identify which events failed
            failed_ids = {e.get("id") for e in failed}
            for event, entity in batch_to_flush:
                if entity.get("id") in failed_ids:
                    await self._dlq.add(
                        event,
                        entity,
                        f"Upsert failed after {attempt + 1} attempts",
                    )

            # Update entities for retry (only failed ones)
            entities = failed

            if attempt < self._config.retry_attempts - 1:
                await asyncio.sleep(self._config.retry_delay_seconds)

    async def retry_dead_letter(self) -> tuple[int, int]:
        """Retry entries in the dead-letter queue.

        Returns:
            Tuple of (successful_count, failed_count)
        """
        return await self._dlq.retry_batch(self._client, self._config.retry_attempts)

    def dead_letter_size(self) -> int:
        """Return the current dead-letter queue size."""
        return self._dlq.size()
