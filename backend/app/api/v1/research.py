"""REST API endpoints for Research and Writing Agents."""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.models.user import User
from app.services.research.schemas import (
    DocumentExportResponse,
    DocumentResponse,
    DraftDocumentRequest,
    ResearchBriefResult,
    ResearchExecutionRequest,
    ResearchSessionSummary,
    WebSearchRequest,
    WebSearchResponse,
)
from app.services.research.service import ResearchService

router = APIRouter(prefix="/research", tags=["Research & Writing Agents"])
_research_service = ResearchService()


@router.post("/search", response_model=WebSearchResponse)
async def search_sources(
    payload: WebSearchRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> WebSearchResponse:
    """Search approved research sources with quality ranking, validation, and audit trail."""
    current_user, session_id = auth
    return await _research_service.search_sources(
        db=db,
        user_id=current_user.id,
        request=payload,
        session_id=session_id,
    )


@router.post("/run", response_model=ResearchBriefResult)
async def execute_research(
    payload: ResearchExecutionRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> ResearchBriefResult:
    """Execute end-to-end multi-source research investigation, fact extraction, and citation mapping."""
    current_user, session_id = auth
    return await _research_service.execute_research(
        db=db,
        user_id=current_user.id,
        topic=payload.topic,
        query=payload.query,
        session_id=session_id,
    )


@router.get("/sessions", response_model=List[ResearchSessionSummary])
async def list_research_sessions(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[ResearchSessionSummary]:
    """Retrieve historical research investigations for the authenticated user."""
    current_user, _ = auth
    return await _research_service.list_user_sessions(
        db=db,
        user_id=current_user.id,
    )


@router.get("/sessions/{session_id}", response_model=ResearchBriefResult)
async def get_research_session(
    session_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> ResearchBriefResult:
    """Retrieve full details, facts, and sources for a specific research session."""
    current_user, _ = auth
    detail = await _research_service.get_session_details(
        db=db,
        user_id=current_user.id,
        session_id=session_id,
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found.",
        )
    return detail


@router.post("/documents/draft", response_model=DocumentResponse)
async def draft_document(
    payload: DraftDocumentRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    """Draft a structured, publication-grade document grounded in research facts and citations."""
    current_user, session_id = auth
    return await _research_service.draft_document(
        db=db,
        user_id=current_user.id,
        request=payload,
        session_id_auth=session_id,
    )


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[DocumentResponse]:
    """List all generated document artifacts for the authenticated user."""
    current_user, _ = auth
    return await _research_service.list_user_documents(
        db=db,
        user_id=current_user.id,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    """Retrieve a single generated document artifact by ID."""
    current_user, _ = auth
    doc = await _research_service.get_document(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document artifact not found.",
        )
    return doc


@router.get("/documents/{document_id}/export", response_model=DocumentExportResponse)
async def export_document(
    document_id: uuid.UUID,
    export_format: str = Query(default="html", pattern="^(html|markdown|text)$"),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentExportResponse:
    """Export a document artifact to HTML or Markdown format."""
    current_user, _ = auth
    exported = await _research_service.export_document(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
        export_format=export_format,
    )
    if not exported:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document artifact not found.",
        )
    return exported
