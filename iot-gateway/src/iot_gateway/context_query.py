"""Read-only query facade over the Orion-LD context broker (Issue #204).

This facade is the *only* FIWARE access path exposed to non-Gateway
consumers (Unity, React dashboard, Yanshee response policy, research
reports).

Design constraints (ADR-0014, Issue #204 SPEC-3):

- **Read-only by construction.** The facade performs HTTP ``GET`` requests
  only. It has no upsert, no delete, no entity mutation and no command
  forwarding. There is deliberately no write method to misuse.
- **No authorization semantics.** Reading context never authorizes a physical
  action. Robot skills are launched only by the Gateway-approved incident
  outbox (``iot_gateway.alert_outbox``).
- **No command path.** The facade never talks to MQTT and never reaches the
  bridge.

Evidence level: L1 (unit, mocked HTTP). L2 when run against the local
Orion-LD container.
"""

from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)

#: Entity type used for the projected incident alerts.
ALERT_ENTITY_TYPE = "Alert"

#: Entity type used for the robot capability entities.
ROBOT_ENTITY_TYPE = "Robot"

#: Hosts that are considered local and therefore exempt from the credential
#: requirement. A non-loopback host must present a bearer token.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


class ContextTransport(Protocol):
    """Minimal HTTP GET transport used by the facade.

    Kept as a protocol so the facade can be exercised without a live broker
    and so the read-only guarantee is auditable in one place.
    """

    async def get_json(
        self, url: str, headers: dict[str, str] | None = None
    ) -> Any:
        """Perform an HTTP GET and return the decoded JSON body."""
        ...


@dataclass
class ContextQueryConfig:
    """Configuration for the read-only context facade.

    Deployment safety (ADR-0017):

    - ``token`` is an optional bearer token for a credentialed Orion-LD
      deployment, read from ``ORION_LD_TOKEN``. It authorises **reads only**;
      the facade has no write method and never dispatches a skill.
    - ``require_tls`` (from ``ORION_LD_REQUIRE_TLS``) makes TLS mandatory.
    - ``ca_bundle`` (from ``ORION_LD_CA_BUNDLE``) is the CA bundle used to
      verify the broker certificate.

    A configuration that requires TLS without a CA bundle, or that addresses a
    non-loopback host without a token, is rejected when the configuration is
    built from the environment, rather than silently downgraded to an
    unauthenticated plaintext request.
    """

    base_url: str = "http://localhost:1026"
    context_url: str = "http://localhost:3000/contexts/smart-factory-context.jsonld"
    timeout_seconds: float = 5.0
    token: str | None = None
    require_tls: bool = False
    ca_bundle: str | None = None

    @classmethod
    def from_env(cls) -> "ContextQueryConfig":
        """Build configuration from environment variables.

        Raises:
            ValueError: if the resulting configuration is insecure (TLS
                required without a CA bundle, or a non-loopback host without
                a token).
        """
        import os

        config = cls(
            base_url=os.environ.get("ORION_LD_URL", "http://localhost:1026"),
            context_url=os.environ.get(
                "ORION_LD_CONTEXT",
                "http://localhost:3000/contexts/smart-factory-context.jsonld",
            ),
            timeout_seconds=float(
                os.environ.get("ORION_LD_CONTEXT_TIMEOUT", "5.0")
            ),
            token=os.environ.get("ORION_LD_TOKEN") or None,
            require_tls=os.environ.get("ORION_LD_REQUIRE_TLS", "").strip()
            in {"1", "true", "True", "yes"},
            ca_bundle=os.environ.get("ORION_LD_CA_BUNDLE") or None,
        )
        config.assert_deployment_safe()
        return config

    def assert_deployment_safe(self) -> None:
        """Reject a configuration that would expose the read path.

        Raises:
            ValueError: when TLS is required without a CA bundle, or when a
                non-loopback host is addressed without a bearer token.
        """
        if self.require_tls and not self.ca_bundle:
            raise ValueError(
                "ORION_LD_REQUIRE_TLS is set but ORION_LD_CA_BUNDLE is not; "
                "refusing to fall back to an unverified TLS connection."
            )
        host = urlparse(self.base_url).hostname or ""
        if host not in LOOPBACK_HOSTS and not self.token:
            raise ValueError(
                f"ORION_LD_URL host {host!r} is not loopback and ORION_LD_TOKEN "
                "is not set; refusing an unauthenticated read request."
            )


@dataclass
class ContextEntity:
    """A single NGSI-LD entity as read back from the broker.

    Attributes:
        entity_id: Entity id, e.g. ``urn:ngsi-ld:Alert:INC-001``.
        entity_type: NGSI-LD entity type.
        attributes: Raw attribute map as returned by the broker.
        observed_at: Timestamp of the most recent attribute change, if the
            broker reported one.
    """

    entity_id: str
    entity_type: str
    attributes: dict[str, Any] = field(default_factory=dict)
    observed_at: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ContextEntity":
        """Build an entity from an Orion-LD JSON payload."""
        attributes = {
            key: value
            for key, value in payload.items()
            if key not in ("id", "type", "@context", "dateCreated", "dateModified")
        }
        observed_at = None
        date_modified = payload.get("dateModified")
        if isinstance(date_modified, dict):
            observed_at = date_modified.get("value")
        elif isinstance(date_modified, str):
            observed_at = date_modified
        return cls(
            entity_id=str(payload.get("id") or ""),
            entity_type=str(payload.get("type") or ""),
            attributes=attributes,
            observed_at=observed_at,
        )

    def property(self, name: str) -> Any:
        """Return the ``value`` of a Property attribute, or ``None``."""
        attr = self.attributes.get(name)
        if isinstance(attr, dict):
            return attr.get("value")
        return attr

    def relationship(self, name: str) -> str | None:
        """Return the ``object`` of a Relationship attribute, or ``None``."""
        attr = self.attributes.get(name)
        if isinstance(attr, dict):
            obj = attr.get("object")
            return str(obj) if obj is not None else None
        return None


