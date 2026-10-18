"""API v1 router."""

from fastapi import APIRouter
from app.api.v1.approvals import router as approvals_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.events import router as events_router
from app.api.v1.health import router as health_router
from app.api.v1.memories import router as memories_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.temporal import router as temporal_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router, tags=["Health"])
api_v1_router.include_router(auth_router)
api_v1_router.include_router(approvals_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(temporal_router)
api_v1_router.include_router(memories_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(events_router)

__all__ = ["api_v1_router"]

