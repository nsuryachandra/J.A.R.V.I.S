"""Tests for AgentRun, AgentGoal, AgentInput, AgentOutput, and AgentDelegation."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from pydantic import ValidationError
from app.contracts.agents import (
    AgentDelegation,
    AgentFailure,
    AgentGoal,
    AgentInput,
    AgentOutput,
    AgentRun,
    AgentRunStatus,
    AgentType,
)


def test_agent_run_lifecycle_and_validation():
    """Verify AgentRun creation and initial state."""
    uid = uuid.uuid4()
    goal = AgentGoal(
        description="Organize daily agenda",
        success_criteria=["Events reviewed", "Tasks prioritized"],
    )
    agent_in = AgentInput(
        user_id=uid,
        prompt="Prepare my briefing for today",
    )

    run = AgentRun(
        user_id=uid,
        agent_type=AgentType.EXECUTIVE,
        goal=goal,
        input=agent_in,
        allowed_tools=["calendar.list_events", "tasks.list_tasks"],
    )
    assert run.user_id == uid
    assert run.status == AgentRunStatus.CREATED
    assert run.parent_run_id is None


def test_agent_run_terminal_state_evidence():
    """Verify that SUCCEEDED requires output, and FAILED requires failure details."""
    uid = uuid.uuid4()
    goal = AgentGoal(description="Test goal", success_criteria=["criterion 1"])
    agent_in = AgentInput(user_id=uid, prompt="Do work")

    # SUCCEEDED without output raises ValidationError
    with pytest.raises(ValidationError) as exc1:
        AgentRun(
            user_id=uid,
            agent_type=AgentType.RESEARCH,
            status=AgentRunStatus.SUCCEEDED,
            goal=goal,
            input=agent_in,
        )
    assert "must provide an output object" in str(exc1.value)

    # FAILED without failure raises ValidationError
    with pytest.raises(ValidationError) as exc2:
        AgentRun(
            user_id=uid,
            agent_type=AgentType.RESEARCH,
            status=AgentRunStatus.FAILED,
            goal=goal,
            input=agent_in,
        )
    assert "must provide a failure object" in str(exc2.value)

    # Valid SUCCEEDED run
    now = datetime.now(timezone.utc)
    valid_run = AgentRun(
        user_id=uid,
        agent_type=AgentType.RESEARCH,
        status=AgentRunStatus.SUCCEEDED,
        goal=goal,
        input=agent_in,
        started_at_utc=now,
        ended_at_utc=now + timedelta(seconds=5),
        output=AgentOutput(
            result_summary="Briefing assembled successfully",
            verification_status="VERIFIED",
        ),
    )
    assert valid_run.status == AgentRunStatus.SUCCEEDED
    assert valid_run.output.verification_status == "VERIFIED"


def test_agent_delegation_contract():
    """Verify parent-child delegation relationship."""
    parent_id = uuid.uuid4()
    delegation = AgentDelegation(
        parent_run_id=parent_id,
        child_agent_type=AgentType.TASK,
        sub_goal="Prioritize overdue inbox items",
    )
    assert delegation.parent_run_id == parent_id
    assert delegation.child_agent_type == AgentType.TASK
