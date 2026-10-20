"""Tests for authentication and RBAC."""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
import jwt
import os

# Set test JWT secret before importing
os.environ["JWT_SECRET"] = "test-secret-key"

from iot_gateway import auth
from iot_gateway.auth import (
    USERS_DB,
    ROLE_PERMISSIONS,
    login,
    refresh,
    logout,
    verify_password,
    create_access_token,
    decode_token,
    get_current_user,
    get_user_by_username,
)


class TestPasswordHashing:
    """Tests for password verification."""

    def test_verify_correct_password(self):
        """Correct password verifies successfully."""
        # operator: password is "operator123"
        assert verify_password("operator123", USERS_DB["operator"]["password_hash"]) is True

    def test_verify_incorrect_password(self):
        """Incorrect password fails verification."""
        assert verify_password("wrong", USERS_DB["operator"]["password_hash"]) is False


class TestTokenGeneration:
    """Tests for JWT token generation."""

    def test_create_access_token(self):
        """Access token is created with correct claims."""
        token, expires_in = create_access_token("op-001", "operator", "operator")
        
        assert token is not None
        assert expires_in == 1800  # 30 minutes

    def test_decode_token(self):
        """Token can be decoded correctly."""
        token, _ = create_access_token("op-001", "operator", "operator")
        
        payload = decode_token(token)
        
        assert payload["sub"] == "op-001"
        assert payload["username"] == "operator"
        assert payload["role"] == "operator"

    def test_invalid_token_raises(self):
        """Invalid token raises exception."""
        with pytest.raises(Exception):
            decode_token("invalid-token")


class TestRolePermissions:
    """Tests for role-based permissions."""

    def test_operator_permissions(self):
        """Operator has correct permissions."""
        perms = ROLE_PERMISSIONS["operator"]
        
        assert "dashboard:view" in perms
        assert "incidents:view" in perms
        assert "incidents:acknowledge" in perms
        assert "jobs:view" in perms
        assert "jobs:create" not in perms  # Operator cannot create jobs

    def test_supervisor_permissions(self):
        """Supervisor has correct permissions."""
        perms = ROLE_PERMISSIONS["supervisor"]
        
        assert "dashboard:view" in perms
        assert "incidents:resolve" in perms
        assert "jobs:create" in perms
        assert "safety-gate:emergency-stop" in perms

    def test_admin_permissions(self):
        """Admin has all permissions."""
        perms = ROLE_PERMISSIONS["admin"]
        
        assert "admin:users" in perms
        assert "admin:settings" in perms


class TestLogin:
    """Tests for login functionality."""

    def test_login_success(self):
        """Login succeeds with correct credentials."""
        response = login("operator", "operator123")
        
        assert response.user.username == "operator"
        assert response.user.role == "operator"
        assert response.tokens.access_token is not None
        assert response.tokens.refresh_token is not None

    def test_login_invalid_username(self):
        """Login fails with invalid username."""
        with pytest.raises(Exception) as exc_info:
            login("invalid", "password")
        
        assert "Invalid username or password" in str(exc_info.value)

    def test_login_invalid_password(self):
        """Login fails with invalid password."""
        with pytest.raises(Exception) as exc_info:
            login("operator", "wrongpassword")
        
        assert "Invalid username or password" in str(exc_info.value)

    def test_login_returns_permissions(self):
        """Login returns correct permissions for role."""
        response = login("operator", "operator123")
        
        assert "dashboard:view" in response.user.permissions
        assert "admin:users" not in response.user.permissions


class TestTokenRefresh:
    """Tests for token refresh."""

    def test_refresh_success(self):
        """Token refresh succeeds with valid refresh token."""
        # First login to get tokens
        login_response = login("operator", "operator123")
        
        # Refresh
        refresh_response = refresh(login_response.tokens.refresh_token)
        
        assert refresh_response.access_token is not None
        assert refresh_response.refresh_token is not None

    def test_refresh_invalid_token(self):
        """Token refresh fails with invalid token."""
        with pytest.raises(Exception) as exc_info:
            refresh("invalid-token")
        
        assert "Invalid refresh token" in str(exc_info.value)


class TestLogout:
    """Tests for logout functionality."""

    def test_logout_invalidates_token(self):
        """Logout invalidates the refresh token."""
        login_response = login("operator", "operator123")
        
        # Logout
        logout(login_response.tokens.refresh_token)
        
        # Try to refresh with invalidated token
        with pytest.raises(Exception):
            refresh(login_response.tokens.refresh_token)


class TestAuthRoutes:
    """Tests for auth API routes."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        # Set test secret
        os.environ["JWT_SECRET"] = "test-secret-key"
        
        app = FastAPI()
        auth.create_auth_routes(app)
        
        return TestClient(app)

    def test_login_endpoint(self, client):
        """Login endpoint returns tokens."""
        response = client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "operator123"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]
        assert data["user"]["username"] == "operator"

    def test_login_invalid_credentials(self, client):
        """Login endpoint rejects invalid credentials."""
        response = client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "wrong"},
        )
        
        assert response.status_code == 401

    def test_me_endpoint_without_auth(self, client):
        """Me endpoint requires authentication."""
        response = client.get("/api/auth/me")
        
        assert response.status_code == 401

    def test_me_endpoint_with_auth(self, client):
        """Me endpoint returns user info with valid token."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "operator123"},
        )
        token = login_response.json()["tokens"]["access_token"]
        
        # Get user info
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "operator"
        assert data["role"] == "operator"

    def test_refresh_endpoint(self, client):
        """Refresh endpoint issues new tokens."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "operator123"},
        )
        refresh_token = login_response.json()["tokens"]["refresh_token"]
        
        # Refresh
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_logout_endpoint(self, client):
        """Logout endpoint invalidates token."""
        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "operator123"},
        )
        refresh_token = login_response.json()["tokens"]["refresh_token"]
        
        # Logout
        response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
        )
        
        assert response.status_code == 200
        
        # Try to refresh (should fail)
        refresh_response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
