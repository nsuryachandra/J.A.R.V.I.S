"""Unit tests for TaskService: projects, tasks, blocker state machine, DAG cycle detection, and pending work."""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.approval import ApprovalRequest
from app.models.task import Project, Task
from app.services.task_service import TaskService


@pytest.mark.asyncio
async def test_project_crud_and_tenant_isolation(db_session):
    """Verify project creation, update, listing, and cross-user isolation."""
    uid_a = uuid.uuid4()
    uid_b = uuid.uuid4()

    # Create project for User A
    proj = await TaskService.create_project(
        db=db_session,
        user_id=uid_a,
        title="Autonomous Operating System",
        description="Core architecture initiatives",
        priority="HIGH",
    )
    assert proj.id is not None
    assert proj.title == "Autonomous Operating System"
    assert proj.status == "ACTIVE"
    assert proj.priority == "HIGH"

    # User A lists projects
    projects_a = await TaskService.list_projects(db_session, uid_a)
    assert len(projects_a) == 1
    assert projects_a[0].id == proj.id

    # User B cannot access User A's project
    with pytest.raises(PermissionDeniedError):
        await TaskService.get_project(db_session, proj.id, uid_b)

    with pytest.raises(PermissionDeniedError):
        await TaskService.update_project(db_session, proj.id, uid_b, title="Malicious update")

    # User A updates project
    updated = await TaskService.update_project(
        db_session,
        proj.id,
        uid_a,
        description="Updated architecture blueprint",
        status="ON_HOLD",
    )
    assert updated.description == "Updated architecture blueprint"
    assert updated.status == "ON_HOLD"


@pytest.mark.asyncio
async def test_task_creation_and_project_linking(db_session):
    """Verify task creation under project, validation rules, and defaults."""
    uid = uuid.uuid4()
    proj = await TaskService.create_project(db_session, uid, "Q4 Deliverables")

    # Create task linked to project
    due = datetime.now(timezone.utc) + timedelta(days=3)
    task = await TaskService.create_task(
        db=db_session,
        user_id=uid,
        project_id=proj.id,
        title="Implement OAuth provider",
        priority="HIGH",
        due_at=due,
    )
    assert task.id is not None
    assert task.project_id == proj.id
    assert task.status == "INBOX"
    assert task.priority == "HIGH"
    assert task.due_at is not None

    # Empty title rejected
    with pytest.raises(ValidationError):
        await TaskService.create_task(db_session, uid, title="   ")

    # Linking to another user's project rejected
    other_uid = uuid.uuid4()
    other_proj = await TaskService.create_project(db_session, other_uid, "Other Project")
    with pytest.raises(PermissionDeniedError):
        await TaskService.create_task(db_session, uid, title="Invalid link", project_id=other_proj.id)


@pytest.mark.asyncio
async def test_task_cannot_be_completed_without_evidence(db_session):
    """Verify that a task cannot be marked COMPLETED without verifiable completion evidence."""
    uid = uuid.uuid4()
    task = await TaskService.create_task(
        db=db_session,
        user_id=uid,
        title="Deploy microservice cluster",
    )

    # Attempt to directly set status to COMPLETED without evidence -> rejected
    with pytest.raises(ValidationError) as exc:
        await TaskService.update_task(
            db=db_session,
            task_id=task.id,
            user_id=uid,
            status="COMPLETED",
        )
    assert "without verified completion_evidence" in str(exc.value)

    # Cannot create directly as COMPLETED
    with pytest.raises(ValidationError):
        await TaskService.create_task(
            db=db_session,
            user_id=uid,
            title="Pre-completed task",
            status="COMPLETED",
        )

    # Complete with valid evidence -> succeeds
    completed = await TaskService.complete_task(
        db=db_session,
        task_id=task.id,
        user_id=uid,
        evidence_type="TOOL_OUTPUT",
        description="CI/CD deployment log certified zero exit code",
        verified_by="deployment_agent",
        artifact_uri="https://ci.internal/build/123",
    )
    assert completed.status == "COMPLETED"
    assert completed.completed_at is not None
    assert completed.completion_evidence["evidence_type"] == "TOOL_OUTPUT"
    assert completed.completion_evidence["verified_by"] == "deployment_agent"


