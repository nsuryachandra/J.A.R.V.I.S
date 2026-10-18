"""Domain contracts for tasks, projects, blockers, dependencies, and completion evidence."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.contracts.common import (
    PrivacyScope,
    SensitivityLevel,
    UserScopedResource,
    VersionedContract,
)


class TaskPriority(str, Enum):
    """Execution urgency tier for tasks and projects."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatus(str, Enum):
    """Lifecycle state machine stages for tasks."""

    INBOX = "INBOX"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class ProjectStatus(str, Enum):
    """Lifecycle state of an overarching initiative."""

    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class TaskDependency(BaseModel):
    """Prerequisite relationship between distinct tasks."""

    model_config = ConfigDict(frozen=True)

    depends_on_task_id: UUID
    dependency_type: str = Field(default="BLOCKS", description="BLOCKS, RELATES_TO, SUBTASK_OF")


class TaskBlocker(BaseModel):
    """Explicit condition or external dependency halting task progress."""

    model_config = ConfigDict(frozen=True)

    blocker_id: UUID = Field(default_factory=uuid4)
    reason: str = Field(min_length=1, max_length=1024)
    blocked_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    resolved_at_utc: Optional[datetime] = None


class TaskAssignment(BaseModel):
    """Delegation target for task execution."""

    model_config = ConfigDict(frozen=True)

    assigned_to: str = Field(description="user, executive_agent, or specialized agent")
    agent_type: Optional[str] = None


class TaskCompletionEvidence(BaseModel):
    """Verifiable proof required before any task can be marked completed."""

    model_config = ConfigDict(frozen=True)

    evidence_type: str = Field(description="USER_CONFIRMATION, TOOL_OUTPUT, ARTIFACT_VERIFICATION")
    description: str = Field(min_length=1, max_length=2048)
    verified_by: str = Field(description="Actor certifying completion")
    verified_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    artifact_uri: Optional[str] = None


class Project(UserScopedResource):
    """Top-level initiative grouping related tasks and milestones."""

    contract_type: str = Field(default="task.project")
    project_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    privacy_scope: PrivacyScope = Field(default=PrivacyScope.PROJECT)
    sensitivity: SensitivityLevel = Field(default=SensitivityLevel.PRIVATE)


class Task(UserScopedResource):
    """Actionable unit of work with blockers, dependencies, and completion evidence."""

    contract_type: str = Field(default="task.item")
    task_id: UUID = Field(default_factory=uuid4)
    project_id: Optional[UUID] = None
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    status: TaskStatus = Field(default=TaskStatus.INBOX)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    due_at_utc: Optional[datetime] = None
    blockers: List[TaskBlocker] = Field(default_factory=list)
    dependencies: List[TaskDependency] = Field(default_factory=list)
    assigned_to: Optional[TaskAssignment] = None
    completion_evidence: Optional[TaskCompletionEvidence] = None
    approval_id: Optional[UUID] = None
    privacy_scope: PrivacyScope = Field(default=PrivacyScope.PERSONAL)
    sensitivity: SensitivityLevel = Field(default=SensitivityLevel.PRIVATE)

    @model_validator(mode="after")
    def validate_completion_evidence_rule(self) -> "Task":
        # A task cannot be in COMPLETED state without completion evidence or explicit confirmation
        if self.status == TaskStatus.COMPLETED and self.completion_evidence is None:
            raise ValueError(
                "Task cannot be marked COMPLETED without verified completion_evidence or user confirmation."
            )

        # A task with unresolved blockers cannot be IN_PROGRESS
        if self.status == TaskStatus.IN_PROGRESS:
            unresolved = [b for b in self.blockers if b.resolved_at_utc is None]
            if unresolved:
                raise ValueError(
                    f"Task cannot be IN_PROGRESS while {len(unresolved)} blockers remain unresolved. Transition to BLOCKED instead."
                )

        return self
