"""REST API endpoints for tasks, projects, blockers, and pending-work tracking."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.task import Project, Task
from app.models.user import User
from app.services.task_service import TaskService

router = APIRouter(tags=["Tasks & Projects"])


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------

class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = Field(default="ACTIVE")
    priority: str = Field(default="MEDIUM")
    privacy_scope: str = Field(default="PROJECT")
    sensitivity: int = Field(default=30)


class ProjectUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    privacy_scope: Optional[str] = None
    sensitivity: Optional[int] = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    privacy_scope: str
    sensitivity: int
    created_at: datetime
    updated_at: datetime
    tasks_count: int = 0


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    project_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    status: str = Field(default="INBOX")
    priority: str = Field(default="MEDIUM")
    due_at: Optional[datetime] = None
    next_action: Optional[str] = None
    assigned_agent: Optional[str] = None
    privacy_scope: str = Field(default="PERSONAL")
    sensitivity: int = Field(default=30)
    blockers: Optional[List[Dict[str, Any]]] = None
    dependencies: Optional[List[Dict[str, Any]]] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[datetime] = None
    next_action: Optional[str] = None
    assigned_agent: Optional[str] = None
    project_id: Optional[uuid.UUID] = None
    completion_evidence: Optional[Dict[str, Any]] = None


class TaskBlockerRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1024)
    next_action: Optional[str] = None


class TaskDependencyRequest(BaseModel):
    depends_on_task_id: uuid.UUID
    dependency_type: str = Field(default="BLOCKS")


class TaskCompleteRequest(BaseModel):
    evidence_type: str = Field(min_length=1, description="USER_CONFIRMATION, TOOL_OUTPUT, ARTIFACT_VERIFICATION")
    description: str = Field(min_length=1, max_length=2048)
    verified_by: str = Field(min_length=1)
    artifact_uri: Optional[str] = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    next_action: Optional[str] = None
    assigned_agent: Optional[str] = None
    approval_id: Optional[uuid.UUID] = None
    privacy_scope: str
    sensitivity: int
    blockers: Optional[List[Dict[str, Any]]] = None
    dependencies: Optional[List[Dict[str, Any]]] = None
    completion_evidence: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


def serialize_project(p: Project) -> Dict[str, Any]:
    return {
        "id": p.id,
        "user_id": p.user_id,
        "title": p.title,
        "description": p.description,
        "status": p.status,
        "priority": p.priority,
        "privacy_scope": p.privacy_scope,
        "sensitivity": p.sensitivity,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "tasks_count": len(p.tasks) if p.tasks else 0,
    }


def serialize_task(t: Task) -> Dict[str, Any]:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "project_id": t.project_id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "due_at": t.due_at,
        "started_at": t.started_at,
        "completed_at": t.completed_at,
        "blocked_reason": t.blocked_reason,
        "next_action": t.next_action,
        "assigned_agent": t.assigned_agent,
        "approval_id": t.approval_id,
        "privacy_scope": t.privacy_scope,
        "sensitivity": t.sensitivity,
        "blockers": t.blockers,
        "dependencies": t.dependencies,
        "completion_evidence": t.completion_evidence,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


# -----------------------------------------------------------------------------
# Project Endpoints
# -----------------------------------------------------------------------------

@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreateRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new top-level project initiative."""
    current_user, session_id = auth
    try:
        project = await TaskService.create_project(
            db=db,
            user_id=current_user.id,
            title=req.title,
            description=req.description,
            status=req.status,
            priority=req.priority,
            privacy_scope=req.privacy_scope,
            sensitivity=req.sensitivity,
            session_id=session_id,
        )
        return serialize_project(project)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    status: Optional[str] = Query(default=None),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """List all projects for the current user."""
    current_user, _ = auth
    projects = await TaskService.list_projects(db, current_user.id, status=status)
    return [serialize_project(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Get project by ID with tenant isolation."""
    current_user, _ = auth
    try:
        project = await TaskService.get_project(db, project_id, current_user.id)
        return serialize_project(project)
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    req: ProjectUpdateRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Update project fields."""
    current_user, session_id = auth
    try:
        project = await TaskService.update_project(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            title=req.title,
            description=req.description,
            status=req.status,
            priority=req.priority,
            privacy_scope=req.privacy_scope,
            sensitivity=req.sensitivity,
            session_id=session_id,
        )
        return serialize_project(project)
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


# -----------------------------------------------------------------------------
# Task Endpoints
# -----------------------------------------------------------------------------

@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    req: TaskCreateRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Create and persist an actionable task."""
    current_user, session_id = auth
    try:
        task = await TaskService.create_task(
            db=db,
            user_id=current_user.id,
            title=req.title,
            project_id=req.project_id,
            description=req.description,
            status=req.status,
            priority=req.priority,
            due_at=req.due_at,
            next_action=req.next_action,
            assigned_agent=req.assigned_agent,
            privacy_scope=req.privacy_scope,
            sensitivity=req.sensitivity,
            blockers=req.blockers,
            dependencies=req.dependencies,
            session_id=session_id,
        )
        return serialize_task(task)
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced project not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    project_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """List tasks with optional filters."""
    current_user, _ = auth
    tasks = await TaskService.list_tasks(
        db=db,
        user_id=current_user.id,
        project_id=project_id,
        status=status,
        priority=priority,
    )
    return [serialize_task(t) for t in tasks]


@router.get("/tasks/pending", response_model=Dict[str, Any])
async def query_pending_work(
    include_yesterday: bool = Query(default=False),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Execute pending work analysis according to PRD Sections 14.3 & 14.4."""
    current_user, _ = auth
    data = await TaskService.query_pending_work(
        db=db,
        user_id=current_user.id,
        include_yesterday=include_yesterday,
    )
    result = {
        "summary": data["summary"],
        "in_progress": [serialize_task(t) for t in data["in_progress"]],
        "blocked": [serialize_task(t) for t in data["blocked"]],
        "waiting_for_approval": [serialize_task(t) for t in data["waiting_for_approval"]],
        "overdue": [serialize_task(t) for t in data["overdue"]],
        "upcoming_deadlines": [serialize_task(t) for t in data["upcoming_deadlines"]],
        "pending_approvals": data["pending_approvals"],
    }
    if "yesterday_continuity" in data:
        result["yesterday_continuity"] = [serialize_task(t) for t in data["yesterday_continuity"]]
    return result


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Get task by ID with strict tenant ownership enforcement."""
    current_user, _ = auth
    try:
        task = await TaskService.get_task(db, task_id, current_user.id)
        return serialize_task(task)
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    req: TaskUpdateRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Update task fields and enforce lifecycle invariants."""
    current_user, session_id = auth
    try:
        task = await TaskService.update_task(
            db=db,
            task_id=task_id,
            user_id=current_user.id,
            title=req.title,
            description=req.description,
            status=req.status,
            priority=req.priority,
            due_at=req.due_at,
            next_action=req.next_action,
            assigned_agent=req.assigned_agent,
            project_id=req.project_id,
            completion_evidence=req.completion_evidence,
            session_id=session_id,
        )
        return serialize_task(task)
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/tasks/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: uuid.UUID,
    req: TaskCompleteRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Certify and complete task with verifiable completion evidence."""
    current_user, session_id = auth
    try:
        task = await TaskService.complete_task(
            db=db,
            task_id=task_id,
            user_id=current_user.id,
            evidence_type=req.evidence_type,
            description=req.description,
            verified_by=req.verified_by,
            artifact_uri=req.artifact_uri,
            session_id=session_id,
        )
        return serialize_task(task)
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/tasks/{task_id}/blockers", response_model=TaskResponse)
async def add_blocker(
    task_id: uuid.UUID,
    req: TaskBlockerRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Attach blocker to task, transitioning status to BLOCKED."""
    current_user, session_id = auth
    try:
        task = await TaskService.add_blocker(
            db=db,
            task_id=task_id,
            user_id=current_user.id,
            reason=req.reason,
            next_action=req.next_action,
            session_id=session_id,
        )
        return serialize_task(task)
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/tasks/{task_id}/blockers/{blocker_id}/resolve", response_model=TaskResponse)
async def resolve_blocker(
    task_id: uuid.UUID,
    blocker_id: str,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Resolve blocker. Transitions task back to TODO if all blockers are resolved."""
    current_user, session_id = auth
    try:
        task = await TaskService.resolve_blocker(
            db=db,
            task_id=task_id,
            user_id=current_user.id,
            blocker_id=blocker_id,
            session_id=session_id,
        )
        return serialize_task(task)
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/tasks/{task_id}/dependencies", response_model=TaskResponse)
async def add_dependency(
    task_id: uuid.UUID,
    req: TaskDependencyRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
):
    """Add DAG dependency with cycle detection."""
    current_user, session_id = auth
    try:
        task = await TaskService.add_dependency(
            db=db,
            task_id=task_id,
            user_id=current_user.id,
            depends_on_task_id=req.depends_on_task_id,
            dependency_type=req.dependency_type,
            session_id=session_id,
        )
        return serialize_task(task)
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
