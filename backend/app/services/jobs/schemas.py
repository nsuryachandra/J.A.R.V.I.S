"""Pydantic schemas and contracts for Background Scheduling & Jobs."""

import uuid
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class JobType(str, Enum):
    """Supported background scheduled and cron job types."""

    MORNING_BRIEFING = "MORNING_BRIEFING"
    EVENING_BRIEFING = "EVENING_BRIEFING"
    NIGHTLY_CONSOLIDATION = "NIGHTLY_CONSOLIDATION"
    SCHEDULER_TICK = "SCHEDULER_TICK"
    STALE_TASK_SWEEP = "STALE_TASK_SWEEP"


class JobRunStatus(str, Enum):
    """Lifecycle status of a background job execution."""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TriggerJobRequest(BaseModel):
    """Payload to request execution of a background job."""

    job_type: str = Field(
        default="SCHEDULER_TICK",
        description="Job type: MORNING_BRIEFING, EVENING_BRIEFING, NIGHTLY_CONSOLIDATION, SCHEDULER_TICK, STALE_TASK_SWEEP",
    )
    target_user_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Target user ID to run for. If omitted by an authenticated user, defaults to their user ID.",
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Optional client idempotency key to prevent double execution",
    )
    force: bool = Field(
        default=False,
        description="Force execution even if an idempotent run was already recorded for the period",
    )


class JobRunResponse(BaseModel):
    """Detailed record of a background job execution."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: str
    status: str
    idempotency_key: str
    target_user_id: Optional[uuid.UUID] = None
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class CronWebhookRequest(BaseModel):
    """Payload sent by external Render Cron job or curl trigger."""

    job_type: str = Field(
        default="SCHEDULER_TICK",
        description="Job type to execute across system",
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Cron trigger unique execution key",
    )
    force: bool = Field(
        default=False,
        description="Force run bypassing duplicate schedule checks",
    )


class CronWebhookResponse(BaseModel):
    """Acknowledgment response for Render Cron trigger."""

    success: bool
    job_type: str
    message: str
    job_run_id: Optional[uuid.UUID] = None
    status: str
    details: Optional[Dict[str, Any]] = None
