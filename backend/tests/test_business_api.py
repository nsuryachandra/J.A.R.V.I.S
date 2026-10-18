"""Integration tests for Business & Productivity Agent REST API endpoints and isolation."""

import uuid
import pytest
from httpx import AsyncClient


async def get_auth_headers(client: AsyncClient, email: str) -> dict:
    """Register and authenticate user to obtain JWT authorization header."""
    reg_payload = {
        "email": email,
        "password": "SecurePassword123!",
        "display_name": "Business User",
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
async def test_unauthenticated_business_endpoints_rejected(client: AsyncClient):
    """Verify all business endpoints reject unauthenticated requests with 401."""
    dummy_id = str(uuid.uuid4())

    resp = await client.post("/api/v1/business/leads", json={"company_name": "Test"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/business/leads")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/business/leads/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/business/competitors", json={"name": "Test", "website": "https://t.com"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/business/competitors")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/business/competitors/{dummy_id}")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/business/reports", json={"title": "Test"})
    assert resp.status_code == 401

    resp = await client.get("/api/v1/business/reports")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/business/reports/{dummy_id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_business_lead_and_competitor_api_flow(client: AsyncClient):
    """Verify lead creation, enrichment, competitor analysis, and filtering."""
    email = f"biz_user_{uuid.uuid4().hex[:8]}@example.com"
    headers = await get_auth_headers(client, email)

    # 1. Create Lead
    lead_resp = await client.post(
        "/api/v1/business/leads",
        headers=headers,
        json={
            "company_name": "Alpha Horizon Technologies",
            "contact_name": "Arthur Dent",
            "contact_email": "arthur@alphahorizon.ai",
            "website": "https://alphahorizon.ai",
            "industry": "Technology",
            "auto_enrich": True,
        },
    )
    assert lead_resp.status_code == 200
    lead_data = lead_resp.json()
    lead_id = lead_data["id"]
    assert lead_data["company_name"] == "Alpha Horizon Technologies"
    assert lead_data["lead_score"] >= 80
    assert lead_data["privacy_scope"] == "BUSINESS"

    # 2. Get Lead
    get_lead_resp = await client.get(f"/api/v1/business/leads/{lead_id}", headers=headers)
    assert get_lead_resp.status_code == 200
    assert get_lead_resp.json()["id"] == lead_id

    # 3. List Leads with filter
    list_leads_resp = await client.get(
        "/api/v1/business/leads?status=RESEARCHED&industry=Technology",
        headers=headers,
    )
    assert list_leads_resp.status_code == 200
    assert len(list_leads_resp.json()) >= 1

    # 4. Create Competitor
    comp_resp = await client.post(
        "/api/v1/business/competitors",
        headers=headers,
        json={
            "name": "Apex Cloud Systems",
            "website": "https://apexcloud.com",
            "market_segment": "Enterprise SaaS",
            "threat_level": "HIGH",
            "auto_analyze": True,
        },
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    comp_id = comp_data["id"]
    assert comp_data["name"] == "Apex Cloud Systems"
    assert len(comp_data["strengths"]) >= 1

    # 5. List Competitors
    list_comp_resp = await client.get("/api/v1/business/competitors", headers=headers)
    assert list_comp_resp.status_code == 200
    assert len(list_comp_resp.json()) >= 1

    # 6. Generate Business Report
    rep_resp = await client.post(
        "/api/v1/business/reports",
        headers=headers,
        json={
            "title": "Enterprise Market Competitiveness Assessment",
            "report_type": "MARKET_ANALYSIS",
            "target_companies": ["Alpha Horizon Technologies", "Apex Cloud Systems"],
            "key_objectives": "Outperform legacy providers with sovereign privacy firewalls.",
        },
    )
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    rep_id = rep_data["id"]
    assert rep_data["title"] == "Enterprise Market Competitiveness Assessment"
    assert len(rep_data["recommendations"]) >= 1

    # 7. Get Report
    get_rep_resp = await client.get(f"/api/v1/business/reports/{rep_id}", headers=headers)
    assert get_rep_resp.status_code == 200
    assert get_rep_resp.json()["id"] == rep_id


@pytest.mark.asyncio
async def test_tenant_isolation_on_business_resources(client: AsyncClient):
    """Verify complete tenant isolation between Alice and Bob for leads, competitors, and reports."""
    email_a = f"alice_biz_{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"bob_biz_{uuid.uuid4().hex[:8]}@example.com"

    headers_a = await get_auth_headers(client, email_a)
    headers_b = await get_auth_headers(client, email_b)

    # Alice creates resources
    lead_a = (
        await client.post(
            "/api/v1/business/leads",
            headers=headers_a,
            json={"company_name": "Alice Co"},
        )
    ).json()["id"]

    comp_a = (
        await client.post(
            "/api/v1/business/competitors",
            headers=headers_a,
            json={"name": "Alice Comp", "website": "https://ac.com"},
        )
    ).json()["id"]

    rep_a = (
        await client.post(
            "/api/v1/business/reports",
            headers=headers_a,
            json={"title": "Alice Report"},
        )
    ).json()["id"]

    # Bob attempts to access Alice's resources -> all must return 404
    resp_lead = await client.get(f"/api/v1/business/leads/{lead_a}", headers=headers_b)
    assert resp_lead.status_code == 404

    resp_comp = await client.get(f"/api/v1/business/competitors/{comp_a}", headers=headers_b)
    assert resp_comp.status_code == 404

    resp_rep = await client.get(f"/api/v1/business/reports/{rep_a}", headers=headers_b)
    assert resp_rep.status_code == 404
