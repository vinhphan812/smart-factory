"""NGSI-LD Robot entity mapping for the FIWARE context layer (Issue #204).

This module maps a robot capability reading onto an NGSI-LD ``Robot`` entity.

Safety and honesty constraints (ADR-0006, ADR-0014, Issue #204 SPEC-1):

- Robot ``status``, ``batteryLevel`` and ``supportedActions`` are only ever
  populated from a **verified** capability source. Any other source yields
  explicit ``UNKNOWN`` values plus ``verificationStatus: UNVERIFIED``.
- Nothing in this module can command, dispatch or authorize a physical
  action. It produces a *read model* only.
- The Yanshee SDK is not yet audited (Issues #159/#160). Until that lands the
  default source is :class:`UnverifiedRobotCapabilitySource`, which reports
  ``UNKNOWN`` for every measured field.

Evidence level: L1 (unit) for the mapping, L2 (simulation) for the source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, runtime_checkable

#: Sentinel used whenever a measured value has no verified source.
UNKNOWN_VALUE = "UNKNOWN"

#: Entity id of the Smart Factory lab instance described by ADR-0014.
DEFAULT_FACTORY_ENTITY_ID = "urn:ngsi-ld:Factory:aibot-01"


class VerificationStatus(str, Enum):
    """Whether the values in an entity were backed by a verified source."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class DataQuality(str, Enum):
    """Whether the observation came from physical hardware or a simulation.

    Consumers (dashboard, Unity, research reports) must be able to tell
    simulated data from real physical observation (Issue #204 TC-5).
    """

    PHYSICAL = "PHYSICAL"
    SIMULATED = "SIMULATED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RobotCapability:
    """A robot capability reading.

    Attributes:
        robot_id: Canonical robot identifier, e.g. ``yanshee-01``.
        name: Human readable robot name.
        status: Reported robot status. ``UNKNOWN`` when unverified.
        battery_level: Battery charge in percent, or ``None`` when unknown.
        supported_actions: Actions the robot actually supports.
        verified: True only when the values came from a verified source
            (a real, audited SDK/HIL read).
        verification_source: Identifier of the source that produced the
            reading, e.g. ``yanshee-sdk@0.1.0`` or ``unverified``.
        data_quality: Whether the reading is physical or simulated.
        observed_at: ISO-8601 observation timestamp. ``None`` when unknown;
            never fabricated.
        factory_entity_id: Optional factory the robot belongs to.
    """

    robot_id: str
    name: str = ""
    status: str = UNKNOWN_VALUE
    battery_level: float | None = None
    supported_actions: tuple[str, ...] = ()
    verified: bool = False
    verification_source: str = "unverified"
    data_quality: DataQuality = DataQuality.UNKNOWN
    observed_at: str | None = None
    factory_entity_id: str | None = None


@runtime_checkable
class RobotCapabilitySource(Protocol):
    """Source of robot capability readings.

    Implementations must report ``verified=False`` unless the reading is
    backed by a verified SDK or hardware-in-the-loop observation.
    """

    def fetch(self) -> RobotCapability:
        """Return the latest capability reading."""
        ...


class UnverifiedRobotCapabilitySource:
    """Default source used while the Yanshee SDK is unaudited (#159/#160).

    Every measured field is reported as ``UNKNOWN`` and the reading is
    flagged ``UNVERIFIED``. This is the honest representation of "we have no
    verified robot telemetry yet" and must not be replaced by fabricated
    numbers.
    """

    def __init__(
        self,
        robot_id: str = "yanshee-01",
        name: str = "UBTECH Yanshee",
        data_quality: DataQuality = DataQuality.UNKNOWN,
    ) -> None:
        self._robot_id = robot_id
        self._name = name
        self._data_quality = data_quality

    def fetch(self) -> RobotCapability:
        """Return an explicitly unverified capability reading."""
        return RobotCapability(
            robot_id=self._robot_id,
            name=self._name,
            status=UNKNOWN_VALUE,
            battery_level=None,
            supported_actions=(),
            verified=False,
            verification_source="unverified-no-sdk-audit",
            data_quality=self._data_quality,
            observed_at=None,
        )


@dataclass(frozen=True)
class StaticRobotCapabilitySource:
    """Deterministic capability source for simulations and tests.

    This source never claims hardware verification. It is explicitly
    ``verified=False`` and ``data_quality=SIMULATED`` unless the caller
    overrides it, which keeps L2 evidence clearly labelled as simulation.
    """

    capability: RobotCapability

    def fetch(self) -> RobotCapability:
        """Return the configured capability reading."""
        return self.capability


def robot_entity_id(robot_id: str) -> str:
    """Build the canonical NGSI-LD entity id for a robot."""
    return f"urn:ngsi-ld:Robot:{robot_id}"


def to_robot_entity(capability: RobotCapability) -> dict:
    """Map a capability reading onto an NGSI-LD ``Robot`` entity.

    Unverified readings keep ``UNKNOWN`` values; the entity records why via
    ``verificationStatus`` and ``verificationSource`` so downstream consumers
    cannot mistake a placeholder for an observation.
    """
    status = capability.status or UNKNOWN_VALUE
    supported_actions = list(capability.supported_actions)
    if not capability.verified:
        # An unverified source may not assert a concrete status or a
        # concrete capability list either.
        status = UNKNOWN_VALUE
        supported_actions = []

    entity: dict = {
        "id": robot_entity_id(capability.robot_id),
        "type": "Robot",
        "name": {
            "type": "Text",
            "value": capability.name or capability.robot_id,
        },
        "robotId": {
            "type": "Text",
            "value": capability.robot_id,
        },
        "status": {
            "type": "Text",
            "value": status,
        },
        "supportedActions": {
            "type": "Array",
            "value": supported_actions,
        },
        "verificationStatus": {
            "type": "Text",
            "value": (
                VerificationStatus.VERIFIED.value
                if capability.verified
                else VerificationStatus.UNVERIFIED.value
            ),
        },
        "verificationSource": {
            "type": "Text",
            "value": capability.verification_source,
        },
        "dataQuality": {
            "type": "Text",
            "value": capability.data_quality.value,
        },
    }

    if capability.battery_level is not None and capability.verified:
        entity["batteryLevel"] = {
            "type": "Number",
            "value": capability.battery_level,
        }
    else:
        entity["batteryLevel"] = {
            "type": "Text",
            "value": UNKNOWN_VALUE,
        }

    if capability.observed_at:
        entity["observedAt"] = {
            "type": "DateTime",
            "value": capability.observed_at,
        }

    if capability.factory_entity_id:
        entity["partOf"] = {
            "type": "Relationship",
            "object": capability.factory_entity_id,
        }

    return entity
