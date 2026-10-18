"""Integration tests for Background Scheduling & Jobs REST API endpoints and Render Cron webhook."""

import uuid
import pytest
from httpx import AsyncClient
from app.core.config import get_settings


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Register and authenticate user to obtain JWT authorization header."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Job Test User",
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
async def test_cron_webhook_authentication(client: AsyncClient):
    """Verify Render Cron webhook enforces shared secret authentication."""
    settings = get_settings()
    secret = settings.cron_secret

    # 1. Missing secret -> 401
    resp = await client.post(
        "/api/v1/jobs/cron",
        json={"job_type": "SCHEDULER_TICK"},
    )
    assert resp.status_code == 401

    # 2. Invalid secret -> 401
    resp = await client.post(
        "/api/v1/jobs/cron",
        headers={"X-Cron-Secret": "invalid-wrong-secret"},
        json={"job_type": "SCHEDULER_TICK"},
    )
    assert resp.status_code == 401

    # 3. Valid X-Cron-Secret header -> 200
    resp = await client.post(
        "/api/v1/jobs/cron",
        headers={"X-Cron-Secret": secret},
        json={
            "job_type": "SCHEDULER_TICK",
            "idempotency_key": f"cron_tick_{uuid.uuid4().hex[:8]}",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["job_type"] == "SCHEDULER_TICK"
    assert data["status"] == "SUCCESS"
    assert data["job_run_id"] is not None

    # 4. Valid Authorization Bearer header -> 200
    resp = await client.post(
        "/api/v1/jobs/cron",
        headers={"Authorization": f"Bearer {secret}"},
        json={
            "job_type": "NIGHTLY_CONSOLIDATION",
            "idempotency_key": f"cron_consolidation_{uuid.uuid4().hex[:8]}",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["job_type"] == "NIGHTLY_CONSOLIDATION"


@pytest.mark.asyncio
async def test_user_job_trigger_flow(client: AsyncClient):
    """Verify user can trigger background jobs for their account and cannot target other users."""
    email = f"job_user_{uuid.uuid4().hex[:8]}@example.com"
    headers = await get_auth_headers(client, email)

    # 1. Trigger job without auth -> 401
    resp = await client.post("/api/v1/jobs/trigger", json={"job_type": "MORNING_BRIEFING"})
    assert resp.status_code == 401

    # 2. Trigger job targeting self -> 200
    idemp = f"user_morning_{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/v1/jobs/trigger",
        headers=headers,
        json={"job_type": "MORNING_BRIEFING", "idempotency_key": idemp},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_type"] == "MORNING_BRIEFING"
    assert data["status"] == "SUCCESS"
    assert data["idempotency_key"] == idemp
    job_run_id = data["id"]

    # 3. Attempting to trigger job targeting another user ID -> 403
    foreign_user_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/jobs/trigger",
        headers=headers,
        json={"job_type": "MORNING_BRIEFING", "target_user_id": foreign_user_id},
    )
    assert resp.status_code == 403
    assert "Cannot trigger background job for another user" in resp.json()["detail"]

    # 4. List runs
    list_resp = await client.get("/api/v1/jobs/runs", headers=headers)
    assert list_resp.status_code == 200
    assert any(r["id"] == job_run_id for r in list_resp.json())

    # 5. Get single run
    get_resp = await client.get(f"/api/v1/jobs/runs/{job_run_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job_run_id

    # 6. Get nonexistent run -> 404
    nonexistent_id = str(uuid.uuid4())
    not_found_resp = await client.get(f"/api/v1/jobs/runs/{nonexistent_id}", headers=headers)
    assert not_found_resp.status_code == 404


@pytest.mark.asyncio
async def test_cron_webhook_invalid_job_type_returns_400(client: AsyncClient):
    """Verify invalid job type on cron webhook returns 400 Bad Request."""
    settings = get_settings()
    secret = settings.cron_secret

    resp = await client.post(
        "/api/v1/jobs/cron",
        headers={"X-Cron-Secret": secret},
        json={"job_type": "UNKNOWN_CRON_JOB"},
    )
    assert resp.status_code == 400
    assert "Invalid job type" in resp.json()["detail"]

