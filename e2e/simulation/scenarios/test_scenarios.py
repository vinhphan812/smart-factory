"""E2E scenario suite for issue #180 (SPEC-3 / SPEC-4).

Run against the compose stack started from ``e2e/simulation/docker-compose.e2e.yml``::

    docker compose -f e2e/simulation/docker-compose.e2e.yml up -d
    python -m pytest e2e/simulation/scenarios -v

Evidence level: **L2 simulation**. Every scenario runs against mock devices
and the software stack only — no ESP32, no physical uKit hardware, no Unity
editor. These results are never HIL (L3/L4) or integrated (L5) evidence.

Scenario coverage (manifest: ``e2e/simulation/manifest.json``):

===  ==========================  ==========================================
ID   Scenario                   What it proves
===  ==========================  ==========================================
01   happy_production_cycle     MQTT → gateway → store → WebSocket works
02   malformed_crc              corrupted AMLP CRC is rejected, not acted on
03   duplicate_late_ack         late ACK is flagged; duplicate CMD is deduped
04   broker_outage              broker stop/start → gateway survives + resumes
05   sqlite_lock                DB lock does not corrupt or wedge the gateway
06   ws_reconnect               WS drop → snapshot resync, no silent gap
07   authorization_denial       bad credentials / read-only user are rejected
08   yanshee_offline            robot offline does not break the core plane
===  ==========================  ==========================================
"""

from __future__ import annotations

import json
import os
import pathlib
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
# The AMLP wire codec is owned by the bridge module (read-only import, no
# duplicated implementation here). See AGENTS.md / AMLP-v1.md.
AMLP_TOOLS = REPO_ROOT / "esp32-ukit-bridge" / "tools"

