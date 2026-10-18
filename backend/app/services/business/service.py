"""Domain service orchestrating Business & Productivity Agent operations: Leads, Competitors, and Reports."""

import json
import uuid
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import EntityNotFoundError, ValidationError
from app.models.business import BusinessLead, BusinessReport, CompetitorProfile
from app.models.base import utcnow
from app.services.audit_service import AuditService
from app.services.business.business_agent import BusinessAgent
from app.services.business.schemas import (
    BusinessLeadResponse,
    BusinessReportResponse,
    CompetitorResponse,
    CreateCompetitorRequest,
    CreateLeadRequest,
    GenerateBusinessReportRequest,
)
from app.services.policy_broker import PolicyBroker


class BusinessService:
    """Service managing business leads, competitive intelligence, and executive reporting."""

    def __init__(self, broker: Optional[PolicyBroker] = None):
        self._broker = broker or PolicyBroker()
        self._agent = BusinessAgent()

    @property
    def agent(self) -> BusinessAgent:
        return self._agent

    # --- Leads ---

    async def create_lead(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: CreateLeadRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> BusinessLeadResponse:
        """Create and automatically score/enrich a prospective business lead."""
        score, notes = self._agent.research_and_score_lead(
            company_name=request.company_name,
            industry=request.industry,
            website=request.website,
            contact_email=request.contact_email,
            auto_enrich=request.auto_enrich,
            custom_notes=request.enrichment_notes,
        )

        lead = BusinessLead(
            user_id=user_id,
            company_name=request.company_name,
            contact_name=request.contact_name,
            contact_email=request.contact_email,
            website=request.website,
            industry=request.industry,
            lead_score=score,
            status="RESEARCHED" if request.auto_enrich else "NEW",
            enrichment_notes=notes,
            privacy_scope="BUSINESS",
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="business.lead_create",
            resource_scope=f"business_lead:{lead.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "company_name": lead.company_name,
                "industry": lead.industry,
                "lead_score": lead.lead_score,
                "privacy_scope": lead.privacy_scope,
            },
        )
        await db.commit()

        return BusinessLeadResponse(
            id=lead.id,
            user_id=lead.user_id,
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            contact_email=lead.contact_email,
            website=lead.website,
            industry=lead.industry,
            lead_score=lead.lead_score,
            status=lead.status,
            enrichment_notes=lead.enrichment_notes,
            privacy_scope=lead.privacy_scope,
            created_at=lead.created_at.isoformat(),
            updated_at=lead.updated_at.isoformat(),
        )

    async def list_leads(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        status: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> List[BusinessLeadResponse]:
        """List user leads with optional filtering and tenant isolation."""
        stmt = select(BusinessLead).where(BusinessLead.user_id == user_id)
        if status:
            stmt = stmt.where(BusinessLead.status == status.upper())
        if industry:
            stmt = stmt.where(BusinessLead.industry == industry)
        stmt = stmt.order_by(desc(BusinessLead.lead_score), desc(BusinessLead.created_at))

        result = await db.execute(stmt)
        leads = result.scalars().all()

        return [
            BusinessLeadResponse(
                id=l.id,
                user_id=l.user_id,
                company_name=l.company_name,
                contact_name=l.contact_name,
                contact_email=l.contact_email,
                website=l.website,
                industry=l.industry,
                lead_score=l.lead_score,
                status=l.status,
                enrichment_notes=l.enrichment_notes,
                privacy_scope=l.privacy_scope,
                created_at=l.created_at.isoformat(),
                updated_at=l.updated_at.isoformat(),
            )
            for l in leads
        ]

    async def get_lead(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> BusinessLead:
        """Retrieve single lead ensuring user isolation."""
        stmt = select(BusinessLead).where(
            BusinessLead.id == lead_id,
            BusinessLead.user_id == user_id,
        )
        result = await db.execute(stmt)
        lead = result.scalar_one_or_none()
        if not lead:
            raise EntityNotFoundError("BusinessLead", lead_id)
        return lead

    # --- Competitors ---

    async def create_competitor(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: CreateCompetitorRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> CompetitorResponse:
        """Register and analyze a market competitor."""
        strengths, weaknesses, pricing, threat = self._agent.analyze_competitor_profile(
            name=request.name,
            website=request.website,
            market_segment=request.market_segment,
            initial_strengths=request.strengths,
            initial_weaknesses=request.weaknesses,
            initial_pricing=request.pricing_summary,
            auto_analyze=request.auto_analyze,
        )

        competitor = CompetitorProfile(
            user_id=user_id,
            name=request.name,
            website=request.website,
            market_segment=request.market_segment,
            threat_level=threat,
            strengths=json.dumps(strengths),
            weaknesses=json.dumps(weaknesses),
            pricing_summary=pricing,
            last_monitored_at=utcnow(),
            privacy_scope="BUSINESS",
        )
        db.add(competitor)
        await db.commit()
        await db.refresh(competitor)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="business.competitor_track",
            resource_scope=f"business_competitor:{competitor.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "name": competitor.name,
                "threat_level": competitor.threat_level,
                "market_segment": competitor.market_segment,
            },
        )
        await db.commit()

        return CompetitorResponse(
            id=competitor.id,
            user_id=competitor.user_id,
            name=competitor.name,
            website=competitor.website,
            market_segment=competitor.market_segment,
            threat_level=competitor.threat_level,
            strengths=strengths,
            weaknesses=weaknesses,
            pricing_summary=competitor.pricing_summary,
            last_monitored_at=competitor.last_monitored_at.isoformat() if competitor.last_monitored_at else None,
            privacy_scope=competitor.privacy_scope,
            created_at=competitor.created_at.isoformat(),
            updated_at=competitor.updated_at.isoformat(),
        )

    async def list_competitors(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[CompetitorResponse]:
        """List tracked competitors for authenticated user."""
        stmt = (
            select(CompetitorProfile)
            .where(CompetitorProfile.user_id == user_id)
            .order_by(desc(CompetitorProfile.created_at))
        )
        result = await db.execute(stmt)
        competitors = result.scalars().all()

        out: List[CompetitorResponse] = []
        for c in competitors:
            s_list = json.loads(c.strengths) if c.strengths else []
            w_list = json.loads(c.weaknesses) if c.weaknesses else []
            out.append(
                CompetitorResponse(
                    id=c.id,
                    user_id=c.user_id,
                    name=c.name,
                    website=c.website,
                    market_segment=c.market_segment,
                    threat_level=c.threat_level,
                    strengths=s_list,
                    weaknesses=w_list,
                    pricing_summary=c.pricing_summary,
                    last_monitored_at=c.last_monitored_at.isoformat() if c.last_monitored_at else None,
                    privacy_scope=c.privacy_scope,
                    created_at=c.created_at.isoformat(),
                    updated_at=c.updated_at.isoformat(),
                )
            )
        return out

    async def get_competitor(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        competitor_id: uuid.UUID,
    ) -> CompetitorProfile:
        """Retrieve single competitor profile ensuring user isolation."""
        stmt = select(CompetitorProfile).where(
            CompetitorProfile.id == competitor_id,
            CompetitorProfile.user_id == user_id,
        )
        result = await db.execute(stmt)
        competitor = result.scalar_one_or_none()
        if not competitor:
            raise EntityNotFoundError("CompetitorProfile", competitor_id)
        return competitor

    # --- Reports ---

    async def generate_report(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: GenerateBusinessReportRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> BusinessReportResponse:
        """Compile and store an executive business intelligence report."""
        summary, content, recommendations = self._agent.generate_executive_report(
            title=request.title,
            report_type=request.report_type,
            target_companies=request.target_companies,
            key_objectives=request.key_objectives,
        )

        report = BusinessReport(
            user_id=user_id,
            title=request.title,
            report_type=request.report_type.upper(),
            summary=summary,
            content=content,
            recommendations=json.dumps(recommendations),
            privacy_scope="BUSINESS",
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="business.report_generate",
            resource_scope=f"business_report:{report.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "title": report.title,
                "report_type": report.report_type,
                "recommendations_count": len(recommendations),
            },
        )
        await db.commit()

        return BusinessReportResponse(
            id=report.id,
            user_id=report.user_id,
            title=report.title,
            report_type=report.report_type,
            summary=report.summary,
            content=report.content,
            recommendations=recommendations,
            privacy_scope=report.privacy_scope,
            created_at=report.created_at.isoformat(),
            updated_at=report.updated_at.isoformat(),
        )

    async def list_reports(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[BusinessReportResponse]:
        """List generated business reports for authenticated user."""
        stmt = (
            select(BusinessReport)
            .where(BusinessReport.user_id == user_id)
            .order_by(desc(BusinessReport.created_at))
        )
        result = await db.execute(stmt)
        reports = result.scalars().all()

        out: List[BusinessReportResponse] = []
        for r in reports:
            recs = json.loads(r.recommendations) if r.recommendations else []
            out.append(
                BusinessReportResponse(
                    id=r.id,
                    user_id=r.user_id,
                    title=r.title,
                    report_type=r.report_type,
                    summary=r.summary,
                    content=r.content,
                    recommendations=recs,
                    privacy_scope=r.privacy_scope,
                    created_at=r.created_at.isoformat(),
                    updated_at=r.updated_at.isoformat(),
                )
            )
        return out

    async def get_report(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        report_id: uuid.UUID,
    ) -> BusinessReport:
        """Retrieve single business report ensuring user isolation."""
        stmt = select(BusinessReport).where(
            BusinessReport.id == report_id,
            BusinessReport.user_id == user_id,
        )
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()
        if not report:
            raise EntityNotFoundError("BusinessReport", report_id)
        return report
