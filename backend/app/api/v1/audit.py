"""Audit ledger query and cryptographic verification API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["Audit Ledger"])


@router.get("", response_model=List[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[AuditLogResponse]:
    """Retrieve immutable, user-scoped audit log entries."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.sequence_number.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()

    return [
        AuditLogResponse(
            id=log.id,
            sequence_number=log.sequence_number,
            user_id=log.user_id,
            tool_name=log.tool_name,
            risk_class=log.risk_class,
            action_type=log.action_type,
            decision=log.decision,
            result_status=log.result_status,
            error_code=log.error_code,
            details=log.details,
            correlation_id=log.correlation_id,
            previous_hash=log.previous_hash,
            record_hash=log.record_hash,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/verify-chain")
async def verify_audit_chain(
    limit: int = Query(default=500, ge=1, le=5000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Verify cryptographic hash chaining across sequential audit logs."""
    is_valid, error = await AuditService.verify_chain(session=db, limit=limit)
    return {
        "is_valid": is_valid,
        "error": error,
        "verified_by": str(current_user.id),
    }
