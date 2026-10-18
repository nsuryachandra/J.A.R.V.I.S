"""Integration tests for Coding Agent REST API endpoints, approval flow, and isolation."""

import tempfile
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Register and authenticate user to obtain JWT authorization header."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Coding User",
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
async def test_unauthenticated_coding_endpoints_rejected(client: AsyncClient):
    """Verify all coding endpoints reject unauthenticated requests with 401."""
    dummy_id = str(uuid.uuid4())

    resp = await client.post("/api/v1/coding/sessions", json={"workspace_path": ".", "title": "T"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/coding/sessions")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/coding/sessions/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/coding/inspect", json={"workspace_path": "."})
    assert resp.status_code == 401

    resp = await client.post("/api/v1/coding/proposals", json={"session_id": dummy_id, "target_file": "f", "title": "t", "description": "d", "proposed_content": "c"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/coding/proposals")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/coding/proposals/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/coding/proposals/{dummy_id}/apply", json={"proposal_id": dummy_id})
    assert resp.status_code == 401

    resp = await client.post("/api/v1/coding/tests/run", json={"workspace_path": "."})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_coding_session_inspect_and_proposals_api(client: AsyncClient):
    """Verify session creation, file inspection, and proposal generation."""
    headers = await get_auth_headers(client, "coding_api_user@jarvis.ai")

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        target_file = base / "math_ops.py"
        target_file.write_text("def multiply(a, b):\n    return a * b\n", encoding="utf-8")

        # 1. Create coding session
        sess_resp = await client.post(
            "/api/v1/coding/sessions",
            headers=headers,
            json={"workspace_path": str(base), "title": "Math Ops Refactor"},
        )
        assert sess_resp.status_code == 200
        session_id = sess_resp.json()["id"]

        # 2. List sessions
        list_sess = await client.get("/api/v1/coding/sessions", headers=headers)
        assert list_sess.status_code == 200
        assert any(s["id"] == session_id for s in list_sess.json())

        # 3. Inspect code
        inspect_resp = await client.post(
            "/api/v1/coding/inspect",
            headers=headers,
            json={"workspace_path": str(base), "relative_file_path": "math_ops.py", "include_symbols": True},
        )
        assert inspect_resp.status_code == 200
        inspect_data = inspect_resp.json()
        assert inspect_data["total_files"] == 1
        assert inspect_data["files"][0]["syntax_valid"] is True
        assert any(s["name"] == "multiply" for s in inspect_data["files"][0]["symbols"])

        # 4. Propose change
        prop_resp = await client.post(
            "/api/v1/coding/proposals",
            headers=headers,
            json={
                "session_id": session_id,
                "target_file": "math_ops.py",
                "title": "Add Type Annotations",
                "description": "Add int type hints",
                "proposed_content": "def multiply(a: int, b: int) -> int:\n    return a * b\n",
            },
        )
        assert prop_resp.status_code == 200
        prop_data = prop_resp.json()
        proposal_id = prop_data["id"]
        assert prop_data["status"] == "PENDING_APPROVAL"
        assert "+def multiply(a: int, b: int) -> int:" in prop_data["diff_content"]

        # 5. List proposals
        proposals_list = await client.get(f"/api/v1/coding/proposals?session_id={session_id}", headers=headers)
        assert proposals_list.status_code == 200
        assert any(p["id"] == proposal_id for p in proposals_list.json())


@pytest.mark.asyncio
async def test_coding_consequential_apply_and_approval_flow(client: AsyncClient):
    """Verify consequential patch application requires Policy Broker approval."""
    headers = await get_auth_headers(client, "approval_flow_user@jarvis.ai")

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        target_file = base / "config.py"
        target_file.write_text("DEBUG = False\n", encoding="utf-8")

        # 1. Setup session & proposal
        sess_resp = await client.post(
            "/api/v1/coding/sessions",
            headers=headers,
            json={"workspace_path": str(base), "title": "Config Update"},
        )
        session_id = sess_resp.json()["id"]

        prop_resp = await client.post(
            "/api/v1/coding/proposals",
            headers=headers,
            json={
                "session_id": session_id,
                "target_file": "config.py",
                "title": "Enable Debug",
                "description": "Switch debug flag",
                "proposed_content": "DEBUG = True\n",
            },
        )
        proposal_id = prop_resp.json()["id"]

        # 2. Dry run application succeeds without mutating file
        dry_resp = await client.post(
            f"/api/v1/coding/proposals/{proposal_id}/apply",
            headers=headers,
            json={"proposal_id": proposal_id, "dry_run": True},
        )
        assert dry_resp.status_code == 200
        assert dry_resp.json()["applied"] is False
        assert target_file.read_text(encoding="utf-8") == "DEBUG = False\n"

        # 3. Applying without approval fails with 403 Forbidden
        unapproved_resp = await client.post(
            f"/api/v1/coding/proposals/{proposal_id}/apply",
            headers=headers,
            json={"proposal_id": proposal_id, "dry_run": False},
        )
        assert unapproved_resp.status_code == 403
        assert "Approval required" in unapproved_resp.json()["detail"]

        # 4. Check proposal for linked approval_id
        prop_detail = await client.get(f"/api/v1/coding/proposals/{proposal_id}", headers=headers)
        assert prop_detail.status_code == 200
        approval_id = prop_detail.json()["approval_id"]
        assert approval_id is not None

        # 5. Authorize approval request via approvals API
        decide_resp = await client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers=headers,
            json={"approval_method": "UI_CONFIRMATION"},
        )
        assert decide_resp.status_code == 200

        # 6. Apply with approval_id succeeds
        apply_resp = await client.post(
            f"/api/v1/coding/proposals/{proposal_id}/apply",
            headers=headers,
            json={"proposal_id": proposal_id, "approval_id": approval_id, "dry_run": False},
        )
        assert apply_resp.status_code == 200
        assert apply_resp.json()["applied"] is True
        assert apply_resp.json()["status"] == "APPLIED"
        assert target_file.read_text(encoding="utf-8") == "DEBUG = True\n"


@pytest.mark.asyncio
async def test_coding_api_tenant_isolation(client: AsyncClient):
    """Verify tenant isolation across users."""
    headers_a = await get_auth_headers(client, "coder_alpha@jarvis.ai")
    headers_b = await get_auth_headers(client, "coder_beta@jarvis.ai")

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "secret.py").write_text("SECRET = '123'\n", encoding="utf-8")

        sess_resp = await client.post(
            "/api/v1/coding/sessions",
            headers=headers_a,
            json={"workspace_path": str(tmpdir), "title": "Alpha Workspace"},
        )
        session_id_a = sess_resp.json()["id"]

        prop_resp = await client.post(
            "/api/v1/coding/proposals",
            headers=headers_a,
            json={
                "session_id": session_id_a,
                "target_file": "secret.py",
                "title": "Alpha Proposal",
                "description": "Refactor",
                "proposed_content": "SECRET = '456'\n",
            },
        )
        proposal_id_a = prop_resp.json()["id"]

        # User B queries User A's session -> 404
        resp_b_sess = await client.get(f"/api/v1/coding/sessions/{session_id_a}", headers=headers_b)
        assert resp_b_sess.status_code == 404

        # User B queries User A's proposal -> 404
        resp_b_prop = await client.get(f"/api/v1/coding/proposals/{proposal_id_a}", headers=headers_b)
        assert resp_b_prop.status_code == 404

        # User B attempts to apply User A's proposal -> 404
        resp_b_apply = await client.post(
            f"/api/v1/coding/proposals/{proposal_id_a}/apply",
            headers=headers_b,
            json={"proposal_id": proposal_id_a},
        )
        assert resp_b_apply.status_code == 404


@pytest.mark.asyncio
async def test_coding_api_validation_and_path_traversal(client: AsyncClient):
    """Verify request validation rejects invalid inputs and path traversal attempts."""
    headers = await get_auth_headers(client, "validation_coder@jarvis.ai")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Path traversal in inspection returns 400
        resp = await client.post(
            "/api/v1/coding/inspect",
            headers=headers,
            json={"workspace_path": tmpdir, "relative_file_path": "../../etc/shadow"},
        )
        assert resp.status_code == 400
        assert "Path traversal blocked" in resp.json()["detail"]

        # Empty title on session returns 422
        resp = await client.post("/api/v1/coding/sessions", headers=headers, json={"workspace_path": tmpdir, "title": ""})
        assert resp.status_code == 422
