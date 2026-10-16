"""P0 SSRF tests for the alert notification WebhookNotification handler.

Covers fixes for the inverted allowlist check vulnerability:
1. FAIL-CLOSED when SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS is unset/empty.
2. Strict hostname match when allowlist is set (hostname, not netloc).
3. allow_redirects=False (verified by mock call).
4. Hostname normalised (userinfo/port stripped — parsed.hostname vs parsed.netloc).
5. No raw URLs or credentials in log messages.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iot_gateway.alerts import (
    AlertEvent,
    AlertSeverity,
    AlertSource,
    AlertStatus,
    WebhookNotification,
)


def _make_event(alert_id: str = "ssrf-test-001") -> AlertEvent:
    return AlertEvent(
        alert_id=alert_id,
        severity=AlertSeverity.CRITICAL,
        source=AlertSource.SYSTEM,
        message="Test alert",
        status=AlertStatus.PENDING,
    )


def _make_mock_aiohttp(status: int = 200):
    """Build a correctly-structured aiohttp mock."""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_post_result = MagicMock()
    mock_post_result.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_result.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session, mock_post_result


class TestWebhookNotificationSSRF:

    # Fix 1: FAIL-CLOSED

    @pytest.mark.asyncio
    async def test_fail_closed_when_allowlist_unset(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "")
        handler = WebhookNotification(
            url="https://example.com/webhook",
            allowed_hosts=None,
        )
        result = await handler.handle(_make_event())
        assert result is False, "Webhook must be rejected when allowlist is empty"

    @pytest.mark.asyncio
    async def test_fail_closed_when_allowlist_empty_string(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "")
        handler = WebhookNotification(
            url="https://example.com/webhook",
            allowed_hosts=None,
        )
        result = await handler.handle(_make_event())
        assert result is False

    # Fix 2: Strict hostname match

    @pytest.mark.asyncio
    async def test_reject_off_allowlist_host(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "trusted.example.com")
        handler = WebhookNotification(
            url="https://evil.attacker.com/webhook",
            allowed_hosts=None,
        )
        result = await handler.handle(_make_event())
        assert result is False, "Off-allowlist host must be rejected"

    @pytest.mark.asyncio
    async def test_accept_on_allowlist_host(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "allowed.example.com")
        handler = WebhookNotification(
            url="https://allowed.example.com/webhook",
            allowed_hosts=None,
        )
        mock_session, _ = _make_mock_aiohttp(status=200)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await handler.handle(_make_event())
        assert result is True, "On-allowlist host should be accepted"

    # Fix 4: Hostname normalisation

    @pytest.mark.asyncio
    async def test_normalize_strips_userinfo(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "example.com")
        handler = WebhookNotification(
            url="https://user:secret@example.com/hook",
            allowed_hosts=None,
        )
        mock_session, _ = _make_mock_aiohttp(status=200)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await handler.handle(_make_event())
        assert result is True, "Userinfo must be stripped before hostname comparison"

    @pytest.mark.asyncio
    async def test_normalize_strips_port(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "example.com")
        handler = WebhookNotification(
            url="https://example.com:8443/webhook",
            allowed_hosts=None,
        )
        mock_session, _ = _make_mock_aiohttp(status=200)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await handler.handle(_make_event())
        assert result is True, "Port must be stripped before hostname comparison"

    @pytest.mark.asyncio
    async def test_case_insensitive_match(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "example.com")
        handler = WebhookNotification(
            url="https://EXAMPLE.COM/webhook",
            allowed_hosts=None,
        )
        mock_session, _ = _make_mock_aiohttp(status=200)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await handler.handle(_make_event())
        assert result is True, "Matching must be case-insensitive"

    @pytest.mark.asyncio
    async def test_subdomain_not_accepted(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "example.com")
        handler = WebhookNotification(
            url="https://evil.example.com/webhook",
            allowed_hosts=None,
        )
        result = await handler.handle(_make_event())
        assert result is False, "Subdomains must not match unless explicitly allowlisted"

    # Fix 3: allow_redirects=False

    @pytest.mark.asyncio
    async def test_allow_redirects_false(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "example.com")
        handler = WebhookNotification(
            url="https://example.com/webhook",
            allowed_hosts=None,
        )

        captured_kwargs: list[dict] = []
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post_result = MagicMock()
        mock_post_result.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_result.__aexit__ = AsyncMock(return_value=None)

        def capture_post(*args, **kwargs):
            captured_kwargs.append(kwargs)
            return mock_post_result

        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=capture_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            await handler.handle(_make_event())

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0].get("allow_redirects") is False, (
            f"allow_redirects must be False, got {captured_kwargs[0].get('allow_redirects')}"
        )

    # Fix 5: No raw URLs / credentials in logs

    @pytest.mark.asyncio
    async def test_no_raw_url_in_logs_on_reject(self, monkeypatch, caplog):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "allowed.example.com")
        handler = WebhookNotification(
            url="https://example.com/webhook",
            allowed_hosts=None,
        )
        with caplog.at_level(logging.WARNING):
            result = await handler.handle(_make_event("log-check-001"))

        assert result is False
        for record in caplog.records:
            log_text = record.getMessage()
            assert "://" not in log_text, (
                f"Raw URL leaked in log: {log_text}"
            )

    @pytest.mark.asyncio
    async def test_no_credentials_in_logs_on_reject(self, monkeypatch, caplog):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "example.com")
        handler = WebhookNotification(
            url="https://user:secretpass@example.com/hook",
            allowed_hosts=None,
        )
        with caplog.at_level(logging.WARNING):
            result = await handler.handle(_make_event("log-check-002"))

        assert result is False
        for record in caplog.records:
            log_text = record.getMessage()
            assert "secretpass" not in log_text, f"Credentials leaked: {log_text}"
            assert "user:secretpass" not in log_text, f"Userinfo leaked: {log_text}"

    # Per-instance override

    @pytest.mark.asyncio
    async def test_per_instance_allowed_hosts_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "wrong.example.com")
        handler = WebhookNotification(
            url="https://correct.example.com/webhook",
            allowed_hosts=["correct.example.com"],
        )
        mock_session, _ = _make_mock_aiohttp(status=200)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await handler.handle(_make_event())
        assert result is True, "Per-instance allowlist must override module env"

    @pytest.mark.asyncio
    async def test_per_instance_empty_list_is_fail_closed(self, monkeypatch):
        monkeypatch.setenv("SAFETY_ALERT_WEBHOOK_ALLOWED_HOSTS", "example.com")
        handler = WebhookNotification(
            url="https://example.com/webhook",
            allowed_hosts=[],
        )
        result = await handler.handle(_make_event())
        assert result is False, "Empty per-instance list must be fail-closed"
