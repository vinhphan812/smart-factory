"""Authentication and RBAC for the Smart Factory Gateway.

SECURITY REMEDIATION (PR #242 Review):
- JWT_SECRET must be explicitly provisioned; application fails closed when absent
- Hardcoded identities removed from production path; test users isolated via config
- SHA-256 password hashes replaced with PBKDF2-HMAC-SHA256 KDF
- Token storage moved to httpOnly cookies (dashboard responsibility)
- P0 FINDING: Token persistence removed - tokens ONLY in httpOnly cookies, never in response body
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel


# =============================================================================
# Configuration - Fail closed when secrets are not provisioned
# =============================================================================

# Number of PBKDF2 iterations ( OWASP recommended minimum for HMAC-SHA256 )
PBKDF2_ITERATIONS = 600000
SALT_LENGTH = 32

JWT_SECRET: str | None = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Test mode flag - only enable in isolated test configurations
# When True, allows hardcoded test users for unit testing
_TEST_MODE = os.environ.get("AUTH_TEST_MODE", "").lower() in ("1", "true", "yes")

# In-memory user store - ONLY populated in test mode or via explicit provisioning
# Production must provision users via environment variables or external auth
USERS_DB: dict[str, dict[str, Any]] = {}

# Refresh tokens store (token -> user_id)
REFRESH_TOKENS: dict[str, str] = {}

# Role-based permissions
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
    """Ensure JWT_SECRET is provisioned; fail closed if not configured."""
    if JWT_SECRET is None:
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET is not configured. Authentication is unavailable.",
        )
    return JWT_SECRET


def _get_jwt_secret() -> str:
    """Get JWT_SECRET or raise if not configured."""
    secret = _require_jwt_secret()
    if not secret or len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET must be at least 32 characters.",
        )
    return secret


def initialize_test_users() -> None:
    """Initialize isolated test users - ONLY call in test configurations."""
    global USERS_DB
    if not _TEST_MODE:
        return

    # Pre-computed PBKDF2-HMAC-SHA256 hashes for test passwords
    # These are intentionally weak hashes for testing only
    # Format: salt$hash (hex encoded)
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
    """Provision a new user with PBKDF2-HMAC-SHA256 hashed password.

    Args:
        username: Unique username
        password: Plain text password (will be hashed)
        role: User role (operator, supervisor, admin)
        user_id: Unique user identifier
        display_name: Human-readable display name
    """
    password_hash = _hash_password(password)
    USERS_DB[username] = {
        "user_id": user_id,
        "username": username,
        "password_hash": password_hash,
        "role": role,
        "display_name": display_name,
    }


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
    """Internal login result. Carries token material for server-side callers."""

    user: UserResponse
    tokens: TokenResponse


class LoginResponse(BaseModel):
    """Public login response body.

    Deliberately has no ``tokens`` field: session tokens are delivered via
    httpOnly cookies only, so token material never reaches browser JavaScript.
    """

    user: UserResponse


# =============================================================================
# Password Verification - Uses PBKDF2-HMAC-SHA256 KDF
# =============================================================================


def _hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with random salt.

    Returns: hex-encoded string in format "salt:hash"
    """
    salt = secrets.token_bytes(SALT_LENGTH)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{salt.hex()}:{hash_bytes.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against PBKDF2-HMAC-SHA256 hash.

    The stored hash is in format "salt:hash" (hex encoded).
    """
    try:
        # Parse stored hash
        parts = password_hash.split(":")
        if len(parts) != 2:
            return False
        salt_hex, hash_hex = parts

        # Re-compute hash with stored salt
        salt = bytes.fromhex(salt_hex)
        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PBKDF2_ITERATIONS,
        )

        # Use constant-time comparison
        return secrets.compare_digest(computed_hash.hex(), hash_hex)
    except (ValueError, TypeError, AttributeError):
        # Invalid hash format or other error
        return False


# =============================================================================
# Token Management
# =============================================================================


def create_access_token(user_id: str, username: str, role: str) -> tuple[str, int]:
    """Create JWT access token."""
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


def create_refresh_token(user_id: str) -> str:
    """Create refresh token."""
    token = secrets.token_urlsafe(32)
    REFRESH_TOKENS[token] = user_id
    return token


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify JWT token."""
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
    # Fail closed if no users provisioned and not in test mode
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

    # Rotate refresh token (security measure)
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


def get_current_user(
    authorization: str | None = None,
    request: Request = None,
) -> UserResponse:
    """Get current authenticated user from access token.
    
    Supports both:
    - Authorization: Bearer <token> header (for API clients)
    - access_token cookie (for browser cookie-based auth)
    """
    token = None
    
    # First try Authorization header
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    
    # Fall back to cookie
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
    """Dependency factory that enforces a specific permission."""
    def permission_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if required_permission not in current_user.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {required_permission}",
            )
        return current_user
    return permission_checker


