"""Integration tests for Voice System REST API endpoints."""

import base64
import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Helper to register/login a test user and obtain bearer auth headers."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Voice User",
        "timezone": "Asia/Kolkata",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_unauthenticated_voice_endpoints_rejected(client: AsyncClient):
    """Verify that unauthenticated callers cannot access voice endpoints."""
    resp = await client.get("/api/v1/voice/profiles")
    assert resp.status_code == 401

    resp = await client.get("/api/v1/voice/preferences")
    assert resp.status_code == 401

    resp = await client.put("/api/v1/voice/preferences", json={"speed": 1.1})
    assert resp.status_code == 401

    resp = await client.post("/api/v1/voice/synthesize", json={"text": "Hello"})
    assert resp.status_code == 401

    resp = await client.post("/api/v1/voice/stream", json={"text": "Hello"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/voice/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_voice_profiles_and_preferences_lifecycle(client: AsyncClient):
    """Verify listing profiles and updating voice preferences."""
    headers = await get_auth_headers(client, "voice_prefs@jarvis.ai")

    # 1. List profiles
    prof_resp = await client.get("/api/v1/voice/profiles", headers=headers)
    assert prof_resp.status_code == 200
    profiles = prof_resp.json()
    assert len(profiles) >= 8
    languages = {p["language"] for p in profiles}
    assert "en" in languages
    assert "hi" in languages
    assert "te" in languages

    # 2. Get initial preferences
    pref_resp = await client.get("/api/v1/voice/preferences", headers=headers)
    assert pref_resp.status_code == 200
    pref_data = pref_resp.json()
    assert pref_data["selected_profile_id"] == "indian_english_male"
    assert pref_data["speed"] == 1.0
    assert pref_data["voice_enabled"] is True

    # 3. Update preferences
    update_resp = await client.put(
        "/api/v1/voice/preferences",
        json={"selected_profile_id": "telugu_male", "speed": 1.25, "privacy_mode": True},
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["selected_profile_id"] == "telugu_male"
    assert updated["speed"] == 1.25
    assert updated["privacy_mode"] is True
    assert updated["active_profile"]["language"] == "te"


@pytest.mark.asyncio
async def test_voice_synthesize_endpoint(client: AsyncClient):
    """Verify text-to-speech synthesis endpoint returns base64 audio and metadata."""
    headers = await get_auth_headers(client, "voice_synth@jarvis.ai")

    payload = {
        "text": "Good evening, sir. Your scheduled 16-hour fasting window begins now.",
        "format": "mp3",
    }
    resp = await client.post("/api/v1/voice/synthesize", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["character_count"] == len(payload["text"])
    assert data["duration_seconds"] > 0.5
    assert data["content_type"] == "audio/mpeg"
    assert data["provider"] == "mock"
    assert len(data["audio_base64"]) > 0

    # Ensure valid base64
    raw_audio = base64.b64decode(data["audio_base64"])
    assert len(raw_audio) > 0


@pytest.mark.asyncio
async def test_voice_stream_endpoint(client: AsyncClient):
    """Verify streaming synthesized audio chunks."""
    headers = await get_auth_headers(client, "voice_stream@jarvis.ai")

    payload = {
        "text": "Streaming audio verification for personal assistant feedback.",
        "format": "mp3",
    }
    resp = await client.post("/api/v1/voice/stream", json=payload, headers=headers)
    assert resp.status_code == 200
    assert "audio/mpeg" in resp.headers["content-type"]
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_voice_usage_and_user_isolation(client: AsyncClient):
    """Verify usage metric accumulation and cross-user isolation."""
    headers_a = await get_auth_headers(client, "user_a_voice@jarvis.ai")
    headers_b = await get_auth_headers(client, "user_b_voice@jarvis.ai")

    # User A initiates synthesis
    text_a = "Synthesizing test audio for User A."
    await client.post(
        "/api/v1/voice/synthesize",
        json={"text": text_a},
        headers=headers_a,
    )

    # Check User A usage
    resp_a = await client.get("/api/v1/voice/usage", headers=headers_a)
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["total_requests"] == 1
    assert data_a["total_characters"] == len(text_a)

    # User B usage must be zero
    resp_b = await client.get("/api/v1/voice/usage", headers=headers_b)
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["total_requests"] == 0
    assert data_b["total_characters"] == 0


@pytest.mark.asyncio
async def test_voice_validation_boundaries(client: AsyncClient):
    """Verify negative validation boundaries and bad inputs."""
    headers = await get_auth_headers(client, "voice_validation@jarvis.ai")

    # Empty text
    resp_empty = await client.post(
        "/api/v1/voice/synthesize",
        json={"text": ""},
        headers=headers,
    )
    assert resp_empty.status_code == 422

    # Speed out of range
    resp_speed = await client.post(
        "/api/v1/voice/synthesize",
        json={"text": "Hello", "speed": 5.0},
        headers=headers,
    )
    assert resp_speed.status_code == 422

    # Unknown profile ID
    resp_bad_prof = await client.put(
        "/api/v1/voice/preferences",
        json={"selected_profile_id": "nonexistent_profile_id"},
        headers=headers,
    )
    assert resp_bad_prof.status_code == 400
