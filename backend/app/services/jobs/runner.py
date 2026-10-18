"""Job Runner Service orchestrating background cron execution, briefings, consolidation, and ticks."""

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import EntityNotFoundError, ValidationError
from app.models.base import utcnow
from app.models.event import Routine
from app.models.job import JobRun
from app.models.memory import Memory
from app.models.task import Task
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.event_service import EventService
from app.services.jobs.schemas import JobRunResponse, JobType
from app.services.proactive_service import ProactiveService
from app.temporal.timezone import TimezoneService


class JobRunnerService:
    """Service governing execution, idempotency, failure tracking, and metrics for scheduled jobs."""

    @classmethod
    async def execute_job(
        cls,
        db: AsyncSession,
        job_type: str,
        user_id: Optional[uuid.UUID] = None,
        idempotency_key: Optional[str] = None,
        force: bool = False,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> JobRun:
        """Execute a background scheduled job with strict idempotency and audit tracking."""
        norm_type = job_type.upper().strip()
        valid_types = {jt.value for jt in JobType}
        if norm_type not in valid_types:
            raise ValidationError(f"Invalid job type '{job_type}'. Valid types: {sorted(list(valid_types))}")

        # Derive deterministic idempotency key if not supplied
        now = utcnow()
        date_str = now.strftime("%Y-%m-%d")
        hour_str = now.strftime("%Y-%m-%d-%H")
        user_scope = str(user_id) if user_id else "global"

        if not idempotency_key:
            if norm_type in (JobType.MORNING_BRIEFING.value, JobType.EVENING_BRIEFING.value, JobType.NIGHTLY_CONSOLIDATION.value):
                idempotency_key = f"{norm_type}:{user_scope}:{date_str}"
            else:
                idempotency_key = f"{norm_type}:{user_scope}:{hour_str}"

        # 1. Idempotency verification: Check if successful run exists
        if not force:
            existing_stmt = select(JobRun).where(
                JobRun.idempotency_key == idempotency_key,
                JobRun.status == "SUCCESS",
            )
            res = await db.execute(existing_stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return existing

        # 2. Initialize job run record
        job_run = JobRun(
            job_type=norm_type,
            status="RUNNING",
            idempotency_key=idempotency_key,
            target_user_id=user_id,
            started_at=now,
        )
        db.add(job_run)
        await db.commit()
        await db.refresh(job_run)

        start_time = time.perf_counter()
        details: Dict[str, Any] = {}

        try:
            # 3. Dispatch to specific job worker
            if norm_type == JobType.MORNING_BRIEFING.value:
                details = await cls._run_morning_briefing(db, user_id, now)
            elif norm_type == JobType.EVENING_BRIEFING.value:
                details = await cls._run_evening_briefing(db, user_id, now)
            elif norm_type == JobType.NIGHTLY_CONSOLIDATION.value:
                details = await cls._run_nightly_consolidation(db, user_id, now)
            elif norm_type == JobType.SCHEDULER_TICK.value:
                details = await cls._run_scheduler_tick(db, user_id, now)
            elif norm_type == JobType.STALE_TASK_SWEEP.value:
                details = await cls._run_stale_task_sweep(db, user_id, now)

            # 4. Success completion
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            job_run.status = "SUCCESS"
            job_run.completed_at = utcnow()
            job_run.duration_ms = duration_ms
            job_run.details = json.dumps(details)
            job_run.error_message = None

            await db.commit()
            await db.refresh(job_run)

            # Record audit log
            await AuditService.record_event(
                session=db,
                user_id=user_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
                session_id=session_id_auth,
                action_type=f"job.{norm_type.lower()}",
                resource_scope=f"job_run:{job_run.id}",
                decision="ALLOW",
                result_status="SUCCESS",
                details={
                    "job_type": norm_type,
                    "idempotency_key": idempotency_key,
                    "duration_ms": duration_ms,
                    "details": details,
                },
            )
            await db.commit()

            return job_run

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            job_run.status = "FAILED"
            job_run.completed_at = utcnow()
            job_run.duration_ms = duration_ms
            job_run.details = json.dumps({"partial_details": details})
            job_run.error_message = str(exc)

            await db.commit()
            await db.refresh(job_run)

            # Record audit failure log
            try:
                await AuditService.record_event(
                    session=db,
                    user_id=user_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
                    session_id=session_id_auth,
                    action_type=f"job.{norm_type.lower()}",
                    resource_scope=f"job_run:{job_run.id}",
                    decision="ALLOW",
                    result_status="FAILURE",
                    details={
                        "job_type": norm_type,
                        "idempotency_key": idempotency_key,
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    },
                )
                await db.commit()
            except Exception:
                pass

            raise exc

    # -------------------------------------------------------------------------
    # Worker Implementations
    # -------------------------------------------------------------------------

    @classmethod
    async def _get_target_users(cls, db: AsyncSession, user_id: Optional[uuid.UUID]) -> List[User]:
        """Fetch targeted user or all active users for system-wide jobs."""
        if user_id:
            stmt = select(User).where(User.id == user_id)
            res = await db.execute(stmt)
            u = res.scalar_one_or_none()
            if not u:
                raise EntityNotFoundError("User", user_id)
            return [u]

        stmt = select(User).where(User.is_active == True)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def _run_morning_briefing(
        cls,
        db: AsyncSession,
        user_id: Optional[uuid.UUID],
        now: datetime,
    ) -> Dict[str, Any]:
        """Generate and dispatch morning briefings according to PRD 16.1 & 31.3."""
        users = await cls._get_target_users(db, user_id)
        generated_count = 0
        skipped_count = 0

        for user in users:
            try:
                res = await ProactiveService.generate_morning_briefing(db, user.id, current_dt=now)
                if res.get("notification_id"):
                    generated_count += 1
                else:
                    skipped_count += 1
            except Exception:
                skipped_count += 1

        return {
            "total_users_evaluated": len(users),
            "briefings_dispatched": generated_count,
            "briefings_skipped": skipped_count,
        }

    @classmethod
    async def _run_evening_briefing(
        cls,
        db: AsyncSession,
        user_id: Optional[uuid.UUID],
        now: datetime,
    ) -> Dict[str, Any]:
        """Generate and dispatch evening briefings according to PRD 16.2."""
        users = await cls._get_target_users(db, user_id)
        generated_count = 0
        skipped_count = 0

        for user in users:
            try:
                res = await ProactiveService.generate_evening_briefing(db, user.id, current_dt=now)
                if res.get("notification_id"):
                    generated_count += 1
                else:
                    skipped_count += 1
            except Exception:
                skipped_count += 1

        return {
            "total_users_evaluated": len(users),
            "briefings_dispatched": generated_count,
            "briefings_skipped": skipped_count,
        }

    @classmethod
    async def _run_nightly_consolidation(
        cls,
        db: AsyncSession,
        user_id: Optional[uuid.UUID],
        now: datetime,
    ) -> Dict[str, Any]:
        """Execute nightly consolidation according to PRD 31.4."""
        users = await cls._get_target_users(db, user_id)
        routines_synced = 0
        expired_memories_archived = 0
        stale_tasks_flagged = 0

        for user in users:
            # 1. Expand and sync routine occurrences for next 14 days
            routines_stmt = select(Routine).where(
                Routine.user_id == user.id,
                Routine.is_active == True,
            )
            r_res = await db.execute(routines_stmt)
            routines = r_res.scalars().all()
            for r in routines:
                try:
                    await EventService.expand_and_sync_occurrences(db, r.id, user.id, days_ahead=14)
                    routines_synced += 1
                except Exception:
                    pass

            # 2. Archive expired temporary memories
            mem_stmt = select(Memory).where(
                Memory.user_id == user.id,
                Memory.status == "ACTIVE",
                Memory.valid_until.is_not(None),
                Memory.valid_until < now,
            )
            mem_res = await db.execute(mem_stmt)
            expired_mems = mem_res.scalars().all()
            for m in expired_mems:
                m.status = "ARCHIVED"
                m.updated_at = now
                expired_memories_archived += 1

            # 3. Count stale unfinished tasks
            seven_days_ago = now - timedelta(days=7)
            task_stmt = select(Task).where(
                Task.user_id == user.id,
                Task.status.in_(["INBOX", "PLANNED", "IN_PROGRESS"]),
                Task.updated_at < seven_days_ago,
            )
            task_res = await db.execute(task_stmt)
            stale_tasks = task_res.scalars().all()
            stale_tasks_flagged += len(stale_tasks)

        await db.commit()

        return {
            "users_processed": len(users),
            "routines_synced": routines_synced,
            "expired_memories_archived": expired_memories_archived,
            "stale_tasks_flagged": stale_tasks_flagged,
        }

    @classmethod
    async def _run_scheduler_tick(
        cls,
        db: AsyncSession,
        user_id: Optional[uuid.UUID],
        now: datetime,
    ) -> Dict[str, Any]:
        """Periodic scheduler tick evaluating routine occurrences and check-ins."""
        users = await cls._get_target_users(db, user_id)
        meal_check_ins = 0

        for user in users:
            try:
                notif = await ProactiveService.evaluate_and_dispatch_meal_check_in(db, user.id, current_dt=now)
                if notif and notif.status == "DISPATCHED":
                    meal_check_ins += 1
            except Exception:
                pass

        return {
            "users_evaluated": len(users),
            "meal_check_ins_dispatched": meal_check_ins,
            "timestamp": now.isoformat(),
        }

    @classmethod
    async def _run_stale_task_sweep(
        cls,
        db: AsyncSession,
        user_id: Optional[uuid.UUID],
        now: datetime,
    ) -> Dict[str, Any]:
        """Sweep and categorize overdue / stale tasks across users."""
        users = await cls._get_target_users(db, user_id)
        overdue_count = 0

        for user in users:
            stmt = select(Task).where(
                Task.user_id == user.id,
                Task.status.in_(["INBOX", "PLANNED", "IN_PROGRESS"]),
                Task.due_at.is_not(None),
                Task.due_at < now,
            )
            res = await db.execute(stmt)
            overdue = res.scalars().all()
            overdue_count += len(overdue)

        return {
            "users_evaluated": len(users),
            "overdue_tasks_found": overdue_count,
        }

    # -------------------------------------------------------------------------
    # Query & Retrieval
    # -------------------------------------------------------------------------

    @classmethod
    async def list_job_runs(
        cls,
        db: AsyncSession,
        user_id: Optional[uuid.UUID] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[JobRunResponse]:
        """List past job runs with optional user and type filtering."""
        stmt = select(JobRun).order_by(desc(JobRun.started_at)).limit(limit)

        if user_id:
            stmt = stmt.where(
                or_(
                    JobRun.target_user_id == user_id,
                    JobRun.target_user_id.is_(None),
                )
            )
        if job_type:
            stmt = stmt.where(JobRun.job_type == job_type.upper().strip())

        res = await db.execute(stmt)
        runs = res.scalars().all()

        out: List[JobRunResponse] = []
        for r in runs:
            parsed_details = json.loads(r.details) if r.details else None
            out.append(
                JobRunResponse(
                    id=r.id,
                    job_type=r.job_type,
                    status=r.status,
                    idempotency_key=r.idempotency_key,
                    target_user_id=r.target_user_id,
                    started_at=r.started_at.isoformat(),
                    completed_at=r.completed_at.isoformat() if r.completed_at else None,
                    duration_ms=r.duration_ms,
                    details=parsed_details,
                    error_message=r.error_message,
                    created_at=r.created_at.isoformat(),
                    updated_at=r.updated_at.isoformat(),
                )
            )
        return out

    @classmethod
    async def get_job_run(
        cls,
        db: AsyncSession,
        job_run_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> JobRunResponse:
        """Fetch single job run by ID enforcing user isolation if requested."""
        stmt = select(JobRun).where(JobRun.id == job_run_id)
        if user_id:
            stmt = stmt.where(
                or_(
                    JobRun.target_user_id == user_id,
                    JobRun.target_user_id.is_(None),
                )
            )
        res = await db.execute(stmt)
        r = res.scalar_one_or_none()
        if not r:
            raise EntityNotFoundError("JobRun", job_run_id)

        parsed_details = json.loads(r.details) if r.details else None
        return JobRunResponse(
            id=r.id,
            job_type=r.job_type,
            status=r.status,
            idempotency_key=r.idempotency_key,
            target_user_id=r.target_user_id,
            started_at=r.started_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
            duration_ms=r.duration_ms,
            details=parsed_details,
            error_message=r.error_message,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
