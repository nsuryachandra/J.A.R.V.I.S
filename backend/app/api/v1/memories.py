"""REST API endpoints for declarative memory management and semantic retrieval."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.models.memory import Memory
from app.models.user import User
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memories", tags=["Memory & Personal Context"])


# Request and Response Models


class CreateMemoryRequest(BaseModel):
    """Payload to create or propose a memory."""

    content: str = Field(min_length=1, max_length=8192)
    memory_type: str = Field(default="SEMANTIC")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    confirmed_by_user: bool = Field(default=False)
    status: str = Field(default="ACTIVE")
    privacy_scope: str = Field(default="PERSONAL")
    sensitivity: int = Field(default=30)
    source_type: str = Field(default="USER_DIRECT")
    source_id: Optional[str] = None
    provenance_evidence: Optional[str] = None
    valid_until: Optional[datetime] = None


class UpdateMemoryRequest(BaseModel):
    """Payload to update an existing memory."""

    content: Optional[str] = Field(default=None, min_length=1, max_length=8192)
    privacy_scope: Optional[str] = None
    sensitivity: Optional[int] = None
    valid_until: Optional[datetime] = None


class CorrectMemoryRequest(BaseModel):
    """Payload to correct and supersede an existing memory."""

    corrected_content: str = Field(min_length=1, max_length=8192)
    reason: str = Field(min_length=1, max_length=1024)


class ForgetMemoryRequest(BaseModel):
    """Payload to forget an existing memory."""

    reason: str = Field(default="User requested deletion", min_length=1, max_length=1024)


class MemorySearchRequest(BaseModel):
    """Payload for hybrid semantic memory search."""

    query: str = Field(min_length=1, max_length=512)
    memory_type: Optional[str] = None
    allowed_scopes: Optional[List[str]] = None
    max_sensitivity: int = Field(default=30)
    limit: int = Field(default=10, ge=1, le=50)
    threshold: float = Field(default=0.15, ge=0.0, le=1.0)


class MemoryResponse(BaseModel):
    """Public serialization of a memory record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    memory_type: str
    content: str
    status: str
    confidence: float
    confirmed_by_user: bool
    valid_from: datetime
    valid_until: Optional[datetime] = None
    superseded_by_id: Optional[UUID] = None
    privacy_scope: str
    sensitivity: int
    source_type: str
    provenance_evidence: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MemorySearchResultItem(BaseModel):
    """Scored memory search outcome."""

    memory: MemoryResponse
    score: float