class AiohttpContextTransport:
    """HTTP transport that performs ``GET`` requests only."""

    def __init__(self, config: ContextQueryConfig) -> None:
        self._config = config
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return (and lazily create) the HTTP session."""
        if self._session is None or self._session.closed:
            headers = {
                "Accept": "application/json",
                "Link": (
                    f'<{self._config.context_url}>; '
                    'rel="http://www.w3.org/ns/json-ld#context"; '
                    'type="application/ld+json"'
                ),
            }
            if self._config.token:
                headers["Authorization"] = f"Bearer {self._config.token}"
            ssl_context: ssl.SSLContext | None = None
            if self._config.require_tls:
                ssl_context = ssl.create_default_context(
                    cafile=self._config.ca_bundle
                )
            self._session = aiohttp.ClientSession(
                headers=headers, ssl=ssl_context
            )
        return self._session

    async def get_json(
        self, url: str, headers: dict[str, str] | None = None
    ) -> Any:
        """Perform an HTTP GET and return the decoded JSON body."""
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=self._config.timeout_seconds)
        async with session.get(url, headers=headers, timeout=timeout) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


class ContextQueryFacade:
    """Read-only facade over the Orion-LD NGSI-LD API.

    The facade exposes queries only. There is intentionally no method that
    mutates context, and no method that forwards a command. Consumers that
    want to change physical state must go through the Gateway command path.
    """

    def __init__(
        self,
        config: ContextQueryConfig | None = None,
        transport: ContextTransport | None = None,
    ) -> None:
        self._config = config or ContextQueryConfig()
        self._transport = transport or AiohttpContextTransport(self._config)

    @property
    def config(self) -> ContextQueryConfig:
        """Return the facade configuration."""
        return self._config

    async def get_entity(self, entity_id: str) -> ContextEntity | None:
        """Read a single entity by id.

        Returns ``None`` when the entity does not exist.
        """
        url = (
            f"{self._config.base_url}/ngsi-ld/v1/entities/"
            f"{_quote_entity_id(entity_id)}"
        )
        try:
            payload = await self._transport.get_json(url)
        except Exception as exc:  # noqa: BLE001 - surfaced as absence of data
            logger.warning("Context query failed for %s: %s", entity_id, exc)
            return None
        if not isinstance(payload, dict):
            return None
        return ContextEntity.from_payload(payload)

    async def query_entities(
        self,
        entity_type: str,
        limit: int = 100,
    ) -> list[ContextEntity]:
        """Read entities of a given type.

        Args:
            entity_type: NGSI-LD entity type, e.g. ``Alert`` or ``Robot``.
            limit: Maximum number of entities to return.

        Returns:
            The matching entities, empty when the query fails.
        """
        url = (
            f"{self._config.base_url}/ngsi-ld/v1/entities"
            f"?type={entity_type}&limit={limit}"
        )
        try:
            payload = await self._transport.get_json(url)
        except Exception as exc:  # noqa: BLE001 - surfaced as absence of data
            logger.warning(
                "Context query failed for type %s: %s", entity_type, exc
            )
            return []
        if not isinstance(payload, list):
            return []
        return [
            ContextEntity.from_payload(item)
            for item in payload
            if isinstance(item, dict)
        ]

    async def get_alerts(self, limit: int = 100) -> list[ContextEntity]:
        """Read all projected incident alerts."""
        return await self.query_entities(ALERT_ENTITY_TYPE, limit=limit)

    async def get_alert(self, incident_id: str) -> ContextEntity | None:
        """Read the alert projected from a given Gateway incident id."""
        return await self.get_entity(f"urn:ngsi-ld:Alert:{incident_id}")

    async def get_robots(self, limit: int = 50) -> list[ContextEntity]:
        """Read all robot capability entities."""
        return await self.query_entities(ROBOT_ENTITY_TYPE, limit=limit)

    async def get_robot(self, robot_id: str) -> ContextEntity | None:
        """Read a single robot capability entity."""
        return await self.get_entity(f"urn:ngsi-ld:Robot:{robot_id}")

    async def close(self) -> None:
        """Release transport resources, when the transport owns any."""
        close = getattr(self._transport, "close", None)
        if callable(close):
            await close()


def _quote_entity_id(entity_id: str) -> str:
    """Percent-encode an entity id for use in a URL path."""
    from urllib.parse import quote

    return quote(entity_id, safe="")


def is_context_fresh(
    entity: ContextEntity,
    now: datetime | None = None,
    max_age_seconds: float = 120.0,
) -> bool:
    """Return True when an entity is recent enough to act on.

    Context that is stale or missing a timestamp must never be used to
    authorize an action (Issue #204 SPEC-6 / TC-3). An entity without
    ``observedAt`` is treated as **not fresh**.
    """
    if entity.observed_at is None:
        return False
    reference = now or datetime.now(timezone.utc)
    try:
        observed = datetime.fromisoformat(entity.observed_at)
    except (TypeError, ValueError):
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    age = (reference - observed).total_seconds()
    return 0 <= age <= max_age_seconds
