"""Integration tests for Communication & Calls REST API endpoints, approval gates, and isolation."""

import uuid
import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Register and authenticate user to obtain JWT authorization header."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Communication User",
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
async def test_unauthenticated_communication_endpoints_rejected(client: AsyncClient):
    """Verify all communication endpoints reject unauthenticated requests with 401."""
    dummy_id = str(uuid.uuid4())

    resp = await client.post("/api/v1/communication/drafts", json={"channel": "EMAIL", "recipient": "a@b.com", "body": "hi"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/communication/drafts")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/communication/drafts/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/communication/drafts/{dummy_id}/send", json={})
    assert resp.status_code == 401

    resp = await client.post("/api/v1/communication/calls", json={"recipient_phone": "+123", "purpose": "sync"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/communication/calls")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/communication/calls/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/communication/calls/{dummy_id}/initiate", json={})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_message_drafting_and_approval_dispatch_flow(client: AsyncClient):
    """Verify message drafting, 403 approval gate, approval granting, and dispatch."""
    email = f"comm_user_{uuid.uuid4().hex[:8]}@example.com"
    headers = await get_auth_headers(client, email)

    # 1. Create message draft
    draft_resp = await client.post(
        "/api/v1/communication/drafts",
        headers=headers,
        json={
            "channel": "EMAIL",
            "recipient": "investor@venture.com",
            "subject": "Q4 Performance Briefing",
            "body": "Here is our quarterly update on operational scalability.",
        },
    )
    assert draft_resp.status_code == 200
    draft_data = draft_resp.json()
    draft_id = draft_data["id"]
    assert draft_data["status"] == "DRAFT"

    # 2. Attempt send without approval -> 403 Forbidden
    send_blocked = await client.post(
        f"/api/v1/communication/drafts/{draft_id}/send",
        headers=headers,
        json={},
    )
    assert send_blocked.status_code == 403
    assert "approval required" in send_blocked.json()["detail"].lower()

    # 3. Retrieve generated approval request
    approvals_resp = await client.get("/api/v1/approvals", headers=headers)
    assert approvals_resp.status_code == 200
    approvals = approvals_resp.json()
    assert len(approvals) >= 1
    approval_req = next(a for a in approvals if a["tool_name"] == "communication.send_message")
    approval_id = approval_req["id"]

    # 4. Approve request
    approve_resp = await client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers=headers,
        json={"user_note": "Email verified for dispatch."},
    )
    assert approve_resp.status_code == 200

    # 5. Dispatch with approval_id -> 200 OK
    send_success = await client.post(
        f"/api/v1/communication/drafts/{draft_id}/send",
        headers=headers,
        json={"approval_id": approval_id},
    )
    assert send_success.status_code == 200
    assert send_success.json()["status"] == "SENT"


@pytest.mark.asyncio
async def test_telephony_call_and_approval_flow(client: AsyncClient):
    """Verify call planning, 403 approval gate, approval granting, and call completion."""
    email = f"call_user_{uuid.uuid4().hex[:8]}@example.com"
    headers = await get_auth_headers(client, email)

    # 1. Plan call
    call_resp = await client.post(
        "/api/v1/communication/calls",
        headers=headers,
        json={
            "recipient_phone": "+1-555-0844",
            "recipient_name": "Chief Architect",
            "purpose": "Security compliance review",
            "briefing_notes": "Discuss SOC2 audit criteria and policy enforcement.",
            "recording_consent_disclosed": True,
        },
    )
    assert call_resp.status_code == 200
    call_data = call_resp.json()
    call_id = call_data["id"]
    assert call_data["status"] == "PLANNED"

    # 2. Attempt initiate without approval -> 403 Forbidden
    call_blocked = await client.post(
        f"/api/v1/communication/calls/{call_id}/initiate",
        headers=headers,
        json={},
    )
    assert call_blocked.status_code == 403
    assert "approval required" in call_blocked.json()["detail"].lower()

    # 3. Retrieve approval request
    approvals_resp = await client.get("/api/v1/approvals", headers=headers)
    assert approvals_resp.status_code == 200
    approval_req = next(a for a in approvals_resp.json() if a["tool_name"] == "communication.initiate_call")
    approval_id = approval_req["id"]

    # 4. Approve request
    approve_resp = await client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers=headers,
        json={"user_note": "Call authorized."},
    )
    assert approve_resp.status_code == 200

    # 5. Initiate with approval_id -> 200 OK
    init_resp = await client.post(
        f"/api/v1/communication/calls/{call_id}/initiate",
        headers=headers,
        json={"approval_id": approval_id},
    )
    assert init_resp.status_code == 200
    assert init_resp.json()["status"] == "COMPLETED"
    assert init_resp.json()["transcript"] is not None


@pytest.mark.asyncio
async def test_tenant_isolation_on_communication_resources(client: AsyncClient):
    """Verify complete tenant isolation between Alice and Bob for drafts and calls."""
    email_a = f"alice_comm_{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"bob_comm_{uuid.uuid4().hex[:8]}@example.com"

    headers_a = await get_auth_headers(client, email_a)
    headers_b = await get_auth_headers(client, email_b)

    draft_a = (
        await client.post(
            "/api/v1/communication/drafts",
            headers=headers_a,
            json={"channel": "SMS", "recipient": "+1-555-0101", "body": "Alice Secret"},
        )
    ).json()["id"]

    call_a = (
        await client.post(
            "/api/v1/communication/calls",
            headers=headers_a,
            json={"recipient_phone": "+1-555-0102", "purpose": "Alice Private Call"},
        )
    ).json()["id"]

    # Bob attempts access -> 404
    resp_draft = await client.get(f"/api/v1/communication/drafts/{draft_a}", headers=headers_b)
    assert resp_draft.status_code == 404

    resp_call = await client.get(f"/api/v1/communication/calls/{call_a}", headers=headers_b)
    assert resp_call.status_code == 404
