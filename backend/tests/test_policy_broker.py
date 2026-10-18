"""Tests for PolicyBroker evaluation of SAFE, MODERATE, and CONSEQUENTIAL tools."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.models.user import User
from app.services.policy_broker import BrokerDecision, PolicyBroker
from app.services.tool_registry import (
    RiskClass,
    ToolDefinition,
    ToolRegistry,
    get_tool_registry,
)


class DummyInput(BaseModel):
    query: str
    count: int = 5


class DummyOutput(BaseModel):
    success: bool


@pytest.fixture
def mock_user() -> User:
    return User(
        email="test_pilot@jarvis.ai",
        hashed_password="hashed_pw",
        timezone="Asia/Kolkata",
    )


@pytest.mark.asyncio
async def test_policy_broker_safe_read_operation(
    db_session: AsyncSession, mock_user: User
):
    """Verify SAFE operation is permitted directly when registry and scope checks pass."""
    db_session.add(mock_user)
    await db_session.flush()

    broker = PolicyBroker()
    eval_result = await broker.evaluate_action(
        session=db_session,
        actor=mock_user,
        tool_name="profile.read",
        arguments={},
    )
    assert eval_result.decision == BrokerDecision.ALLOW
    assert eval_result.risk_class == "SAFE"


@pytest.mark.asyncio
async def test_policy_broker_moderate_read_operation(
    db_session: AsyncSession, mock_user: User
):
    """Verify MODERATE read operation passes when no extra capabilities are required."""
    db_session.add(mock_user)
    await db_session.flush()

    broker = PolicyBroker()
    eval_result = await broker.evaluate_action(
        session=db_session,
        actor=mock_user,
        tool_name="tasks.read",
        arguments={"limit": 10},
    )
    assert eval_result.decision == BrokerDecision.ALLOW
    assert eval_result.risk_class == "MODERATE"


@pytest.mark.asyncio
async def test_policy_broker_moderate_write_operation(
    db_session: AsyncSession, mock_user: User
):
    """Verify MODERATE write operation passes under its explicit write policy."""
    db_session.add(mock_user)
    await db_session.flush()

    broker = PolicyBroker()
    eval_result = await broker.evaluate_action(
        session=db_session,
        actor=mock_user,
        tool_name="tasks.create",
        arguments={"title": "Test task", "priority": "high"},
    )
    assert eval_result.decision == BrokerDecision.ALLOW
    assert eval_result.risk_class == "MODERATE"


@pytest.mark.asyncio
async def test_policy_broker_moderate_sensitive_data_denied_without_capability(
    db_session: AsyncSession, mock_user: User
):
    """Verify MODERATE sensitive data tool is denied if actor lacks required user capability."""
    db_session.add(mock_user)
    await db_session.flush()

    broker = PolicyBroker()
    # Actor provides NO capabilities
    eval_result = await broker.evaluate_action(
        session=db_session,
        actor=mock_user,
        tool_name="documents.read_sensitive",
        arguments={"document_id": "doc_123"},
        actor_capabilities=set(),
    )
    assert eval_result.decision == BrokerDecision.DENY
    assert "capabilit" in eval_result.reason.lower()


@pytest.mark.asyncio
async def test_policy_broker_moderate_sensitive_data_allowed_with_capability(
    db_session: AsyncSession, mock_user: User
):
    """Verify MODERATE sensitive data tool is allowed when actor possesses required capability."""
    db_session.add(mock_user)
    await db_session.flush()

    broker = PolicyBroker()
    eval_result = await broker.evaluate_action(
        session=db_session,
        actor=mock_user,
        tool_name="documents.read_sensitive",
        arguments={"document_id": "doc_123"},
        actor_capabilities={"docs:read_sensitive"},
    )
    assert eval_result.decision == BrokerDecision.ALLOW


@pytest.mark.asyncio
async def test_policy_broker_consequential_requires_approval(
    db_session: AsyncSession, mock_user: User
):
    """Verify CONSEQUENTAL tool without approval returns REQUIRE_APPROVAL and generates request."""
    db_session.add(mock_user)
    await db_session.flush()

    broker = PolicyBroker()
    eval_result = await broker.evaluate_action(
        session=db_session,
        actor=mock_user,
        tool_name="email.send_mock",
        arguments={"recipient": "ceo@jarvis.ai", "subject": "Update", "body": "All good"},
        actor_capabilities={"email:send"},
    )
    assert eval_result.decision == BrokerDecision.REQUIRE_APPROVAL
    assert eval_result.approval_request is not None
    assert eval_result.approval_request.tool_name == "email.send_mock"
    assert eval_result.approval_request.status == "PENDING"


@pytest.mark.asyncio
async def test_policy_broker_disabled_tool(
    db_session: AsyncSession, mock_user: User
):
    """Verify disabled tool evaluation returns TOOL_DISABLED."""
    db_session.add(mock_user)
    await db_session.flush()

    custom_registry = ToolRegistry()
    disabled_tool = ToolDefinition(
        name="system.offline_tool",
        version="1.0.0",
        description="Offline tool",
        risk_class=RiskClass.SAFE,
        input_schema=DummyInput,
        output_schema=DummyOutput,
        is_enabled=False,
    )
    custom_registry.register(disabled_tool)

    broker = PolicyBroker(registry=custom_registry)
    eval_result = await broker.evaluate_action(
        session=db_session,
        actor=mock_user,
        tool_name="system.offline_tool",
        arguments={"query": "test", "count": 1},
    )
    assert eval_result.decision == BrokerDecision.TOOL_DISABLED
