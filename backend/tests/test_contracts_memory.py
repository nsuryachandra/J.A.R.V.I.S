"""Tests for MemoryCandidate, MemoryRecord, MemoryCorrection, and MemoryForgetRequest."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from pydantic import ValidationError
from app.contracts.common import (
    PrivacyScope,
    SensitivityLevel,
    SourceReference,
    SourceType,
)
from app.contracts.memory import (
    MemoryCandidate,
    MemoryConflict,
    MemoryCorrection,
    MemoryForgetRequest,
    MemoryRecord,
    MemoryStatus,
    MemoryType,
)


def test_memory_candidate_validation():
    """Verify MemoryCandidate constraints and default CANDIDATE status."""
    cand = MemoryCandidate(
        user_id=uuid.uuid4(),
        memory_type=MemoryType.SEMANTIC,
        content="User prefers green tea in the morning",
        confidence=0.85,
        source=SourceReference(source_type=SourceType.USER_INFERRED),
    )
    assert cand.status == MemoryStatus.CANDIDATE
    assert cand.confidence == 0.85

    # MemoryCandidate cannot be created with ACTIVE or CONFIRMED status
    with pytest.raises(ValidationError):
        MemoryCandidate(
            user_id=uuid.uuid4(),
            memory_type=MemoryType.SEMANTIC,
            content="User prefers green tea",
            confidence=0.85,
            source=SourceReference(source_type=SourceType.USER_INFERRED),
            status=MemoryStatus.CONFIRMED,
        )


def test_memory_record_confirmed_rules():
    """Verify that an inferred memory requires user confirmation to be marked CONFIRMED."""
    # Inferred memory without user confirmation fails validation when marked CONFIRMED
    with pytest.raises(ValidationError) as exc:
        MemoryRecord(
            user_id=uuid.uuid4(),
            memory_type=MemoryType.SEMANTIC,
            content="User allergic to peanuts",
            status=MemoryStatus.CONFIRMED,
            confidence=0.9,
            confirmed_by_user=False,
            source=SourceReference(source_type=SourceType.USER_INFERRED),
        )
    assert "USER_INFERRED memory cannot be CONFIRMED without explicit user confirmation" in str(exc.value)

    # Inferred memory with user confirmation succeeds
    rec = MemoryRecord(
        user_id=uuid.uuid4(),
        memory_type=MemoryType.SEMANTIC,
        content="User allergic to peanuts",
        status=MemoryStatus.CONFIRMED,
        confidence=0.9,
        confirmed_by_user=True,
        source=SourceReference(source_type=SourceType.USER_INFERRED),
    )
    assert rec.status == MemoryStatus.CONFIRMED
    assert rec.confirmed_by_user is True


def test_memory_record_expiration_validation():
    """Verify that valid_until_utc must be strictly after valid_from_utc."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        MemoryRecord(
            user_id=uuid.uuid4(),
            memory_type=MemoryType.TASK_RELATED,
            content="Temporary gate code 1234",
            status=MemoryStatus.ACTIVE,
            confidence=1.0,
            valid_from_utc=now,
            valid_until_utc=now - timedelta(hours=1),  # In the past relative to valid_from
            source=SourceReference(source_type=SourceType.USER_DIRECT),
        )


def test_memory_forget_request_audit_linkage():
    """Verify MemoryForgetRequest contains mandatory audit correlation tracking."""
    mid = uuid.uuid4()
    uid = uuid.uuid4()
    forget_req = MemoryForgetRequest(
        memory_id=mid,
        user_id=uid,
        reason="User requested deletion of obsolete medical detail",
    )
    assert forget_req.memory_id == mid
    assert forget_req.user_id == uid
    assert isinstance(forget_req.audit_correlation_id, uuid.UUID)


def test_memory_conflict_contract():
    """Verify MemoryConflict contract."""
    m1 = uuid.uuid4()
    c1 = uuid.uuid4()
    conflict = MemoryConflict(
        existing_memory_id=m1,
        conflicting_candidate_id=c1,
        discrepancy_description="Existing memory says vegetarian, candidate says user ordered steak",
    )
    assert conflict.existing_memory_id == m1
    assert conflict.conflicting_candidate_id == c1
    assert conflict.resolution_status == "UNRESOLVED"
