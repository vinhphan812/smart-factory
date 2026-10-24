"""Controlled scenario for the FIWARE -> Yanshee context path (Issue #204).

Scenario (Issue #204 SPEC-4)::

    anomalous sensor value
      -> Gateway alert
      -> NGSI-LD Alert Property
      -> Dashboard / Unity subscriber
      -> Yanshee approved notification

The scenario is executed against an in-memory NGSI-LD broker double so it is
deterministic and runnable without Docker. It records a **transport and
provenance trace** so that every hop is auditable, and it asserts the
acceptance criteria TC-1..TC-5.

Evidence level: L2 (simulation). The broker is a double, the robot is a
mock, and no physical hardware is involved. Nothing here proves that the
real Yanshee SDK or a real Orion-LD deployment behaves this way — that
remains BLOCKED on Issue #160 (SDK audit) and Issue #202 (CI/E2E harness).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from edge_ai_robot.context import (
    DecisionReason,
    GatewayApproval,
    SkillDecision,
    YansheeResponsePolicy,
)

from iot_gateway.adapters.orion_incident import IncidentProjection, to_alert_entity
from iot_gateway.adapters.orion_robot import (
    DataQuality,
    RobotCapability,
    StaticRobotCapabilitySource,
    UnverifiedRobotCapabilitySource,
    to_robot_entity,
)
from iot_gateway.context_query import ContextEntity, ContextQueryFacade

TRACE: list[dict[str, Any]] = []

NOW = datetime(2026, 10, 23, 9, 0, 0, tzinfo=timezone.utc)


def _record(hop: str, **fields: Any) -> None:
    """Append a transport/provenance hop to the trace."""
    TRACE.append({"hop": hop, "at": NOW.isoformat(), **fields})


class FakeBrokerTransport:
    """In-memory NGSI-LD broker double (GET + upsert for the sink side)."""

    def __init__(self) -> None:
        self.entities: dict[str, dict[str, Any]] = {}
        self.get_requests: list[str] = []

    async def upsert(self, entity: dict[str, Any]) -> None:
        """Store an entity (sink side of the scenario)."""
        self.entities[entity["id"]] = entity
        _record(
            "orion-upsert",
            entity_id=entity["id"],
            entity_type=entity["type"],
            trace_id=entity.get("traceId", {}).get("value"),
        )

    async def get_json(
        self, url: str, headers: dict[str, str] | None = None
    ) -> Any:
        self.get_requests.append(url)
        _record("orion-get", url=url)
        for entity_id, entity in self.entities.items():
            encoded = entity_id.replace(":", "%3A")
            if encoded in url or entity_id in url:
                return entity
        if "type=Alert" in url:
            return [
                e for e in self.entities.values() if e["type"] == "Alert"
            ]
        if "type=Robot" in url:
            return [
                e for e in self.entities.values() if e["type"] == "Robot"
            ]
        return []


class FakeYansheeMock:
    """Robot mock recording the skills it was asked to perform."""

    def __init__(self) -> None:
        self.received: list[dict[str, Any]] = []

    def receive(self, payload: dict[str, Any]) -> None:
        """Record a delivered notification."""
        self.received.append(payload)
        _record(
            "yanshee-notification",
            skill=payload.get("skill"),
            trace_id=payload.get("trace_id"),
        )


class FakeSubscriber:
    """Stand-in for the Unity / React context subscriber."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.alerts: list[ContextEntity] = []

    def on_alert(self, entity: ContextEntity) -> None:
        """Receive a projected alert entity."""
        self.alerts.append(entity)
        _record(
            "subscriber-alert",
            subscriber=self.name,
            entity_id=entity.entity_id,
            trace_id=entity.property("traceId"),
        )


class FakeGatewayOutbox:
    """Gateway-approved incident outbox double."""

    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {}

    def approve(
        self, entry_id: str, incident_id: str, skill: str
    ) -> GatewayApproval:
        """Record a Gateway-approved notification."""
        self.entries[entry_id] = {
            "entry_id": entry_id,
            "incident_id": incident_id,
            "skill": skill,
        }
        _record(
            "gateway-approval",
            entry_id=entry_id,
            incident_id=incident_id,
            skill=skill,
        )
        return GatewayApproval(
            outbox_entry_id=entry_id,
            incident_id=incident_id,
            skill=skill,
            approved_at=NOW.isoformat(),
        )


def _anomalous_sensor_event() -> dict[str, Any]:
    """The triggering stimulus: an anomalous conveyor motor temperature."""
    return {
        "event_id": "evt-anom-001",
        "device_id": "conveyor-01",
        "event_type": "telemetry",
        "payload": {
            "state": "RUNNING",
            "sensors": {"temperature_centi_c": 8500},
        },
        "received_at": NOW.isoformat(),
        "sequence": 101,
    }