# Endpoints


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or propose a memory",
)
async def create_memory(
    payload: CreateMemoryRequest,
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> MemoryResponse:
    """Create a persistent memory record linked to the authenticated user."""
    current_user, session_id = auth_context

    memory = await MemoryService.create_memory(
        db=db,
        user_id=current_user.id,
        content=payload.content,
        memory_type=payload.memory_type,
        confidence=payload.confidence,
        status=payload.status,
        confirmed_by_user=payload.confirmed_by_user,
        privacy_scope=payload.privacy_scope,
        sensitivity=payload.sensitivity,
        source_type=payload.source_type,
        source_id=payload.source_id,
        provenance_evidence=payload.provenance_evidence,
        valid_until=payload.valid_until,
        session_id=session_id,
    )
    return MemoryResponse.model_validate(memory)


@router.get(
    "",
    response_model=List[MemoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List authenticated user's memories",
)
async def list_memories(
    memory_type: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    privacy_scope: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[MemoryResponse]:
    """Retrieve memories scoped strictly to the authenticated user with optional filters."""
    current_user, _ = auth_context

    stmt = select(Memory).where(Memory.user_id == current_user.id)
    if memory_type:
        stmt = stmt.where(Memory.memory_type == memory_type)
    if status_filter:
        stmt = stmt.where(Memory.status == status_filter)
    else:
        # Default to ACTIVE and CONFIRMED (exclude DELETED and SUPERSEDED unless explicitly requested)
        stmt = stmt.where(Memory.status.in_(["ACTIVE", "CONFIRMED", "CANDIDATE"]))
    if privacy_scope:
        stmt = stmt.where(Memory.privacy_scope == privacy_scope)

    stmt = stmt.order_by(Memory.updated_at.desc()).limit(limit)
    res = await db.execute(stmt)
    memories = res.scalars().all()
    return [MemoryResponse.model_validate(m) for m in memories]


@router.get(
    "/{memory_id}",
    response_model=MemoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get memory by ID",
)
async def get_memory(
    memory_id: UUID,
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> MemoryResponse:
    """Retrieve a single memory record verifying user ownership."""
    current_user, _ = auth_context
    memory = await MemoryService.get_memory_by_id(db, memory_id, current_user.id)
    return MemoryResponse.model_validate(memory)


@router.patch(
    "/{memory_id}",
    response_model=MemoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update memory",
)
async def update_memory(
    memory_id: UUID,
    payload: UpdateMemoryRequest,
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> MemoryResponse:
    """Update fields on an existing memory record with change history."""
    current_user, session_id = auth_context
    memory = await MemoryService.update_memory(
        db=db,
        memory_id=memory_id,
        user_id=current_user.id,
        new_content=payload.content,
        privacy_scope=payload.privacy_scope,
        sensitivity=payload.sensitivity,
        valid_until=payload.valid_until,
        session_id=session_id,
    )
    return MemoryResponse.model_validate(memory)


@router.post(
    "/{memory_id}/confirm",
    response_model=MemoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm a candidate memory",
)
async def confirm_memory(
    memory_id: UUID,
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> MemoryResponse:
    """Confirm a proposed candidate memory and transition to ACTIVE."""
    current_user, session_id = auth_context
    memory = await MemoryService.confirm_memory(
        db=db,
        memory_id=memory_id,
        user_id=current_user.id,
        session_id=session_id,
    )
    return MemoryResponse.model_validate(memory)


@router.post(
    "/{memory_id}/correct",
    response_model=MemoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Correct and supersede memory",
)
async def correct_memory(
    memory_id: UUID,
    payload: CorrectMemoryRequest,
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> MemoryResponse:
    """Supersede existing memory with user-provided correction."""
    current_user, session_id = auth_context
    _, new_mem = await MemoryService.correct_memory(
        db=db,
        memory_id=memory_id,
        user_id=current_user.id,
        corrected_content=payload.corrected_content,
        reason=payload.reason,
        session_id=session_id,
    )
    return MemoryResponse.model_validate(new_mem)


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Forget memory (Right to be Forgotten)",
)
async def forget_memory(
    memory_id: UUID,
    payload: Optional[ForgetMemoryRequest] = None,
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Right-to-be-forgotten deletion marking memory DELETED and auditing action."""
    current_user, session_id = auth_context
    reason = payload.reason if payload else "User requested deletion"
    await MemoryService.forget_memory(
        db=db,
        memory_id=memory_id,
        user_id=current_user.id,
        reason=reason,
        session_id=session_id,
    )


@router.post(
    "/search",
    response_model=List[MemorySearchResultItem],
    status_code=status.HTTP_200_OK,
    summary="Semantic and hybrid memory search",
)
async def search_memories(
    payload: MemorySearchRequest,
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[MemorySearchResultItem]:
    """Search user memories using vector similarity, keyword matching, and privacy filters."""
    current_user, _ = auth_context
    results = await MemoryService.search_memories(
        db=db,
        user_id=current_user.id,
        query=payload.query,
        memory_type=payload.memory_type,
        allowed_scopes=payload.allowed_scopes,
        max_sensitivity=payload.max_sensitivity,
        limit=payload.limit,
        threshold=payload.threshold,
    )
    return [
        MemorySearchResultItem(
            memory=MemoryResponse.model_validate(mem),
            score=score,
        )
        for mem, score in results
    ]
