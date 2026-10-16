"""Device Registry and Configuration Ownership for Smart Factory.

Implements the Device Registry specification from docs/device-registry.md.
Provides strongly-typed schemas, validation, file loading, and query methods.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


DEVICE_ID_PATTERN = re.compile(r"^[a-z](?:[a-z0-9_-]{0,62}[a-z0-9])?$")


class DeviceLocation(BaseModel):
    """Physical location of a device within the factory."""

    model_config = ConfigDict(extra="forbid")

    factory_zone: Optional[str] = None
    line: Optional[str] = None
    notes: Optional[str] = None


class DeviceOwner(BaseModel):
    """Owner metadata for configuration responsibility."""

    model_config = ConfigDict(extra="forbid")

    team: str = Field(..., min_length=1)
    contact: str = Field(..., min_length=1)


class MqttTopics(BaseModel):
    """MQTT topic templates for a device."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(..., min_length=1)
    result: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    telemetry: Optional[str] = None

    def resolve(self, device_id: str) -> Dict[str, str]:
        """Resolve topic templates with the concrete device_id."""
        resolved = {
            "command": self.command.replace("{device_id}", device_id),
            "result": self.result.replace("{device_id}", device_id),
            "status": self.status.replace("{device_id}", device_id),
        }
        if self.telemetry:
            resolved["telemetry"] = self.telemetry.replace("{device_id}", device_id)
        return resolved


class DeviceEntry(BaseModel):
    """Entry describing a registered device in the factory."""

    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(..., min_length=1, max_length=64)
    device_type: str = Field(..., min_length=1)
    firmware_version: str = Field(..., min_length=1)
    capabilities: List[str] = Field(default_factory=list)
    mqtt_topics: MqttTopics
    physical_location: Optional[DeviceLocation] = None
    owner: DeviceOwner
    registered_at: str
    last_seen: Optional[str] = None

    @field_validator("device_id")
    @classmethod
    def validate_device_id_format(cls, v: str) -> str:
        if not DEVICE_ID_PATTERN.match(v):
            raise ValueError(
                f"Invalid device_id '{v}'. Must be lowercase a-z, 0-9, '-', '_', "
                "start with a letter, not end with '-' or '_', and be max 64 chars."
            )
        return v

    def has_capability(self, capability: str) -> bool:
        """Check if this device supports a given capability/command."""
        return capability in self.capabilities

    def get_resolved_topics(self) -> Dict[str, str]:
        """Return the fully resolved MQTT topics for this device."""
        return self.mqtt_topics.resolve(self.device_id)


class DeviceRegistry:
    """In-memory registry managing known devices and their capabilities."""

    def __init__(self, devices: Optional[Dict[str, DeviceEntry]] = None) -> None:
        self._devices: Dict[str, DeviceEntry] = devices or {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceRegistry":
        """Load and validate a device registry from a dictionary."""
        devices: Dict[str, DeviceEntry] = {}
        for key, raw_entry in data.items():
            if not isinstance(raw_entry, dict):
                raise ValueError(f"Device entry for key '{key}' must be a dictionary.")
            entry = DeviceEntry.model_validate(raw_entry)
            if entry.device_id != key:
                raise ValueError(
                    f"Dictionary key '{key}' does not match entry device_id '{entry.device_id}'."
                )
            devices[key] = entry
        return cls(devices)

    @classmethod
    def from_file(cls, path: Path | str) -> "DeviceRegistry":
        """Load and validate device registry from a JSON file."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Device registry file not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Root of device registry JSON must be an object.")
        return cls.from_dict(data)

    def get_device(self, device_id: str) -> Optional[DeviceEntry]:
        """Lookup a device by device_id."""
        return self._devices.get(device_id)

    def has_device(self, device_id: str) -> bool:
        """Check whether a device is registered."""
        return device_id in self._devices

    def has_capability(self, device_id: str, capability: str) -> bool:
        """Check if a registered device supports a specific capability."""
        device = self.get_device(device_id)
        if not device:
            return False
        return device.has_capability(capability)

    def list_devices(self, device_type: Optional[str] = None) -> List[DeviceEntry]:
        """List all devices, optionally filtered by device_type."""
        if device_type:
            return [d for d in self._devices.values() if d.device_type == device_type]
        return list(self._devices.values())

    def get_topics(self, device_id: str) -> Optional[Dict[str, str]]:
        """Return resolved MQTT topics for a device, or None if not found."""
        device = self.get_device(device_id)
        if not device:
            return None
        return device.get_resolved_topics()

    def register_device(self, entry: DeviceEntry) -> None:
        """Add or update a device entry in the registry."""
        self._devices[entry.device_id] = entry

    def count(self) -> int:
        """Return number of registered devices."""
        return len(self._devices)

    def to_dict(self) -> Dict[str, Any]:
        """Export registry back to canonical dictionary representation."""
        return {dev_id: entry.model_dump() for dev_id, entry in self._devices.items()}
