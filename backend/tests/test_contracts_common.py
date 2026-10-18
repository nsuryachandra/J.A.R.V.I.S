"""Tests for common contracts, identifiers, provenance, pagination, and error representations."""

from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError
from app.contracts.common import (
    APIError,
    CorrelationContext,
    OperationResult,
    PaginationRequest,
    PaginationResponse,
    PrivacyScope,
    Provenance,
    SensitivityLevel,
    SortOrder,
    SourceReference,
    SourceType,
    UserScopedResource,
    ValidationIssue,
    VersionedContract,
)


def test_sensitivity_level_ordering():
    """Verify strict comparative ordering between sensitivity tiers."""
    assert SensitivityLevel.PUBLIC < SensitivityLevel.INTERNAL
    assert SensitivityLevel.INTERNAL < SensitivityLevel.PRIVATE
    assert SensitivityLevel.PRIVATE < SensitivityLevel.SENSITIVE
    assert SensitivityLevel.SENSITIVE < SensitivityLevel.HIGHLY_SENSITIVE

    assert SensitivityLevel.PUBLIC.is_less_or_equal(SensitivityLevel.PUBLIC)
    assert SensitivityLevel.PUBLIC.is_less_or_equal(SensitivityLevel.HIGHLY_SENSITIVE)
    assert SensitivityLevel.HIGHLY_SENSITIVE.is_strictly_greater(SensitivityLevel.PRIVATE)


def test_source_reference_utc_enforcement():
    """Verify that source reference timestamps must be timezone-aware UTC."""
    # Aware datetime succeeds
    aware_dt = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    ref = SourceReference(source_type=SourceType.USER_DIRECT, timestamp_utc=aware_dt)
    assert ref.timestamp_utc == aware_dt

    # Naive datetime raises ValidationError
    naive_dt = datetime(2026, 10, 18, 12, 0, 0)
    with pytest.raises(ValidationError):
        SourceReference(source_type=SourceType.USER_DIRECT, timestamp_utc=naive_dt)


def test_provenance_validation():
    """Verify provenance metadata schema."""
    ref = SourceReference(source_type=SourceType.CONVERSATION, source_id="msg_123")
    prov = Provenance(
        source=ref,
        author_id=uuid.uuid4(),
        actor_type="user",
        evidence="Spoken in morning check-in",
    )
    assert prov.source.source_type == SourceType.CONVERSATION
    assert prov.actor_type == "user"
    assert prov.created_at_utc.tzinfo == timezone.utc


def test_correlation_context_defaults():
    """Verify correlation context provides valid UUIDs."""
    ctx = CorrelationContext()
    assert isinstance(ctx.correlation_id, uuid.UUID)
    assert ctx.session_id is None
    assert ctx.user_id is None


def test_versioned_contract_forbids_extra_fields():
    """Verify VersionedContract rejects unknown extra fields."""
    contract = VersionedContract(contract_type="test.entity")
    assert contract.schema_version == "1.0.0"

    with pytest.raises(ValidationError):
        VersionedContract(contract_type="test.entity", unexpected_extra_field="malicious")


def test_user_scoped_resource_requires_user_id():
    """Verify UserScopedResource enforces ownership and UTC timestamps."""
    uid = uuid.uuid4()
    resource = UserScopedResource(user_id=uid, contract_type="resource.item")
    assert resource.user_id == uid
    assert isinstance(resource.resource_id, uuid.UUID)
    assert resource.created_at_utc.tzinfo == timezone.utc

    with pytest.raises(ValidationError):
        # Missing user_id
        UserScopedResource(contract_type="resource.item")


def test_pagination_request_bounds():
    """Verify pagination validation boundaries."""
    req = PaginationRequest(page=1, page_size=25, sort_order=SortOrder.ASC)
    assert req.page == 1
    assert req.page_size == 25

    # Page < 1 rejected
    with pytest.raises(ValidationError):
        PaginationRequest(page=0)

    # Page size > 100 rejected
    with pytest.raises(ValidationError):
        PaginationRequest(page_size=101)


def test_operation_result_consistency():
    """Verify OperationResult ensures consistency between success flag and error payload."""
    res_success = OperationResult[str](success=True, data="computed")
    assert res_success.data == "computed"
    assert res_success.error is None

    # success=True with error raises ValidationError
    with pytest.raises(ValidationError):
        OperationResult[str](
            success=True,
            error=APIError(code="FAIL", message="Something broke"),
        )

    # success=False without error raises ValidationError
    with pytest.raises(ValidationError):
        OperationResult[str](success=False)
