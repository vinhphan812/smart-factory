"""Regression tests for the production compose security guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_production_compose.py"
SPEC = importlib.util.spec_from_file_location("check_production_compose", SCRIPT)
assert SPEC and SPEC.loader
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)
COMPOSE_PATH = ROOT / "docker-compose.full.yml"


def compliant_compose() -> dict:
    with COMPOSE_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_fixed_production_compose_passes() -> None:
    assert GUARD.validate_compose(compliant_compose()) == []


def test_rejects_wildcard_cors() -> None:
    compose = compliant_compose()
    compose["services"]["orion-ld"]["environment"]["ORION_LD_CORS_ORIGINS"] = "*"
    assert "ORION_LD_CORS_ORIGINS" in "\n".join(GUARD.validate_compose(compose))


def test_rejects_empty_actuation_token() -> None:
    compose = compliant_compose()
    compose["services"]["factory-control"]["environment"]["SAFETY_OPERATOR_TOKEN"] = ""
    assert "SAFETY_OPERATOR_TOKEN" in "\n".join(GUARD.validate_compose(compose))


def test_rejects_default_mqtt_password() -> None:
    compose = compliant_compose()
    compose["services"]["mqtt"]["environment"]["MQTT_GW_PASSWORD"] = "${MQTT_GW_PASSWORD:-changeme}"
    assert "MQTT_GW_PASSWORD" in "\n".join(GUARD.validate_compose(compose))


def test_rejects_mqtt_without_tls_only_mode() -> None:
    compose = compliant_compose()
    compose["services"]["mqtt"]["environment"]["MQTT_TLS_ONLY"] = "false"
    assert "mqtt must enable TLS-only access on port 8883" in GUARD.validate_compose(compose)


def test_rejects_plain_mqtt() -> None:
    compose = compliant_compose()
    compose["services"]["iot-gateway"]["environment"]["MQTT_PORT"] = "1883"
    compose["services"]["iot-gateway"]["environment"]["MQTT_TLS_ENABLED"] = "false"
    assert "iot-gateway must use TLS MQTT on port 8883" in GUARD.validate_compose(compose)


def test_readonly_profile_has_no_actuation_service_or_credential() -> None:
    compose = compliant_compose()
    readonly = compose["services"]["factory-control-readonly"]

    assert readonly["profiles"] == ["PRODUCTION_READONLY"]
    assert readonly["environment"]["SAFETY_OPERATOR_TOKEN"] == ""
    readonly_services = GUARD.services_for_profile(compose, "PRODUCTION_READONLY")
    assert "factory-control" not in readonly_services
    assert "iot-gateway" not in readonly_services
    assert "edge-ai-robot" not in readonly_services
    assert "dashboard" not in readonly_services
    assert all(
        "/command" not in str(value)
        for service in readonly_services.values()
        for value in service.get("environment", {}).values()
    )
    assert all(
        name == "factory-control-readonly" or "SAFETY_OPERATOR_TOKEN" not in service.get("environment", {})
        for name, service in readonly_services.items()
    )
    assert GUARD.validate_compose(compose) == []
