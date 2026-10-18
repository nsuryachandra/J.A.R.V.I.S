"""Domain service orchestrating tasks, projects, blocker state machines, and pending-work queries."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified
from app.contracts.common import PrivacyScope, SensitivityLevel
from app.contracts.tasks import ProjectStatus, TaskPriority, TaskStatus
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.approval import ApprovalRequest
from app.models.base import utcnow
from app.models.task import Project, Task
from app.services.audit_service import AuditService


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is offset-aware in UTC for safe comparisons and arithmetic."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class TaskService:
    """Service governing project and task execution, DAG dependency validation, and pending work tracking."""

    # -------------------------------------------------------------------------
    # Project Operations
    # -------------------------------------------------------------------------

    @classmethod
    async def create_project(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        description: Optional[str] = None,
        status: str = "ACTIVE",
        priority: str = "MEDIUM",
        privacy_scope: str = "PROJECT",
        sensitivity: int = 30,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Project:
        """Create a new top-level project initiative."""
        clean_title = title.strip()
        if not clean_title:
            raise ValidationError("Project title cannot be empty.")

        project = Project(
            user_id=user_id,
            title=clean_title,
            description=description.strip() if description else None,
            status=status.upper(),
            priority=priority.upper(),
            privacy_scope=privacy_scope,
            sensitivity=sensitivity,
        )
        db.add(project)
        await db.flush()

        await AuditService.record_event(
            session=db,
            action_type="project.create",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"project:{project.id}",
            details={"project_id": str(project.id), "title": clean_title, "status": project.status},
        )
        await db.commit()
        return await cls.get_project(db, project.id, user_id)

    @classmethod
    async def get_project(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Project:
        """Fetch project with strict user-tenant ownership enforcement."""
        stmt = (
            select(Project)
            .where(Project.id == project_id)
            .options(selectinload(Project.tasks))
            .execution_options(populate_existing=True)
        )
        res = await db.execute(stmt)
        project = res.scalar_one_or_none()

        if project is None:
            raise EntityNotFoundError("Project", project_id)

        if project.user_id != user_id:
            raise PermissionDeniedError("Access denied: Project belongs to another user.")

        return project

    @classmethod
    async def update_project(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        privacy_scope: Optional[str] = None,
        sensitivity: Optional[int] = None,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Project:
        """Update existing project fields."""
        project = await cls.get_project(db, project_id, user_id)

        if title is not None:
            clean = title.strip()
            if not clean:
                raise ValidationError("Project title cannot be empty.")
            project.title = clean

        if description is not None:
            project.description = description.strip()

        if status is not None:
            project.status = status.upper()

        if priority is not None:
            project.priority = priority.upper()

        if privacy_scope is not None:
            project.privacy_scope = privacy_scope

        if sensitivity is not None:
            project.sensitivity = sensitivity

        project.updated_at = utcnow()

        await AuditService.record_event(
            session=db,
            action_type="project.update",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"project:{project.id}",
            details={"project_id": str(project.id), "status": project.status},
        )
        await db.commit()
        return await cls.get_project(db, project.id, user_id)

    @classmethod
    async def list_projects(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        status: Optional[str] = None,
    ) -> List[Project]:
        """List all projects belonging to user."""
        stmt = (
            select(Project)
            .where(Project.user_id == user_id)
            .options(selectinload(Project.tasks))
            .order_by(Project.created_at.desc())
        )
        if status:
            stmt = stmt.where(Project.status == status.upper())

        res = await db.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Task Operations
    # -------------------------------------------------------------------------

    @classmethod
    async def create_task(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        project_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
        status: str = "INBOX",
        priority: str = "MEDIUM",
        due_at: Optional[datetime] = None,
        next_action: Optional[str] = None,
        assigned_agent: Optional[str] = None,
        privacy_scope: str = "PERSONAL",
        sensitivity: int = 30,
        blockers: Optional[List[Dict[str, Any]]] = None,
        dependencies: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Task:
        """Create and persist an actionable task."""
        clean_title = title.strip()
        if not clean_title:
            raise ValidationError("Task title cannot be empty.")

        # If project_id provided, verify tenant ownership
        if project_id:
            await cls.get_project(db, project_id, user_id)

        clean_status = status.upper()
        clean_priority = priority.upper()
        blocker_list = list(blockers or [])
        dep_list = list(dependencies or [])

        # Invariant 1: Task cannot be created COMPLETED without evidence
        if clean_status == "COMPLETED":
            raise ValidationError(
                "Task cannot be marked COMPLETED at creation without verified completion evidence."
            )

        # Invariant 2: Task cannot be IN_PROGRESS with unresolved blockers
        if clean_status == "IN_PROGRESS":
            unresolved = [b for b in blocker_list if b.get("resolved_at_utc") is None]
            if unresolved:
                raise ValidationError(
                    f"Task cannot be IN_PROGRESS while {len(unresolved)} blockers remain unresolved. Transition to BLOCKED instead."
                )

        started_at = utcnow() if clean_status == "IN_PROGRESS" else None

        task = Task(
            user_id=user_id,
            project_id=project_id,
            title=clean_title,
            description=description.strip() if description else None,
            status=clean_status,
            priority=clean_priority,
            due_at=ensure_utc(due_at),
            started_at=started_at,
            next_action=next_action.strip() if next_action else None,
            assigned_agent=assigned_agent,
            privacy_scope=privacy_scope,
            sensitivity=sensitivity,
            blockers=blocker_list,
            dependencies=dep_list,
        )
        db.add(task)
        await db.flush()

        await AuditService.record_event(
            session=db,
            action_type="task.create",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"task:{task.id}",
            details={"task_id": str(task.id), "title": clean_title, "status": clean_status},
        )
        await db.commit()
        return await cls.get_task(db, task.id, user_id)

    @classmethod
    async def get_task(
        cls,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Task:
        """Fetch task with strict user-tenant ownership enforcement."""
        stmt = (
            select(Task)
            .where(Task.id == task_id)
            .options(selectinload(Task.project))
            .execution_options(populate_existing=True)
        )
        res = await db.execute(stmt)
        task = res.scalar_one_or_none()

        if task is None:
            raise EntityNotFoundError("Task", task_id)

        if task.user_id != user_id:
            raise PermissionDeniedError("Access denied: Task belongs to another user.")

        return task

    @classmethod
    async def update_task(
        cls,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        due_at: Optional[datetime] = None,
        next_action: Optional[str] = None,
        assigned_agent: Optional[str] = None,
        project_id: Optional[uuid.UUID] = None,
        completion_evidence: Optional[Dict[str, Any]] = None,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Task:
        """Update existing task with strict invariant enforcement."""
        task = await cls.get_task(db, task_id, user_id)

        if title is not None:
            clean = title.strip()
            if not clean:
                raise ValidationError("Task title cannot be empty.")
            task.title = clean

        if description is not None:
            task.description = description.strip()

        if priority is not None:
            task.priority = priority.upper()

        if due_at is not None:
            task.due_at = ensure_utc(due_at)

        if next_action is not None:
            task.next_action = next_action.strip()

        if assigned_agent is not None:
            task.assigned_agent = assigned_agent

        if project_id is not None:
            await cls.get_project(db, project_id, user_id)
            task.project_id = project_id

        if completion_evidence is not None:
            task.completion_evidence = completion_evidence

        # Status transition checks
        if status is not None:
            target_status = status.upper()

            # Rule: Cannot transition to COMPLETED without completion_evidence
            if target_status == "COMPLETED":
                evidence = completion_evidence or task.completion_evidence
                if not evidence:
                    raise ValidationError(
                        "Task cannot be marked COMPLETED without verified completion_evidence or user confirmation."
                    )
                task.status = "COMPLETED"
                task.completed_at = utcnow()

            # Rule: Cannot transition to IN_PROGRESS with unresolved blockers
            elif target_status == "IN_PROGRESS":
                blockers = task.blockers or []
                unresolved = [b for b in blockers if b.get("resolved_at_utc") is None]
                if unresolved:
                    raise ValidationError(
                        f"Task cannot be IN_PROGRESS while {len(unresolved)} blockers remain unresolved. Transition to BLOCKED instead."
                    )
                task.status = "IN_PROGRESS"
                if not task.started_at:
                    task.started_at = utcnow()
            else:
                task.status = target_status

        task.updated_at = utcnow()

        await AuditService.record_event(
            session=db,
            action_type="task.update",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"task:{task.id}",
            details={"task_id": str(task.id), "status": task.status},
        )
        await db.commit()
        return await cls.get_task(db, task.id, user_id)

    @classmethod
    async def add_blocker(
        cls,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str,
        next_action: Optional[str] = None,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Task:
        """Attach a blocker to a task and transition status to BLOCKED."""
        clean_reason = reason.strip()
        if not clean_reason:
            raise ValidationError("Blocker reason cannot be empty.")

        task = await cls.get_task(db, task_id, user_id)

        blockers = list(task.blockers or [])
        new_blocker = {
            "blocker_id": str(uuid.uuid4()),
            "reason": clean_reason,
            "blocked_at_utc": utcnow().isoformat(),
            "resolved_at_utc": None,
        }
        blockers.append(new_blocker)
        task.blockers = blockers
        flag_modified(task, "blockers")
        task.status = "BLOCKED"
        task.blocked_reason = clean_reason
        if next_action:
            task.next_action = next_action.strip()

        task.updated_at = utcnow()

        await AuditService.record_event(
            session=db,
            action_type="task.block",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"task:{task.id}",
            details={"task_id": str(task.id), "reason": clean_reason},
        )
        await db.commit()
        return await cls.get_task(db, task.id, user_id)

    @classmethod
    async def resolve_blocker(
        cls,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        blocker_id: str,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Task:
        """Resolve a task blocker. If all blockers are cleared, returns task to TODO."""
        task = await cls.get_task(db, task_id, user_id)

        blockers = list(task.blockers or [])
        found = False
        now_iso = utcnow().isoformat()

        for b in blockers:
            if b.get("blocker_id") == blocker_id:
                b["resolved_at_utc"] = now_iso
                found = True
                break

        if not found:
            raise ValidationError(f"Blocker with id {blocker_id} not found on task {task_id}.")

        task.blockers = blockers
        flag_modified(task, "blockers")

        # Check if all blockers are resolved
        unresolved = [b for b in blockers if b.get("resolved_at_utc") is None]
        if not unresolved:
            task.blocked_reason = None
            if task.status == "BLOCKED":
                task.status = "TODO"

        task.updated_at = utcnow()

        await AuditService.record_event(
            session=db,
            action_type="task.unblock",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"task:{task.id}",
            details={"task_id": str(task.id), "blocker_id": blocker_id},
        )
        await db.commit()
        return await cls.get_task(db, task.id, user_id)

    @classmethod
    async def add_dependency(
        cls,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        depends_on_task_id: uuid.UUID,
        dependency_type: str = "BLOCKS",
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Task:
        """
        Add a DAG dependency between two tasks with circular dependency cycle detection.
        Ensures task A cannot depend on task B if task B already depends directly or indirectly on A.
        """
        if task_id == depends_on_task_id:
            raise ValidationError("A task cannot depend on itself.")

        task = await cls.get_task(db, task_id, user_id)
        prerequisite = await cls.get_task(db, depends_on_task_id, user_id)

        # Detect cycle: Check if task_id is reachable from depends_on_task_id
        is_cyclic = await cls._has_path(db, user_id, start_id=depends_on_task_id, target_id=task_id)
        if is_cyclic:
            raise ValidationError(
                f"Circular dependency detected: task {depends_on_task_id} already depends on task {task_id}."
            )

        deps = list(task.dependencies or [])
        # Prevent duplicate dependency
        if any(d.get("depends_on_task_id") == str(depends_on_task_id) for d in deps):
            return task

        deps.append({
            "depends_on_task_id": str(depends_on_task_id),
            "dependency_type": dependency_type,
        })
        task.dependencies = deps
        flag_modified(task, "dependencies")
        task.updated_at = utcnow()

        await AuditService.record_event(
            session=db,
            action_type="task.dependency_added",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"task:{task.id}",
            details={"task_id": str(task.id), "depends_on_task_id": str(depends_on_task_id)},
        )
        await db.commit()
        return await cls.get_task(db, task.id, user_id)

    @classmethod
    async def _has_path(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        start_id: uuid.UUID,
        target_id: uuid.UUID,
    ) -> bool:
        """BFS traversal to check reachability from start_id to target_id across dependencies."""
        visited: Set[uuid.UUID] = set()
        queue: List[uuid.UUID] = [start_id]

        # Fetch all tasks for user to inspect dependencies in-memory
        stmt = select(Task.id, Task.dependencies).where(Task.user_id == user_id)
        res = await db.execute(stmt)
        dep_graph: Dict[uuid.UUID, List[uuid.UUID]] = {}
        for tid, deps in res.all():
            dep_graph[tid] = [
                uuid.UUID(d["depends_on_task_id"])
                for d in (deps or [])
                if "depends_on_task_id" in d
            ]

        while queue:
            curr = queue.pop(0)
            if curr == target_id:
                return True
            if curr in visited:
                continue
            visited.add(curr)

            for neighbor in dep_graph.get(curr, []):
                if neighbor not in visited:
                    queue.append(neighbor)

        return False

    @classmethod
    async def complete_task(
        cls,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        evidence_type: str,
        description: str,
        verified_by: str,
        artifact_uri: Optional[str] = None,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Task:
        """Certify and complete a task with verifiable completion evidence."""
        clean_desc = description.strip()
        if not clean_desc:
            raise ValidationError("Completion evidence description cannot be empty.")

        evidence = {
            "evidence_type": evidence_type,
            "description": clean_desc,
            "verified_by": verified_by,
            "verified_at_utc": utcnow().isoformat(),
            "artifact_uri": artifact_uri,
        }

        return await cls.update_task(
            db=db,
            task_id=task_id,
            user_id=user_id,
            status="COMPLETED",
            completion_evidence=evidence,
            session_id=session_id,
            correlation_id=correlation_id,
        )

    @classmethod
    async def list_tasks(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[Task]:
        """List tasks with optional filters."""
        stmt = (
            select(Task)
            .where(Task.user_id == user_id)
            .options(selectinload(Task.project))
            .order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc())
        )
        if project_id:
            stmt = stmt.where(Task.project_id == project_id)
        if status:
            stmt = stmt.where(Task.status == status.upper())
        if priority:
            stmt = stmt.where(Task.priority == priority.upper())

        res = await db.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # PRD 14.3 & 14.4 Pending Work & Yesterday Continuity Query
    # -------------------------------------------------------------------------

    @classmethod
    async def query_pending_work(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        include_yesterday: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute comprehensive pending work analysis according to PRD Sections 14.3 & 14.4.
        Returns:
          - in_progress tasks
          - blocked tasks with blocker reasons and next actions
          - pending approvals
          - upcoming deadlines (next 7 days)
          - overdue tasks
          - yesterday continuity items (if requested)
        """
        now = utcnow()
        yesterday_start = now - timedelta(days=1)

        # 1. Fetch all unfinished tasks
        unfinished_statuses = [
            "INBOX",
            "PLANNED",
            "IN_PROGRESS",
            "BLOCKED",
            "WAITING_FOR_USER",
            "WAITING_FOR_APPROVAL",
        ]
        stmt = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status.in_(unfinished_statuses),
            )
            .options(selectinload(Task.project))
            .order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc())
        )
        res = await db.execute(stmt)
        all_unfinished = list(res.scalars().all())

        in_progress = [t for t in all_unfinished if t.status == "IN_PROGRESS"]
        blocked = [t for t in all_unfinished if t.status == "BLOCKED"]
        waiting_for_approval = [t for t in all_unfinished if t.status == "WAITING_FOR_APPROVAL"]

        # 2. Overdue and upcoming deadlines
        overdue = []
        upcoming = []
        seven_days_out = now + timedelta(days=7)

        for t in all_unfinished:
            if t.due_at:
                due = ensure_utc(t.due_at)
                if due and due < now:
                    overdue.append(t)
                elif due and now <= due <= seven_days_out:
                    upcoming.append(t)

        # 3. Pending approvals from ApprovalRequest table
        appr_stmt = select(ApprovalRequest).where(
            ApprovalRequest.user_id == user_id,
            ApprovalRequest.status.in_(["PENDING", "pending"]),
        )
        appr_res = await db.execute(appr_stmt)
        pending_approvals = list(appr_res.scalars().all())

        response: Dict[str, Any] = {
            "summary": {
                "total_unfinished": len(all_unfinished),
                "in_progress_count": len(in_progress),
                "blocked_count": len(blocked),
                "overdue_count": len(overdue),
                "upcoming_deadlines_count": len(upcoming),
                "pending_approvals_count": len(pending_approvals),
            },
            "in_progress": in_progress,
            "blocked": blocked,
            "waiting_for_approval": waiting_for_approval,
            "overdue": overdue,
            "upcoming_deadlines": upcoming,
            "pending_approvals": [
                {
                    "approval_id": str(a.id),
                    "tool_name": a.tool_name,
                    "risk_class": a.risk_class,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in pending_approvals
            ],
        }

        # 4. Yesterday continuity items (PRD Section 14.4)
        if include_yesterday:
            yesterday_stmt = (
                select(Task)
                .where(
                    Task.user_id == user_id,
                    or_(
                        Task.updated_at >= yesterday_start,
                        Task.created_at >= yesterday_start,
                    ),
                )
                .options(selectinload(Task.project))
                .order_by(Task.updated_at.desc())
            )
            y_res = await db.execute(yesterday_stmt)
            response["yesterday_continuity"] = list(y_res.scalars().all())

        return response
