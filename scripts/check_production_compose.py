#!/usr/bin/env python
"""Fail closed when production compose security controls are weakened.

The checker is intentionally structural: it validates the committed compose
source without resolving environment variables, so CI can run it without
credentials.  Exit 0 means the file satisfies the deployment invariants;
exit 1 means one or more invariant violations were found; exit 2 is a usage
or YAML parsing error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

PRODUCTION_PROFILES = {"PRODUCTION", "PRODUCTION_READONLY"}
REQUIRED_VARIABLE = "${"
DEFAULT_MARKERS = (":-", ":+")


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _profiles(service: dict[str, Any]) -> set[str]:
    value = service.get("profiles", [])
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def _environment(service: dict[str, Any]) -> dict[str, Any]:
    value = service.get("environment", {})
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return dict(
            item.split("=", 1) if isinstance(item, str) and "=" in item else (item, "")
            for item in value
            if isinstance(item, str)
        )
    return {}


def _is_required_reference(value: Any) -> bool:
    text = _as_text(value)
    return text.startswith(REQUIRED_VARIABLE) and ":?" in text and text.endswith("}")


def _has_default_reference(value: Any) -> bool:
    text = _as_text(value)
    return text.startswith(REQUIRED_VARIABLE) and any(marker in text for marker in DEFAULT_MARKERS)


def _uses_plaintext_broker(environment: dict[str, Any]) -> bool:
    port = str(environment.get("MQTT_PORT", ""))
    tls = str(environment.get("MQTT_TLS_ENABLED", "")).lower()
    return port == "1883" or tls not in {"true", "1", "yes"}


def services_for_profile(compose: dict[str, Any], profile: str) -> dict[str, dict[str, Any]]:
    """Return the Compose services activated by one named profile."""
    services = compose.get("services", {})
    if not isinstance(services, dict):
        return {}
    return {
        name: service
        for name, service in services.items()
        if isinstance(service, dict) and (not _profiles(service) or profile in _profiles(service))
    }


def validate_compose(compose: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    services = compose.get("services")
    if not isinstance(services, dict):
        return ["services must be a mapping"]

    production_services = {
        name: service
        for name, service in services.items()
        if isinstance(service, dict) and _profiles(service) & PRODUCTION_PROFILES
    }
    # Services with no profiles are Compose-default services and therefore
    # participate in each production profile as well.
    production_services.update(
        {
            name: service
            for name, service in services.items()
            if isinstance(service, dict) and not _profiles(service)
        }
    )
    if not production_services:
        return ["no services are assigned to a production profile"]

    orion = services.get("orion-ld")
    if not isinstance(orion, dict):
        errors.append("orion-ld service is required for production")
    else:
        cors = _environment(orion).get("ORION_LD_CORS_ORIGINS")
        if cors == "*" or not _is_required_reference(cors):
            errors.append("orion-ld must require a non-wildcard ORION_LD_CORS_ORIGINS")

    mqtt = services.get("mqtt")
    if not isinstance(mqtt, dict):
        errors.append("mqtt service is required for production")
    else:
        mqtt_env = _environment(mqtt)
        password = mqtt_env.get("MQTT_GW_PASSWORD")
        if not _is_required_reference(password) or _has_default_reference(password) or password in {"", "changeme"}:
            errors.append("mqtt must require a non-default MQTT_GW_PASSWORD")
        mqtt_ports = mqtt.get("ports", [])
        if not isinstance(mqtt_ports, list) or not any("8883:8883" in str(port) for port in mqtt_ports):
            errors.append("mqtt must publish TLS port 8883")
        if _uses_plaintext_broker(mqtt_env) or str(mqtt_env.get("MQTT_TLS_ONLY", "")).lower() not in {"true", "1", "yes"}:
            errors.append("mqtt must enable TLS-only access on port 8883")

    for name, service in production_services.items():
        environment = _environment(service)
        if name == "factory-control":
            token = environment.get("SAFETY_OPERATOR_TOKEN")
            if not _is_required_reference(token) or _has_default_reference(token) or token == "":
                errors.append("factory-control must require SAFETY_OPERATOR_TOKEN")
        if name in {"iot-gateway", "factory-control", "factory-control-readonly", "edge-ai-robot"}:
            if _uses_plaintext_broker(environment):
                errors.append(f"{name} must use TLS MQTT on port 8883")

    readonly = services.get("factory-control-readonly")
    if not isinstance(readonly, dict) or "PRODUCTION_READONLY" not in _profiles(readonly):
        errors.append("factory-control-readonly must be assigned to PRODUCTION_READONLY")
    elif _environment(readonly).get("SAFETY_OPERATOR_TOKEN") != "":
        errors.append("factory-control-readonly must not carry an actuation credential")

    control = services.get("factory-control")
    if isinstance(control, dict) and "PRODUCTION_READONLY" in _profiles(control):
        errors.append("factory-control must be absent from PRODUCTION_READONLY")

    return errors


def load_compose(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError("compose document must be a mapping")
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compose_file", nargs="?", type=Path, default=Path("docker-compose.full.yml"))
    args = parser.parse_args(argv)
    try:
        errors = validate_compose(load_compose(args.compose_file))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {args.compose_file} satisfies production compose security invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
