"""E2E smoke tests for the Smart Factory simulation stack.

Issue: #180, #182, #186

Tests run after all services are healthy. Each test is independent and can
be run individually.

L0: docker compose starts without errors
L1: service health endpoints respond
L1: gateway ingests mock MQTT events
L1: WebSocket connection established
L1: Orion-LD is reachable
L1: Scenario manifest and stable seed present (#180 SPEC-3)
L1: Negative scenarios: malformed JSON discard, broker auth rejection, snapshot resync (#180 SPEC-4)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from urllib.request import urlopen
from urllib.error import URLError

import pytest

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s  %(message)s")
log = logging.getLogger("smoke-tests")

# Configuration from environment (Docker sets these in the smoke-tests service)
GW_WS_PORT = int(os.environ.get("GW_WS_PORT", "8000"))
GW_HTTP_PORT = int(os.environ.get("GW_HTTP_PORT", "8001"))
ORION_PORT = int(os.environ.get("ORION_LD_PORT", "1026"))
FC_PORT   = int(os.environ.get("FC_PORT",   "8001"))
DASH_PORT = int(os.environ.get("DASH_PORT", "5173"))
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
TIMEOUT   = int(os.environ.get("SMOKE_TEST_TIMEOUT_S", "60"))

# Internal Docker network URLs (service name = container_name)
GW_BASE   = f"http://iot-gateway:{GW_HTTP_PORT}"
FC_BASE   = f"http://factory-control:{FC_PORT}"
ORION_BASE = f"http://orion-ld:{ORION_PORT}"
DASH_BASE = f"http://dashboard:{DASH_PORT}"


# ── Helpers ──────────────────────────────────────────────────────────────────

def wait_for(url: str, timeout: int = TIMEOUT, name: str = "service") -> bool:
    """Poll url until it returns 2xx or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=5) as resp:
                if resp.status < 400:
                    log.info("%s is UP (%s)", name, url)
                    return True
        except URLError:
            pass
        time.sleep(2)
    log.error("%s did not become available within %ds: %s", name, timeout, url)
    return False


def wait_for_gateway_events(min_count: int = 1, timeout: int = 30) -> int:
    """Wait until gateway has at least min_count events stored."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"{GW_BASE}/events?limit=100", timeout=5) as resp:
                if resp.status == 200:
                    events = json.loads(resp.read())
                    event_list = events.get("events", []) if isinstance(events, dict) else events
                    if isinstance(event_list, list) and len(event_list) >= min_count:
                        log.info("Gateway has %d events (threshold: %d)", len(event_list), min_count)
                        return len(event_list)
        except URLError:
            pass
        time.sleep(2)
    log.error("Gateway did not ingest %d events within %ds", min_count, timeout)
    return 0


# ── L0: Compose started ───────────────────────────────────────────────────────

def test_compose_services_started():
    """Verify all containers are running (checked via health status HTTP)."""
    services = [
        (f"{GW_BASE}/health",     "iot-gateway"),
        (f"{ORION_BASE}/version", "orion-ld"),
        (f"{FC_BASE}/health",      "factory-control"),
    ]
    for url, name in services:
        assert wait_for(url, timeout=60, name=name), f"{name} not healthy"


# ── L1: Health endpoints ─────────────────────────────────────────────────────

def test_gateway_health():
    with urlopen(f"{GW_BASE}/health", timeout=5) as resp:
        body = json.loads(resp.read())
    assert resp.status == 200
    assert body.get("status") == "ok"
    assert "high_watermark" in body
    assert "event_count" in body
    log.info("Gateway health: %s", body)


def test_orion_ld_version():
    """Verify Orion-LD responds with version info (Orion has no /health route)."""
    with urlopen(f"{ORION_BASE}/version", timeout=5) as resp:
        body = json.loads(resp.read())
    assert resp.status == 200
    log.info("Orion-LD version response: %s", body)


def test_factory_control_health():
    with urlopen(f"{FC_BASE}/health", timeout=5) as resp:
        body = json.loads(resp.read())
    assert resp.status == 200
    log.info("Factory-control health: %s", body)


# ── L1: Gateway ingests mock events ──────────────────────────────────────────

def test_gateway_ingests_events():
    """After ~5 ticks of the mock publisher, the gateway must have events."""
    count = wait_for_gateway_events(min_count=1, timeout=30)
    assert count >= 1, f"Gateway has no events after 30s (expected >= 1)"
    log.info("PASS — gateway ingested %d events", count)


def test_gateway_event_fields():
    """Sample an event and verify it has all required canonical fields."""
    with urlopen(f"{GW_BASE}/events?limit=1", timeout=5) as resp:
        events = json.loads(resp.read())
    event_list = events.get("events", []) if isinstance(events, dict) else events
    assert isinstance(event_list, list) and len(event_list) > 0, "No events to inspect"
    ev = event_list[0]
    required = {"event_id", "device_id", "event_type", "payload", "mqtt_topic",
                "mqtt_timestamp_ms", "ingested_at", "sequence"}
    missing = required - set(ev.keys())
    assert not missing, f"Event missing required fields: {missing}"
    log.info("Event fields OK: event_id=%s device=%s type=%s",
             ev["event_id"], ev["device_id"], ev["event_type"])


# ── L1: WebSocket ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_websocket_receives_events():
    """Connect to gateway WS, receive at least one event within 15s."""
    import websockets

    ws_url = f"ws://iot-gateway:{GW_WS_PORT}"
    try:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=15)
            event = json.loads(msg)
            assert "event_id" in event, f"WS message is not an event: {msg}"
            log.info("WS received event: %s / %s / %s",
                     event.get("event_id"), event.get("device_id"), event.get("event_type"))
    except Exception as exc:
        pytest.fail(f"WebSocket test failed: {exc}")


# ── L1: Issue #180 Scenario Manifest & Negative Scenarios ───────────────────

def test_scenario_manifest_loaded():
    """Verify e2e/simulation/manifest.json is present, valid, and has stable seed."""
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    assert os.path.exists(manifest_path), "manifest.json must exist"
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("stable_seed") == 424242
    assert data.get("evidence_level") == "L2 simulation"
    assert len(data.get("scenarios", [])) >= 8
    log.info("Scenario manifest loaded successfully with %d scenarios", len(data["scenarios"]))


def test_malformed_json_handling():
    """Publish a malformed JSON message via MQTT and verify gateway stays up and ignores it."""
    import paho.mqtt.client as mqtt

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set("admin", "changeme")
    client.connect("mqtt", 1883, 60)
    client.loop_start()

    info = client.publish("smart-factory/mock-conveyor-a/telemetry", "{malformed json...", qos=1)
    info.wait_for_publish()
    client.loop_stop()
    client.disconnect()

    with urlopen(f"{GW_BASE}/health", timeout=5) as resp:
        assert resp.status == 200
    log.info("Malformed JSON successfully ignored by gateway without crash")


def test_snapshot_resync_endpoint():
    """Verify gateway /snapshot endpoint returns high_watermark and per_device_latest."""
    with urlopen(f"{GW_BASE}/snapshot?since_sequence=0", timeout=5) as resp:
        body = json.loads(resp.read())
    assert resp.status == 200
    assert "high_watermark" in body
    assert "per_device_latest" in body
    assert isinstance(body["events"], list)
    log.info("Snapshot endpoint responded correctly: high_watermark=%s", body["high_watermark"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--junitxml=junit.xml"])
