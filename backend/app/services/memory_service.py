"""Domain service governing memory lifecycle, ingestion, semantic retrieval, and right-to-be-forgotten."""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.contracts.common import PrivacyScope, SensitivityLevel
from app.contracts.privacy import PrivacyPolicyEnforcer
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.base import utcnow
from app.models.memory import Memory, MemoryHistory
from app.services.audit_service import AuditService
from app.services.embedding_service import cosine_similarity, get_embedding_provider


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is offset-aware in UTC for safe comparisons and arithmetic."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class MemoryService:
    """Service orchestrating declarative memory operations, semantic search, and audit history."""

    @classmethod
    async def create_memory(
        cls,
        db: AsyncSession,
        user_id: UUID,
        content: str,
        memory_type: str = "SEMANTIC",
        confidence: float = 1.0,
        status: str = "ACTIVE",
        confirmed_by_user: bool = False,
        privacy_scope: str = "PERSONAL",
        sensitivity: int = 30,  # SensitivityLevel.PRIVATE.value
        source_type: str = "USER_DIRECT",
        source_id: Optional[str] = None,
        source_message_id: Optional[UUID] = None,
        provenance_evidence: Optional[str] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        session_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
    ) -> Memory:
        """Create and persist a new memory record with vector embeddings and audit tracking."""
        clean_content = content.strip()
        if not clean_content:
            raise ValidationError("Memory content cannot be empty.")

        if confidence < 0.0 or confidence > 1.0:
            raise ValidationError("Memory confidence must be between 0.0 and 1.0.")

        # Inferred memories cannot be created as confirmed without confirmation flag
        if source_type == "USER_INFERRED" and status in ("CONFIRMED", "ACTIVE") and not confirmed_by_user:
            # Force status to CANDIDATE
            status = "CANDIDATE"

        # Generate deterministic embedding vector
        embedding_provider = get_embedding_provider()
        embedding = embedding_provider.embed_text(clean_content)

        memory = Memory(
            user_id=user_id,
            memory_type=memory_type,
            content=clean_content,
            status=status,
            confidence=confidence,
            confirmed_by_user=confirmed_by_user,
            valid_from=valid_from or utcnow(),
            valid_until=valid_until,
            privacy_scope=privacy_scope,
            sensitivity=sensitivity,
            source_type=source_type,
            source_id=source_id,
            source_message_id=source_message_id,
            provenance_evidence=provenance_evidence,
            embedding_vector=embedding,
        )
        db.add(memory)
        await db.flush()

        # Record MemoryHistory entry
        history = MemoryHistory(
            memory_id=memory.id,
            user_id=user_id,
            action="CREATED",
            new_content=clean_content,
            reason="Initial ingestion",
            correlation_id=correlation_id,
        )
        db.add(history)

        # Audit log creation
        await AuditService.record_event(
            session=db,
            action_type="memory.create",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"memory:{memory.id}",
            details={
                "memory_id": str(memory.id),
                "type": memory_type,
                "status": status,
                "confidence": confidence,
                "privacy_scope": privacy_scope,
            },
        )
        await db.commit()
        return await cls.get_memory_by_id(db, memory.id, user_id)

    @classmethod
    async def get_memory_by_id(
        cls,
        db: AsyncSession,
        memory_id: UUID,
        user_id: UUID,
    ) -> Memory:
        """Fetch memory with strict user-tenant ownership enforcement."""
        stmt = (
            select(Memory)
            .where(Memory.id == memory_id)
            .options(selectinload(Memory.history))
            .execution_options(populate_existing=True)
        )
        res = await db.execute(stmt)
        memory = res.scalar_one_or_none()

        if memory is None:
            raise EntityNotFoundError("Memory", memory_id)

        if memory.user_id != user_id:
            # Strict tenant isolation
            raise PermissionDeniedError("Access denied: Memory belongs to another user.")

        return memory

    @classmethod
    async def confirm_memory(
        cls,
        db: AsyncSession,
        memory_id: UUID,
        user_id: UUID,
        session_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
    ) -> Memory:
        """Promote a candidate memory to ACTIVE upon user confirmation."""
        memory = await cls.get_memory_by_id(db, memory_id, user_id)

        old_status = memory.status
        memory.status = "ACTIVE"
        memory.confirmed_by_user = True
        memory.updated_at = utcnow()

        # Add history record
        history = MemoryHistory(
            memory_id=memory.id,
            user_id=user_id,
            action="CONFIRMED",
            previous_content=memory.content,
            new_content=memory.content,
            reason=f"Confirmed from status {old_status}",
            correlation_id=correlation_id,
        )
        db.add(history)

        await AuditService.record_event(
            session=db,
            action_type="memory.confirm",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"memory:{memory.id}",
            details={"memory_id": str(memory.id), "from_status": old_status, "to_status": "ACTIVE"},
        )
        await db.commit()
        return await cls.get_memory_by_id(db, memory.id, user_id)

    @classmethod
    async def update_memory(
        cls,
        db: AsyncSession,
        memory_id: UUID,
        user_id: UUID,
        new_content: Optional[str] = None,
        privacy_scope: Optional[str] = None,
        sensitivity: Optional[int] = None,
        valid_until: Optional[datetime] = None,
        session_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
    ) -> Memory:
        """Apply mutations to an existing memory with change tracking."""
        memory = await cls.get_memory_by_id(db, memory_id, user_id)
        prev_content = memory.content

        if new_content is not None:
            clean = new_content.strip()
            if not clean:
                raise ValidationError("Updated memory content cannot be empty.")
            memory.content = clean
            # Update embedding
            memory.embedding_vector = get_embedding_provider().embed_text(clean)

        if privacy_scope is not None:
            memory.privacy_scope = privacy_scope

        if sensitivity is not None:
            memory.sensitivity = sensitivity

        if valid_until is not None:
            memory.valid_until = valid_until

        memory.updated_at = utcnow()

        history = MemoryHistory(
            memory_id=memory.id,
            user_id=user_id,
            action="UPDATED",
            previous_content=prev_content,
            new_content=memory.content,
            reason="User/Agent update",
            correlation_id=correlation_id,
        )
        db.add(history)

        await AuditService.record_event(
            session=db,
            action_type="memory.update",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"memory:{memory.id}",
            details={"memory_id": str(memory.id), "content_changed": new_content is not None},
        )
        await db.commit()
        return await cls.get_memory_by_id(db, memory.id, user_id)

    @classmethod
    async def correct_memory(
        cls,
        db: AsyncSession,
        memory_id: UUID,
        user_id: UUID,
        corrected_content: str,
        reason: str,
        session_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
    ) -> Tuple[Memory, Memory]:
        """Supersede an existing memory with an authoritative corrected version."""
        existing = await cls.get_memory_by_id(db, memory_id, user_id)

        clean_corrected = corrected_content.strip()
        if not clean_corrected:
            raise ValidationError("Corrected content cannot be empty.")

        # Create new corrected memory record
        new_memory = await cls.create_memory(
            db=db,
            user_id=user_id,
            content=clean_corrected,
            memory_type=existing.memory_type,
            confidence=1.0,
            status="ACTIVE",
            confirmed_by_user=True,
            privacy_scope=existing.privacy_scope,
            sensitivity=existing.sensitivity,
            source_type="USER_DIRECT",
            provenance_evidence=f"Correction of {existing.id}: {reason}",
            session_id=session_id,
            correlation_id=correlation_id,
        )

        # Mark existing memory as SUPERSEDED
        existing.status = "SUPERSEDED"
        existing.superseded_by_id = new_memory.id
        existing.updated_at = utcnow()

        history = MemoryHistory(
            memory_id=existing.id,
            user_id=user_id,
            action="CORRECTED",
            previous_content=existing.content,
            new_content=clean_corrected,
            reason=f"Superseded by {new_memory.id}: {reason}",
            correlation_id=correlation_id,
        )
        db.add(history)

        await AuditService.record_event(
            session=db,
            action_type="memory.correct",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"memory:{existing.id}",
            details={"superseded_memory_id": str(existing.id), "new_memory_id": str(new_memory.id)},
        )
        await db.commit()
        refreshed_existing = await cls.get_memory_by_id(db, existing.id, user_id)
        return refreshed_existing, new_memory

    @classmethod
    async def forget_memory(
        cls,
        db: AsyncSession,
        memory_id: UUID,
        user_id: UUID,
        reason: str,
        session_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
    ) -> None:
        """Right-to-be-forgotten deletion with audit compliance."""
        memory = await cls.get_memory_by_id(db, memory_id, user_id)

        prev_content = memory.content
        memory.status = "DELETED"
        memory.updated_at = utcnow()

        history = MemoryHistory(
            memory_id=memory.id,
            user_id=user_id,
            action="DELETED",
            previous_content=prev_content,
            new_content=None,
            reason=reason,
            correlation_id=correlation_id,
        )
        db.add(history)

        await AuditService.record_event(
            session=db,
            action_type="memory.forget",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"memory:{memory.id}",
            details={"memory_id": str(memory.id), "reason": reason},
        )
        await db.commit()

    @classmethod
    async def search_memories(
        cls,
        db: AsyncSession,
        user_id: UUID,
        query: str,
        memory_type: Optional[str] = None,
        allowed_scopes: Optional[List[str]] = None,
        max_sensitivity: int = 30,  # SensitivityLevel.PRIVATE
        limit: int = 10,
        threshold: float = 0.15,
    ) -> List[Tuple[Memory, float]]:
        """
        Hybrid semantic retrieval with strict user isolation, privacy scope filtering,
        recency decay, and similarity ranking.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # Query all active, unexpired memories for this user
        now = utcnow()
        stmt = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.status == "ACTIVE",
            )
        )
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)

        res = await db.execute(stmt)
        candidates = res.scalars().all()

        # Compute query embedding
        query_vec = get_embedding_provider().embed_text(clean_query)
        scopes = allowed_scopes or ["PERSONAL", "CONVERSATION"]

        results: List[Tuple[Memory, float]] = []

        query_tokens = set(re_tokens(clean_query))

        for mem in candidates:
            # Filter expired
            valid_until_utc = ensure_utc(mem.valid_until)
            if valid_until_utc and valid_until_utc < now:
                continue

            # Filter privacy scope
            if mem.privacy_scope not in scopes:
                continue

            # Filter sensitivity ceiling
            if mem.sensitivity > max_sensitivity:
                continue

            # Compute semantic vector similarity
            mem_vec = mem.embedding_vector or []
            sim = cosine_similarity(query_vec, mem_vec)

            # Keyword overlap boost
            content_tokens = set(re_tokens(mem.content))
            common = query_tokens.intersection(content_tokens)
            keyword_bonus = min(0.3, len(common) * 0.1)

            # If there is neither semantic similarity nor keyword overlap, it is completely irrelevant
            if sim <= 0.05 and keyword_bonus <= 0.0:
                continue

            # Recency decay (half-life ~60 days)
            updated_at_utc = ensure_utc(mem.updated_at) or now
            delta_days = max(0.0, (now - updated_at_utc).total_seconds() / 86400.0)
            recency_factor = math.exp(-delta_days / 60.0)

            # Hybrid score composition
            score = (
                0.60 * sim
                + 0.20 * keyword_bonus
                + 0.10 * mem.confidence
                + 0.10 * recency_factor
            )

            if score >= threshold:
                results.append((mem, float(score)))

        # Sort descending by composite score
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]


def re_tokens(text: str) -> List[str]:
    """Helper tokenizer for keyword overlap scoring."""
    import re
    return re.findall(r"\w+", text.lower())