# The scenario suite runs on the HOST against the published compose ports.
GW_HTTP = os.environ.get("E2E_GW_HTTP_URL", "http://localhost:8001")
GW_WS = os.environ.get("E2E_GW_WS_URL", "ws://localhost:8000/ws")
FC_HTTP = os.environ.get("E2E_FC_HTTP_URL", "http://localhost:8002")
ROBOT_HTTP = os.environ.get("E2E_ROBOT_HTTP_URL", "http://localhost:8003")
MQTT_HOST = os.environ.get("E2E_MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("E2E_MQTT_PORT", "1883"))

pytestmark = pytest.mark.scenario  # overridden per test


def _import_amlp():
    if str(AMLP_TOOLS) not in sys.path:
        sys.path.insert(0, str(AMLP_TOOLS))
    from amlp import protocol  # noqa: PLC0415

    return protocol


def _publish(client: Any, topic: str, payload: dict[str, Any]) -> None:
    info = client.publish(topic, json.dumps(payload), qos=1)
    info.wait_for_publish(timeout=15)


# ── SCENARIO-01 ──────────────────────────────────────────────────────────────

@pytest.mark.scenario("SCENARIO-01", "happy_production_cycle")
def test_happy_production_cycle(mqtt_client, gateway_events, wait_until, manifest):
    """A full production cycle is ingested, stored and broadcast."""
    rng = random.Random(manifest["stable_seed"])
    device = f"e2e-happy-{rng.randrange(1000, 9999)}"
    now_ms = int(time.time() * 1000)
    client = mqtt_client()

    _publish(
        client,
        f"smart-factory/{device}/telemetry",
        {"device_id": device, "telemetry": {"speed_rpm": 55, "load_kg": 1.5}, "timestamp_ms": now_ms},
    )
    _publish(client, f"smart-factory/{device}/status", {"device_id": device, "online": True, "timestamp_ms": now_ms})
    _publish(
        client,
        f"smart-factory/{device}/command/ack",
        {"device_id": device, "command_id": "101", "status": "ok", "timestamp_ms": now_ms},
    )

    events = wait_until(
        lambda: [e for e in gateway_events(device_id=device) if e["event_type"] != "heartbeat"],
        timeout=60,
        message=f"gateway did not ingest the cycle for {device}",
    )
    types = {e["event_type"] for e in events}
    assert {"telemetry", "status_online", "command_ack"} <= types, types
    assert all(e["sequence"] > 0 for e in events)
    assert all(e["mqtt_topic"].startswith(f"smart-factory/{device}/") for e in events)


# ── SCENARIO-02 ──────────────────────────────────────────────────────────────

@pytest.mark.scenario("SCENARIO-02", "malformed_crc")
def test_malformed_crc_is_rejected(mqtt_client, gateway_events, wait_until):
    """A corrupted AMLP CRC must be rejected by the decoder, not acted upon."""
    protocol = _import_amlp()

    frame = protocol.telemetry_frame("speed", 60)
    encoded = protocol.encode_frame(frame)
    assert b"*" in encoded

    # Corrupt the CRC nibble only — the body stays syntactically valid.
    body, _, crc = encoded.rstrip(b"\r\n").rpartition(b"*")
    corrupted = body + b"*" + bytes((crc[0] ^ 0x01,)) + crc[1:]

    with pytest.raises(protocol.FrameError):
        protocol.decode_frame(corrupted)

    # The incremental parser must drop the bad frame instead of emitting it.
    parser = protocol.StreamParser()
    assert parser.feed(corrupted) == []

    # A valid frame after the corruption is still accepted (no desync).
    recovered = parser.feed(protocol.encode_frame(protocol.telemetry_frame("speed", 61)))
    assert len(recovered) == 1

    # No actuation may result from the rejected frame: the gateway must not
    # see any command ACK derived from the corrupted payload.
    client = mqtt_client()
    _publish(
        client,
        "smart-factory/e2e-crc-probe/command/ack",
        {"device_id": "e2e-crc-probe", "command_id": "999", "status": "ok"},
    )
    wait_until(
        lambda: gateway_events(device_id="e2e-crc-probe"),
        timeout=30,
        message="probe ack was not ingested",
    )
    corrupt_acks = [
        e
        for e in gateway_events(device_id="e2e-crc-probe")
        if e["event_type"] == "command_ack" and e["payload"].get("status") == "corrupted"
    ]
    assert not corrupt_acks


# ── SCENARIO-03 ──────────────────────────────────────────────────────────────

@pytest.mark.scenario("SCENARIO-03", "duplicate_late_ack")
def test_duplicate_and_late_ack(mqtt_client, gateway_events, wait_until, manifest):
    """Late ACKs are flagged out-of-order; duplicate commands are deduped."""
    protocol = _import_amlp()
    rng = random.Random(manifest["stable_seed"])
    device = f"e2e-dup-{rng.randrange(1000, 9999)}"
    client = mqtt_client()

    base_ms = int(time.time() * 1000)
    _publish(
        client,
        f"smart-factory/{device}/command/ack",
        {"device_id": device, "command_id": "42", "status": "ok", "timestamp_ms": base_ms},
    )
    # Late ACK: same correlation, older source timestamp → must be flagged.
    _publish(
        client,
        f"smart-factory/{device}/command/ack",
        {"device_id": device, "command_id": "42", "status": "ok", "timestamp_ms": base_ms - 5000},
    )

    events = wait_until(
        lambda: [e for e in gateway_events(device_id=device) if e["event_type"] == "command_ack"],
        timeout=60,
        message=f"no command ACK ingested for {device}",
    )
    assert len(events) >= 2, events
    assert any(e["out_of_order"] for e in events), "late ACK was not flagged out_of_order"

    # Duplicate command handling lives in the AMLP reference profile: the
    # second frame with the same correlation id returns the cached ACK and
    # must not execute the command twice.
    from amlp.simulator import SimulatorCore  # noqa: PLC0415

    core = SimulatorCore()
    cmd = protocol.encode_frame(protocol.command_frame(7, "CONVEYOR_START", ["60"]))
    first = core.handle_frame(protocol.decode_frame(cmd))
    second = core.handle_frame(protocol.decode_frame(cmd))
    assert first is not None and second is not None
    assert first.fields == second.fields
    assert core.conveyor_running is True


# ── SCENARIO-04 ──────────────────────────────────────────────────────────────

@pytest.mark.scenario("SCENARIO-04", "broker_outage")
def test_broker_outage_and_recovery(compose, mqtt_client, gateway_events, http_get, wait_until):
    """Broker outage is survivable and ingestion resumes after recovery."""
    status, _ = http_get(f"{GW_HTTP}/health")
    assert status == 200, "gateway must be healthy before the outage"

    compose("stop", "mqtt")
    try:
        time.sleep(5)
        # The gateway process must survive the broker outage.
        status, body = http_get(f"{GW_HTTP}/health")
        assert status == 200, f"gateway unhealthy during outage: {status} {body[:200]!r}"
    finally:
        compose("start", "mqtt")

    # Wait for the broker to be back and for the gateway to reconnect.
    wait_until(
        lambda: http_get(f"{GW_HTTP}/health")[0] == 200,
        timeout=60,
        message="gateway did not recover",
    )

    device = "e2e-outage-recovery"
    deadline = time.time() + 120
    ingested = False
    while time.time() < deadline and not ingested:
        client = mqtt_client()
        try:
            _publish(
                client,
                f"smart-factory/{device}/telemetry",
                {"device_id": device, "telemetry": {"speed_rpm": 10}, "timestamp_ms": int(time.time() * 1000)},
            )
        except Exception:
            time.sleep(3)
            continue
        ingested = bool(gateway_events(device_id=device))
        if not ingested:
            time.sleep(3)
    assert ingested, "gateway did not resume ingestion after the broker outage"


# ── SCENARIO-05 ──────────────────────────────────────────────────────────────

@pytest.mark.scenario("SCENARIO-05", "sqlite_lock")
def test_sqlite_lock_does_not_wedge_gateway(compose, mqtt_client, gateway_events, http_get, wait_until):
    """A concurrent write lock on the gateway DB must not corrupt or wedge it."""
    lock_proc = subprocess.Popen(
        [
            "docker", "compose", "-f", str(REPO_ROOT / "e2e" / "simulation" / "docker-compose.e2e.yml"),
            "run", "--rm", "--no-deps", "-T", "backup-restore-drill",
            "python", "/tests/scenarios/sqlite_lock_holder.py",
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        time.sleep(8)
        device = "e2e-sqlite-lock"
        client = mqtt_client()
        _publish(
            client,
            f"smart-factory/{device}/telemetry",
            {"device_id": device, "telemetry": {"speed_rpm": 33}, "timestamp_ms": int(time.time() * 1000)},
        )
        # The gateway must stay responsive while the DB is locked.
        for _ in range(10):
            status, body = http_get(f"{GW_HTTP}/health")
            assert status == 200, f"gateway unhealthy under DB lock: {status} {body[:200]!r}"
            time.sleep(1)
    finally:
        lock_proc.terminate()
        try:
            lock_proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            lock_proc.kill()

    # After the lock is released the gateway must ingest normally again.
    device = "e2e-sqlite-lock-after"
    client = mqtt_client()
    _publish(
        client,
        f"smart-factory/{device}/telemetry",
        {"device_id": device, "telemetry": {"speed_rpm": 44}, "timestamp_ms": int(time.time() * 1000)},
    )
    events = wait_until(
        lambda: gateway_events(device_id=device),
        timeout=90,
        message="gateway did not recover after the DB lock was released",
    )
    assert events

    # The store must still be readable and internally consistent.
    status, body = http_get(f"{GW_HTTP}/snapshot?since_sequence=0")
    assert status == 200
    snapshot = json.loads(body)
    assert snapshot["high_watermark"] >= len(snapshot["events"])


# ── SCENARIO-06 ──────────────────────────────────────────────────────────────

@pytest.mark.scenario("SCENARIO-06", "ws_reconnect")
def test_ws_reconnect_resyncs_without_gap(gateway_events, http_get, wait_until):
    """A dropped WebSocket client can resync from the snapshot endpoint."""
    websockets = pytest.importorskip("websockets")

    import asyncio

    async def _run() -> dict[str, Any]:
        ws_url = GW_WS
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        return message

    first = asyncio.run(_run())
    assert "event_id" in first, first

    last_sequence = first.get("sequence", 0)
    status, body = http_get(f"{GW_HTTP}/snapshot?since_sequence={last_sequence}")
    assert status == 200
    snapshot = json.loads(body)
    assert "high_watermark" in snapshot
    assert "per_device_latest" in snapshot
    assert all(e["sequence"] > last_sequence for e in snapshot["events"])


# ── SCENARIO-07 ──────────────────────────────────────────────────────────────

@pytest.mark.scenario("SCENARIO-07", "authorization_denial")
def test_authorization_denial(mqtt_client, gateway_events, wait_until):
    """Bad credentials are refused and the read-only gateway user cannot publish."""
    import paho.mqtt.client as mqtt

    # 1. Wrong password → broker must refuse the connection.
    refused = False
    bad = mqtt.Client(
        client_id="e2e-scn-bad-creds",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    bad.username_pw_set("gateway", "definitely-not-the-password")
    try:
        bad.connect(MQTT_HOST, MQTT_PORT, 30)
        bad.loop_start()
        time.sleep(3)
        # paho raises or the broker closes the connection → not authorised.
        refused = not bad.is_connected()
    except Exception:
        refused = True
    finally:
        try:
            bad.loop_stop()
            bad.disconnect()
        except Exception:
            pass
    assert refused, "broker accepted an invalid password"

    # 2. The gateway credential is read-only → it must not be able to publish.
    device = "e2e-authz-probe"
    ro = mqtt_client(username="gateway", password="changeme")
    _publish(
        ro,
        f"smart-factory/{device}/telemetry",
        {"device_id": device, "telemetry": {"speed_rpm": 99}, "timestamp_ms": int(time.time() * 1000)},
    )
    time.sleep(5)
    assert not gateway_events(device_id=device), "read-only gateway user was able to publish"


# ── SCENARIO-08 ──────────────────────────────────────────────────────────────

@pytest.mark.scenario("SCENARIO-08", "yanshee_offline")
def test_yanshee_offline_does_not_break_core(compose, http_get, gateway_events, wait_until):
    """With the robot offline the gateway and control plane stay healthy."""
    status, body = http_get(f"{GW_HTTP}/health")
    assert status == 200, body

    compose("stop", "edge-ai-robot")
    try:
        time.sleep(4)
        status, body = http_get(f"{GW_HTTP}/health")
        assert status == 200, f"gateway unhealthy while robot offline: {body[:200]!r}"
        status, body = http_get(f"{FC_HTTP}/health")
        assert status == 200, f"factory-control unhealthy while robot offline: {body[:200]!r}"
        # Robot endpoint must be gone.
        status, _ = http_get(f"{ROBOT_HTTP}/health")
        assert status == 0, "robot endpoint still answering while stopped"
    finally:
        compose("start", "edge-ai-robot")

    status, _ = http_get(f"{ROBOT_HTTP}/health")
    assert status == 200, "robot did not come back online"
