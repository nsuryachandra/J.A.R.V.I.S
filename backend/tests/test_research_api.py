"""Integration tests for Research and Writing Agents REST API endpoints."""

import uuid
import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Register and authenticate user to obtain JWT authorization header."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Research User",
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
async def test_unauthenticated_research_endpoints_rejected(client: AsyncClient):
    """Verify all research endpoints require valid authentication."""
    dummy_id = str(uuid.uuid4())

    resp = await client.post("/api/v1/research/search", json={"query": "test"})
    assert resp.status_code == 401

    resp = await client.post("/api/v1/research/run", json={"topic": "T", "query": "Q"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/research/sessions")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/research/sessions/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/research/documents/draft", json={"title": "Doc"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/research/documents")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/research/documents/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/research/documents/{dummy_id}/export")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_research_search_api(client: AsyncClient):
    """Verify authenticated web search endpoint returns validated sources."""
    headers = await get_auth_headers(client, "search_user@jarvis.ai")

    resp = await client.post(
        "/api/v1/research/search",
        headers=headers,
        json={"query": "circadian autophagy fasting", "max_results": 4},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "circadian autophagy fasting"
    assert data["total_results"] > 0
    assert len(data["results"]) <= 4
    for item in data["results"]:
        assert "url" in item
        assert "credibility_score" in item
        assert item["credibility_score"] > 0.0


@pytest.mark.asyncio
async def test_research_execution_and_session_details(client: AsyncClient):
    """Verify full research flow, session persistence, and session detail retrieval."""
    headers = await get_auth_headers(client, "exec_user@jarvis.ai")

    # 1. Execute research
    run_resp = await client.post(
        "/api/v1/research/run",
        headers=headers,
        json={
            "topic": "Intermittent Fasting & Autophagy",
            "query": "peak autophagy hours human clinical data",
            "depth": "standard",
        },
    )
    assert run_resp.status_code == 200
    brief = run_resp.json()
    session_id = brief["session_id"]
    assert brief["findings_count"] > 0
    assert len(brief["facts"]) > 0
    assert len(brief["sources"]) > 0

    # 2. List sessions
    list_resp = await client.get("/api/v1/research/sessions", headers=headers)
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert len(sessions) >= 1
    found = [s for s in sessions if s["id"] == session_id]
    assert len(found) == 1
    assert found[0]["topic"] == "Intermittent Fasting & Autophagy"

    # 3. Get session details
    detail_resp = await client.get(f"/api/v1/research/sessions/{session_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["session_id"] == session_id
    assert len(detail["facts"]) == len(brief["facts"])
    assert len(detail["sources"]) == len(brief["sources"])


@pytest.mark.asyncio
async def test_document_draft_and_export_lifecycle(client: AsyncClient):
    """Verify drafting structured documents, listing artifacts, and HTML export."""
    headers = await get_auth_headers(client, "writer_user@jarvis.ai")

    # 1. Run quick research to get ground truth session
    run_resp = await client.post(
        "/api/v1/research/run",
        headers=headers,
        json={
            "topic": "Agentic Verification Patterns",
            "query": "deterministic audit trails hash chain",
        },
    )
    assert run_resp.status_code == 200
    session_id = run_resp.json()["session_id"]

    # 2. Draft document
    draft_resp = await client.post(
        "/api/v1/research/documents/draft",
        headers=headers,
        json={
            "title": "Agent Verification Protocol Specification",
            "doc_type": "SPEC",
            "session_id": session_id,
            "instructions": "Target audience: Security Auditors",
            "format": "MARKDOWN",
        },
    )
    assert draft_resp.status_code == 200
    doc = draft_resp.json()
    doc_id = doc["id"]
    assert doc["title"] == "Agent Verification Protocol Specification"
    assert doc["doc_type"] == "SPEC"
    assert doc["word_count"] > 20
    assert "# Agent Verification Protocol Specification" in doc["content_markdown"]

    # 3. List documents
    docs_resp = await client.get("/api/v1/research/documents", headers=headers)
    assert docs_resp.status_code == 200
    docs = docs_resp.json()
    assert any(d["id"] == doc_id for d in docs)

    # 4. Get document by ID
    get_resp = await client.get(f"/api/v1/research/documents/{doc_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == doc_id

    # 5. Export document as HTML
    export_resp = await client.get(f"/api/v1/research/documents/{doc_id}/export?export_format=html", headers=headers)
    assert export_resp.status_code == 200
    exported = export_resp.json()
    assert exported["content_type"] == "text/html"
    assert "<!DOCTYPE html>" in exported["exported_content"]
    assert "Agent Verification Protocol Specification" in exported["exported_content"]


@pytest.mark.asyncio
async def test_research_api_isolation_and_not_found(client: AsyncClient):
    """Verify tenant isolation: User B cannot access User A's sessions or documents."""
    headers_a = await get_auth_headers(client, "user_alpha@jarvis.ai")
    headers_b = await get_auth_headers(client, "user_beta@jarvis.ai")

    # User A runs research and drafts doc
    run_resp = await client.post(
        "/api/v1/research/run",
        headers=headers_a,
        json={"topic": "Alpha Confidential Research", "query": "alpha research"},
    )
    session_id_a = run_resp.json()["session_id"]

    draft_resp = await client.post(
        "/api/v1/research/documents/draft",
        headers=headers_a,
        json={"title": "Alpha Confidential Doc", "session_id": session_id_a},
    )
    doc_id_a = draft_resp.json()["id"]

    # User B attempts to access User A's session -> 404
    resp_session_b = await client.get(f"/api/v1/research/sessions/{session_id_a}", headers=headers_b)
    assert resp_session_b.status_code == 404

    # User B attempts to access User A's document -> 404
    resp_doc_b = await client.get(f"/api/v1/research/documents/{doc_id_a}", headers=headers_b)
    assert resp_doc_b.status_code == 404

    # User B attempts to export User A's document -> 404
    resp_export_b = await client.get(f"/api/v1/research/documents/{doc_id_a}/export", headers=headers_b)
    assert resp_export_b.status_code == 404


@pytest.mark.asyncio
async def test_research_api_validation_boundaries(client: AsyncClient):
    """Verify payload validation fails gracefully on empty or malformed inputs."""
    headers = await get_auth_headers(client, "validation_user@jarvis.ai")

    # Empty search query
    resp = await client.post("/api/v1/research/search", headers=headers, json={"query": ""})
    assert resp.status_code == 422

    # Empty topic on research run
    resp = await client.post("/api/v1/research/run", headers=headers, json={"topic": "", "query": "valid query"})
    assert resp.status_code == 422

    # Empty title on document draft
    resp = await client.post("/api/v1/research/documents/draft", headers=headers, json={"title": ""})
    assert resp.status_code == 422

    # Invalid export format
    valid_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/research/documents/{valid_id}/export?export_format=invalid_format", headers=headers)
    assert resp.status_code == 422
