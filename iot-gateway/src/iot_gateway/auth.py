"""Authentication and RBAC for the Smart Factory Gateway.

SECURITY REMEDIATION (PR #242 Review):
- JWT_SECRET must be explicitly provisioned; application fails closed when absent
- Hardcoded identities removed from production path; test users isolated via config
- SHA-256 password hashes replaced with PBKDF2-HMAC-SHA256 KDF
- Token storage moved to httpOnly cookies (dashboard responsibility)
- P0 FINDING: Token persistence removed - tokens ONLY in httpOnly cookies, never in response body
- P0 FINDING: Origin/Referer CSRF validation, CORS policy, refresh revocation and rotation
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel


# =============================================================================
# Configuration - Fail closed when secrets are not provisioned
# =============================================================================

PBKDF2_ITERATIONS = 600000
SALT_LENGTH = 32

JWT_SECRET: str | None = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

_TEST_MODE = os.environ.get("AUTH_TEST_MODE", "").lower() in ("1", "true", "yes")

USERS_DB: dict[str, dict[str, Any]] = {}

# Refresh tokens and families store for rotation and server-side revocation
REFRESH_TOKENS: dict[str, str] = {}
REFRESH_TOKEN_RECORDS: dict[str, dict[str, Any]] = {}
REFRESH_FAMILIES: dict[str, set[str]] = {}

ROLE_PERMISSIONS: dict[str, list[str]] = {
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


def _require_jwt_secret() -> str:
    if JWT_SECRET is None:
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET is not configured. Authentication is unavailable.",
        )
    return JWT_SECRET


def _get_jwt_secret() -> str:
    secret = _require_jwt_secret()
    if not secret or len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET must be at least 32 characters.",
        )
    return secret


def initialize_test_users() -> None:
    global USERS_DB
    if not _TEST_MODE:
        return

    test_users = {
        "operator": {
            "user_id": "op-001",
            "username": "operator",
            "password_hash": _hash_password("operator123"),
            "role": "operator",
            "display_name": "Operator User",
        },
        "supervisor": {
            "user_id": "sp-001",
            "username": "supervisor",
            "password_hash": _hash_password("supervisor123"),
            "role": "supervisor",
            "display_name": "Supervisor User",
        },
        "admin": {
            "user_id": "ad-001",
            "username": "admin",
            "password_hash": _hash_password("admin123"),
            "role": "admin",
            "display_name": "Admin User",
        },
    }
    USERS_DB = test_users


def provision_user(
    username: str,
    password: str,
    role: str,
    user_id: str,
    display_name: str,
) -> None:
    password_hash = _hash_password(password)
    USERS_DB[username] = {
        "user_id": user_id,
        "username": username,
        "password_hash": password_hash,
        "role": role,
        "display_name": display_name,
    }


# =============================================================================
# CSRF and Origin / Referer Validation
# =============================================================================

def _extract_origin_from_referer(referer: str) -> str | None:
    if not referer:
        return None
    try:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return None


class CSRFProtectionMiddleware:
    """Server-side Origin/Referer validation for mutating requests relying on cookies."""
    def __init__(self, app: Any, allowed_origins: list[str] | None = None):
        self.app = app
        env_origins = os.environ.get("ALLOWED_ORIGINS")
        if env_origins:
            self.allowed_origins = [o.strip() for o in env_origins.split(",") if o.strip()]
        else:
            self.allowed_origins = allowed_origins or [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]

    async def __call__(self, scope: dict, receive: callable, send: callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            headers = dict(scope.get("headers", []))
            cookie_header = headers.get(b"cookie", b"").decode("latin1", errors="ignore")

            # Check if request relies on cookie authentication
            if "access_token" in cookie_header or "refresh_token" in cookie_header or "session" in cookie_header.lower():
                origin = headers.get(b"origin", b"").decode("latin1", errors="ignore")
                referer = headers.get(b"referer", b"").decode("latin1", errors="ignore")

                client_origin = origin or _extract_origin_from_referer(referer)

                allowed = False
                if client_origin and client_origin in self.allowed_origins:
                    allowed = True

                if not allowed:
                    response = Response(
                        content='{"detail": "CSRF validation failed: missing or disallowed Origin/Referer header"}',
                        status_code=403,
                        media_type="application/json",
                    )
                    await response(scope, receive, send)
                    return

        await self.app(scope, receive, send)


# =============================================================================
# Pydantic Models
# =============================================================================

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


class LoginResponse(BaseModel):
    user: UserResponse


# =============================================================================
# Password Verification
# =============================================================================

def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_LENGTH)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{salt.hex()}:{hash_bytes.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        parts = password_hash.split(":")
        if len(parts) != 2:
            return False
        salt_hex, hash_hex = parts

        salt = bytes.fromhex(salt_hex)
        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PBKDF2_ITERATIONS,
        )

        return secrets.compare_digest(computed_hash.hex(), hash_hex)
    except (ValueError, TypeError, AttributeError):
        return False


# =============================================================================
# Token Management & Revocation
# =============================================================================

def create_access_token(user_id: str, username: str, role: str) -> tuple[str, int]:
    secret = _get_jwt_secret()
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expires,
        "type": "access",
    }
    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    return token, ACCESS_TOKEN_EXPIRE_MINUTES * 60


def create_refresh_token_with_family(user_id: str, family_id: str | None = None) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    fam_id = family_id or secrets.token_hex(16)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    REFRESH_TOKEN_RECORDS[token] = {
        "user_id": user_id,
        "family_id": fam_id,
        "revoked": False,
        "expires_at": expires_at,
    }
    REFRESH_TOKENS[token] = user_id

    if fam_id not in REFRESH_FAMILIES:
        REFRESH_FAMILIES[fam_id] = set()
    REFRESH_FAMILIES[fam_id].add(token)

    return token, fam_id


def create_refresh_token(user_id: str) -> str:
    token, _ = create_refresh_token_with_family(user_id)
    return token


def revoke_refresh_family(family_id: str) -> None:
    if family_id in REFRESH_FAMILIES:
        for t in REFRESH_FAMILIES[family_id]:
            if t in REFRESH_TOKEN_RECORDS:
                REFRESH_TOKEN_RECORDS[t]["revoked"] = True


def decode_token(token: str) -> dict[str, Any]:
    secret = _get_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except (jwt.InvalidTokenError, jwt.DecodeError):
        raise HTTPException(status_code=401, detail="Invalid token")


# =============================================================================
# User Management
# =============================================================================

def get_user_by_username(username: str) -> Optional[dict[str, Any]]:
    return USERS_DB.get(username)


def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    for user in USERS_DB.values():
        if user["user_id"] == user_id:
            return user
    return None


def login(username: str, password: str) -> AuthResponse:
    if not USERS_DB and not _TEST_MODE:
        raise HTTPException(
            status_code=503,
            detail="No users provisioned. Authentication is not configured.",
        )

    user = get_user_by_username(username)

    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    access_token, expires_in = create_access_token(
        user["user_id"], user["username"], user["role"]
    )
    refresh_token = create_refresh_token(user["user_id"])

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
    record = REFRESH_TOKEN_RECORDS.get(refresh_token)
    if not record:
        legacy_user_id = REFRESH_TOKENS.get(refresh_token)
        if legacy_user_id:
            fam_id = secrets.token_hex(16)
            record = {"user_id": legacy_user_id, "family_id": fam_id, "revoked": False}
            REFRESH_TOKEN_RECORDS[refresh_token] = record
        else:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    if record["revoked"]:
        # Reuse detection: revoke entire token family
        revoke_refresh_family(record["family_id"])
        raise HTTPException(status_code=401, detail="Refresh token reuse detected — family revoked")

    user_id = record["user_id"]
    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Rotate token
    record["revoked"] = True

    access_token, expires_in = create_access_token(
        user["user_id"], user["username"], user["role"]
    )
    new_refresh_token, _ = create_refresh_token_with_family(
        user["user_id"], family_id=record["family_id"]
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=expires_in,
    )


def logout(refresh_token: str) -> None:
    record = REFRESH_TOKEN_RECORDS.get(refresh_token)
    if record:
        revoke_refresh_family(record["family_id"])
    REFRESH_TOKENS.pop(refresh_token, None)
    REFRESH_TOKEN_RECORDS.pop(refresh_token, None)


def get_current_user(
    authorization: str | None = None,
    request: Request = None,
) -> UserResponse:
    token = None

    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token and request:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

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


def require_permission(required_permission: str):
    def permission_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if required_permission not in current_user.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {required_permission}",
            )
        return current_user
    return permission_checker


def get_current_user_from_request(request: Request) -> UserResponse:
    authorization = request.headers.get("Authorization")
    return get_current_user(authorization=authorization, request=request)


def create_auth_routes(app: FastAPI) -> None:
    @app.post("/api/auth/login", response_model=LoginResponse)
    async def auth_login(request: LoginRequest, response: Response) -> LoginResponse:
        result = login(request.username, request.password)

        response.set_cookie(
            key="access_token",
            value=result.tokens.access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        response.set_cookie(
            key="refresh_token",
            value=result.tokens.refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )

        return LoginResponse(user=result.user)

    @app.post("/api/auth/refresh", response_model=dict)
    async def auth_refresh(request: Request, response: Response) -> dict:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            body = await request.body()
            import json
            try:
                data = json.loads(body)
                refresh_token = data.get("refresh_token")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        if not refresh_token:
            raise HTTPException(
                status_code=401,
                detail="Refresh token required in cookie or body",
            )

        result_tokens = refresh(refresh_token)

        response.set_cookie(
            key="access_token",
            value=result_tokens.access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        response.set_cookie(
            key="refresh_token",
            value=result_tokens.refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )

        return {"status": "refreshed", "expires_in": result_tokens.expires_in}

    @app.post("/api/auth/logout")
    async def auth_logout(request: Request, response: Response) -> dict[str, str]:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            body = await request.body()
            import json
            try:
                data = json.loads(body)
                refresh_token = data.get("refresh_token")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        if refresh_token:
            logout(refresh_token)

        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")

        return {"status": "logged_out"}

    @app.get("/api/auth/me", response_model=UserResponse)
    async def auth_me(current_user: UserResponse = Depends(get_current_user_from_request)) -> UserResponse:
        return current_user

    @app.get("/api/auth/status")
    async def auth_status() -> dict[str, Any]:
        if JWT_SECRET is None:
            return {
                "available": False,
                "reason": "JWT_SECRET not configured",
                "test_mode": _TEST_MODE,
            }
        if not USERS_DB and not _TEST_MODE:
            return {
                "available": False,
                "reason": "No users provisioned",
                "test_mode": _TEST_MODE,
            }
        return {
            "available": True,
            "test_mode": _TEST_MODE,
        }


if _TEST_MODE:
    initialize_test_users()
