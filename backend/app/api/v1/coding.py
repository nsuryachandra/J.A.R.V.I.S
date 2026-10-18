"""REST API router for Coding Agent workspace sessions, inspection, diffs, proposals, and sandboxed test execution."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.models.user import User
from app.services.coding.schemas import (
    ApplyChangeRequest,
    ApplyChangeResponse,
    CodeChangeProposalResponse,
    CodingSessionSummary,
    CreateCodingSessionRequest,
    InspectCodeRequest,
    InspectCodeResponse,
    ProposeChangeRequest,
    RunTestsRequest,
    TestExecutionResponse,
)
from app.services.coding.service import CodingService

router = APIRouter(prefix="/coding", tags=["Coding Agent"])
_coding_service = CodingService()


@router.post("/sessions", response_model=CodingSessionSummary)
async def create_coding_session(
    payload: CreateCodingSessionRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> CodingSessionSummary:
    """Create a new coding workspace session."""
    current_user, session_id = auth
    try:
        return await _coding_service.create_session(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=session_id,
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/sessions", response_model=List[CodingSessionSummary])
async def list_coding_sessions(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[CodingSessionSummary]:
    """List historical coding sessions for the authenticated user."""
    current_user, _ = auth
    return await _coding_service.list_user_sessions(
        db=db,
        user_id=current_user.id,
    )


@router.get("/sessions/{session_id}", response_model=CodingSessionSummary)
async def get_coding_session(
    session_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> CodingSessionSummary:
    """Retrieve details for a specific coding session."""
    current_user, _ = auth
    session_rec = await _coding_service.get_session(
        db=db,
        user_id=current_user.id,
        session_id=session_id,
    )
    if not session_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coding session not found.",
        )

    return CodingSessionSummary(
        id=session_rec.id,
        user_id=session_rec.user_id,
        workspace_path=session_rec.workspace_path,
        title=session_rec.title,
        status=session_rec.status,
        proposals_count=len(session_rec.proposals),
        created_at=session_rec.created_at.isoformat() if session_rec.created_at else "",
    )


@router.post("/inspect", response_model=InspectCodeResponse)
async def inspect_code(
    payload: InspectCodeRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> InspectCodeResponse:
    """Inspect workspace code files, AST classes/functions, and syntax validity."""
    current_user, session_id = auth
    try:
        return await _coding_service.inspect_code(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=session_id,
        )
    except (ValueError, FileNotFoundError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/proposals", response_model=CodeChangeProposalResponse)
async def propose_change(
    payload: ProposeChangeRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> CodeChangeProposalResponse:
    """Create a refactoring change proposal with a generated unified git diff."""
    current_user, session_id = auth
    try:
        return await _coding_service.propose_change(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=session_id,
        )
    except EntityNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/proposals", response_model=List[CodeChangeProposalResponse])
async def list_proposals(
    session_id: Optional[uuid.UUID] = Query(default=None),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[CodeChangeProposalResponse]:
    """List code refactoring proposals for the authenticated user."""
    current_user, _ = auth
    return await _coding_service.list_proposals(
        db=db,
        user_id=current_user.id,
        session_id=session_id,
    )


@router.get("/proposals/{proposal_id}", response_model=CodeChangeProposalResponse)
async def get_proposal(
    proposal_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> CodeChangeProposalResponse:
    """Retrieve details and diff for a specific change proposal."""
    current_user, _ = auth
    proposal = await _coding_service.get_proposal(
        db=db,
        user_id=current_user.id,
        proposal_id=proposal_id,
    )
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Code change proposal not found.",
        )

    return CodeChangeProposalResponse(
        id=proposal.id,
        session_id=proposal.session_id,
        user_id=proposal.user_id,
        title=proposal.title,
        description=proposal.description,
        target_file=proposal.target_file,
        diff_content=proposal.diff_content,
        status=proposal.status,
        approval_id=proposal.approval_id,
        applied_at=proposal.applied_at.isoformat() if proposal.applied_at else None,
        created_at=proposal.created_at.isoformat() if proposal.created_at else "",
    )


@router.post("/proposals/{proposal_id}/apply", response_model=ApplyChangeResponse)
async def apply_proposal(
    proposal_id: uuid.UUID,
    payload: ApplyChangeRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> ApplyChangeResponse:
    """Apply an approved code change proposal directly to the target file."""
    current_user, session_id = auth
    try:
        return await _coding_service.apply_change(
            db=db,
            user=current_user,
            proposal_id=proposal_id,
            approval_id=payload.approval_id,
            dry_run=payload.dry_run,
            session_id_auth=session_id,
        )
    except EntityNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except PermissionDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/tests/run", response_model=TestExecutionResponse)
async def run_sandboxed_tests(
    payload: RunTestsRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> TestExecutionResponse:
    """Run sandboxed pytest suite with resource bounds, timeouts, and result parsing."""
    current_user, session_id = auth
    try:
        return await _coding_service.run_tests(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=session_id,
        )
    except FileNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
