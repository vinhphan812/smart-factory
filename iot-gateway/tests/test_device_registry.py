"""Unit tests for DeviceRegistry in iot_gateway."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from iot_gateway.device_registry import (
    DeviceEntry,
    DeviceLocation,
    DeviceOwner,
    DeviceRegistry,
    MqttTopics,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "contracts" / "v1" / "examples"
EXAMPLE_REGISTRY_PATH = EXAMPLES_DIR / "device-registry.json"


def test_load_golden_example():
    """Verify loading the golden example device-registry.json."""
    assert EXAMPLE_REGISTRY_PATH.exists(), f"Example not found at {EXAMPLE_REGISTRY_PATH}"
    registry = DeviceRegistry.from_file(EXAMPLE_REGISTRY_PATH)

    assert registry.count() >= 5
    assert registry.has_device("bridge-001")
    assert registry.has_device("conveyor-01")
    assert registry.has_device("sorting-01")
    assert registry.has_device("packaging-01")
    assert registry.has_device("forklift-01")
    assert registry.has_device("iot-gateway-01")


def test_device_entry_details():
    """Verify loaded device fields and ownership."""
    registry = DeviceRegistry.from_file(EXAMPLE_REGISTRY_PATH)
    device = registry.get_device("conveyor-01")

    assert device is not None
    assert device.device_id == "conveyor-01"
    assert device.device_type == "mega_reference"
    assert device.firmware_version == "v1.0.0"
    assert device.owner.team == "controls"
    assert device.owner.contact == "controls@aibot.dntu.edu.vn"
    assert device.physical_location is not None
    assert device.physical_location.factory_zone == "Material Transfer"


def test_capabilities_query():
    """Verify capability lookup on devices."""
    registry = DeviceRegistry.from_file(EXAMPLE_REGISTRY_PATH)

    assert registry.has_capability("conveyor-01", "CONVEYOR_START") is True
    assert registry.has_capability("conveyor-01", "CONVEYOR_STOP") is True
    assert registry.has_capability("conveyor-01", "SORT_ROUTE") is False
    assert registry.has_capability("unknown-device", "CONVEYOR_START") is False


def test_topic_resolution():
    """Verify MQTT topic template substitution."""
    registry = DeviceRegistry.from_file(EXAMPLE_REGISTRY_PATH)
    topics = registry.get_topics("conveyor-01")

    assert topics is not None
    assert topics["command"] == "smart-factory/conveyor-01/command"
    assert topics["result"] == "smart-factory/conveyor-01/result"
    assert topics["status"] == "smart-factory/conveyor-01/status"
    assert topics["telemetry"] == "smart-factory/conveyor-01/telemetry"


def test_topic_unknown_device():
    """Verify get_topics returns None for unregistered devices."""
    registry = DeviceRegistry.from_file(EXAMPLE_REGISTRY_PATH)
    assert registry.get_topics("ghost-device") is None


def test_list_devices_filtered():
    """Verify filtering device list by device_type."""
    registry = DeviceRegistry.from_file(EXAMPLE_REGISTRY_PATH)

    mega_devices = registry.list_devices(device_type="mega_reference")
    assert len(mega_devices) >= 3
    for dev in mega_devices:
        assert dev.device_type == "mega_reference"

    esp_devices = registry.list_devices(device_type="esp32_bridge")
    assert len(esp_devices) == 1
    assert esp_devices[0].device_id == "bridge-001"

    non_existent = registry.list_devices(device_type="non_existent_type")
    assert non_existent == []


def test_device_id_validation():
    """Verify device_id naming rules per docs/device-registry.md."""
    # Valid IDs
    valid_ids = ["conveyor-01", "bridge_001", "robot1", "a", "line-a-subline-1"]
    for dev_id in valid_ids:
        entry = DeviceEntry(
            device_id=dev_id,
            device_type="simulator",
            firmware_version="1.0",
            capabilities=["TEST"],
            mqtt_topics=MqttTopics(command="c", result="r", status="s"),
            owner=DeviceOwner(team="t", contact="c"),
            registered_at="2026-10-16T00:00:00Z",
        )
        assert entry.device_id == dev_id

    # Invalid IDs (uppercase, ends with hyphen/underscore, starts with digit, too long)
    invalid_ids = [
        "Conveyor-01",
        "conveyor-",
        "conveyor_",
        "1conveyor",
        "-conveyor",
        "_conveyor",
        "conveyor 01",
        "conveyor@01",
        "a" * 65,
    ]
    for bad_id in invalid_ids:
        with pytest.raises(ValidationError):
            DeviceEntry(
                device_id=bad_id,
                device_type="simulator",
                firmware_version="1.0",
                capabilities=["TEST"],
                mqtt_topics=MqttTopics(command="c", result="r", status="s"),
                owner=DeviceOwner(team="t", contact="c"),
                registered_at="2026-10-16T00:00:00Z",
            )


def test_key_mismatch_error():
    """Verify error when dict key does not match device_id in entry."""
    data = {
        "conveyor-01": {
            "device_id": "different-id",
            "device_type": "simulator",
            "firmware_version": "1.0",
            "capabilities": [],
            "mqtt_topics": {"command": "c", "result": "r", "status": "s"},
            "owner": {"team": "t", "contact": "c"},
            "registered_at": "2026-10-16T00:00:00Z",
        }
    }
    with pytest.raises(ValueError, match="does not match entry device_id"):
        DeviceRegistry.from_dict(data)


def test_file_not_found():
    """Verify error on nonexistent file."""
    with pytest.raises(FileNotFoundError):
        DeviceRegistry.from_file("nonexistent_registry.json")


def test_register_and_export():
    """Verify dynamic device registration and to_dict export."""
    registry = DeviceRegistry()
    assert registry.count() == 0

    new_device = DeviceEntry(
        device_id="custom-sensor-01",
        device_type="sensor",
        firmware_version="v0.1.0",
        capabilities=["READ_TEMP", "READ_HUMIDITY"],
        mqtt_topics=MqttTopics(
            command="smart-factory/{device_id}/cmd",
            result="smart-factory/{device_id}/res",
            status="smart-factory/{device_id}/st",
        ),
        physical_location=DeviceLocation(factory_zone="Lab Zone", line="Test Line"),
        owner=DeviceOwner(team="research", contact="research@factory.local"),
        registered_at="2026-10-16T12:00:00Z",
    )
    registry.register_device(new_device)

    assert registry.count() == 1
    assert registry.has_device("custom-sensor-01")
    assert registry.has_capability("custom-sensor-01", "READ_TEMP") is True

    exported = registry.to_dict()
    assert "custom-sensor-01" in exported
    assert exported["custom-sensor-01"]["device_type"] == "sensor"
