"""Unit tests for MemoryService lifecycle, confirmation, corrections, forget, and search."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.memory import Memory, MemoryHistory
from app.services.memory_service import MemoryService


@pytest.mark.asyncio
async def test_memory_creation_with_embedding(db_session):
    """Verify creating a memory persists record, generates embedding vector, and creates history."""
    uid = uuid.uuid4()
    content = "User prefers black coffee with no sugar"
    memory = await MemoryService.create_memory(
        db=db_session,
        user_id=uid,
        content=content,
        memory_type="SEMANTIC",
        confidence=0.95,
        status="ACTIVE",
        privacy_scope="PERSONAL",
        sensitivity=20,
    )

    assert memory.id is not None
    assert memory.user_id == uid
    assert memory.content == content
    assert memory.confidence == 0.95
    assert memory.status == "ACTIVE"
    assert memory.embedding_vector is not None
    assert len(memory.embedding_vector) == 64  # Deterministic 64-dim vector
    assert len(memory.history) == 1
    assert memory.history[0].action == "CREATED"


@pytest.mark.asyncio
async def test_memory_candidate_and_confirmation(db_session):
    """Verify candidate memory requires confirmation to become ACTIVE."""
    uid = uuid.uuid4()
    # Inferred memory without explicit confirmation starts as CANDIDATE
    memory = await MemoryService.create_memory(
        db=db_session,
        user_id=uid,
        content="User might be planning a trip to Tokyo in spring",
        memory_type="EPISODIC",
        confidence=0.6,
        status="ACTIVE",  # Attempting active on inferred
        confirmed_by_user=False,
        source_type="USER_INFERRED",
    )
    # Service automatically forces to CANDIDATE
    assert memory.status == "CANDIDATE"
    assert memory.confirmed_by_user is False

    # Confirm the candidate
    confirmed = await MemoryService.confirm_memory(
        db=db_session,
        memory_id=memory.id,
        user_id=uid,
    )
    assert confirmed.status == "ACTIVE"
    assert confirmed.confirmed_by_user is True

    # History now contains CREATED and CONFIRMED
    actions = [h.action for h in confirmed.history]
    assert "CREATED" in actions
    assert "CONFIRMED" in actions


@pytest.mark.asyncio
async def test_memory_update_and_history(db_session):
    """Verify mutating memory content updates embedding and appends history."""
    uid = uuid.uuid4()
    memory = await MemoryService.create_memory(
        db=db_session,
        user_id=uid,
        content="Flight number is AI-101",
    )
    old_vec = list(memory.embedding_vector)

    updated = await MemoryService.update_memory(
        db=db_session,
        memory_id=memory.id,
        user_id=uid,
        new_content="Flight number is AI-102 (rescheduled)",
    )
    assert updated.content == "Flight number is AI-102 (rescheduled)"
    assert updated.embedding_vector != old_vec

    # Verify history captures previous and new content
    latest_hist = updated.history[-1]
    assert latest_hist.action == "UPDATED"
    assert latest_hist.previous_content == "Flight number is AI-101"
    assert latest_hist.new_content == "Flight number is AI-102 (rescheduled)"


@pytest.mark.asyncio
async def test_memory_correction_supersedes_original(db_session):
    """Verify correcting memory marks old record SUPERSEDED and links new active record."""
    uid = uuid.uuid4()
    old_mem = await MemoryService.create_memory(
        db=db_session,
        user_id=uid,
        content="Meeting is in Conference Room Alpha",
    )

    old_updated, new_mem = await MemoryService.correct_memory(
        db=db_session,
        memory_id=old_mem.id,
        user_id=uid,
        corrected_content="Meeting is in Conference Room Beta",
        reason="Room Alpha air conditioning under repair",
    )

    assert old_updated.status == "SUPERSEDED"
    assert old_updated.superseded_by_id == new_mem.id

    assert new_mem.status == "ACTIVE"
    assert new_mem.content == "Meeting is in Conference Room Beta"
    assert new_mem.confirmed_by_user is True


@pytest.mark.asyncio
async def test_memory_forget_right_to_be_forgotten(db_session):
    """Verify forget_memory marks record DELETED and creates audit history."""
    uid = uuid.uuid4()
    memory = await MemoryService.create_memory(
        db=db_session,
        user_id=uid,
        content="Previous employer was Acme Corp",
    )

    corr_id = uuid.uuid4()
    await MemoryService.forget_memory(
        db=db_session,
        memory_id=memory.id,
        user_id=uid,
        reason="User requested GDPR right-to-be-forgotten deletion",
        correlation_id=corr_id,
    )

    # Re-fetch
    refetched = await MemoryService.get_memory_by_id(db_session, memory.id, uid)
    assert refetched.status == "DELETED"
    assert refetched.history[-1].action == "DELETED"
    assert refetched.history[-1].correlation_id == corr_id


@pytest.mark.asyncio
async def test_memory_tenant_isolation(db_session):
    """Verify User A cannot access, confirm, or modify User B's memories."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    mem_a = await MemoryService.create_memory(
        db=db_session,
        user_id=user_a,
        content="User A private secret fact",
    )

    # User B attempting to fetch User A's memory gets PermissionDeniedError
    with pytest.raises(PermissionDeniedError):
        await MemoryService.get_memory_by_id(db_session, mem_a.id, user_b)

    # User B attempting to update User A's memory gets PermissionDeniedError
    with pytest.raises(PermissionDeniedError):
        await MemoryService.update_memory(
            db=db_session,
            memory_id=mem_a.id,
            user_id=user_b,
            new_content="Tampered content",
        )

    # User B attempting to forget User A's memory gets PermissionDeniedError
    with pytest.raises(PermissionDeniedError):
        await MemoryService.forget_memory(
            db=db_session,
            memory_id=mem_a.id,
            user_id=user_b,
            reason="Malicious deletion attempt",
        )