def _incident_from_anomaly() -> dict[str, Any]:
    """The Gateway incident the anomaly produces."""
    return {
        "id": "INC-ANOM-001",
        "severity": "CRITICAL",
        "device_id": "conveyor-01",
        "title": "Conveyor motor temperature anomaly",
        "message": "Motor temperature 85.00 C exceeds threshold 75.00 C.",
        "timestamp": NOW.isoformat(),
        "status": "open",
        "source": "temperature-sensor",
        "recommended_action": "Reduce load and inspect motor cooling",
        "acknowledged_by": None,
        "acknowledged_at": None,
        "resolved_by": None,
        "resolved_at": None,
        "notes": None,
        "audit_trail": [],
    }


@pytest.fixture(autouse=True)
def _clear_trace() -> None:
    TRACE.clear()


async def _run_scenario(
    *,
    robot_capability: RobotCapability,
    stale: bool = False,
    approve: bool = True,
) -> tuple[dict[str, Any], FakeYansheeMock, list[FakeSubscriber], Any]:
    """Execute the controlled scenario and return the observable outcome."""
    TRACE.clear()
    broker = FakeBrokerTransport()
    outbox = FakeGatewayOutbox()
    robot_mock = FakeYansheeMock()
    unity = FakeSubscriber("unity")
    react = FakeSubscriber("react")

    # --- Hop 1: anomalous sensor value arrives at the Gateway ----------
    event = _anomalous_sensor_event()
    _record(
        "sensor-anomaly",
        event_id=event["event_id"],
        device_id=event["device_id"],
        temperature_centi_c=event["payload"]["sensors"]["temperature_centi_c"],
    )

    # --- Hop 2: Gateway raises and stores the incident ------------------
    incident = _incident_from_anomaly()
    _record(
        "gateway-incident",
        incident_id=incident["id"],
        severity=incident["severity"],
        source_event_id=event["event_id"],
    )

    # --- Hop 3: incident projected onto an NGSI-LD Alert ----------------
    observed_at = (
        (NOW - timedelta(hours=1)).isoformat() if stale else NOW.isoformat()
    )
    projection = IncidentProjection(
        incident=incident,
        trace_id="trace-anom-001",
        source_event_id=event["event_id"],
        module_entity_id="urn:ngsi-ld:Module:conveyor-01",
        sensor_entity_id="urn:ngsi-ld:Sensor:conveyor-temp-01",
        data_quality=DataQuality.SIMULATED,
    )
    alert_entity = to_alert_entity(projection)
    alert_entity["dateModified"] = {
        "type": "DateTime",
        "value": observed_at,
    }
    await broker.upsert(alert_entity)

    robot_entity = to_robot_entity(robot_capability)
    robot_entity["dateModified"] = {
        "type": "DateTime",
        "value": NOW.isoformat(),
    }
    await broker.upsert(robot_entity)

    # --- Hop 4: Dashboard / Unity subscribers read the context ----------
    facade = ContextQueryFacade(transport=broker)
    unity_alert = await facade.get_alert(incident["id"])
    react_alert = await facade.get_alert(incident["id"])
    assert unity_alert is not None
    assert react_alert is not None
    unity.on_alert(unity_alert)
    react.on_alert(react_alert)

    # --- Hop 5: Gateway approves a Yanshee notification -----------------
    approval = (
        outbox.approve("outbox-001", incident["id"], "yanshee/speech")
        if approve
        else None
    )

    # --- Hop 6: Yanshee response policy evaluates the context -----------
    policy = YansheeResponsePolicy(
        context_reader=facade, robot_id="yanshee-01", now_provider=NOW
    )
    decision = await policy.evaluate(
        incident["id"], "yanshee/speech", approval
    )
    _record(
        "response-policy",
        decision=decision.decision.value,
        reason=decision.reason.value,
    )

    # --- Hop 7: only an approved decision reaches the robot -------------
    if decision.approved:
        robot_mock.receive(
            {
                "skill": "yanshee/speech",
                "incident_id": incident["id"],
                "trace_id": incident["id"] and unity_alert.property("traceId"),
                "data_quality": unity_alert.property("dataQuality"),
            }
        )

    subscribers = [unity, react]
    return (
        {
            "event": event,
            "incident": incident,
            "alert_entity": alert_entity,
            "robot_entity": robot_entity,
            "decision": decision,
            "facade": facade,
            "broker": broker,
            "outbox": outbox,
        },
        robot_mock,
        subscribers,
        decision,
    )


