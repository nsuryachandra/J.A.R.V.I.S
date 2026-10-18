"""Tests for ToolCallProposal, ToolCallDecision, ToolExecutionResult, and VerificationEvidence."""

from datetime import datetime, timezone
import hashlib
import json
import uuid
import pytest
from pydantic import ValidationError
from app.contracts.tools import (
    ApprovalReference,
    ExecutionStatus,
    ToolCallDecision,
    ToolCallProposal,
    ToolExecutionFailure,
    ToolExecutionRequest,
    ToolExecutionResult,
    VerificationEvidence,
)


def test_tool_call_proposal_invariants():
    """Verify ToolCallProposal invariants: starts in PROPOSED and cannot claim completion."""
    pid = uuid.uuid4()
    args = {"recipient": "boss@company.com", "subject": "Update"}
    canonical_hash = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()

    proposal = ToolCallProposal(
        proposal_id=pid,
        tool_name="email.send_draft",
        arguments=args,
        canonical_arguments_hash=canonical_hash,
        risk_class="CONSEQUENTIAL",
        proposed_by_agent="executive_agent",
    )
    assert proposal.status == ExecutionStatus.PROPOSED
    assert proposal.tool_name == "email.send_draft"

    # Proposal claiming SUCCEEDED or EXECUTING raises ValidationError
    with pytest.raises(ValidationError) as exc:
        ToolCallProposal(
            proposal_id=pid,
            tool_name="email.send_draft",
            arguments=args,
            canonical_arguments_hash=canonical_hash,
            proposed_by_agent="executive_agent",
            status=ExecutionStatus.SUCCEEDED,
        )
    assert "Use ToolExecutionResult for executed actions" in str(exc.value)


def test_tool_execution_result_state_invariants():
    """Verify ToolExecutionResult must represent completed outcome, not PROPOSED."""
    pid = uuid.uuid4()
    eid = uuid.uuid4()

    # Attempting to create execution result in PROPOSED state raises ValidationError
    with pytest.raises(ValidationError) as exc:
        ToolExecutionResult(
            execution_id=eid,
            proposal_id=pid,
            tool_name="notes.create_note",
            status=ExecutionStatus.PROPOSED,
            output={},
            duration_ms=45,
        )
    assert "must represent completed outcome" in str(exc.value)

    # Valid execution result
    evidence = VerificationEvidence(
        verification_method="API_RECEIPT",
        verification_payload={"status_code": 200, "note_id": str(uuid.uuid4())},
    )
    res = ToolExecutionResult(
        execution_id=eid,
        proposal_id=pid,
        tool_name="notes.create_note",
        status=ExecutionStatus.SUCCEEDED,
        output={"status": "created"},
        evidence=evidence,
        duration_ms=45,
    )
    assert res.status == ExecutionStatus.SUCCEEDED
    assert res.evidence.verification_method == "API_RECEIPT"


def test_approval_reference_hash_validation():
    """Verify ApprovalReference enforces 64-char SHA-256 hash format."""
    aid = uuid.uuid4()
    # Invalid hash length raises ValidationError
    with pytest.raises(ValidationError):
        ApprovalReference(
            approval_id=aid,
            approved_by="user",
            canonical_arguments_hash="short_hash",
        )

    # Valid 64-char hash succeeds
    valid_hash = "a" * 64
    ref = ApprovalReference(
        approval_id=aid,
        approved_by="user",
        canonical_arguments_hash=valid_hash,
    )
    assert ref.canonical_arguments_hash == valid_hash
