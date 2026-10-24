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
    assert "ORION_LD_CORS_ORIGINS" in "\n".join(GUARD.validate_compose(compose, repo_root=ROOT))


def test_rejects_empty_actuation_token() -> None:
    compose = compliant_compose()
    compose["services"]["factory-control"]["environment"]["SAFETY_OPERATOR_TOKEN"] = ""
    assert "SAFETY_OPERATOR_TOKEN" in "\n".join(GUARD.validate_compose(compose, repo_root=ROOT))


def test_rejects_default_mqtt_password() -> None:
    compose = compliant_compose()
    compose["services"]["mqtt"]["environment"]["MQTT_GW_PASSWORD"] = "${MQTT_GW_PASSWORD:-changeme}"
    assert "MQTT_GW_PASSWORD" in "\n".join(GUARD.validate_compose(compose, repo_root=ROOT))


def test_rejects_mqtt_without_tls_only_mode() -> None:
    compose = compliant_compose()
    compose["services"]["mqtt"]["environment"]["MQTT_TLS_ONLY"] = "false"
    assert "mqtt must enable TLS-only access on port 8883" in GUARD.validate_compose(compose, repo_root=ROOT)


def test_rejects_plain_mqtt() -> None:
    compose = compliant_compose()
    compose["services"]["iot-gateway"]["environment"]["MQTT_PORT"] = "1883"
    compose["services"]["iot-gateway"]["environment"]["MQTT_TLS_ENABLED"] = "false"
    assert "iot-gateway must use TLS MQTT on port 8883" in GUARD.validate_compose(compose, repo_root=ROOT)


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
    assert GUARD.validate_compose(compose, repo_root=ROOT) == []


def test_rejects_floating_tag_image() -> None:
    compose = compliant_compose()
    compose["services"]["mongodb"]["image"] = "mongo:4.4"
    assert "mongodb must pin its image by digest" in "\n".join(GUARD.validate_compose(compose, repo_root=ROOT))


def test_rejects_partial_digest_pin() -> None:
    compose = compliant_compose()
    compose["services"]["mongodb"]["image"] = "mongo:4.4@sha256:not-a-real-digest"
    assert "mongodb must pin its image by digest" in "\n".join(GUARD.validate_compose(compose, repo_root=ROOT))


def test_all_production_images_are_digest_pinned() -> None:
    """Every production-profile service image is pinned to an OCI digest."""
    compose = compliant_compose()
    production = GUARD.services_for_profile(compose, "PRODUCTION")
    production.update(GUARD.services_for_profile(compose, "PRODUCTION_READONLY"))
    assert production
    for name, service in production.items():
        image = service.get("image", "")
        assert "@sha256:" in image, f"{name} is not digest pinned: {image}"


def test_rejects_published_plaintext_mqtt_port() -> None:
    compose = compliant_compose()
    compose["services"]["mqtt"]["ports"] = ["${MQTT_TLS_BIND:-127.0.0.1}:8883:8883", "1883:1883"]
    assert "mqtt must not publish a plaintext broker port" in "\n".join(GUARD.validate_compose(compose, repo_root=ROOT))


def test_rejects_mqtt_without_acl_entrypoint_mount() -> None:
    compose = compliant_compose()
    compose["services"]["mqtt"]["volumes"] = [
        volume
        for volume in compose["services"]["mqtt"]["volumes"]
        if "mqtt-broker/entrypoint.d" not in volume
    ]
    assert "mqtt must mount the broker entrypoint" in "\n".join(GUARD.validate_compose(compose, repo_root=ROOT))


def test_rejects_mqtt_without_tls_trust_material() -> None:
    compose = compliant_compose()
    compose["services"]["mqtt"]["volumes"] = [
        volume
        for volume in compose["services"]["mqtt"]["volumes"]
        if "mqtt-broker/config/tls" not in volume
    ]
    assert "mqtt must mount the broker TLS trust material" in "\n".join(GUARD.validate_compose(compose, repo_root=ROOT))


def test_rejects_default_bridge_password() -> None:
    compose = compliant_compose()
    compose["services"]["mqtt"]["environment"]["MQTT_BRIDGE_PASSWORD"] = "${MQTT_BRIDGE_PASSWORD:-changeme}"
    assert "mqtt must require a non-default MQTT_BRIDGE_PASSWORD" in "\n".join(
        GUARD.validate_compose(compose, repo_root=ROOT)
    )


