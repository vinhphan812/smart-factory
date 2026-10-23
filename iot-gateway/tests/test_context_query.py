"""Unit tests for the read-only FIWARE context facade (Issue #204).

The facade is the only FIWARE access path exposed to consumers. These
tests pin down the read-only guarantee (SPEC-3) and the staleness rule that
keeps outdated context from being usable (SPEC-6 / TC-3).
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from iot_gateway.context_query import (
    ALERT_ENTITY_TYPE,
    ROBOT_ENTITY_TYPE,
    ContextEntity,
    ContextQueryConfig,
    ContextQueryFacade,
    is_context_fresh,
)


class FakeTransport:
    """Records every request so read-only behaviour is auditable."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = responses or {}
        self.requested_urls: list[str] = []

    async def get_json(
        self, url: str, headers: dict[str, str] | None = None
    ) -> Any:
        self.requested_urls.append(url)
        for fragment, payload in self.responses.items():
            if fragment in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        return []


class TestFacadeIsReadOnly:
    """The facade must not expose any mutation or command path."""

    def test_no_write_or_command_methods_exist(self) -> None:
        forbidden = (
            "upsert",
            "post",
            "patch",
            "put",
            "delete",
            "create_entity",
            "update_entity",
            "dispatch",
            "send_command",
            "publish",
            "execute",
            "move",
        )
        public_methods = [
            name
            for name in dir(ContextQueryFacade)
            if not name.startswith("_")
            and callable(getattr(ContextQueryFacade, name))
        ]
        for name in public_methods:
            for verb in forbidden:
                assert verb not in name.lower(), (
                    f"ContextQueryFacade exposes a mutating method: {name}"
                )

    def test_all_requests_use_get_transport(self) -> None:
        transport = FakeTransport({"/entities": []})
        facade = ContextQueryFacade(
            ContextQueryConfig(base_url="http://broker:1026"), transport
        )

        import asyncio

        asyncio.run(facade.get_alerts())

        assert transport.requested_urls
        for url in transport.requested_urls:
            assert url.startswith("http://broker:1026/ngsi-ld/v1/entities")


class TestFacadeQueries:
    """Query behaviour."""

    def test_get_alerts_uses_type_filter(self) -> None:
        transport = FakeTransport({"/entities": []})
        facade = ContextQueryFacade(
            ContextQueryConfig(base_url="http://broker:1026"), transport
        )

        import asyncio

        asyncio.run(facade.get_alerts(limit=7))

        url = transport.requested_urls[0]
        assert f"type={ALERT_ENTITY_TYPE}" in url
        assert "limit=7" in url

    def test_get_robots_uses_type_filter(self) -> None:
        transport = FakeTransport({"/entities": []})
        facade = ContextQueryFacade(
            ContextQueryConfig(base_url="http://broker:1026"), transport
        )

        import asyncio

        asyncio.run(facade.get_robots())

        assert f"type={ROBOT_ENTITY_TYPE}" in transport.requested_urls[0]

    def test_get_alert_uses_canonical_id(self) -> None:
        transport = FakeTransport({"/entities": []})
        facade = ContextQueryFacade(
            ContextQueryConfig(base_url="http://broker:1026"), transport
        )

        import asyncio

        asyncio.run(facade.get_alert("INC-001"))

        assert "urn%3Angsi-ld%3AAlert%3AINC-001" in transport.requested_urls[0]

    def test_get_alert_returns_entity(self) -> None:
        payload = {
            "id": "urn:ngsi-ld:Alert:INC-001",
            "type": "Alert",
            "status": {"type": "Text", "value": "active"},
            "dateModified": {"type": "DateTime", "value": "2026-10-23T08:00:00Z"},
        }
        transport = FakeTransport({"/entities/": payload})
        facade = ContextQueryFacade(
            ContextQueryConfig(base_url="http://broker:1026"), transport
        )

        import asyncio

        entity = asyncio.run(facade.get_alert("INC-001"))

        assert entity is not None
        assert entity.entity_id == "urn:ngsi-ld:Alert:INC-001"
        assert entity.property("status") == "active"

    def test_missing_entity_returns_none(self) -> None:
        transport = FakeTransport({"/entities/": RuntimeError("404")})
        facade = ContextQueryFacade(
            ContextQueryConfig(base_url="http://broker:1026"), transport
        )

        import asyncio

        assert asyncio.run(facade.get_alert("INC-404")) is None

    def test_query_failure_returns_empty_list(self) -> None:
        transport = FakeTransport({"/entities": RuntimeError("boom")})
        facade = ContextQueryFacade(
            ContextQueryConfig(base_url="http://broker:1026"), transport
        )

        import asyncio

        assert asyncio.run(facade.get_alerts()) == []


