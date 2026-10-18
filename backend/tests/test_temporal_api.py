"""Tests for Temporal REST endpoints, authentication enforcement, user isolation, and audit."""

from datetime import datetime
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.audit import AuditLog
from app.temporal.timezone import UTC


async def get_auth_headers(client: AsyncClient, email: str = "temporal@jarvis.ai") -> dict:
    """Helper to register and login a test user, returning Bearer auth headers."""
    reg_payload = {
        "email": email,
        "password": "StrongPassword123!",
        "display_name": "Temporal Tester",
        "timezone": "Asia/Kolkata",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_unauthenticated_temporal_endpoints_rejected(client: AsyncClient):
    """Verify that unauthenticated callers are rejected with 401."""
    # /api/v1/temporal/resolve
    res1 = await client.post("/api/v1/temporal/resolve", json={"text": "tomorrow at 2 PM"})
    assert res1.status_code == 401

    # /api/v1/temporal/timezone
    res2 = await client.get("/api/v1/temporal/timezone")
    assert res2.status_code == 401

    # /api/v1/temporal/expand-recurrence
    res3 = await client.post(
        "/api/v1/temporal/expand-recurrence",
        json={
            "routine_id": str(uuid.uuid4()),
            "rrule": "FREQ=DAILY",
            "dtstart_local": "2026-10-19T08:00:00",
        },
    )
    assert res3.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_temporal_resolve_tomorrow_at_2pm(
    client: AsyncClient,
    db_session,
):
    """Verify authenticated user can resolve 'tomorrow at 2 PM' using their Asia/Kolkata timezone."""
    headers = await get_auth_headers(client, "resolve_user@jarvis.ai")

    # Fixed reference time for deterministic testing: Sunday Oct 18, 2026, 04:30:00 UTC
    ref_time = "2026-10-18T04:30:00Z"

    resp = await client.post(
        "/api/v1/temporal/resolve",
        headers=headers,
        json={
            "text": "tomorrow at 2 PM",
            "reference_time_utc": ref_time,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RESOLVED"
    assert data["timezone"] == "Asia/Kolkata"
    assert "2026-10-19T14:00:00+05:30" in data["resolved_local"]
    assert data["resolved_utc"] == "2026-10-19T08:30:00Z"
    assert data["confidence"] == 1.0

    # Verify audit ledger recorded the resolution event
    stmt = select(AuditLog).where(AuditLog.action_type == "temporal.resolve")
    result = await db_session.execute(stmt)
    records = result.scalars().all()
    assert len(records) >= 1
    latest = records[-1]
    assert latest.resource_scope == "temporal"
    assert latest.details["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_authenticated_get_timezone(client: AsyncClient):
    """Verify retrieving authenticated user's timezone information."""
    headers = await get_auth_headers(client, "tz_user@jarvis.ai")

    resp = await client.get("/api/v1/temporal/timezone", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_timezone"] == "Asia/Kolkata"
    assert data["current_utc_offset"] == "+05:30"
    assert data["is_dst"] is False


@pytest.mark.asyncio
async def test_expand_recurrence_api(client: AsyncClient):
    """Verify expanding recurrence rules via REST API."""
    headers = await get_auth_headers(client, "rec_user@jarvis.ai")

    rid = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/temporal/expand-recurrence",
        headers=headers,
        json={
            "routine_id": rid,
            "rule_version": 1,
            "rrule": "FREQ=WEEKLY;BYDAY=MO,FR;COUNT=4",
            "dtstart_local": "2026-10-19T08:00:00",
            "max_occurrences": 10,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 4
    assert len(data["occurrences"]) == 4
    assert data["timezone"] == "Asia/Kolkata"
    assert data["occurrences"][0]["local_time"].startswith("2026-10-19T08:00:00")


@pytest.mark.asyncio
async def test_occurrence_key_api(client: AsyncClient):
    """Verify computing deterministic occurrence key via REST API."""
    headers = await get_auth_headers(client, "occ_user@jarvis.ai")

    rid = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/temporal/occurrence-key?routine_id={rid}&rule_version=1&local_date_time=2026-10-19T08:00:00%2B05:30",
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["occurrence_key"]) == 64
    assert data["routine_id"] == rid


@pytest.mark.asyncio
async def test_validate_timezone_endpoint(client: AsyncClient):
    """Verify public timezone validation endpoint."""
    resp1 = await client.post("/api/v1/temporal/validate-timezone", json={"timezone": "Asia/Kolkata"})
    assert resp1.status_code == 200
    assert resp1.json()["is_valid"] is True
    assert resp1.json()["current_utc_offset"] == "+05:30"

    resp2 = await client.post("/api/v1/temporal/validate-timezone", json={"timezone": "Invalid/Place"})
    assert resp2.status_code == 200
    assert resp2.json()["is_valid"] is False
