"""Integration tests for Browser & Computer Agent REST API endpoints, approval gates, and tenant isolation."""

import uuid
import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Register and authenticate user to obtain JWT authorization header."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Browser User",
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
async def test_unauthenticated_browser_endpoints_rejected(client: AsyncClient):
    """Verify all browser endpoints reject unauthenticated requests with 401."""
    dummy_id = str(uuid.uuid4())

    resp = await client.post("/api/v1/browser/sessions", json={"title": "Test"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/browser/sessions")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/browser/sessions/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/browser/sessions/{dummy_id}/navigate", json={"url": "https://example.com"})
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/browser/sessions/{dummy_id}/page")
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/browser/sessions/{dummy_id}/fill", json={"selector": "input", "value": "x"})
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/browser/sessions/{dummy_id}/submit", json={"selector": "button"})
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/browser/sessions/{dummy_id}/screenshot", json={})
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/browser/sessions/{dummy_id}/screenshots")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/browser/sessions/{dummy_id}/actions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_browser_full_navigation_and_interaction_flow(client: AsyncClient):
    """Verify session creation, SSRF defense, navigation, reading, and screenshots."""
    email = f"browser_user_{uuid.uuid4().hex[:8]}@example.com"
    headers = await get_auth_headers(client, email)

    # 1. Create session
    create_resp = await client.post(
        "/api/v1/browser/sessions",
        headers=headers,
        json={"title": "Web Research Flow", "viewport_width": 1280, "viewport_height": 800},
    )
    assert create_resp.status_code == 200
    session_data = create_resp.json()
    session_id = session_data["id"]
    assert session_data["title"] == "Web Research Flow"
    assert session_data["current_url"] == "about:blank"

    # 2. Get session details
    get_resp = await client.get(f"/api/v1/browser/sessions/{session_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == session_id

    # 3. SSRF Protection: Navigate to loopback address must be blocked
    ssrf_resp = await client.post(
        f"/api/v1/browser/sessions/{session_id}/navigate",
        headers=headers,
        json={"url": "http://127.0.0.1:8000/internal-secrets"},
    )
    assert ssrf_resp.status_code == 400
    assert "blocked" in ssrf_resp.json()["detail"].lower()

    # 4. Navigate to valid public URL
    nav_resp = await client.post(
        f"/api/v1/browser/sessions/{session_id}/navigate",
        headers=headers,
        json={"url": "https://example.com"},
    )
    assert nav_resp.status_code == 200
    assert nav_resp.json()["url"] == "https://example.com"
    assert nav_resp.json()["status"] == "LOADED"

    # 5. Read page content wrapped in untrusted boundaries
    page_resp = await client.get(f"/api/v1/browser/sessions/{session_id}/page", headers=headers)
    assert page_resp.status_code == 200
    page_data = page_resp.json()
    assert "<untrusted_content" in page_data["content"]
    assert len(page_data["elements"]) > 0

    # 6. Capture visual screenshot
    shot_resp = await client.post(
        f"/api/v1/browser/sessions/{session_id}/screenshot",
        headers=headers,
        json={"caption": "Snapshot of Example Domain"},
    )
    assert shot_resp.status_code == 200
    shot_data = shot_resp.json()
    assert shot_data["image_base64"].startswith("iVBORw0KGgo")
    assert shot_data["caption"] == "Snapshot of Example Domain"

    # 7. List screenshots
    shots_list_resp = await client.get(f"/api/v1/browser/sessions/{session_id}/screenshots", headers=headers)
    assert shots_list_resp.status_code == 200
    assert len(shots_list_resp.json()) >= 1


@pytest.mark.asyncio
async def test_form_submission_approval_gate_and_isolation(client: AsyncClient):
    """Verify form submission requires approval, executes upon approval, and enforces tenant isolation."""
    email_a = f"alice_browser_{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"bob_browser_{uuid.uuid4().hex[:8]}@example.com"

    headers_a = await get_auth_headers(client, email_a)
    headers_b = await get_auth_headers(client, email_b)

    # Alice creates a session
    resp_a = await client.post(
        "/api/v1/browser/sessions",
        headers=headers_a,
        json={"title": "Alice Checkout Session"},
    )
    session_id = resp_a.json()["id"]

    # Bob tries to access Alice's session -> must be 404
    bob_get = await client.get(f"/api/v1/browser/sessions/{session_id}", headers=headers_b)
    assert bob_get.status_code == 404

    # Alice navigates to checkout page
    await client.post(
        f"/api/v1/browser/sessions/{session_id}/navigate",
        headers=headers_a,
        json={"url": "https://example.com/checkout"},
    )

    # Alice fills form fields
    fill_resp = await client.post(
        f"/api/v1/browser/sessions/{session_id}/fill",
        headers=headers_a,
        json={"selector": "#shipping-name", "value": "Alice Wonderland"},
    )
    assert fill_resp.status_code == 200
    assert fill_resp.json()["success"] is True

    # Alice attempts submit without approval -> 403 Forbidden
    submit_fail = await client.post(
        f"/api/v1/browser/sessions/{session_id}/submit",
        headers=headers_a,
        json={"selector": "#submit-order"},
    )
    assert submit_fail.status_code == 403
    assert "approval required" in submit_fail.json()["detail"].lower()

    # Retrieve approval request from pending approvals
    approvals_resp = await client.get("/api/v1/approvals", headers=headers_a)
    assert approvals_resp.status_code == 200
    pending_approvals = approvals_resp.json()
    assert len(pending_approvals) >= 1
    approval_req = next(a for a in pending_approvals if a["tool_name"] == "browser.submit_form")
    approval_id = approval_req["id"]

    # Alice approves the pending request
    approve_resp = await client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers=headers_a,
        json={"user_note": "Order confirmed and verified."},
    )
    assert approve_resp.status_code == 200

    # Alice re-submits with approval_id -> succeeds with 200
    submit_success = await client.post(
        f"/api/v1/browser/sessions/{session_id}/submit",
        headers=headers_a,
        json={"selector": "#submit-order", "approval_id": approval_id},
    )
    assert submit_success.status_code == 200
    data = submit_success.json()
    assert data["status"] == "SUCCESS"
    assert data["new_url"] == "https://example.com/order-success"

    # Verify action history
    actions_resp = await client.get(f"/api/v1/browser/sessions/{session_id}/actions", headers=headers_a)
    assert actions_resp.status_code == 200
    actions = actions_resp.json()
    action_types = [a["action_type"] for a in actions]
    assert "NAVIGATE" in action_types
    assert "FILL_FORM" in action_types
    assert "SUBMIT_FORM" in action_types