@pytest.mark.asyncio
async def test_task_blocker_lifecycle_and_in_progress_invariant(db_session):
    """Verify that tasks cannot be IN_PROGRESS while unresolved blockers exist, and test blocker resolution."""
    uid = uuid.uuid4()
    task = await TaskService.create_task(
        db=db_session,
        user_id=uid,
        title="Run database migration",
    )

    # Add blocker
    blocked = await TaskService.add_blocker(
        db=db_session,
        task_id=task.id,
        user_id=uid,
        reason="Awaiting production database replica sync",
        next_action="Ping DBA team",
    )
    assert blocked.status == "BLOCKED"
    assert blocked.blocked_reason == "Awaiting production database replica sync"
    assert blocked.next_action == "Ping DBA team"
    assert len(blocked.blockers) == 1
    blocker_id = blocked.blockers[0]["blocker_id"]

    # Attempt to transition to IN_PROGRESS while blocker is unresolved -> rejected
    with pytest.raises(ValidationError) as exc:
        await TaskService.update_task(
            db=db_session,
            task_id=task.id,
            user_id=uid,
            status="IN_PROGRESS",
        )
    assert "blockers remain unresolved" in str(exc.value)

    # Resolve blocker
    unblocked = await TaskService.resolve_blocker(
        db=db_session,
        task_id=task.id,
        user_id=uid,
        blocker_id=blocker_id,
    )
    assert unblocked.status == "TODO"
    assert unblocked.blocked_reason is None

    # Now transitioning to IN_PROGRESS succeeds
    in_prog = await TaskService.update_task(
        db=db_session,
        task_id=task.id,
        user_id=uid,
        status="IN_PROGRESS",
    )
    assert in_prog.status == "IN_PROGRESS"
    assert in_prog.started_at is not None


@pytest.mark.asyncio
async def test_task_dag_dependency_and_cycle_detection(db_session):
    """Verify DAG task dependency chain and prevent circular loops."""
    uid = uuid.uuid4()
    task_a = await TaskService.create_task(db_session, uid, "Task A: Ship frontend")
    task_b = await TaskService.create_task(db_session, uid, "Task B: Build API")
    task_c = await TaskService.create_task(db_session, uid, "Task C: Design database")

    # A depends on B
    await TaskService.add_dependency(db_session, task_a.id, uid, task_b.id)
    # B depends on C
    await TaskService.add_dependency(db_session, task_b.id, uid, task_c.id)

    # Self-dependency rejected
    with pytest.raises(ValidationError):
        await TaskService.add_dependency(db_session, task_a.id, uid, task_a.id)

    # Attempt C depends on A -> Cycle (A -> B -> C -> A) must be rejected
    with pytest.raises(ValidationError) as exc:
        await TaskService.add_dependency(db_session, task_c.id, uid, task_a.id)
    assert "Circular dependency detected" in str(exc.value)


@pytest.mark.asyncio
async def test_pending_work_query_and_yesterday_continuity(db_session):
    """Verify comprehensive pending work analysis and PRD 14.3 / 14.4 yesterday continuity."""
    uid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. In-progress task
    await TaskService.create_task(
        db=db_session,
        user_id=uid,
        title="Active code review",
        status="IN_PROGRESS",
    )

    # 2. Blocked task
    t_block = await TaskService.create_task(db_session, uid, "Deploy staging")
    await TaskService.add_blocker(db_session, t_block.id, uid, "Staging VM out of disk space")

    # 3. Overdue task
    await TaskService.create_task(
        db=db_session,
        user_id=uid,
        title="Submit tax paperwork",
        due_at=now - timedelta(days=2),
    )

    # 4. Upcoming task
    await TaskService.create_task(
        db=db_session,
        user_id=uid,
        title="Prepare board slides",
        due_at=now + timedelta(days=3),
    )

    # 5. Pending Approval Request
    approval = ApprovalRequest(
        user_id=uid,
        tool_name="email.send",
        tool_version="1.0.0",
        normalized_arguments={"to": "investor@fund.com"},
        arguments_hash="hash_dummy_12345",
        target_resource="email:investor@fund.com",
        risk_class="CONSEQUENTIAL",
        status="PENDING",
        expires_at=now + timedelta(minutes=15),
    )
    db_session.add(approval)
    await db_session.commit()

    # Query pending work
    pending = await TaskService.query_pending_work(
        db=db_session,
        user_id=uid,
        include_yesterday=True,
    )

    summary = pending["summary"]
    assert summary["total_unfinished"] >= 4
    assert summary["in_progress_count"] >= 1
    assert summary["blocked_count"] >= 1
    assert summary["overdue_count"] >= 1
    assert summary["upcoming_deadlines_count"] >= 1
    assert summary["pending_approvals_count"] >= 1

    # Verify lists
    assert any(t.title == "Active code review" for t in pending["in_progress"])
    assert any(t.title == "Deploy staging" for t in pending["blocked"])
    assert any(t.title == "Submit tax paperwork" for t in pending["overdue"])
    assert any(t.title == "Prepare board slides" for t in pending["upcoming_deadlines"])
    assert any(a["tool_name"] == "email.send" for a in pending["pending_approvals"])
    assert "yesterday_continuity" in pending
