"""Integration tests for Memory REST API endpoints, authentication, user isolation, and audit."""

from datetime import datetime
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.audit import AuditLog


async def get_auth_headers(client: AsyncClient, email: str = "memory_user@jarvis.ai") -> dict:
    """Helper to register and login a test user, returning Bearer auth headers."""
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "display_name": "Memory Tester",
        "timezone": "Asia/Kolkata",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_unauthenticated_memory_endpoints_rejected(client: AsyncClient):
    """Verify that unauthenticated requests to memory endpoints return 401."""
    mid = str(uuid.uuid4())
    res1 = await client.get("/api/v1/memories")
    assert res1.status_code == 401

    res2 = await client.post("/api/v1/memories", json={"content": "secret"})
    assert res2.status_code == 401

    res3 = await client.get(f"/api/v1/memories/{mid}")
    assert res3.status_code == 401

    res4 = await client.post("/api/v1/memories/search", json={"query": "test"})
    assert res4.status_code == 401


@pytest.mark.asyncio
async def test_memory_crud_api_flow(client: AsyncClient, db_session):
    """Verify complete CRUD, confirm, correct, search, and forget flow via API."""
    headers = await get_auth_headers(client, "mem_crud@jarvis.ai")

    # 1. Create a candidate memory
    create_resp = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "User prefers vegetarian meals during travel",
            "memory_type": "PREFERENCE",
            "confidence": 0.8,
            "status": "CANDIDATE",
            "privacy_scope": "PERSONAL",
        },
    )
    assert create_resp.status_code == 201
    mem_data = create_resp.json()
    mem_id = mem_data["id"]
    assert mem_data["content"] == "User prefers vegetarian meals during travel"
    assert mem_data["status"] == "CANDIDATE"

    # 2. Confirm candidate memory
    confirm_resp = await client.post(
        f"/api/v1/memories/{mem_id}/confirm",
        headers=headers,
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "ACTIVE"
    assert confirm_resp.json()["confirmed_by_user"] is True

    # 3. List memories
    list_resp = await client.get("/api/v1/memories", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["id"] == mem_id for item in items)

    # 4. Search memories semantically
    search_resp = await client.post(
        "/api/v1/memories/search",
        headers=headers,
        json={"query": "vegetarian food while traveling"},
    )
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) >= 1
    assert results[0]["memory"]["id"] == mem_id
    assert results[0]["score"] > 0.2

    # 5. Correct memory (supersedes old memory)
    correct_resp = await client.post(
        f"/api/v1/memories/{mem_id}/correct",
        headers=headers,
        json={
            "corrected_content": "User prefers strictly vegan meals during travel",
            "reason": "User transitioned from vegetarian to vegan diet",
        },
    )
    assert correct_resp.status_code == 200
    new_mem = correct_resp.json()
    assert new_mem["content"] == "User prefers strictly vegan meals during travel"
    assert new_mem["status"] == "ACTIVE"

    # 6. Forget memory (Right to be Forgotten)
    forget_resp = await client.delete(
        f"/api/v1/memories/{new_mem['id']}",
        headers=headers,
    )
    assert forget_resp.status_code == 204

    # 7. Verify audit ledger captured memory operations
    stmt = select(AuditLog).where(AuditLog.action_type.like("memory.%"))
    audit_res = await db_session.execute(stmt)
    audit_records = audit_res.scalars().all()
    actions = [r.action_type for r in audit_records]
    assert "memory.create" in actions
    assert "memory.confirm" in actions
    assert "memory.correct" in actions
    assert "memory.forget" in actions


@pytest.mark.asyncio
async def test_cross_user_memory_api_isolation(client: AsyncClient):
    """Verify that User B cannot view or modify User A's memories via API."""
    headers_a = await get_auth_headers(client, "user_a@jarvis.ai")
    headers_b = await get_auth_headers(client, "user_b@jarvis.ai")

    # User A creates a memory
    create_resp = await client.post(
        "/api/v1/memories",
        headers=headers_a,
        json={"content": "Top secret plan for User A"},
    )
    mem_id = create_resp.json()["id"]

    # User B tries to get User A's memory -> 403 Forbidden
    get_resp = await client.get(f"/api/v1/memories/{mem_id}", headers=headers_b)
    assert get_resp.status_code == 403

    # User B tries to update User A's memory -> 403 Forbidden
    patch_resp = await client.patch(
        f"/api/v1/memories/{mem_id}",
        headers=headers_b,
        json={"content": "Hacked content"},
    )
    assert patch_resp.status_code == 403

    # User B tries to delete User A's memory -> 403 Forbidden
    del_resp = await client.delete(f"/api/v1/memories/{mem_id}", headers=headers_b)
    assert del_resp.status_code == 403
