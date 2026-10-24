"""Deployment configuration for the read-only FIWARE context facade.

Covers Issue #204 / ADR-0017: the facade must be configurable for a
credentialed, TLS-protected Orion-LD deployment, and it must refuse a
partially-specified secure configuration instead of silently downgrading.
"""

from __future__ import annotations

import pytest

from iot_gateway.context_query import ContextQueryConfig


class TestContextQueryConfigEnvironment:
    """Configuration is read from the environment, fail-closed."""

    def test_defaults_are_loopback_read_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in (
            "ORION_LD_URL",
            "ORION_LD_CONTEXT",
            "ORION_LD_CONTEXT_TIMEOUT",
            "ORION_LD_TOKEN",
            "ORION_LD_REQUIRE_TLS",
            "ORION_LD_CA_BUNDLE",
        ):
            monkeypatch.delenv(name, raising=False)
        config = ContextQueryConfig.from_env()
        assert config.base_url == "http://localhost:1026"
        assert config.token is None
        assert config.require_tls is False
        assert config.ca_bundle is None

    def test_token_and_tls_are_read_from_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ORION_LD_TOKEN", "s3cr3t-token")
        monkeypatch.setenv("ORION_LD_REQUIRE_TLS", "1")
        monkeypatch.setenv("ORION_LD_CA_BUNDLE", "/etc/ssl/certs/orion.pem")
        config = ContextQueryConfig.from_env()
        assert config.token == "s3cr3t-token"
        assert config.require_tls is True
        assert config.ca_bundle == "/etc/ssl/certs/orion.pem"

    def test_require_tls_without_ca_bundle_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ORION_LD_REQUIRE_TLS", "1")
        monkeypatch.delenv("ORION_LD_CA_BUNDLE", raising=False)
        with pytest.raises(ValueError, match="ORION_LD_CA_BUNDLE"):
            ContextQueryConfig.from_env()

    def test_non_loopback_host_without_token_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ORION_LD_URL", "https://orion.example.org")
        monkeypatch.delenv("ORION_LD_TOKEN", raising=False)
        with pytest.raises(ValueError, match="ORION_LD_TOKEN"):
            ContextQueryConfig.from_env()

    def test_non_loopback_host_with_token_is_allowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ORION_LD_URL", "https://orion.example.org")
        monkeypatch.setenv("ORION_LD_TOKEN", "s3cr3t-token")
        config = ContextQueryConfig.from_env()
        assert config.base_url == "https://orion.example.org"
        assert config.token == "s3cr3t-token"

    def test_loopback_host_without_token_is_allowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ORION_LD_URL", "http://localhost:1026")
        monkeypatch.delenv("ORION_LD_TOKEN", raising=False)
        config = ContextQueryConfig.from_env()
        assert config.token is None
