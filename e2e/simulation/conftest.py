"""pytest configuration for e2e/smoke-tests."""

import pytest

pytest_plugins = []


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
