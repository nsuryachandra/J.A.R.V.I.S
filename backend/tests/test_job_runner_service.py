"""Unit and domain integration tests for Background Scheduling & Jobs runner."""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import EntityNotFoundError, ValidationError
from app.models.base import utcnow
from app.models.event import Routine
from app.models.job import JobRun
from app.models.memory import Memory
from app.models.task import Task
from app.models.user import User
from app.services.event_service import EventService
from app.services.jobs.runner import JobRunnerService
from app.services.jobs.schemas import JobType


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    """Create primary test user."""
    u = User(
        id=uuid.uuid4(),
        email=f"job_user_{uuid.uuid4().hex[:6]}@jarvis.ai",
        hashed_password="hashed_pw_test",
        timezone="Asia/Kolkata",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create second user for tenant isolation testing."""
    u = User(
        id=uuid.uuid4(),
        email=f"job_other_{uuid.uuid4().hex[:6]}@jarvis.ai",
        hashed_password="hashed_pw_test",
        timezone="Asia/Kolkata",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


class TestJobRunnerService:
    """Domain tests for background jobs, briefings, consolidation, scheduler ticks, and idempotency."""

    @pytest.mark.asyncio
    async def test_morning_briefing_job_execution(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Verify MORNING_BRIEFING execution dispatches briefing and records JobRun."""
        idemp = f"morning_test_{uuid.uuid4().hex[:8]}"
        run = await JobRunnerService.execute_job(
            db=db_session,
            job_type=JobType.MORNING_BRIEFING.value,
            user_id=user.id,
            idempotency_key=idemp,
        )

        assert run.job_type == "MORNING_BRIEFING"
        assert run.status == "SUCCESS"
        assert run.idempotency_key == idemp
        assert run.duration_ms is not None
        assert run.target_user_id == user.id
        assert run.error_message is None
        assert "briefings_dispatched" in run.details

    @pytest.mark.asyncio
    async def test_evening_briefing_job_execution(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Verify EVENING_BRIEFING execution records successful completion."""
        idemp = f"evening_test_{uuid.uuid4().hex[:8]}"
        run = await JobRunnerService.execute_job(
            db=db_session,
            job_type=JobType.EVENING_BRIEFING.value,
            user_id=user.id,
            idempotency_key=idemp,
        )

        assert run.job_type == "EVENING_BRIEFING"
        assert run.status == "SUCCESS"
        assert run.idempotency_key == idemp
        assert run.duration_ms is not None
        assert "briefings_dispatched" in run.details

    @pytest.mark.asyncio
    async def test_nightly_consolidation_job(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Verify NIGHTLY_CONSOLIDATION expands routine occurrences and archives expired memories."""
        # 1. Create a routine for the user
        routine = await EventService.create_routine(
            db=db_session,
            user_id=user.id,
            title="Nightly Reading",
            recurrence_rule="FREQ=DAILY;INTERVAL=1",
            dtstart_local="2026-10-18T21:30:00",
            target_time="21:30:00",
            timezone_name=user.timezone,
            expand_days=3,
        )

        # 2. Create an expired memory
        past_time = utcnow() - timedelta(days=2)
        expired_mem = Memory(
            user_id=user.id,
            content="Temporary transit code 9928",
            memory_type="SEMANTIC",
            confidence=1.0,
            status="ACTIVE",
            valid_until=past_time,
        )
        db_session.add(expired_mem)
        await db_session.commit()

        # 3. Execute consolidation job
        idemp = f"consolidation_test_{uuid.uuid4().hex[:8]}"
        run = await JobRunnerService.execute_job(
            db=db_session,
            job_type=JobType.NIGHTLY_CONSOLIDATION.value,
            user_id=user.id,
            idempotency_key=idemp,
        )

        assert run.status == "SUCCESS"
        assert "routines_synced" in run.details
        assert "expired_memories_archived" in run.details

        # Verify memory was transitioned to ARCHIVED
        refreshed_mem = await db_session.get(Memory, expired_mem.id)
        assert refreshed_mem.status == "ARCHIVED"

    @pytest.mark.asyncio
    async def test_scheduler_tick_job(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Verify SCHEDULER_TICK runs periodic check-ins successfully."""
        idemp = f"tick_test_{uuid.uuid4().hex[:8]}"
        run = await JobRunnerService.execute_job(
            db=db_session,
            job_type=JobType.SCHEDULER_TICK.value,
            user_id=user.id,
            idempotency_key=idemp,
        )

        assert run.status == "SUCCESS"
        assert "meal_check_ins_dispatched" in run.details

    @pytest.mark.asyncio
    async def test_job_idempotency_guard(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Verify duplicate job with identical idempotency_key returns cached run without re-running."""
        idemp = f"idemp_unique_{uuid.uuid4().hex[:8]}"

        run1 = await JobRunnerService.execute_job(
            db=db_session,
            job_type=JobType.SCHEDULER_TICK.value,
            user_id=user.id,
            idempotency_key=idemp,
        )
        assert run1.status == "SUCCESS"

        # Calling again with same idempotency key returns run1
        run2 = await JobRunnerService.execute_job(
            db=db_session,
            job_type=JobType.SCHEDULER_TICK.value,
            user_id=user.id,
            idempotency_key=idemp,
        )
        assert run2.id == run1.id

    @pytest.mark.asyncio
    async def test_invalid_job_type_raises_validation_error(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Verify invalid job type raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            await JobRunnerService.execute_job(
                db=db_session,
                job_type="NON_EXISTENT_JOB_TYPE",
                user_id=user.id,
            )
        assert "Invalid job type" in str(exc.value)

    @pytest.mark.asyncio
    async def test_list_job_runs_tenant_isolation(
        self,
        db_session: AsyncSession,
        user: User,
        other_user: User,
    ):
        """Verify user only sees their own or global job runs, never other user's private runs."""
        run_u1 = await JobRunnerService.execute_job(
            db=db_session,
            job_type=JobType.SCHEDULER_TICK.value,
            user_id=user.id,
            idempotency_key=f"u1_run_{uuid.uuid4().hex[:6]}",
        )
        run_u2 = await JobRunnerService.execute_job(
            db=db_session,
            job_type=JobType.SCHEDULER_TICK.value,
            user_id=other_user.id,
            idempotency_key=f"u2_run_{uuid.uuid4().hex[:6]}",
        )

        user_runs = await JobRunnerService.list_job_runs(db_session, user_id=user.id)
        assert any(r.id == run_u1.id for r in user_runs)
        assert not any(r.id == run_u2.id for r in user_runs)

        # Other user cannot access user's run via get_job_run
        with pytest.raises(EntityNotFoundError):
            await JobRunnerService.get_job_run(db_session, run_u1.id, user_id=other_user.id)

    @pytest.mark.asyncio
    async def test_job_failure_tracking(
        self,
        db_session: AsyncSession,
        user: User,
        monkeypatch,
    ):
        """Verify that when a job worker raises an exception, JobRun records FAILED status and error."""
        async def failing_worker(*args, **kwargs):
            raise RuntimeError("Database connection timed out during consolidation.")

        monkeypatch.setattr(JobRunnerService, "_run_nightly_consolidation", failing_worker)

        idemp = f"failing_job_{uuid.uuid4().hex[:8]}"
        with pytest.raises(RuntimeError) as exc:
            await JobRunnerService.execute_job(
                db=db_session,
                job_type=JobType.NIGHTLY_CONSOLIDATION.value,
                user_id=user.id,
                idempotency_key=idemp,
            )
        assert "Database connection timed out" in str(exc.value)

        # Check job run record in database
        stmt = select(JobRun).where(JobRun.idempotency_key == idemp)
        res = await db_session.execute(stmt)
        run = res.scalar_one_or_none()
        assert run is not None
        assert run.status == "FAILED"
        assert "Database connection timed out" in run.error_message

