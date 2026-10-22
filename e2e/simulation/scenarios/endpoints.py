"""Endpoint and path constants for the Smart Factory E2E scenario suite.

The scenario suite runs on the **host** against the compose stack started
from ``e2e/simulation/docker-compose.e2e.yml``. It needs host-side execution
because three of the negative scenarios inject faults with the ``docker
compose`` CLI, and the compose file uses host-relative bind mounts that the
Docker daemon must resolve on the host.

Consequently the default endpoints are the *published host* ports. Every value
can be overridden through the environment, so the same module works against a
remote runner or a differently mapped port set.

Evidence level: **L2 simulation** — no ESP32, no physical uKit hardware, no
Unity editor. Never HIL (L3/L4) or integrated (L5) evidence.
"""

from __future__ import annotations

import os
import pathlib

#: Repository root. ``conftest.py`` lives in ``<repo>/e2e/simulation/scenarios``
#: so three parents up is the repository root.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
E2E_DIR = REPO_ROOT / "e2e" / "simulation"
COMPOSE_FILE = E2E_DIR / "docker-compose.e2e.yml"
MANIFEST_FILE = E2E_DIR / "manifest.json"

#: Published host endpoints of the compose stack.
GW_HTTP_URL = os.environ.get("E2E_GW_HTTP_URL", "http://localhost:8001")
GW_WS_URL = os.environ.get("E2E_GW_WS_URL", "ws://localhost:8000/ws")
FC_HTTP_URL = os.environ.get("E2E_FC_HTTP_URL", "http://localhost:8002")
ROBOT_HTTP_URL = os.environ.get("E2E_ROBOT_HTTP_URL", "http://localhost:8003")
MQTT_HOST = os.environ.get("E2E_MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("E2E_MQTT_PORT", "1883"))

#: Credentials are read from the environment; the defaults mirror the
#: development-only defaults already shipped in docker-compose.e2e.yml.
MQTT_ADMIN_USERNAME = os.environ.get("MQTT_ADMIN_USERNAME", "admin")
MQTT_ADMIN_PASSWORD = os.environ.get("MQTT_ADMIN_PASSWORD", "changeme")
MQTT_GW_USERNAME = os.environ.get("MQTT_GW_USERNAME", "gateway")
MQTT_GW_PASSWORD = os.environ.get("MQTT_GW_PASSWORD", "changeme")
