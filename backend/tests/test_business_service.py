"""Unit and domain integration tests for Business & Productivity Agent service."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.contracts.common import PrivacyScope
from app.core.exceptions import EntityNotFoundError
from app.models.audit import AuditLog
from app.models.user import User
from app.services.business.engines import LeadResearchEngine
from app.services.business.schemas import (
    CreateCompetitorRequest,
    CreateLeadRequest,
    GenerateBusinessReportRequest,
)
from app.services.business.service import BusinessService


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    """Create test user fixture."""
    u = User(
        id=uuid.uuid4(),
        email=f"business_unit_{uuid.uuid4().hex[:6]}@jarvis.ai",
        hashed_password="hashed_pw_test",
        timezone="Asia/Kolkata",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


class TestLeadResearchEngine:
    """Tests for lead scoring algorithm and firmographic enrichment."""

    def test_lead_score_calculation(self):
        # Baseline tech lead with valid domain and corporate email
        score_high = LeadResearchEngine.calculate_lead_score(
            company_name="Acme AI Corp",
            website="https://acmeai.io",
            contact_email="vp@acmeai.io",
            industry="Technology",
        )
        assert score_high >= 80

        # Consumer lead with generic free email and non-target industry
        score_low = LeadResearchEngine.calculate_lead_score(
            company_name="Local Bakery",
            website=None,
            contact_email="baker@gmail.com",
            industry="Food & Beverage",
        )
        assert score_low <= 60
        assert score_high > score_low

    def test_firmographic_enrichment_generation(self):
        notes = LeadResearchEngine.enrich_lead_data(
            company_name="Fintech Global",
            industry="Finance",
            website="https://fintechglobal.com",
        )
        assert "Fintech Global" in notes
        assert "Industry Vertical: Finance" in notes
        assert "Recommended Outreach Angle" in notes


class TestBusinessService:
    """Domain tests for leads, competitors, executive reports, privacy firewalls, and audits."""

    @pytest.fixture
    def business_service(self) -> BusinessService:
        return BusinessService()

    @pytest.mark.asyncio
    async def test_lead_lifecycle_and_filtering(
        self,
        db_session: AsyncSession,
        user: User,
        business_service: BusinessService,
    ):
        # 1. Create and auto-enrich lead
        lead_req = CreateLeadRequest(
            company_name="Starlight Robotics",
            contact_name="Sarah Connor",
            contact_email="sarah@starlight.io",
            website="https://starlight.io",
            industry="Technology",
            auto_enrich=True,
        )
        lead = await business_service.create_lead(
            db=db_session,
            user_id=user.id,
            request=lead_req,
        )
        assert lead.company_name == "Starlight Robotics"
        assert lead.contact_name == "Sarah Connor"
        assert lead.lead_score >= 80
        assert lead.status == "RESEARCHED"
        assert lead.privacy_scope == "BUSINESS"
        assert "Firmographic Intelligence Summary" in (lead.enrichment_notes or "")

        # 2. Retrieve single lead
        lead_db = await business_service.get_lead(
            db=db_session,
            user_id=user.id,
            lead_id=lead.id,
        )
        assert lead_db.id == lead.id

        # 3. List leads with filtering
        leads_all = await business_service.list_leads(db=db_session, user_id=user.id)
        assert len(leads_all) >= 1
        assert any(l.id == lead.id for l in leads_all)

        leads_filtered = await business_service.list_leads(
            db=db_session,
            user_id=user.id,
            status="RESEARCHED",
            industry="Technology",
        )
        assert len(leads_filtered) >= 1

        leads_empty = await business_service.list_leads(
            db=db_session,
            user_id=user.id,
            industry="Automotive",
        )
        assert len(leads_empty) == 0

    @pytest.mark.asyncio
    async def test_competitor_tracking_and_analysis(
        self,
        db_session: AsyncSession,
        user: User,
        business_service: BusinessService,
    ):
        comp_req = CreateCompetitorRequest(
            name="OmniCorp Systems",
            website="https://omnicorp.com",
            market_segment="Enterprise AI",
            threat_level="HIGH",
            strengths=["Global market share"],
            auto_analyze=True,
        )
        comp = await business_service.create_competitor(
            db=db_session,
            user_id=user.id,
            request=comp_req,
        )
        assert comp.name == "OmniCorp Systems"
        assert comp.market_segment == "Enterprise AI"
        assert comp.threat_level in ("HIGH", "MEDIUM")
        assert len(comp.strengths) >= 2
        assert len(comp.weaknesses) >= 1
        assert comp.pricing_summary is not None
        assert comp.privacy_scope == "BUSINESS"

        # List competitors
        comps = await business_service.list_competitors(db=db_session, user_id=user.id)
        assert len(comps) >= 1
        assert any(c.id == comp.id for c in comps)

    @pytest.mark.asyncio
    async def test_executive_report_generation(
        self,
        db_session: AsyncSession,
        user: User,
        business_service: BusinessService,
    ):
        rep_req = GenerateBusinessReportRequest(
            title="Q4 AI Operations Expansion Brief",
            report_type="MARKET_ANALYSIS",
            target_companies=["Acme Corp", "Starlight Robotics"],
            key_objectives="Scale sovereign enterprise adoption and reduce churn.",
        )
        report = await business_service.generate_report(
            db=db_session,
            user_id=user.id,
            request=rep_req,
        )
        assert report.title == "Q4 AI Operations Expansion Brief"
        assert report.report_type == "MARKET_ANALYSIS"
        assert "Acme Corp" in report.summary
        assert "## 1. Executive Summary" in report.content
        assert "## 3. Financial & Performance Metrics" in report.content
        assert len(report.recommendations) >= 2
        assert report.privacy_scope == "BUSINESS"

        # List reports
        reps = await business_service.list_reports(db=db_session, user_id=user.id)
        assert len(reps) >= 1
        assert any(r.id == report.id for r in reps)

    def test_privacy_scope_firewall_enforcement(self, business_service: BusinessService):
        # BUSINESS data cannot leak into PERSONAL scope without explicit bridge
        assert business_service.agent.verify_business_scope_isolation(PrivacyScope.PERSONAL) is False

        # BUSINESS data can flow into compatible BUSINESS or AGENT scopes
        assert business_service.agent.verify_business_scope_isolation(PrivacyScope.BUSINESS) is True
        assert business_service.agent.verify_business_scope_isolation(PrivacyScope.AGENT) is True

    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self,
        db_session: AsyncSession,
        user: User,
        business_service: BusinessService,
    ):
        lead = await business_service.create_lead(
            db=db_session,
            user_id=user.id,
            request=CreateLeadRequest(company_name="Private Lead"),
        )
        comp = await business_service.create_competitor(
            db=db_session,
            user_id=user.id,
            request=CreateCompetitorRequest(name="Private Comp", website="https://c.io"),
        )
        rep = await business_service.generate_report(
            db=db_session,
            user_id=user.id,
            request=GenerateBusinessReportRequest(title="Private Report"),
        )

        other_user_id = uuid.uuid4()
        with pytest.raises(EntityNotFoundError):
            await business_service.get_lead(db=db_session, user_id=other_user_id, lead_id=lead.id)

        with pytest.raises(EntityNotFoundError):
            await business_service.get_competitor(db=db_session, user_id=other_user_id, competitor_id=comp.id)

        with pytest.raises(EntityNotFoundError):
            await business_service.get_report(db=db_session, user_id=other_user_id, report_id=rep.id)

    @pytest.mark.asyncio
    async def test_audit_trail_recorded(
        self,
        db_session: AsyncSession,
        user: User,
        business_service: BusinessService,
    ):
        await business_service.create_lead(
            db=db_session,
            user_id=user.id,
            request=CreateLeadRequest(company_name="Audit Lead"),
        )
        await business_service.create_competitor(
            db=db_session,
            user_id=user.id,
            request=CreateCompetitorRequest(name="Audit Comp", website="https://a.io"),
        )
        await business_service.generate_report(
            db=db_session,
            user_id=user.id,
            request=GenerateBusinessReportRequest(title="Audit Brief"),
        )

        stmt = AuditLog.__table__.select().where(AuditLog.user_id == user.id)
        result = await db_session.execute(stmt)
        rows = result.fetchall()
        action_types = [r.action_type for r in rows]
        assert "business.lead_create" in action_types
        assert "business.competitor_track" in action_types
        assert "business.report_generate" in action_types
