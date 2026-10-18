"""REST API router for Browser & Computer Agent sessions, navigation, DOM extraction, and approvals."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.user import User
from app.services.browser.schemas import (
    BrowserActionResponse,
    BrowserSessionSummary,
    CaptureScreenshotRequest,
    CreateBrowserSessionRequest,
    FillFormRequest,
    FillFormResponse,
    NavigateRequest,
    NavigateResponse,
    ReadPageResponse,
    ScreenshotResponse,
    SubmitFormRequest,
    SubmitFormResponse,
)
from app.services.browser.service import BrowserService

router = APIRouter(prefix="/browser", tags=["Browser & Computer Agent"])
_browser_service = BrowserService()


@router.post("/sessions", response_model=BrowserSessionSummary)
async def create_browser_session(
    payload: CreateBrowserSessionRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> BrowserSessionSummary:
    """Create a new user-scoped browser interaction session."""
    current_user, session_id = auth
    try:
        return await _browser_service.create_session(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=session_id,
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/sessions", response_model=List[BrowserSessionSummary])
async def list_browser_sessions(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[BrowserSessionSummary]:
    """List browser interaction sessions for the authenticated user."""
    current_user, _ = auth
    return await _browser_service.list_user_sessions(
        db=db,
        user_id=current_user.id,
    )


@router.get("/sessions/{session_id}", response_model=BrowserSessionSummary)
async def get_browser_session(
    session_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> BrowserSessionSummary:
    """Retrieve details for a specific browser session."""
    current_user, _ = auth
    try:
        session_rec = await _browser_service.get_session(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
        return BrowserSessionSummary(
            id=session_rec.id,
            user_id=session_rec.user_id,
            title=session_rec.title,
            current_url=session_rec.current_url,
            status=session_rec.status,
            viewport_width=session_rec.viewport_width,
            viewport_height=session_rec.viewport_height,
            created_at=session_rec.created_at.isoformat(),
            updated_at=session_rec.updated_at.isoformat(),
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Browser session not found.")


@router.post("/sessions/{session_id}/navigate", response_model=NavigateResponse)
async def navigate_browser(
    session_id: uuid.UUID,
    payload: NavigateRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> NavigateResponse:
    """Navigate browser to target URL with SSRF/loopback blocklist validation."""
    current_user, auth_session_id = auth
    try:
        return await _browser_service.navigate(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Browser session not found.")
    except ValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/sessions/{session_id}/page", response_model=ReadPageResponse)
async def read_browser_page(
    session_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> ReadPageResponse:
    """Extract page text and structured elements wrapped in security delimiter tags."""
    current_user, auth_session_id = auth
    try:
        return await _browser_service.read_page(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            session_id_auth=auth_session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Browser session not found.")
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/sessions/{session_id}/fill", response_model=FillFormResponse)
async def fill_browser_form(
    session_id: uuid.UUID,
    payload: FillFormRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> FillFormResponse:
    """Fill input field on current page."""
    current_user, auth_session_id = auth
    try:
        return await _browser_service.fill_form(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Browser session not found.")
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/sessions/{session_id}/submit", response_model=SubmitFormResponse)
async def submit_browser_form(
    session_id: uuid.UUID,
    payload: SubmitFormRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> SubmitFormResponse:
    """Submit interactive form under consequential Policy Broker approval gate."""
    current_user, auth_session_id = auth
    try:
        return await _browser_service.submit_form(
            db=db,
            user=current_user,
            session_id=session_id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Browser session not found.")
    except PermissionDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/sessions/{session_id}/screenshot", response_model=ScreenshotResponse)
async def capture_browser_screenshot(
    session_id: uuid.UUID,
    payload: CaptureScreenshotRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> ScreenshotResponse:
    """Capture base64 visual screenshot for human review and auditing."""
    current_user, auth_session_id = auth
    try:
        return await _browser_service.capture_screenshot(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Browser session not found.")
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/sessions/{session_id}/screenshots", response_model=List[ScreenshotResponse])
async def list_browser_screenshots(
    session_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[ScreenshotResponse]:
    """List screenshots captured for a session."""
    current_user, _ = auth
    try:
        return await _browser_service.list_screenshots(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Browser session not found.")


@router.get("/sessions/{session_id}/actions", response_model=List[BrowserActionResponse])
async def list_browser_actions(
    session_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[BrowserActionResponse]:
    """List audit actions recorded for a session."""
    current_user, _ = auth
    try:
        return await _browser_service.list_actions(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Browser session not found.")