class TestContextEntity:
    """Entity parsing helpers."""

    def test_from_payload_extracts_attributes(self) -> None:
        payload = {
            "id": "urn:ngsi-ld:Alert:INC-9",
            "type": "Alert",
            "severity": {"type": "Text", "value": "critical"},
            "relatedTo": {
                "type": "Relationship",
                "object": "urn:ngsi-ld:Module:conveyor-01",
            },
        }
        entity = ContextEntity.from_payload(payload)

        assert entity.entity_type == "Alert"
        assert entity.property("severity") == "critical"
        assert entity.relationship("relatedTo") == (
            "urn:ngsi-ld:Module:conveyor-01"
        )

    def test_missing_relationship_returns_none(self) -> None:
        entity = ContextEntity.from_payload(
            {"id": "urn:ngsi-ld:Alert:INC-9", "type": "Alert"}
        )
        assert entity.relationship("relatedTo") is None

    def test_missing_property_returns_none(self) -> None:
        entity = ContextEntity.from_payload(
            {"id": "urn:ngsi-ld:Alert:INC-9", "type": "Alert"}
        )
        assert entity.property("status") is None


class TestFreshness:
    """Stale context must never be usable (SPEC-6 / TC-3)."""

    def _entity(self, observed_at: str | None) -> ContextEntity:
        payload: dict[str, Any] = {
            "id": "urn:ngsi-ld:Alert:INC-1",
            "type": "Alert",
        }
        if observed_at is not None:
            payload["dateModified"] = {
                "type": "DateTime",
                "value": observed_at,
            }
        return ContextEntity.from_payload(payload)

    def test_fresh_entity_is_fresh(self) -> None:
        now = datetime(2026, 10, 23, 8, 0, 30, tzinfo=timezone.utc)
        entity = self._entity("2026-10-23T08:00:00+00:00")
        assert is_context_fresh(entity, now=now) is True

    def test_stale_entity_is_not_fresh(self) -> None:
        now = datetime(2026, 10, 23, 8, 10, 0, tzinfo=timezone.utc)
        entity = self._entity("2026-10-23T08:00:00+00:00")
        assert is_context_fresh(entity, now=now) is False

    def test_entity_without_timestamp_is_not_fresh(self) -> None:
        entity = self._entity(None)
        assert is_context_fresh(entity) is False

    def test_malformed_timestamp_is_not_fresh(self) -> None:
        entity = self._entity("not-a-timestamp")
        assert is_context_fresh(entity) is False

    def test_future_timestamp_is_not_fresh(self) -> None:
        now = datetime(2026, 10, 23, 8, 0, 0, tzinfo=timezone.utc)
        future = (now + timedelta(seconds=30)).isoformat()
        entity = self._entity(future)
        assert is_context_fresh(entity, now=now) is False


class TestConfig:
    """Configuration handling."""

    def test_defaults(self) -> None:
        config = ContextQueryConfig()
        assert config.base_url == "http://localhost:1026"
        assert config.timeout_seconds == 5.0

    def test_from_env_overrides(self, monkeypatch) -> None:
        monkeypatch.setenv("ORION_LD_URL", "http://orion:1026")
        monkeypatch.setenv("ORION_LD_CONTEXT_TIMEOUT", "9.5")
        config = ContextQueryConfig.from_env()
        assert config.base_url == "http://orion:1026"
        assert config.timeout_seconds == 9.5
