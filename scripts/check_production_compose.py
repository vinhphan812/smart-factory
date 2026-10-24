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
import re
import sys
from pathlib import Path
from typing import Any

import yaml

PRODUCTION_PROFILES = {"PRODUCTION", "PRODUCTION_READONLY"}
REQUIRED_VARIABLE = "${"
DEFAULT_MARKERS = (":-", ":+")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
# The broker must be configured by the entrypoint that writes the ACL and
# password files, and it must see the TLS material it is told to trust.
ACL_ENTRYPOINT_MOUNT = "mqtt-broker/entrypoint.d"
TLS_MATERIAL_MOUNT = "mqtt-broker/config/tls"
# Every broker credential the production profiles wire up must come from the
# operator environment. A default (`:-`) or a literal value would let the
# broker start with a credential that is published in the repository.
MQTT_CREDENTIAL_VARIABLES = (
    "MQTT_ADMIN_PASSWORD",
    "MQTT_GW_PASSWORD",
    "MQTT_BRIDGE_PASSWORD",
)
FORBIDDEN_PASSWORD_LITERALS = {"", "changeme", "password", "admin", "mosquitto"}
# Services in a production profile that can command a device and therefore
# must carry a required operator token. `factory-control-readonly` is
# deliberately absent: a read-only deployment has no actuation code path.
ACTUATION_SERVICES = frozenset({"iot-gateway", "factory-control"})


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


def _image_reference(service: dict[str, Any]) -> str:
    return _as_text(service.get("image"))


def _image_digest(image: str) -> str:
    """Return the digest part of an image reference, or an empty string."""
    if "@" not in image:
        return ""
    return image.rsplit("@", 1)[1].strip()


def _is_digest_pinned(image: str) -> bool:
    """True when the image is pinned to an immutable OCI manifest digest."""
    return bool(DIGEST_PATTERN.match(_image_digest(image)))


def _mounts(service: dict[str, Any], fragment: str) -> bool:
    volumes = service.get("volumes", [])
    if not isinstance(volumes, list):
        return False
    return any(fragment in str(volume) for volume in volumes)


def _publishes_plaintext_mqtt_port(port: str) -> bool:
    """True when a Compose port mapping publishes the plaintext MQTT port.

    The container-side port is the second-to-last colon-separated field of a
    ``host:container`` mapping, or the only field for a container-only
    mapping. A host port of 1883 is acceptable only when the container side
    is the TLS port.
    """
    parts = [part for part in str(port).split(":") if part]
    if not parts:
        return False
    container_port = parts[-2] if len(parts) >= 2 else parts[-1]
    return container_port == "1883"


def _repository_relative_mount(mqtt: dict[str, Any], fragment: str) -> str | None:
    """Return the repo-relative host path of the mount containing `fragment`.

    The production broker relies on host bind mounts whose content the guard
    must be able to inspect: the ACL/password generator and the TLS trust
    material are not part of the Compose document.
    """
    for volume in mqtt.get("volumes", []) or []:
        text = str(volume)
        if fragment not in text:
            continue
        host_path = text.split(":", 1)[0].strip()
        if host_path.startswith("./"):
            host_path = host_path[2:]
        elif host_path.startswith("/") or not host_path:
            # An absolute or named-volume path is not inspectable from the
            # repository; it cannot be verified as repository content.
            return None
        return host_path
    return None


def _entrypoint_enforces_acl(script_text: str) -> list[str]:
    """Return the ACL/auth invariants the broker entrypoint must implement."""
    failures: list[str] = []
    if "acl_file" not in script_text:
        failures.append("the broker entrypoint must write an acl_file")
    if "password_file" not in script_text:
        failures.append("the broker entrypoint must write a password_file")
    if "allow_anonymous false" not in script_text:
        failures.append("the broker entrypoint must set allow_anonymous false")
    if "MQTT_TLS_ONLY" not in script_text:
        failures.append("the broker entrypoint must support a TLS-only listener")
    return failures


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


