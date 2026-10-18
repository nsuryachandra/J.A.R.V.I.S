"""Integration tests for Vision, Camera, & Screen REST API endpoints and privacy enforcement."""

import uuid
import pytest
from httpx import AsyncClient

# Standard valid 1x1 PNG image base64
VALID_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Register and authenticate user to obtain JWT authorization header."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Vision User",
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
async def test_unauthenticated_vision_endpoints_rejected(client: AsyncClient):
    """Verify all vision endpoints reject unauthenticated requests with 401."""
    dummy_id = str(uuid.uuid4())

    resp = await client.post("/api/v1/vision/sessions", json={"title": "Test"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/vision/sessions")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/vision/sessions/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/vision/sessions/{dummy_id}/toggle", json={"action": "MUTE"})
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/vision/sessions/{dummy_id}/frames", json={"image_base64": VALID_PNG_BASE64})
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/vision/sessions/{dummy_id}/frames")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/vision/analyze", json={"image_base64": VALID_PNG_BASE64})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_vision_session_lifecycle_and_analysis_flow(client: AsyncClient):
    """Verify session creation, frame ingestion, multimodal OCR, and listing."""
    email = f"vision_user_{uuid.uuid4().hex[:8]}@example.com"
    headers = await get_auth_headers(client, email)

    # 1. Create session with valid consent
    create_resp = await client.post(
        "/api/v1/vision/sessions",
        headers=headers,
        json={
            "title": "Camera Workspace Stream",
            "session_type": "CAMERA_STREAM",
            "consent_granted": True,
            "device_info": "HD Webcam",
        },
    )
    assert create_resp.status_code == 200
    session_data = create_resp.json()
    session_id = session_data["id"]
    assert session_data["title"] == "Camera Workspace Stream"
    assert session_data["session_type"] == "CAMERA_STREAM"
    assert session_data["status"] == "ACTIVE"
    assert session_data["privacy_indicator"] is True

    # 2. Get session details
    get_resp = await client.get(f"/api/v1/vision/sessions/{session_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == session_id

    # 3. Analyze frame in session (OCR query)
    frame_resp = await client.post(
        f"/api/v1/vision/sessions/{session_id}/frames",
        headers=headers,
        json={
            "image_base64": VALID_PNG_BASE64,
            "query_prompt": "Please extract OCR text from document",
            "width": 1920,
            "height": 1080,
        },
    )
    assert frame_resp.status_code == 200
    frame_data = frame_resp.json()
    assert frame_data["session_id"] == session_id
    assert frame_data["ocr_text"] is not None
    assert "JARVIS Multimodal OCR Engine" in frame_data["ocr_text"]

    # 4. List frames in session
    frames_list = await client.get(f"/api/v1/vision/sessions/{session_id}/frames", headers=headers)
    assert frames_list.status_code == 200
    assert len(frames_list.json()) == 1

    # 5. Standalone direct analysis
    standalone_resp = await client.post(
        "/api/v1/vision/analyze",
        headers=headers,
        json={
            "image_base64": VALID_PNG_BASE64,
            "query_prompt": "Inspect scene",
        },
    )
    assert standalone_resp.status_code == 200
    assert standalone_resp.json()["analysis_result"] is not None


@pytest.mark.asyncio
async def test_privacy_enforcement_and_tenant_isolation(client: AsyncClient):
    """Verify privacy mute blocks analysis and cross-user sessions are inaccessible."""
    email_a = f"alice_vision_{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"bob_vision_{uuid.uuid4().hex[:8]}@example.com"

    headers_a = await get_auth_headers(client, email_a)
    headers_b = await get_auth_headers(client, email_b)

    # Alice creates a session
    resp_a = await client.post(
        "/api/v1/vision/sessions",
        headers=headers_a,
        json={"title": "Alice Screen Share", "session_type": "SCREEN_SHARE", "consent_granted": True},
    )
    session_id = resp_a.json()["id"]

    # Bob tries to access Alice's session -> must be 404
    bob_get = await client.get(f"/api/v1/vision/sessions/{session_id}", headers=headers_b)
    assert bob_get.status_code == 404

    # Alice mutes the privacy indicator
    mute_resp = await client.post(
        f"/api/v1/vision/sessions/{session_id}/toggle",
        headers=headers_a,
        json={"action": "MUTE"},
    )
    assert mute_resp.status_code == 200
    assert mute_resp.json()["status"] == "MUTED"
    assert mute_resp.json()["privacy_indicator"] is False

    # Frame ingestion while MUTED must return 403 Forbidden
    frame_blocked = await client.post(
        f"/api/v1/vision/sessions/{session_id}/frames",
        headers=headers_a,
        json={"image_base64": VALID_PNG_BASE64},
    )
    assert frame_blocked.status_code == 403
    assert "muted" in frame_blocked.json()["detail"].lower()

    # Rejection of invalid / corrupt image
    corrupt_frame = await client.post(
        "/api/v1/vision/analyze",
        headers=headers_a,
        json={"image_base64": "invalid-base64-content"},
    )
    assert corrupt_frame.status_code == 400
