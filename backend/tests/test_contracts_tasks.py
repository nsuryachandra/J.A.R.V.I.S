"""Tests for Task, Project, TaskBlocker, TaskDependency, and TaskCompletionEvidence."""

from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError
from app.contracts.common import PrivacyScope
from app.contracts.tasks import (
    Project,
    ProjectStatus,
    Task,
    TaskAssignment,
    TaskBlocker,
    TaskCompletionEvidence,
    TaskDependency,
    TaskPriority,
    TaskStatus,
)


def test_task_creation_defaults():
    """Verify default task properties."""
    uid = uuid.uuid4()
    task = Task(
        user_id=uid,
        title="Schedule quarterly dentist appointment",
        priority=TaskPriority.MEDIUM,
    )
    assert task.user_id == uid
    assert task.status == TaskStatus.INBOX
    assert task.priority == TaskPriority.MEDIUM
    assert task.completion_evidence is None


def test_task_cannot_be_completed_without_evidence():
    """Verify that a Task cannot be created or updated to COMPLETED without completion evidence."""
    uid = uuid.uuid4()

    # Attempting COMPLETED without completion_evidence raises ValidationError
    with pytest.raises(ValidationError) as exc:
        Task(
            user_id=uid,
            title="Clean car",
            status=TaskStatus.COMPLETED,
        )
    assert "Task cannot be marked COMPLETED without verified completion_evidence" in str(exc.value)

    # With completion_evidence, COMPLETED succeeds
    evidence = TaskCompletionEvidence(
        evidence_type="USER_CONFIRMATION",
        description="User verbally confirmed: 'I have finished cleaning the car'",
        verified_by="user",
    )
    task_done = Task(
        user_id=uid,
        title="Clean car",
        status=TaskStatus.COMPLETED,
        completion_evidence=evidence,
    )
    assert task_done.status == TaskStatus.COMPLETED
    assert task_done.completion_evidence.verified_by == "user"


def test_task_cannot_be_in_progress_with_unresolved_blockers():
    """Verify that a Task cannot be IN_PROGRESS if unresolved blockers exist."""
    uid = uuid.uuid4()
    blocker = TaskBlocker(reason="Waiting for server credentials from client")

    with pytest.raises(ValidationError) as exc:
        Task(
            user_id=uid,
            title="Deploy application",
            status=TaskStatus.IN_PROGRESS,
            blockers=[blocker],
        )
    assert "cannot be IN_PROGRESS while 1 blockers remain unresolved" in str(exc.value)

    # Once blocker is resolved, IN_PROGRESS succeeds
    resolved_blocker = TaskBlocker(
        reason="Waiting for server credentials",
        resolved_at_utc=datetime.now(timezone.utc),
    )
    task_ok = Task(
        user_id=uid,
        title="Deploy application",
        status=TaskStatus.IN_PROGRESS,
        blockers=[resolved_blocker],
    )
    assert task_ok.status == TaskStatus.IN_PROGRESS


def test_project_ownership_and_status():
    """Verify Project container and ownership."""
    uid = uuid.uuid4()
    proj = Project(
        user_id=uid,
        title="Home Renovation",
        status=ProjectStatus.ACTIVE,
        priority=TaskPriority.HIGH,
        privacy_scope=PrivacyScope.PROJECT,
    )
    assert proj.user_id == uid
    assert proj.status == ProjectStatus.ACTIVE
    assert proj.priority == TaskPriority.HIGH
