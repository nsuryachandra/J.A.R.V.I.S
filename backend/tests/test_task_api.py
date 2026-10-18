"""Integration tests for Task & Project REST endpoints, authentication enforcement, and cross-user isolation."""

import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token
from app.models.user import User


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Helper to register/login a test user and obtain bearer auth headers."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Test User",
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
async def test_unauthenticated_task_endpoints_rejected(client: AsyncClient):
    """Verify that unauthenticated callers cannot access task or project routes."""
    # Project endpoints
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/projects", json={"title": "Hacked"})
    assert resp.status_code == 401

    # Task endpoints
    resp = await client.get("/api/v1/tasks")
    assert resp.status_code == 401

    resp = await client.get("/api/v1/tasks/pending")
    assert resp.status_code == 401

    dummy_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/tasks/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/tasks/{dummy_id}/complete", json={
        "evidence_type": "USER_CONFIRMATION",
        "description": "Done",
        "verified_by": "user",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_task_and_project_api_crud_flow(client: AsyncClient):
    """Verify complete project and task lifecycle over HTTP REST API."""
    headers = await get_auth_headers(client, "task_user@jarvis.ai")

    # 1. Create a project
    proj_resp = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": "Autonomous Coding Agent",
            "description": "Multi-agent tool invocation engine",
            "priority": "HIGH",
        },
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]
    assert proj_resp.json()["title"] == "Autonomous Coding Agent"

    # 2. Create a task linked to project
    task_resp = await client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "title": "Implement Sandboxed Code Runner",
            "project_id": project_id,
            "priority": "HIGH",
            "status": "PLANNED",
        },
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]
    assert task_resp.json()["status"] == "PLANNED"
    assert task_resp.json()["project_id"] == project_id

    # 3. Add blocker
    blocker_resp = await client.post(
        f"/api/v1/tasks/{task_id}/blockers",
        headers=headers,
        json={
            "reason": "Security review pending on syscall filter",
            "next_action": "Schedule review with infosec",
        },
    )
    assert blocker_resp.status_code == 200
    b_data = blocker_resp.json()
    assert b_data["status"] == "BLOCKED"
    assert b_data["blocked_reason"] == "Security review pending on syscall filter"
    blocker_id = b_data["blockers"][0]["blocker_id"]

    # 4. Resolve blocker
    resolve_resp = await client.post(
        f"/api/v1/tasks/{task_id}/blockers/{blocker_id}/resolve",
        headers=headers,
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "TODO"
    assert resolve_resp.json()["blocked_reason"] is None

    # 5. Complete task with evidence
    complete_resp = await client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=headers,
        json={
            "evidence_type": "ARTIFACT_VERIFICATION",
            "description": "All 50 unit tests and sandbox isolation checks passing",
            "verified_by": "lead_engineer",
            "artifact_uri": "artifacts/sandbox_test_run.json",
        },
    )
    assert complete_resp.status_code == 200
    c_data = complete_resp.json()
    assert c_data["status"] == "COMPLETED"
    assert c_data["completed_at"] is not None
    assert c_data["completion_evidence"]["verified_by"] == "lead_engineer"

    # 6. Query pending work endpoint
    pending_resp = await client.get("/api/v1/tasks/pending?include_yesterday=true", headers=headers)
    assert pending_resp.status_code == 200
    pend_data = pending_resp.json()
    assert "summary" in pend_data
    assert "in_progress" in pend_data
    assert "blocked" in pend_data
    assert "yesterday_continuity" in pend_data


@pytest.mark.asyncio
async def test_cross_user_task_isolation(client: AsyncClient):
    """Verify that User B cannot access or modify User A's tasks or projects."""
    headers_a = await get_auth_headers(client, "alice_tasks@jarvis.ai")
    headers_b = await get_auth_headers(client, "bob_tasks@jarvis.ai")

    # User A creates a project and task
    p_resp = await client.post(
        "/api/v1/projects",
        headers=headers_a,
        json={"title": "Alice Confidential Strategy"},
    )
    proj_id = p_resp.json()["id"]

    t_resp = await client.post(
        "/api/v1/tasks",
        headers=headers_a,
        json={"title": "Alice Secret Task", "project_id": proj_id},
    )
    task_id = t_resp.json()["id"]

    # User B attempts to access project
    resp = await client.get(f"/api/v1/projects/{proj_id}", headers=headers_b)
    assert resp.status_code == 403

    resp = await client.patch(
        f"/api/v1/projects/{proj_id}",
        headers=headers_b,
        json={"title": "Hacked Title"},
    )
    assert resp.status_code == 403

    # User B attempts to access task
    resp = await client.get(f"/api/v1/tasks/{task_id}", headers=headers_b)
    assert resp.status_code == 403

    resp = await client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=headers_b,
        json={"title": "Hacked Task Title"},
    )
    assert resp.status_code == 403

    resp = await client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=headers_b,
        json={
            "evidence_type": "USER_CONFIRMATION",
            "description": "Malicious completion",
            "verified_by": "bob",
        },
    )
    assert resp.status_code == 403
