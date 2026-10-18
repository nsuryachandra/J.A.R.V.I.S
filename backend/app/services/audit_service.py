"""Transaction-safe, concurrency-controlled append-only audit ledger service."""

import asyncio
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import mask_sensitive_data
from app.models.audit import AuditLedgerState, AuditLog, GENESIS_HASH

# Global asynchronous lock to serialize concurrent audit writes within the application process
_audit_write_lock = asyncio.Lock()


def calculate_record_hash(
    seq: int,
    prev_hash: str,
    action_type: str,
    decision: str,
    result_status: str,
    arguments_hash: Optional[str],
    details: Dict[str, Any],
) -> str:
    """Compute deterministic cryptographic SHA-256 hash for an audit record."""
    canonical_details = json.dumps(details, sort_keys=True, separators=(",", ":"))
    canonical_payload = (
        f"{seq}:{prev_hash}:{action_type}:{decision}:{result_status}:"
        f"{arguments_hash or ''}:{canonical_details}"
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


class AuditService:
    """Manages transaction-safe sequential insertion and cryptographic verification of audit records."""

    @classmethod
    async def record_event(
        cls,
        session: AsyncSession,
        action_type: str,
        decision: str,
        user_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        agent_run_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_version: Optional[str] = None,
        risk_class: Optional[str] = None,
        resource_scope: Optional[str] = None,
        arguments_hash: Optional[str] = None,
        approval_id: Optional[UUID] = None,
        result_status: str = "SUCCESS",
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditLog:
        """Atomically append an audit log row with deterministic sequential hash chaining."""
        sanitized_details = mask_sensitive_data(details or {})
        uid = UUID(str(user_id)) if user_id and not isinstance(user_id, UUID) else user_id
        sid = UUID(str(session_id)) if session_id and not isinstance(session_id, UUID) else session_id
        appr_id = UUID(str(approval_id)) if approval_id and not isinstance(approval_id, UUID) else approval_id

        async with _audit_write_lock:
            # Query or initialize ledger head row
            stmt = select(AuditLedgerState).where(AuditLedgerState.id == "PRIMARY_LEDGER")
            result = await session.execute(stmt)
            ledger_state = result.scalar_one_or_none()

            if ledger_state is None:
                ledger_state = AuditLedgerState(
                    id="PRIMARY_LEDGER",
                    sequence_number=0,
                    last_record_hash=GENESIS_HASH,
                )
                session.add(ledger_state)
                await session.flush()

            next_seq = ledger_state.sequence_number + 1
            prev_hash = ledger_state.last_record_hash

            record_hash = calculate_record_hash(
                seq=next_seq,
                prev_hash=prev_hash,
                action_type=action_type,
                decision=decision,
                result_status=result_status,
                arguments_hash=arguments_hash,
                details=sanitized_details,
            )

            audit_log = AuditLog(
                sequence_number=next_seq,
                user_id=uid,
                session_id=sid,
                agent_run_id=agent_run_id,
                tool_name=tool_name,
                tool_version=tool_version,
                risk_class=risk_class,
                action_type=action_type,
                resource_scope=resource_scope,
                arguments_hash=arguments_hash,
                approval_id=appr_id,
                decision=decision,
                result_status=result_status,
                error_code=error_code,
                details=sanitized_details,
                ip_address=ip_address,
                correlation_id=correlation_id,
                previous_hash=prev_hash,
                record_hash=record_hash,
            )
            session.add(audit_log)

            # Update ledger head state
            ledger_state.sequence_number = next_seq
            ledger_state.last_record_hash = record_hash
            await session.flush()

            return audit_log

    @classmethod
    async def verify_chain(
        cls, session: AsyncSession, limit: int = 1000
    ) -> Tuple[bool, Optional[str]]:
        """Verify cryptographic hash chaining across sequential audit logs."""
        stmt = select(AuditLog).order_by(AuditLog.sequence_number.asc()).limit(limit)
        result = await session.execute(stmt)
        logs: List[AuditLog] = list(result.scalars().all())

        if not logs:
            return True, None

        expected_prev_hash = GENESIS_HASH

        for log in logs:
            if log.previous_hash != expected_prev_hash:
                return (
                    False,
                    f"Chain break at seq {log.sequence_number}: expected previous_hash "
                    f"{expected_prev_hash}, found {log.previous_hash}",
                )

            recomputed_hash = calculate_record_hash(
                seq=log.sequence_number,
                prev_hash=log.previous_hash,
                action_type=log.action_type,
                decision=log.decision,
                result_status=log.result_status,
                arguments_hash=log.arguments_hash,
                details=log.details,
            )

            if log.record_hash != recomputed_hash:
                return (
                    False,
                    f"Tampered record at seq {log.sequence_number}: recomputed {recomputed_hash} != {log.record_hash}",
                )

            expected_prev_hash = log.record_hash

        return True, None
