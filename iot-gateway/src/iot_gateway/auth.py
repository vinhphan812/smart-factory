"""Authentication and RBAC for the Smart Factory Gateway."""

import secrets
import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Header
from pydantic import BaseModel
import jwt


# Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# In-memory user store (in production, use a proper database)
# Passwords are stored as SHA256 hashes for simplicity
USERS_DB: dict[str, dict[str, Any]] = {
    "operator": {
        "user_id": "op-001",
        "username": "operator",
        "password_hash": hashlib.sha256(b"operator123").hexdigest(),
        "role": "operator",
        "display_name": "Operator User",
    },
    "supervisor": {
        "user_id": "sp-001",
        "username": "supervisor",
        "password_hash": hashlib.sha256(b"supervisor123").hexdigest(),
        "role": "supervisor",
        "display_name": "Supervisor User",
    },
    "admin": {
        "user_id": "ad-001",
        "username": "admin",
        "password_hash": hashlib.sha256(b"admin123").hexdigest(),
        "role": "admin",
        "display_name": "Admin User",
    },
}

# Refresh tokens store (token -> user_id)
REFRESH_TOKENS: dict[str, str] = {}

# Role-based permissions
ROLE_PERMISSIONS = {
    "operator": [
        "dashboard:view",
        "incidents:view",
        "incidents:acknowledge",
        "safety-gate:status",
        "jobs:view",
        "materials:view",
    ],
    "supervisor": [
        "dashboard:view",
        "incidents:view",
        "incidents:acknowledge",
        "incidents:resolve",
        "safety-gate:status",
        "safety-gate:emergency-stop",
        "safety-gate:interlock",
        "safety-gate:override",
        "jobs:view",
        "jobs:create",
        "jobs:cancel",
        "materials:view",
    ],
    "admin": [
        "dashboard:view",
        "incidents:view",
        "incidents:acknowledge",
        "incidents:resolve",
        "safety-gate:status",
        "safety-gate:emergency-stop",
        "safety-gate:interlock",
        "safety-gate:override",
        "jobs:view",
        "jobs:create",
        "jobs:cancel",
        "materials:view",
        "admin:users",
        "admin:settings",
    ],
}


# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    role: str
    display_name: str
    permissions: list[str]


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    return hashlib.sha256(password.encode()).hexdigest() == password_hash


def create_access_token(user_id: str, username: str, role: str) -> tuple[str, int]:
    """Create JWT access token."""
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expires,
        "type": "access",
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, ACCESS_TOKEN_EXPIRE_MINUTES * 60


def create_refresh_token(user_id: str) -> str:
    """Create refresh token."""
    token = secrets.token_urlsafe(32)
    REFRESH_TOKENS[token] = user_id
    return token


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_user_by_username(username: str) -> Optional[dict[str, Any]]:
    """Get user from database."""
    return USERS_DB.get(username)


def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    """Get user by ID."""
    for user in USERS_DB.values():
        if user["user_id"] == user_id:
            return user
    return None


def login(username: str, password: str) -> AuthResponse:
    """Authenticate user and return tokens."""
    user = get_user_by_username(username)

    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    # Create tokens
    access_token, expires_in = create_access_token(
        user["user_id"], user["username"], user["role"]
    )
    refresh_token = create_refresh_token(user["user_id"])

    # Build response
    user_response = UserResponse(
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
        display_name=user["display_name"],
        permissions=ROLE_PERMISSIONS.get(user["role"], []),
    )

    tokens = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )

    return AuthResponse(user=user_response, tokens=tokens)


def refresh(refresh_token: str) -> TokenResponse:
    """Refresh access token."""
    user_id = REFRESH_TOKENS.get(refresh_token)

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )

    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    # Create new tokens
    access_token, expires_in = create_access_token(
        user["user_id"], user["username"], user["role"]
    )

    # Rotate refresh token (optional security measure)
    del REFRESH_TOKENS[refresh_token]
    new_refresh_token = create_refresh_token(user["user_id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=expires_in,
    )


def logout(refresh_token: str) -> None:
    """Invalidate refresh token."""
    REFRESH_TOKENS.pop(refresh_token, None)


def get_current_user(authorization: str = Header(None)) -> UserResponse:
    """Get current authenticated user from access token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = parts[1]
    payload = decode_token(token)

    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return UserResponse(
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
        display_name=user["display_name"],
        permissions=ROLE_PERMISSIONS.get(user["role"], []),
    )


def create_auth_routes(app: FastAPI) -> None:
    """Add authentication routes to the FastAPI app."""

    @app.post("/api/auth/login", response_model=AuthResponse)
    async def auth_login(request: LoginRequest) -> AuthResponse:
        """Login with username and password."""
        return login(request.username, request.password)

    @app.post("/api/auth/refresh", response_model=TokenResponse)
    async def auth_refresh(request: RefreshTokenRequest) -> TokenResponse:
        """Refresh access token."""
        return refresh(request.refresh_token)

    @app.post("/api/auth/logout")
    async def auth_logout(request: LogoutRequest) -> dict[str, str]:
        """Logout and invalidate refresh token."""
        logout(request.refresh_token)
        return {"status": "logged_out"}

    @app.get("/api/auth/me", response_model=UserResponse)
    async def auth_me(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        """Get current user info."""
        return current_user
