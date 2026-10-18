"""Integration tests for Events, Routines, and Habit REST API endpoints."""

import uuid
import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Helper to register/login a test user and obtain bearer auth headers."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Event User",
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
async def test_unauthenticated_event_endpoints_rejected(client: AsyncClient):
    """Verify that unauthenticated callers cannot access events, routines, occurrences, or habit endpoints."""
    # Events
    resp = await client.get("/api/v1/events")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/events", json={"title": "Test", "local_start": "2026-10-25T10:00:00"})
    assert resp.status_code == 401

    dummy_id = uuid.uuid4()
    resp = await client.post(f"/api/v1/events/{dummy_id}/confirm", json={"notes": "confirmed"})
    assert resp.status_code == 401

    # Routines
    resp = await client.get("/api/v1/routines")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/routines", json={
        "title": "Gym",
        "recurrence_rule": "FREQ=DAILY",
        "dtstart_local": "2026-10-18T07:00:00",
    })
    assert resp.status_code == 401

    # Occurrences
    resp = await client.post(f"/api/v1/occurrences/{dummy_id}/check-in")
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/occurrences/{dummy_id}/confirm", json={"notes": "Done"})
    assert resp.status_code == 401

    # Habit Query
    resp = await client.get("/api/v1/habits/last?habit=fasting")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_events_and_routines_full_api_lifecycle(client: AsyncClient):
    """Verify complete event and habit routine lifecycle over REST endpoints."""
    headers = await get_auth_headers(client, "lifecycle_user@jarvis.ai")

    # 1. Create a planned one-time event
    event_payload = {
        "title": "Dentist Checkup",
        "local_start": "2026-10-26T14:30:00",
        "local_end": "2026-10-26T15:30:00",
        "timezone": "Asia/Kolkata",
        "status": "PLANNED",
    }
    resp = await client.post("/api/v1/events", json=event_payload, headers=headers)
    assert resp.status_code == 201
    event_data = resp.json()
    assert event_data["title"] == "Dentist Checkup"
    assert event_data["status"] == "PLANNED"
    assert event_data["confirmed_at"] is None
    event_id = event_data["id"]

    # 2. List events
    resp = await client.get("/api/v1/events", headers=headers)
    assert resp.status_code == 200
    events_list = resp.json()
    assert len(events_list) == 1
    assert events_list[0]["id"] == event_id

    # 3. Confirm one-time event
    resp = await client.post(
        f"/api/v1/events/{event_id}/confirm",
        json={"notes": "Clean checkup, no cavities"},
        headers=headers,
    )
    assert resp.status_code == 200
    confirmed_event = resp.json()
    assert confirmed_event["status"] == "COMPLETED"
    assert confirmed_event["confirmed_at"] is not None

    # 4. Create recurring routine
    routine_payload = {
        "title": "Intermittent Fasting",
        "recurrence_rule": "FREQ=DAILY",
        "dtstart_local": "2026-10-18T08:00:00",
        "timezone": "Asia/Kolkata",
        "expand_days": 14,
    }
    resp = await client.post("/api/v1/routines", json=routine_payload, headers=headers)
    assert resp.status_code == 201
    routine_data = resp.json()
    routine_id = routine_data["id"]
    assert routine_data["title"] == "Intermittent Fasting"
    assert routine_data["occurrences_count"] >= 14

    # 5. Fetch routine occurrences
    resp = await client.get(f"/api/v1/routines/{routine_id}/occurrences", headers=headers)
    assert resp.status_code == 200
    occs = resp.json()
    assert len(occs) >= 14
    first_occ = occs[0]
    first_occ_id = first_occ["id"]
    assert first_occ["status"] == "PLANNED"
    assert first_occ["confirmation"] is None

    # 6. Record check-in
    resp = await client.post(f"/api/v1/occurrences/{first_occ_id}/check-in", headers=headers)
    assert resp.status_code == 200
    checked_in = resp.json()
    assert checked_in["status"] == "PROMPTED"
    assert checked_in["last_check_in_at"] is not None

    # 7. Confirm occurrence
    resp = await client.post(
        f"/api/v1/occurrences/{first_occ_id}/confirm",
        json={"confirmed_by": "user", "notes": "Completed 18 hour fast"},
        headers=headers,
    )
    assert resp.status_code == 200
    confirmed_occ = resp.json()
    assert confirmed_occ["status"] == "COMPLETED"
    assert confirmed_occ["confirmation"] is not None
    assert confirmed_occ["confirmation"]["confirmed_by"] == "user"

    # 8. Query last habit
    resp = await client.get("/api/v1/habits/last?habit=fasting", headers=headers)
    assert resp.status_code == 200
    habit_data = resp.json()
    assert habit_data["has_confirmed_history"] is True
    assert habit_data["has_active_routine"] is True
    assert "Your last confirmed fasting day was" in habit_data["formatted_message"]


@pytest.mark.asyncio
async def test_cross_user_isolation(client: AsyncClient):
    """Verify that User B cannot access or confirm User A's events and routines."""
    headers_a = await get_auth_headers(client, "event_user_a@jarvis.ai")
    headers_b = await get_auth_headers(client, "event_user_b@jarvis.ai")

    # User A creates an event
    resp_a = await client.post("/api/v1/events", json={
        "title": "Private Medical Consultation",
        "local_start": "2026-10-27T10:00:00",
    }, headers=headers_a)
    event_id = resp_a.json()["id"]

    # User B attempts to read User A's event -> 403 Forbidden
    resp_b_read = await client.get(f"/api/v1/events/{event_id}", headers=headers_b)
    assert resp_b_read.status_code == 403

    # User B attempts to confirm User A's event -> 403 Forbidden
    resp_b_confirm = await client.post(f"/api/v1/events/{event_id}/confirm", json={"notes": "Hacked"}, headers=headers_b)
    assert resp_b_confirm.status_code == 403
