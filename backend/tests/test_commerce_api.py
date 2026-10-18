"""Integration tests for Commerce & External Actions REST API endpoints, approval gates, and isolation."""

import uuid
import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Register and authenticate user to obtain JWT authorization header."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Commerce User",
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
async def test_unauthenticated_commerce_endpoints_rejected(client: AsyncClient):
    """Verify all commerce endpoints reject unauthenticated requests with 401."""
    dummy_id = str(uuid.uuid4())

    resp = await client.post("/api/v1/commerce/compare", json={"query": "Laptop"})
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/commerce/orders",
        json={
            "merchant": "BestBuy",
            "title": "Laptop",
            "items": [{"name": "Laptop", "quantity": 1, "unit_price": 1000.0, "total_price": 1000.0}],
            "idempotency_key": "idemp_test_unauth",
        },
    )
    assert resp.status_code == 401

    resp = await client.get("/api/v1/commerce/orders")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/commerce/orders/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post(f"/api/v1/commerce/orders/{dummy_id}/execute", json={})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_compare_products_endpoint(client: AsyncClient):
    """Verify product comparison API endpoint returns ranked options."""
    email = f"comm_user_{uuid.uuid4().hex[:8]}@example.com"
    headers = await get_auth_headers(client, email)

    resp = await client.post(
        "/api/v1/commerce/compare",
        headers=headers,
        json={"query": "Noise-Cancelling Headphones", "category": "Audio", "max_price": 300.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "Noise-Cancelling Headphones"
    assert data["category"] == "Audio"
    assert len(data["options"]) >= 2
    assert "Noise-Cancelling Headphones" in data["best_value_recommendation"]


@pytest.mark.asyncio
async def test_order_draft_and_consequential_approval_execution_flow(client: AsyncClient):
    """Verify end-to-end commerce workflow: draft -> 400 without confirmation -> 403 approval gate -> approve -> execute -> idempotent replay."""
    email = f"comm_user_{uuid.uuid4().hex[:8]}@example.com"
    headers = await get_auth_headers(client, email)

    # 1. Draft order (SAFE action)
    order_payload = {
        "order_type": "PURCHASE",
        "merchant": "Global Electronics",
        "title": "Workstation Accessories",
        "currency": "USD",
        "items": [
            {"name": "Mechanical Keyboard", "quantity": 1, "unit_price": 150.0, "total_price": 150.0},
            {"name": "Precision Mouse", "quantity": 1, "unit_price": 80.0, "total_price": 80.0},
        ],
        "delivery_details": "Tech Office Suite 10",
        "idempotency_key": f"idemp_api_{uuid.uuid4().hex[:8]}",
    }
    draft_resp = await client.post("/api/v1/commerce/orders", headers=headers, json=order_payload)
    assert draft_resp.status_code == 200
    draft_data = draft_resp.json()
    order_id = draft_data["id"]
    assert draft_data["merchant"] == "Global Electronics"
    assert draft_data["subtotal_amount"] == 230.0
    assert draft_data["tax_amount"] == 18.40  # 8% tax
    assert draft_data["total_amount"] == 248.40
    assert draft_data["status"] == "DRAFT"

    # 2. List orders
    list_resp = await client.get("/api/v1/commerce/orders", headers=headers)
    assert list_resp.status_code == 200
    assert any(o["id"] == order_id for o in list_resp.json())

    # 3. Get single order
    get_resp = await client.get(f"/api/v1/commerce/orders/{order_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == order_id

    # 4. Attempt execution with confirmed_by_user = False -> 400 Bad Request
    fail_confirm_resp = await client.post(
        f"/api/v1/commerce/orders/{order_id}/execute",
        headers=headers,
        json={"confirmed_by_user": False},
    )
    assert fail_confirm_resp.status_code == 400
    assert "Double-confirmation required" in fail_confirm_resp.json()["detail"]

    # 5. Attempt execution with confirmed_by_user = True but no approval -> 403 Forbidden
    gated_resp = await client.post(
        f"/api/v1/commerce/orders/{order_id}/execute",
        headers=headers,
        json={"confirmed_by_user": True},
    )
    assert gated_resp.status_code == 403
    assert "Approval required to execute financial transaction" in gated_resp.json()["detail"]

    # 6. Fetch pending approval request
    approvals_resp = await client.get("/api/v1/approvals", headers=headers)
    assert approvals_resp.status_code == 200
    approvals_data = approvals_resp.json()
    assert len(approvals_data) > 0
    target_approval = next(
        a for a in approvals_data if a.get("tool_name") == "commerce.execute_order"
    )
    approval_id = target_approval["id"]

    # 7. Approve the request
    resolve_resp = await client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers=headers,
        json={"approval_method": "UI_CONFIRMATION"},
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "GRANTED"

    # 8. Execute order with approval_id
    exec_resp = await client.post(
        f"/api/v1/commerce/orders/{order_id}/execute",
        headers=headers,
        json={
            "approval_id": approval_id,
            "confirmed_by_user": True,
            "payment_method": "CORP_CARD",
        },
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["order_id"] == order_id
    assert exec_data["status"] == "EXECUTED"
    assert exec_data["total_charged"] == 248.40
    assert exec_data["transaction_reference"].startswith("TXN-")
    assert "Successfully charged" in exec_data["receipt_summary"]

    # 9. Idempotent replay: executing already executed order returns receipt directly
    replay_resp = await client.post(
        f"/api/v1/commerce/orders/{order_id}/execute",
        headers=headers,
        json={
            "approval_id": approval_id,
            "confirmed_by_user": True,
            "payment_method": "CORP_CARD",
        },
    )
    assert replay_resp.status_code == 200
    assert replay_resp.json()["status"] == "EXECUTED"
    assert replay_resp.json()["transaction_reference"] == exec_data["transaction_reference"]
    assert "previously executed" in replay_resp.json()["receipt_summary"]


@pytest.mark.asyncio
async def test_tenant_isolation_api(client: AsyncClient):
    """Verify cross-tenant isolation over REST API endpoints."""
    user_a_email = f"user_a_{uuid.uuid4().hex[:8]}@example.com"
    user_b_email = f"user_b_{uuid.uuid4().hex[:8]}@example.com"
    headers_a = await get_auth_headers(client, user_a_email)
    headers_b = await get_auth_headers(client, user_b_email)

    # User A creates draft
    draft_resp = await client.post(
        "/api/v1/commerce/orders",
        headers=headers_a,
        json={
            "merchant": "VendorA",
            "title": "Private Item",
            "items": [{"name": "Item A", "quantity": 1, "unit_price": 50.0, "total_price": 50.0}],
            "idempotency_key": f"idemp_{uuid.uuid4().hex[:8]}",
        },
    )
    assert draft_resp.status_code == 200
    order_id = draft_resp.json()["id"]

    # User B cannot access User A's order -> 404
    get_resp = await client.get(f"/api/v1/commerce/orders/{order_id}", headers=headers_b)
    assert get_resp.status_code == 404

    # User B cannot execute User A's order -> 404
    exec_resp = await client.post(
        f"/api/v1/commerce/orders/{order_id}/execute",
        headers=headers_b,
        json={"confirmed_by_user": True},
    )
    assert exec_resp.status_code == 404
