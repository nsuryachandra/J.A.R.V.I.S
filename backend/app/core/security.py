"""Cryptographic security utilities for password hashing, JWT tokens, and token hashing."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID
import argon2
import bcrypt
import jwt
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, TokenExpiredError

# Argon2id password hasher instance configured with recommended security parameters
_argon2_hasher = argon2.PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=argon2.Type.ID,
)


def hash_password(plain_password: str, algorithm: str | None = None) -> str:
    """Hash plaintext password using Argon2id or bcrypt according to configuration."""
    algo = algorithm or get_settings().password_hashing_algorithm.lower()

    if algo == "bcrypt":
        salt = bcrypt.gensalt(rounds=12)
        hashed_bytes = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
        return hashed_bytes.decode("utf-8")
    elif algo == "argon2id":
        return _argon2_hasher.hash(plain_password)
    else:
        raise ValueError(f"Unsupported password hashing algorithm: '{algo}'")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored Argon2id or bcrypt hash."""
    if not hashed_password or not plain_password:
        return False

    try:
        if hashed_password.startswith("$argon2"):
            return _argon2_hasher.verify(hashed_password, plain_password)
        elif hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        else:
            return False
    except Exception:
        return False


def create_access_token(
    user_id: UUID,
    session_id: UUID,
    expires_minutes: int | None = None,
) -> str:
    """Create short-lived JWT access token containing only subject, session, and timestamps."""
    settings = get_settings()
    expire_delta = expires_minutes or settings.access_token_expire_minutes
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expire_delta)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "access",
    }

    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a signed JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.app_secret_key,
            algorithms=["HS256"],
            options={"require": ["sub", "sid", "exp", "iat", "type"]},
        )
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Access token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token") from exc


def generate_refresh_token() -> str:
    """Generate high-entropy cryptographically secure refresh token string."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Calculate SHA-256 hash of a token for safe database persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
