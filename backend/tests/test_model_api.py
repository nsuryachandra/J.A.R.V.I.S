"""Integration tests for Model Routing and Inference REST API endpoints."""

import uuid
import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Helper to register/login a test user and obtain bearer auth headers."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Model User",
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
async def test_unauthenticated_model_endpoints_rejected(client: AsyncClient):
    """Verify that unauthenticated callers cannot invoke model routes."""
    resp = await client.get("/api/v1/models/routes")
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/models/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/models/structured/intent",
        json={"query": "Remind me to buy milk"},
    )
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/models/structured/plan",
        json={"goal": "Deploy app to production"},
    )
    assert resp.status_code == 401

    resp = await client.get("/api/v1/models/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_model_routes_endpoint(client: AsyncClient):
    """Verify routes endpoint returns logical mappings and mock provider status."""
    headers = await get_auth_headers(client, "routes_tester@jarvis.ai")
    resp = await client.get("/api/v1/models/routes", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_provider"] == "mock"
    assert "fast_chat" in data["routes"]
    assert "reasoning" in data["routes"]
    assert "coding" in data["routes"]
    assert "vision" in data["routes"]
    assert "embedding" in data["routes"]


@pytest.mark.asyncio
async def test_model_chat_endpoint(client: AsyncClient):
    """Verify conversational chat endpoint responds with valid content and usage metrics."""
    headers = await get_auth_headers(client, "chat_tester@jarvis.ai")
    payload = {
        "messages": [
            {"role": "system", "content": "You are JARVIS."},
            {"role": "user", "content": "Good morning JARVIS."},
        ],
        "role": "fast_chat",
        "temperature": 0.5,
        "max_tokens": 512,
    }
    resp = await client.post("/api/v1/models/chat", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "JARVIS" in data["content"] or len(data["content"]) > 0
    assert data["role"] == "assistant"
    assert data["provider"] == "mock"
    assert data["total_tokens"] > 0
    assert data["prompt_tokens"] > 0
    assert data["completion_tokens"] > 0
    assert data["latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_model_structured_intent_endpoint(client: AsyncClient):
    """Verify structured intent classification via HTTP."""
    headers = await get_auth_headers(client, "intent_tester@jarvis.ai")
    payload = {"query": "Check the status of my pending project tasks"}
    resp = await client.post("/api/v1/models/structured/intent", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "TASK_QUERY"
    assert data["confidence"] >= 0.8
    assert data["requires_tools"] is True
    assert data["risk_level"] == "SAFE"


@pytest.mark.asyncio
async def test_model_structured_plan_endpoint(client: AsyncClient):
    """Verify structured plan generation via HTTP."""
    headers = await get_auth_headers(client, "plan_tester@jarvis.ai")
    payload = {"goal": "Prepare quarterly financial statement"}
    resp = await client.post("/api/v1/models/structured/plan", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "quarterly financial statement" in data["goal"]
    assert len(data["steps"]) == 3
    assert data["estimated_risk"] == "SAFE"
    assert len(data["required_tools"]) >= 1


@pytest.mark.asyncio
async def test_model_usage_endpoint_and_isolation(client: AsyncClient):
    """Verify user token consumption tracking and tenant isolation."""
    headers_a = await get_auth_headers(client, "user_a_model@jarvis.ai")
    headers_b = await get_auth_headers(client, "user_b_model@jarvis.ai")

    # User A initiates 2 completions
    await client.post(
        "/api/v1/models/chat",
        json={"messages": [{"role": "user", "content": "Test prompt 1"}]},
        headers=headers_a,
    )
    await client.post(
        "/api/v1/models/chat",
        json={"messages": [{"role": "user", "content": "Test prompt 2"}]},
        headers=headers_a,
    )

    # Check User A usage metrics
    resp_a = await client.get("/api/v1/models/usage", headers=headers_a)
    assert resp_a.status_code == 200
    usage_a = resp_a.json()
    assert usage_a["total_calls"] == 2
    assert usage_a["total_tokens"] > 0
    assert usage_a["prompt_tokens"] > 0
    assert usage_a["completion_tokens"] > 0

    # User B has made 0 calls, must be completely isolated
    resp_b = await client.get("/api/v1/models/usage", headers=headers_b)
    assert resp_b.status_code == 200
    usage_b = resp_b.json()
    assert usage_b["total_calls"] == 0
    assert usage_b["total_tokens"] == 0
    assert usage_b["prompt_tokens"] == 0
    assert usage_b["completion_tokens"] == 0


@pytest.mark.asyncio
async def test_invalid_model_inputs_rejected(client: AsyncClient):
    """Verify negative validation boundaries for model endpoints."""
    headers = await get_auth_headers(client, "validation_tester@jarvis.ai")

    # Invalid temperature out of range (ge=0.0, le=2.0)
    resp_temp = await client.post(
        "/api/v1/models/chat",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 5.0,
        },
        headers=headers,
    )
    assert resp_temp.status_code == 422

    # Negative max_tokens
    resp_tokens = await client.post(
        "/api/v1/models/chat",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 0,
        },
        headers=headers,
    )
    assert resp_tokens.status_code == 422

    # Empty intent query
    resp_intent = await client.post(
        "/api/v1/models/structured/intent",
        json={"query": ""},
        headers=headers,
    )
    assert resp_intent.status_code == 422

    # Empty plan goal
    resp_plan = await client.post(
        "/api/v1/models/structured/plan",
        json={"goal": ""},
        headers=headers,
    )
    assert resp_plan.status_code == 422
