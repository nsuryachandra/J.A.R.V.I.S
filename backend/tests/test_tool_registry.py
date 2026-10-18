"""Tool registry, input validation schemas, and risk classification tests."""

import pytest
from pydantic import BaseModel, ValidationError
from app.services.tool_registry import (
    ModeratePolicy,
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


def test_tool_registration_and_lookup():
    """Verify registering a tool and retrieving its metadata."""
    local_registry = ToolRegistry()
    tool = ToolDefinition(
        name="test.dummy_tool",
        version="1.0.0",
        description="A dummy test tool",
        risk_class=RiskClass.SAFE,
        input_schema=DummyInput,
        output_schema=DummyOutput,
    )
    local_registry.register(tool)

    assert local_registry.is_registered("test.dummy_tool") is True
    retrieved = local_registry.get("test.dummy_tool")
    assert retrieved is not None
    assert retrieved.name == "test.dummy_tool"
    assert retrieved.risk_class == RiskClass.SAFE
    assert retrieved.requires_approval is False


def test_consequential_tool_always_requires_approval():
    """Verify that any tool declared as CONSEQUENTIAL automatically sets requires_approval=True."""
    tool = ToolDefinition(
        name="system.dangerous_action",
        version="1.0.0",
        description="Dangerous operation",
        risk_class=RiskClass.CONSEQUENTIAL,
        input_schema=DummyInput,
        output_schema=DummyOutput,
        requires_approval=False,  # Attempting to override MUST be enforced to True
    )
    assert tool.requires_approval is True


def test_moderate_policy_approval_default():
    """Verify moderate policy can flag a moderate tool to require approval by default."""
    policy = ModeratePolicy(requires_approval_by_default=True, write_operation=True)
    tool = ToolDefinition(
        name="data.moderate_write",
        version="1.0.0",
        description="Write operation requiring approval",
        risk_class=RiskClass.MODERATE,
        input_schema=DummyInput,
        output_schema=DummyOutput,
        moderate_policy=policy,
    )
    assert tool.requires_approval is True


def test_tool_input_schema_validation():
    """Verify Pydantic input schema rejects invalid or missing fields."""
    registry = get_tool_registry()
    email_tool = registry.get("email.send_mock")
    assert email_tool is not None

    # Valid arguments
    valid = email_tool.input_schema(recipient="test@example.com", subject="Hi", body="Text")
    assert valid.recipient == "test@example.com"

    # Missing body raises ValidationError
    with pytest.raises(ValidationError):
        email_tool.input_schema(recipient="test@example.com", subject="Hi")