@pytest.mark.asyncio
async def test_semantic_search_ranking_and_filters(db_session):
    """Verify semantic search ranks relevant memories above irrelevant ones and respects privacy scopes."""
    uid = uuid.uuid4()

    # Memory 1: Green tea preference (Personal)
    mem1 = await MemoryService.create_memory(
        db=db_session,
        user_id=uid,
        content="User prefers drinking organic green tea every morning",
        privacy_scope="PERSONAL",
        sensitivity=20,
    )

    # Memory 2: Business revenue targets (Business)
    mem2 = await MemoryService.create_memory(
        db=db_session,
        user_id=uid,
        content="Quarterly revenue target is 5 million dollars",
        privacy_scope="BUSINESS",
        sensitivity=30,
    )

    # Memory 3: Expired gate code (Personal, but expired)
    now = datetime.now(timezone.utc)
    mem3 = await MemoryService.create_memory(
        db=db_session,
        user_id=uid,
        content="Gate code is 9988 for building access",
        privacy_scope="PERSONAL",
        valid_until=now - timedelta(days=1),  # Expired yesterday
    )

    # 1. Search for tea in PERSONAL scope -> mem1 matches, mem2 excluded by scope, mem3 excluded by expiry
    results_tea = await MemoryService.search_memories(
        db=db_session,
        user_id=uid,
        query="What tea does user drink in morning?",
        allowed_scopes=["PERSONAL"],
    )
    assert len(results_tea) >= 1
    top_mem, score = results_tea[0]
    assert top_mem.id == mem1.id
    assert score > 0.2

    # 2. Search for revenue in PERSONAL scope -> excluded because mem2 is BUSINESS
    results_business = await MemoryService.search_memories(
        db=db_session,
        user_id=uid,
        query="quarterly revenue target",
        allowed_scopes=["PERSONAL"],
    )
    assert len(results_business) == 0

    # 3. Search for revenue in BUSINESS scope -> mem2 found
    results_biz_allowed = await MemoryService.search_memories(
        db=db_session,
        user_id=uid,
        query="quarterly revenue target",
        allowed_scopes=["BUSINESS"],
    )
    assert len(results_biz_allowed) >= 1
    assert results_biz_allowed[0][0].id == mem2.id
