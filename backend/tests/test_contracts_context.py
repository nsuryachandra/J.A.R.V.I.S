"""Tests for ContextItem, ContextBudget, ContextWindow, and ContextAssemblyResult."""

import uuid
import pytest
from pydantic import ValidationError
from app.contracts.common import (
    PrivacyScope,
    SensitivityLevel,
    SourceReference,
    SourceType,
)
from app.contracts.context import (
    ContextAssemblyResult,
    ContextBudget,
    ContextItem,
    ContextItemType,
    ContextSelectionReason,
    ContextWindow,
)


def test_context_budget_bounds_validation():
    """Verify ContextBudget ensures sub-allocations do not exceed max_tokens."""
    # Valid budget
    budget = ContextBudget(
        max_tokens=8000,
        allocated_system_tokens=1000,
        allocated_memory_tokens=2000,
        allocated_conversation_tokens=4000,
    )
    assert budget.max_tokens == 8000

    # Allocations exceeding max_tokens raises ValidationError
    with pytest.raises(ValidationError) as exc:
        ContextBudget(
            max_tokens=5000,
            allocated_system_tokens=2000,
            allocated_memory_tokens=2000,
            allocated_conversation_tokens=2000,  # Sum = 6000 > 5000
        )
    assert "exceeds max_tokens" in str(exc.value)


def test_context_window_token_math_and_ceiling():
    """Verify ContextWindow validates total token count matches item sum and adheres to budget."""
    uid = uuid.uuid4()
    budget = ContextBudget(max_tokens=4000)

    item1 = ContextItem(
        item_type=ContextItemType.CURRENT_MESSAGE,
        source=SourceReference(source_type=SourceType.USER_DIRECT),
        content="What is on my schedule?",
        token_estimate=15,
        selection_reason=ContextSelectionReason.DIRECT_INPUT,
    )
    item2 = ContextItem(
        item_type=ContextItemType.SYSTEM_POLICY,
        source=SourceReference(source_type=SourceType.SYSTEM_EVENT),
        content="System instructions: Be concise and helpful.",
        token_estimate=30,
        selection_reason=ContextSelectionReason.MANDATORY_SAFETY,
    )

    # Valid ContextWindow (15 + 30 = 45)
    win = ContextWindow(
        user_id=uid,
        items=[item1, item2],
        total_estimated_tokens=45,
        budget=budget,
    )
    assert win.total_estimated_tokens == 45
    assert len(win.items) == 2

    # Mismatched token estimate raises ValidationError
    with pytest.raises(ValidationError) as exc1:
        ContextWindow(
            user_id=uid,
            items=[item1, item2],
            total_estimated_tokens=50,  # Should be 45
            budget=budget,
        )
    assert "does not match sum of items" in str(exc1.value)

    # Exceeding budget ceiling raises ValidationError
    small_budget = ContextBudget(
        max_tokens=100,
        allocated_system_tokens=30,
        allocated_memory_tokens=30,
        allocated_conversation_tokens=30,
    )
    big_item = ContextItem(
        item_type=ContextItemType.LONG_TERM_MEMORY,
        source=SourceReference(source_type=SourceType.CONVERSATION),
        content="Large memory dump",
        token_estimate=150,
        selection_reason=ContextSelectionReason.RELEVANCE_MATCH,
    )
    with pytest.raises(ValidationError) as exc2:
        ContextWindow(
            user_id=uid,
            items=[big_item],
            total_estimated_tokens=150,
            budget=small_budget,
        )
    assert "exceeds maximum budget" in str(exc2.value)
