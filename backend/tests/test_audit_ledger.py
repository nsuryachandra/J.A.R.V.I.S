"""Tests for append-only audit ledger, hash-chain concurrency, and tamper detection."""

import asyncio
from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog
from app.services.audit_service import AuditService


@pytest.mark.asyncio
async def test_audit_log_append_and_hash_chaining(db_session: AsyncSession):
    """Verify that sequential audit events form a valid cryptographic SHA-256 hash chain."""
    uid = uuid4()

    # Append 5 sequential audit events
    for i in range(1, 6):
        await AuditService.record_event(
            session=db_session,
            action_type=f"EVENT_{i}",
            decision="ALLOW",
            user_id=uid,
            details={"step": i},
        )
    await db_session.commit()

    is_valid, err = await AuditService.verify_chain(session=db_session)
    assert is_valid is True
    assert err is None


@pytest.mark.asyncio
async def test_audit_log_concurrent_writes_deterministic_chain(
    db_session: AsyncSession,
):
    """Verify that multiple concurrent async writers serialize deterministically without breaking the chain."""
    uid = uuid4()

    async def write_event(index: int):
        await AuditService.record_event(
            session=db_session,
            action_type=f"CONCURRENT_EVENT_{index}",
            decision="ALLOW",
            user_id=uid,
            details={"worker_index": index},
        )

    # Launch 10 concurrent writes simultaneously
    await asyncio.gather(*(write_event(i) for i in range(10)))
    await db_session.commit()

    is_valid, err = await AuditService.verify_chain(session=db_session)
    assert is_valid is True
    assert err is None


@pytest.mark.asyncio
async def test_audit_log_tamper_detection(db_session: AsyncSession):
    """Verify that modifying a record's hash or previous hash is immediately flagged as tampering."""
    uid = uuid4()
    log1 = await AuditService.record_event(
        session=db_session,
        action_type="LEGIT_EVENT_1",
        decision="ALLOW",
        user_id=uid,
    )
    log2 = await AuditService.record_event(
        session=db_session,
        action_type="LEGIT_EVENT_2",
        decision="ALLOW",
        user_id=uid,
    )
    await db_session.commit()

    # Malicious actor tampers with log1's record_hash directly in DB
    log1.record_hash = "a" * 64
    await db_session.commit()

    is_valid, err = await AuditService.verify_chain(session=db_session)
    assert is_valid is False
    assert "tampered" in err.lower() or "chain break" in err.lower()


@pytest.mark.asyncio
async def test_audit_log_masks_sensitive_secrets(db_session: AsyncSession):
    """Verify that sensitive dictionary keys and tokens are automatically masked in audit details."""
    uid = uuid4()
    log = await AuditService.record_event(
        session=db_session,
        action_type="LOGIN_ATTEMPT",
        decision="ALLOW",
        user_id=uid,
        details={
            "user": "tony",
            "password": "ClearTextPasswordShouldBeMasked",
            "api_key": "nvapi-abcdef12345678901234567890",
            "token": "secret_jwt_token",
        },
    )
    await db_session.commit()

    assert log.details["user"] == "tony"
    assert log.details["password"] == "***MASKED***"
    assert log.details["api_key"] == "***MASKED***"
    assert log.details["token"] == "***MASKED***"
