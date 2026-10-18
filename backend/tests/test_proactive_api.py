"""Integration tests for Proactive Intelligence REST API endpoints."""

import uuid
import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Helper to register/login a test user and obtain bearer auth headers."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Proactive User",
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
async def test_unauthenticated_proactive_endpoints_rejected(client: AsyncClient):
    """Verify that unauthenticated callers cannot access proactive routes."""
    resp = await client.get("/api/v1/proactive/quiet-hours")
    assert resp.status_code == 401

    resp = await client.get("/api/v1/proactive/briefing/morning")
    assert resp.status_code == 401

    resp = await client.get("/api/v1/proactive/briefing/evening")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/proactive/evaluate")
    assert resp.status_code == 401

    resp = await client.get("/api/v1/proactive/notifications")
    assert resp.status_code == 401

    dummy_id = uuid.uuid4()
    resp = await client.post(f"/api/v1/proactive/notifications/{dummy_id}/dismiss")
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/proactive/notifications/{dummy_id}/read")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_proactive_api_full_lifecycle(client: AsyncClient):
    """Verify complete proactive briefing and notification lifecycle over HTTP."""
    headers = await get_auth_headers(client, "proactive_lifecycle@jarvis.ai")

    # 1. Check quiet hours status
    qh_resp = await client.get("/api/v1/proactive/quiet-hours", headers=headers)
    assert qh_resp.status_code == 200
    qh_data = qh_resp.json()
    assert "is_active" in qh_data
    assert qh_data["timezone"] == "Asia/Kolkata"
    assert qh_data["preferred_address_form"] == "sir"

    # 2. Get morning briefing
    morning_resp = await client.get("/api/v1/proactive/briefing/morning", headers=headers)
    assert morning_resp.status_code == 200
    morning_data = morning_resp.json()
    assert morning_data["briefing_type"] == "MORNING_BRIEFING"
    assert "Good morning" in morning_data["greeting"]
    assert morning_data["notification_id"] is not None

    # 3. Get evening briefing
    evening_resp = await client.get("/api/v1/proactive/briefing/evening", headers=headers)
    assert evening_resp.status_code == 200
    evening_data = evening_resp.json()
    assert evening_data["briefing_type"] == "EVENING_BRIEFING"
    assert "Good evening" in evening_data["greeting"]

    # 4. Trigger evaluate cycle
    eval_resp = await client.post("/api/v1/proactive/evaluate", headers=headers)
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert "notifications_count" in eval_data

    # 5. List notifications
    notif_resp = await client.get("/api/v1/proactive/notifications", headers=headers)
    assert notif_resp.status_code == 200
    notifs = notif_resp.json()
    assert len(notifs) >= 1
    first_notif_id = notifs[0]["id"]

    # 6. Mark notification as read
    read_resp = await client.post(f"/api/v1/proactive/notifications/{first_notif_id}/read", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["status"] == "READ"

    # 7. Dismiss notification
    dismiss_resp = await client.post(f"/api/v1/proactive/notifications/{first_notif_id}/dismiss", headers=headers)
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["status"] == "DISMISSED"


@pytest.mark.asyncio
async def test_cross_user_proactive_isolation(client: AsyncClient):
    """Verify that User B cannot dismiss or access User A's notifications."""
    headers_a = await get_auth_headers(client, "proactive_user_a@jarvis.ai")
    headers_b = await get_auth_headers(client, "proactive_user_b@jarvis.ai")

    # User A triggers morning briefing to create a notification
    resp_a = await client.get("/api/v1/proactive/briefing/morning", headers=headers_a)
    notif_id = resp_a.json()["notification_id"]

    # User B attempts to dismiss User A's notification -> 403 Forbidden
    resp_b_dismiss = await client.post(f"/api/v1/proactive/notifications/{notif_id}/dismiss", headers=headers_b)
    assert resp_b_dismiss.status_code == 403

    # User B attempts to mark User A's notification as read -> 403 Forbidden
    resp_b_read = await client.post(f"/api/v1/proactive/notifications/{notif_id}/read", headers=headers_b)
    assert resp_b_read.status_code == 403