def validate_compose(compose: dict[str, Any], repo_root: Path | None = None) -> list[str]:
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
        # Every broker credential the deployment wires up must be required
        # from the operator environment and must not carry a literal default.
        for variable in MQTT_CREDENTIAL_VARIABLES:
            password = mqtt_env.get(variable)
            if (
                not _is_required_reference(password)
                or _has_default_reference(password)
                or _as_text(password).lower() in FORBIDDEN_PASSWORD_LITERALS
            ):
                errors.append(f"mqtt must require a non-default {variable}")
        mqtt_ports = mqtt.get("ports", [])
        if not isinstance(mqtt_ports, list) or not any("8883:8883" in str(port) for port in mqtt_ports):
            errors.append("mqtt must publish TLS port 8883")
        if any(_publishes_plaintext_mqtt_port(str(port)) for port in mqtt_ports if isinstance(mqtt_ports, list)):
            errors.append("mqtt must not publish a plaintext broker port")
        if _uses_plaintext_broker(mqtt_env) or str(mqtt_env.get("MQTT_TLS_ONLY", "")).lower() not in {"true", "1", "yes"}:
            errors.append("mqtt must enable TLS-only access on port 8883")
        # ACL enforcement is only real if the broker is configured by the
        # entrypoint that writes the ACL and password files, and if it can
        # read the TLS trust material it is told to trust.
        if not _mounts(mqtt, ACL_ENTRYPOINT_MOUNT):
            errors.append("mqtt must mount the broker entrypoint that writes the ACL and password files")
        if not _mounts(mqtt, TLS_MATERIAL_MOUNT):
            errors.append("mqtt must mount the broker TLS trust material")
        # Mounting the entrypoint is not sufficient on its own: the script
        # must actually generate the ACL and password files and refuse
        # anonymous access, otherwise the broker would run with no
        # authorisation boundary despite a compliant-looking Compose file.
        if repo_root is not None:
            entrypoint = _repository_relative_mount(mqtt, ACL_ENTRYPOINT_MOUNT)
            if entrypoint is None:
                errors.append(
                    "mqtt must mount the broker entrypoint from a repository-relative path "
                    "so its ACL enforcement can be verified"
                )
            else:
                script_path = repo_root / entrypoint
                if script_path.is_dir():
                    # The mount exposes the broker entrypoint directory; the
                    # Compose `entrypoint:` key names the script inside it.
                    script_path = script_path / "init.sh"
                if not script_path.is_file():
                    errors.append(f"mqtt broker entrypoint {entrypoint} is missing from the repository")
                else:
                    script_text = script_path.read_text(encoding="utf-8")
                    for failure in _entrypoint_enforces_acl(script_text):
                        errors.append(f"mqtt broker entrypoint {entrypoint} {failure}")
            # The TLS material is operator-supplied and therefore absent from
            # the repository by design. The guard records the expected paths
            # rather than failing, because their absence is correct.
            tls_mount = _repository_relative_mount(mqtt, TLS_MATERIAL_MOUNT)
            if tls_mount is None:
                errors.append(
                    "mqtt must mount the broker TLS trust material from a repository-relative path"
                )

    for name, service in production_services.items():
        environment = _environment(service)
        image = _image_reference(service)
        if not image:
            errors.append(f"{name} must declare an image reference")
        elif not _is_digest_pinned(image):
            errors.append(f"{name} must pin its image by digest, not by a floating tag: {image}")
        if name in ACTUATION_SERVICES:
            token = environment.get("SAFETY_OPERATOR_TOKEN")
            if not _is_required_reference(token) or _has_default_reference(token) or token == "":
                errors.append(f"{name} must require SAFETY_OPERATOR_TOKEN")
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
        errors = validate_compose(load_compose(args.compose_file), repo_root=args.compose_file.resolve().parent)
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