class TestControlledScenario:
    """The happy path of the controlled scenario."""

    @pytest.mark.asyncio
    async def test_scenario_produces_one_approved_notification(self) -> None:
        capability = RobotCapability(
            robot_id="yanshee-01",
            name="UBTECH Yanshee",
            status="idle",
            battery_level=91.0,
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk-mock@0.1.0",
            data_quality=DataQuality.SIMULATED,
            observed_at=NOW.isoformat(),
        )
        state, robot_mock, subscribers, decision = await _run_scenario(
            robot_capability=capability
        )

        assert decision.decision is SkillDecision.APPROVED
        assert len(robot_mock.received) == 1

    @pytest.mark.asyncio
    async def test_tc1_alert_reaches_both_subscribers_with_same_trace(self) -> None:
        """TC-1: one alert in Orion, Unity and React, exact source trace."""
        capability = RobotCapability(
            robot_id="yanshee-01",
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk-mock@0.1.0",
            data_quality=DataQuality.SIMULATED,
            observed_at=NOW.isoformat(),
        )
        state, robot_mock, subscribers, decision = await _run_scenario(
            robot_capability=capability
        )

        unity, react = subscribers
        assert len(unity.alerts) == 1
        assert len(react.alerts) == 1

        unity_alert = unity.alerts[0]
        react_alert = react.alerts[0]

        assert unity_alert.entity_id == react_alert.entity_id
        assert unity_alert.property("traceId") == "trace-anom-001"
        assert react_alert.property("traceId") == "trace-anom-001"
        # The trace matches the originating Gateway event.
        assert (
            unity_alert.property("sourceEventId")
            == state["event"]["event_id"]
        )

    @pytest.mark.asyncio
    async def test_tc2_robot_receives_only_approved_skill(self) -> None:
        """TC-2: the robot mock receives only an approved skill."""
        capability = RobotCapability(
            robot_id="yanshee-01",
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk-mock@0.1.0",
            data_quality=DataQuality.SIMULATED,
            observed_at=NOW.isoformat(),
        )
        _, robot_mock, _, _ = await _run_scenario(
            robot_capability=capability
        )

        assert len(robot_mock.received) == 1
        assert robot_mock.received[0]["skill"] == "yanshee/speech"

    @pytest.mark.asyncio
    async def test_tc3_stale_context_never_dispatches(self) -> None:
        """TC-3: outdated context never dispatches a robot action."""
        capability = RobotCapability(
            robot_id="yanshee-01",
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk-mock@0.1.0",
            data_quality=DataQuality.SIMULATED,
            observed_at=NOW.isoformat(),
        )
        _, robot_mock, _, decision = await _run_scenario(
            robot_capability=capability, stale=True
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.CONTEXT_STALE
        assert robot_mock.received == []

    @pytest.mark.asyncio
    async def test_tc5_simulated_data_is_distinguishable(self) -> None:
        """TC-5: user-facing views distinguish simulated from physical."""
        capability = RobotCapability(
            robot_id="yanshee-01",
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk-mock@0.1.0",
            data_quality=DataQuality.SIMULATED,
            observed_at=NOW.isoformat(),
        )
        state, _, subscribers, _ = await _run_scenario(
            robot_capability=capability
        )

        unity, react = subscribers
        assert unity.alerts[0].property("dataQuality") == "SIMULATED"
        assert react.alerts[0].property("dataQuality") == "SIMULATED"
        assert (
            state["robot_entity"]["dataQuality"]["value"] == "SIMULATED"
        )

    @pytest.mark.asyncio
    async def test_unapproved_incident_never_reaches_the_robot(self) -> None:
        """A context change without Gateway approval dispatches nothing."""
        capability = RobotCapability(
            robot_id="yanshee-01",
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk-mock@0.1.0",
            data_quality=DataQuality.SIMULATED,
            observed_at=NOW.isoformat(),
        )
        _, robot_mock, _, decision = await _run_scenario(
            robot_capability=capability, approve=False
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.NO_GATEWAY_APPROVAL
        assert robot_mock.received == []

    @pytest.mark.asyncio
    async def test_unverified_robot_capability_blocks_notification(self) -> None:
        """SPEC-1: without a verified SDK reading, nothing is proposed."""
        capability = UnverifiedRobotCapabilitySource().fetch()
        _, robot_mock, _, decision = await _run_scenario(
            robot_capability=capability
        )

        assert decision.decision is SkillDecision.DENIED
        assert decision.reason is DecisionReason.ROBOT_CAPABILITY_UNVERIFIED
        assert robot_mock.received == []

    @pytest.mark.asyncio
    async def test_trace_records_every_hop_in_order(self) -> None:
        """The scenario produces an auditable transport/provenance trace."""
        capability = RobotCapability(
            robot_id="yanshee-01",
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk-mock@0.1.0",
            data_quality=DataQuality.SIMULATED,
            observed_at=NOW.isoformat(),
        )
        await _run_scenario(robot_capability=capability)

        hops = [entry["hop"] for entry in TRACE]
        assert hops[0] == "sensor-anomaly"
        assert hops[1] == "gateway-incident"
        assert "orion-upsert" in hops
        assert "gateway-approval" in hops
        assert "response-policy" in hops
        assert hops[-1] == "yanshee-notification"

    @pytest.mark.asyncio
    async def test_trace_is_json_serialisable(self) -> None:
        """The trace can be attached to a report as raw evidence."""
        capability = RobotCapability(
            robot_id="yanshee-01",
            supported_actions=("notify_operator",),
            verified=True,
            verification_source="yanshee-sdk-mock@0.1.0",
            data_quality=DataQuality.SIMULATED,
            observed_at=NOW.isoformat(),
        )
        await _run_scenario(robot_capability=capability)

        payload = json.dumps(TRACE, indent=2, default=str)
        assert "sensor-anomaly" in payload