def test_rejects_default_admin_password() -> None:
    compose = compliant_compose()
    compose["services"]["mqtt"]["environment"]["MQTT_ADMIN_PASSWORD"] = "${MQTT_ADMIN_PASSWORD:-admin}"
    assert "mqtt must require a non-default MQTT_ADMIN_PASSWORD" in "\n".join(
        GUARD.validate_compose(compose, repo_root=ROOT)
    )


def test_rejects_literal_mqtt_password() -> None:
    compose = compliant_compose()
    compose["services"]["mqtt"]["environment"]["MQTT_GW_PASSWORD"] = "changeme"
    assert "mqtt must require a non-default MQTT_GW_PASSWORD" in "\n".join(
        GUARD.validate_compose(compose, repo_root=ROOT)
    )


def test_rejects_empty_actuation_token_on_gateway() -> None:
    """The gateway actuates devices, so its operator token must be required."""
    compose = compliant_compose()
    compose["services"]["iot-gateway"]["environment"]["SAFETY_OPERATOR_TOKEN"] = ""
    assert "iot-gateway must require SAFETY_OPERATOR_TOKEN" in "\n".join(
        GUARD.validate_compose(compose, repo_root=ROOT)
    )


def test_rejects_defaulted_actuation_token_on_gateway() -> None:
    compose = compliant_compose()
    compose["services"]["iot-gateway"]["environment"]["SAFETY_OPERATOR_TOKEN"] = (
        "${SAFETY_OPERATOR_TOKEN:-changeme}"
    )
    assert "iot-gateway must require SAFETY_OPERATOR_TOKEN" in "\n".join(
        GUARD.validate_compose(compose, repo_root=ROOT)
    )


def test_readonly_service_is_not_treated_as_actuation_capable() -> None:
    """The read-only control plane legitimately carries an empty token."""
    compose = compliant_compose()
    assert compose["services"]["factory-control-readonly"]["environment"]["SAFETY_OPERATOR_TOKEN"] == ""
    assert "factory-control-readonly" not in GUARD.ACTUATION_SERVICES
    assert GUARD.validate_compose(compose, repo_root=ROOT) == []


def test_rejects_entrypoint_that_does_not_write_an_acl(tmp_path) -> None:
    """A broker entrypoint without an ACL has no authorisation boundary."""
    compose = compliant_compose()
    entrypoint_dir = tmp_path / "infrastructure" / "mqtt-broker" / "entrypoint.d"
    entrypoint_dir.mkdir(parents=True)
    (entrypoint_dir / "init.sh").write_text(
        "#!/bin/sh\n"
        "cat > /mosquitto/config/mosquitto.conf << EOF\n"
        "allow_anonymous false\n"
        "EOF\n",
        encoding="utf-8",
    )
    errors = GUARD.validate_compose(compose, repo_root=tmp_path)
    joined = "\n".join(errors)
    assert "must write an acl_file" in joined
    assert "must write a password_file" in joined


def test_rejects_entrypoint_that_allows_anonymous_access(tmp_path) -> None:
    """`allow_anonymous true` would let any client connect without credentials."""
    compose = compliant_compose()
    entrypoint_dir = tmp_path / "infrastructure" / "mqtt-broker" / "entrypoint.d"
    entrypoint_dir.mkdir(parents=True)
    (entrypoint_dir / "init.sh").write_text(
        "#!/bin/sh\n"
        "cat > /mosquitto/config/mosquitto.conf << EOF\n"
        "allow_anonymous true\n"
        "acl_file /mosquitto/config/acl\n"
        "password_file /mosquitto/config/passwd\n"
        "EOF\n",
        encoding="utf-8",
    )
    errors = GUARD.validate_compose(compose, repo_root=tmp_path)
    assert "must set allow_anonymous false" in "\n".join(errors)


def test_repository_entrypoint_enforces_acl() -> None:
    """The real repository entrypoint implements the ACL invariants."""
    script = ROOT / "infrastructure" / "mqtt-broker" / "entrypoint.d" / "init.sh"
    assert script.is_file()
    assert GUARD._entrypoint_enforces_acl(script.read_text(encoding="utf-8")) == []



