"""Authentication and session lifecycle tests covering Argon2id, bcrypt, JWT, and rotation."""

import time
from uuid import uuid4
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password, verify_password
from app.models.user import User


def test_argon2id_hashing_and_verification():
    """Verify Argon2id password hashing and constant-time verification."""
    password = "CorrectHorseBatteryStaple123!"
    hashed = hash_password(password, algorithm="argon2id")

    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


def test_bcrypt_fallback_hashing_and_verification():
    """Verify bcrypt fallback password hashing and verification."""
    password = "BcryptFallbackPassword456!"
    hashed = hash_password(password, algorithm="bcrypt")

    assert hashed.startswith(("$2a$", "$2b$", "$2y$"))
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword456!", hashed) is False


def test_invalid_hash_format_handling():
    """Verify that corrupt or unrecognized hash strings return False rather than crashing."""
    assert verify_password("password", "not_a_valid_hash") is False
    assert verify_password("password", "") is False


@pytest.mark.asyncio
async def test_user_registration_and_login_flow(client: AsyncClient):
    """Verify complete registration, login, and profile retrieval flow."""
    reg_payload = {
        "email": "agent@jarvis.ai",
        "password": "SuperSecretPassword123!",
        "display_name": "Tony Stark",
        "timezone": "Asia/Kolkata",
    }
    reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == "agent@jarvis.ai"
    assert user_data["display_name"] == "Tony Stark"

    # Login
    login_payload = {
        "email": "agent@jarvis.ai",
        "password": "SuperSecretPassword123!",
    }
    login_resp = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "Bearer"

    access_token = token_data["access_token"]

    # Access protected /me route
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "agent@jarvis.ai"
    assert me_data["display_name"] == "Tony Stark"


@pytest.mark.asyncio
async def test_login_invalid_password_returns_401(client: AsyncClient):
    """Verify login failure with incorrect credentials returns HTTP 401."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "fail_test@jarvis.ai",
            "password": "ValidPassword123!",
            "display_name": "Tester",
        },
    )

    # Attempt login with wrong password
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "fail_test@jarvis.ai", "password": "WrongPassword123!"},
    )
    assert resp.status_code == 401
    err = resp.json()["error"]
    assert err["code"] == "AUTHENTICATION_FAILED"


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_reuse_prevention(client: AsyncClient):
    """Verify refresh token rotation: old token is invalidated and reuse is rejected."""
    # 1. Register and login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh_test@jarvis.ai",
            "password": "Password123!",
            "display_name": "Refresh Tester",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh_test@jarvis.ai", "password": "Password123!"},
    )
    token_data = login_resp.json()
    original_refresh = token_data["refresh_token"]

    # 2. Rotate refresh token
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh},
    )
    assert refresh_resp.status_code == 200
    rotated_data = refresh_resp.json()
    new_refresh = rotated_data["refresh_token"]
    assert new_refresh != original_refresh

    # 3. Reusing original refresh token MUST be rejected
    reuse_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh},
    )
    assert reuse_resp.status_code == 401
    assert "revoked" in reuse_resp.json()["error"]["message"].lower()

    # 4. New refresh token works cleanly
    valid_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert valid_resp.status_code == 200


@pytest.mark.asyncio
async def test_session_revocation_and_logout(client: AsyncClient):
    """Verify explicit session revocation prevents further access."""
    # Register user first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout_test@jarvis.ai",
            "password": "LogoutPassword123!",
            "display_name": "Logout Tester",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout_test@jarvis.ai", "password": "LogoutPassword123!"},
    )
    token_data = login_resp.json()
    access_token = token_data["access_token"]

    # Call logout
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_resp.status_code == 200

    # Subsequent request using that session's token MUST be rejected
    blocked_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert blocked_resp.status_code == 401
    assert "revoked" in blocked_resp.json()["error"]["message"].lower()
