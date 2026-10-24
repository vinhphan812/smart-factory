"""Shared fixtures for the Smart Factory E2E scenario suite (issue #180).

The suite runs on the HOST against the compose stack started from
``e2e/simulation/docker-compose.e2e.yml``:

* traffic enters through the published MQTT port (``1883``),
* assertions read the gateway REST API (``8001``) and WebSocket (``8000``),
* faults are injected with the ``docker compose`` CLI (broker outage, robot
  offline) and with an in-container SQLite write lock (SQLite lock scenario).

Evidence level: **L2 simulation**. No ESP32, no physical uKit hardware and no
Unity editor are required. This is never HIL (L3/L4) or integrated (L5)
evidence — see ``docs/testing-and-acceptance.md``.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any, Callable

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
E2E_DIR = REPO_ROOT / "e2e" / "simulation"
COMPOSE_FILE = E2E_DIR / "docker-compose.e2e.yml"

GW_HTTP_URL = os.environ.get("E2E_GW_HTTP_URL", "http://localhost:8001")
GW_WS_URL = os.environ.get("E2E_GW_WS_URL", "ws://localhost:8000/ws")
FC_HTTP_URL = os.environ.get("E2E_FC_HTTP_URL", "http://localhost:8002")
ROBOT_HTTP_URL = os.environ.get("E2E_ROBOT_HTTP_URL", "http://localhost:8003")
MQTT_HOST = os.environ.get("E2E_MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("E2E_MQTT_PORT", "1883"))

# Credentials are read from the environment; the defaults mirror the
# development-only defaults already shipped in docker-compose.e2e.yml.
MQTT_ADMIN_USERNAME = os.environ.get("MQTT_ADMIN_USERNAME", "admin")
MQTT_ADMIN_PASSWORD = os.environ.get("MQTT_ADMIN_PASSWORD", "changeme")
MQTT_GW_USERNAME = os.environ.get("MQTT_GW_USERNAME", "gateway")
MQTT_GW_PASSWORD = os.environ.get("MQTT_GW_PASSWORD", "changeme")

REPORT_PATH = pathlib.Path(
    os.environ.get("E2E_REPORT_PATH", str(REPO_ROOT / "e2e" / "simulation" / "e2e-report.json"))
)

_RESULTS: list[dict[str, Any]] = []
_TAGS: dict[str, dict[str, Any]] = {}


# ── Report plugin (machine-readable JSON, issue #180 SPEC-5) ─────────────────

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "scenario(id, name): E2E scenario identifier from the scenario manifest"
    )


def pytest_itemcollected(item: pytest.Item) -> None:
    marker = item.get_closest_marker("scenario")
    if marker is not None:
        args = list(marker.args)
        _TAGS[item.nodeid] = {
            "scenario_id": args[0] if args else None,
            "scenario_name": args[1] if len(args) > 1 else None,
            "tags": [m.name for m in item.iter_markers() if m.name != "scenario"],
        }


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when != "call":
        return
    tags = _TAGS.get(report.nodeid, {})
    _RESULTS.append(
        {
            "nodeid": report.nodeid,
            "outcome": report.outcome,
            "duration_s": round(report.duration, 3),
            "scenario_id": tags.get("scenario_id"),
            "scenario_name": tags.get("scenario_name"),
            "tags": tags.get("tags", []),
            "longrepr": None if report.passed else str(report.longrepr),
        }
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    payload = {
        "schema": "smart-factory/e2e-report/v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_level": "L2 simulation",
        "hardware_required": False,
        "target_sha": os.environ.get("TARGET_SHA") or _git_sha(),
        "compose_file": str(COMPOSE_FILE.relative_to(REPO_ROOT)).replace("\\", "/"),
        "endpoints": {
            "gateway_http": GW_HTTP_URL,
            "gateway_ws": GW_WS_URL,
            "factory_control": FC_HTTP_URL,
            "edge_ai_robot": ROBOT_HTTP_URL,
            "mqtt": f"{MQTT_HOST}:{MQTT_PORT}",
        },
        "totals": {
            "tests": len(_RESULTS),
            "passed": sum(1 for r in _RESULTS if r["outcome"] == "passed"),
            "failed": sum(1 for r in _RESULTS if r["outcome"] == "failed"),
        },
        "results": _RESULTS,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def manifest() -> dict[str, Any]:
    """Scenario manifest with the stable seed (issue #180 SPEC-3)."""
    return json.loads((E2E_DIR / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def compose() -> Callable[..., subprocess.CompletedProcess]:
    """Run `docker compose` against the E2E file (fault injection)."""

    def _run(*args: str, check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
        cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), *args]
        return subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=check, timeout=timeout
        )

    return _run


@pytest.fixture(scope="session")
def http_get() -> Callable[[str], tuple[int, bytes]]:
    def _get(url: str, timeout: float = 10.0) -> tuple[int, bytes]:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except (urllib.error.URLError, OSError) as exc:
            return 0, str(exc).encode()

    return _get


@pytest.fixture(scope="session")
def gateway_events(http_get) -> Callable[..., list[dict[str, Any]]]:
    def _events(device_id: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        url = f"{GW_HTTP_URL}/events?limit={limit}"
        if device_id:
            url += f"&device_id={device_id}"
        status, body = http_get(url)
        assert status == 200, f"GET {url} -> {status}: {body[:200]!r}"
        return json.loads(body).get("events", [])

    return _events


@pytest.fixture
def mqtt_client():
    """Factory for connected paho-mqtt clients (auto-cleanup)."""
    import paho.mqtt.client as mqtt

    clients: list[Any] = []

    def _make(
        username: str | None = MQTT_ADMIN_USERNAME,
        password: str | None = MQTT_ADMIN_PASSWORD,
        client_id: str | None = None,
        connect: bool = True,
    ) -> Any:
        cid = client_id or f"e2e-scn-{int(time.time() * 1000) % 10_000_000}"
        client = mqtt.Client(
            client_id=cid, callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        if username:
            client.username_pw_set(username, password)
        if connect:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_start()
        clients.append(client)
        return client

    yield _make

    for client in clients:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:  # pragma: no cover - best effort cleanup
            pass


@pytest.fixture(scope="session")
def wait_until() -> Callable[..., Any]:
    """Poll a predicate until it returns a truthy value or the timeout expires."""

    def _wait(
        predicate: Callable[[], Any],
        timeout: float = 60.0,
        interval: float = 1.0,
        message: str = "condition not met",
    ) -> Any:
        deadline = time.time() + timeout
        last: Any = None
        while time.time() < deadline:
            last = predicate()
            if last:
                return last
            time.sleep(interval)
        raise AssertionError(f"{message} (timeout {timeout}s)")

    return _wait
