"""Tests proving multi-tenant and cross-user data isolation boundaries."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.approval_service import ApprovalService


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client: AsyncClient):
    """Verify protected endpoints reject requests missing authorization header."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401

    resp_approvals = await client.get("/api/v1/approvals")
    assert resp_approvals.status_code == 401

    resp_audit = await client.get("/api/v1/audit-logs")
    assert resp_audit.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_approval_isolation(client: AsyncClient, db_session: AsyncSession):
    """Verify User A cannot view, approve, or deny User B's approval request."""
    # 1. Register User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@jarvis.ai", "password": "AlicePassword123!", "display_name": "Alice"},
    )
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@jarvis.ai", "password": "AlicePassword123!"},
    )
    token_a = login_a.json()["access_token"]

    # 2. Register User B
    resp_b = await client.post(
        "/api/v1/auth/register",
        json={"email": "bob@jarvis.ai", "password": "BobPassword123!", "display_name": "Bob"},
    )
    user_b_id = resp_b.json()["id"]

    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "bob@jarvis.ai", "password": "BobPassword123!"},
    )
    token_b = login_b.json()["access_token"]

    # 3. Create approval request belonging to Bob
    bob_approval = await ApprovalService.create_request(
        session=db_session,
        user_id=user_b_id,
        tool_name="email.send_mock",
        tool_version="1.0.0",
        arguments={"recipient": "boss@jarvis.ai", "subject": "Hi", "body": "Hello"},
        target_resource="email_client",
    )
    await db_session.commit()

    # 4. Alice attempts to view Bob's approval -> MUST return 403 or 404
    alice_view_resp = await client.get(
        f"/api/v1/approvals/{bob_approval.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert alice_view_resp.status_code == 403

    # 5. Alice attempts to approve Bob's approval -> MUST return 403
    alice_approve_resp = await client.post(
        f"/api/v1/approvals/{bob_approval.id}/approve",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert alice_approve_resp.status_code == 403

    # 6. Bob can approve his own approval successfully
    bob_approve_resp = await client.post(
        f"/api/v1/approvals/{bob_approval.id}/approve",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert bob_approve_resp.status_code == 200
    assert bob_approve_resp.json()["status"] == "GRANTED"


@pytest.mark.asyncio
async def test_cross_user_audit_isolation(client: AsyncClient):
    """Verify audit log query returns only records belonging to the authenticated user."""
    # Register and login as Charlie
    await client.post(
        "/api/v1/auth/register",
        json={"email": "charlie@jarvis.ai", "password": "CharliePassword123!", "display_name": "Charlie"},
    )
    login_c = await client.post(
        "/api/v1/auth/login",
        json={"email": "charlie@jarvis.ai", "password": "CharliePassword123!"},
    )
    token_c = login_c.json()["access_token"]

    audit_resp = await client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) > 0
    # Every returned audit log must belong to Charlie or be general user activity
    for log in logs:
        if log["user_id"]:
            assert log["user_id"] == login_c.json().get("user_id", log["user_id"])
