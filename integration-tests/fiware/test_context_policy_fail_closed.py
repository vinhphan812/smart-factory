"""Fail-closed behaviour of the Yanshee response policy over the real
configuration path (Issue #204 / ADR-0017).

The existing ``edge-ai-robot/tests/test_context_policy.py`` injects a
``FakeContextReader``. These tests instead build the facade from
``ContextQueryConfig.from_env()`` and let the real ``ContextEntity`` parsing
run, so a defect in the environment wiring, in ``from_payload()`` or in the
freshness handling cannot hide behind a fake.

Evidence level: L2 (simulation) — the transport is a stub, the broker is not
real, and no hardware is involved.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from edge_ai_robot.context import (
    DecisionReason,
    GatewayApproval,
    SkillDecision,
    YansheeResponsePolicy,
)

from iot_gateway.context_query import ContextQueryConfig, ContextQueryFacade

NOW = datetime(2026, 10, 24, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _clean_orion_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the environment so ``from_env()`` is deterministic."""
    for name in (
        "ORION_LD_URL",
        "ORION_LD_CONTEXT",
        "ORION_LD_CONTEXT_TIMEOUT",
        "ORION_LD_TOKEN",
        "ORION_LD_REQUIRE_TLS",
        "ORION_LD_CA_BUNDLE",
    ):
        monkeypatch.delenv(name, raising=False)


class RoutingTransport:
    """Routes the single-entity GET to the alert or the robot payload.

    ``ContextQueryFacade.get_alert`` and ``get_robot`` both issue
    ``GET {base_url}/ngsi-ld/v1/entities/{quoted_id}``, so the entity type
    appears in the URL.
    """

    def __init__(
        self, alert: dict[str, Any] | None, robot: dict[str, Any] | None
    ) -> None:
        self._alert = alert
        self._robot = robot

    async def get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        if "Alert" in url:
            return self._alert
        if "Robot" in url:
            return self._robot
        return None

    async def close(self) -> None:
        return None


def _alert_payload(observed_at: str, status: str = "active") -> dict[str, Any]:
    """Build an Orion-LD Alert payload.

    ``ContextEntity.from_payload`` derives ``observed_at`` from
    ``dateModified`` only, so ``dateModified.value`` must carry the
    observation timestamp.
    """
    return {
        "id": "urn:ngsi-ld:Alert:INC-001",
        "type": "Alert",
        "dateModified": {"type": "DateTime", "value": observed_at},
        "status": {"type": "Text", "value": status},
    }


def _robot_payload(
    verified: bool = True, emergency_stop: bool = False
) -> dict[str, Any]:
    """Build an Orion-LD Robot payload."""
    return {
        "id": "urn:ngsi-ld:Robot:yanshee-01",
        "type": "Robot",
        "dateModified": {"type": "DateTime", "value": "2026-10-24T08:00:00+00:00"},
        "status": {"type": "Text", "value": "idle"},
        "supportedActions": {"type": "Array", "value": ["notify_operator"]},
        "verificationStatus": {
            "type": "Text",
            "value": "VERIFIED" if verified else "UNVERIFIED",
        },
        "verificationSource": {
            "type": "Text",
            "value": "yanshee-sdk@0.1.0" if verified else "unverified-no-sdk-audit",
        },
        "dataQuality": {
            "type": "Text",
            "value": "PHYSICAL" if verified else "UNKNOWN",
        },
        "emergencyStop": {"type": "Boolean", "value": emergency_stop},
    }


def _facade(transport: RoutingTransport) -> ContextQueryFacade:
    """Build the facade through the real environment-driven configuration."""
    config = ContextQueryConfig.from_env()
    return ContextQueryFacade(config, transport=transport)


def _approval() -> GatewayApproval:
    return GatewayApproval(
        outbox_entry_id="outbox-001",
        incident_id="INC-001",
        skill="yanshee/speech",
        approved_at="2026-10-24T08:00:00+00:00",
    )


def _policy(facade: ContextQueryFacade) -> YansheeResponsePolicy:
    return YansheeResponsePolicy(
        context_reader=facade, robot_id="yanshee-01", now_provider=NOW
    )


class TestFailClosedOverRealConfiguration:
    """The policy must refuse anything that is not fresh and verified."""

    @pytest.mark.asyncio
    async def test_stale_context_is_denied(self) -> None:
        stale = (NOW - timedelta(seconds=600)).isoformat()
        facade = _facade(
            RoutingTransport(_alert_payload(stale), _robot_payload())
        )
        decision = await _policy(facade).evaluate(
            "INC-001", "yanshee/speech", _approval()
        )
        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.CONTEXT_STALE

    @pytest.mark.asyncio
    async def test_missing_observation_timestamp_is_denied(self) -> None:
        payload = _alert_payload("2026-10-24T08:00:00+00:00")
        payload.pop("dateModified")
        facade = _facade(RoutingTransport(payload, _robot_payload()))
        decision = await _policy(facade).evaluate(
            "INC-001", "yanshee/speech", _approval()
        )
        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.CONTEXT_STALE

    @pytest.mark.asyncio
    async def test_unverified_robot_capability_is_denied(self) -> None:
        facade = _facade(
            RoutingTransport(
                _alert_payload("2026-10-24T08:00:00+00:00"),
                _robot_payload(verified=False),
            )
        )
        decision = await _policy(facade).evaluate(
            "INC-001", "yanshee/speech", _approval()
        )
        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.ROBOT_CAPABILITY_UNVERIFIED

    @pytest.mark.asyncio
    async def test_emergency_stop_blocks_fresh_verified_context(self) -> None:
        facade = _facade(
            RoutingTransport(
                _alert_payload("2026-10-24T08:00:00+00:00"),
                _robot_payload(verified=True, emergency_stop=True),
            )
        )
        decision = await _policy(facade).evaluate(
            "INC-001", "yanshee/speech", _approval()
        )
        assert decision.decision is SkillDecision.BLOCKED
        assert decision.reason is DecisionReason.EMERGENCY_STOP_ACTIVE

    @pytest.mark.asyncio
    async def test_physical_skill_topic_is_blocked(self) -> None:
        facade = _facade(
            RoutingTransport(
                _alert_payload("2026-10-24T08:00:00+00:00"), _robot_payload()
            )
        )
        decision = await _policy(facade).evaluate(
            "INC-001", "yanshee/movement", _approval()
        )
        assert decision.decision is SkillDecision.BLOCKED
        assert decision.reason is DecisionReason.PHYSICAL_SKILL_BLOCKED

    @pytest.mark.asyncio
    async def test_context_without_gateway_approval_is_denied(self) -> None:
        facade = _facade(
            RoutingTransport(
                _alert_payload("2026-10-24T08:00:00+00:00"), _robot_payload()
            )
        )
        decision = await _policy(facade).evaluate("INC-001", "yanshee/speech", None)
        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.NO_GATEWAY_APPROVAL

    @pytest.mark.asyncio
    async def test_fresh_verified_context_is_approved(self) -> None:
        """The positive control: the denials above are not vacuous."""
        facade = _facade(
            RoutingTransport(
                _alert_payload("2026-10-24T08:00:00+00:00"), _robot_payload()
            )
        )
        decision = await _policy(facade).evaluate(
            "INC-001", "yanshee/speech", _approval()
        )
        assert decision.decision is SkillDecision.APPROVED
        assert decision.reason is DecisionReason.OK
