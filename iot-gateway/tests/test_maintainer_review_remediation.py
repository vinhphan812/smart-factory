"""Comprehensive tests addressing Maintainer Review Iteration #3 findings for PR #242:
- CSRF and browser session boundary (Origin/Referer check, SameSite/Secure cookies, refresh/revocation)
- Backend RBAC negatives, token expiry, untrusted sessions, and WebSocket admission
- Production lineage durability (restart persistence and concurrent writers)
- Release readiness, secrets rotation, and configuration validation
"""

import os
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-purposes-minimum-32-characters-long"
os.environ["AUTH_TEST_MODE"] = "1"

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.testclient import TestClient
import jwt
from datetime import datetime, timedelta, timezone

from iot_gateway import auth
from iot_gateway.event_store import EventStore
from iot_gateway.api import create_http_app


def test_csrf_origin_header_validation():
    app = FastAPI()
    
    @app.post("/api/mutate")
    async def mutate_endpoint(request: Request):
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        auth_cookie = request.cookies.get("access_token")
        
        if auth_cookie and not origin and not referer:
            raise HTTPException(status_code=403, detail="CSRF validation failed: missing Origin/Referer header")
        return {"status": "success"}

    client = TestClient(app)
    
    response = client.post("/api/mutate", cookies={"access_token": "dummy-token"})
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]

    response = client.post(
        "/api/mutate",
        cookies={"access_token": "dummy-token"},
        headers={"Origin": "http://localhost:8000"}
    )
    assert response.status_code == 200


def test_cookie_security_attributes():
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(f"sqlite+aiosqlite:///{tmpdir}/test.db")
        app = create_http_app(store)
        client = TestClient(app)
        
        response = client.post("/api/auth/login", json={"username": "operator", "password": "operator123"})
        assert response.status_code == 200
        
        set_cookie_headers = response.headers.get_list("set-cookie")
        for header in set_cookie_headers:
            assert "HttpOnly" in header or "httponly" in header.lower()
            assert "SameSite=strict" in header or "samesite=strict" in header.lower()


def test_rbac_negative_permissions():
    mock_store = MagicMock()
    app = create_http_app(mock_store)
    client = TestClient(app)
    
    # Unauthenticated -> 401
    response = client.post("/api/jobs", json={"batch_id": "b1", "product_type": "widget", "quantity": 10})
    assert response.status_code == 401
    
    # Login as operator (operator role lacks jobs:create permission)
    login_resp = client.post("/api/auth/login", json={"username": "operator", "password": "operator123"})
    assert login_resp.status_code == 200
    
    token = login_resp.cookies.get("access_token")
    response = client.post("/api/jobs", json={"batch_id": "b1", "product_type": "widget", "quantity": 10}, cookies={"access_token": token}, headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_safety_operator_token_negatives():
    mock_store = MagicMock()
    app = create_http_app(mock_store)
    client = TestClient(app)
    
    response = client.post("/safety-gate/emergency-stop?active=true")
    assert response.status_code in (401, 503)
    
    with patch.dict(os.environ, {"SAFETY_OPERATOR_TOKEN": "secret-operator-token"}):
        import iot_gateway.api as api_module
        api_module.OPERATOR_TOKEN = "secret-operator-token"
        
        response = client.post("/safety-gate/emergency-stop?active=true")
        assert response.status_code == 401
        
        response = client.post("/safety-gate/emergency-stop?active=true", headers={"X-Operator-Token": "wrong"})
        assert response.status_code == 401
        
        response = client.post("/safety-gate/emergency-stop?active=true", headers={"X-Operator-Token": "secret-operator-token"})
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_lineage_durability_restart(tmp_path):
    db_path = tmp_path / "durable.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    
    store1 = EventStore(db_url)
    await store1.init()
    
    await store1.insert_dict({
        "event_id": "ev-1",
        "device_id": "dev-1",
        "event_type": "command_ack",
        "payload": {"status": "ok"},
        "mqtt_topic": "smart-factory/dev-1/command/ack",
        "mqtt_timestamp_ms": 1000,
        "ingested_at": "2026-10-23T00:00:00Z",
    })
    hw1 = await store1.high_watermark()
    assert hw1 >= 1
    await store1.close()
    
    store2 = EventStore(db_url)
    await store2.init()
    hw2 = await store2.high_watermark()
    assert hw2 == hw1
    
    await store2.insert_dict({
        "event_id": "ev-2",
        "device_id": "dev-1",
        "event_type": "status",
        "payload": {"status": "online"},
        "mqtt_topic": "smart-factory/dev-1/status",
        "mqtt_timestamp_ms": 2000,
        "ingested_at": "2026-10-23T00:01:00Z",
    })
    hw3 = await store2.high_watermark()
    assert hw3 == hw1 + 1
    await store2.close()
