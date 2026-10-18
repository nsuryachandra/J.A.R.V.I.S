"""REST API router for Business & Productivity Agent operations: Leads, Competitors, and Reports."""

import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, ValidationError
from app.models.user import User
from app.services.business.schemas import (
    BusinessLeadResponse,
    BusinessReportResponse,
    CompetitorResponse,
    CreateCompetitorRequest,
    CreateLeadRequest,
    GenerateBusinessReportRequest,
)
from app.services.business.service import BusinessService

router = APIRouter(prefix="/business", tags=["Business & Productivity Agents"])
_business_service = BusinessService()


# --- Leads ---


@router.post("/leads", response_model=BusinessLeadResponse)
async def create_business_lead(
    payload: CreateLeadRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> BusinessLeadResponse:
    """Create and automatically enrich a prospective business lead."""
    current_user, auth_session_id = auth
    try:
        return await _business_service.create_lead(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/leads", response_model=List[BusinessLeadResponse])
async def list_business_leads(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    industry_filter: Optional[str] = Query(default=None, alias="industry"),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[BusinessLeadResponse]:
    """List business leads for authenticated user with optional status and industry filtering."""
    current_user, _ = auth
    return await _business_service.list_leads(
        db=db,
        user_id=current_user.id,
        status=status_filter,
        industry=industry_filter,
    )


@router.get("/leads/{lead_id}", response_model=BusinessLeadResponse)
async def get_business_lead(
    lead_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> BusinessLeadResponse:
    """Retrieve details for a specific business lead."""
    current_user, _ = auth
    try:
        lead = await _business_service.get_lead(
            db=db,
            user_id=current_user.id,
            lead_id=lead_id,
        )
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
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business lead not found.")


# --- Competitors ---


@router.post("/competitors", response_model=CompetitorResponse)
async def create_competitor(
    payload: CreateCompetitorRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> CompetitorResponse:
    """Register and analyze a market competitor."""
    current_user, auth_session_id = auth
    try:
        return await _business_service.create_competitor(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/competitors", response_model=List[CompetitorResponse])
async def list_competitors(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[CompetitorResponse]:
    """List tracked market competitors for authenticated user."""
    current_user, _ = auth
    return await _business_service.list_competitors(
        db=db,
        user_id=current_user.id,
    )


@router.get("/competitors/{competitor_id}", response_model=CompetitorResponse)
async def get_competitor(
    competitor_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> CompetitorResponse:
    """Retrieve details for a specific competitor profile."""
    current_user, _ = auth
    try:
        c = await _business_service.get_competitor(
            db=db,
            user_id=current_user.id,
            competitor_id=competitor_id,
        )
        s_list = json.loads(c.strengths) if c.strengths else []
        w_list = json.loads(c.weaknesses) if c.weaknesses else []
        return CompetitorResponse(
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
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor profile not found.")


# --- Reports ---


@router.post("/reports", response_model=BusinessReportResponse)
async def generate_business_report(
    payload: GenerateBusinessReportRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> BusinessReportResponse:
    """Generate and store a structured executive business intelligence report."""
    current_user, auth_session_id = auth
    try:
        return await _business_service.generate_report(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/reports", response_model=List[BusinessReportResponse])
async def list_business_reports(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[BusinessReportResponse]:
    """List generated business reports for authenticated user."""
    current_user, _ = auth
    return await _business_service.list_reports(
        db=db,
        user_id=current_user.id,
    )


@router.get("/reports/{report_id}", response_model=BusinessReportResponse)
async def get_business_report(
    report_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> BusinessReportResponse:
    """Retrieve details for a specific business report."""
    current_user, _ = auth
    try:
        r = await _business_service.get_report(
            db=db,
            user_id=current_user.id,
            report_id=report_id,
        )
        recs = json.loads(r.recommendations) if r.recommendations else []
        return BusinessReportResponse(
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
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business report not found.")