# =============================================================================
# Authentication Routes
# =============================================================================


def get_current_user_from_request(request: Request) -> UserResponse:
    """Dependency that gets current user from request (cookie or header).

    Reads the Authorization header directly from the request so that
    non-browser API clients (CLI, service accounts, Unity) can still use
    Bearer tokens. Browsers use the httpOnly cookie path.
    """
    authorization = request.headers.get("Authorization")
    return get_current_user(authorization=authorization, request=request)


def create_auth_routes(app: FastAPI) -> None:
    """Add authentication routes to the FastAPI app."""

    @app.post("/api/auth/login", response_model=LoginResponse)
    async def auth_login(request: LoginRequest, response: Response) -> LoginResponse:
        """Login with username and password.

        SECURITY: Returns tokens ONLY in httpOnly cookies, NOT in response body.
        The response body contains user info only - tokens must be retrieved from cookies.
        """
        result = login(request.username, request.password)

        # Set httpOnly cookies for production use
        # Tokens are ONLY in cookies - NOT returned in response body
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

        # Return user only - tokens are in httpOnly cookies, never in the body.
        # Exposing token material in the JSON body would let any script running
        # in the page (or any XSS) read the session token, which is exactly what
        # the httpOnly cookie is meant to prevent.
        return LoginResponse(user=result.user)

    @app.post("/api/auth/refresh", response_model=dict)
    async def auth_refresh(request: Request, response: Response) -> dict:
        """Refresh access token.
        
        Reads refresh_token from cookie (preferred) or request body.
        Sets new tokens ONLY in httpOnly cookies.
        """
        # Try cookie first, then body
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            # Fall back to body for backwards compatibility
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
        
        result = refresh(refresh_token)

        # Set new tokens in httpOnly cookies ONLY - not in response body
        response.set_cookie(
            key="access_token",
            value=result.access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        response.set_cookie(
            key="refresh_token",
            value=result.refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )

        # Return minimal response - tokens are in cookies only
        return {"status": "refreshed", "expires_in": result.expires_in}

    @app.post("/api/auth/logout")
    async def auth_logout(request: Request, response: Response) -> dict[str, str]:
        """Logout and invalidate refresh token.
        
        Reads refresh_token from cookie if available.
        """
        # Try cookie first, then body
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            # Fall back to body for backwards compatibility
            body = await request.body()
            import json
            try:
                data = json.loads(body)
                refresh_token = data.get("refresh_token")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        
        if refresh_token:
            logout(refresh_token)

        # Clear cookies
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")

        return {"status": "logged_out"}

    @app.get("/api/auth/me", response_model=UserResponse)
    async def auth_me(current_user: UserResponse = Depends(get_current_user_from_request)) -> UserResponse:
        """Get current user info.
        
        Reads access_token from cookie or Authorization header.
        """
        return current_user

    @app.get("/api/auth/status")
    async def auth_status() -> dict[str, Any]:
        """Check authentication service status.

        Returns whether authentication is configured and available.
        """
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


# Initialize test users at module load if in test mode
if _TEST_MODE:
    initialize_test_users()
