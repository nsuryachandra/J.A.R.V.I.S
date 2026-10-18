"""REST API router for Background Scheduling & Jobs: Render Cron integration and job management."""

import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, ValidationError
from app.models.user import User
from app.services.jobs.runner import JobRunnerService
from app.services.jobs.schemas import (
    CronWebhookRequest,
    CronWebhookResponse,
    JobRunResponse,
    TriggerJobRequest,
)

router = APIRouter(prefix="/jobs", tags=["Background Scheduling & Jobs"])


@router.post("/cron", response_model=CronWebhookResponse)
async def trigger_cron_job(
    payload: CronWebhookRequest,
    x_cron_secret: Optional[str] = Header(default=None, alias="X-Cron-Secret"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db_session),
) -> CronWebhookResponse:
    """
    Webhook endpoint for Render Cron jobs or external schedulers.
    Requires shared secret via 'X-Cron-Secret' header or 'Authorization: Bearer <secret>'.
    """
    settings = get_settings()
    configured_secret = settings.cron_secret

    # Verify secret
    provided_secret = None
    if x_cron_secret:
        provided_secret = x_cron_secret.strip()
    elif authorization and authorization.startswith("Bearer "):
        provided_secret = authorization.replace("Bearer ", "").strip()

    if not provided_secret or provided_secret != configured_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing cron authentication secret.",
        )

    try:
        job_run = await JobRunnerService.execute_job(
            db=db,
            job_type=payload.job_type,
            user_id=None,  # system-wide run across all users
            idempotency_key=payload.idempotency_key,
            force=payload.force,
        )
        parsed_details = json.loads(job_run.details) if job_run.details else None
        return CronWebhookResponse(
            success=job_run.status in ("SUCCESS", "SKIPPED"),
            job_type=job_run.job_type,
            message=f"Cron job {job_run.job_type} finished with status {job_run.status}.",
            job_run_id=job_run.id,
            status=job_run.status,
            details=parsed_details,
        )
    except ValidationError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))


@router.post("/trigger", response_model=JobRunResponse)
async def trigger_user_job(
    payload: TriggerJobRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> JobRunResponse:
    """Trigger background job execution specifically for authenticated user."""
    current_user, auth_session_id = auth
    target_uid = payload.target_user_id or current_user.id

    # Enforce tenant boundary: regular users cannot trigger jobs targeting other users
    if target_uid != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot trigger background job for another user.",
        )

    try:
        job_run = await JobRunnerService.execute_job(
            db=db,
            job_type=payload.job_type,
            user_id=target_uid,
            idempotency_key=payload.idempotency_key,
            force=payload.force,
            session_id_auth=auth_session_id,
        )
        parsed_details = json.loads(job_run.details) if job_run.details else None
        return JobRunResponse(
            id=job_run.id,
            job_type=job_run.job_type,
            status=job_run.status,
            idempotency_key=job_run.idempotency_key,
            target_user_id=job_run.target_user_id,
            started_at=job_run.started_at.isoformat(),
            completed_at=job_run.completed_at.isoformat() if job_run.completed_at else None,
            duration_ms=job_run.duration_ms,
            details=parsed_details,
            error_message=job_run.error_message,
            created_at=job_run.created_at.isoformat(),
            updated_at=job_run.updated_at.isoformat(),
        )
    except ValidationError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))


@router.get("/runs", response_model=List[JobRunResponse])
async def list_job_runs(
    job_type: Optional[str] = Query(default=None, alias="type"),
    limit: int = Query(default=50, ge=1, le=100),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[JobRunResponse]:
    """List background job execution history with tenant isolation."""
    current_user, _ = auth
    return await JobRunnerService.list_job_runs(
        db=db,
        user_id=current_user.id,
        job_type=job_type,
        limit=limit,
    )


@router.get("/runs/{run_id}", response_model=JobRunResponse)
async def get_job_run(
    run_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> JobRunResponse:
    """Retrieve details of a specific job run."""
    current_user, _ = auth
    try:
        return await JobRunnerService.get_job_run(
            db=db,
            job_run_id=run_id,
            user_id=current_user.id,
        )
    except EntityNotFoundError as enf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(enf))
